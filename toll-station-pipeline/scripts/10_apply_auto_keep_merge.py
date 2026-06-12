from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NORMALIZATION_DIR = ROOT / "data" / "normalization"
CANDIDATES_CSV = NORMALIZATION_DIR / "toll_stations_normalized_candidates.csv"
DUPLICATE_REVIEW_CSV = NORMALIZATION_DIR / "toll_duplicate_review.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = fieldnames or (list(rows[0].keys()) if rows else [])
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def first_value(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def enrich_keep_with_merge(keep: dict[str, str], merge_rows: list[dict[str, str]]) -> dict[str, object]:
    merged = dict(keep)
    merged_from = []
    source_datasets = {keep.get("dataset", "")}

    for row in merge_rows:
        merged_from.append(row.get("candidate_id", ""))
        source_datasets.add(row.get("dataset", ""))
        for field in ["address", "source_url", "google_place_id", "google_cid", "name_google"]:
            merged[field] = first_value(merged.get(field), row.get(field))

    merged["merged_from_candidate_ids"] = ";".join(item for item in merged_from if item)
    merged["source_datasets"] = ";".join(sorted(item for item in source_datasets if item))
    merged["clean_status"] = "auto_keep_merge"
    return merged


def choose_keep(rows: list[dict[str, str]]) -> dict[str, str]:
    b_rows = [row for row in rows if row.get("dataset") == "B_final"]
    if b_rows:
        return b_rows[0]
    return rows[0]


def apply_review_decisions(
    candidates: list[dict[str, str]],
    duplicate_review_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    by_candidate = {row["candidate_id"]: row for row in candidates}
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in duplicate_review_rows:
        groups[row["duplicate_group_id"]].append(row)

    updated_review: list[dict[str, object]] = []
    clean_rows: list[dict[str, object]] = []
    handled_candidate_ids: set[str] = set()

    for group_id, review_rows in sorted(groups.items()):
        group_candidates = [by_candidate[row["candidate_id"]] for row in review_rows if row["candidate_id"] in by_candidate]
        if not group_candidates:
            continue

        keep = choose_keep(group_candidates)
        keep_id = keep["candidate_id"]
        merge_rows = [row for row in group_candidates if row["candidate_id"] != keep_id]
        clean_rows.append(enrich_keep_with_merge(keep, merge_rows))

        for row in review_rows:
            candidate_id = row["candidate_id"]
            candidate = by_candidate.get(candidate_id, {})
            decision = "keep" if candidate_id == keep_id else "merge"
            note = (
                "auto: B_final được ưu tiên làm bản chính"
                if candidate.get("dataset") == "B_final" and decision == "keep"
                else "auto: merge thông tin bổ sung vào bản chính"
            )
            if not any(item.get("dataset") == "B_final" for item in group_candidates) and decision == "keep":
                note = "auto: nhóm chỉ có A, giữ một bản A làm bản chính"

            updated = dict(row)
            updated["preferred_candidate_id"] = keep_id
            updated["review_decision"] = decision
            updated["review_note"] = note
            updated_review.append(updated)
            handled_candidate_ids.add(candidate_id)

    for row in candidates:
        if row["candidate_id"] in handled_candidate_ids:
            continue
        clean = dict(row)
        clean["merged_from_candidate_ids"] = ""
        clean["source_datasets"] = row.get("dataset", "")
        clean["clean_status"] = "auto_keep_unique"
        clean_rows.append(clean)

    return updated_review, clean_rows


def clean_output_row(row: dict[str, object], index: int) -> dict[str, object]:
    source_original_id = str(row.get("source_original_id") or "").strip()
    candidate_id = str(row.get("candidate_id") or "").strip()
    clean_id = source_original_id if str(row.get("dataset")) == "B_final" and source_original_id else f"vn-toll-clean-{index + 1:03d}"
    tags = first_value(row.get("tags"), "barrier=toll_booth;toll=yes;payment:etc=yes")
    return {
        "id": clean_id,
        "name": row.get("name_normalized", ""),
        "lat": row.get("lat", ""),
        "lon": row.get("lon", ""),
        "address": row.get("address", ""),
        "province": row.get("province", ""),
        "road": row.get("road", ""),
        "operator": row.get("operator", ""),
        "source_datasets": row.get("source_datasets", row.get("dataset", "")),
        "source_original_id": source_original_id,
        "candidate_id": candidate_id,
        "source_url": row.get("source_url", ""),
        "google_place_id": row.get("google_place_id", ""),
        "google_cid": row.get("google_cid", ""),
        "osm_id": row.get("osm_id", ""),
        "osm_name": row.get("osm_name", ""),
        "confidence": row.get("confidence", ""),
        "tags": tags,
        "clean_status": row.get("clean_status", ""),
        "merged_from_candidate_ids": row.get("merged_from_candidate_ids", ""),
        "needs_manual_fields": "operator;km_marker" if not row.get("operator") else "km_marker",
    }


def geojson_feature(row: dict[str, object]) -> dict[str, object] | None:
    try:
        lat = float(row["lat"])
        lon = float(row["lon"])
    except (TypeError, ValueError):
        return None
    properties = {key: value for key, value in row.items() if key not in {"lat", "lon"}}
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": properties,
    }


def main() -> None:
    candidates = read_csv(CANDIDATES_CSV)
    duplicate_review_rows = read_csv(DUPLICATE_REVIEW_CSV)
    updated_review, raw_clean_rows = apply_review_decisions(candidates, duplicate_review_rows)
    clean_rows = [clean_output_row(row, index) for index, row in enumerate(raw_clean_rows)]
    clean_rows.sort(key=lambda row: str(row["name"]).lower())

    write_csv(DUPLICATE_REVIEW_CSV, updated_review)
    write_csv(NORMALIZATION_DIR / "toll_stations_clean_auto.csv", clean_rows)
    (NORMALIZATION_DIR / "toll_stations_clean_auto.json").write_text(
        json.dumps(clean_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    features = [feature for row in clean_rows if (feature := geojson_feature(row))]
    (NORMALIZATION_DIR / "toll_stations_clean_auto.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = {
        "candidate_total": len(candidates),
        "duplicate_review_rows": len(updated_review),
        "clean_total": len(clean_rows),
        "auto_keep_from_b": sum(1 for row in updated_review if row["dataset"] == "B_final" and row["review_decision"] == "keep"),
        "auto_merge_from_a": sum(1 for row in updated_review if row["dataset"] == "A_colleague" and row["review_decision"] == "merge"),
        "auto_keep_from_a_duplicate_groups": sum(1 for row in updated_review if row["dataset"] == "A_colleague" and row["review_decision"] == "keep"),
        "unique_kept": sum(1 for row in clean_rows if row["clean_status"] == "auto_keep_unique"),
        "outputs": {
            "review": "data/normalization/toll_duplicate_review.csv",
            "clean_csv": "data/normalization/toll_stations_clean_auto.csv",
            "clean_json": "data/normalization/toll_stations_clean_auto.json",
            "clean_geojson": "data/normalization/toll_stations_clean_auto.geojson",
        },
    }
    (NORMALIZATION_DIR / "toll_clean_auto_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (NORMALIZATION_DIR / "toll_clean_auto_summary.md").write_text(
        f"""# Auto keep/merge trạm thu phí

## Rule đã áp dụng

- Trong nhóm trùng có **B_final**: giữ B là `keep`.
- Các dòng **A_colleague** cùng nhóm: đánh dấu `merge` để lấy thêm address/url/cid nếu cần.
- Nhóm chỉ có A: giữ một dòng A là `keep`.
- Candidate không nằm trong nhóm trùng: giữ nguyên.

## Kết quả

- Tổng candidate đầu vào: {summary["candidate_total"]}
- Số dòng review đã cập nhật decision: {summary["duplicate_review_rows"]}
- Tổng clean dataset sau auto keep/merge: {summary["clean_total"]}
- B được auto keep trong nhóm trùng: {summary["auto_keep_from_b"]}
- A được auto merge trong nhóm trùng: {summary["auto_merge_from_a"]}
- A được keep vì nhóm chỉ có A: {summary["auto_keep_from_a_duplicate_groups"]}
- Candidate unique được giữ nguyên: {summary["unique_kept"]}

## Output

- `toll_duplicate_review.csv`: đã điền `review_decision`.
- `toll_stations_clean_auto.csv`: clean dataset tạm thời.
- `toll_stations_clean_auto.json`: clean dataset dạng JSON.
- `toll_stations_clean_auto.geojson`: clean dataset để hiển thị map.
""",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
