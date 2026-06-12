import json
import csv
from pathlib import Path
from datetime import datetime, timezone


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
MATCHED_DIR = PIPELINE_ROOT / "data" / "matched"
REPORT_DIR = PIPELINE_ROOT / "data" / "report"
REJECTED_DIR = PIPELINE_ROOT / "data" / "rejected"
REPORT_STATUSES = {
    "matched": "matched.geojson",
    "missing_in_osm": "missing.geojson",
    "location_mismatch": "wrong_location.geojson",
    "tag_mismatch": "tag_mismatch.geojson",
    "name_mismatch": "name_mismatch.geojson",
    "duplicate_candidate": "duplicate_candidate.geojson",
}
SOURCE_PREFIX = {
    "google_maps_scraper": "gmaps",
}

# ── Helpers ──────────────────────────────────────────────────
def to_feature(station: dict, extra_props: dict | None = None) -> dict | None:
    """Chuyển 1 station thành GeoJSON Feature."""
    extra_props = extra_props or {}
    lat = station.get("snapped_lat") or station.get("lat")
    lon = station.get("snapped_lon") or station.get("lon")

    if not lat or not lon:
        return None

    match = station.get("match") or {}
    osm = match.get("osm_match") or {}

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat]
        },
        "properties": {
            "id":         station.get("id"),
            "name":       station.get("name"),
            "province":   station.get("province"),
            "road":       station.get("road"),
            "type":       station.get("type"),
            "operator":   station.get("operator"),
            "status":     station.get("status"),
            "lat":        lat,
            "lon":        lon,
            "confidence": station.get("confidence"),
            "source":     station.get("source"),
            "source_url": station.get("source_url"),
            "coordinate_source": station.get("coordinate_source"),
            "coordinate_confidence": station.get("coordinate_confidence"),
            "coordinate_note": station.get("coordinate_note"),
            "match_status":  match.get("status"),
            "match_reason":  match.get("reason"),
            "osm_id": osm.get("osm_id") or osm.get("id"),
            "osm_name": osm.get("name"),
            "osm_lat": osm.get("lat"),
            "osm_lon": osm.get("lon"),
            "osm_distance_m": osm.get("distance_m"),
            **extra_props
        }
    }

def write_geojson(features: list, path: Path):
    features = [f for f in features if f is not None]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "type": "FeatureCollection",
            "features": features
        }, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"  Written {len(features)} features -> {path}")

