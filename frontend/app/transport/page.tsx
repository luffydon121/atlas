"use client";

import { useState } from "react";
import { EChart, lineOption } from "@/components/EChart";
import { Panel, Stat, State } from "@/components/ui";
import { useEnvelope } from "@/lib/api";
import { num, pct, tone } from "@/lib/format";

type Choke = { id: string; name: string; available: boolean; loading?: boolean; latest_date?: string; transits_7d_avg?: number; baseline_avg?: number; pct_vs_baseline?: number; z?: number; tanker_7d?: number; container_7d?: number; disrupted?: boolean; history?: { date: string; total: number; tanker: number; container: number }[] };
type Airport = { code: string; name: string };
type Activity = { name: string; aircraft_nearby: number; on_ground: number; airborne: number; history: { time: string; value: number }[] };

type Port = { portid: string; portname: string; country: string; available: boolean; loading?: boolean; latest_date?: string; calls_7d_avg?: number; baseline_avg?: number; pct_vs_baseline?: number | null; container_7d?: number; tanker_7d?: number; history?: { date: string; calls: number }[] };

export default function Transport() {
  const ports = useEnvelope<Port[]>("/api/trade/ports", { refreshInterval: (d) => (d?.data.some((p: Port) => p.loading) ? 15_000 : 0) });
  const [portId, setPortId] = useState("port1188");
  const port = ports.data?.data.find((p) => p.portid === portId);
  const ships = useEnvelope<Choke[]>("/api/shipping/chokepoints", { refreshInterval: (d) => (d?.data.some((c: Choke) => c.loading) ? 10_000 : 0) });
  const airports = useEnvelope<Airport[]>("/api/aviation/airports");
  const [id, setId] = useState("chokepoint1");
  const [code, setCode] = useState("SYD");
  const air = useEnvelope<Activity>(`/api/aviation/airport/${code}`, { refreshInterval: 300_000 });
  const c = ships.data?.data.find((x) => x.id === id);
  return (
    <div className="page">
      <div className="grid-2">
        <Panel title="Maritime chokepoints" meta={ships.data?.meta}>
          <State loading={ships.isLoading} error={ships.error}>
            <table className="t mono"><thead><tr><th>Chokepoint</th><th>Transits/day</th><th>vs 1Y</th><th>z</th><th>Tanker</th><th>Container</th><th>Latest</th></tr></thead>
              <tbody>{ships.data?.data.map((s) => <tr key={s.id} onClick={() => setId(s.id)} style={{ cursor: "pointer", background: s.id === id ? "var(--panel-2)" : undefined }}><td>{s.name}{s.disrupted ? " ▲" : ""}</td><td>{num(s.transits_7d_avg, 1)}</td><td className={tone(s.pct_vs_baseline)}>{pct(s.pct_vs_baseline, 1)}</td><td>{num(s.z)}</td><td>{num(s.tanker_7d, 1)}</td><td>{num(s.container_7d, 1)}</td><td className="muted">{s.latest_date ?? "—"}</td></tr>)}</tbody></table>
          </State>
        </Panel>
        <Panel title={`${c?.name ?? ""} daily transits`}>
          <EChart height={290} option={lineOption([{ name: "Total", points: c?.history?.map((h) => [h.date, h.total]) ?? [] }, { name: "Tanker", points: c?.history?.map((h) => [h.date, h.tanker]) ?? [] }, { name: "Container", points: c?.history?.map((h) => [h.date, h.container]) ?? [] }], { scale: false })} />
        </Panel>
      </div>
      <div className="grid-2">
        <Panel title="Major ports" meta={ports.data?.meta}>
          <State loading={ports.isLoading && !ports.data} error={ports.error}>
            <table className="t sticky"><thead><tr><th>Port</th><th>Calls/day</th><th>vs 1Y</th><th>Container</th><th>Tanker</th></tr></thead>
              <tbody>{ports.data?.data.map((p) => <tr key={p.portid} onClick={() => setPortId(p.portid)} style={{ cursor: "pointer", background: p.portid === portId ? "var(--panel-2)" : undefined }}><td>{p.portname}<div className="muted" style={{ fontSize: 12 }}>{p.country}</div></td>{p.available ? <><td>{num(p.calls_7d_avg, 1)}</td><td className={tone(p.pct_vs_baseline)}>{pct(p.pct_vs_baseline, 1)}</td><td>{num(p.container_7d, 1)}</td><td>{num(p.tanker_7d, 1)}</td></> : <td colSpan={4} className="muted">{p.loading ? "Loading…" : "No data"}</td>}</tr>)}</tbody></table>
          </State>
        </Panel>
        <Panel title={`${port?.portname ?? "Port"} daily calls`}><EChart height={290} option={lineOption([{ name: "Port calls", points: port?.history?.map((h): [string, number] => [h.date, h.calls]) ?? [] }], { scale: false })} /></Panel>
      </div>
      <Panel title="Airport activity proxy" meta={air.data?.meta} actions={<select className="input" aria-label="Airport" value={code} onChange={(e) => setCode(e.target.value)}>{airports.data?.data.map((a) => <option key={a.code} value={a.code}>{a.code} {a.name}</option>)}</select>}>
        <State loading={air.isLoading} error={air.error}>
          <div className="grid-3"><Stat k="Aircraft within about 55 km" v={air.data?.data.aircraft_nearby ?? "—"} /><Stat k="On ground" v={air.data?.data.on_ground ?? "—"} /><Stat k="Airborne" v={air.data?.data.airborne ?? "—"} /></div>
          <EChart height={150} option={lineOption([{ name: "Aircraft nearby", points: air.data?.data.history.map((h) => [h.time.slice(5, 16).replace("T", " "), h.value]) ?? [] }], { scale: false })} />
        </State>
      </Panel>
    </div>
  );
}
