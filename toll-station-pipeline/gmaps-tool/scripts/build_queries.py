import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVINCES_PATH = ROOT / "config" / "provinces.csv"
TEMPLATES_PATH = ROOT / "config" / "query_templates.txt"
OUTPUT_PATH = ROOT / "queries" / "provinces_etc.txt"


def read_provinces() -> list[str]:
    with PROVINCES_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        return [row["province"].strip() for row in csv.DictReader(file) if row.get("province")]


def read_templates() -> list[str]:
    return [
        line.strip()
        for line in TEMPLATES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def main() -> None:
    provinces = read_provinces()
    templates = read_templates()
    queries = []

    for province in provinces:
        for template in templates:
            queries.append(template.format(province=province))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(queries) + "\n", encoding="utf-8")
    print(f"Wrote {len(queries)} queries -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
