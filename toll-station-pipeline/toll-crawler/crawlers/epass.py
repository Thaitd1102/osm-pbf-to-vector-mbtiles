from bs4 import BeautifulSoup
from .base import BaseCrawler


class EPassCrawler(BaseCrawler):
    source = "epass_public_list"
    source_url = "https://vinfastauto.com/vn_vi/tram-thu-phi-khong-dung-epass"

    def crawl(self) -> list[dict]:
        res = self.get(self.source_url, timeout=20)
        soup = BeautifulSoup(res.text, "html.parser")
        records = []
        seen = set()

        for table in soup.select("table"):
            headers = [cell.get_text(" ", strip=True) for cell in table.select("thead th")]
            for row in table.select("tbody tr"):
                cells = [cell.get_text(" ", strip=True) for cell in row.select("td")]
                if not cells:
                    continue
                if headers and len(headers) == len(cells):
                    record = dict(zip(headers, cells))
                else:
                    record = {f"col_{index + 1}": value for index, value in enumerate(cells)}
                key = "|".join(cells)
                if key in seen:
                    continue
                seen.add(key)
                records.append(record)

        if records:
            return records

        for item in soup.select("li, p"):
            text = item.get_text(" ", strip=True)
            if "trạm" not in text.lower() or "phí" not in text.lower():
                continue
            if text in seen:
                continue
            seen.add(text)
            records.append({"Nội dung": text})

        return records
