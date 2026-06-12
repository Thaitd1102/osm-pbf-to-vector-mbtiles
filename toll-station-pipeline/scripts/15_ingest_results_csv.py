import csv
import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_RESULTS = ROOT / "data" / "final" / "results.csv"
CLEAN_DATASET = ROOT / "data" / "clean" / "toll_stations_clean.csv"
OUT_CSV = ROOT / "data" / "final" / "results_clean_candidates.csv"
OUT_JSON = ROOT / "data" / "final" / "results_clean_candidates.json"
OUT_REVIEW_CSV = ROOT / "data" / "final" / "results_review.csv"


OUTPUT_COLUMNS = [
    "id",
    "name",
    "category",
    "address",
    "lat",
    "lon",
    "google_place_id",
    "google_cid",
    "google_maps_url",
    "thumbnail",
    "image_url",
    "review_count",
    "review_rating",
    "source",
    "match_status",
    "nearest_clean_name",
    "nearest_clean_distance_m",
    "action_suggestion",
]

REVIEW_COLUMNS = OUTPUT_COLUMNS + [
    "review_decision",
    "corrected_name",
    "corrected_address",
    "review_note",
]


def normalize_text(value):
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", value)


def stable_id(row):
    raw_key = row.get("place_id") or row.get("cid") or (
        f"{row.get('title', '')}|{row.get('latitude', '')}|{row.get('longitude', '')}"
    )
    digest = hashlib.sha1(raw_key.encode("utf-8")).hexdigest()[:14]
    return f"vn-toll-results-{digest}"


def distance_m(lat1, lon1, lat2, lon2):
    radius = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_int(value):
    value = (value or "").replace(",", "").strip()
    try:
        return int(value)
    except ValueError:
        return 0


def first_image(row):
    thumbnail = (row.get("thumbnail") or "").strip()
    images_raw = row.get("images") or ""
    try:
        images = json.loads(images_raw)
    except json.JSONDecodeError:
        images = []

    image_url = ""
    if isinstance(images, list):
        for item in images:
            if isinstance(item, dict) and item.get("image"):
                image_url = item["image"]
                break

    return thumbnail, image_url or thumbnail


def is_toll_candidate(row):
    title = normalize_text(row.get("title"))
    category = normalize_text(row.get("category"))
    address = normalize_text(row.get("address"))
    text = f"{title} {category} {address}"

    title_is_toll = (
        title.startswith("tram thu phi")
        or title.startswith("tram thu ve")
        or re.search(r"\btram\s+bot\b", title)
        or re.search(r"\bbot\b", title)
    )
    negative = (
        "diem dan the" in text
        or "dan the" in text
        or "dich vu van tai" in category
        or "tram sac xe dien" in category
        or "tram xe buyt" in category
        or "tram nghi" in category
        or "nha hang" in category
        or "bai do xe" in category
        or "van phong cong ty" in category
        or "trung tam" in category
        or "khach san" in category
        or "cua hang" in category
        or "quan ca phe" in category
        or "noi tho cung" in category
        or "bao tang" in category
        or "ben du thuyen" in category
    )

    if negative:
        return False

    # Category "Trạm thu phí" is the cleanest Google Maps signal.
    if category == "tram thu phi":
        return True

    # Some useful results are tagged as generic construction/blank but have a
    # clear toll-station title. Keep these, but do not trust address-only hits.
    generic_category = category in {"", "cong trinh xay dung", "so giao thong van tai", "cau"}
    return bool(title_is_toll and generic_category)


def quality_score(row):
    title = normalize_text(row.get("title"))
    category = normalize_text(row.get("category"))
    score = parse_int(row.get("review_count"))

    if "tram thu phi" in category:
        score += 10_000
    if "tram thu phi" in title:
        score += 2_000
    if row.get("thumbnail"):
        score += 100
    if row.get("address"):
        score += 50
    return score


def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def unique_candidates(rows):
    selected = {}
    for row in rows:
        if not is_toll_candidate(row):
            continue

        lat = parse_float(row.get("latitude"))
        lon = parse_float(row.get("longitude"))
        if lat is None or lon is None:
            continue

        key = row.get("place_id") or row.get("cid")
        if not key:
            key = f"{normalize_text(row.get('title'))}|{round(lat, 5)}|{round(lon, 5)}"

        current = selected.get(key)
        if current is None or quality_score(row) > quality_score(current):
            selected[key] = row

    return list(selected.values())


