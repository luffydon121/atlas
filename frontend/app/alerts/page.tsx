"use client";

import { useState } from "react";
import { Panel, State } from "@/components/ui";
import { send, useApi } from "@/lib/api";
import { ago, num } from "@/lib/format";

type Alert = { id: number; kind: string; target: string; threshold: number | null; label: string | null; last_fired: string | null; last_checked: string | null; last_error: string | null };
const HINT: Record<string, string> = { new_filing: "Ticker, e.g. AAPL", series_change: "Series id, e.g. us.cpi", chokepoint_drop: "any or chokepoint1", commodity_weather: "coffee, cocoa, wheat…", earthquake: "any", satellite_change: "Area id, such as whaleback" };

export default function Alerts() {
  const { data, error, isLoading, mutate } = useApi<{ alerts: Alert[]; kinds: Record<string, string> }>("/api/alerts");
  const [form, setForm] = useState({ kind: "price_above", target: "", threshold: "" });
  const [message, setMessage] = useState<string | null>(null);
  const run = (p: Promise<unknown>) => p.then(() => { setMessage(null); mutate(); }).catch((e) => setMessage(e.message));
  return (
    <div className="page">
      <section className="panel"><form className="row" style={{ padding: 8 }} onSubmit={(e) => { e.preventDefault(); run(send("/api/alerts", "POST", { kind: form.kind, target: form.target, threshold: form.threshold === "" ? null : +form.threshold })); }}>
        <select className="input" aria-label="Alert type" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>{Object.entries(data?.kinds ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        <input required className="input mono" aria-label="Target" placeholder={HINT[form.kind] ?? "Symbol, e.g. AAPL"} value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })} />
        <input type="number" step="any" className="input mono" style={{ width: 100 }} aria-label="Threshold" placeholder="Threshold" value={form.threshold} onChange={(e) => setForm({ ...form, threshold: e.target.value })} />
        <button className="btn on">Create</button>
        <button type="button" className="btn" onClick={() => send("/api/alerts/evaluate", "POST").then((r) => { setMessage(`${r.fired} alert(s) fired.`); mutate(); }).catch((e) => setMessage(e.message))}>Check now</button>
      </form>{message && <div className="notice">{message}</div>}</section>
      <Panel title="Configured alerts" style={{ flex: 1 }}>
        <State loading={isLoading} error={error} empty={!data?.alerts.length}>
          <table className="t mono"><thead><tr><th>Rule</th><th className="l">Target</th><th>Threshold</th><th>Last checked</th><th>Last fired</th><th className="l">Problem</th><th /></tr></thead>
            <tbody>{data?.alerts.map((a) => <tr key={a.id}><td>{data.kinds[a.kind]}</td><td className="l">{a.target}</td><td>{num(a.threshold)}</td><td>{ago(a.last_checked)}</td><td>{ago(a.last_fired)}</td><td className="wrap" style={{ color: "var(--serious)" }}>{a.last_error}</td><td><button className="btn" onClick={() => run(send(`/api/alerts/${a.id}`, "DELETE"))}>Delete</button></td></tr>)}</tbody></table>
        </State>
      </Panel>
    </div>
  );
}
