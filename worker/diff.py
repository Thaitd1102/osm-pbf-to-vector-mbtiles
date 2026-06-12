from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


COLORS = {
    "create": "#22c55e",
    "modify": "#f97316",
    "delete": "#ef4444",
}


def build_node_index(*pbf_paths: Path) -> dict[int, tuple[float, float]]:
    # TODO(flow): Build id -> lat/lon để vẽ node/way trong changes.osc lên bản đồ.
    import osmium

    class NodeIndex(osmium.SimpleHandler):
        def __init__(self) -> None:
            super().__init__()
            self.coords: dict[int, tuple[float, float]] = {}

        def node(self, node: Any) -> None:
            if node.location.valid():
                self.coords[node.id] = (float(node.location.lat), float(node.location.lon))

    index = NodeIndex()
    for path in pbf_paths:
        index.apply_file(str(path), locations=False)
    return index.coords


def tags_from(element: ET.Element) -> dict[str, str]:
    return {
        tag.get("k", ""): tag.get("v", "")
        for tag in element.findall("tag")
        if tag.get("k")
    }


def osc_to_geojson(osc_path: Path, src_pbf: Path, target_pbf: Path, output_path: Path) -> Path:
    # TODO(flow): Convert changes.osc thành GeoJSON cho frontend showDiffLayer().
    node_coords = build_node_index(src_pbf, target_pbf)
    root = ET.parse(osc_path).getroot()
    features: list[dict[str, Any]] = []

    for action in root:
        action_type = action.tag
        color = COLORS.get(action_type, "#888888")

        for element in action:
            common = {
                "action": action_type,
                "id": element.get("id"),
                "color": color,
                "tags": tags_from(element),
            }

            if element.tag == "node":
                lat = element.get("lat")
                lon = element.get("lon")
                if lat is None or lon is None:
                    node_id = int(element.get("id", "0"))
                    lat_lon = node_coords.get(node_id)
                    if not lat_lon:
                        continue
                    lat_value, lon_value = lat_lon
                else:
                    lat_value = float(lat)
                    lon_value = float(lon)

                features.append(
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [lon_value, lat_value]},
                        "properties": {**common, "osm_type": "node"},
                    }
                )

            elif element.tag == "way":
                coords = []
                for nd in element.findall("nd"):
                    ref = int(nd.get("ref", "0"))
                    lat_lon = node_coords.get(ref)
                    if lat_lon:
                        lat_value, lon_value = lat_lon
                        coords.append([lon_value, lat_value])

                if len(coords) < 2:
                    continue

                geometry_type = "Polygon" if len(coords) >= 4 and coords[0] == coords[-1] else "LineString"
                geometry_coords = [coords] if geometry_type == "Polygon" else coords
                features.append(
                    {
                        "type": "Feature",
                        "geometry": {"type": geometry_type, "coordinates": geometry_coords},
                        "properties": {**common, "osm_type": "way"},
                    }
                )

    geojson = {"type": "FeatureCollection", "features": features}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(geojson), encoding="utf-8")
    return output_path