def build_clean_index(clean_rows):
    place_ids = {row.get("google_place_id", "") for row in clean_rows if row.get("google_place_id")}
    cids = {row.get("google_cid", "") for row in clean_rows if row.get("google_cid")}
    points = []

    for row in clean_rows:
        lat = parse_float(row.get("lat"))
        lon = parse_float(row.get("lon"))
        if lat is not None and lon is not None:
            points.append((lat, lon, row.get("name", "")))

    return place_ids, cids, points


def nearest_clean(lat, lon, clean_points):
    best_name = ""
    best_distance = None
    for clean_lat, clean_lon, clean_name in clean_points:
        current = distance_m(lat, lon, clean_lat, clean_lon)
        if best_distance is None or current < best_distance:
            best_distance = current
            best_name = clean_name
    return best_name, best_distance


def classify(row, clean_place_ids, clean_cids, clean_points):
    place_id = row.get("place_id") or ""
    cid = row.get("cid") or ""
    lat = parse_float(row.get("latitude"))
    lon = parse_float(row.get("longitude"))
    nearest_name, nearest_distance = nearest_clean(lat, lon, clean_points)

    if (place_id and place_id in clean_place_ids) or (cid and cid in clean_cids):
        return "already_in_clean_by_google_id", nearest_name, nearest_distance, "keep_as_reference"
    if nearest_distance is not None and nearest_distance <= 100:
        return "already_in_clean_by_distance", nearest_name, nearest_distance, "review_name_or_metadata"
    if nearest_distance is not None and nearest_distance <= 500:
        return "possible_duplicate_nearby", nearest_name, nearest_distance, "manual_review"
    return "new_candidate", nearest_name, nearest_distance, "review_before_merge"


def to_output_row(row, clean_place_ids, clean_cids, clean_points):
    thumbnail, image_url = first_image(row)
    lat = parse_float(row.get("latitude"))
    lon = parse_float(row.get("longitude"))
    match_status, nearest_name, nearest_distance, action = classify(
        row, clean_place_ids, clean_cids, clean_points
    )

    return {
        "id": stable_id(row),
        "name": (row.get("title") or "").strip(),
        "category": (row.get("category") or "").strip(),
        "address": (row.get("address") or "").strip(),
        "lat": lat,
        "lon": lon,
        "google_place_id": (row.get("place_id") or "").strip(),
        "google_cid": (row.get("cid") or "").strip(),
        "google_maps_url": (row.get("link") or "").strip(),
        "thumbnail": thumbnail,
        "image_url": image_url,
        "review_count": parse_int(row.get("review_count")),
        "review_rating": (row.get("review_rating") or "").strip(),
        "source": "colleague_google_maps_results",
        "match_status": match_status,
        "nearest_clean_name": nearest_name,
        "nearest_clean_distance_m": (
            round(nearest_distance, 2) if nearest_distance is not None else ""
        ),
        "action_suggestion": action,
    }


def write_outputs(rows):
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    with OUT_JSON.open("w", encoding="utf-8") as file:
        json.dump(rows, file, ensure_ascii=False, indent=2)

    review_rows = []
    for row in rows:
        if row["match_status"] not in {"new_candidate", "possible_duplicate_nearby"}:
            continue
        review_row = dict(row)
        review_row["review_decision"] = ""
        review_row["corrected_name"] = ""
        review_row["corrected_address"] = ""
        review_row["review_note"] = ""
        review_rows.append(review_row)

    with OUT_REVIEW_CSV.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(review_rows)

    return len(review_rows)


def main():
    raw_rows = read_csv(RAW_RESULTS)
    clean_rows = read_csv(CLEAN_DATASET)
    candidates = unique_candidates(raw_rows)
    clean_place_ids, clean_cids, clean_points = build_clean_index(clean_rows)

    output_rows = [
        to_output_row(row, clean_place_ids, clean_cids, clean_points)
        for row in candidates
    ]
    output_rows.sort(
        key=lambda row: (
            row["match_status"] != "new_candidate",
            row["match_status"],
            row["name"],
        )
    )
    review_count = write_outputs(output_rows)

    status_counts = {}
    for row in output_rows:
        status_counts[row["match_status"]] = status_counts.get(row["match_status"], 0) + 1

    print(f"Raw rows              : {len(raw_rows)}")
    print(f"Unique toll candidates: {len(output_rows)}")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")
    print(f"Written CSV : {OUT_CSV}")
    print(f"Written JSON: {OUT_JSON}")
    print(f"Written review CSV: {OUT_REVIEW_CSV} ({review_count} rows)")


if __name__ == "__main__":
    main()
