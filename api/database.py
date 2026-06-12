from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:110204@postgres:5432/maps_vietnam",
)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def connect():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_database() -> None:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("create extension if not exists postgis")
            cursor.execute(
                """
                create table if not exists osm_versions (
                    name text primary key,
                    size_bytes bigint not null,
                    modified_at timestamptz not null,
                    path text,
                    updated_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                """
                create table if not exists pipeline_jobs (
                    id text primary key,
                    state text not null,
                    progress integer not null default 0,
                    message text not null default '',
                    request jsonb,
                    output_url text,
                    patched_pbf_url text,
                    diff_geojson_url text,
                    mbtiles_url text,
                    preview_url text,
                    cache jsonb,
                    error text,
                    created_at timestamptz not null default now(),
                    updated_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                """
                create table if not exists toll_stations (
                    id bigserial primary key,
                    name text not null,
                    address text,
                    source text not null,
                    source_query text,
                    google_place_id text unique,
                    google_maps_uri text,
                    confidence numeric(4, 2),
                    tags jsonb not null default '{}'::jsonb,
                    geom geometry(Point, 4326) not null,
                    created_at timestamptz not null default now(),
                    updated_at timestamptz not null default now()
                )
                """
            )
            cursor.execute(
                "create index if not exists toll_stations_geom_idx on toll_stations using gist (geom)"
            )
            cursor.execute(
                "create index if not exists toll_stations_tags_idx on toll_stations using gin (tags)"
            )
        connection.commit()


def upsert_version(version: dict[str, Any]) -> None:
    with connect() as connection:
        connection.execute(
            """
            insert into osm_versions (name, size_bytes, modified_at, path, updated_at)
            values (%s, %s, %s, %s, now())
            on conflict (name) do update set
                size_bytes = excluded.size_bytes,
                modified_at = excluded.modified_at,
                path = excluded.path,
                updated_at = now()
            """,
            (
                version["name"],
                version["size"],
                version["modified_at"],
                version.get("path"),
            ),
        )
        connection.commit()


def upsert_job(payload: dict[str, Any]) -> None:
    created_at = payload.get("created_at") or now_iso()
    updated_at = payload.get("updated_at") or now_iso()
    with connect() as connection:
        connection.execute(
            """
            insert into pipeline_jobs (
                id, state, progress, message, request, output_url, patched_pbf_url,
                diff_geojson_url, mbtiles_url, preview_url, cache, error,
                created_at, updated_at
            )
            values (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
            on conflict (id) do update set
                state = excluded.state,
                progress = excluded.progress,
                message = excluded.message,
                request = excluded.request,
                output_url = excluded.output_url,
                patched_pbf_url = excluded.patched_pbf_url,
                diff_geojson_url = excluded.diff_geojson_url,
                mbtiles_url = excluded.mbtiles_url,
                preview_url = excluded.preview_url,
                cache = excluded.cache,
                error = excluded.error,
                updated_at = excluded.updated_at
            """,
            (
                payload["id"],
                payload.get("state", "queued"),
                int(payload.get("progress", 0)),
                payload.get("message", ""),
                json.dumps(payload.get("request")) if payload.get("request") is not None else None,
                payload.get("output_url"),
                payload.get("patched_pbf_url"),
                payload.get("diff_geojson_url"),
                payload.get("mbtiles_url"),
                payload.get("preview_url"),
                json.dumps(payload.get("cache")) if payload.get("cache") is not None else None,
                payload.get("error"),
                created_at,
                updated_at,
            ),
        )
        connection.commit()


def get_job_from_database(job_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute("select * from pipeline_jobs where id = %s", (job_id,)).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "state": row["state"],
        "progress": row["progress"],
        "message": row["message"],
        "request": row["request"],
        "output_url": row["output_url"],
        "patched_pbf_url": row["patched_pbf_url"],
        "diff_geojson_url": row["diff_geojson_url"],
        "mbtiles_url": row["mbtiles_url"],
        "preview_url": row["preview_url"],
        "cache": row["cache"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        "error": row["error"],
    }


def get_latest_done_job_from_database() -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            select *
            from pipeline_jobs
            where state = 'done'
            order by updated_at desc
            limit 1
            """
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "state": row["state"],
        "progress": row["progress"],
        "message": row["message"],
        "request": row["request"],
        "output_url": row["output_url"],
        "patched_pbf_url": row["patched_pbf_url"],
        "diff_geojson_url": row["diff_geojson_url"],
        "mbtiles_url": row["mbtiles_url"],
        "preview_url": row["preview_url"],
        "cache": row["cache"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        "error": row["error"],
    }


def list_done_jobs_from_database(limit: int = 50) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            select *
            from pipeline_jobs
            where state = 'done'
            order by updated_at desc
            limit %s
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "state": row["state"],
            "progress": row["progress"],
            "message": row["message"],
            "request": row["request"],
            "output_url": row["output_url"],
            "patched_pbf_url": row["patched_pbf_url"],
            "diff_geojson_url": row["diff_geojson_url"],
            "mbtiles_url": row["mbtiles_url"],
            "preview_url": row["preview_url"],
            "cache": row["cache"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            "error": row["error"],
        }
        for row in rows
    ]


def database_status() -> dict[str, Any]:
    init_database()
    with connect() as connection:
        row = connection.execute(
            """
            select
                (select count(*) from osm_versions) as versions,
                (select count(*) from pipeline_jobs) as jobs,
                (select count(*) from toll_stations) as toll_stations
            """
        ).fetchone()
    return {"connected": True, **dict(row)}
