import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
USER_REVIEW_CSV = ROOT / "data" / "final" / "1.csv"
RESOLVED_REVIEW_CSV = ROOT / "data" / "final" / "results_review_resolved.csv"
CLEAN_CSV = ROOT / "data" / "clean" / "toll_stations_clean.csv"
CLEAN_JSON = ROOT / "data" / "clean" / "toll_stations_clean.json"
CLEAN_GEOJSON = ROOT / "data" / "clean" / "toll_stations_clean.geojson"


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


def should_reject_review_row(row, excel_row_number):
    name = clean(row.get("name")).lower()
    note = clean(row.get("review_note")).lower()

    if 108 <= excel_row_number <= 120:
        return True, "manual_note_excel_rows_108_120_reject"
    if "điểm dán" in name or "diem dan" in name or "dán thu phí" in name or "dan thu phi" in name:
        return True, "not_toll_station_tagging_point"
    if "điểm dán" in note or "diem dan" in note:
        return True, "not_toll_station_tagging_point"
    return False, ""


def update_resolved_review():
    user_rows = read_csv(USER_REVIEW_CSV)
    reject_ids = {}
    for index, row in enumerate(user_rows, start=2):
        reject, reason = should_reject_review_row(row, index)
        if reject:
            reject_ids[clean(row.get("id"))] = reason

    resolved_rows = read_csv(RESOLVED_REVIEW_CSV)
    fieldnames = list(resolved_rows[0].keys()) if resolved_rows else []
    for field in ["resolved_review_decision", "review_warning"]:
        if field not in fieldnames:
            fieldnames.append(field)

    changed = 0
    for row in resolved_rows:
        row_id = clean(row.get("id"))
        reason = reject_ids.get(row_id)
        if not reason:
            continue
        if row.get("resolved_review_decision") != "reject":
            changed += 1
        row["resolved_review_decision"] = "reject"
        row["review_warning"] = reason

    write_csv(RESOLVED_REVIEW_CSV, resolved_rows, fieldnames)
    return reject_ids, changed


def cleanup_clean(reject_ids):
    rows = read_csv(CLEAN_CSV)
    fieldnames = list(rows[0].keys()) if rows else []
    before = len(rows)
    output_rows = [row for row in rows if clean(row.get("id")) not in reject_ids]
    write_csv(CLEAN_CSV, output_rows, fieldnames)
    with CLEAN_JSON.open("w", encoding="utf-8") as file:
        json.dump(output_rows, file, ensure_ascii=False, indent=2)
    feature_count = write_geojson(CLEAN_GEOJSON, output_rows)
    return before, len(output_rows), feature_count


def main():
    reject_ids, changed = update_resolved_review()
    before, after, feature_count = cleanup_clean(reject_ids)
    print(f"Review rows forced to reject: {changed}")
    print(f"Reject ids from notes       : {len(reject_ids)}")
    print(f"Clean rows before          : {before}")
    print(f"Clean rows after           : {after}")
    print(f"GeoJSON features           : {feature_count}")
    print(f"Updated review: {RESOLVED_REVIEW_CSV}")
    print(f"Updated clean : {CLEAN_CSV}")


if __name__ == "__main__":
    main()
