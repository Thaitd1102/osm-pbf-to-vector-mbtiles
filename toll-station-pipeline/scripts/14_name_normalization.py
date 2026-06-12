from __future__ import annotations

import csv
import math
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PIPELINE_ROOT / "data"
CLEAN_CSV = DATA_DIR / "clean" / "toll_stations_clean.csv"
COLLEAGUE_CSV = DATA_DIR / "final" / "tram_thu_phi.csv"
OSM_NAME_UPDATES_CSV = DATA_DIR / "report" / "merged_osm_name_updates.csv"
OUTPUT_DIR = DATA_DIR / "name-normalization"


GENERIC_NAMES = {
    "tram thu phi",
    "tram thu phi etc",
    "tram thu phi khong dung",
    "toll booth",
    "toll gantry",
    "tram thu phi loi vao cao toc",
}
ROAD_PREFIXES = ("duong ", "di cao toc ", "cao toc ", "quoc lo ", "ql", "ct", "dt", "dt.")


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_text(value: object) -> str:
    text = clean(value).lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d")
    text = re.sub(r"[\-–—_/(),.;:+]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\bkm\s*(\d+)\b", r"km \1", text)
    text = re.sub(r"\bql\s*(\d+[a-z]?)\b", r"quoc lo \1", text)
    return text


def display_name(value: object) -> str:
    text = re.sub(r"\s+", " ", clean(value)).strip()
    text = re.sub(r"\bKm\s*(\d+)", r"Km \1", text, flags=re.IGNORECASE)
    return text


def as_float(value: object) -> float | None:
    text = clean(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def similarity(a: str, b: str) -> float:
    left = normalize_text(a)
    right = normalize_text(b)
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def is_placeholder_name(name: str) -> bool:
    normalized = normalize_text(name)
    return bool(re.fullmatch(r"osm toll \d+", normalized)) or normalized in {"", "unknown", "none"}


def is_generic_name(name: str) -> bool:
    return normalize_text(name) in GENERIC_NAMES


def looks_like_road_name(name: str) -> bool:
    normalized = normalize_text(name)
    return normalized.startswith(ROAD_PREFIXES) and "tram thu phi" not in normalized


def canonical_name(name: str) -> str:
    text = display_name(name)
    text = re.sub(r"(?i)^trạm thu phí", "Trạm thu phí", text)
    text = re.sub(r"(?i)^trạm thu phi", "Trạm thu phí", text)
    text = re.sub(r"(?i)^trạm", "Trạm", text)
    return text


def add_candidate(candidates: list[dict[str, str]], source: str, name: object, confidence: str = "") -> None:
    value = display_name(name)
    if not value:
        return
    normalized = normalize_text(value)
    if not normalized:
        return
    if any(item["name_normalized"] == normalized and item["source"] == source for item in candidates):
        return
    candidates.append(
        {
            "source": source,
            "name": value,
            "name_normalized": normalized,
            "candidate_confidence": confidence,
        }
    )


def colleague_index(rows: list[dict[str, str]]) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]], list[dict[str, str]]]:
    by_place: dict[str, dict[str, str]] = {}
    by_cid: dict[str, dict[str, str]] = {}
    for row in rows:
        place_id = clean(row.get("place_id"))
        cid = clean(row.get("cid"))
        if place_id:
            by_place[place_id] = row
        if cid:
            by_cid[cid] = row
    return by_place, by_cid, rows


def nearest_colleague(row: dict[str, str], colleague_rows: list[dict[str, str]]) -> dict[str, str] | None:
    lat = as_float(row.get("lat"))
    lon = as_float(row.get("lon"))
    if lat is None or lon is None:
        return None
    best: tuple[float, dict[str, str]] | None = None
    for candidate in colleague_rows:
        c_lat = as_float(candidate.get("lat"))
        c_lon = as_float(candidate.get("lng"))
        if c_lat is None or c_lon is None:
            continue
        distance = haversine(lat, lon, c_lat, c_lon)
        if distance <= 80 and (best is None or distance < best[0]):
            best = (distance, candidate)
    return best[1] if best else None


