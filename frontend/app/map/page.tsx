"use client";

import * as maplibregl from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import type { GeoJSONSource, Map as LibreMap } from "maplibre-gl";
import { useCallback, useEffect, useRef, useState } from "react";
import { get, type Envelope, useEnvelope } from "@/lib/api";
import { daysAgo } from "@/lib/format";
import { useTheme } from "@/lib/theme";

type Layer = { id: string; label: string; group: string; source: string; freshness: string };
type Result = Envelope<FeatureCollection>;

// The worker is served from /public (see scripts/copy-map-worker.mjs) because bundling breaks it.
maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");

const STYLES = { dark: "https://tiles.openfreemap.org/styles/dark", light: "https://tiles.openfreemap.org/styles/positron" };
const COLORS: Record<string, string> = {
  hazards_quakes: "#e66767", hazards_events: "#d95926", hazards_storms: "#d55181", agriculture: "#199e70", geopolitics: "#c98500", chokepoints: "#3987e5", ports: "#a4b3c2", routes: "#3987e5",
  aircraft: "#9085e9", airports: "#a4b3c2", energy: "#c98500", industrial: "#75869a", satellite_aois: "#38c6bd", economy: "#3987e5",
};
const RASTERS = [
  { id: "gibs_truecolor", label: "MODIS true colour", url: "MODIS_Terra_CorrectedReflectance_TrueColor/default/{date}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg" },
  { id: "gibs_fires", label: "VIIRS thermal anomalies", url: "VIIRS_SNPP_Thermal_Anomalies_375m_All/default/{date}/GoogleMapsCompatible_Level7/{z}/{y}/{x}.png" },
];
const GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/";

function popup(props: Record<string, unknown>): HTMLElement {
  // Feed text is untrusted, so it is only ever set as text content.
  const box = document.createElement("div");
  const title = document.createElement("b");
  title.textContent = String(props.name ?? props.title ?? props.callsign ?? props.place ?? "Feature");
  box.append(title);
  for (const [k, v] of Object.entries(props)) {
    if (v === null || v === undefined || v === "" || ["name", "title", "url", "id"].includes(k)) continue;
    const line = document.createElement("div");
    line.style.color = "var(--ink-2)";
    line.textContent = `${k.replace(/_/g, " ")}: ${v}`;
    box.append(line);
  }
  const url = String(props.url ?? "");
  if (url.startsWith("https://") || url.startsWith("http://")) {
    const a = document.createElement("a");
    a.href = url;
    a.target = "_blank";
    a.rel = "noreferrer noopener";
    a.textContent = "Open source";
    a.style.textDecoration = "underline";
    box.append(a);
  }
  return box;
}

