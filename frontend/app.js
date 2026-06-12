const API_BASE = window.API_BASE || "/api";
const API_URL = new URL(API_BASE, window.location.origin).href.replace(/\/$/, "");
const USE_ONLINE_FALLBACK = window.USE_ONLINE_FALLBACK ?? true;
const SHOW_INTERNAL_BASE_OVERLAY = window.SHOW_INTERNAL_BASE_OVERLAY ?? false;
const SHOW_INTERNAL_POINTS = window.SHOW_INTERNAL_POINTS ?? false;
const SHOW_INTERNAL_LABELS = window.SHOW_INTERNAL_LABELS ?? false;
const VIETNAM_CENTER = [108.369134, 15.392187];
const VIETNAM_BOUNDS = [[102.0409, 7.730748], [111.6685, 23.47731]];
const TILE_BOUNDS = [102.095945, 7.382239, 114.642323, 23.402135];
const VIEW_MAX_ZOOM = 16;
const RENDER_MAX_ZOOM = 14;
const TOLL_GEOJSON_URL = `${API_URL}/toll-data/clean/toll_stations_clean.geojson`;
const TOLL_GEOJSON_SOURCE_ID = "toll-stations-geojson";
const TOLL_GEOJSON_LAYER_IDS = ["toll-geojson-halo", "toll-geojson-point"];
const INTERNAL_TOLL_LAYER_IDS = ["internal-toll-gantry-halo", "internal-toll-gantry"];

let selectedBounds = null;
let diffLegend = null;
let pollTimer = null;
let drawState = null;

const elements = {
  src: document.getElementById("version-src"),
  target: document.getElementById("version-target"),
  minzoom: document.getElementById("minzoom"),
  maxzoom: document.getElementById("maxzoom"),
  renderMbtiles: document.getElementById("render-mbtiles"),
  exportPng: document.getElementById("export-png"),
  toggleBasemap: document.getElementById("btn-toggle-basemap"),
  toggleDiff: document.getElementById("btn-toggle-diff"),
  tollCountBadge: document.getElementById("toll-count-badge"),
  bbox: document.getElementById("bbox-value"),
  drawBbox: document.getElementById("btn-draw-bbox"),
  clearBbox: document.getElementById("btn-clear-bbox"),
  clearLog: document.getElementById("btn-clear-log"),
  submit: document.getElementById("submit-job"),
  state: document.getElementById("job-state"),
  progress: document.getElementById("progress-bar"),
  message: document.getElementById("job-message"),
  output: document.getElementById("output-link"),
  flowArea: document.getElementById("flow-area"),
  flowAreaCard: document.getElementById("flow-area-card"),
  flowSize: document.getElementById("flow-size"),
  flowTiles: document.getElementById("flow-tiles"),
  flowBasemap: document.getElementById("flow-basemap"),
  flowZoom: document.getElementById("flow-zoom"),
  zoomLevel: document.getElementById("zoom-level"),
  flowOutput: document.getElementById("flow-output"),
  logBody: document.getElementById("log-body")
};

const INTERNAL_BASE_LAYER_IDS = [
  "internal-landuse",
  "internal-landcover",
  "internal-water",
  "internal-waterway",
  "internal-boundary",
  "internal-road-casing",
  "internal-road",
  "internal-pois"
];
let internalBasemapVisible = false;
let diffPointsVisible = true;
const completedJobs = new Map();
const renderedPatchJobIds = new Set();
const renderedDiffPrefixes = new Set();

