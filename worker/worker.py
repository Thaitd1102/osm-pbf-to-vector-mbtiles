from __future__ import annotations

import json
import os
import shutil
import subprocess
from hashlib import sha256
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import redis
from celery import Celery

from database import upsert_job
from diff import osc_to_geojson
from render import render_png_map


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
STATUS_TTL_SECONDS = int(os.getenv("STATUS_TTL_SECONDS", "86400"))

celery_app = Celery("maps_vietnam", broker=REDIS_URL, backend=REDIS_URL)
store = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def update_job(job_id: str, **fields: Any) -> None:
    # TODO(flow): Ghi progress vào Redis để API /jobs/{id} cho frontend poll.
    key = f"job:{job_id}"
    current = json.loads(store.get(key) or "{}")
    current.update(fields)
    current["updated_at"] = now_iso()
    if "created_at" not in current:
        current["created_at"] = current["updated_at"]
    store.setex(key, STATUS_TTL_SECONDS, json.dumps(current))
    try:
        upsert_job(current)
    except Exception:
        pass


def run(command: list[str], cwd: Path | None = None) -> None:
    # TODO(flow): Wrapper cho các lệnh CLI nặng như osmium/tilemaker.
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "command failed"
        raise RuntimeError(f"{' '.join(command)}\n{detail}")


def bbox_arg(request: dict[str, Any]) -> str:
    bbox = request["bbox"]
    return f"{bbox['min_lon']},{bbox['min_lat']},{bbox['max_lon']},{bbox['max_lat']}"


def cache_key(version_name: str, request: dict[str, Any]) -> str:
    # TODO(flow): Hash này quyết định cache bbox extract có hit hay phải đọc PBF lớn.
    payload = {
        "version": version_name,
        "bbox": request["bbox"],
        "extract_strategy": "smart",
    }
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(normalized.encode("utf-8")).hexdigest()


def extract_with_cache(source: Path, destination: Path, request: dict[str, Any]) -> bool:
    # TODO(flow): Nếu cache miss thì osmium extract --strategy smart tạo bbox .osm.pbf.
    if destination.exists() and destination.stat().st_size > 0:
        return True
    base_name = destination.name.removesuffix(".osm.pbf")
    partial = destination.with_name(f"{base_name}.partial.osm.pbf")
    if partial.exists():
        partial.unlink()
    run(
        [
            "osmium",
            "extract",
            "--strategy",
            "smart",
            "-b",
            bbox_arg(request),
            "-o",
            str(partial),
            "--overwrite",
            str(source),
        ]
    )
    partial.replace(destination)
    return False


@celery_app.task(name="worker.run_pipeline")
def run_pipeline(job_id: str, request: dict[str, Any]) -> dict[str, Any]:
    # TODO(flow): Pipeline chính: cache extract -> derive changes -> apply -> diff GeoJSON -> optional render.
    tmp_dir = DATA_DIR / "tmp" / job_id
    output_dir = DATA_DIR / "output" / job_id
    cache_dir = DATA_DIR / "cache"
    versions_dir = DATA_DIR / "versions"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    src = versions_dir / request["version_src"]
    target = versions_dir / request["version_target"]
    src_key = cache_key(request["version_src"], request)
    target_key = cache_key(request["version_target"], request)
    src_extract = cache_dir / f"{src_key}.osm.pbf"
    target_extract = cache_dir / f"{target_key}.osm.pbf"
    changes = tmp_dir / "changes.osc"
    patched = output_dir / "patched.osm.pbf"
    diff_geojson = output_dir / "diff.geojson"
    mbtiles = output_dir / "patched.mbtiles"
    png_dir = output_dir / "png"

    try:
        update_job(job_id, state="running", progress=8, message="Cache check for source bbox")
        src_hit = extract_with_cache(src, src_extract, request)

        update_job(
            job_id,
            progress=25,
            message="Cache check for target bbox",
            cache={"bbox_src": "hit" if src_hit else "miss", "bbox_target": "checking"},
        )
        target_hit = extract_with_cache(target, target_extract, request)
        update_job(
            job_id,
            progress=38,
            message="BBox extracts ready",
            cache={"bbox_src": "hit" if src_hit else "miss", "bbox_target": "hit" if target_hit else "miss"},
        )

        update_job(job_id, progress=48, message="Derive OSM changes")
        run(["osmium", "derive-changes", "-o", str(changes), "--overwrite", str(src_extract), str(target_extract)])

        update_job(job_id, progress=68, message="Apply changes to source extract")
        run(["osmium", "apply-changes", "-o", str(patched), "--overwrite", str(src_extract), str(changes)])

        update_job(job_id, progress=76, message="Build GeoJSON diff layer")
        osc_to_geojson(changes, src_extract, target_extract, diff_geojson)
        if changes.exists():
            changes.unlink()

        patched_pbf_url = f"/output/{job_id}/patched.osm.pbf"
        diff_geojson_url = f"/output/{job_id}/diff.geojson"
        result: dict[str, Any] = {
            "output_url": patched_pbf_url,
            "patched_pbf_url": patched_pbf_url,
            "diff_geojson_url": diff_geojson_url,
        }

        export_png = bool(request.get("export_png", False))
        render_mbtiles = bool(request.get("render_mbtiles", request.get("render", False))) or export_png

        if render_mbtiles:
            update_job(
                job_id,
                progress=84,
                message="Render MBTiles with tilemaker",
                patched_pbf_url=patched_pbf_url,
                diff_geojson_url=diff_geojson_url,
            )
            run(
                [
                    "tilemaker",
                    "--input",
                    str(patched),
                    "--output",
                    str(mbtiles),
                    "--config",
                    "/app/tilemaker-config.json",
                    "--process",
                    "/app/tilemaker-process.lua",
                ]
            )

            result["mbtiles_url"] = f"/output/{job_id}/patched.mbtiles"
            update_job(
                job_id,
                progress=90 if export_png else 94,
                message="MBTiles ready",
                **result,
            )

        if export_png:
            minzoom = max(0, min(14, int(request.get("minzoom", 12))))
            maxzoom = max(minzoom, min(14, int(request.get("maxzoom", minzoom))))
            png_urls: dict[str, str] = {}
            update_job(
                job_id,
                progress=94,
                message=f"Render PNG screenshots z{minzoom}-z{maxzoom}",
                **result,
            )
            for index, zoom in enumerate(range(minzoom, maxzoom + 1), start=1):
                png_path = png_dir / f"z{zoom}.png"
                render_png_map(png_path, job_id, request["bbox"], zoom=zoom)
                png_urls[f"z{zoom}"] = f"/output/{job_id}/png/z{zoom}.png"
                update_job(
                    job_id,
                    progress=94 + min(3, index * 3 // max(1, maxzoom - minzoom + 1)),
                    message=f"PNG z{zoom} ready",
                    png_urls=png_urls,
                    **result,
                )
            result["preview_url"] = png_urls.get(f"z{maxzoom}")
            result["png_urls"] = png_urls
            update_job(
                job_id,
                progress=97,
                message=f"PNG screenshots ready z{minzoom}-z{maxzoom}",
                **result,
            )

        update_job(job_id, state="done", progress=100, message="Done", **result)
        return {"job_id": job_id, **result}
    except Exception as exc:
        if changes.exists():
            changes.unlink()
        update_job(job_id, state="failed", progress=100, message="Failed", error=str(exc))
        raise
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
