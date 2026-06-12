from enum import Enum
from pydantic import BaseModel, Field, field_validator


class JobState(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class BBox(BaseModel):
    min_lon: float = Field(..., ge=-180, le=180)
    min_lat: float = Field(..., ge=-90, le=90)
    max_lon: float = Field(..., ge=-180, le=180)
    max_lat: float = Field(..., ge=-90, le=90)

    @field_validator("max_lon")
    @classmethod
    def lon_order(cls, value: float, info):
        min_lon = info.data.get("min_lon")
        if min_lon is not None and value <= min_lon:
            raise ValueError("max_lon must be greater than min_lon")
        return value

    @field_validator("max_lat")
    @classmethod
    def lat_order(cls, value: float, info):
        min_lat = info.data.get("min_lat")
        if min_lat is not None and value <= min_lat:
            raise ValueError("max_lat must be greater than min_lat")
        return value

    def osmium_arg(self) -> str:
        return f"{self.min_lon},{self.min_lat},{self.max_lon},{self.max_lat}"

    def leaflet_bounds(self) -> list[list[float]]:
        return [[self.min_lat, self.min_lon], [self.max_lat, self.max_lon]]


class JobRequest(BaseModel):
    version_src: str
    version_target: str
    bbox: BBox
    minzoom: int = Field(12, ge=0, le=22)
    maxzoom: int = Field(15, ge=0, le=22)
    render: bool = False
    render_mbtiles: bool = False
    export_png: bool = False

    @field_validator("maxzoom")
    @classmethod
    def zoom_order(cls, value: int, info):
        minzoom = info.data.get("minzoom")
        if minzoom is not None and value < minzoom:
            raise ValueError("maxzoom must be greater than or equal to minzoom")
        return value


class JobStatus(BaseModel):
    id: str
    state: JobState
    progress: int = Field(0, ge=0, le=100)
    message: str = ""
    request: JobRequest | None = None
    output_url: str | None = None
    patched_pbf_url: str | None = None
    diff_geojson_url: str | None = None
    mbtiles_url: str | None = None
    preview_url: str | None = None
    png_urls: dict[str, str] | None = None
    cache: dict | None = None
    created_at: str | None = None
    updated_at: str | None = None
    error: str | None = None