def write_csv(stations: list, path: Path):
    fields = [
        "id", "name", "province", "road", "km_marker",
        "type", "operator", "status", "lat", "lon",
        "confidence", "source", "source_url", "coordinate_source",
        "coordinate_confidence", "coordinate_note", "match_status", "match_reason",
        "osm_id", "osm_name", "osm_distance_m",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()

        for s in stations:
            match = s.get("match") or {}
            osm   = match.get("osm_match") or {}
            writer.writerow({
                **s,
                "match_status":  match.get("status"),
                "match_reason":  match.get("reason"),
                "osm_id":        osm.get("osm_id"),
                "osm_name":      osm.get("name"),
                "osm_distance_m": osm.get("distance_m"),
            })

    print(f"  Written {len(stations)} rows -> {path}")


def load_rejected_stations(rejected_dir: Path) -> list[dict]:
    stations = []
    if not rejected_dir.exists():
        return stations
    for path in sorted(rejected_dir.glob("*_rejected.json")):
        records = json.loads(path.read_text(encoding="utf-8"))
        for item in records:
            item["_rejected_file"] = path.name
            stations.append(item)
    return stations


def write_gmaps_review_csv(matched_stations: list[dict], rejected_stations: list[dict], path: Path):
    fields = [
        "review_decision",
        "review_comment",
        "id",
        "name",
        "category",
        "province",
        "road",
        "lat",
        "lon",
        "confidence",
        "match_status",
        "match_reason",
        "reject_reason",
        "review_note",
        "osm_id",
        "osm_name",
        "osm_distance_m",
        "google_place_id",
        "google_cid",
        "source_url",
    ]

    rows = []
    for station in matched_stations:
        match = station.get("match") or {}
        osm = match.get("osm_match") or {}
        rows.append({
            "review_decision": "",
            "review_comment": "",
            "id": station.get("id"),
            "name": station.get("name"),
            "category": station.get("category"),
            "province": station.get("province"),
            "road": station.get("road"),
            "lat": station.get("lat"),
            "lon": station.get("lon"),
            "confidence": station.get("confidence"),
            "match_status": match.get("status"),
            "match_reason": match.get("reason"),
            "reject_reason": "",
            "review_note": station.get("review_note"),
            "osm_id": osm.get("osm_id") or osm.get("id"),
            "osm_name": osm.get("name"),
            "osm_distance_m": osm.get("distance_m"),
            "google_place_id": station.get("google_place_id"),
            "google_cid": station.get("google_cid"),
            "source_url": station.get("source_url"),
        })

    for station in rejected_stations:
        match = station.get("match") or {}
        rows.append({
            "review_decision": "reject",
            "review_comment": "",
            "id": station.get("id"),
            "name": station.get("name"),
            "category": station.get("category"),
            "province": station.get("province"),
            "road": station.get("road"),
            "lat": station.get("lat"),
            "lon": station.get("lon"),
            "confidence": station.get("confidence"),
            "match_status": match.get("status") or "rejected_by_quality",
            "match_reason": match.get("reason"),
            "reject_reason": station.get("reject_reason"),
            "review_note": station.get("review_note"),
            "osm_id": "",
            "osm_name": "",
            "osm_distance_m": "",
            "google_place_id": station.get("google_place_id"),
            "google_cid": station.get("google_cid"),
            "source_url": station.get("source_url"),
        })

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Written {len(rows)} rows -> {path}")


def load_matched_stations(matched_dir: Path) -> list[dict]:
    stations = []
    for path in sorted(matched_dir.glob("*_matched.json")):
        if path.name == "summary.json":
            continue
        records = json.loads(path.read_text(encoding="utf-8"))
        for item in records:
            item["_matched_file"] = path.name
            stations.append(item)
    return stations


def status_buckets(stations: list[dict]) -> dict[str, list[dict]]:
    buckets = {
        "matched":            [],
        "missing_in_osm":     [],
        "location_mismatch":  [],
        "tag_mismatch":       [],
        "name_mismatch":      [],
        "duplicate_candidate":[],
        "no_coordinates":     [],
    }
    for station in stations:
        status = station.get("match", {}).get("status", "no_coordinates")
        buckets.setdefault(status, []).append(station)
    return buckets


def write_status_geojsons(buckets: dict[str, list[dict]], output_dir: Path, prefix: str = "") -> dict[str, str]:
    def name(file_name: str) -> str:
        return f"{prefix}_{file_name}" if prefix else file_name

    files = {
        "matched": name("matched.geojson"),
        "missing_in_osm": name("missing.geojson"),
        "location_mismatch": name("wrong_location.geojson"),
        "tag_mismatch": name("tag_mismatch.geojson"),
        "name_mismatch": name("name_mismatch.geojson"),
        "duplicate_candidate": name("duplicate_candidate.geojson"),
    }

    write_geojson(
        [to_feature(s, {"fix": "ok"})
         for s in buckets["matched"]],
        output_dir / files["matched"]
    )

    write_geojson(
        [to_feature(s, {"fix": "add to OSM"})
         for s in buckets["missing_in_osm"]],
        output_dir / files["missing_in_osm"]
    )

    write_geojson(
        [to_feature(s, {
            "fix": "update OSM location",
            "osm_distance_m": (s.get("match") or {})
                              .get("osm_match", {}).get("distance_m")
         }) for s in buckets["location_mismatch"]],
        output_dir / files["location_mismatch"]
    )

    write_geojson(
        [to_feature(s, {
            "fix": "update OSM tags",
            "tag_issues": (s.get("match") or {}).get("reason")
         }) for s in buckets["tag_mismatch"]],
        output_dir / files["tag_mismatch"]
    )

    write_geojson(
        [to_feature(s, {
            "fix": "review name",
            "our_name": s.get("name"),
            "osm_name": ((s.get("match") or {})
                         .get("osm_match") or {}).get("name")
         }) for s in buckets["name_mismatch"]],
        output_dir / files["name_mismatch"]
    )

    write_geojson(
        [to_feature(s, {"fix": "check duplicate"})
         for s in buckets["duplicate_candidate"]],
        output_dir / files["duplicate_candidate"]
    )

    return files


# ── Main ─────────────────────────────────────────────────────
def generate_report(matched_dir: Path = MATCHED_DIR, output_dir: Path = REPORT_DIR):
    stations = load_matched_stations(matched_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Phân loại theo status
    buckets = status_buckets(stations)
    no_coordinate_stations = [
        s for s in stations
        if not (s.get("snapped_lat") or s.get("lat")) or not (s.get("snapped_lon") or s.get("lon"))
    ]

    print("\nGenerating reports...")

    # ── GeoJSON files ────────────────────────────────────────
    aggregate_files = write_status_geojsons(buckets, output_dir)

    source_files = {}
    for source, prefix in SOURCE_PREFIX.items():
        source_stations = [station for station in stations if station.get("source") == source]
        if not source_stations:
            continue
        source_files[prefix] = write_status_geojsons(status_buckets(source_stations), output_dir, prefix=prefix)
        write_csv(source_stations, output_dir / f"{prefix}_report.csv")
        if prefix == "gmaps":
            rejected_stations = [
                station for station in load_rejected_stations(REJECTED_DIR)
                if station.get("source") == source
            ]
            write_gmaps_review_csv(source_stations, rejected_stations, output_dir / "gmaps_review.csv")

    # ── report.csv — tất cả stations ────────────────────────
    write_csv(stations, output_dir / "report.csv")

    # ── summary.json ─────────────────────────────────────────
    summary = {
        "generated_at":        datetime.now(timezone.utc).isoformat(),
        "source_dir":          str(matched_dir),
        "total_seed":          len(stations),
        "matched":             len(buckets["matched"]),
        "missing_in_osm":      len(buckets["missing_in_osm"]),
        "location_mismatch":   len(buckets["location_mismatch"]),
        "tag_mismatch":        len(buckets["tag_mismatch"]),
        "name_mismatch":       len(buckets["name_mismatch"]),
        "duplicate_candidate": len(buckets["duplicate_candidate"]),
        "no_coordinates":      len(no_coordinate_stations),
        "coverage_pct": round(
            len(buckets["matched"]) / max(len(stations), 1) * 100, 1
        ),
        "thresholds": {
            "matched_m":  200,
            "possible_m": 500,
        },
        "geojson_files": aggregate_files,
        "source_geojson_files": source_files,
    }

    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)
    )
    print(f"  Written summary -> {summary_path}")

    # Print tóm tắt ra terminal
    print(f"""
REPORT SUMMARY
Total seed       : {summary['total_seed']:>4}
Matched          : {summary['matched']:>4}
Missing in OSM   : {summary['missing_in_osm']:>4}
Location mismatch: {summary['location_mismatch']:>4}
Tag mismatch     : {summary['tag_mismatch']:>4}
Name mismatch    : {summary['name_mismatch']:>4}
Duplicate        : {summary['duplicate_candidate']:>4}
No coordinates   : {summary['no_coordinates']:>4}
Coverage         : {summary['coverage_pct']:>5}%
""")

    return summary


if __name__ == "__main__":
    generate_report()
