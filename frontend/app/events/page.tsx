"use client";

import { useState } from "react";
import { EChart, lineOption } from "@/components/EChart";
import { Panel, Stat, State } from "@/components/ui";
import { send, useEnvelope, type Envelope } from "@/lib/api";
import { num, ratioPct, tone } from "@/lib/format";

type Row = { date: string; requested: string; raw_return: number; car: number; beta: number };
type Study = { n: number; skipped: string[]; before: number; after: number; market_adjusted: boolean; mean_car: number | null; median_car: number | null; positive: number; t_stat: number | null; p_value: number | null; events: Row[]; mean_path: { day: number; value: number }[] };
type Sets = { events: { date: string; title: string; rules: string[] }[]; sets: Record<string, string> };
type Regime = { current: string; current_vol: number; regimes: Record<string, { days: number; mean_next_month: number }>; series: { date: string; vol: number }[] };
type Stress = { name: string; start: string; end: string; portfolio: number | null; missing: string[]; weight_covered: number };

export default function EventLab() {
  const sets = useEnvelope<Sets>("/api/quant/analogues");
  const [form, setForm] = useState({ symbol: "XOM", benchmark: "SPY", before: 5, after: 10 });
  const [preset, setPreset] = useState("gulf_energy");
  const [dates, setDates] = useState("");
  const [result, setResult] = useState<Envelope<Study> | null>(null);
  const [regimeFor, setRegimeFor] = useState("SPY");
  const regime = useEnvelope<Regime>(`/api/quant/regimes/${encodeURIComponent(regimeFor)}`);
  const [pair, setPair] = useState({ a: "SPY", b: "TLT", window: 63 });
  const rolling = useEnvelope<{ date: string; value: number }[]>(`/api/quant/rolling?a=${encodeURIComponent(pair.a)}&b=${encodeURIComponent(pair.b)}&window=${pair.window}`);
  const [weights, setWeights] = useState("SPY:60, TLT:40");
  const [stress, setStress] = useState<Envelope<Stress[]> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const chosen = sets.data?.data.events.filter((e) => e.rules.includes(preset)).map((e) => e.date) ?? [];

  async function run() {
    setBusy(true);
    setError(null);
    try {
      const list = dates.trim() ? dates.split(/[\s,]+/).filter(Boolean) : chosen;
      setResult(await send("/api/quant/eventstudy", "POST", { symbol: form.symbol, dates: list, before: form.before, after: form.after, benchmark: form.benchmark || null }));
    } catch (e) {
      setError((e as Error).message);
    }
    setBusy(false);
  }

  const replay = () => {
    const parsed = Object.fromEntries(weights.split(",").map((p) => { const [s, w] = p.split(":"); return [s.trim().toUpperCase(), Number(w)]; }));
    send("/api/quant/stress", "POST", { weights: parsed }).then(setStress).catch((e) => setError(e.message));
  };

  const r = result?.data;
  return (
    <div className="page">
      <Panel title="Event study">
        <div className="row" style={{ padding: "4px 20px 14px" }}>
          <label className="row muted">Asset<input className="input" style={{ width: 96 }} value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })} /></label>
          <label className="row muted">Benchmark<input className="input" style={{ width: 90 }} placeholder="None" value={form.benchmark} onChange={(e) => setForm({ ...form, benchmark: e.target.value.toUpperCase() })} /></label>
          <label className="row muted">Before<input type="number" className="input" style={{ width: 66 }} value={form.before} onChange={(e) => setForm({ ...form, before: +e.target.value })} /></label>
          <label className="row muted">After<input type="number" className="input" style={{ width: 66 }} value={form.after} onChange={(e) => setForm({ ...form, after: +e.target.value })} /></label>
          <select className="input" aria-label="Event set" value={preset} onChange={(e) => setPreset(e.target.value)}>{Object.entries(sets.data?.data.sets ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
          <input className="input" style={{ flex: 1, minWidth: 180 }} aria-label="Custom dates" placeholder="Or your own dates: 2024-01-15, 2024-03-20" value={dates} onChange={(e) => setDates(e.target.value)} />
          <button className="btn on" disabled={busy} onClick={run}>{busy ? "Measuring…" : "Run study"}</button>
        </div>
        {error && <div className="notice bad">{error}</div>}
        {r && <>
          <div className="stat-row"><Stat k="Events measured" v={r.n} s={r.skipped.length ? `${r.skipped.length} without history` : undefined} /><Stat k="Mean move" v={ratioPct(r.mean_car, 1, true)} cls={tone(r.mean_car)} s={r.market_adjusted ? "Against the benchmark" : "Raw"} /><Stat k="Median" v={ratioPct(r.median_car, 1, true)} /><Stat k="Rose" v={`${r.positive} of ${r.n}`} /><Stat k="t-statistic" v={num(r.t_stat)} s={r.p_value !== null ? `p = ${num(r.p_value, 3)}` : "Needs 3 events"} /></div>
          <EChart height={240} option={lineOption([{ name: "Mean cumulative %", points: r.mean_path.map((p): [string, number] => [String(p.day), +(p.value * 100).toFixed(2)]) }])} />
          <table className="t"><thead><tr><th>Event day</th><th>Total return</th><th>Against expected</th><th>Beta</th></tr></thead><tbody>{r.events.map((e) => <tr key={e.date}><td>{e.date}</td><td className={tone(e.raw_return)}>{ratioPct(e.raw_return, 1, true)}</td><td className={tone(e.car)}>{ratioPct(e.car, 1, true)}</td><td>{num(e.beta)}</td></tr>)}</tbody></table>
          <div className="panel-foot">{result?.meta.note}</div>
        </>}
      </Panel>
      <div className="grid-2">
        <Panel title="Volatility regime" meta={regime.data?.meta} actions={<input className="input" style={{ width: 96 }} aria-label="Regime symbol" defaultValue="SPY" onBlur={(e) => setRegimeFor(e.target.value.toUpperCase())} />}>
          <State loading={regime.isLoading && !regime.data} error={regime.error}>{regime.data && <>
            <div className="stat-row"><Stat k="Current state" v={<span style={{ textTransform: "capitalize" }}>{regime.data.data.current}</span>} /><Stat k="21-day volatility" v={ratioPct(regime.data.data.current_vol, 1)} /></div>
            <EChart height={190} option={lineOption([{ name: "Volatility %", points: regime.data.data.series.map((s): [string, number] => [s.date, +(s.vol * 100).toFixed(1)]) }])} />
          </>}</State>
        </Panel>
        <Panel title="Rolling correlation" meta={rolling.data?.meta} actions={<><input className="input" style={{ width: 80 }} aria-label="First symbol" defaultValue="SPY" onBlur={(e) => setPair({ ...pair, a: e.target.value.toUpperCase() })} /><input className="input" style={{ width: 80 }} aria-label="Second symbol" defaultValue="TLT" onBlur={(e) => setPair({ ...pair, b: e.target.value.toUpperCase() })} /></>}>
          <State loading={rolling.isLoading && !rolling.data} error={rolling.error}><EChart height={250} option={lineOption([{ name: `${pair.window}-day correlation`, points: rolling.data?.data.map((p): [string, number] => [p.date, +p.value.toFixed(2)]) ?? [] }])} /></State>
        </Panel>
      </div>
      <Panel title="Portfolio stress test" meta={stress?.meta} actions={<><input className="input" aria-label="Weights" value={weights} onChange={(e) => setWeights(e.target.value)} /><button className="btn" onClick={replay}>Replay</button></>}>
        {stress ? <table className="t"><thead><tr><th>Period</th><th>From</th><th>To</th><th>Change</th><th className="l">Without history</th></tr></thead><tbody>{stress.data.map((s) => <tr key={s.name}><td>{s.name}</td><td>{s.start}</td><td>{s.end}</td><td className={tone(s.portfolio)}>{ratioPct(s.portfolio, 1, true)}</td><td className="l muted">{s.missing.join(", ")}</td></tr>)}</tbody></table> : <div className="notice muted">Enter symbols and weights, then replay five real market shocks.</div>}
      </Panel>
    </div>
  );
}