const map = new maplibregl.Map({
  container: "map",
  center: VIETNAM_CENTER,
  zoom: 10,
  minZoom: 5,
  maxZoom: VIEW_MAX_ZOOM,
  maxBounds: VIETNAM_BOUNDS,
  attributionControl: false,
  fadeDuration: 160,
  maxTileCacheSize: 512,
  renderWorldCopies: false,
  style: {
    version: 8,
    sources: {
      ...(USE_ONLINE_FALLBACK ? {
        osmFallback: {
          type: "raster",
          tiles: [
            "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
            "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
            "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png"
          ],
          tileSize: 256,
          attribution: "© OpenStreetMap contributors"
        }
      } : {}),
      internal: {
        type: "vector",
        tiles: [`${API_URL}/base-tiles/{z}/{x}/{y}.pbf`],
        minzoom: 6,
        maxzoom: 14,
        bounds: TILE_BOUNDS
      },
      [TOLL_GEOJSON_SOURCE_ID]: {
        type: "geojson",
        data: TOLL_GEOJSON_URL
      }
    },
    layers: [
      {id: "background", type: "background", paint: {"background-color": "#f0ede5"}},
      ...(USE_ONLINE_FALLBACK ? [{
        id: "osm-fallback",
        type: "raster",
        source: "osmFallback",
        paint: {"raster-opacity": 1, "raster-resampling": "linear", "raster-fade-duration": 80}
      }] : []),
      ...(SHOW_INTERNAL_BASE_OVERLAY ? [
      {
        id: "landuse",
        type: "fill",
        source: "internal",
        "source-layer": "landuse",
        paint: {
          "fill-color": ["match", ["get", "class"], ["grass", "meadow", "park", "garden", "golf_course", "cemetery"], "#c8fabc", ["farmland", "orchard"], "#eae9da", ["industrial", "commercial", "retail"], "#e9e5e0", "#f5f5f0"],
          "fill-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0.12, 10, 0.18, 13.5, 0.12, 15, 0.06, 17, 0.03]
        }
      },
      {
        id: "landcover",
        type: "fill",
        source: "internal",
        "source-layer": "landcover",
        paint: {
          "fill-color": ["match", ["get", "class"], ["wood", "forest"], "#9bc580", ["wetland"], "#c4d5d6", "#d5e8d0"],
          "fill-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0.1, 10, 0.16, 13.5, 0.11, 15, 0.06, 17, 0.03]
        }
      },
      {
        id: "water",
        type: "fill",
        source: "internal",
        "source-layer": "water",
        paint: {"fill-color": "#b3d9ff", "fill-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0.12, 10, 0.24, 13.5, 0.16, 15, 0.08, 17, 0.04]}
      },
      {
        id: "waterway",
        type: "line",
        source: "internal",
        "source-layer": "waterway",
        paint: {
          "line-color": "#0099ff",
          "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.45, 12, 1.05, 14, 1.65, 17, 2.15],
          "line-opacity": ["interpolate", ["linear"], ["zoom"], 8, 0.58, 13.5, 0.48, 16, 0.34, 18, 0.22],
          "line-blur": 0
        }
      },
      {
        id: "boundary",
        type: "line",
        source: "internal",
        "source-layer": "boundary",
        paint: {
          "line-color": "#999999",
          "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.55, 14, 1.15, 17, 1.25],
          "line-opacity": ["interpolate", ["linear"], ["zoom"], 8, 0.42, 13.5, 0.36, 16, 0.24, 18, 0.16],
          "line-dasharray": [2.2, 2],
          "line-blur": 0
        }
      },
      {
        id: "road-casing",
        type: "line",
        source: "internal",
        "source-layer": "transportation",
        layout: {"line-cap": "round", "line-join": "round"},
        paint: {
          "line-color": "#b0a9a0",
          "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.45, 10, 1.1, 14, 2.7, 17, 3.1],
          "line-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0.24, 13.5, 0.28, 16, 0.2, 18, 0.14],
          "line-blur": 0
        }
      },
      {
        id: "road",
        type: "line",
        source: "internal",
        "source-layer": "transportation",
        layout: {"line-cap": "round", "line-join": "round"},
        paint: {
          "line-color": ["case", ["==", ["get", "toll"], "yes"], "#d23f2f", ["match", ["get", "highway"], ["motorway", "motorway_link"], "#fcd592", ["trunk", "trunk_link"], "#f2b355", ["primary", "primary_link"], "#fddd8f", ["secondary", "tertiary"], "#f1ebe9", "#fefdfb"]],
          "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.4, 10, 0.95, 14, 2.1, 17, 2.55],
          "line-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0.56, 13.5, 0.56, 16, 0.38, 18, 0.24],
          "line-blur": 0
        }
      },
      ] : []),
      ...(SHOW_INTERNAL_LABELS ? [
      {
        id: "place-label",
        type: "symbol",
        source: "internal",
        "source-layer": "place",
        minzoom: 8,
        layout: {
          "text-field": ["get", "name"],
          "text-font": ["Noto Sans Regular"],
          "text-size": ["interpolate", ["linear"], ["zoom"], 8, 10, 12, 12, 16, 15],
          "text-anchor": "center",
          "text-allow-overlap": false,
          "text-ignore-placement": false
        },
        paint: {
          "text-color": "#263238",
          "text-halo-color": "rgba(255, 255, 255, 0.92)",
          "text-halo-width": ["interpolate", ["linear"], ["zoom"], 8, 1.1, 14, 1.5, 17, 1.8],
          "text-halo-blur": 0.1,
          "text-opacity": ["interpolate", ["linear"], ["zoom"], 8, 0.72, 12, 0.9, 16, 0.78]
        }
      }
      ] : []),
      ...(SHOW_INTERNAL_POINTS ? [
      {
        id: "place",
        type: "circle",
        source: "internal",
        "source-layer": "place",
        paint: {"circle-radius": 4, "circle-color": "#3f4a4f", "circle-stroke-color": "#ffffff", "circle-stroke-width": 1}
      },
      {
        id: "pois",
        type: "circle",
        source: "internal",
        "source-layer": "pois",
        paint: {"circle-radius": 4, "circle-color": "#24735a", "circle-stroke-color": "#ffffff", "circle-stroke-width": 1}
      },
      {
        id: "toll-gantry",
        type: "circle",
        source: "internal",
        "source-layer": "toll_gantry",
        paint: {"circle-radius": 5, "circle-color": "#d23f2f", "circle-stroke-color": "#ffffff", "circle-stroke-width": 1}
      }
      ] : []),
      {
        id: "internal-toll-gantry-halo",
        type: "circle",
        source: "internal",
        "source-layer": "toll_gantry",
        minzoom: 5,
        layout: {"visibility": "none"},
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 6, 8, 8, 11, 11, 14, 15, 16, 18],
          "circle-color": "#d23f2f",
          "circle-opacity": ["interpolate", ["linear"], ["zoom"], 5, 0.22, 9, 0.18, 14, 0.14]
        }
      },
      {
        id: "internal-toll-gantry",
        type: "circle",
        source: "internal",
        "source-layer": "toll_gantry",
        minzoom: 5,
        layout: {"visibility": "none"},
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 3.5, 8, 5, 11, 7, 14, 10, 16, 12],
          "circle-color": "#d23f2f",
          "circle-opacity": 0.94,
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 7, 1.2, 13, 2],
          "circle-stroke-opacity": 0.96
        }
      },
      {
        id: "toll-geojson-halo",
        type: "circle",
        source: TOLL_GEOJSON_SOURCE_ID,
        minzoom: 5,
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 6, 8, 8, 11, 11, 14, 15, 16, 18],
          "circle-color": "#0f9f8f",
          "circle-opacity": ["interpolate", ["linear"], ["zoom"], 5, 0.2, 9, 0.17, 14, 0.13]
        }
      },
      {
        id: "toll-geojson-point",
        type: "circle",
        source: TOLL_GEOJSON_SOURCE_ID,
        minzoom: 5,
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 3.5, 8, 5, 11, 7, 14, 10, 16, 12],
          "circle-color": "#0f9f8f",
          "circle-opacity": 0.94,
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 7, 1.2, 13, 2],
          "circle-stroke-opacity": 0.96
        }
      }
    ]
  }
});
window.pipelineMap = map;

