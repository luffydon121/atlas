"use client";

/* eslint-disable @next/next/no-img-element */
import dynamic from "next/dynamic";
import { useState } from "react";
import type { Point } from "@/components/AreaMap";
import { EChart, lineOption } from "@/components/EChart";
import { Panel, Skeleton, Stat, State, Toggle } from "@/components/ui";
import { send, useApi, useEnvelope, type Envelope } from "@/lib/api";
import { daysAgo, num } from "@/lib/format";

type Aoi = { id: string; name: string; tracker: string; index: string; bbox: number[]; ticker: string | null };
type Info = { aois: Aoi[]; indices: Record<string, { name: string; meaning: string }>; unsupported: Record<string, string>; resolution_note: string };
type Scene = { id: string; acquired_at: string; cloud_cover: number | null; platform: string; resolution_m: number; thumbnail: string | null };
type Stats = { valid_fraction: number; mean_before?: number; mean_after?: number; mean_change?: number; pct_increased?: number; pct_decreased?: number; noise_sigma?: number; threshold?: number; confidence: string };
type Change = { stats: Stats; before: Scene; after: Scene; overlay: string | null; index: string; index_meaning: string };

type Area = { id: number; name: string; tracker: string; tracker_label: string; index: string; polygon: Point[]; frequency_days: number; alert_pct: number | null; last_checked: string | null; last_error: string | null };
type Areas = { areas: Area[]; trackers: Record<string, { label: string; index: string }> };
const AreaMap = dynamic(() => import("@/components/AreaMap"), { ssr: false, loading: () => <Skeleton /> });

