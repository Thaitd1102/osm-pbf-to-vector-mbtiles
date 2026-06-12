import json
import re
import unicodedata
from pathlib import Path
from datetime import datetime, timezone


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
CRAWLER_RAW_DIR = PIPELINE_ROOT / "toll-crawler" / "data" / "raw"
GMAPS_RAW_DIR = PIPELINE_ROOT / "gmaps-tool" / "data" / "raw"
NORMALIZED_DIR = PIPELINE_ROOT / "data" / "normalized"

# ── Mapping tỉnh từ địa chỉ ─────────────────────────────────
PROVINCE_KEYWORDS = {
    "Đồng Nai": "Đồng Nai",
    "Hà Nội": "Hà Nội",
    "TP HCM": "TP. Hồ Chí Minh",
    "Hồ Chí Minh": "TP. Hồ Chí Minh",
    "Hải Phòng": "Hải Phòng",
    "Hải Dương": "Hải Dương",
    "Hà Nam": "Hà Nam",
    "Ninh Bình": "Ninh Bình",
    "Nghệ An": "Nghệ An",
    "Thanh Hóa": "Thanh Hóa",
    "Bình Định": "Bình Định",
    "Khánh Hòa": "Khánh Hòa",
    "Quảng Nam": "Quảng Nam",
    "Quảng Ngãi": "Quảng Ngãi",
    "Quảng Bình": "Quảng Bình",
    "Quảng Trị": "Quảng Trị",
    "Thừa Thiên Huế": "Thừa Thiên Huế",
    "Đà Nẵng": "Đà Nẵng",
    "Tiền Giang": "Tiền Giang",
    "Bình Dương": "Bình Dương",
    "Bình Thuận": "Bình Thuận",
    "Lâm Đồng": "Lâm Đồng",
    "Vĩnh Phúc": "Vĩnh Phúc",
    "Hòa Bình": "Hòa Bình",
    "Bắc Giang": "Bắc Giang",
    "Quảng Ninh": "Quảng Ninh",
    "Kiên Giang": "Kiên Giang",
    "Bà Rịa": "Bà Rịa - Vũng Tàu",
    "Vũng Tàu": "Bà Rịa - Vũng Tàu",
    "Thái Bình": "Thái Bình",
    "Nam Định": "Nam Định",
}

# ── Detect road từ tên/địa chỉ ──────────────────────────────
ROAD_PATTERNS = [
    (r"cao tốc\s+[\w\s\-–]+", "highway"),
    (r"QL\s*(\d+\w*)", "QL\\1"),
    (r"quốc lộ\s*(\d+\w*)", "QL\\1"),
    (r"CT\s*(\d+)", "CT\\1"),
]

# ── Detect type ──────────────────────────────────────────────
ETC_KEYWORDS = ["etc", "không dừng", "cao tốc", "gantry"]
BOOTH_KEYWORDS = ["bot", "dừng", "quốc lộ", "ql"]