def load_osm_updates(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    updates: dict[str, dict[str, str]] = {}
    for row in rows:
        for key in (clean(row.get("google_place_id")), clean(row.get("osm_id"))):
            if key:
                updates[key] = row
    return updates


def choose_suggestion(current_name: str, candidates: list[dict[str, str]], row: dict[str, str]) -> tuple[str, str, str]:
    high_priority_sources = ["reviewed_osm_name", "google_name", "colleague_google_name", "colleague_name", "current_name"]
    source_lookup = {item["source"]: item["name"] for item in candidates}

    if is_placeholder_name(current_name) or is_generic_name(current_name) or looks_like_road_name(current_name):
        for source in high_priority_sources:
            name = source_lookup.get(source, "")
            if name and not is_placeholder_name(name) and not is_generic_name(name) and not looks_like_road_name(name):
                return canonical_name(name), "rename", f"current name is weak; use {source}"

    osm_name = clean(row.get("osm_name"))
    if osm_name and similarity(current_name, osm_name) < 0.55 and not looks_like_road_name(osm_name):
        google_name = source_lookup.get("google_name") or source_lookup.get("colleague_google_name")
        if google_name and similarity(google_name, current_name) >= 0.72:
            return canonical_name(current_name), "keep", "current name matches Google better than OSM"

    return canonical_name(current_name), "keep", "current name is acceptable by rules"


def detect_issues(row: dict[str, str], candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    current_name = clean(row.get("name"))
    osm_name = clean(row.get("osm_name"))
    candidate_names = [item["name"] for item in candidates]
    unique_norms = {item["name_normalized"] for item in candidates}

    def add(issue_type: str, severity: str, reason: str) -> None:
        issues.append({"issue_type": issue_type, "severity": severity, "reason": reason})

    if not current_name:
        add("missing_name", "high", "object has no current name")
    if is_generic_name(current_name):
        add("generic_name", "high", "current name is too generic")
    if is_placeholder_name(current_name):
        add("placeholder_name", "high", "current name is an OSM placeholder")
    if looks_like_road_name(current_name):
        add("road_name_as_object_name", "medium", "current name looks like road/direction name")
    if osm_name and is_placeholder_name(osm_name):
        add("osm_placeholder_name", "medium", "matched OSM name is placeholder")
    if osm_name and looks_like_road_name(osm_name):
        add("osm_road_name_as_object_name", "medium", "matched OSM name looks like road/direction name")
    if len(unique_norms) >= 3:
        add("multiple_name_variants", "medium", f"found {len(unique_norms)} distinct candidate names")
    if osm_name and current_name and similarity(current_name, osm_name) < 0.55:
        add("source_name_conflict", "medium", f"current name differs from OSM name: {osm_name}")
    if not clean(row.get("province")):
        add("missing_province_context", "low", "province is missing, harder to standardize name")
    if not clean(row.get("road")) and any("cao tốc" in name.lower() or "ql" in name.lower() for name in candidate_names):
        add("missing_road_context", "low", "road context appears in names but road field is empty")

    return issues


def build_object(row: dict[str, str], colleague_match: dict[str, str] | None, update_match: dict[str, str] | None) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, str]]:
    candidates: list[dict[str, str]] = []
    add_candidate(candidates, "current_name", row.get("name"), "0.90")
    add_candidate(candidates, "osm_name", row.get("osm_name"), "0.65")
    add_candidate(candidates, "road", row.get("road"), "0.35")

    if update_match:
        add_candidate(candidates, "reviewed_osm_name", update_match.get("new_osm_name"), "0.95")
        add_candidate(candidates, "review_google_name", update_match.get("google_name"), "0.85")

    if colleague_match:
        add_candidate(candidates, "colleague_name", colleague_match.get("name"), "0.75")
        add_candidate(candidates, "colleague_google_name", colleague_match.get("google_name"), "0.85")

    add_candidate(candidates, "google_name", row.get("name"), clean(row.get("confidence")) or "0.80")

    issues = detect_issues(row, candidates)
    suggested_name, suggested_action, suggestion_reason = choose_suggestion(row.get("name", ""), candidates, row)
    object_record = {
        "object_id": clean(row.get("id")),
        "object_type": "toll_station",
        "lat": clean(row.get("lat")),
        "lon": clean(row.get("lon")),
        "current_name": clean(row.get("name")),
        "suggested_name": suggested_name,
        "suggested_action": suggested_action,
        "suggestion_reason": suggestion_reason,
        "issue_count": str(len(issues)),
        "issue_types": ";".join(issue["issue_type"] for issue in issues),
        "province": clean(row.get("province")),
        "road": clean(row.get("road")),
        "address": clean(row.get("address")),
        "osm_id": clean(row.get("osm_id")),
        "osm_name": clean(row.get("osm_name")),
        "google_place_id": clean(row.get("google_place_id")),
        "source_datasets": clean(row.get("source_datasets")),
        "candidate_names": " | ".join(item["name"] for item in candidates),
    }
    return candidates, issues, object_record


