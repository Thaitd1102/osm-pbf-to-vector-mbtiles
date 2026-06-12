from __future__ import annotations

import csv
import json
import re
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
NORMALIZATION_DIR = PIPELINE_ROOT / "data" / "normalization"
CLEAN_DIR = PIPELINE_ROOT / "data" / "clean"
SOURCE_CSV = NORMALIZATION_DIR / "toll_stations_clean_auto.csv"
STATUS_OVERRIDES_CSV = CLEAN_DIR / "status_overrides.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)


def load_status_overrides() -> dict[str, dict[str, str]]:
    if not STATUS_OVERRIDES_CSV.exists():
        return {}

    overrides: dict[str, dict[str, str]] = {}
    for row in read_csv(STATUS_OVERRIDES_CSV):
        data = {
            "status": (row.get("status") or "").strip(),
            "status_note": (row.get("status_note") or "").strip(),
        }
        for key in ("id", "google_place_id"):
            value = (row.get(key) or "").strip()
            if value:
                overrides[value] = data
    return overrides


def apply_status_overrides(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    overrides = load_status_overrides()
    output: list[dict[str, str]] = []
    for row in rows:
        item = dict(row)
        item["status"] = item.get("status") or "active"
        item["status_note"] = item.get("status_note") or ""
        override = overrides.get(item.get("id", "")) or overrides.get(item.get("google_place_id", ""))
        if override:
            item["status"] = override.get("status") or item["status"]
            item["status_note"] = override.get("status_note") or item["status_note"]
        output.append(item)
    return output


def first_nonempty(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def infer_province(row: dict[str, str]) -> str:
    current = first_nonempty(row.get("province"))
    if current:
        return current

    address = first_nonempty(row.get("address"))
    parts = [part.strip() for part in address.split(",") if part.strip()]
    if len(parts) < 2:
        return ""

    if parts[-1].lower() in {"việt nam", "viet nam", "vietnam"}:
        candidate = parts[-2]
    else:
        candidate = parts[-1]
    return re.sub(r"^(tỉnh|tp\.?|thành phố)\s+", "", candidate, flags=re.IGNORECASE).strip()


def infer_road(row: dict[str, str]) -> str:
    current = first_nonempty(row.get("road"))
    if current:
        return current

    text = " ".join([first_nonempty(row.get("name")), first_nonempty(row.get("address"))])
    patterns = [
        r"\bQL\s*\.?\s*\d+[A-Z]?\b",
        r"\bQuốc\s*lộ\s*\d+[A-Z]?\b",
        r"\bCT\s*\.?\s*\d+\b",
        r"\bĐT\s*\.?\s*\d+[A-Z]?\b",
        r"\bDT\s*\.?\s*\d+[A-Z]?\b",
        r"Cao\s*tốc\s+[A-Za-zÀ-ỹ0-9\s\-–]+",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            road = re.sub(r"\s+", " ", match.group(0)).strip(" ,-–")
            return road
    return ""


def infer_operator(row: dict[str, str]) -> str:
    current = first_nonempty(row.get("operator"))
    if current:
        return current

    text = " ".join(
        [
            first_nonempty(row.get("name")),
            first_nonempty(row.get("address")),
            first_nonempty(row.get("source_url")),
        ]
    ).lower()
    if "vetc" in text:
        return "VETC"
    if "epass" in text or "e-pass" in text:
        return "ePass"
    if "vdtc" in text:
        return "VDTC"
    return ""


def enrich_missing_fields(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        item = dict(row)
        item["province"] = infer_province(item)
        item["road"] = infer_road(item)
        item["operator"] = infer_operator(item)
        output.append(item)
    return output


def geojson_feature(row: dict[str, str]) -> dict | None:
    try:
        lat = float(row["lat"])
        lon = float(row["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    properties = {
        "id": row.get("id"),
        "name": row.get("name"),
        "address": row.get("address"),
        "formatted_address": row.get("address"),
        "province": row.get("province"),
        "road": row.get("road"),
        "operator": row.get("operator"),
        "source": row.get("source_datasets"),
        "source_datasets": row.get("source_datasets"),
        "source_url": row.get("source_url"),
        "google_place_id": row.get("google_place_id"),
        "google_cid": row.get("google_cid"),
        "osm_id": row.get("osm_id"),
        "osm_name": row.get("osm_name"),
        "confidence": row.get("confidence"),
        "type": "toll_booth",
        "status": row.get("status") or "active",
        "status_note": row.get("status_note"),
        "tags": row.get("tags"),
        "clean_status": row.get("clean_status"),
        "needs_manual_fields": row.get("needs_manual_fields"),
    }
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": properties,
    }


def main() -> None:
    rows = enrich_missing_fields(apply_status_overrides(read_csv(SOURCE_CSV)))
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = CLEAN_DIR / "toll_stations_clean.csv"
    json_path = CLEAN_DIR / "toll_stations_clean.json"
    geojson_path = CLEAN_DIR / "toll_stations_clean.geojson"
    summary_path = CLEAN_DIR / "summary.md"

    write_csv(csv_path, rows)
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    features = [feature for row in rows if (feature := geojson_feature(row))]
    geojson_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    active_rows = [row for row in rows if row.get("status", "active") == "active"]
    closed_rows = [row for row in rows if row.get("status") == "closed_permanently"]
    province_rows = [row for row in rows if row.get("province")]
    road_rows = [row for row in rows if row.get("road")]
    operator_rows = [row for row in rows if row.get("operator")]
    override_note = (
        "\n- Manual status override: `data/clean/status_overrides.csv`"
        if STATUS_OVERRIDES_CSV.exists()
        else ""
    )

    summary_path.write_text(
        f"""# Clean toll station dataset

## Source

- Input: `data/normalization/toll_stations_clean_auto.csv`
- Rule: B_final làm nền, A_colleague merge/bổ sung, A-only được giữ lại.{override_note}

## Output

- `toll_stations_clean.csv`
- `toll_stations_clean.json`
- `toll_stations_clean.geojson`

## Count

- CSV rows: {len(rows)}
- GeoJSON features: {len(features)}
- Active stations: {len(active_rows)}
- Closed permanently: {len(closed_rows)}
- Province filled: {len(province_rows)}
- Road filled: {len(road_rows)}
- Operator filled: {len(operator_rows)}

## Note

Dataset này là bản clean hiện tại dùng để import DB và hiển thị MapLibre.
Một số trường như `operator`, `road`, `km_marker` vẫn có thể cần bổ sung thủ công nếu nguồn crawl không cung cấp đủ.
""",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "clean_csv": str(csv_path.relative_to(PIPELINE_ROOT)),
                "clean_json": str(json_path.relative_to(PIPELINE_ROOT)),
                "clean_geojson": str(geojson_path.relative_to(PIPELINE_ROOT)),
                "rows": len(rows),
                "features": len(features),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
