from bs4 import BeautifulSoup
from .base import BaseCrawler

class VETCCrawler(BaseCrawler):
    source = "vetc_etc_list"
    source_url = "https://vetc.com.vn/tram-thu-phi.html"

    def crawl(self) -> list[dict]:
        res = self.get(self.source_url, timeout=20)
        soup = BeautifulSoup(res.text, "html.parser")

        records = []
        seen = set()
        for block in soup.select("h3"):
            name = block.get_text(strip=True)
            if "TRẠM" not in name.upper():
                continue
            if name in seen:
                continue
            seen.add(name)
            address = ""
            next_p = block.find_next_sibling()
            if next_p:
                address = next_p.get_text(strip=True)

            records.append({
                "Tên trạm": name.title(),
                "Địa chỉ": address,
            })
        return records
