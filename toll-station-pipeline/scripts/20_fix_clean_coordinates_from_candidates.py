import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN_CSV = ROOT / "data" / "clean" / "toll_stations_clean.csv"
CLEAN_JSON = ROOT / "data" / "clean" / "toll_stations_clean.json"
CLEAN_GEOJSON = ROOT / "data" / "clean" / "toll_stations_clean.geojson"
CANDIDATES_CSV = ROOT / "data" / "final" / "results_clean_candidates.csv"


def clean(value):
    return str(value or "").strip()


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def parse_float(value):
    try:
        return float(clean(value).replace(",", "."))
    except ValueError:
        return None


def in_vietnam(lat, lon):
    return lat is not None and lon is not None and 8 <= lat <= 24 and 102 <= lon <= 110


def write_csv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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


def main():
    rows = read_csv(CLEAN_CSV)
    candidates = {row["id"]: row for row in read_csv(CANDIDATES_CSV)}
    fieldnames = list(rows[0].keys()) if rows else []
    fixed = 0
    still_bad = []

    for row in rows:
        lat = parse_float(row.get("lat"))
        lon = parse_float(row.get("lon"))
        if in_vietnam(lat, lon):
            continue

        candidate = candidates.get(row.get("id"))
        if not candidate:
            still_bad.append(row)
            continue

        candidate_lat = parse_float(candidate.get("lat"))
        candidate_lon = parse_float(candidate.get("lon"))
        if not in_vietnam(candidate_lat, candidate_lon):
            still_bad.append(row)
            continue

        row["lat"] = clean(candidate.get("lat"))
        row["lon"] = clean(candidate.get("lon"))
        fixed += 1

    write_csv(CLEAN_CSV, rows, fieldnames)
    with CLEAN_JSON.open("w", encoding="utf-8") as file:
        json.dump(rows, file, ensure_ascii=False, indent=2)
    feature_count = write_geojson(rows)

    print(f"Rows        : {len(rows)}")
    print(f"Fixed coords: {fixed}")
    print(f"Still bad   : {len(still_bad)}")
    print(f"GeoJSON features: {feature_count}")
    for row in still_bad[:20]:
        print(f"BAD {row.get('id')} | {row.get('name')} | {row.get('lat')}, {row.get('lon')}")


if __name__ == "__main__":
    main()
