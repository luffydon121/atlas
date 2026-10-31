"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { EChart, lineOption } from "@/components/EChart";
import { Panel, Skeleton, State, Toggle } from "@/components/ui";
import { useEnvelope } from "@/lib/api";
import { ago, num, ratioPct, tone } from "@/lib/format";

type Rule = { id: string; name: string; mechanism: string; uncertainty: string; basis: string };
type Asset = { symbol: string; role: string; kind: string; rule: string };
type Analogue = { date: string; title: string; url: string };
type Info = { rules: Rule[]; industries: string[]; assets: Asset[]; analogues: Analogue[]; statement: string };
type Feed = { id: number; title: string; severity: string; verification: string; category: string; category_label: string; region: string | null; source: string; observed_at: string; rules: string[]; exposed: boolean };
type Detail = Feed & Info & { url: string | null; lat: number | null; nearby: { name: string; km: number; kind: string }[]; observed_moves: { symbol: string; from: string; to: string; change: number }[]; observed_note: string; evidence: { label: string; source: string; time: string | null; url: string | null; kind: string }[] };
type Reaction = { symbol: string; kind: string; role: string; n: number; mean_car: number | null; positive: number; t_stat: number | null; p_value: number | null; survives_correction: boolean; market_adjusted: boolean; mean_path: { day: number; value: number }[] };
type Reactions = { rows: Reaction[]; unavailable: string[]; window: number[]; dates: string[]; note: string };

const VERIFY: Record<string, string> = { official: "Official", derived: "Derived", unverified: "Unverified" };

function Reactions({ rules }: { rules: string[] }) {
  const key = rules.join(",");
  const { data, error, isLoading } = useEnvelope<Reactions>(key ? `/api/impact/reactions?rules=${encodeURIComponent(key)}` : null);
  const d = data?.data;
  const plotted = d?.rows.filter((r) => r.mean_path.length).slice(0, 4) ?? [];
  return (
    <Panel title="What happened around similar past events" meta={data?.meta}>
      <State loading={isLoading && !data} error={error} empty={!!d && !d.rows.length}>
        {d && <>
          <EChart height={220} option={lineOption(plotted.map((r) => ({ name: r.symbol, points: r.mean_path.map((p): [string, number] => [String(p.day), +(p.value * 100).toFixed(2)]) })), { yName: "Mean % vs expected" })} />
          <div className="panel-body"><table className="t sticky"><thead><tr><th>Asset</th><th>Events</th><th>Mean move</th><th>Rose</th><th>t</th><th>Survives correction</th></tr></thead>
            <tbody>{d.rows.map((r) => <tr key={r.symbol}><td><Link href={`/chart?s=${encodeURIComponent(r.symbol)}`}>{r.symbol}</Link></td><td>{r.n}</td><td className={tone(r.mean_car)}>{ratioPct(r.mean_car, 1, true)}</td><td>{r.positive} of {r.n}</td><td>{num(r.t_stat)}</td><td>{r.survives_correction ? "Yes" : "No"}</td></tr>)}</tbody></table></div>
          {!d.rows.some((r) => r.survives_correction) && <div className="notice">No reaction here is distinguishable from noise after correcting for testing several assets. Treat these as history, not a pattern.</div>}
        </>}
      </State>
    </Panel>
  );
}

function Exposure({ info }: { info: Info }) {
  return <>
    {info.rules.length === 0 && <div className="notice">No documented exposure matches this event. ATLAS will not guess one.</div>}
    {info.rules.length > 0 && <Panel title="Possible exposure">
      <div className="cards">
        <div className="note-card"><b>Hypothetical</b>{info.statement}</div>
        {info.rules.map((r) => <div key={r.id} className="note-card"><b>{r.name}</b><div>{r.mechanism}</div><div className="muted" style={{ marginTop: 6 }}>Uncertain: {r.uncertainty}</div><div className="muted" style={{ marginTop: 6 }}>Basis: {r.basis}</div></div>)}
      </div>
      {info.industries.length > 0 && <div className="row" style={{ padding: "0 20px 14px" }}>{info.industries.map((i) => <span key={i} className="tag">{i}</span>)}</div>}
      <table className="t"><thead><tr><th>Asset</th><th className="l">Why it may be exposed</th><th className="l">Type</th></tr></thead>
        <tbody>{info.assets.map((a) => <tr key={a.symbol}><td><Link href={`/chart?s=${encodeURIComponent(a.symbol)}`}>{a.symbol}</Link></td><td className="wrap ink2">{a.role}</td><td className="l muted">{a.kind}</td></tr>)}</tbody></table>
    </Panel>}
    {info.rules.length > 0 && <Reactions rules={info.rules.map((r) => r.id)} />}
    {info.analogues.length > 0 && <Panel title="Comparable past events"><table className="t"><tbody>{info.analogues.map((a) => <tr key={a.date + a.title}><td>{a.date}</td><td className="wrap"><a href={a.url} target="_blank" rel="noreferrer noopener">{a.title}</a></td></tr>)}</tbody></table></Panel>}
  </>;
}

