from __future__ import annotations

import csv
import json
import math
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COLLEAGUE_CSV = ROOT / "data" / "final" / "tram_thu_phi.csv"
OURS_CSV = ROOT / "data" / "final" / "merged_toll_stations_final.csv"
REPORT_DIR = ROOT / "data" / "report"

DISTANCE_MATCH_M = 120.0
NAME_MATCH_SCORE = 0.86
A_NAME = "A_colleague_tram_thu_phi"
B_NAME = "B_our_final_dataset"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def clean_text(value: str) -> str:
    text = unicodedata.normalize("NFD", value or "")
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.lower()
    text = re.sub(r"\btram\b|\bthu\b|\bphi\b|\bbot\b|\betc\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def text_score(left: str, right: str) -> float:
    left_clean = clean_text(left)
    right_clean = clean_text(right)
    if not left_clean or not right_clean:
        return 0.0
    return SequenceMatcher(None, left_clean, right_clean).ratio()


def to_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def row_name(row: dict[str, str], *fields: str) -> str:
    for field in fields:
        if row.get(field):
            return row[field]
    return ""


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def non_empty_count(rows: list[dict[str, str]], field: str) -> int:
    return sum(1 for row in rows if str(row.get(field, "")).strip())


def attribute_rows(dataset: str, rows: list[dict[str, str]], fields: list[str]) -> list[dict[str, object]]:
    total = len(rows)
    return [
        {
            "dataset": dataset,
            "field": field,
            "non_empty": non_empty_count(rows, field),
            "total": total,
            "coverage_percent": round(non_empty_count(rows, field) * 100 / total, 1) if total else 0,
        }
        for field in fields
    ]


def simple_list(rows: list[dict[str, object]], side: str) -> list[str]:
    if side == "A":
        return [str(row.get("colleague_name") or row.get("colleague_google_name") or "").strip() for row in rows]
    return [str(row.get("ours_name") or "").strip() for row in rows]


def write_markdown_summary(path: Path, summary: dict[str, object], a_only: list[dict[str, object]], b_only: list[dict[str, object]], name_review: list[dict[str, object]]) -> None:
    def bullet(items: list[str]) -> str:
        if not items:
            return "- Không có\n"
        return "\n".join(f"- {item}" for item in items if item) + "\n"

    content = f"""# So sánh dữ liệu trạm thu phí

Quy ước:

- A = `tram_thu_phi.csv` của đồng nghiệp.
- B = `merged_toll_stations_final.csv` của mình.

## Tổng quan

- Tổng trạm bên A: {summary["a_total"]}
- Tổng trạm bên B: {summary["b_total"]}
- Khớp tốt theo tọa độ: {summary["matched_by_distance"]}
- Khớp theo tên, cần kiểm tra tọa độ: {summary["matched_by_name"]}
- A có, B chưa có: {summary["a_only"]}
- B có, A chưa có: {summary["b_only"]}

Ngưỡng khớp tọa độ: <= {summary["distance_match_threshold_m"]} m.

## A có nhưng B chưa có

{bullet(simple_list(a_only, "A"))}
## B có nhưng A chưa có

{bullet(simple_list(b_only, "B"))}
## Khớp theo tên nhưng cần review

{bullet([f'{row.get("colleague_name")} <-> {row.get("ours_name")} | distance_m={row.get("distance_m")} | score={row.get("name_score")}' for row in name_review])}
"""
    path.write_text(content, encoding="utf-8")


def main() -> None:
    colleague_rows = read_csv(COLLEAGUE_CSV)
    ours_rows = read_csv(OURS_CSV)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    colleague_fields = list(colleague_rows[0].keys()) if colleague_rows else []
    ours_fields = list(ours_rows[0].keys()) if ours_rows else []

    matched_ours: set[int] = set()
    report_rows: list[dict[str, object]] = []

    for colleague_index, colleague in enumerate(colleague_rows):
        colleague_lat = to_float(colleague.get("lat", ""))
        colleague_lon = to_float(colleague.get("lng", ""))
        colleague_name = row_name(colleague, "name", "google_name")

        nearest = None
        nearest_distance = None
        best_name = None
        best_name_score = 0.0

        for ours_index, ours in enumerate(ours_rows):
            ours_lat = to_float(ours.get("lat", ""))
            ours_lon = to_float(ours.get("lon", ""))
            if colleague_lat is not None and colleague_lon is not None and ours_lat is not None and ours_lon is not None:
                distance = haversine_m(colleague_lat, colleague_lon, ours_lat, ours_lon)
                if nearest_distance is None or distance < nearest_distance:
                    nearest_distance = distance
                    nearest = (ours_index, ours)

            score = text_score(colleague_name, row_name(ours, "name", "osm_name"))
            if score > best_name_score:
                best_name_score = score
                best_name = (ours_index, ours)

        status = "colleague_only"
        match_index = None
        match_row = None
        match_distance = nearest_distance
        match_score = best_name_score

        if nearest and nearest_distance is not None and nearest_distance <= DISTANCE_MATCH_M:
            status = "matched_by_distance"
            match_index, match_row = nearest
            match_score = text_score(colleague_name, row_name(match_row, "name", "osm_name"))
        elif best_name and best_name_score >= NAME_MATCH_SCORE:
            status = "matched_by_name"
            match_index, match_row = best_name
            if colleague_lat is not None and colleague_lon is not None:
                ours_lat = to_float(match_row.get("lat", ""))
                ours_lon = to_float(match_row.get("lon", ""))
                if ours_lat is not None and ours_lon is not None:
                    match_distance = haversine_m(colleague_lat, colleague_lon, ours_lat, ours_lon)

        if match_index is not None:
            matched_ours.add(match_index)

        report_rows.append(
            {
                "compare_status": status,
                "distance_m": round(match_distance, 2) if match_distance is not None else "",
                "name_score": round(match_score, 3),
                "colleague_name": colleague.get("name", ""),
                "colleague_google_name": colleague.get("google_name", ""),
                "colleague_lat": colleague.get("lat", ""),
                "colleague_lon": colleague.get("lng", ""),
                "colleague_address": colleague.get("address", ""),
                "colleague_url": colleague.get("google_maps_url", ""),
                "ours_id": match_row.get("id", "") if match_row else "",
                "ours_name": match_row.get("name", "") if match_row else "",
                "ours_lat": match_row.get("lat", "") if match_row else "",
                "ours_lon": match_row.get("lon", "") if match_row else "",
                "ours_source": match_row.get("source", "") if match_row else "",
                "ours_status": match_row.get("final_status", "") if match_row else "",
            }
        )

    for ours_index, ours in enumerate(ours_rows):
        if ours_index in matched_ours:
            continue
        report_rows.append(
            {
                "compare_status": "ours_only",
                "distance_m": "",
                "name_score": "",
                "colleague_name": "",
                "colleague_google_name": "",
                "colleague_lat": "",
                "colleague_lon": "",
                "colleague_address": "",
                "colleague_url": "",
                "ours_id": ours.get("id", ""),
                "ours_name": ours.get("name", ""),
                "ours_lat": ours.get("lat", ""),
                "ours_lon": ours.get("lon", ""),
                "ours_source": ours.get("source", ""),
                "ours_status": ours.get("final_status", ""),
            }
        )

    report_path = REPORT_DIR / "colleague_compare_report.csv"
    write_csv(report_path, report_rows)

    matched_distance = [row for row in report_rows if row["compare_status"] == "matched_by_distance"]
    matched_name = [row for row in report_rows if row["compare_status"] == "matched_by_name"]
    colleague_only = [row for row in report_rows if row["compare_status"] == "colleague_only"]
    ours_only = [row for row in report_rows if row["compare_status"] == "ours_only"]

    write_csv(REPORT_DIR / "colleague_compare_A_has_B_missing.csv", colleague_only)
    write_csv(REPORT_DIR / "colleague_compare_B_has_A_missing.csv", ours_only)
    write_csv(REPORT_DIR / "colleague_compare_matched_by_distance.csv", matched_distance)
    write_csv(REPORT_DIR / "colleague_compare_name_match_review.csv", matched_name)

    attribute_summary = [
        *attribute_rows(A_NAME, colleague_rows, colleague_fields),
        *attribute_rows(B_NAME, ours_rows, ours_fields),
    ]
    write_csv(REPORT_DIR / "colleague_compare_attribute_completeness.csv", attribute_summary)

    column_difference = {
        "a_dataset": A_NAME,
        "b_dataset": B_NAME,
        "a_columns": colleague_fields,
        "b_columns": ours_fields,
        "a_only_columns": sorted(set(colleague_fields) - set(ours_fields)),
        "b_only_columns": sorted(set(ours_fields) - set(colleague_fields)),
        "same_name_columns": sorted(set(colleague_fields) & set(ours_fields)),
        "equivalent_columns": {
            "A.lng": "B.lon",
            "A.google_maps_url": "B.source_url",
            "A.google_name": "B.name or B.osm_name",
            "A.address": "B.formatted_address",
            "A.cid": "B.google_cid",
            "A.place_id": "B.google_place_id",
        },
    }
    (REPORT_DIR / "colleague_compare_column_difference.json").write_text(
        json.dumps(column_difference, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = {
        "a_dataset": A_NAME,
        "b_dataset": B_NAME,
        "a_total": len(colleague_rows),
        "b_total": len(ours_rows),
        "matched_by_distance": sum(row["compare_status"] == "matched_by_distance" for row in report_rows),
        "matched_by_name": sum(row["compare_status"] == "matched_by_name" for row in report_rows),
        "a_only": sum(row["compare_status"] == "colleague_only" for row in report_rows),
        "b_only": sum(row["compare_status"] == "ours_only" for row in report_rows),
        "distance_match_threshold_m": DISTANCE_MATCH_M,
        "name_match_score": NAME_MATCH_SCORE,
        "report": str(report_path.relative_to(ROOT)),
        "a_has_b_missing_report": "data\\report\\colleague_compare_A_has_B_missing.csv",
        "b_has_a_missing_report": "data\\report\\colleague_compare_B_has_A_missing.csv",
        "matched_by_distance_report": "data\\report\\colleague_compare_matched_by_distance.csv",
        "name_match_review_report": "data\\report\\colleague_compare_name_match_review.csv",
        "attribute_completeness_report": "data\\report\\colleague_compare_attribute_completeness.csv",
        "column_difference_report": "data\\report\\colleague_compare_column_difference.json",
        "markdown_summary": "data\\report\\colleague_compare_summary.md",
    }
    summary_path = REPORT_DIR / "colleague_compare_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown_summary(REPORT_DIR / "colleague_compare_summary.md", summary, colleague_only, ours_only, matched_name)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
