import json
from datetime import datetime, timezone
from pathlib import Path
import requests


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
}

class BaseCrawler:
    source: str       # "vetc", "epass", "osm", "manual"
    source_url: str

    def crawl(self) -> list[dict]:
        """Override ở subclass — trả về list raw records."""
        raise NotImplementedError

    def get(self, url: str, timeout: int = 20) -> requests.Response:
        res = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        res.raise_for_status()
        return res

    def post(self, url: str, data: dict, timeout: int = 60) -> requests.Response:
        res = requests.post(url, data=data, headers=DEFAULT_HEADERS, timeout=timeout)
        res.raise_for_status()
        return res

    def wrap(self, raw: dict) -> dict:
        """Wrap raw data vào schema chuẩn bước 1."""
        return {
            "source": self.source,
            "source_url": self.source_url,
            "raw": raw,
            "crawled_at": datetime.now(timezone.utc).isoformat()
        }

    def save(self, output_path: Path):
        records = self.crawl()
        wrapped = [self.wrap(r) for r in records]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(wrapped, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"[{self.source}] Saved {len(wrapped)} records -> {output_path}")
        return wrapped