function EventDetail({ id }: { id: number }) {
  const { data, error, isLoading } = useEnvelope<Detail>(`/api/impact/events/${id}`);
  const e = data?.data;
  return (
    <State loading={isLoading && !data} error={error}>
      {e && <div style={{ display: "grid", gap: 16 }}>
        <Panel title={e.title} meta={data?.meta}>
          <div className="feed-meta" style={{ padding: "0 20px 14px" }}><span className={`sev ${e.severity}`}>{e.severity}</span><span className="tag">{VERIFY[e.verification]}</span><span>{e.category_label}</span><span>{e.source}</span><span>{ago(e.observed_at)}</span>
            {e.url && <a href={e.url} target="_blank" rel="noreferrer noopener" style={{ textDecoration: "underline" }}>Source</a>}{e.lat !== null && <Link href={`/map?event=${e.id}`} style={{ textDecoration: "underline" }}>Show on map</Link>}</div>
        </Panel>
        {e.nearby.length > 0 && <Panel title="Nearby tracked infrastructure"><table className="t"><tbody>{e.nearby.map((n) => <tr key={n.name}><td className="wrap">{n.name}</td><td className="l muted">{n.kind}</td><td>{n.km} km</td></tr>)}</tbody></table></Panel>}
        {e.observed_moves.length > 0 && <Panel title="Observed moves since this reading"><table className="t"><tbody>{e.observed_moves.map((m) => <tr key={m.symbol}><td>{m.symbol}</td><td className="muted">{m.from} to {m.to}</td><td className={tone(m.change)}>{ratioPct(m.change, 1, true)}</td></tr>)}</tbody></table><div className="panel-foot">{e.observed_note}</div></Panel>}
        <Exposure info={e} />
        <Panel title="Evidence"><table className="t"><tbody>{e.evidence.map((x, i) => <tr key={i}><td className="wrap">{x.url ? <a href={x.url} target="_blank" rel="noreferrer noopener" style={{ textDecoration: "underline" }}>{x.label}</a> : x.label}</td><td className="l muted">{x.kind}</td><td className="l muted">{x.source}</td></tr>)}</tbody></table></Panel>
      </div>}
    </State>
  );
}

function Scenario() {
  const [zone, setZone] = useState("gulf_of_mexico");
  const { data, error, isLoading } = useEnvelope<Info & { statement: string; zones: Record<string, string> }>(`/api/impact/scenario?zone=${zone}`);
  return (
    <div style={{ display: "grid", gap: 16 }}>
      <Panel title="Explore a scenario" meta={data?.meta} actions={<select className="input" aria-label="Region" value={zone} onChange={(e) => setZone(e.target.value)}>{Object.entries(data?.data.zones ?? { gulf_of_mexico: "US Gulf Coast and Gulf of Mexico" }).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>}>
        <div className="notice"><b style={{ color: "var(--ink)" }}>Hypothetical.</b> {data?.data.statement} Choose a region to see what is documented there and how markets moved around past events.</div>
      </Panel>
      <State loading={isLoading && !data} error={error}>{data && <Exposure info={{ ...data.data, statement: "These exposures are hypotheses from documented geography and business lines." }} />}</State>
    </div>
  );
}

export default function ImpactPage() {
  const params = useSearchParams();
  const router = useRouter();
  const selected = params.get("event");
  const [verification, setVerification] = useState("all");
  const [mode, setMode] = useState<"Events" | "Scenario">(selected ? "Events" : "Events");
  const { data, error, isLoading } = useEnvelope<{ events: Feed[]; unavailable: string[] }>(`/api/impact/events${verification === "all" ? "" : `?verification=${verification}`}`, { refreshInterval: 300_000 });
  const rows = data?.data.events ?? [];
  const chosen = selected ? Number(selected) : rows.find((r) => r.exposed)?.id;
  return (
    <div className="page">
      <div className="row"><Toggle value={mode} options={["Events", "Scenario"] as const} onChange={setMode} />{mode === "Events" && <Toggle value={verification} options={[{ value: "all", label: "All" }, { value: "official", label: "Official" }, { value: "derived", label: "Derived" }, { value: "unverified", label: "Unverified" }]} onChange={setVerification} />}</div>
      {mode === "Scenario" ? <Scenario /> : <div className="impact-grid">
        <Panel title="Event feed" meta={data?.meta} className="impact-feed">
          <State loading={isLoading && !data} error={error} empty={!rows.length}>
            {rows.map((e) => <button key={e.id} className={`feed-item ${e.id === chosen ? "sel" : ""}`} onClick={() => router.replace(`/impact?event=${e.id}`, { scroll: false })}><b>{e.title}</b><span className="feed-meta"><span className={`sev ${e.severity}`}>{e.severity}</span><span>{VERIFY[e.verification]}</span><span>{e.category_label}</span><span>{ago(e.observed_at)}</span>{e.exposed && <span className="tag">Exposure</span>}</span></button>)}
          </State>
          {!!data?.data.unavailable.length && <div className="panel-foot">Unavailable right now: {data.data.unavailable.join(", ")}.</div>}
        </Panel>
        <div style={{ minWidth: 0 }}>{chosen ? <EventDetail id={chosen} key={chosen} /> : isLoading ? <section className="panel"><Skeleton /></section> : <Scenario />}</div>
      </div>}
    </div>
  );
}
