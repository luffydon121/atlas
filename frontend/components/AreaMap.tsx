"use client";

import type { FeatureCollection } from "geojson";
import type { GeoJSONSource, Map as LibreMap } from "maplibre-gl";
import * as maplibregl from "maplibre-gl";
import { useEffect, useRef } from "react";
import { useTheme } from "@/lib/theme";

maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");

export type Point = [number, number];
const STYLES = { dark: "https://tiles.openfreemap.org/styles/dark", light: "https://tiles.openfreemap.org/styles/positron" };

function shape(points: Point[]): FeatureCollection {
  const coords = points.length > 2 ? [...points, points[0]] : points;
  return { type: "FeatureCollection", features: points.length > 1 ? [{ type: "Feature", properties: {}, geometry: points.length > 2 ? { type: "Polygon", coordinates: [coords] } : { type: "LineString", coordinates: coords } }] : [] };
}

export default function AreaMap({ points, onAdd, overlay, center }: { points: Point[]; onAdd?: (p: Point) => void; overlay?: { url: string; bbox: number[] } | null; center?: Point }) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<LibreMap | null>(null);
  const add = useRef(onAdd);
  const theme = useTheme();

  useEffect(() => {
    add.current = onAdd;
  }, [onAdd]);

  useEffect(() => {
    const m = new maplibregl.Map({ container: host.current!, style: STYLES[theme === "dark" ? "dark" : "light"], center: center ?? [134, -25], zoom: center ? 9 : 4 });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.on("load", () => {
      m.addSource("area", { type: "geojson", data: shape(points) });
      m.addLayer({ id: "area-fill", type: "fill", source: "area", paint: { "fill-color": "#2997ff", "fill-opacity": 0.2 } });
      m.addLayer({ id: "area-line", type: "line", source: "area", paint: { "line-color": "#2997ff", "line-width": 2 } });
      map.current = m;
    });
    m.on("click", (e) => add.current?.([+e.lngLat.lng.toFixed(5), +e.lngLat.lat.toFixed(5)]));
    return () => {
      map.current = null;
      m.remove();
    };
    // The map is rebuilt only for a theme change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme]);

  useEffect(() => {
    (map.current?.getSource("area") as GeoJSONSource | undefined)?.setData(shape(points));
  }, [points]);

  useEffect(() => {
    const m = map.current;
    if (!m || !overlay) return;
    const [w, s, e, n] = overlay.bbox;
    if (m.getLayer("overlay")) m.removeLayer("overlay");
    if (m.getSource("overlay")) m.removeSource("overlay");
    m.addSource("overlay", { type: "image", url: overlay.url, coordinates: [[w, n], [e, n], [e, s], [w, s]] });
    m.addLayer({ id: "overlay", type: "raster", source: "overlay", paint: { "raster-opacity": 0.85 } });
    m.fitBounds([[w, s], [e, n]], { padding: 30, duration: 600 });
  }, [overlay]);

  return <div ref={host} className="area-map" data-testid="area-map" />;
}
