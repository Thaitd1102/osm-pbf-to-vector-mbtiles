import csv
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PIPELINE_ROOT / "data" / "report"

ORIGINAL_REVIEW_FILE = REPORT_DIR / "gmaps_name_review_template.csv"
USER_REVIEW_FILE = REPORT_DIR / "gmaps_name_review_user.csv"
OUTPUT_FILE = REPORT_DIR / "merged_osm_name_updates.csv"


def clean(value: object) -> str:
    return str(value or "").strip()


def row_key(row: dict) -> str:
    return clean(row.get("osm_id")) or clean(row.get("google_place_id"))


def load_rows(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def main() -> None:
    if not ORIGINAL_REVIEW_FILE.exists():
        raise FileNotFoundError(f"Missing original review file: {ORIGINAL_REVIEW_FILE}")
    if not USER_REVIEW_FILE.exists():
        raise FileNotFoundError(f"Missing user review file: {USER_REVIEW_FILE}")

    original_by_key = {row_key(row): row for row in load_rows(ORIGINAL_REVIEW_FILE)}
    reviewed_rows = load_rows(USER_REVIEW_FILE)
    updates = []
    skipped = []

    for row in reviewed_rows:
        key = row_key(row)
        original = original_by_key.get(key)
        if not original:
            skipped.append({**row, "skip_reason": "not_found_in_original_review"})
            continue

        original_name = clean(original.get("osm_current_name"))
        edited_osm_name = clean(row.get("osm_current_name"))
        corrected_name = clean(row.get("corrected_osm_name"))
        new_name = corrected_name or edited_osm_name

        if not new_name or new_name == original_name:
            skipped.append({**row, "skip_reason": "no_name_change"})
            continue

        updates.append({
            "osm_id": clean(row.get("osm_id")),
            "old_osm_name": original_name,
            "new_osm_name": new_name,
            "google_name": clean(row.get("google_name")),
            "lat": clean(row.get("lat")),
            "lon": clean(row.get("lon")),
            "osm_lat": clean(row.get("osm_lat")),
            "osm_lon": clean(row.get("osm_lon")),
            "osm_distance_m": clean(row.get("osm_distance_m")),
            "google_place_id": clean(row.get("google_place_id")),
            "source_url": clean(row.get("source_url")),
            "review_comment": clean(row.get("review_comment")),
        })

    fieldnames = [
        "osm_id",
        "old_osm_name",
        "new_osm_name",
        "google_name",
        "lat",
        "lon",
        "osm_lat",
        "osm_lon",
        "osm_distance_m",
        "google_place_id",
        "source_url",
        "review_comment",
    ]
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updates)

    print(f"Reviewed rows : {len(reviewed_rows)}")
    print(f"Name updates  : {len(updates)}")
    print(f"Skipped       : {len(skipped)}")
    print(f"Output        : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
