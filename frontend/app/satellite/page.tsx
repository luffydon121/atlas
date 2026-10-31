"use client";

/* eslint-disable @next/next/no-img-element */
import { useState } from "react";
import { EChart, lineOption } from "@/components/EChart";
import { Panel, Stat, State, Toggle } from "@/components/ui";
import { send, useEnvelope, type Envelope } from "@/lib/api";
import { daysAgo, num } from "@/lib/format";

type Aoi = { id: string; name: string; tracker: string; index: string; bbox: number[]; ticker: string | null };
type Info = { aois: Aoi[]; indices: Record<string, { name: string; meaning: string }>; unsupported: Record<string, string>; resolution_note: string };
type Scene = { id: string; acquired_at: string; cloud_cover: number | null; platform: string; resolution_m: number; thumbnail: string | null };
type Stats = { valid_fraction: number; mean_before?: number; mean_after?: number; mean_change?: number; pct_increased?: number; pct_decreased?: number; noise_sigma?: number; threshold?: number; confidence: string };
type Change = { stats: Stats; before: Scene; after: Scene; overlay: string | null; index: string; index_meaning: string };

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
        <Panel title="Change detection" meta={result?.meta} style={{ height: 430 }} actions={<>
          <select className="input" aria-label="Index" value={idx} onChange={(e) => setIndex(e.target.value)}>{Object.entries(info.data?.data.indices ?? {}).map(([k, v]) => <option key={k} value={k}>{v.name}</option>)}</select>
          <button className="btn on" disabled={busy || mission !== "sentinel-2" || !beforeId} onClick={run}>{busy ? "Reading pixels…" : "Compare"}</button></>}>
          {error && <div className="notice bad">{error}</div>}
          {!r && !error && <div className="notice muted">Choose two clear scenes and compare. Pixels are read from public cloud-optimised files, so this can take about 20 seconds.</div>}
          {r && <>
            <div className="grid-4"><Stat k="Mean before" v={num(r.stats.mean_before, 3)} s={r.before.acquired_at.slice(0, 10)} /><Stat k="Mean after" v={num(r.stats.mean_after, 3)} s={r.after.acquired_at.slice(0, 10)} /><Stat k="Pixels rose" v={`${num(r.stats.pct_increased, 1)}%`} s={`by > ${r.stats.threshold}`} /><Stat k="Pixels fell" v={`${num(r.stats.pct_decreased, 1)}%`} s={`Confidence ${r.stats.confidence}`} /></div>
            <div className="row" style={{ padding: 8, alignItems: "flex-start", flexWrap: "nowrap" }}>
              {r.before.thumbnail && <figure style={{ margin: 0, flex: 1 }}><img src={r.before.thumbnail} alt="Before scene preview" style={{ width: "100%" }} /><figcaption className="muted">Whole tile, before</figcaption></figure>}
              {r.after.thumbnail && <figure style={{ margin: 0, flex: 1 }}><img src={r.after.thumbnail} alt="After scene preview" style={{ width: "100%" }} /><figcaption className="muted">Whole tile, after</figcaption></figure>}
              {r.overlay && <figure style={{ margin: 0, flex: 1 }}><img src={r.overlay} alt="Change map of the watch area" style={{ width: "100%", background: "var(--panel-2)" }} /><figcaption className="muted">Change map: blue rose, orange fell</figcaption></figure>}
            </div>
            <div className="notice">{r.index_meaning}. Clear pixels {num(r.stats.valid_fraction * 100, 1)}%, noise σ {num(r.stats.noise_sigma, 3)}. Confidence is derived from these, not from ground truth.</div>
          </>}
        </Panel>
      </div>
      <div className="grid-2">
        <Panel title="Stored measurements for this area"><State empty={!history.data?.data.length}><EChart height={170} option={lineOption([{ name: `Mean ${history.data?.data[0]?.index ?? "index"}`, points: history.data?.data.map((h) => [h.acquired_at.slice(0, 10), +h.mean.toFixed(4)]) ?? [] }])} /></State></Panel>
        <Panel title="Trackers ATLAS refuses to estimate">{Object.entries(info.data?.data.unsupported ?? {}).map(([k, v]) => <div key={k} className="notice"><b style={{ textTransform: "capitalize", color: "var(--ink)" }}>{k}:</b> {v}</div>)}</Panel>
      </div>
    </div>
  );
}
