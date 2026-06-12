import json
import subprocess
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PIPELINE_ROOT.parent
FINAL_JSON_FILE = PIPELINE_ROOT / "data" / "final" / "merged_toll_stations_final.json"


def clean(value: object) -> str:
    return str(value or "").strip()


def sql_text(value: object, *, null_if_empty: bool = False) -> str:
    text = clean(value)
    if null_if_empty and not text:
        return "NULL"
    return "'" + text.replace("'", "''") + "'"


def sql_number(value: object) -> str:
    if value is None or value == "":
        return "NULL"
    return str(float(value))


def station_tags(station: dict) -> dict:
    return {
        "type": station.get("type"),
        "operator": station.get("operator"),
        "status": station.get("status"),
        "road": station.get("road"),
        "km_marker": station.get("km_marker"),
        "category": station.get("category"),
        "osm_id": station.get("osm_id"),
        "osm_name": station.get("osm_name"),
        "osm_distance_m": station.get("osm_distance_m"),
        "final_status": station.get("final_status"),
        "review_action": station.get("review_action"),
        "review_comment": station.get("review_comment"),
        "payment": "etc",
        "barrier": "toll_booth",
        "toll": "yes",
        "payment:etc": "yes",
    }


def insert_statement(station: dict) -> str:
    tags = json.dumps(station_tags(station), ensure_ascii=False)
    lon = float(station["lon"])
    lat = float(station["lat"])
    confidence = station.get("confidence")

    return f"""
insert into toll_stations (
    name, address, source, source_query, google_place_id, google_maps_uri,
    confidence, tags, geom, updated_at
) values (
    {sql_text(station.get("name"))},
    {sql_text(station.get("formatted_address"), null_if_empty=True)},
    {sql_text(station.get("source") or "google_maps_scraper")},
    NULL,
    {sql_text(station.get("google_place_id"), null_if_empty=True)},
    {sql_text(station.get("source_url"), null_if_empty=True)},
    {sql_number(confidence)},
    {sql_text(tags)}::jsonb,
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
    stations = json.loads(FINAL_JSON_FILE.read_text(encoding="utf-8"))
    valid = [station for station in stations if station.get("lat") is not None and station.get("lon") is not None]

    sql_parts = [
        "create extension if not exists postgis;",
        "truncate table toll_stations restart identity;",
    ]
    sql_parts.extend(insert_statement(station) for station in valid)
    sql_parts.append("select count(*) as toll_stations_inserted from toll_stations;")
    run_psql("\n".join(sql_parts))

    print(f"Inserted {len(valid)} toll stations into PostgreSQL/PostGIS.")


if __name__ == "__main__":
    main()
