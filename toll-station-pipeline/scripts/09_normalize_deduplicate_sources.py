from __future__ import annotations

import csv
import json
import math
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
INPUT_A = DATA_DIR / "final" / "tram_thu_phi.csv"
INPUT_B = DATA_DIR / "final" / "merged_toll_stations_final.csv"
OUTPUT_DIR = DATA_DIR / "normalization"

DISTANCE_DUPLICATE_M = 120.0
DISTANCE_NEAR_NAME_M = 350.0
NAME_DUPLICATE_SCORE = 0.82
NAME_REVIEW_SCORE = 0.9


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows and not fieldnames:
        path.write_text("", encoding="utf-8-sig")
        return
    fieldnames = fieldnames or list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def strip_accents(value: str) -> str:
    text = unicodedata.normalize("NFD", value or "")
    return "".join(char for char in text if unicodedata.category(char) != "Mn")


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFC", value or "").strip()
    text = re.sub(r"\s+", " ", text)
    replacements = {
        "TRẠM THU PHÍ": "Trạm thu phí",
        "Trạm Thu Phí": "Trạm thu phí",
        "Trạm Thu phí": "Trạm thu phí",
        "Trạm thu phí": "Trạm thu phí",
        "BOT ": "BOT ",
        "QL ": "QL",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def match_key(value: str) -> str:
    text = strip_accents(value).lower()
    text = re.sub(r"\btram\b|\bthu\b|\bphi\b|\bbot\b|\betc\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def name_score(left: str, right: str) -> float:
    left_key = match_key(left)
    right_key = match_key(right)
    if not left_key or not right_key:
        return 0.0
    return SequenceMatcher(None, left_key, right_key).ratio()


def to_float(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class DisjointSet:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def candidate_from_a(index: int, row: dict[str, str]) -> dict[str, object]:
    name = row.get("google_name") or row.get("name", "")
    lat = to_float(row.get("lat"))
    lon = to_float(row.get("lng"))
    return {
        "candidate_id": f"A-{index + 1:03d}",
        "dataset": "A_colleague",
        "source_file": "tram_thu_phi.csv",
        "source_original_id": row.get("place_id") or row.get("cid") or f"A-{index + 1:03d}",
        "name_raw": row.get("name", ""),
        "name_google": row.get("google_name", ""),
        "name_normalized": normalize_name(name),
        "name_match_key": match_key(name),
        "lat": lat,
        "lon": lon,
        "address": row.get("address", ""),
        "province": "",
        "road": "",
        "operator": "",
        "source_url": row.get("google_maps_url", ""),
        "google_place_id": row.get("place_id", ""),
        "google_cid": row.get("cid", ""),
        "osm_id": "",
        "osm_name": "",
        "confidence": "",
        "tags": "",
        "status": row.get("status", ""),
        "review_status": "pending",
    }


def candidate_from_b(index: int, row: dict[str, str]) -> dict[str, object]:
    name = row.get("name", "")
    lat = to_float(row.get("lat"))
    lon = to_float(row.get("lon"))
    return {
        "candidate_id": f"B-{index + 1:03d}",
        "dataset": "B_final",
        "source_file": "merged_toll_stations_final.csv",
        "source_original_id": row.get("id", ""),
        "name_raw": name,
        "name_google": "",
        "name_normalized": normalize_name(name),
        "name_match_key": match_key(name),
        "lat": lat,
        "lon": lon,
        "address": row.get("formatted_address", ""),
        "province": row.get("province", ""),
        "road": row.get("road", ""),
        "operator": row.get("operator", ""),
        "source_url": row.get("source_url", ""),
        "google_place_id": row.get("google_place_id", ""),
        "google_cid": row.get("google_cid", ""),
        "osm_id": row.get("osm_id", ""),
        "osm_name": row.get("osm_name", ""),
        "confidence": row.get("confidence", ""),
        "tags": row.get("tags", ""),
        "status": row.get("final_status") or row.get("status", ""),
        "review_status": "pending",
    }


def duplicate_reason(left: dict[str, object], right: dict[str, object]) -> tuple[str, float | None, float]:
    left_place = str(left.get("google_place_id") or "").strip()
    right_place = str(right.get("google_place_id") or "").strip()
    if left_place and right_place and left_place == right_place:
        return "same_google_place_id", None, 1.0

    left_cid = str(left.get("google_cid") or "").strip()
    right_cid = str(right.get("google_cid") or "").strip()
    if left_cid and right_cid and left_cid == right_cid:
        return "same_google_cid", None, 1.0

    lat1 = left.get("lat")
    lon1 = left.get("lon")
    lat2 = right.get("lat")
    lon2 = right.get("lon")
    distance = None
    if isinstance(lat1, float) and isinstance(lon1, float) and isinstance(lat2, float) and isinstance(lon2, float):
        distance = haversine_m(lat1, lon1, lat2, lon2)

    score = name_score(str(left.get("name_normalized") or ""), str(right.get("name_normalized") or ""))
    if distance is not None and distance <= DISTANCE_DUPLICATE_M:
        return "near_same_location", distance, score
    if distance is not None and distance <= DISTANCE_NEAR_NAME_M and score >= NAME_DUPLICATE_SCORE:
        return "near_location_similar_name", distance, score
    if distance is not None and distance <= 2000 and score >= NAME_REVIEW_SCORE:
        return "similar_name_needs_review", distance, score
    return "", distance, score


def main() -> None:
    rows_a = read_csv(INPUT_A)
    rows_b = read_csv(INPUT_B)
    candidates = [candidate_from_a(index, row) for index, row in enumerate(rows_a)]
    candidates.extend(candidate_from_b(index, row) for index, row in enumerate(rows_b))

    dsu = DisjointSet(len(candidates))
    pair_rows: list[dict[str, object]] = []

    for left_index, left in enumerate(candidates):
        for right_index in range(left_index + 1, len(candidates)):
            right = candidates[right_index]
            reason, distance, score = duplicate_reason(left, right)
            if not reason:
                continue
            dsu.union(left_index, right_index)
            pair_rows.append(
                {
                    "pair_status": reason,
                    "distance_m": round(distance, 2) if distance is not None else "",
                    "name_score": round(score, 3),
                    "left_candidate_id": left["candidate_id"],
                    "left_dataset": left["dataset"],
                    "left_name": left["name_normalized"],
                    "left_lat": left["lat"],
                    "left_lon": left["lon"],
                    "right_candidate_id": right["candidate_id"],
                    "right_dataset": right["dataset"],
                    "right_name": right["name_normalized"],
                    "right_lat": right["lat"],
                    "right_lon": right["lon"],
                    "suggested_action": "merge_if_same_station" if reason != "similar_name_needs_review" else "manual_check",
                }
            )

    group_members: dict[int, list[int]] = {}
    for index in range(len(candidates)):
        root = dsu.find(index)
        group_members.setdefault(root, []).append(index)

    duplicate_groups = {root: members for root, members in group_members.items() if len(members) > 1}
    group_id_by_root = {root: f"DUP-{position + 1:03d}" for position, root in enumerate(sorted(duplicate_groups))}

    candidate_rows: list[dict[str, object]] = []
    for index, candidate in enumerate(candidates):
        root = dsu.find(index)
        row = dict(candidate)
        row["duplicate_group_id"] = group_id_by_root.get(root, "")
        row["duplicate_group_size"] = len(group_members[root])
        row["duplicate_status"] = "duplicate_candidate" if root in duplicate_groups else "unique_candidate"
        candidate_rows.append(row)

    duplicate_review_rows: list[dict[str, object]] = []
    for root, members in sorted(duplicate_groups.items(), key=lambda item: group_id_by_root[item[0]]):
        group_id = group_id_by_root[root]
        group_candidates = [candidate_rows[index] for index in members]
        preferred = next((row for row in group_candidates if row["dataset"] == "B_final"), group_candidates[0])
        for row in group_candidates:
            duplicate_review_rows.append(
                {
                    "duplicate_group_id": group_id,
                    "group_size": len(group_candidates),
                    "candidate_id": row["candidate_id"],
                    "dataset": row["dataset"],
                    "name_normalized": row["name_normalized"],
                    "lat": row["lat"],
                    "lon": row["lon"],
                    "address": row["address"],
                    "google_cid": row["google_cid"],
                    "google_place_id": row["google_place_id"],
                    "osm_id": row["osm_id"],
                    "preferred_candidate_id": preferred["candidate_id"],
                    "suggested_action": "keep_preferred_or_merge_fields",
                    "review_decision": "",
                    "review_note": "",
                }
            )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT_DIR / "toll_stations_normalized_candidates.csv", candidate_rows)
    write_csv(OUTPUT_DIR / "toll_duplicate_pairs.csv", pair_rows)
    write_csv(OUTPUT_DIR / "toll_duplicate_review.csv", duplicate_review_rows)

    summary = {
        "input_a": str(INPUT_A.relative_to(ROOT)),
        "input_b": str(INPUT_B.relative_to(ROOT)),
        "a_total": len(rows_a),
        "b_total": len(rows_b),
        "candidate_total": len(candidates),
        "unique_candidate_total": sum(1 for row in candidate_rows if row["duplicate_status"] == "unique_candidate"),
        "duplicate_candidate_total": sum(1 for row in candidate_rows if row["duplicate_status"] == "duplicate_candidate"),
        "duplicate_group_total": len(duplicate_groups),
        "duplicate_pair_total": len(pair_rows),
        "distance_duplicate_m": DISTANCE_DUPLICATE_M,
        "distance_near_name_m": DISTANCE_NEAR_NAME_M,
        "name_duplicate_score": NAME_DUPLICATE_SCORE,
        "name_review_score": NAME_REVIEW_SCORE,
    }
    (OUTPUT_DIR / "toll_normalization_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUTPUT_DIR / "toll_normalization_summary.md").write_text(
        f"""# Chuẩn hóa và check trùng dữ liệu trạm thu phí

## Input

- A: `{summary["input_a"]}` ({summary["a_total"]} dòng)
- B: `{summary["input_b"]}` ({summary["b_total"]} dòng)

## Output

- `toll_stations_normalized_candidates.csv`: toàn bộ candidate sau khi chuẩn hóa cột/tên.
- `toll_duplicate_review.csv`: danh sách nhóm nghi trùng để review tay.
- `toll_duplicate_pairs.csv`: các cặp tạo thành nhóm nghi trùng.
- `toll_normalization_summary.json`: thống kê dạng JSON.

## Thống kê

- Tổng candidate sau khi gộp A+B: {summary["candidate_total"]}
- Candidate unique tạm thời: {summary["unique_candidate_total"]}
- Candidate nằm trong nhóm nghi trùng: {summary["duplicate_candidate_total"]}
- Số nhóm nghi trùng: {summary["duplicate_group_total"]}
- Số cặp nghi trùng: {summary["duplicate_pair_total"]}

## Tiêu chí nghi trùng

- Trùng `google_place_id`.
- Trùng `google_cid`.
- Tọa độ cách nhau <= {DISTANCE_DUPLICATE_M} m.
- Tọa độ cách nhau <= {DISTANCE_NEAR_NAME_M} m và tên tương đồng >= {NAME_DUPLICATE_SCORE}.
- Tên tương đồng >= {NAME_REVIEW_SCORE} trong phạm vi 2 km thì đưa vào manual check.

## Cách xử lý tiếp

1. Mở `toll_duplicate_review.csv`.
2. Với mỗi `duplicate_group_id`, chọn candidate nên giữ ở cột `review_decision`.
3. Ưu tiên giữ record B nếu đã có metadata pipeline/OSM/tags.
4. Bổ sung thông tin Google Maps từ A nếu A có address/url/cid tốt hơn.
5. Sau review mới sinh clean dataset và import DB.
""",
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