map.addControl(new maplibregl.NavigationControl({showCompass: false}), "top-left");
map.addControl(new maplibregl.AttributionControl({compact: true}), "bottom-left");

function displayValue(value) {
  return value === undefined || value === null ? "" : String(value).trim();
}

function escapeHtml(value) {
  return displayValue(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function imageHtml(url) {
  const value = displayValue(url);
  if (!/^https?:\/\//i.test(value)) return "";
  return `<img class="toll-popup-image" src="${escapeHtml(value)}" alt="">`;
}

function tollHasEtc(props) {
  const tags = displayValue(props.tags);
  return displayValue(props.payment_etc) === "yes"
    || displayValue(props.payment) === "etc"
    || tags.includes("payment:etc=yes")
    || tags.includes("payment=etc");
}

function tollStatusText(status) {
  const value = displayValue(status);
  if (!value || value === "active") return "Đang hoạt động";
  if (value === "inactive") return "Không hoạt động";
  if (value === "closed") return "Đã đóng cửa";
  if (value === "closed_permanently") return "Đã đóng cửa vĩnh viễn";
  return value;
}

function tollPopupHtml(props) {
  const hasEtc = tollHasEtc(props);
  const image = displayValue(props.image_url) || displayValue(props.thumbnail);
  const sourceUrl = displayValue(props.source_url);
  const rows = [
    ["Loại", "Trạm thu phí ETC"],
    ["Thu phí ETC", hasEtc ? "Có" : "Không"],
    ["Tình trạng", tollStatusText(props.status)],
    ["Ghi chú trạng thái", props.status_note],
    ["Đơn vị vận hành", props.operator],
    ["Tỉnh/thành", props.province],
    ["Tuyến", props.road],
    ["Địa chỉ", props.address],
    ["Độ tin cậy", props.confidence]
  ].filter(([, value]) => displayValue(value));

  return `
    <section class="toll-popup">
      ${imageHtml(image)}
      <strong>${escapeHtml(props.name) || "Trạm thu phí"}</strong>
      ${rows.map(([key, value]) => `<div><b>${escapeHtml(key)}:</b> ${escapeHtml(value)}</div>`).join("")}
      ${sourceUrl ? `<a class="toll-popup-link" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Mở nguồn tham chiếu</a>` : ""}
    </section>
  `;
}

map.on("click", "internal-toll-gantry", event => {
  const feature = event.features && event.features[0];
  if (!feature) return;
  const props = feature.properties || {};
  new maplibregl.Popup({maxWidth: "320px"})
    .setLngLat(event.lngLat)
    .setHTML(tollPopupHtml(props))
    .addTo(map);
});
map.on("mouseenter", "internal-toll-gantry", () => { map.getCanvas().style.cursor = "pointer"; });
map.on("mouseleave", "internal-toll-gantry", () => { map.getCanvas().style.cursor = ""; });

map.on("click", "toll-geojson-point", event => {
  const feature = event.features && event.features[0];
  if (!feature) return;
  const props = feature.properties || {};
  new maplibregl.Popup({maxWidth: "340px"})
    .setLngLat(event.lngLat)
    .setHTML(tollPopupHtml(props))
    .addTo(map);
});
map.on("mouseenter", "toll-geojson-point", () => { map.getCanvas().style.cursor = "pointer"; });
map.on("mouseleave", "toll-geojson-point", () => { map.getCanvas().style.cursor = ""; });

function setStatus(state, progress, message) {
  elements.state.textContent = state;
  elements.progress.style.width = `${Math.max(0, Math.min(100, progress))}%`;
  elements.message.textContent = message || "";
}

function addLog(message, type = "dim") {
  const line = document.createElement("div");
  line.className = `log-line ${type}`;
  line.textContent = `[${new Date().toLocaleTimeString("vi-VN")}] ${message}`;
  elements.logBody.appendChild(line);
  elements.logBody.scrollTop = elements.logBody.scrollHeight;
}

function clearLog() {
  elements.logBody.innerHTML = "";
}

function updateZoomLabel() {
  const zoom = map.getZoom().toFixed(2);
  elements.flowZoom.textContent = zoom;
  elements.zoomLevel.textContent = zoom;
}

function clampRenderZoom(value) {
  return Math.min(RENDER_MAX_ZOOM, Math.max(0, Number(value || RENDER_MAX_ZOOM)));
}

function normalizedRenderZooms() {
  const minzoom = clampRenderZoom(elements.minzoom.value || 12);
  const maxzoom = Math.max(minzoom, clampRenderZoom(elements.maxzoom.value));
  return {minzoom, maxzoom};
}

function outputUrl(path) {
  if (!path) return "";
  return path.startsWith("/output") ? path : `/api${path}`;
}

function boundsToPolygon(bounds) {
  if (!bounds) return {type: "FeatureCollection", features: []};
  const {west, south, east, north} = bounds;
  return {
    type: "FeatureCollection",
    features: [{
      type: "Feature",
      properties: {},
      geometry: {
        type: "Polygon",
        coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]]
      }
    }]
  };
}

function normalizeBounds(a, b) {
  return {
    west: Number(Math.min(a.lng, b.lng).toFixed(6)),
    south: Number(Math.min(a.lat, b.lat).toFixed(6)),
    east: Number(Math.max(a.lng, b.lng).toFixed(6)),
    north: Number(Math.max(a.lat, b.lat).toFixed(6))
  };
}

function updateBboxSource() {
  const source = map.getSource("selected-bbox");
  if (source) source.setData(boundsToPolygon(selectedBounds));
}

function addWorkingSources() {
  if (!map.getSource("selected-bbox")) {
    map.addSource("selected-bbox", {type: "geojson", data: boundsToPolygon(null)});
    map.addLayer({
      id: "selected-bbox-fill",
      type: "fill",
      source: "selected-bbox",
      paint: {"fill-color": "#2f79a3", "fill-opacity": 0.12}
    });
    map.addLayer({
      id: "selected-bbox-line",
      type: "line",
      source: "selected-bbox",
      paint: {"line-color": "#2f79a3", "line-width": 3}
    });
  }
}

async function loadInternalBaseMap() {
  const response = await fetch(`${API_BASE}/base-map`);
  if (!response.ok) throw new Error("Không đọc được trạng thái bản đồ nội bộ");
  const data = await response.json();
  if (!data.exists) {
    elements.flowBasemap.textContent = "Chưa có MBTiles";
    addLog(`Chưa có MBTiles nội bộ: ${data.name}. Chạy build_base_map.py trước.`, "err");
    return;
  }
  if (data.center) {
    const [lon, lat, zoom] = data.center.split(",").map(Number);
    if (Number.isFinite(lon) && Number.isFinite(lat)) {
      map.jumpTo({center: [lon, lat], zoom: Number.isFinite(zoom) ? zoom : map.getZoom()});
    }
  } else if (data.bounds) {
    const [west, south, east, north] = data.bounds.split(",").map(Number);
    if ([west, south, east, north].every(Number.isFinite)) {
      map.fitBounds([[west, south], [east, north]], {padding: 36});
    }
  }
  elements.flowBasemap.textContent = `${data.name.replace(".mbtiles", "")} ổn định`;
  addLog(`MapLibre đang dùng nền nội bộ: ${data.name}.`, "ok");
}

function showLegend() {
  if (diffLegend) return;
  diffLegend = document.createElement("div");
  diffLegend.className = "legend map-legend";
  diffLegend.innerHTML = `
    <div class="legend-row"><span class="dot create"></span>Thêm mới</div>
    <div class="legend-row"><span class="dot modify"></span>Chỉnh sửa</div>
    <div class="legend-row"><span class="dot delete"></span>Xóa</div>
  `;
  document.getElementById("map").appendChild(diffLegend);
}

function hideLegend() {
  if (!diffLegend) return;
  diffLegend.remove();
  diffLegend = null;
}

function popupHtml(feature) {
  const props = feature.properties || {};
  let tags = props.tags || {};
  if (typeof tags === "string") {
    try {
      tags = JSON.parse(tags);
    } catch {
      tags = {};
    }
  }
  const tagHtml = Object.entries(tags).map(([key, value]) => `${key}=${value}`).join("<br>");
  return `
    <strong>${String(props.action || "").toUpperCase()}</strong> - ${props.osm_type || feature.geometry.type}<br>
    ID: ${props.id || ""}<br>
    ${tagHtml || "(no tags)"}
  `;
}

function geojsonBounds(geojson) {
  const bounds = new maplibregl.LngLatBounds();
  const visit = coords => {
    if (typeof coords[0] === "number") {
      bounds.extend(coords);
      return;
    }
    coords.forEach(visit);
  };
  (geojson.features || []).forEach(feature => visit(feature.geometry.coordinates));
  return bounds;
}

function removeLayerIfExists(id) {
  if (map.getLayer(id)) map.removeLayer(id);
}

function removeSourceIfExists(id) {
  if (map.getSource(id)) map.removeSource(id);
}

function overlayBeforeLayerId() {
  const dynamicDiffLayers = [...renderedDiffPrefixes].flatMap(diffLayerIds);
  return ["selected-bbox-fill", ...dynamicDiffLayers].find(id => map.getLayer(id));
}

function vectorMapLayerDefinitions(sourceId = "internal", prefix = "internal") {
  return [
    {
      id: `${prefix}-landuse`,
      type: "fill",
      source: sourceId,
      "source-layer": "landuse",
      paint: {
        "fill-color": ["match", ["get", "class"], ["grass", "meadow", "park", "garden", "golf_course", "cemetery"], "#dcebd5", ["farmland", "orchard"], "#e8e2c7", ["industrial", "commercial", "retail"], "#e7ddd8", "#ece6d8"],
        "fill-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0.12, 10, 0.18, 13.5, 0.12, 15, 0.06, 17, 0.03]
      }
    },
    {
      id: `${prefix}-landcover`,
      type: "fill",
      source: sourceId,
      "source-layer": "landcover",
      paint: {
        "fill-color": ["match", ["get", "class"], ["wood", "forest"], "#cfe3c6", ["wetland"], "#cde2dc", "#d8e8cb"],
        "fill-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0.1, 10, 0.16, 13.5, 0.11, 15, 0.06, 17, 0.03]
      }
    },
    {
      id: `${prefix}-water`,
      type: "fill",
      source: sourceId,
      "source-layer": "water",
      paint: {"fill-color": "#67bfe8", "fill-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0.12, 10, 0.24, 13.5, 0.16, 15, 0.08, 17, 0.04]}
    },
    {
      id: `${prefix}-waterway`,
      type: "line",
      source: sourceId,
      "source-layer": "waterway",
      paint: {
        "line-color": "#149bd0",
        "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.45, 12, 1.05, 14, 1.65, 17, 2.15],
        "line-opacity": ["interpolate", ["linear"], ["zoom"], 8, 0.58, 13.5, 0.48, 16, 0.34, 18, 0.22],
        "line-blur": 0
      }
    },
    {
      id: `${prefix}-boundary`,
      type: "line",
      source: sourceId,
      "source-layer": "boundary",
      paint: {
        "line-color": "#8e67a0",
        "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.55, 14, 1.15, 17, 1.25],
        "line-opacity": ["interpolate", ["linear"], ["zoom"], 8, 0.42, 13.5, 0.36, 16, 0.24, 18, 0.16],
        "line-dasharray": [2.2, 2],
        "line-blur": 0
      }
    },
    {
      id: `${prefix}-road-casing`,
      type: "line",
      source: sourceId,
      "source-layer": "transportation",
      layout: {"line-cap": "round", "line-join": "round"},
      paint: {
        "line-color": "#b9a885",
        "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.45, 10, 1.1, 14, 2.7, 17, 3.1],
        "line-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0.24, 13.5, 0.28, 16, 0.2, 18, 0.14],
        "line-blur": 0
      }
    },
    {
      id: `${prefix}-road`,
      type: "line",
      source: sourceId,
      "source-layer": "transportation",
      layout: {"line-cap": "round", "line-join": "round"},
      paint: {
        "line-color": ["case", ["==", ["get", "toll"], "yes"], "#c44e2f", ["match", ["get", "highway"], ["motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link"], "#d6a43a", ["secondary", "tertiary"], "#ffffff", "#f8faf7"]],
        "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.4, 10, 0.95, 14, 2.1, 17, 2.55],
        "line-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0.56, 13.5, 0.56, 16, 0.38, 18, 0.24],
        "line-blur": 0
      }
    },
    {
      id: `${prefix}-pois`,
      type: "circle",
      source: sourceId,
      "source-layer": "pois",
      paint: {"circle-radius": 4, "circle-color": "#24735a", "circle-stroke-color": "#ffffff", "circle-stroke-width": 1}
    },
    {
      id: `${prefix}-toll-gantry`,
      type: "circle",
      source: sourceId,
      "source-layer": "toll_gantry",
      paint: {"circle-radius": 5, "circle-color": "#d23f2f", "circle-stroke-color": "#ffffff", "circle-stroke-width": 1}
    }
  ];
}

function internalBaseLayerDefinitions() {
  return vectorMapLayerDefinitions("internal", "internal");
}

function patchedJobSourceId(jobId) {
  return `patched-job-${jobId}`;
}

function patchedJobLayerPrefix(jobId) {
  return `patched-job-${jobId}`;
}

function patchedJobLayerIds(jobId) {
  const prefix = patchedJobLayerPrefix(jobId);
  return [
    `${prefix}-landuse`,
    `${prefix}-landcover`,
    `${prefix}-water`,
    `${prefix}-waterway`,
    `${prefix}-boundary`,
    `${prefix}-road-casing`,
    `${prefix}-road`,
    `${prefix}-pois`,
    `${prefix}-toll-gantry`
  ];
}

function diffLayerIds(prefix) {
  return [`${prefix}-polygon`, `${prefix}-line`, `${prefix}-point`];
}

function diffPrefixForJob(jobId) {
  return `diff-${jobId}`;
}

function setLayerVisibility(id, visible) {
  if (map.getLayer(id)) {
    map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
  }
}

function syncTollStationLayerVisibility() {
  TOLL_GEOJSON_LAYER_IDS.forEach(id => setLayerVisibility(id, !internalBasemapVisible));
  INTERNAL_TOLL_LAYER_IDS.forEach(id => setLayerVisibility(id, internalBasemapVisible));
}

async function updateTollCountBadge() {
  if (!elements.tollCountBadge) return;
  try {
    const response = await fetch(TOLL_GEOJSON_URL, {cache: "no-store"});
    if (!response.ok) throw new Error("Không tải được GeoJSON trạm thu phí");
    const geojson = await response.json();
    const count = geojson.features?.length || 0;
    elements.tollCountBadge.textContent = `Trạm thu phí: ${count}`;
  } catch (error) {
    elements.tollCountBadge.textContent = "Trạm thu phí: lỗi tải";
    addLog(error.message, "err");
  }
}

function setInternalBasemap(visible) {
  internalBasemapVisible = visible;
  if (visible) {
    const beforeId = overlayBeforeLayerId();
    internalBaseLayerDefinitions().forEach(layer => {
      if (!map.getLayer(layer.id)) {
        map.addLayer(layer, beforeId);
      }
    });
    renderCompletedJobLayers();
  } else {
    [...INTERNAL_BASE_LAYER_IDS].reverse().forEach(removeLayerIfExists);
    removeAllPatchedJobBasemaps();
    removeAllDiffLayers();
    hideLegend();
  }
  setLayerVisibility("osm-fallback", !visible);
  syncTollStationLayerVisibility();
  elements.toggleBasemap.classList.toggle("active", visible);
  elements.toggleBasemap.textContent = visible ? "Nền OSM online" : "Nền MBTiles";
  elements.flowBasemap.textContent = visible ? "MBTiles nội bộ" : "OSM online";
  addLog(visible ? "Đã bật nền MBTiles nội bộ." : "Đã quay về nền OSM online.", "info");
}

function removePatchedJobBasemap(jobId) {
  [...patchedJobLayerIds(jobId)].reverse().forEach(removeLayerIfExists);
  removeSourceIfExists(patchedJobSourceId(jobId));
  renderedPatchJobIds.delete(jobId);
}

function removeAllPatchedJobBasemaps() {
  [...renderedPatchJobIds].forEach(removePatchedJobBasemap);
}

function showPatchedJobBasemap(jobId) {
  if (!internalBasemapVisible) return;
  removePatchedJobBasemap(jobId);
  const beforeId = overlayBeforeLayerId();
  if (!map.getLayer("internal-road")) {
    internalBaseLayerDefinitions().forEach(layer => {
      if (!map.getLayer(layer.id)) map.addLayer(layer, beforeId);
    });
  }
  const sourceId = patchedJobSourceId(jobId);
  const prefix = patchedJobLayerPrefix(jobId);
  map.addSource(sourceId, {
    type: "vector",
    tiles: [`${API_URL}/job-tiles/${jobId}/{z}/{x}/{y}.pbf`],
    minzoom: 0,
    maxzoom: RENDER_MAX_ZOOM
  });
  vectorMapLayerDefinitions(sourceId, prefix).forEach(layer => map.addLayer(layer, beforeId));
  renderedPatchJobIds.add(jobId);
  elements.flowBasemap.textContent = "MBTiles nội bộ + vùng đã render";
}

function removeDiffLayer(prefix) {
  diffLayerIds(prefix).forEach(removeLayerIfExists);
  removeSourceIfExists(prefix);
  renderedDiffPrefixes.delete(prefix);
}

function removeAllDiffLayers() {
  [...renderedDiffPrefixes].forEach(removeDiffLayer);
}

function setDiffVisibility(visible) {
  diffPointsVisible = visible;
  if (!visible) {
    [...renderedDiffPrefixes].forEach(prefix => removeLayerIfExists(`${prefix}-point`));
  } else {
    [...renderedDiffPrefixes].forEach(prefix => addDiffPointLayer(prefix));
  }
  elements.toggleDiff.classList.toggle("inactive", !visible);
  elements.toggleDiff.textContent = visible ? "Ẩn chấm" : "Hiện chấm";
  addLog(visible ? "Đã hiện các chấm point." : "Đã ẩn các chấm point.", "info");
}

function renderCompletedJobLayers() {
  if (!internalBasemapVisible) return;
  [...completedJobs.values()].forEach(job => {
    if (job.mbtiles_url) showPatchedJobBasemap(job.id);
  });
  renderCompletedDiffLayers();
}

function renderCompletedDiffLayers() {
  if (!internalBasemapVisible) return;
  [...completedJobs.values()].forEach(job => {
    if (job.diff_geojson_url) {
      showDiffLayer(job.diff_geojson_url, {prefix: diffPrefixForJob(job.id), fit: false})
        .catch(error => addLog(`Không tải diff ${job.id}: ${error.message}`, "err"));
    }
  });
}

async function showDiffLayer(diffUrl, options = {}) {
  const prefix = options.prefix || "diff";
  if (!internalBasemapVisible) return;
  const response = await fetch(outputUrl(diffUrl));
  if (!response.ok) throw new Error("Không tải được diff GeoJSON");
  const geojson = await response.json();

  diffLayerIds(prefix).forEach(removeLayerIfExists);
  removeSourceIfExists(prefix);
  map.addSource(prefix, {type: "geojson", data: geojson});
  map.addLayer({
    id: `${prefix}-polygon`,
    type: "fill",
    source: prefix,
    filter: ["==", ["geometry-type"], "Polygon"],
    paint: {"fill-color": ["coalesce", ["get", "color"], "#888888"], "fill-opacity": 0.18}
  });
  renderedDiffPrefixes.add(prefix);
  map.addLayer({
    id: `${prefix}-line`,
    type: "line",
    source: prefix,
    filter: ["any", ["==", ["geometry-type"], "LineString"], ["==", ["geometry-type"], "Polygon"]],
    paint: {"line-color": ["coalesce", ["get", "color"], "#888888"], "line-width": 3, "line-opacity": 0.88}
  });
  if (diffPointsVisible) addDiffPointLayer(prefix);

  diffLayerIds(prefix).filter(layerId => map.getLayer(layerId)).forEach(layerId => {
    map.on("click", layerId, event => {
      const feature = event.features?.[0];
      if (!feature) return;
      new maplibregl.Popup().setLngLat(event.lngLat).setHTML(popupHtml(feature)).addTo(map);
    });
    map.on("mouseenter", layerId, () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", layerId, () => { map.getCanvas().style.cursor = ""; });
  });

  showLegend();
  if (geojson.features?.length && options.fit !== false) {
    map.fitBounds(geojsonBounds(geojson), {padding: 28, maxZoom: 16});
  }
  addLog(`Đã hiển thị ${geojson.features?.length || 0} object thay đổi trên bản đồ.`, "ok");
}

function addDiffPointLayer(prefix) {
  if (!map.getSource(prefix) || map.getLayer(`${prefix}-point`)) return;
  map.addLayer({
    id: `${prefix}-point`,
    type: "circle",
    source: prefix,
    filter: ["==", ["geometry-type"], "Point"],
    paint: {"circle-radius": 6, "circle-color": ["coalesce", ["get", "color"], "#888888"], "circle-stroke-color": "#ffffff", "circle-stroke-width": 1.5}
  });
}

function bboxFromBounds(bounds) {
  return {
    min_lon: bounds.west,
    min_lat: bounds.south,
    max_lon: bounds.east,
    max_lat: bounds.north
  };
}

function boundsFromBbox(bbox) {
  return {
    west: bbox.min_lon,
    south: bbox.min_lat,
    east: bbox.max_lon,
    north: bbox.max_lat
  };
}

function formatBBox(bbox) {
  return `${bbox.min_lon}, ${bbox.min_lat}\n${bbox.max_lon}, ${bbox.max_lat}`;
}

function lonToTileX(lon, zoom) {
  return Math.floor((lon + 180) / 360 * 2 ** zoom);
}

function latToTileY(lat, zoom) {
  const rad = lat * Math.PI / 180;
  return Math.floor((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2 * 2 ** zoom);
}

function estimateTileCount(bbox, minzoom, maxzoom) {
  if (!bbox || minzoom > maxzoom) return 0;
  let total = 0;
  for (let z = minzoom; z <= maxzoom; z += 1) {
    const x1 = lonToTileX(bbox.min_lon, z);
    const x2 = lonToTileX(bbox.max_lon, z);
    const y1 = latToTileY(bbox.max_lat, z);
    const y2 = latToTileY(bbox.min_lat, z);
    total += (Math.abs(x2 - x1) + 1) * (Math.abs(y2 - y1) + 1);
  }
  return total;
}

function bboxSizeLabel(bbox) {
  if (!bbox) return "0 m x 0 m";
  const midlat = (bbox.min_lat + bbox.max_lat) / 2;
  const width = Math.abs(bbox.max_lon - bbox.min_lon) * 111320 * Math.cos(midlat * Math.PI / 180);
  const height = Math.abs(bbox.max_lat - bbox.min_lat) * 111320;
  return `${width.toFixed(0)} m x ${height.toFixed(0)} m`;
}

function updateFlowSummary(statusText = "") {
  const bbox = selectedBounds ? bboxFromBounds(selectedBounds) : null;
  const {minzoom, maxzoom} = normalizedRenderZooms();
  elements.flowArea.textContent = bbox ? "Đã chọn" : "Chưa chọn";
  elements.flowSize.textContent = bboxSizeLabel(bbox);
  elements.flowTiles.textContent = bbox ? String(estimateTileCount(bbox, minzoom, maxzoom)) : "0";
  elements.flowOutput.textContent = statusText || "patched.osm.pbf + diff.geojson";
  elements.flowAreaCard.classList.toggle("ready", Boolean(bbox));
}

function updateSubmitState() {
  elements.submit.disabled = !selectedBounds || !elements.src.value || !elements.target.value;
  updateFlowSummary();
}

function applySelectedBounds(bounds) {
  selectedBounds = bounds;
  updateBboxSource();
  elements.bbox.textContent = formatBBox(bboxFromBounds(selectedBounds));
  addLog(`Đã khoanh vùng ${bboxSizeLabel(bboxFromBounds(selectedBounds))}.`, "info");
  updateSubmitState();
}

function startBboxDraw() {
  drawState = {active: true, start: null};
  map.dragPan.disable();
  map.getCanvas().style.cursor = "crosshair";
  setStatus("Đang khoanh", 0, "Kéo chuột trên bản đồ để khoanh bbox.");
  addLog("Bắt đầu khoanh bbox trên bản đồ.", "info");
}

function clearBbox() {
  selectedBounds = null;
  updateBboxSource();
  elements.bbox.textContent = "Chưa chọn vùng";
  addLog("Đã xóa vùng đang chọn.", "dim");
  updateSubmitState();
}

function finishDrawing() {
  drawState = null;
  map.dragPan.enable();
  map.getCanvas().style.cursor = "";
}

map.on("mousedown", event => {
  if (!drawState?.active) return;
  event.preventDefault();
  drawState.start = event.lngLat;
});

map.on("mousemove", event => {
  if (!drawState?.start) return;
  selectedBounds = normalizeBounds(drawState.start, event.lngLat);
  updateBboxSource();
});

map.on("mouseup", event => {
  if (!drawState?.start) return;
  const bounds = normalizeBounds(drawState.start, event.lngLat);
  finishDrawing();
  if (bounds.west === bounds.east || bounds.south === bounds.north) {
    clearBbox();
    return;
  }
  applySelectedBounds(bounds);
});

map.on("load", () => {
  addWorkingSources();
  syncTollStationLayerVisibility();
  updateTollCountBadge();
  updateZoomLabel();
  loadInternalBaseMap().catch(error => {
    elements.flowBasemap.textContent = "Lỗi nền nội bộ";
    addLog(error.message, "err");
  });
  restoreCompletedJobsDisplay().catch(error => addLog(`Không khôi phục các job đã render: ${error.message}`, "dim"));
});

map.on("zoom", updateZoomLabel);

map.on("error", event => {
  const message = event.error?.message || "MapLibre render lỗi không xác định";
  addLog(message, "err");
});

async function loadVersions() {
  setStatus("Đang tải", 0, "Đang đọc danh sách version...");
  addLog("Đọc danh sách PBF trong data/versions.", "dim");
  const response = await fetch(`${API_BASE}/versions`);
  if (!response.ok) throw new Error("Không đọc được /versions");
  const data = await response.json();
  const versions = data.versions || [];
  const options = versions.map(item => `<option value="${item.name}">${item.name}</option>`).join("");
  elements.src.innerHTML = options;
  elements.target.innerHTML = options;
  if (versions.length > 1) {
    elements.src.selectedIndex = 0;
    elements.target.selectedIndex = versions.length - 1;
  }
  setStatus("Idle", 0, versions.length ? "Sẵn sàng nhận job mới." : "Chưa có file .osm.pbf trong data/versions.");
  addLog(`Tìm thấy ${versions.length} version PBF.`, versions.length ? "ok" : "err");
  updateSubmitState();
}

async function restoreCompletedJobsDisplay() {
  const response = await fetch(`${API_BASE}/jobs/completed?limit=80`);
  if (response.status === 404) return;
  if (!response.ok) throw new Error("Không đọc được danh sách job đã render");
  const jobs = await response.json();
  const displayJobs = jobs.filter(job => job.mbtiles_url || job.diff_geojson_url).reverse();
  if (!displayJobs.length) return;

  displayJobs.forEach(job => completedJobs.set(job.id, job));
  if (internalBasemapVisible) {
    renderCompletedJobLayers();
  }

  const latest = displayJobs[displayJobs.length - 1];
  if (latest.patched_pbf_url || latest.output_url) {
    const pbfUrl = latest.patched_pbf_url || latest.output_url;
    elements.output.href = outputUrl(pbfUrl);
    elements.output.textContent = "Tải patched.osm.pbf mới nhất";
  }
  setStatus("Restored", 100, `Đã nạp ${displayJobs.length} vùng đã render`);
  addLog(`Đã nạp ${displayJobs.length} vùng vá từ DB. Bật Nền MBTiles để xem.`, "ok");
}

async function submitJob() {
  if (!selectedBounds) return;
  const payload = {
    version_src: elements.src.value,
    version_target: elements.target.value,
    bbox: bboxFromBounds(selectedBounds),
    ...normalizedRenderZooms(),
    render: elements.renderMbtiles.checked,
    render_mbtiles: elements.renderMbtiles.checked,
    export_png: elements.exportPng.checked
  };

  elements.submit.disabled = true;
  removeLayerIfExists("preview-overlay");
  removeSourceIfExists("preview-overlay");
  elements.output.removeAttribute("href");
  elements.output.textContent = "Đang chạy";
  setStatus("Queued", 3, "Đang gửi job...");
  updateFlowSummary("Đang tạo job patch");
  addLog(`Gửi job: ${payload.version_src} -> ${payload.version_target}.`, "info");

  const response = await fetch(`${API_BASE}/jobs`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Không tạo được job");
  }
  addLog(`Job ${data.id} đã vào queue.`, "ok");
  pollJob(data.id);
}

function showPreview(previewUrl) {
  ["preview-overlay"].forEach(removeLayerIfExists);
  removeSourceIfExists("preview-overlay");
  const {west, south, east, north} = selectedBounds;
  map.addSource("preview-overlay", {
    type: "image",
    url: previewUrl,
    coordinates: [[west, north], [east, north], [east, south], [west, south]]
  });
  map.addLayer({
    id: "preview-overlay",
    type: "raster",
    source: "preview-overlay",
    paint: {"raster-opacity": 0.72}
  });
}

async function pollJob(jobId) {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const response = await fetch(`${API_BASE}/jobs/${jobId}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Không đọc được job");
      setStatus(data.state, data.progress, data.error || data.message);
      updateFlowSummary(data.message || data.state);

      if (data.state === "done" || data.state === "failed") {
        clearInterval(pollTimer);
        elements.submit.disabled = false;
        addLog(data.state === "done" ? "Job hoàn tất." : `Job lỗi: ${data.error || data.message}`, data.state === "done" ? "ok" : "err");
      }

      if (data.state === "done" && data.output_url) {
        completedJobs.set(data.id, data);
        const pbfUrl = data.patched_pbf_url || data.output_url;
        elements.output.href = outputUrl(pbfUrl);
        elements.output.textContent = "Tải patched.osm.pbf";

        if (internalBasemapVisible) {
          if (data.mbtiles_url) {
            showPatchedJobBasemap(data.id);
          }
          if (data.diff_geojson_url) {
            await showDiffLayer(data.diff_geojson_url, {prefix: diffPrefixForJob(data.id)});
          }
        } else if (data.mbtiles_url || data.diff_geojson_url) {
          addLog("Vùng render đã lưu. Bật Nền MBTiles để xem trên map.", "info");
        }

        if (data.png_urls) {
          const pngCount = Object.keys(data.png_urls).length;
          addLog(`Đã tạo ${pngCount} ảnh PNG theo mức zoom.`, "ok");
        } else if (data.preview_url) {
          addLog(`PNG preview đã tạo: ${data.preview_url}`, "ok");
        }

        if (data.mbtiles_url) {
          addLog(`MBTiles đã tạo: ${data.mbtiles_url}`, "ok");
        }
      }
    } catch (error) {
      clearInterval(pollTimer);
      elements.submit.disabled = false;
      setStatus("Error", 100, error.message);
      addLog(error.message, "err");
    }
  }, 1000);
}

elements.submit.addEventListener("click", () => {
  submitJob().catch(error => {
    elements.submit.disabled = false;
    setStatus("Error", 100, error.message);
  });
});

elements.src.addEventListener("change", updateSubmitState);
elements.target.addEventListener("change", updateSubmitState);
elements.drawBbox.addEventListener("click", startBboxDraw);
elements.clearBbox.addEventListener("click", clearBbox);
elements.clearLog.addEventListener("click", clearLog);
elements.toggleBasemap.addEventListener("click", () => setInternalBasemap(!internalBasemapVisible));
elements.toggleDiff.addEventListener("click", () => setDiffVisibility(!diffPointsVisible));
elements.minzoom.addEventListener("change", () => {
  elements.minzoom.value = String(clampRenderZoom(elements.minzoom.value || 12));
  const {maxzoom} = normalizedRenderZooms();
  elements.maxzoom.value = String(maxzoom);
  updateFlowSummary();
});
elements.maxzoom.addEventListener("change", () => {
  const {maxzoom} = normalizedRenderZooms();
  elements.maxzoom.value = String(maxzoom);
  updateFlowSummary();
});

loadVersions().catch(error => setStatus("Error", 100, error.message));
