(function () {
  const params = new URLSearchParams(window.location.search);
  const jobId = params.get("job_id");
  const apiBase = (params.get("api") || "/api").replace(/\/$/, "");
  const bbox = [
    Number(params.get("min_lon")),
    Number(params.get("min_lat")),
    Number(params.get("max_lon")),
    Number(params.get("max_lat"))
  ];
  const zoom = Number(params.get("zoom"));

  if (!jobId || bbox.some(value => !Number.isFinite(value))) {
    window.__RENDER_READY__ = false;
    throw new Error("Missing job_id or bbox params");
  }

  const map = new maplibregl.Map({
    container: "map",
    attributionControl: false,
    fadeDuration: 0,
    interactive: false,
    center: [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2],
    zoom: Number.isFinite(zoom) ? zoom : 12,
    style: {
      version: 8,
      sources: {
        patched: {
          type: "vector",
          tiles: [`${apiBase}/job-tiles/${jobId}/{z}/{x}/{y}.pbf`],
          minzoom: 0,
          maxzoom: 14,
          bounds: bbox
        }
      },
      layers: [
        {id: "background", type: "background", paint: {"background-color": "#f0ede5"}},
        {
          id: "landuse",
          type: "fill",
          source: "patched",
          "source-layer": "landuse",
          paint: {
            "fill-color": ["match", ["get", "class"], ["grass", "meadow", "park", "garden", "golf_course", "cemetery"], "#c8fabc", ["farmland", "orchard"], "#eae9da", ["industrial", "commercial", "retail"], "#e9e5e0", "#f5f5f0"],
            "fill-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0.12, 10, 0.18, 13.5, 0.12, 15, 0.06, 17, 0.03]
          }
        },
        {
          id: "landcover",
          type: "fill",
          source: "patched",
          "source-layer": "landcover",
          paint: {
            "fill-color": ["match", ["get", "class"], ["wood", "forest"], "#9bc580", ["wetland"], "#c4d5d6", "#d5e8d0"],
            "fill-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0.1, 10, 0.16, 13.5, 0.11, 15, 0.06, 17, 0.03]
          }
        },
        {
          id: "water",
          type: "fill",
          source: "patched",
          "source-layer": "water",
          paint: {"fill-color": "#b3d9ff", "fill-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0.12, 10, 0.24, 13.5, 0.16, 15, 0.08, 17, 0.04]}
        },
        {
          id: "waterway",
          type: "line",
          source: "patched",
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
          source: "patched",
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
          source: "patched",
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
          source: "patched",
          "source-layer": "transportation",
          layout: {"line-cap": "round", "line-join": "round"},
          paint: {
            "line-color": ["case", ["==", ["get", "toll"], "yes"], "#d23f2f", ["match", ["get", "highway"], ["motorway", "motorway_link"], "#fcd592", ["trunk", "trunk_link"], "#f2b355", ["primary", "primary_link"], "#fddd8f", ["secondary", "tertiary"], "#f1ebe9", "#fefdfb"]],
            "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.4, 10, 0.95, 14, 2.1, 17, 2.55],
            "line-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0.56, 13.5, 0.56, 16, 0.38, 18, 0.24],
            "line-blur": 0
          }
        },
        {
          id: "toll-gantry",
          type: "circle",
          source: "patched",
          "source-layer": "toll_gantry",
          paint: {"circle-radius": 5, "circle-color": "#d23f2f", "circle-stroke-color": "#ffffff", "circle-stroke-width": 1}
        },
        {
          id: "pois",
          type: "circle",
          source: "patched",
          "source-layer": "pois",
          paint: {"circle-radius": 4, "circle-color": "#24735a", "circle-stroke-color": "#ffffff", "circle-stroke-width": 1}
        }
      ]
    }
  });

  map.once("idle", () => {
    window.__RENDER_READY__ = true;
  });
  map.on("error", event => {
    console.error(event.error || event);
  });
})();
