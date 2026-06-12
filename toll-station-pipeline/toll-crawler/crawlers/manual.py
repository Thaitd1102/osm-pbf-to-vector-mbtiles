import json
from pathlib import Path
from .base import BaseCrawler

class ManualCrawler(BaseCrawler):
    source = "manual_mentor"
    source_url = "local_file"

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.source_url = str(self.file_path)

    def crawl(self) -> list[dict]:
        if not self.file_path.exists():
            return []
        return json.loads(self.file_path.read_text(encoding="utf-8"))
