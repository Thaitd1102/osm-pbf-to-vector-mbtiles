from pathlib import Path
import json
from crawlers.vetc import VETCCrawler
from crawlers.epass import EPassCrawler
from crawlers.osm import OSMCrawler
from crawlers.manual import ManualCrawler

RAW_DIR = Path("data/raw")
MANUAL_INPUT = Path("../data/raw/toll_stations.json")
ERRORS_PATH = RAW_DIR / "crawl_errors.json"

crawlers = [
    (VETCCrawler(),                    RAW_DIR / "vetc_raw.json"),
    (EPassCrawler(),                   RAW_DIR / "epass_raw.json"),
    (OSMCrawler(),                     RAW_DIR / "osm_raw.json"),
    (ManualCrawler(MANUAL_INPUT),      RAW_DIR / "manual_raw.json"),
]

errors = []
for crawler, output in crawlers:
    try:
        crawler.save(output)
    except Exception as e:
        print(f"[ERROR] {crawler.source}: {e}")
        errors.append({
            "source": crawler.source,
            "source_url": getattr(crawler, "source_url", ""),
            "error": str(e),
        })

if errors:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ERRORS_PATH.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDone with {len(errors)} error(s). See {ERRORS_PATH}")
else:
    print("\nDone. Raw data saved to data/raw/")
