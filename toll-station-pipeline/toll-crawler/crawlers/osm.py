import requests
from .base import BaseCrawler

class OSMCrawler(BaseCrawler):
    source = "osm_overpass"
    source_url = "https://overpass-api.de/api/interpreter"
    endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.openstreetmap.ru/api/interpreter",
    ]

    QUERY = """
    [out:json][timeout:60];
    (
      node["highway"="toll_gantry"](7.73,102.04,23.48,111.67);
      way["highway"="toll_gantry"](7.73,102.04,23.48,111.67);
      node["barrier"="toll_booth"](7.73,102.04,23.48,111.67);
      way["barrier"="toll_booth"](7.73,102.04,23.48,111.67);
      node["toll"="yes"](7.73,102.04,23.48,111.67);
      way["toll"="yes"](7.73,102.04,23.48,111.67);
    );
    out center tags;
    """

    def crawl(self) -> list[dict]:
        last_error = None
        for endpoint in self.endpoints:
            try:
                res = requests.post(endpoint, data={"data": self.QUERY}, timeout=90)
                res.raise_for_status()
                self.source_url = endpoint
                break
            except Exception as exc:
                last_error = exc
        else:
            raise RuntimeError(f"All Overpass endpoints failed: {last_error}")

        if "json" not in res.headers.get("Content-Type", "") and not res.text.lstrip().startswith("{"):
            raise RuntimeError(f"Overpass returned non-JSON response: {res.text[:200]}")
        elements = res.json().get("elements", [])
        records = []
        for el in elements:
            tags = el.get("tags", {})
            center = el.get("center", {})
            records.append({
                "osm_id": el.get("id"),
                "osm_type": el.get("type"),
                "lat": el.get("lat") or center.get("lat"),
                "lon": el.get("lon") or center.get("lon"),
                "Tên trạm": tags.get("name", ""),
                "highway": tags.get("highway", ""),
                "barrier": tags.get("barrier", ""),
                "operator": tags.get("operator", ""),
                "toll": tags.get("toll", ""),
                "tags": tags,
            })
        return records