function Monitoring() {
  const list = useApi<Areas>("/api/satellite/areas");
  const [points, setPoints] = useState<Point[]>([]);
  const [form, setForm] = useState({ name: "", tracker: "mine", frequency_days: 7, alert_pct: "" });
  const [picked, setPicked] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const history = useApi<{ acquired_at: string; mean: number; clear_fraction: number }[]>(picked ? `/api/satellite/areas/${picked}/history` : null);

  const lons = points.map((p) => p[0]), lats = points.map((p) => p[1]);
  const wide = points.length ? Math.max(...lons) - Math.min(...lons) : 0, tall = points.length ? Math.max(...lats) - Math.min(...lats) : 0;
  const tooBig = wide > 0.3 || tall > 0.3;

  async function save() {
    try {
      const made: Area = await send("/api/satellite/areas", "POST", { name: form.name, tracker: form.tracker, frequency_days: form.frequency_days, alert_pct: form.alert_pct ? +form.alert_pct : null, polygon: points });
      setPoints([]);
      setForm({ ...form, name: "" });
      setPicked(made.id);
      setMessage(null);
      list.mutate();
    } catch (e) {
      setMessage((e as Error).message);
    }
  }

  async function check(id: number) {
    setBusy(true);
    try {
      const r = await send(`/api/satellite/areas/${id}/check`, "POST");
      setMessage(r.new_scene ? `New scene measured.${r.changed_pct !== undefined ? ` ${r.changed_pct.toFixed(1)}% of pixels changed against the same season last year.` : " No same-season scene to compare with."}` : "No newer clear scene yet.");
      history.mutate();
      list.mutate();
    } catch (e) {
      setMessage((e as Error).message);
    }
    setBusy(false);
  }

  return (
    <div className="grid-2">
      <Panel title="Draw a monitoring area" actions={<><button className="btn" disabled={!points.length} onClick={() => setPoints(points.slice(0, -1))}>Undo</button><button className="btn" disabled={!points.length} onClick={() => setPoints([])}>Clear</button></>}>
        <AreaMap points={points} onAdd={(p) => setPoints((v) => [...v, p])} />
        <div className="row" style={{ padding: 14 }}>
          <input className="input" aria-label="Area name" placeholder="Name this area" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <select className="input" aria-label="Tracker" value={form.tracker} onChange={(e) => setForm({ ...form, tracker: e.target.value })}>{Object.entries(list.data?.trackers ?? {}).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select>
          <label className="row muted">Every<input type="number" min={1} className="input" style={{ width: 62 }} value={form.frequency_days} onChange={(e) => setForm({ ...form, frequency_days: +e.target.value })} />days</label>
          <label className="row muted">Alert at<input type="number" min={0} className="input" style={{ width: 62 }} placeholder="%" value={form.alert_pct} onChange={(e) => setForm({ ...form, alert_pct: e.target.value })} /></label>
          <button className="btn on" disabled={points.length < 3 || !form.name || tooBig} onClick={save}>Save area</button>
        </div>
        <div className="panel-foot" role="status" style={tooBig ? { color: "var(--serious)" } : undefined}>{points.length ? `About ${Math.round(wide * 100)} by ${Math.round(tall * 100)} km.${tooBig ? " Too large: zoom in and redraw under 30 km a side." : ""}` : "Zoom in, then click the map to add at least three corners. Keep each side under about 30 km."}</div>
      </Panel>
      <Panel title="Your areas">
        {message && <div className="notice">{message}</div>}
        <State loading={list.isLoading && !list.data} error={list.error} empty={!list.data?.areas.length}>
          <table className="t"><tbody>{list.data?.areas.map((a) => <tr key={a.id} title={a.last_error ?? undefined} style={{ background: a.id === picked ? "var(--panel-2)" : undefined }}><td className="wrap"><button style={{ background: "none", border: 0, padding: 0, cursor: "pointer", textAlign: "left" }} onClick={() => setPicked(a.id)}>{a.name}</button><div className="muted" style={{ fontSize: 12 }}>{a.tracker_label} · every {a.frequency_days} days{a.alert_pct ? ` · alert at ${a.alert_pct}%` : ""}</div></td><td><span className="row" style={{ justifyContent: "flex-end" }}><button className="btn" disabled={busy} onClick={() => check(a.id)}>Check</button><a className="btn" href={`/api/satellite/areas/${a.id}/report`} target="_blank" rel="noreferrer">Report</a><button className="btn" onClick={() => send(`/api/satellite/areas/${a.id}`, "DELETE").then(() => list.mutate())}>Delete</button></span></td></tr>)}</tbody></table>
        </State>
        {picked && !!history.data?.length && <EChart height={170} option={lineOption([{ name: "Mean index", points: history.data.map((h): [string, number] => [h.acquired_at.slice(0, 10), +h.mean.toFixed(4)]) }])} />}
      </Panel>
    </div>
  );
}

export default function Satellite() {
  const info = useEnvelope<Info>("/api/satellite/aois");
  const [tracker, setTracker] = useState("mining");
  const [aoiId, setAoiId] = useState("whaleback");
  const [mission, setMission] = useState("sentinel-2");
  const [cloud, setCloud] = useState(15);
  const [before, setBefore] = useState("");
  const [after, setAfter] = useState("");
  const [index, setIndex] = useState<string | null>(null);
  const [result, setResult] = useState<Envelope<Change> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const aois = info.data?.data.aois ?? [];
  const aoi = aois.find((a) => a.id === aoiId);
  const trackers = [...new Set(aois.map((a) => a.tracker))];
  const b = aoi?.bbox;
  const start = daysAgo(500);
  const scenes = useEnvelope<{ scenes: Scene[]; matched: number | null }>(b ? `/api/satellite/scenes?west=${b[0]}&south=${b[1]}&east=${b[2]}&north=${b[3]}&mission=${mission}&max_cloud=${cloud}&start=${start}&limit=60` : null);
  const history = useEnvelope<{ acquired_at: string; index: string; mean: number; valid_fraction: number }[]>(aoi ? `/api/satellite/history/${aoi.id}` : null);
  const list = scenes.data?.data.scenes ?? [];
  const beforeId = before || list[list.length - 1]?.id;
  const afterId = after || list[0]?.id;
  const idx = index ?? aoi?.index ?? "ndvi";

  async function run() {
    if (!aoi) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await send("/api/satellite/change", "POST", { bbox: aoi.bbox, before_id: beforeId, after_id: afterId, index: idx, aoi: aoi.id }));
      history.mutate();
    } catch (e) {
      setError((e as Error).message);
    }
    setBusy(false);
  }

  const r = result?.data;
  return (
    <div className="page">
      <div className="notice" style={{ padding: 0 }}>{info.data?.data.resolution_note}</div>
      <div className="row">
        <Toggle value={tracker} options={trackers.map((t) => ({ value: t, label: t[0].toUpperCase() + t.slice(1) }))} onChange={(t) => { setTracker(t); const first = aois.find((a) => a.tracker === t); if (first) { setAoiId(first.id); setBefore(""); setAfter(""); setIndex(null); setResult(null); } }} />
        <select className="input" aria-label="Watch area" value={aoiId} onChange={(e) => { setAoiId(e.target.value); setBefore(""); setAfter(""); setResult(null); }}>{aois.filter((a) => a.tracker === tracker).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select>
        <select className="input" aria-label="Mission" value={mission} onChange={(e) => setMission(e.target.value)}><option value="sentinel-2">Sentinel-2 (10 m)</option><option value="landsat">Landsat (30 m, catalogue only)</option></select>
        <label className="row muted">Max cloud %<input type="number" className="input mono" style={{ width: 60 }} value={cloud} onChange={(e) => setCloud(+e.target.value)} /></label>
      </div>
      <div className="grid-2">
        <Panel title={`Scenes (${scenes.data?.data.matched ?? "…"} matched)`} meta={scenes.data?.meta} style={{ height: 430 }}>
          <State loading={scenes.isLoading} error={scenes.error} empty={!list.length}>
            <table className="t mono"><thead><tr><th>Acquired (UTC)</th><th>Cloud</th><th>Res</th><th className="l">Platform</th><th>Use as</th></tr></thead>
              <tbody>{list.map((s) => <tr key={s.id}><td>{s.acquired_at.slice(0, 16).replace("T", " ")}</td><td>{num(s.cloud_cover, 1)}%</td><td>{s.resolution_m} m</td><td className="l ink2">{s.platform}</td><td><button className={`btn ${beforeId === s.id ? "on" : ""}`} onClick={() => setBefore(s.id)}>Before</button> <button className={`btn ${afterId === s.id ? "on" : ""}`} onClick={() => setAfter(s.id)}>After</button></td></tr>)}</tbody></table>
          </State>
        </Panel>
        <Panel title="Change detection" meta={result?.meta} style={{ minHeight: 430 }} actions={<>
          <select className="input" aria-label="Index" value={idx} onChange={(e) => setIndex(e.target.value)}>{Object.entries(info.data?.data.indices ?? {}).map(([k, v]) => <option key={k} value={k}>{v.name}</option>)}</select>
          <button className="btn on" disabled={busy || mission !== "sentinel-2" || !beforeId} onClick={run}>{busy ? "Reading pixels…" : "Compare"}</button></>}>
          {error && <div className="notice bad">{error}</div>}
          {!r && !error && <div className="notice muted">Choose two clear scenes and compare. Pixels are read from public cloud-optimised files, so this can take about 20 seconds.</div>}
          {r && <>
            <div className="grid-4"><Stat k="Mean before" v={num(r.stats.mean_before, 3)} s={r.before.acquired_at.slice(0, 10)} /><Stat k="Mean after" v={num(r.stats.mean_after, 3)} s={r.after.acquired_at.slice(0, 10)} /><Stat k="Pixels rose" v={`${num(r.stats.pct_increased, 1)}%`} s={`by > ${r.stats.threshold}`} /><Stat k="Pixels fell" v={`${num(r.stats.pct_decreased, 1)}%`} s={`Confidence ${r.stats.confidence}`} /></div>
            <div className="row" style={{ padding: 8, alignItems: "flex-start", flexWrap: "nowrap" }}>
              {r.before.thumbnail && <figure style={{ margin: 0, flex: 1 }}><img src={r.before.thumbnail} alt="Before scene preview" style={{ width: "100%" }} /><figcaption className="muted">Whole tile, before</figcaption></figure>}
              {r.after.thumbnail && <figure style={{ margin: 0, flex: 1 }}><img src={r.after.thumbnail} alt="After scene preview" style={{ width: "100%" }} /><figcaption className="muted">Whole tile, after</figcaption></figure>}
              </div>
            {r.overlay && aoi && <AreaMap points={[]} overlay={{ url: r.overlay, bbox: aoi.bbox }} center={[(aoi.bbox[0] + aoi.bbox[2]) / 2, (aoi.bbox[1] + aoi.bbox[3]) / 2]} />}
            <div className="notice">{r.index_meaning}. Clear pixels {num(r.stats.valid_fraction * 100, 1)}%, noise σ {num(r.stats.noise_sigma, 3)}. Confidence is derived from these, not from ground truth.</div>
          </>}
        </Panel>
      </div>
      <Monitoring />
      <div className="grid-2">
        <Panel title="Stored measurements for this area"><State empty={!history.data?.data.length}><EChart height={170} option={lineOption([{ name: `Mean ${history.data?.data[0]?.index ?? "index"}`, points: history.data?.data.map((h) => [h.acquired_at.slice(0, 10), +h.mean.toFixed(4)]) ?? [] }])} /></State></Panel>
        <Panel title="Trackers ATLAS refuses to estimate">{Object.entries(info.data?.data.unsupported ?? {}).map(([k, v]) => <div key={k} className="notice"><b style={{ textTransform: "capitalize", color: "var(--ink)" }}>{k}:</b> {v}</div>)}</Panel>
      </div>
    </div>
  );
}
