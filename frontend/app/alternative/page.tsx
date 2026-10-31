"use client";

import { useState } from "react";
import { EChart, lineOption } from "@/components/EChart";
import { Panel, Stat, State } from "@/components/ui";
import { useEnvelope } from "@/lib/api";
import { compact, num } from "@/lib/format";

type Signal = { id: string; name: string; status: string; method: string; uncertainty: string; validation: string };
type Attention = { article: string; stats: { available: boolean; views_7d_avg?: number; views_90d_avg?: number; z?: number; latest_date?: string; validation?: { test: string; in_sample: number; out_of_sample: number; n: number; caveat: string } }; history: { date: string; value: number }[] };

export default function Alternative() {
  const signals = useEnvelope<Signal[]>("/api/alt/signals");
  const [form, setForm] = useState({ symbol: "MSFT", article: "Microsoft" });
  const [query, setQuery] = useState(form);
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
      <Panel title="Signal register: methodology, uncertainty, validation" meta={signals.data?.meta}>
        <table className="t"><thead><tr><th>Signal</th><th className="l">Status</th><th className="l">Method</th><th className="l">Uncertainty</th><th className="l">Validation</th></tr></thead>
          <tbody>{signals.data?.data.map((r) => <tr key={r.id}><td>{r.name}</td><td className="l"><span className="tag">{r.status}</span></td><td className="wrap ink2">{r.method}</td><td className="wrap ink2">{r.uncertainty}</td><td className="wrap ink2">{r.validation}</td></tr>)}</tbody></table>
      </Panel>
    </div>
  );
}
