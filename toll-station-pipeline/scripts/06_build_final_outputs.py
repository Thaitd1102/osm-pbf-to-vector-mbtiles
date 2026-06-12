import csv
import json
import sqlite3
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
MATCHED_FILE = PIPELINE_ROOT / "data" / "matched" / "gmaps_matched.json"
NAME_UPDATES_FILE = PIPELINE_ROOT / "data" / "report" / "merged_osm_name_updates.csv"
ISSUE_REVIEW_FILE = PIPELINE_ROOT / "data" / "report" / "gmaps_issue_review_clean.csv"
FINAL_DIR = PIPELINE_ROOT / "data" / "final"
DB_FILE = PIPELINE_ROOT / "db" / "tolls.db"
FINAL_JSON_FILE = FINAL_DIR / "merged_toll_stations_final.json"
FINAL_CSV_FILE = FINAL_DIR / "merged_toll_stations_final.csv"
FINAL_GEOJSON_FILE = FINAL_DIR / "merged_toll_stations_final.geojson"


KEEP_STATUSES = {"matched", "name_mismatch"}
GOOD_REVIEW_DECISIONS = {
    "create_new_osm_toll_booth",
    "keep_google_coordinates",
    "keep_corrected_coordinates",
    "fix_osm_tags",
}


def clean(value: object) -> str:
    return str(value or "").strip()


def load_json(path: Path) -> list[dict]:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def as_float(value: object) -> float | None:
    text = clean(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def record_key(record: dict) -> str:
    return clean(record.get("google_place_id")) or clean(record.get("id"))


def base_station(record: dict, final_name: str | None = None) -> dict:
    match = record.get("match") or {}
    osm = match.get("osm_match") or {}
    name = normalize_final_name(final_name or clean(record.get("name")))
    lat = as_float(record.get("lat"))
    lon = as_float(record.get("lon"))

    return {
        "id": record.get("id"),
        "name": name,
        "province": record.get("province") or "",
        "road": record.get("road") or "",
        "km_marker": record.get("km_marker") or "",
        "type": "toll_booth",
        "operator": record.get("operator") or "",
        "status": record.get("status") or "active",
        "lat": lat,
        "lon": lon,
        "source": "google_maps_scraper",
        "source_url": record.get("source_url") or "",
        "confidence": record.get("confidence") or 0.8,
        "google_place_id": record.get("google_place_id") or "",
        "google_cid": record.get("google_cid") or "",
        "category": record.get("category") or "",
        "formatted_address": record.get("formatted_address") or "",
        "osm_id": clean(osm.get("osm_id") or osm.get("id")),
        "osm_name": clean(osm.get("name")),
        "osm_lat": as_float(osm.get("lat")),
        "osm_lon": as_float(osm.get("lon")),
        "osm_distance_m": as_float(osm.get("distance_m")),
        "final_status": "reviewed_valid",
        "review_action": "",
        "review_comment": "",
        "tags": "barrier=toll_booth;toll=yes;payment:etc=yes",
    }


def issue_station(row: dict) -> dict:
    lat = as_float(row.get("corrected_lat")) or as_float(row.get("google_lat"))
    lon = as_float(row.get("corrected_lon")) or as_float(row.get("google_lon"))
    name = normalize_final_name(clean(row.get("corrected_name")) or clean(row.get("google_name")))
    decision = clean(row.get("review_decision"))

    station_id = clean(row.get("google_place_id")) or clean(row.get("osm_id")) or name
    station = {
        "id": f"final-{station_id}",
        "name": name,
        "province": "",
        "road": "",
        "km_marker": "",
        "type": "toll_booth",
        "operator": "",
        "status": "active",
        "lat": lat,
        "lon": lon,
        "source": "google_maps_scraper",
        "source_url": row.get("google_source_url") or "",
        "confidence": 0.8,
        "google_place_id": row.get("google_place_id") or "",
        "google_cid": "",
        "category": row.get("google_category") or "",
        "formatted_address": "",
        "osm_id": row.get("osm_id") or "",
        "osm_name": row.get("osm_current_name") or "",
        "osm_lat": as_float(row.get("osm_lat")),
        "osm_lon": as_float(row.get("osm_lon")),
        "osm_distance_m": as_float(row.get("osm_distance_m")),
        "final_status": "reviewed_valid",
        "review_action": decision,
        "review_comment": row.get("review_comment") or "",
        "tags": "barrier=toll_booth;toll=yes;payment:etc=yes",
    }
    if decision == "fix_osm_tags":
        station["lat"] = station["osm_lat"] or lat
        station["lon"] = station["osm_lon"] or lon
    return station


def normalize_final_name(name: str) -> str:
    # Google Maps sometimes prepends unrelated business/category text to a real toll station name.
    for prefix in ("Nhà đất ",):
        if name.startswith(prefix):
            return name[len(prefix):].strip()
    return name


def to_feature(station: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [station["lon"], station["lat"]],
        },
        "properties": {
            key: value
            for key, value in station.items()
            if key not in {"lat", "lon"}
        },
    }


