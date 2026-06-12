from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PIPELINE_ROOT.parent
CLEAN_DIR = PIPELINE_ROOT / "data" / "clean"
CLEAN_CSV = CLEAN_DIR / "toll_stations_clean.csv"
PIPELINE_OSM = CLEAN_DIR / "toll_stations_clean.osm"
PROJECT_OSM = PROJECT_ROOT / "data" / "toll" / "toll_stations_clean.osm"
OSM_SYNTHETIC_NODE_ID_START = 14_000_000_000


def clean(value: object) -> str:
    return str(value or "").strip()


def parse_tags(raw_tags: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    for item in clean(raw_tags).split(";"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            tags[key] = value
    return tags


def add_tag(node: ET.Element, key: str, value: object) -> None:
    text = clean(value)
    if text:
        ET.SubElement(node, "tag", {"k": key, "v": text})


def osm_node(row: dict[str, str], node_id: int) -> ET.Element | None:
    lat = clean(row.get("lat"))
    lon = clean(row.get("lon"))
    if not lat or not lon:
        return None

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    node = ET.Element(
        "node",
        {
            "id": str(node_id),
            "lat": lat,
            "lon": lon,
            "version": "1",
            "timestamp": timestamp,
        },
    )

    tags = parse_tags(row.get("tags", ""))
    tags.update(
        {
            "barrier": "toll_booth",
            "highway": "toll_gantry",
            "toll": "yes",
            "payment:etc": "yes",
            "payment": "etc",
        }
    )

    for key in sorted(tags):
        add_tag(node, key, tags[key])

    add_tag(node, "name", row.get("name"))
    add_tag(node, "addr:full", row.get("address"))
    add_tag(node, "addr:province", row.get("province"))
    add_tag(node, "road", row.get("road"))
    add_tag(node, "operator", row.get("operator"))
    add_tag(node, "source", "maps-vietnam toll-station-pipeline")
    add_tag(node, "source:datasets", row.get("source_datasets"))
    add_tag(node, "source:google_place_id", row.get("google_place_id"))
    add_tag(node, "source:google_cid", row.get("google_cid"))
    add_tag(node, "source:url", row.get("source_url"))
    add_tag(node, "ref:osm_match", row.get("osm_id"))
    add_tag(node, "note:osm_match_name", row.get("osm_name"))
    add_tag(node, "maps_vietnam:id", row.get("id"))
    add_tag(node, "maps_vietnam:clean_status", row.get("clean_status"))
    add_tag(node, "maps_vietnam:confidence", row.get("confidence"))
    add_tag(node, "maps_vietnam:status", row.get("status") or "active")
    add_tag(node, "maps_vietnam:status_note", row.get("status_note"))
    return node


def read_rows() -> list[dict[str, str]]:
    with CLEAN_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_osm(path: Path, rows: list[dict[str, str]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)

    root = ET.Element(
        "osm",
        {
            "version": "0.6",
            "generator": "maps-vietnam toll-station-pipeline",
        },
    )
    count = 0
    for index, row in enumerate(rows):
        node = osm_node(row, OSM_SYNTHETIC_NODE_ID_START + index)
        if node is None:
            continue
        root.append(node)
        count += 1

    ET.indent(root, space="  ")
    tree = ET.ElementTree(root)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return count


def main() -> None:
    rows = read_rows()
    count = write_osm(PIPELINE_OSM, rows)
    write_osm(PROJECT_OSM, rows)

    print(
        json.dumps(
            {
                "source_csv": str(CLEAN_CSV.relative_to(PIPELINE_ROOT)),
                "pipeline_osm": str(PIPELINE_OSM.relative_to(PIPELINE_ROOT)),
                "project_osm": str(PROJECT_OSM.relative_to(PROJECT_ROOT)),
                "nodes": count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
