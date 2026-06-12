import json
import math
import re
import unicodedata
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_DIR = PIPELINE_ROOT / "data" / "normalized"
MATCHED_DIR = PIPELINE_ROOT / "data" / "matched"
REJECTED_DIR = PIPELINE_ROOT / "data" / "rejected"

# ── Ngưỡng khoảng cách ──────────────────────────────────────
THRESHOLD_MATCHED  = 200   # m — coi là matched
THRESHOLD_POSSIBLE = 500   # m — cần review
GEOCODE_NAME_THRESHOLD = 0.55
GEOCODE_REVIEW_THRESHOLD = 0.50

# ── Haversine distance (m) ───────────────────────────────────
def haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6_371_000
    p = math.pi / 180
    a = (math.sin((lat2-lat1)*p/2)**2 +
         math.cos(lat1*p) * math.cos(lat2*p) *
         math.sin((lon2-lon1)*p/2)**2)
    return 2 * R * math.asin(math.sqrt(a))

# ── Text similarity cho tên trạm ────────────────────────────
def normalize_text(text: str) -> str:
    """Lowercase, bỏ dấu, bỏ ký tự đặc biệt."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9\s]", "", text).strip()

def name_similarity(a: str, b: str) -> float:
    """Token overlap score 0.0 → 1.0."""
    if not a or not b:
        return 0.0
    tokens_a = set(normalize_text(a).split())
    tokens_b = set(normalize_text(b).split())
    # Bỏ stopwords không có giá trị
    stopwords = {"tram", "thu", "phi", "bot", "cao", "toc", "quoc", "lo"}
    tokens_a -= stopwords
    tokens_b -= stopwords
    if not tokens_a or not tokens_b:
        return 0.0
    overlap = tokens_a & tokens_b
    return len(overlap) / max(len(tokens_a), len(tokens_b))

def core_tokens(text: str) -> set[str]:
    stopwords = {
        "tram", "thu", "phi", "bot", "cao", "toc", "quoc", "lo", "ql",
        "so", "km", "duong", "di", "ve", "vao", "ra",
    }
    return set(normalize_text(text).split()) - stopwords

def load_json(path: Path) -> list[dict]:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def is_gmaps_quality_rejected(station: dict) -> tuple[bool, str]:
    if station.get("source") != "google_maps_scraper":
        return False, ""

    category = normalize_text(station.get("category", ""))
    review_note = (station.get("review_note") or "").lower()
    name = normalize_text(station.get("name", ""))

    if category != normalize_text("Trạm thu phí"):
        return True, f"Google Maps category is not toll station: {station.get('category') or 'empty'}"
    if "tag/service point" in review_note:
        return True, "Google Maps result looks like ETC tag/service point"
    if "office/company" in review_note:
        return True, "Google Maps result looks like company/office"
    if "tram thu phi" not in name and "bot" not in name:
        return True, "name does not look like a toll station"

    return False, ""


def nearby_osm_candidates(osm_records: list[dict], lat: float, lon: float, radius_m: int = 1000) -> list[dict]:
    candidates = []
    for osm in osm_records:
        osm_lat = osm.get("lat")
        osm_lon = osm.get("lon")
        if osm_lat is None or osm_lon is None:
            continue
        try:
            distance = haversine(float(lat), float(lon), float(osm_lat), float(osm_lon))
        except (TypeError, ValueError):
            continue
        if distance <= radius_m:
            candidate = {**osm, "distance_m": distance, "osm_id": osm.get("id")}
            candidates.append(candidate)
    return sorted(candidates, key=lambda item: item["distance_m"])[:10]


def find_coordinate_from_osm(station: dict, osm_records: list[dict]) -> tuple[dict | None, float]:
    best = None
    best_score = 0.0
    best_overlap_count = 0
    station_name = station.get("name", "")
    station_text = " ".join(str(station.get(key, "")) for key in ["name", "formatted_address", "province", "road"])
    station_tokens = core_tokens(station_text)
    station_province = normalize_text(station.get("province", ""))
    station_road = normalize_text(station.get("road", ""))

    for osm in osm_records:
        if osm.get("lat") is None or osm.get("lon") is None:
            continue
        osm_name = osm.get("name", "")
        if not osm_name:
            continue
        osm_text = normalize_text(" ".join(str(osm.get(key, "")) for key in ["name", "province", "road", "operator"]))
        osm_tokens = core_tokens(osm_text)
        score = name_similarity(station_name, osm_name)
        token_overlap = station_tokens & osm_tokens
        if len(token_overlap) >= 2:
            score += 0.10
        if station_province and station_province in osm_text:
            score += 0.12
        if station_road and station_road in osm_text:
            score += 0.12
        if station.get("operator") and station.get("operator") == osm.get("operator"):
            score += 0.06
        if score > best_score:
            best = osm
            best_score = score
            best_overlap_count = len(token_overlap)

    strong_match = best_score >= GEOCODE_NAME_THRESHOLD
    review_match = best_score >= GEOCODE_REVIEW_THRESHOLD and best_overlap_count >= 2
    if best and (strong_match or review_match):
        return best, round(min(best_score, 1.0), 3)
    return None, round(best_score, 3)


def enrich_coordinates(station: dict, osm_records: list[dict]) -> dict:
    if station.get("lat") is not None and station.get("lon") is not None:
        return station

    osm_match, score = find_coordinate_from_osm(station, osm_records)
    if not osm_match:
        return {
            **station,
            "coordinate_source": "missing",
            "coordinate_confidence": score,
            "coordinate_note": "no reliable OSM name match; needs manual lat/lon",
        }

    source = "osm_name_match" if score >= GEOCODE_NAME_THRESHOLD else "osm_name_match_review"
    note = "copied from" if score >= GEOCODE_NAME_THRESHOLD else "review copied from"
    return {
        **station,
        "lat": osm_match.get("lat"),
        "lon": osm_match.get("lon"),
        "coordinate_source": source,
        "coordinate_confidence": score,
        "coordinate_note": f"{note} {osm_match.get('id')}",
        "nearest_highway_osm_id": osm_match.get("id"),
        "nearest_road_name": osm_match.get("name"),
    }

# ── Logic đối soát ───────────────────────────────────────────
def check_tag_match(osm: dict, our: dict) -> list[str]:
    """Trả về list tag issues nếu có."""
    issues = []
    our_type = our.get("type")

    if our_type == "etc":
        if osm.get("type") != "etc":
            issues.append("expected highway=toll_gantry")
    elif our_type == "toll_booth":
        if osm.get("type") != "toll_booth":
            issues.append("expected barrier=toll_booth")

    return issues

def match_station(our: dict, osm_candidates: list) -> dict:
    """
    So sánh 1 trạm của ta với danh sách OSM candidates.
    Trả về match result.
    """
    # Không có tọa độ → không thể đối soát
    if not our.get("lat") or not our.get("lon"):
        return {
            "status": "missing_in_osm",
            "reason": "no coordinates — cannot match",
            "osm_match": None,
        }

    # Không có candidate nào trong vòng 1km
    if not osm_candidates:
        return {
            "status": "missing_in_osm",
            "reason": "no OSM object within 1km",
            "osm_match": None,
        }

    best = osm_candidates[0]  # gần nhất
    dist = best["distance_m"]
    name_score = name_similarity(our.get("name", ""), best.get("name", "") or "")
    tag_issues = check_tag_match(best, our)

    # ── Quyết định status ────────────────────────────────────
    if dist > THRESHOLD_POSSIBLE:
        return {
            "status": "missing_in_osm",
            "reason": f"nearest OSM object {dist:.0f}m away (> {THRESHOLD_POSSIBLE}m)",
            "osm_match": None,
        }

    if dist > THRESHOLD_MATCHED:
        return {
            "status": "location_mismatch",
            "reason": f"distance {dist:.0f}m (> {THRESHOLD_MATCHED}m threshold)",
            "osm_match": best,
        }

    # Trong 200m — kiểm tra thêm name + tag
    if name_score < 0.3 and best.get("name"):
        return {
            "status": "name_mismatch",
            "reason": f"name similarity {name_score:.2f} (our: '{our['name']}' vs osm: '{best['name']}')",
            "osm_match": best,
        }

    if tag_issues:
        return {
            "status": "tag_mismatch",
            "reason": ", ".join(tag_issues),
            "osm_match": best,
        }

    return {
        "status": "matched",
        "reason": f"distance {dist:.0f}m, name_score {name_score:.2f}",
        "osm_match": best,
    }

def empty_stats(total: int = 0) -> dict:
    return {
        "total": total,
        "matched": 0,
        "missing_in_osm": 0,
        "location_mismatch": 0,
        "tag_mismatch": 0,
        "name_mismatch": 0,
        "duplicate_candidate": 0,
        "no_coordinates": 0,
        "rejected_by_quality": 0,
    }


# ── Main ─────────────────────────────────────────────────────
def run_matching(osm_records: list[dict], normalized_path: Path, output_path: Path):
    stations = json.loads(normalized_path.read_text(encoding="utf-8"))
    rejected = []
    accepted = []
    for station in stations:
        is_rejected, reason = is_gmaps_quality_rejected(station)
        if is_rejected:
            rejected.append({
                **station,
                "reject_reason": reason,
                "match": {
                    "status": "rejected_by_quality",
                    "reason": reason,
                    "osm_match": None,
                },
            })
        else:
            accepted.append(station)

    results = []
    stats = empty_stats(len(stations))
    stats["rejected_by_quality"] = len(rejected)

    for s in accepted:
        s = enrich_coordinates(s, osm_records)
        lat, lon = s.get("lat"), s.get("lon")

        if not lat or not lon:
            match_result = {
                "status": "missing_in_osm",
                "reason": "no coordinates",
                "osm_match": None,
            }
            stats["no_coordinates"] += 1
            stats["missing_in_osm"] += 1
        else:
            candidates = nearby_osm_candidates(osm_records, float(lat), float(lon))
            match_result = match_station(s, candidates)
            stats[match_result["status"]] = stats.get(match_result["status"], 0) + 1

        # Check duplicate — nếu 2 trạm của ta cùng match 1 osm_id
        results.append({**s, "match": match_result})

    # Detect duplicates
    osm_id_seen = {}
    for r in results:
        osm_id = (r["match"].get("osm_match") or {}).get("osm_id")
        if osm_id:
            if osm_id in osm_id_seen:
                # Cả 2 đều mark là duplicate_candidate
                previous_status = r["match"].get("status")
                if previous_status in stats and stats[previous_status] > 0:
                    stats[previous_status] -= 1
                r["match"]["status"] = "duplicate_candidate"
                first = osm_id_seen[osm_id]
                first_status = first["match"].get("status")
                if first_status in stats and stats[first_status] > 0:
                    stats[first_status] -= 1
                first["match"]["status"] = "duplicate_candidate"
                stats["duplicate_candidate"] += 1
            else:
                osm_id_seen[osm_id] = r

    # Ghi output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    if rejected:
        REJECTED_DIR.mkdir(parents=True, exist_ok=True)
        rejected_path = REJECTED_DIR / output_path.name.replace("_matched", "_rejected")
        rejected_path.write_text(
            json.dumps(rejected, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # Summary
    summary = {
        "run_at": __import__("datetime").datetime.utcnow().isoformat(),
        "thresholds": {
            "matched_m": THRESHOLD_MATCHED,
            "possible_m": THRESHOLD_POSSIBLE,
        },
        **stats
    }
    summary_path = output_path.parent / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)
    )

    print(f"\nMatching complete:")
    for k, v in stats.items():
        print(f"  {k:25s}: {v}")

    return results, summary


def run_all():
    osm_path = NORMALIZED_DIR / "osm_normalized.json"
    osm_records = load_json(osm_path)
    MATCHED_DIR.mkdir(parents=True, exist_ok=True)

    summary = {
        "run_at": __import__("datetime").datetime.utcnow().isoformat(),
        "thresholds": {
            "matched_m": THRESHOLD_MATCHED,
            "possible_m": THRESHOLD_POSSIBLE,
        },
        "sources": {},
        "total": 0,
        "matched": 0,
        "missing_in_osm": 0,
        "location_mismatch": 0,
        "tag_mismatch": 0,
        "name_mismatch": 0,
        "duplicate_candidate": 0,
        "no_coordinates": 0,
        "rejected_by_quality": 0,
    }

    missing_coordinates = []
    for normalized_path in sorted(NORMALIZED_DIR.glob("*_normalized.json")):
        if normalized_path.name == "osm_normalized.json":
            continue
        output_path = MATCHED_DIR / normalized_path.name.replace("_normalized", "_matched")
        results, source_summary = run_matching(osm_records, normalized_path, output_path)
        missing_coordinates.extend([
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "source": item.get("source"),
                "province": item.get("province"),
                "road": item.get("road"),
                "coordinate_confidence": item.get("coordinate_confidence"),
                "coordinate_note": item.get("coordinate_note"),
            }
            for item in results
            if item.get("lat") is None or item.get("lon") is None
        ])
        source_name = normalized_path.stem.replace("_normalized", "")
        summary["sources"][source_name] = source_summary
        for key in ["total", "matched", "missing_in_osm", "location_mismatch", "tag_mismatch", "name_mismatch", "duplicate_candidate", "no_coordinates", "rejected_by_quality"]:
            summary[key] += source_summary.get(key, 0)

    (MATCHED_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (MATCHED_DIR / "missing_coordinates.json").write_text(
        json.dumps(missing_coordinates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nWrote matched outputs to {MATCHED_DIR}")


if __name__ == "__main__":
    run_all()