def write_csv(stations: list[dict], path: Path) -> None:
    fields = [
        "id",
        "name",
        "province",
        "road",
        "km_marker",
        "type",
        "operator",
        "status",
        "lat",
        "lon",
        "source",
        "source_url",
        "confidence",
        "google_place_id",
        "google_cid",
        "category",
        "formatted_address",
        "osm_id",
        "osm_name",
        "osm_lat",
        "osm_lon",
        "osm_distance_m",
        "final_status",
        "review_action",
        "review_comment",
        "tags",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(stations)


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS toll_stations")
    conn.execute("""
        CREATE TABLE toll_stations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            province TEXT,
            road TEXT,
            km_marker TEXT,
            type TEXT,
            operator TEXT,
            status TEXT,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            source TEXT,
            source_url TEXT,
            confidence REAL,
            google_place_id TEXT,
            google_cid TEXT,
            category TEXT,
            formatted_address TEXT,
            osm_id TEXT,
            osm_name TEXT,
            osm_lat REAL,
            osm_lon REAL,
            osm_distance_m REAL,
            final_status TEXT,
            review_action TEXT,
            review_comment TEXT,
            tags TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


def save_db(stations: list[dict]) -> None:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    init_db(conn)
    fields = [
        "id",
        "name",
        "province",
        "road",
        "km_marker",
        "type",
        "operator",
        "status",
        "lat",
        "lon",
        "source",
        "source_url",
        "confidence",
        "google_place_id",
        "google_cid",
        "category",
        "formatted_address",
        "osm_id",
        "osm_name",
        "osm_lat",
        "osm_lon",
        "osm_distance_m",
        "final_status",
        "review_action",
        "review_comment",
        "tags",
    ]
    placeholders = ", ".join([f":{field}" for field in fields])
    conn.executemany(
        f"INSERT INTO toll_stations ({', '.join(fields)}) VALUES ({placeholders})",
        stations,
    )
    conn.commit()
    conn.close()


def main() -> None:
    matched_records = load_json(MATCHED_FILE)
    if not matched_records and FINAL_JSON_FILE.exists():
        stations = load_json(FINAL_JSON_FILE)
        save_db(stations)
        summary = {
            "final_station_count": len(stations),
            "db_path": str(DB_FILE.relative_to(PIPELINE_ROOT)),
            "csv_path": str(FINAL_CSV_FILE.relative_to(PIPELINE_ROOT)),
            "geojson_path": str(FINAL_GEOJSON_FILE.relative_to(PIPELINE_ROOT)),
            "json_path": str(FINAL_JSON_FILE.relative_to(PIPELINE_ROOT)),
            "note": "Reused existing final dataset and refreshed SQLite DB.",
        }
        (FINAL_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    name_updates_by_place = {
        clean(row.get("google_place_id")): clean(row.get("new_osm_name"))
        for row in load_csv(NAME_UPDATES_FILE)
        if clean(row.get("google_place_id")) and clean(row.get("new_osm_name"))
    }

    stations_by_key = {}
    for record in matched_records:
        match_status = clean((record.get("match") or {}).get("status"))
        if match_status not in KEEP_STATUSES:
            continue
        key = record_key(record)
        final_name = name_updates_by_place.get(clean(record.get("google_place_id"))) or clean(record.get("name"))
        station = base_station(record, final_name)
        if station["lat"] is not None and station["lon"] is not None:
            stations_by_key[key] = station

    for row in load_csv(ISSUE_REVIEW_FILE):
        decision = clean(row.get("review_decision"))
        if decision == "duplicate":
            continue
        if decision not in GOOD_REVIEW_DECISIONS:
            continue
        station = issue_station(row)
        if station["lat"] is not None and station["lon"] is not None:
            stations_by_key[clean(row.get("google_place_id")) or station["id"]] = station

    stations = sorted(stations_by_key.values(), key=lambda item: (item["name"], item["lat"], item["lon"]))
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    FINAL_JSON_FILE.write_text(
        json.dumps(stations, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(stations, FINAL_CSV_FILE)
    FINAL_GEOJSON_FILE.write_text(
        json.dumps({
            "type": "FeatureCollection",
            "features": [to_feature(station) for station in stations],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary = {
        "final_station_count": len(stations),
        "db_path": str(DB_FILE.relative_to(PIPELINE_ROOT)),
        "csv_path": str(FINAL_CSV_FILE.relative_to(PIPELINE_ROOT)),
        "geojson_path": str(FINAL_GEOJSON_FILE.relative_to(PIPELINE_ROOT)),
        "json_path": str(FINAL_JSON_FILE.relative_to(PIPELINE_ROOT)),
        "note": "Final dataset excludes manual duplicate rows and includes reviewed name/tag/location fixes.",
    }
    (FINAL_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    save_db(stations)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
