from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from uuid import uuid4

from celery import Celery
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from cache import DATA_DIR, get_job, list_versions, now_iso, set_job
from database import database_status, get_latest_done_job_from_database, init_database, list_done_jobs_from_database
from models import JobRequest, JobState, JobStatus


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
BASE_MBTILES = Path(os.getenv("BASE_MBTILES", "/data/base/vietnam-260101-navigation.mbtiles"))
celery_app = Celery("maps_vietnam", broker=REDIS_URL, backend=REDIS_URL)

app = FastAPI(title="Maps Vietnam OSM Pipeline", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

output_dir = DATA_DIR / "output"
output_dir.mkdir(parents=True, exist_ok=True)
app.mount("/output", StaticFiles(directory=output_dir), name="output")

toll_data_dir = Path(os.getenv("TOLL_DATA_DIR", "/toll-data"))
if not toll_data_dir.exists():
    toll_data_dir = Path(__file__).resolve().parents[1] / "toll-station-pipeline" / "data"
if toll_data_dir.exists():
    app.mount("/toll-data", StaticFiles(directory=toll_data_dir), name="toll-data")


@app.on_event("startup")
def startup() -> None:
    try:
        init_database()
    except Exception as exc:
        print(f"WARNING: PostgreSQL init failed: {exc}", flush=True)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/database")
def database() -> dict[str, object]:
    try:
        return database_status()
    except Exception as exc:
        return {"connected": False, "error": str(exc)}


@app.get("/versions")
def versions() -> dict[str, list[dict]]:
    available_versions = list_versions()
    return {
        "versions": available_versions,
        "version_src": available_versions,
        "version_target": available_versions,
    }


@app.get("/base-map")
def base_map_status() -> dict[str, object]:
    # TODO(flow): Frontend gọi trước khi add lớp vector tile nội bộ.
    metadata = {}
    if BASE_MBTILES.exists():
        with sqlite3.connect(f"file:{BASE_MBTILES}?mode=ro", uri=True) as connection:
            metadata = dict(connection.execute("select name, value from metadata").fetchall())

    return {
        "name": BASE_MBTILES.name,
        "exists": BASE_MBTILES.exists(),
        "path": str(BASE_MBTILES),
        "center": metadata.get("center"),
        "bounds": metadata.get("bounds"),
        "minzoom": metadata.get("minzoom"),
        "maxzoom": metadata.get("maxzoom"),
    }


@app.get("/base-tiles/{z}/{x}/{y}.pbf")
def base_tile(z: int, x: int, y: int) -> Response:
    # TODO(flow): MapLibre gọi endpoint này thay cho OSM online tiles.
    if not BASE_MBTILES.exists():
        raise HTTPException(status_code=404, detail=f"Base MBTiles not found: {BASE_MBTILES}")

    # MBTiles lưu tile_row theo TMS, còn client web gửi y theo XYZ nên cần flip y.
    tms_y = (1 << z) - 1 - y
    with sqlite3.connect(f"file:{BASE_MBTILES}?mode=ro", uri=True) as connection:
        row = connection.execute(
            "select tile_data from tiles where zoom_level = ? and tile_column = ? and tile_row = ?",
            (z, x, tms_y),
        ).fetchone()

    if not row:
        # TODO(flow): Tile trống nằm ngoài dữ liệu Việt Nam; trả 204 để log/browser không báo lỗi đỏ.
        return Response(status_code=204)

    headers = {"Cache-Control": "public, max-age=3600"}
    if row[0][:2] == b"\x1f\x8b":
        headers["Content-Encoding"] = "gzip"

    return Response(
        content=row[0],
        media_type="application/vnd.mapbox-vector-tile",
        headers=headers,
    )


@app.get("/job-tiles/{job_id}/{z}/{x}/{y}.pbf")
def job_tile(job_id: str, z: int, x: int, y: int) -> Response:
    mbtiles = DATA_DIR / "output" / job_id / "patched.mbtiles"
    if not mbtiles.exists():
        raise HTTPException(status_code=404, detail=f"Patched MBTiles not found for job: {job_id}")

    tms_y = (1 << z) - 1 - y
    with sqlite3.connect(f"file:{mbtiles}?mode=ro", uri=True) as connection:
        row = connection.execute(
            "select tile_data from tiles where zoom_level = ? and tile_column = ? and tile_row = ?",
            (z, x, tms_y),
        ).fetchone()

    if not row:
        return Response(status_code=204)

    headers = {"Cache-Control": "no-store"}
    if row[0][:2] == b"\x1f\x8b":
        headers["Content-Encoding"] = "gzip"

    return Response(
        content=row[0],
        media_type="application/vnd.mapbox-vector-tile",
        headers=headers,
    )


@app.post("/jobs", response_model=JobStatus)
def create_job(request: JobRequest) -> JobStatus:
    # TODO(flow): API validate request rồi đẩy job sang Celery worker.run_pipeline.
    available = {item["name"] for item in list_versions()}
    missing = [name for name in [request.version_src, request.version_target] if name not in available]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing version file(s): {', '.join(missing)}")

    job_id = uuid4().hex
    payload = {
        "id": job_id,
        "state": JobState.queued.value,
        "progress": 0,
        "message": "Job queued",
        "request": request.model_dump(mode="json"),
        "created_at": now_iso(),
    }
    set_job(job_id, payload)
    celery_app.send_task("worker.run_pipeline", args=[job_id, request.model_dump(mode="json")])
    return JobStatus(**payload)


@app.get("/jobs/latest", response_model=JobStatus)
def get_latest_done_job() -> JobStatus:
    payload = get_latest_done_job_from_database()
    if not payload:
        raise HTTPException(status_code=404, detail="No completed job found")
    return JobStatus(**payload)


@app.get("/jobs/completed", response_model=list[JobStatus])
def list_completed_jobs(limit: int = 50) -> list[JobStatus]:
    safe_limit = max(1, min(200, limit))
    return [JobStatus(**payload) for payload in list_done_jobs_from_database(safe_limit)]


@app.get("/jobs/{job_id}", response_model=JobStatus)
def get_status(job_id: str) -> JobStatus:
    # TODO(flow): Frontend poll hàm này mỗi 1s để nhận progress + output URLs.
    payload = get_job(job_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(**payload)
