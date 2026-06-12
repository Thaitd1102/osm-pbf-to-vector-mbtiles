import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN_CSV = ROOT / "data" / "clean" / "toll_stations_clean.csv"
CLEAN_JSON = ROOT / "data" / "clean" / "toll_stations_clean.json"
CLEAN_GEOJSON = ROOT / "data" / "clean" / "toll_stations_clean.geojson"


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def clean_text(value):
    value = str(value or "").strip()
    value = re.sub(r"\s+", " ", value)
    value = value.replace("–", "-").replace("—", "-")
    return value


def normalize_name(name):
    name = clean_text(name)
    name = re.sub(r"(?i)\btrạm\s+thu\s+phí\b", "Trạm thu phí", name)
    name = re.sub(r"(?i)\bcao\s+toc\b", "cao tốc", name)
    name = re.sub(r"(?i)\bcao\s+tốc\b", "cao tốc", name)
    name = re.sub(r"(?i)\bkm\s*(\d)", r"Km \1", name)
    name = re.sub(r"(?i)\bql\s*([0-9]+[a-z]?(?:-[a-z]+)?)\b", lambda m: f"Quốc lộ {m.group(1).upper()}", name)
    name = re.sub(r"\s*-\s*", " - ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def parse_float(value):
    try:
        return float(str(value or "").strip().replace(",", "."))
    except ValueError:
        return None


def write_geojson(path, rows):
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
    with path.open("w", encoding="utf-8") as file:
        json.dump({"type": "FeatureCollection", "features": features}, file, ensure_ascii=False, indent=2)
    return len(features)


def main():
    rows = read_csv(CLEAN_CSV)
    fieldnames = list(rows[0].keys()) if rows else []
    changed = []
    for row in rows:
        old_name = row.get("name", "")
        new_name = normalize_name(old_name)
        if new_name != old_name:
            changed.append((row.get("id"), old_name, new_name))
            row["name"] = new_name

    write_csv(CLEAN_CSV, rows, fieldnames)
    with CLEAN_JSON.open("w", encoding="utf-8") as file:
        json.dump(rows, file, ensure_ascii=False, indent=2)
    features = write_geojson(CLEAN_GEOJSON, rows)

    print(f"Rows          : {len(rows)}")
    print(f"Names changed : {len(changed)}")
    print(f"GeoJSON       : {features} features")
    for row_id, old_name, new_name in changed[:80]:
        print(f"- {row_id}: {old_name} -> {new_name}")


if __name__ == "__main__":
    main()
