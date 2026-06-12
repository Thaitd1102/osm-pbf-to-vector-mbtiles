from __future__ import annotations

import os
import subprocess
from pathlib import Path


DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
BASE_VERSION = os.getenv("BASE_VERSION", "vietnam-260101.osm.pbf")
BASE_MBTILES = Path(os.getenv("BASE_MBTILES", "/data/base/vietnam-260101-navigation.mbtiles"))


def main() -> None:
    # TODO(flow): Chạy script này một lần để convert PBF nội bộ thành MBTiles cho UI.
    source_pbf = DATA_DIR / "versions" / BASE_VERSION
    if not source_pbf.exists():
        raise SystemExit(f"Missing source PBF: {source_pbf}")

    BASE_MBTILES.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "tilemaker",
        "--input",
        str(source_pbf),
        "--output",
        str(BASE_MBTILES),
        "--config",
        "/app/tilemaker-config.json",
        "--process",
        "/app/tilemaker-process.lua",
    ]
    subprocess.run(command, check=True)
    print(f"Base map written: {BASE_MBTILES}")


if __name__ == "__main__":
    main()