export default function WorldMap() {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<LibreMap | null>(null);
  const theme = useTheme();
  const [ready, setReady] = useState(false);
  const [on, setOn] = useState<string[]>(["hazards_quakes", "hazards_events", "chokepoints", "routes", "ports"]);
  const [meta, setMeta] = useState<Record<string, Result["meta"] | { error: string }>>({});
  const [raster, setRaster] = useState<string[]>([]);
  const [offset, setOffset] = useState(2);
  const [playing, setPlaying] = useState(false);
  const [tier, setTier] = useState("all");
  const layers = useEnvelope<Layer[]>("/api/map/layers");
  const date = daysAgo(offset);

  useEffect(() => {
    const m = new maplibregl.Map({ container: host.current!, style: STYLES[theme === "dark" ? "dark" : "light"], center: [60, 20], zoom: 1.6, attributionControl: { compact: false } });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.on("load", () => { map.current = m; setReady(true); });
    return () => { map.current = null; setReady(false); m.remove(); };
  }, [theme]);

  const load = useCallback(async (id: string) => {
    const m = map.current;
    if (!m) return;
    const b = m.getBounds();
    const clamp = (v: number, lim: number) => Math.max(-lim, Math.min(lim, v));
    const q = id === "aircraft" ? `?west=${clamp(b.getWest(), 180)}&south=${clamp(b.getSouth(), 85)}&east=${clamp(b.getEast(), 180)}&north=${clamp(b.getNorth(), 85)}` : "";
    try {
      const r: Result = await get(`/api/map/layer/${id}${q}`);
      setMeta((v) => ({ ...v, [id]: r.meta }));
      if (!map.current) return;
      const src = m.getSource(id) as GeoJSONSource | undefined;
      if (src) src.setData(r.data);
      else {
        m.addSource(id, { type: "geojson", data: r.data });
        const color = COLORS[id] ?? "#3987e5";
        if (id === "routes") m.addLayer({ id, type: "line", source: id, paint: { "line-color": color, "line-width": 1.2, "line-opacity": 0.55, "line-dasharray": [3, 3] } });
        else {
          const radius: maplibregl.ExpressionSpecification | number = id === "hazards_quakes" ? ["interpolate", ["linear"], ["get", "mag"], 4.5, 3, 8, 14] : id === "aircraft" ? 2.5 : 5;
          m.addLayer({ id, type: "circle", source: id, paint: { "circle-radius": radius, "circle-color": id === "agriculture" ? ["match", ["get", "level"], "elevated", "#e66767", "watch", "#c98500", "#199e70"] : color, "circle-opacity": 0.8, "circle-stroke-color": theme === "dark" ? "#000000" : "#ffffff", "circle-stroke-width": 1 } });
          m.on("click", id, (e) => {
            const f = e.features?.[0];
            if (f) new maplibregl.Popup({ closeButton: false }).setLngLat(e.lngLat).setDOMContent(popup(f.properties as Record<string, unknown>)).addTo(m);
          });
          m.on("mouseenter", id, () => { m.getCanvas().style.cursor = "pointer"; });
          m.on("mouseleave", id, () => { m.getCanvas().style.cursor = ""; });
        }
      }
    } catch (e) {
      setMeta((v) => ({ ...v, [id]: { error: (e as Error).message } }));
    }
  }, [theme]);

  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    for (const l of layers.data?.data ?? []) {
      const visible = on.includes(l.id);
      if (m.getLayer(l.id)) m.setLayoutProperty(l.id, "visibility", visible ? "visible" : "none");
      else if (visible) load(l.id);
    }
  }, [on, ready, layers.data, load]);

  useEffect(() => {
    const m = map.current;
    if (!ready || !m || !on.includes("aircraft")) return;
    const handler = () => load("aircraft");
    m.on("moveend", handler);
    return () => { m.off("moveend", handler); };
  }, [on, ready, load]);

  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    for (const r of RASTERS) {
      if (m.getLayer(r.id)) m.removeLayer(r.id);
      if (m.getSource(r.id)) m.removeSource(r.id);
      if (raster.includes(r.id)) {
        m.addSource(r.id, { type: "raster", tiles: [GIBS + r.url.replace("{date}", date)], tileSize: 256, attribution: "NASA GIBS" });
        const first = m.getStyle().layers.find((x) => x.type === "symbol")?.id;
        m.addLayer({ id: r.id, type: "raster", source: r.id, paint: { "raster-opacity": 0.85 } }, first);
      }
    }
  }, [raster, date, ready]);

  useEffect(() => {
    const m = map.current;
    if (ready && m?.getLayer("geopolitics")) m.setFilter("geopolitics", tier === "all" ? null : ["==", ["get", "tier"], tier]);
  }, [tier, ready, meta.geopolitics]);

  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => setOffset((o) => (o <= 1 ? 30 : o - 1)), 1500);
    return () => clearInterval(t);
  }, [playing]);

  const toggle = (id: string) => setOn((v) => (v.includes(id) ? v.filter((x) => x !== id) : [...v, id]));
  const groups = [...new Set(layers.data?.data.map((l) => l.group))];

  return (
    <div className="map-wrap">
      <div ref={host} style={{ position: "absolute", inset: 0 }} data-testid="world-map" data-ready={ready} />
      <aside className="map-side" aria-label="Map layers">
        <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 10 }}>World map</div>
        {groups.map((g) => (
          <div key={g} style={{ marginBottom: 8 }}>
            <div className="muted" style={{ fontSize: 12, fontWeight: 600, margin: "4px 0 2px" }}>{g}</div>
            {layers.data?.data.filter((l) => l.group === g).map((l) => {
              const m = meta[l.id];
              const failed = m && "error" in m;
              return (
                <div key={l.id}>
                  <label className="row" style={{ flexWrap: "nowrap", cursor: "pointer", padding: "2px 0" }}>
                    <input type="checkbox" className="switch" checked={on.includes(l.id)} onChange={() => toggle(l.id)} />
                    <i style={{ width: 8, height: 8, borderRadius: 4, background: COLORS[l.id], flex: "none" }} />
                    <span style={{ flex: 1 }} title={failed ? "Unavailable" : l.freshness}>{l.label}</span>
                  </label>
                  {on.includes(l.id) && m && <div className="muted" style={{ fontSize: 11, paddingLeft: 20 }}>{"error" in m ? m.error : m.note}</div>}
                </div>
              );
            })}
          </div>
        ))}
        {on.includes("geopolitics") && <label className="row muted" style={{ marginBottom: 8 }}>Event tier<select className="input" value={tier} onChange={(e) => setTier(e.target.value)}><option value="all">All</option><option value="official">Official</option><option value="automated">Automated</option></select></label>}
        <div className="muted" style={{ fontSize: 12, fontWeight: 600, margin: "4px 0 2px" }}>Satellite imagery</div>
        {RASTERS.map((r) => <label key={r.id} className="row" style={{ cursor: "pointer", padding: "2px 0" }}><input type="checkbox" className="switch" checked={raster.includes(r.id)} onChange={() => setRaster((v) => (v.includes(r.id) ? v.filter((x) => x !== r.id) : [...v, r.id]))} />{r.label}</label>)}
        <div className="row" style={{ marginTop: 6 }}><span className="mono">{date}</span><button className="btn" onClick={() => setPlaying(!playing)}>{playing ? "Pause" : "Play 30d"}</button></div>
        <input type="range" aria-label="Imagery date" min={1} max={30} value={31 - offset} onChange={(e) => setOffset(31 - +e.target.value)} style={{ width: "100%" }} />
        <div className="muted" style={{ fontSize: 11 }}>Playback applies to NASA imagery. Other layers show current data.</div>
      </aside>
    </div>
  );
}
