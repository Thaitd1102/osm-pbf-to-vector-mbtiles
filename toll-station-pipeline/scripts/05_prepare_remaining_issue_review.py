import csv
import json
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
MATCHED_FILE = PIPELINE_ROOT / "data" / "matched" / "gmaps_matched.json"
OUTPUT_FILE = PIPELINE_ROOT / "data" / "report" / "gmaps_issue_review_template.csv"


REVIEW_STATUSES = {
    "location_mismatch",
    "missing_in_osm",
    "duplicate_candidate",
    "tag_mismatch",
}


def clean(value: object) -> str:
    return str(value or "").strip()


def load_json(path: Path) -> list[dict]:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    records = load_json(MATCHED_FILE)
    rows = []

    for record in records:
        match = record.get("match") or {}
        status = clean(match.get("status"))
        if status not in REVIEW_STATUSES:
            continue

        osm = match.get("osm_match") or {}
        rows.append({
            "review_decision": "",
            "review_comment": "",
            "issue_type": status,
            "suggested_action": {
                "location_mismatch": "check_or_correct_coordinates",
                "missing_in_osm": "create_new_osm_toll_booth",
                "duplicate_candidate": "mark_duplicate_or_keep_one",
                "tag_mismatch": "fix_osm_tags",
            }.get(status, ""),
            "google_name": record.get("name"),
            "google_lat": record.get("lat"),
            "google_lon": record.get("lon"),
            "google_category": record.get("category"),
            "google_place_id": record.get("google_place_id"),
            "google_source_url": record.get("source_url"),
            "osm_id": osm.get("osm_id") or osm.get("id"),
            "osm_current_name": osm.get("name"),
            "osm_lat": osm.get("lat"),
            "osm_lon": osm.get("lon"),
            "osm_type": osm.get("type"),
            "osm_operator": osm.get("operator"),
            "osm_distance_m": round(float(osm.get("distance_m")), 1) if osm.get("distance_m") is not None else "",
            "match_reason": match.get("reason"),
            "corrected_name": "",
            "corrected_lat": "",
            "corrected_lon": "",
        })

    fieldnames = [
        "review_decision",
        "review_comment",
        "issue_type",
        "suggested_action",
        "google_name",
        "google_lat",
        "google_lon",
        "google_category",
        "google_place_id",
        "google_source_url",
        "osm_id",
        "osm_current_name",
        "osm_lat",
        "osm_lon",
        "osm_type",
        "osm_operator",
        "osm_distance_m",
        "match_reason",
        "corrected_name",
        "corrected_lat",
        "corrected_lon",
    ]

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    counts = {}
    for row in rows:
        counts[row["issue_type"]] = counts.get(row["issue_type"], 0) + 1

    print(f"Written {len(rows)} rows -> {OUTPUT_FILE}")
    for status in sorted(counts):
        print(f"  {status}: {counts[status]}")


if __name__ == "__main__":
    main()
