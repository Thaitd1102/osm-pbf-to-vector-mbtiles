import argparse
import csv
import json
import re
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "output" / "gmaps_results.csv"
DEFAULT_OUTPUT = ROOT / "data" / "raw" / "gmaps_raw.json"


def clean(value: str | None) -> str:
    return (value or "").strip()


def parse_float(value: str | None) -> float | None:
    value = clean(value)
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def slug(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9à-ỹ]+", "-", value, flags=re.IGNORECASE)
    return re.sub(r"-+", "-", value).strip("-")


def first(row: dict, *names: str) -> str:
    for name in names:
        value = clean(row.get(name))
        if value:
            return value
    return ""


def looks_like_toll(row: dict) -> bool:
    text = " ".join(clean(value).lower() for value in row.values())
    keywords = ["trạm thu phí", "tram thu phi", "toll", "vetc", "epass", "bot"]
    return any(keyword in text for keyword in keywords)


def normalize_row(row: dict, index: int, crawled_at: str) -> dict:
    name = first(row, "title", "name", "Name", "Title")
    address = first(row, "address", "complete_address", "Address")
    lat = parse_float(first(row, "latitude", "lat", "Latitude"))
    lon = parse_float(first(row, "longitude", "lng", "lon", "Longitude"))
    place_id = first(row, "place_id", "placeId", "Place ID")
    cid = first(row, "cid", "CID")
    station_id = f"gmaps-{slug(place_id or cid or name or str(index))}"

    return {
        "id": station_id,
        "source": "google_maps_scraper",
        "source_url": first(row, "link", "url", "google_maps_url", "reviews_link"),
        "crawled_at": crawled_at,
        "name": name,
        "address": address,
        "province": "",
        "road": "",
        "type": "unknown",
        "operator": "",
        "lat": lat,
        "lon": lon,
        "google_place_id": place_id or None,
        "google_cid": cid or None,
        "category": first(row, "category", "categories"),
        "rating": parse_float(first(row, "review_rating", "rating", "Rating")),
        "review_count": first(row, "review_count", "reviews", "Review Count"),
        "raw": row,
    }


def import_csv(input_path: Path, output_path: Path, include_all: bool) -> None:
    crawled_at = datetime.now(UTC).isoformat()
    records = []
    seen = set()

    with input_path.open("r", encoding="utf-8-sig", newline="") as file:
        for index, row in enumerate(csv.DictReader(file), start=1):
            if not include_all and not looks_like_toll(row):
                continue
            record = normalize_row(row, index, crawled_at)
            dedupe_key = (
                record.get("google_place_id")
                or record.get("google_cid")
                or f"{record.get('name')}|{record.get('lat')}|{record.get('lon')}"
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            records.append(record)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Imported {len(records)} records -> {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--include-all", action="store_true")
    args = parser.parse_args()

    import_csv(args.input, args.output, args.include_all)


if __name__ == "__main__":
    main()