def main() -> None:
    clean_rows = read_csv(CLEAN_CSV)
    colleague_by_place, colleague_by_cid, colleague_rows = colleague_index(read_csv(COLLEAGUE_CSV))
    osm_updates = load_osm_updates(read_csv(OSM_NAME_UPDATES_CSV))

    candidate_rows: list[dict[str, object]] = []
    issue_rows: list[dict[str, object]] = []
    object_rows: list[dict[str, str]] = []

    for row in clean_rows:
        colleague_match = (
            colleague_by_place.get(clean(row.get("google_place_id")))
            or colleague_by_cid.get(clean(row.get("google_cid")))
            or nearest_colleague(row, colleague_rows)
        )
        update_match = osm_updates.get(clean(row.get("google_place_id"))) or osm_updates.get(clean(row.get("osm_id")))
        candidates, issues, object_record = build_object(row, colleague_match, update_match)
        object_rows.append(object_record)

        for candidate in candidates:
            candidate_rows.append(
                {
                    "object_id": object_record["object_id"],
                    "object_type": "toll_station",
                    "candidate_source": candidate["source"],
                    "candidate_name": candidate["name"],
                    "candidate_name_normalized": candidate["name_normalized"],
                    "candidate_confidence": candidate["candidate_confidence"],
                    "current_name": object_record["current_name"],
                    "lat": object_record["lat"],
                    "lon": object_record["lon"],
                }
            )
        for issue in issues:
            issue_rows.append(
                {
                    "object_id": object_record["object_id"],
                    "object_type": "toll_station",
                    "current_name": object_record["current_name"],
                    "suggested_name": object_record["suggested_name"],
                    "issue_type": issue["issue_type"],
                    "severity": issue["severity"],
                    "reason": issue["reason"],
                    "candidate_names": object_record["candidate_names"],
                    "province": object_record["province"],
                    "road": object_record["road"],
                    "lat": object_record["lat"],
                    "lon": object_record["lon"],
                }
            )

    review_rows = []
    for item in object_rows:
        if item["issue_count"] == "0" and item["suggested_action"] == "keep":
            continue
        review_rows.append(
            {
                **item,
                "reviewed_name": "",
                "review_status": "",
                "review_note": "",
                "ai_suggested_name": "",
                "ai_confidence": "",
                "ai_reason": "",
            }
        )

    clean_name_rows = []
    for item in object_rows:
        clean_name_rows.append(
            {
                "object_id": item["object_id"],
                "object_type": item["object_type"],
                "current_name": item["current_name"],
                "suggested_name": item["suggested_name"],
                "suggested_action": item["suggested_action"],
                "issue_types": item["issue_types"],
                "province": item["province"],
                "road": item["road"],
                "lat": item["lat"],
                "lon": item["lon"],
            }
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(
        OUTPUT_DIR / "name_candidates.csv",
        candidate_rows,
        ["object_id", "object_type", "candidate_source", "candidate_name", "candidate_name_normalized", "candidate_confidence", "current_name", "lat", "lon"],
    )
    write_csv(
        OUTPUT_DIR / "name_issues.csv",
        issue_rows,
        ["object_id", "object_type", "current_name", "suggested_name", "issue_type", "severity", "reason", "candidate_names", "province", "road", "lat", "lon"],
    )
    write_csv(
        OUTPUT_DIR / "name_review.csv",
        review_rows,
        [
            "object_id", "object_type", "lat", "lon", "current_name", "suggested_name", "suggested_action",
            "suggestion_reason", "issue_count", "issue_types", "candidate_names", "province", "road", "address",
            "osm_id", "osm_name", "google_place_id", "source_datasets", "reviewed_name", "review_status",
            "review_note", "ai_suggested_name", "ai_confidence", "ai_reason",
        ],
    )
    write_csv(
        OUTPUT_DIR / "name_clean.csv",
        clean_name_rows,
        ["object_id", "object_type", "current_name", "suggested_name", "suggested_action", "issue_types", "province", "road", "lat", "lon"],
    )

    issue_counter = Counter(row["issue_type"] for row in issue_rows)
    severity_counter = Counter(row["severity"] for row in issue_rows)
    summary_lines = [
        "# Object Name Normalization",
        "",
        "## Input",
        "",
        f"- Clean toll stations: `{CLEAN_CSV.relative_to(PIPELINE_ROOT)}`",
        f"- Colleague Google dataset: `{COLLEAGUE_CSV.relative_to(PIPELINE_ROOT)}`",
        f"- Reviewed OSM name updates: `{OSM_NAME_UPDATES_CSV.relative_to(PIPELINE_ROOT)}`",
        "",
        "## Output",
        "",
        "- `name_candidates.csv`: tất cả tên ứng viên theo từng object.",
        "- `name_issues.csv`: các lỗi tên phát hiện bằng rule.",
        "- `name_review.csv`: file để review tay hoặc đưa AI gợi ý.",
        "- `name_clean.csv`: tên đề xuất hiện tại sau rule-based pass.",
        "",
        "## Count",
        "",
        f"- Objects: {len(object_rows)}",
        f"- Candidate name rows: {len(candidate_rows)}",
        f"- Issue rows: {len(issue_rows)}",
        f"- Objects needing review: {len(review_rows)}",
        "",
        "## Issue Types",
        "",
    ]
    for issue_type, count in issue_counter.most_common():
        summary_lines.append(f"- {issue_type}: {count}")
    summary_lines.extend(["", "## Severity", ""])
    for severity, count in severity_counter.most_common():
        summary_lines.append(f"- {severity}: {count}")
    summary_lines.extend(
        [
            "",
            "## Suggested Next Step",
            "",
            "1. Mở `name_review.csv` để duyệt các dòng có issue.",
            "2. Điền `reviewed_name`, `review_status` = keep/rename/manual_review.",
            "3. Với các dòng khó, dùng AI điền `ai_suggested_name`, `ai_confidence`, `ai_reason` trước khi review.",
            "4. Sau khi review xong, apply ngược vào clean dataset/OSM output.",
        ]
    )
    (OUTPUT_DIR / "summary.md").write_text("\n".join(summary_lines), encoding="utf-8")

    print(f"Wrote name normalization outputs to {OUTPUT_DIR.relative_to(PIPELINE_ROOT)}")
    print(f"Objects: {len(object_rows)}")
    print(f"Issue rows: {len(issue_rows)}")
    print(f"Review rows: {len(review_rows)}")


if __name__ == "__main__":
    main()
