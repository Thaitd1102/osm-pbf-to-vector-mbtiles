from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

import psycopg


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:110204@postgres:5432/maps_vietnam",
)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def upsert_job(payload: dict[str, Any]) -> None:
    created_at = payload.get("created_at") or now_iso()
    updated_at = payload.get("updated_at") or now_iso()
    with psycopg.connect(DATABASE_URL) as connection:
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
