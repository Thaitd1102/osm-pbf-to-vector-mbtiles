import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN_CSV = ROOT / "data" / "clean" / "toll_stations_clean.csv"
CLEAN_JSON = ROOT / "data" / "clean" / "toll_stations_clean.json"
CLEAN_GEOJSON = ROOT / "data" / "clean" / "toll_stations_clean.geojson"
REVIEW_CSV = ROOT / "data" / "final" / "results_review_resolved.csv"


OUTPUT_COLUMNS = [
    "id",
    "name",
    "lat",
    "lon",
    "address",
    "province",
    "road",
    "operator",
    "source_datasets",
    "source_original_id",
    "candidate_id",
    "source_url",
    "thumbnail",
    "image_url",
    "google_place_id",
    "google_cid",
    "osm_id",
    "osm_name",
    "confidence",
    "tags",
    "clean_status",
    "merged_from_candidate_ids",
    "needs_manual_fields",
    "status",
    "status_note",
]


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def parse_float(value):
    value = normalize_coord(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_coord(value):
    value = clean(str(value))
    if not value:
        return ""
    value = value.replace(",", ".")
    sign = ""
    if value.startswith("-"):
        sign = "-"
        value = value[1:]
    if value.count(".") > 1:
        parts = [part for part in value.split(".") if part != ""]
        if len(parts) >= 2:
            value = f"{parts[0]}.{''.join(parts[1:])}"
    return f"{sign}{value}"


def write_geojson(path, rows):
    features = []
    for row in rows:
        lat = parse_float(row.get("lat"))
        lon = parse_float(row.get("lon"))
        if lat is None or lon is None:
            continue

        properties = {key: value for key, value in row.items() if key not in {"lat", "lon"}}
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": properties,
            }
        )

    with path.open("w", encoding="utf-8") as file:
        json.dump({"type": "FeatureCollection", "features": features}, file, ensure_ascii=False, indent=2)

    return len(features)


def clean(value):
    return (value or "").strip()


def confidence_for(row):
    category = clean(row.get("category")).lower()
    if category == "trạm thu phí":
        return "0.80"
    return "0.68"


def to_clean_row(row):
    name = clean(row.get("corrected_name")) or clean(row.get("name"))
    address = clean(row.get("corrected_address")) or clean(row.get("address"))
    missing_fields = []
    if not address:
        missing_fields.append("address")
    missing_fields.extend(["province", "road", "operator"])

    return {
        "id": clean(row.get("id")),
        "name": name,
        "lat": normalize_coord(row.get("lat")),
        "lon": normalize_coord(row.get("lon")),
        "address": address,
        "province": "",
        "road": "",
        "operator": "",
        "source_datasets": "colleague_google_maps_results",
        "source_original_id": clean(row.get("google_place_id")) or clean(row.get("google_cid")),
        "candidate_id": clean(row.get("id")),
        "source_url": clean(row.get("google_maps_url")),
        "thumbnail": clean(row.get("thumbnail")),
        "image_url": clean(row.get("image_url")),
        "google_place_id": clean(row.get("google_place_id")),
        "google_cid": clean(row.get("google_cid")),
        "osm_id": "",
        "osm_name": "",
        "confidence": confidence_for(row),
        "tags": "barrier=toll_booth;toll=yes;payment:etc=yes",
        "clean_status": "reviewed_from_results",
        "merged_from_candidate_ids": clean(row.get("id")),
        "needs_manual_fields": ";".join(dict.fromkeys(missing_fields)),
        "status": "active",
        "status_note": clean(row.get("review_note")),
    }


def row_key(row):
    return clean(row.get("google_place_id")) or clean(row.get("google_cid")) or clean(row.get("id"))


def normalize_existing_rows(rows):
    for row in rows:
        row["lat"] = normalize_coord(row.get("lat"))
        row["lon"] = normalize_coord(row.get("lon"))
    return rows


def main():
    clean_rows = normalize_existing_rows(read_csv(CLEAN_CSV))
    review_rows = read_csv(REVIEW_CSV)
    existing_keys = {row_key(row) for row in clean_rows if row_key(row)}
    existing_ids = {clean(row.get("id")) for row in clean_rows if clean(row.get("id"))}

    added = []
    skipped = {
        "reject": 0,
        "unsure": 0,
        "possible_duplicate_nearby": 0,
        "already_exists": 0,
    }

    for row in review_rows:
        decision = clean(row.get("resolved_review_decision")).lower()
        match_status = clean(row.get("match_status"))

        if decision == "reject":
            skipped["reject"] += 1
            continue
        if decision == "unsure":
            skipped["unsure"] += 1
            continue
        if match_status == "possible_duplicate_nearby":
            skipped["possible_duplicate_nearby"] += 1
            continue
        if decision not in {"keep", "merge"}:
            skipped["unsure"] += 1
            continue

        new_row = to_clean_row(row)
        key = row_key(new_row)
        if key in existing_keys or new_row["id"] in existing_ids:
            skipped["already_exists"] += 1
            continue

        existing_keys.add(key)
        existing_ids.add(new_row["id"])
        added.append(new_row)

    output_rows = clean_rows + added
    write_csv(CLEAN_CSV, output_rows)
    with CLEAN_JSON.open("w", encoding="utf-8") as file:
        json.dump(output_rows, file, ensure_ascii=False, indent=2)
    feature_count = write_geojson(CLEAN_GEOJSON, output_rows)

    print(f"Clean rows before : {len(clean_rows)}")
    print(f"Added rows        : {len(added)}")
    print(f"Clean rows after  : {len(output_rows)}")
    for reason, count in skipped.items():
        print(f"Skipped {reason}: {count}")
    print(f"Updated CSV : {CLEAN_CSV}")
    print(f"Updated JSON: {CLEAN_JSON}")
    print(f"Updated GeoJSON: {CLEAN_GEOJSON} ({feature_count} features)")


if __name__ == "__main__":
    main()
