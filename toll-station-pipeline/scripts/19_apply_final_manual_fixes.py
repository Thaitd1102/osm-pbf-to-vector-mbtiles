import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN_CSV = ROOT / "data" / "clean" / "toll_stations_clean.csv"
CLEAN_JSON = ROOT / "data" / "clean" / "toll_stations_clean.json"
CLEAN_GEOJSON = ROOT / "data" / "clean" / "toll_stations_clean.geojson"
CANDIDATES_CSV = ROOT / "data" / "final" / "results_clean_candidates.csv"
RESOLVED_REVIEW_CSV = ROOT / "data" / "final" / "results_review_resolved.csv"


REMOVE_IDS = {
    "vn-toll-results-70d67780da1440": "not_toll_station_vetc_service_point",
    "vn-toll-results-953cd242cbc07d": "not_toll_station_epass_office",
}

ADD_IDS = {
    "vn-toll-results-18d929834244af": "manual_keep_google_confirmed_generic_toll_station",
    "vn-toll-results-389322d4f5b691": "manual_keep_google_confirmed_generic_toll_station",
}


def clean(value):
    return str(value or "").strip()


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_float(value):
    try:
        return float(clean(value).replace(",", "."))
    except ValueError:
        return None


def write_geojson(rows):
    features = []
    for row in rows:
        lat = parse_float(row.get("lat"))
        lon = parse_float(row.get("lon"))
        if lat is None or lon is None:
            continue
        props = {key: value for key, value in row.items() if key not in {"lat", "lon"}}
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": props,
            }
        )
    with CLEAN_GEOJSON.open("w", encoding="utf-8") as file:
        json.dump({"type": "FeatureCollection", "features": features}, file, ensure_ascii=False, indent=2)
    return len(features)


def candidate_to_clean(row, fieldnames):
    output = {field: "" for field in fieldnames}
    output.update(
        {
            "id": clean(row.get("id")),
            "name": clean(row.get("name")),
            "lat": clean(row.get("lat")),
            "lon": clean(row.get("lon")),
            "address": clean(row.get("address")),
            "source_datasets": "colleague_google_maps_results",
            "source_original_id": clean(row.get("google_place_id")) or clean(row.get("google_cid")),
            "candidate_id": clean(row.get("id")),
            "source_url": clean(row.get("google_maps_url")),
            "thumbnail": clean(row.get("thumbnail")),
            "image_url": clean(row.get("image_url")),
            "google_place_id": clean(row.get("google_place_id")),
            "google_cid": clean(row.get("google_cid")),
            "confidence": "0.75",
            "tags": "barrier=toll_booth;toll=yes;payment:etc=yes",
            "clean_status": "manual_keep_after_results_review",
            "merged_from_candidate_ids": clean(row.get("id")),
            "needs_manual_fields": "province;road;operator",
            "status": "active",
            "status_note": ADD_IDS[clean(row.get("id"))],
        }
    )
    return output


def update_resolved_review():
    if not RESOLVED_REVIEW_CSV.exists():
        return
    rows = read_csv(RESOLVED_REVIEW_CSV)
    fieldnames = list(rows[0].keys()) if rows else []
    for field in ["resolved_review_decision", "review_warning"]:
        if field not in fieldnames:
            fieldnames.append(field)
    for row in rows:
        row_id = clean(row.get("id"))
        if row_id in REMOVE_IDS:
            row["resolved_review_decision"] = "reject"
            row["review_warning"] = REMOVE_IDS[row_id]
        if row_id in ADD_IDS:
            row["resolved_review_decision"] = "keep"
            row["review_warning"] = ADD_IDS[row_id]
    write_csv(RESOLVED_REVIEW_CSV, rows, fieldnames)


def main():
    rows = read_csv(CLEAN_CSV)
    fieldnames = list(rows[0].keys()) if rows else []
    for field in ["thumbnail", "image_url"]:
        if field not in fieldnames:
            fieldnames.append(field)

    before = len(rows)
    rows = [row for row in rows if clean(row.get("id")) not in REMOVE_IDS]
    removed = before - len(rows)

    existing_ids = {clean(row.get("id")) for row in rows}
    candidates = {clean(row.get("id")): row for row in read_csv(CANDIDATES_CSV)}
    added = 0
    for add_id in ADD_IDS:
        if add_id in existing_ids:
            continue
        candidate = candidates.get(add_id)
        if not candidate:
            continue
        rows.append(candidate_to_clean(candidate, fieldnames))
        existing_ids.add(add_id)
        added += 1

    write_csv(CLEAN_CSV, rows, fieldnames)
    with CLEAN_JSON.open("w", encoding="utf-8") as file:
        json.dump(rows, file, ensure_ascii=False, indent=2)
    features = write_geojson(rows)
    update_resolved_review()

    print(f"Rows before : {before}")
    print(f"Removed     : {removed}")
    print(f"Added       : {added}")
    print(f"Rows after  : {len(rows)}")
    print(f"GeoJSON features: {features}")


if __name__ == "__main__":
    main()
