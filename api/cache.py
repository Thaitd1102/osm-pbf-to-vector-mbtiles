from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import redis

from database import get_job_from_database, upsert_job, upsert_version


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
STATUS_TTL_SECONDS = int(os.getenv("STATUS_TTL_SECONDS", "86400"))

_redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def job_key(job_id: str) -> str:
    return f"job:{job_id}"


def set_job(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    # TODO(flow): Worker/API gọi hàm này để lưu status job vào Redis.
    existing = get_job(job_id) or {}
    merged = {**existing, **payload, "updated_at": now_iso()}
    if "created_at" not in merged:
        merged["created_at"] = merged["updated_at"]
    _redis.setex(job_key(job_id), STATUS_TTL_SECONDS, json.dumps(merged))
    try:
        upsert_job(merged)
    except Exception:
        pass
    return merged


def get_job(job_id: str) -> dict[str, Any] | None:
    raw = _redis.get(job_key(job_id))
    if raw:
        return json.loads(raw)
    try:
        return get_job_from_database(job_id)
    except Exception:
        return None


def list_versions() -> list[dict[str, Any]]:
    # TODO(flow): Quét data/versions/*.osm.pbf cho dropdown version.
    versions_dir = DATA_DIR / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)
    versions = []
    for path in sorted(versions_dir.glob("*.osm.pbf")):
        stat = path.stat()
        versions.append(
            {
                "name": path.name,
                "size": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                "path": str(path),
            }
        )
    for version in versions:
        try:
            upsert_version(version)
        except Exception:
            pass
    return versions