def slugify(text: str) -> str:
    """Tạo ID từ tên trạm."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:60]


def extract_province(address: str) -> str:
    for keyword, province in PROVINCE_KEYWORDS.items():
        if keyword.lower() in address.lower():
            return province
    return ""


def extract_road(name: str, address: str) -> str:
    text = f"{name} {address}".lower()
    for pattern, road_fmt in ROAD_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            if "\\1" in road_fmt:
                return road_fmt.replace("\\1", m.group(1).upper())
            return m.group(0).title()
    return ""


def detect_type(name: str, address: str) -> str:
    text = f"{name} {address}".lower()
    for kw in ETC_KEYWORDS:
        if kw in text:
            return "etc"
    return "toll_booth"


def detect_confidence(record: dict) -> float:
    """
    Score 0.0 → 1.0 dựa trên độ đầy đủ data.
    """
    score = 0.5  # base từ crawl được
    if record.get("province"):
        score += 0.1
    if record.get("road"):
        score += 0.1
    if record.get("lat") and record.get("lon"):
        score += 0.2
    if record.get("km_marker"):
        score += 0.1
    return round(min(score, 1.0), 2)


def detect_operator(name: str, address: str, category: str = "") -> str:
    text = f"{name} {address} {category}".lower()
    if "vetc" in text:
        return "VETC"
    if "epass" in text or "vdtc" in text:
        return "ePass/VDTC"
    return ""


def gmaps_review_note(name: str, address: str, category: str) -> str:
    text = f"{name} {address} {category}".lower()
    notes = []
    if "dán thẻ" in text or "dan the" in text:
        notes.append("may be tag/service point, not toll station")
    if "văn phòng" in text or "cong ty" in text or "công ty" in text:
        notes.append("may be office/company, not toll station")
    if "trạm thu phí" not in text and "tram thu phi" not in text:
        notes.append("name does not explicitly contain toll station")
    return "; ".join(notes)


def is_junk(raw: dict) -> bool:
    """Filter record rác — dropdown, header, v.v."""
    name = raw.get("Tên trạm", "") or raw.get("col_2", "") or raw.get("name", "") or raw.get("col_1", "")
    junk_keywords = [
        "tìm các trạm",
        "chọn tỉnh",
        "toàn quốc của vetc",
        "tên trạm",
        "stt",
        "trạm trong vdtc",
    ]
    return any(kw in name.lower() for kw in junk_keywords)


def normalize_vetc(record: dict) -> dict | None:
    raw = record["raw"]

    if is_junk(raw):
        return None

    name = raw.get("Tên trạm", "").strip()
    address = raw.get("Địa chỉ", "").strip()

    if not name:
        return None

    province = extract_province(address)
    road = extract_road(name, address)
    toll_type = detect_type(name, address)

    normalized = {
        "id": f"vn-toll-{slugify(name)}",
        "name": name,
        "province": province,
        "road": road,
        "km_marker": "",        # VETC không có — để trống
        "type": toll_type,      # "etc" | "toll_booth"
        "operator": "VETC",
        "status": "active",
        "lat": None,
        "lon": None,
        "source": record["source"],
        "source_url": record["source_url"],
        "confidence": 0.0,      # tính sau
        "crawled_at": record["crawled_at"],
        # Geocode fields — điền ở bước sau
        "google_place_id": None,
        "formatted_address": address,
        "geocoded_at": None,
        # Snap fields — điền ở bước sau
        "snapped_lat": None,
        "snapped_lon": None,
        "nearest_highway_osm_id": None,
        "nearest_road_name": None,
        "snap_distance_m": None,
    }

    normalized["confidence"] = detect_confidence(normalized)
    return normalized


def normalize_osm(record: dict) -> dict | None:
    raw = record["raw"]
    name = raw.get("Tên trạm", "").strip()

    if not name and not raw.get("osm_id"):
        return None

    # OSM đã có tọa độ sẵn
    lat = raw.get("lat")
    lon = raw.get("lon")

    toll_type = "etc" if raw.get("highway") == "toll_gantry" else "toll_booth"

    normalized = {
        "id": f"vn-toll-osm-{raw.get('osm_id', '')}",
        "name": name or f"OSM toll {raw.get('osm_id')}",
        "province": "",
        "road": "",
        "km_marker": "",
        "type": toll_type,
        "operator": raw.get("operator", ""),
        "status": "active",
        "lat": lat,
        "lon": lon,
        "source": record["source"],
        "source_url": record["source_url"],
        "confidence": 0.7 if (lat and lon) else 0.3,
        "crawled_at": record["crawled_at"],
        "google_place_id": None,
        "formatted_address": "",
        "geocoded_at": None,
        "snapped_lat": None,
        "snapped_lon": None,
        "nearest_highway_osm_id": None,
        "nearest_road_name": None,
        "snap_distance_m": None,
    }
    return normalized


def normalize_epass(record: dict) -> dict | None:
    raw = record["raw"]

    if is_junk(raw):
        return None

    name = (raw.get("Tên trạm") or raw.get("col_2") or raw.get("Nội dung") or "").strip()
    address = (raw.get("Địa chỉ") or raw.get("col_3") or raw.get("col_4") or "").strip()
    route_text = (raw.get("Quốc lộ/Tỉnh") or raw.get("col_4") or "").strip()

    if not name or not name.lower().startswith("trạm"):
        return None

    province = extract_province(f"{address} {route_text}") or address
    road = extract_road(name, f"{address} {route_text}")
    toll_type = detect_type(name, f"{address} {route_text}")

    normalized = {
        "id": f"vn-toll-{slugify(name)}",
        "name": name,
        "province": province,
        "road": road,
        "km_marker": "",
        "type": toll_type,
        "operator": "ePass/VDTC",
        "status": "active",
        "lat": None,
        "lon": None,
        "source": record["source"],
        "source_url": record["source_url"],
        "confidence": 0.0,
        "crawled_at": record["crawled_at"],
        "google_place_id": None,
        "formatted_address": " ".join(part for part in [address, route_text] if part),
        "geocoded_at": None,
        "snapped_lat": None,
        "snapped_lon": None,
        "nearest_highway_osm_id": None,
        "nearest_road_name": None,
        "snap_distance_m": None,
    }
    normalized["confidence"] = detect_confidence(normalized)
    return normalized


def normalize_manual(record: dict) -> dict | None:
    raw = record["raw"]
    name = (raw.get("name") or raw.get("Tên trạm") or "").strip()
    if not name:
        return None

    normalized = {
        "id": raw.get("id") or f"vn-toll-{slugify(name)}",
        "name": name,
        "province": raw.get("province", ""),
        "road": raw.get("road", ""),
        "km_marker": raw.get("km_marker", ""),
        "type": raw.get("type", "etc"),
        "operator": raw.get("operator", ""),
        "status": raw.get("status", "active"),
        "lat": raw.get("lat"),
        "lon": raw.get("lon"),
        "source": record["source"],
        "source_url": record["source_url"],
        "confidence": 0.0,
        "crawled_at": record["crawled_at"],
        "google_place_id": raw.get("google_place_id"),
        "formatted_address": raw.get("formatted_address", ""),
        "geocoded_at": raw.get("geocoded_at"),
        "snapped_lat": raw.get("snapped_lat"),
        "snapped_lon": raw.get("snapped_lon"),
        "nearest_highway_osm_id": raw.get("nearest_highway_osm_id"),
        "nearest_road_name": raw.get("nearest_road_name"),
        "snap_distance_m": raw.get("snap_distance_m"),
    }
    normalized["confidence"] = detect_confidence(normalized)
    return normalized


def normalize_gmaps(record: dict) -> dict | None:
    name = (record.get("name") or "").strip()
    address = (record.get("address") or "").strip()
    category = (record.get("category") or "").strip()

    if not name:
        return None

    lat = record.get("lat")
    lon = record.get("lon")
    province = record.get("province") or extract_province(address)
    road = record.get("road") or extract_road(name, address)
    operator = record.get("operator") or detect_operator(name, address, category)
    note = gmaps_review_note(name, address, category)

    normalized = {
        "id": f"vn-toll-gmaps-{slugify(record.get('google_place_id') or record.get('google_cid') or name)}",
        "name": name,
        "province": province,
        "road": road,
        "km_marker": "",
        "type": detect_type(name, address),
        "operator": operator,
        "status": "active",
        "lat": lat,
        "lon": lon,
        "source": record["source"],
        "source_url": record.get("source_url", ""),
        "confidence": 0.0,
        "crawled_at": record.get("crawled_at"),
        "google_place_id": record.get("google_place_id"),
        "formatted_address": address,
        "geocoded_at": record.get("crawled_at"),
        "snapped_lat": None,
        "snapped_lon": None,
        "nearest_highway_osm_id": None,
        "nearest_road_name": None,
        "snap_distance_m": None,
        "google_cid": record.get("google_cid"),
        "category": category,
        "rating": record.get("rating"),
        "review_count": record.get("review_count"),
        "review_note": note,
    }
    normalized["confidence"] = detect_confidence(normalized)
    if note:
        normalized["confidence"] = round(max(0.3, normalized["confidence"] - 0.25), 2)
    return normalized


# ── Router theo source ───────────────────────────────────────
NORMALIZERS = {
    "vetc_etc_list": normalize_vetc,
    "osm_overpass":  normalize_osm,
    "epass_public_list": normalize_epass,
    "manual_mentor": normalize_manual,
    "google_maps_scraper": normalize_gmaps,
}


def normalize_file(input_path: Path, output_path: Path):
    if not input_path.exists() or not input_path.read_text(encoding="utf-8").strip():
        print(f"[WARN] Empty or missing raw file: {input_path}")
        return []

    records = json.loads(input_path.read_text(encoding="utf-8"))

    results = []
    skipped = 0

    for record in records:
        source = record.get("source", "")
        normalizer = NORMALIZERS.get(source)

        if not normalizer:
            print(f"[WARN] No normalizer for source: {source}")
            skipped += 1
            continue

        normalized = normalizer(record)
        if normalized:
            results.append(normalized)
        else:
            skipped += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"Normalized {len(results)} records, skipped {skipped} -> {output_path}")
    return results


if __name__ == "__main__":
    for raw_dir in [CRAWLER_RAW_DIR, GMAPS_RAW_DIR]:
        if not raw_dir.exists():
            continue
        for raw_file in raw_dir.glob("*_raw.json"):
            out = NORMALIZED_DIR / raw_file.name.replace("_raw", "_normalized")
            normalize_file(raw_file, out)
