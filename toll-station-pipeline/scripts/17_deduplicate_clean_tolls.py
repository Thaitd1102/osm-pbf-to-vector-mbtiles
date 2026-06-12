import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN_CSV = ROOT / "data" / "clean" / "toll_stations_clean.csv"
CLEAN_JSON = ROOT / "data" / "clean" / "toll_stations_clean.json"
CLEAN_GEOJSON = ROOT / "data" / "clean" / "toll_stations_clean.geojson"
REVIEW_CSV = ROOT / "data" / "final" / "results_review_resolved.csv"


# keep_id -> drop_ids
MERGE_GROUPS = {
    "vn-toll-results-99e95a3669a3f8": ["vn-toll-results-ecf3ef937f19db"],
    "vn-toll-results-bb6920af6c9fa1": ["vn-toll-results-f05a17a33cb5a1"],
    "vn-toll-results-022c2d4e049418": ["vn-toll-results-c6c551c8facd8a"],
    "vn-toll-results-17fee3612cf4d5": ["vn-toll-results-365655e8bad75e"],
    "vn-toll-results-852b9a6b761f54": ["vn-toll-results-85de560ace163d"],
    "vn-toll-results-43cd4ceb51a555": ["vn-toll-results-8d3b8dddd9fd91"],
    "vn-toll-results-2548de6c7d62ae": ["vn-toll-results-b0dfec5126dfe4"],
    "vn-toll-results-b81e9e3b43b716": ["vn-toll-results-e2f1caf33cb0e7"],
    "vn-toll-results-386eef74a7fe33": ["vn-toll-results-65802a0cb6e142"],
    "vn-toll-results-329cb8981a939e": ["vn-toll-results-828dfbbbc0c896"],
    "vn-toll-results-bb234595df3e9c": ["vn-toll-results-f860c384497f5e"],
}


def clean(value):
    return str(value or "").strip()


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def unique_join(*values):
    items = []
    for value in values:
        for item in clean(value).split(";"):
            item = item.strip()
            if item and item not in items:
                items.append(item)
    return ";".join(items)


def merge_row(keep, drop):
    for key, value in drop.items():
        if key not in keep:
            keep[key] = ""
        if not clean(keep.get(key)) and clean(value):
            keep[key] = clean(value)

    keep["source_datasets"] = unique_join(keep.get("source_datasets"), drop.get("source_datasets"))
    keep["merged_from_candidate_ids"] = unique_join(
        keep.get("merged_from_candidate_ids"),
        drop.get("merged_from_candidate_ids"),
        drop.get("id"),
    )
    keep["needs_manual_fields"] = unique_join(
        keep.get("needs_manual_fields"),
        drop.get("needs_manual_fields"),
    )
    keep["clean_status"] = "deduplicated_after_results_merge"
    return keep


def parse_float(value):
    try:
        return float(clean(value).replace(",", "."))
    except ValueError:
        return None


def write_csv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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


def enrich_images(rows):
    if not REVIEW_CSV.exists():
        return rows

    review_by_id = {row.get("id"): row for row in read_csv(REVIEW_CSV)}
    for row in rows:
        review_row = review_by_id.get(row.get("id"))
        if not review_row:
            row.setdefault("thumbnail", "")
            row.setdefault("image_url", "")
            continue
        row["thumbnail"] = clean(row.get("thumbnail")) or clean(review_row.get("thumbnail"))
        row["image_url"] = clean(row.get("image_url")) or clean(review_row.get("image_url"))
    return rows


def main():
    rows = enrich_images(read_csv(CLEAN_CSV))
    fieldnames = list(rows[0].keys()) if rows else []
    for field in ["thumbnail", "image_url"]:
        if field not in fieldnames:
            fieldnames.append(field)

    by_id = {row["id"]: row for row in rows}
    drop_ids = set()
    merged_pairs = 0

    for keep_id, group_drop_ids in MERGE_GROUPS.items():
        keep = by_id.get(keep_id)
        if not keep:
            continue
        for drop_id in group_drop_ids:
            drop = by_id.get(drop_id)
            if not drop:
                continue
            by_id[keep_id] = merge_row(keep, drop)
            drop_ids.add(drop_id)
            merged_pairs += 1

    output_rows = [row for row in rows if row.get("id") not in drop_ids]
    write_csv(CLEAN_CSV, output_rows, fieldnames)
    with CLEAN_JSON.open("w", encoding="utf-8") as file:
        json.dump(output_rows, file, ensure_ascii=False, indent=2)
    feature_count = write_geojson(CLEAN_GEOJSON, output_rows)

    print(f"Rows before : {len(rows)}")
    print(f"Merged pairs: {merged_pairs}")
    print(f"Rows after  : {len(output_rows)}")
    print(f"GeoJSON features: {feature_count}")
    print(f"Updated CSV : {CLEAN_CSV}")
    print(f"Updated JSON: {CLEAN_JSON}")
    print(f"Updated GeoJSON: {CLEAN_GEOJSON}")


if __name__ == "__main__":
    main()
