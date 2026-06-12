from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PIPELINE_ROOT.parent
CLEAN_CSV = PIPELINE_ROOT / "data" / "clean" / "toll_stations_clean.csv"
TABLE_NAME = "toll_stations"


def clean(value: object) -> str:
    return str(value or "").strip()


def sql_text(value: object, *, null_if_empty: bool = False) -> str:
    text = clean(value)
    if null_if_empty and not text:
        return "NULL"
    return "'" + text.replace("'", "''") + "'"


def sql_number(value: object) -> str:
    text = clean(value)
    if not text:
        return "NULL"
    return str(float(text))


def tags_json(row: dict[str, str]) -> str:
    raw_tags = clean(row.get("tags"))
    tags: dict[str, object] = {}
    if raw_tags:
        for item in raw_tags.split(";"):
            if "=" in item:
                key, value = item.split("=", 1)
                tags[key.strip()] = value.strip()

    tags.update(
        {
            "payment": "etc",
            "barrier": "toll_booth",
            "toll": "yes",
            "payment:etc": "yes",
            "source_datasets": row.get("source_datasets"),
            "osm_id": row.get("osm_id"),
            "osm_name": row.get("osm_name"),
            "status": row.get("status"),
            "status_note": row.get("status_note"),
            "clean_status": row.get("clean_status"),
            "needs_manual_fields": row.get("needs_manual_fields"),
            "merged_from_candidate_ids": row.get("merged_from_candidate_ids"),
            "thumbnail": row.get("thumbnail"),
            "image_url": row.get("image_url"),
        }
    )
    return json.dumps(tags, ensure_ascii=False)


def create_table_sql() -> str:
    return f"""
create extension if not exists postgis;

drop table if exists {TABLE_NAME};
drop table if exists toll_stations_clean;

create table {TABLE_NAME} (
    id text primary key,
    name text not null,
    address text,
    province text,
    road text,
    operator text,
    source_datasets text,
    source_original_id text,
    candidate_id text,
    source_url text,
    thumbnail text,
    image_url text,
    google_place_id text,
    google_cid text,
    osm_id text,
    osm_name text,
    confidence numeric(4, 2),
    status text not null default 'active',
    status_note text,
    tags jsonb not null default '{{}}'::jsonb,
    clean_status text,
    needs_manual_fields text,
    geom geometry(Point, 4326) not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index {TABLE_NAME}_geom_idx on {TABLE_NAME} using gist (geom);
create index {TABLE_NAME}_tags_idx on {TABLE_NAME} using gin (tags);
"""


def insert_statement(row: dict[str, str]) -> str:
    lon = float(row["lon"])
    lat = float(row["lat"])
    return f"""
insert into {TABLE_NAME} (
    id, name, address, province, road, operator, source_datasets,
    source_original_id, candidate_id, source_url, thumbnail, image_url, google_place_id, google_cid,
    osm_id, osm_name, confidence, status, status_note, tags, clean_status, needs_manual_fields,
    geom, updated_at
) values (
    {sql_text(row.get("id"))},
    {sql_text(row.get("name"))},
    {sql_text(row.get("address"), null_if_empty=True)},
    {sql_text(row.get("province"), null_if_empty=True)},
    {sql_text(row.get("road"), null_if_empty=True)},
    {sql_text(row.get("operator"), null_if_empty=True)},
    {sql_text(row.get("source_datasets"), null_if_empty=True)},
    {sql_text(row.get("source_original_id"), null_if_empty=True)},
    {sql_text(row.get("candidate_id"), null_if_empty=True)},
    {sql_text(row.get("source_url"), null_if_empty=True)},
    {sql_text(row.get("thumbnail"), null_if_empty=True)},
    {sql_text(row.get("image_url"), null_if_empty=True)},
    {sql_text(row.get("google_place_id"), null_if_empty=True)},
    {sql_text(row.get("google_cid"), null_if_empty=True)},
    {sql_text(row.get("osm_id"), null_if_empty=True)},
    {sql_text(row.get("osm_name"), null_if_empty=True)},
    {sql_number(row.get("confidence"))},
    {sql_text(row.get("status") or "active")},
    {sql_text(row.get("status_note"), null_if_empty=True)},
    {sql_text(tags_json(row))}::jsonb,
    {sql_text(row.get("clean_status"), null_if_empty=True)},
    {sql_text(row.get("needs_manual_fields"), null_if_empty=True)},
    ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326),
    now()
);
"""


def run_psql(sql: str) -> None:
    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "maps_vietnam",
        ],
        cwd=PROJECT_ROOT,
        input=sql,
        text=True,
        encoding="utf-8",
        check=True,
    )


def main() -> None:
    with CLEAN_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    valid_rows = [row for row in rows if clean(row.get("lat")) and clean(row.get("lon"))]
    sql_parts = [create_table_sql()]
    sql_parts.extend(insert_statement(row) for row in valid_rows)
    sql_parts.append(f"select count(*) as {TABLE_NAME}_inserted from {TABLE_NAME};")
    run_psql("\n".join(sql_parts))
    print(f"Inserted {len(valid_rows)} clean toll stations into {TABLE_NAME}.")


if __name__ == "__main__":
    main()
