"use client";

import { useState } from "react";
import { EChart, lineOption } from "@/components/EChart";
import { Panel, Stat, State } from "@/components/ui";
import { useEnvelope } from "@/lib/api";
import { compact, num } from "@/lib/format";

type Signal = { id: string; name: string; status: string; method: string; history: string; source: string; frequency: string; limitations: string; confidence: string; validation: string; assets: string };
type Award = { recipient: string; amount: number; id: string; agency: string; description: string };
type Attention = { article: string; stats: { available: boolean; views_7d_avg?: number; views_90d_avg?: number; z?: number; latest_date?: string; validation?: { test: string; in_sample: number; out_of_sample: number; n: number; caveat: string } }; history: { date: string; value: number }[] };

export default function Alternative() {
  const signals = useEnvelope<Signal[]>("/api/alt/signals");
  const [form, setForm] = useState({ symbol: "MSFT", article: "Microsoft" });
  const [query, setQuery] = useState(form);
  const stocks = useEnvelope<{ date: string; value: number; change: number | null }[]>("/api/alt/inventories");
  const [company, setCompany] = useState("Lockheed Martin");
  const [who, setWho] = useState(company);
  const awards = useEnvelope<Award[]>(`/api/alt/procurement?company=${encodeURIComponent(who)}`);
  const [status, setStatus] = useState("all");
  const a = useEnvelope<Attention>(`/api/alt/attention/${encodeURIComponent(query.symbol)}?article=${encodeURIComponent(query.article)}`);
  const s = a.data?.data.stats;
  return (
    <div className="page">
      <Panel title="Public attention, Wikipedia views" meta={a.data?.meta} actions={<form className="row" onSubmit={(e) => { e.preventDefault(); setQuery(form); }}><input className="input mono" style={{ width: 90 }} aria-label="Ticker" value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value })} /><input className="input" aria-label="Wikipedia article" value={form.article} onChange={(e) => setForm({ ...form, article: e.target.value })} /><button className="btn">Load</button></form>}>
        <State loading={a.isLoading} error={a.error}>
          <div className="grid-4"><Stat k="7-day average" v={compact(s?.views_7d_avg)} /><Stat k="90-day baseline" v={compact(s?.views_90d_avg)} /><Stat k="Attention z-score" v={num(s?.z)} /><Stat k="Out-of-sample correlation" v={num(s?.validation?.out_of_sample, 3)} s={s?.validation ? `In-sample ${s.validation.in_sample}, n=${s.validation.n}` : undefined} /></div>
          <EChart height={200} option={lineOption([{ name: "Daily views", points: a.data?.data.history.map((h) => [h.date, h.value]) ?? [] }], { scale: false })} />
          {s?.validation && <div className="notice">{s.validation.test}. {s.validation.caveat}</div>}
        </State>
      </Panel>
      <div className="grid-2">
        <Panel title="US crude stocks" meta={stocks.data?.meta}>
          <State loading={stocks.isLoading && !stocks.data} error={stocks.error}><EChart height={220} option={lineOption([{ name: "Thousand barrels", points: stocks.data?.data.map((r): [string, number] => [r.date, r.value]) ?? [] }])} /></State>
        </Panel>
        <Panel title="US federal contract awards" meta={awards.data?.meta} actions={<form className="row" onSubmit={(e) => { e.preventDefault(); setWho(company); }}><input className="input" aria-label="Company" value={company} onChange={(e) => setCompany(e.target.value)} /><button className="btn">Search</button></form>}>
          <State loading={awards.isLoading && !awards.data} error={awards.error} empty={!awards.data?.data.length}><table className="t"><tbody>{awards.data?.data.map((r) => <tr key={r.id}><td className="wrap">{r.recipient}<div className="muted" style={{ fontSize: 12 }}>{r.agency}</div></td><td>{compact(r.amount, "$")}</td></tr>)}</tbody></table></State>
        </Panel>
      </div>
      <Panel title="Signal register" meta={signals.data?.meta} csv="atlas-signals" actions={<select className="input" aria-label="Filter status" value={status} onChange={(e) => setStatus(e.target.value)}><option value="all">All</option><option value="live">Live</option><option value="partial">Partial</option><option value="planned">Planned</option><option value="blocked">Blocked</option></select>}>
        <table className="t sticky"><thead><tr><th>Signal</th><th className="l">Status</th><th className="l">Method</th><th className="l">Source</th><th className="l">Frequency</th><th className="l">Limitations</th><th className="l">Confidence</th><th className="l">Validation</th><th className="l">Assets</th></tr></thead>
          <tbody>{signals.data?.data.filter((r) => status === "all" || r.status === status).map((r) => <tr key={r.id}><td>{r.name}</td><td className="l"><span className="tag">{r.status}</span></td><td className="wrap ink2">{r.method}</td><td className="l ink2">{r.source}</td><td className="l ink2">{r.frequency}</td><td className="wrap ink2">{r.limitations}</td><td className="l ink2">{r.confidence}</td><td className="wrap ink2">{r.validation}</td><td className="wrap ink2">{r.assets}</td></tr>)}</tbody></table>
      </Panel>
    </div>
  );
}
