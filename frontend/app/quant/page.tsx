"use client";

import { useState } from "react";
import { EChart, SERIES, axisBase, legend, lineOption, tooltip } from "@/components/EChart";
import { Panel, Stat } from "@/components/ui";
import { send, useEnvelope, type Envelope } from "@/lib/api";
import { num, ratioPct } from "@/lib/format";

type Metrics = { total_return: number; cagr: number; volatility: number; sharpe: number | null; sortino: number | null; max_drawdown: number; calmar: number | null; hit_rate: number; bars: number };
type Curve = { date: string; equity: number; benchmark: number; drawdown: number };
type Walk = { folds: { from: string; to: string; params: Record<string, number>; oos_return: number; in_sample_sharpe: number | null }[]; out_of_sample: Metrics; benchmark: Metrics };
type Result = { strategy: string; metrics: Metrics; benchmark: Metrics; trades: number; exposure: number; curve: Curve[]; walk_forward: Walk | null };
type Mc = { prob_loss: number; final_p5: number; final_p50: number; final_p95: number; median_max_drawdown: number; bands: { day: number; p5: number; p25: number; p50: number; p75: number; p95: number }[] };
type Opt = { weights: Record<string, number>; expected_return: number; volatility: number; sharpe: number; start: string; end: string };
type Factors = { alpha_annual: number; alpha_t: number; r_squared: number; n: number; betas: Record<string, { beta: number; t: number }> };

const NAMES: Record<string, string> = { buy_hold: "Buy and hold", sma_cross: "Moving average cross", momentum: "Momentum", mean_reversion: "Mean reversion" };

function MetricRow({ label, m }: { label: string; m: Metrics }) {
  return <tr><td>{label}</td><td>{ratioPct(m.total_return, 1, true)}</td><td>{ratioPct(m.cagr, 1, true)}</td><td>{ratioPct(m.volatility, 1)}</td><td>{num(m.sharpe)}</td><td>{num(m.sortino)}</td><td>{ratioPct(m.max_drawdown, 1)}</td><td>{num(m.calmar)}</td><td>{m.bars}</td></tr>;
}
const HEAD = <thead><tr><th>Series</th><th>Total</th><th>CAGR</th><th>Vol</th><th>Sharpe</th><th>Sortino</th><th>Max DD</th><th>Calmar</th><th>Bars</th></tr></thead>;

export default function Quant() {
  const strategies = useEnvelope<Record<string, Record<string, number[]>>>("/api/quant/strategies");
  const [form, setForm] = useState({ symbol: "SPY", strategy: "sma_cross", cost_bps: 10, slippage_bps: 5, walk: true, total: true });
  const [cmp, setCmp] = useState<Envelope<(Metrics & { strategy: string; p_value: number | null; survives_correction: boolean })[]> | null>(null);
  const [params, setParams] = useState<Record<string, number>>({ fast: 50, slow: 200 });
  const [res, setRes] = useState<Envelope<Result> | null>(null);
  const [mc, setMc] = useState<Envelope<Mc> | null>(null);
  const [assets, setAssets] = useState("SPY,TLT,GLD,VEA");
  const [objective, setObjective] = useState("risk_parity");
  const [opt, setOpt] = useState<Envelope<Opt> | null>(null);
  const [fac, setFac] = useState<Envelope<Factors> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const guard = async <T,>(fn: () => Promise<T>) => { setBusy(true); setError(null); try { return await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); } };
  const run = () => guard(async () => {
    setRes(await send("/api/quant/backtest", "POST", { symbol: form.symbol, strategy: form.strategy, params, cost_bps: form.cost_bps, slippage_bps: form.slippage_bps, walk_forward: form.walk, total_return: form.total }));
    setMc(await send("/api/quant/montecarlo", "POST", { symbol: form.symbol }));
  });
  const r = res?.data;
  const grid = strategies.data?.data[form.strategy] ?? {};
  return (
    <div className="page">
      <section className="panel"><div className="row" style={{ padding: 8 }}>
        <input className="input mono" style={{ width: 90 }} aria-label="Symbol" value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })} />
        <select className="input" aria-label="Strategy" value={form.strategy} onChange={(e) => { const s = e.target.value; setForm({ ...form, strategy: s }); setParams(Object.fromEntries(Object.entries(strategies.data?.data[s] ?? {}).map(([k, v]) => [k, v[v.length - 1]]))); }}>{Object.keys(strategies.data?.data ?? {}).map((s) => <option key={s} value={s}>{NAMES[s] ?? s}</option>)}</select>
        {Object.keys(grid).map((k) => <label key={k} className="row muted">{k}<input type="number" className="input mono" style={{ width: 64 }} value={params[k] ?? ""} onChange={(e) => setParams({ ...params, [k]: +e.target.value })} /></label>)}
        <label className="row muted">Cost bps<input type="number" className="input mono" style={{ width: 60 }} value={form.cost_bps} onChange={(e) => setForm({ ...form, cost_bps: +e.target.value })} /></label>
        <label className="row muted">Slippage bps<input type="number" className="input mono" style={{ width: 60 }} value={form.slippage_bps} onChange={(e) => setForm({ ...form, slippage_bps: +e.target.value })} /></label>
        <label className="row muted"><input type="checkbox" className="switch" checked={form.total} onChange={(e) => setForm({ ...form, total: e.target.checked })} />Dividends</label>
        <label className="row muted"><input type="checkbox" className="switch" checked={form.walk} onChange={(e) => setForm({ ...form, walk: e.target.checked })} />Walk-forward</label>
        <button className="btn on" disabled={busy} onClick={run}>{busy ? "Running…" : "Run backtest"}</button>
        <button className="btn" disabled={busy} onClick={() => guard(async () => setCmp(await send("/api/quant/compare", "POST", { symbol: form.symbol, cost_bps: form.cost_bps + form.slippage_bps })))}>Compare strategies</button>
        <button className="btn" disabled={busy} onClick={() => guard(async () => setFac(await send(`/api/quant/factors/${encodeURIComponent(form.symbol)}`, "GET")))}>Factor exposure</button>
      </div>{error && <div className="notice bad">{error}</div>}</section>
      {cmp && <Panel title="Strategy comparison" meta={cmp.meta}><table className="t sticky"><thead><tr><th>Strategy</th><th>CAGR</th><th>Sharpe</th><th>Max DD</th><th>p</th><th>Survives correction</th></tr></thead><tbody>{cmp.data.map((s) => <tr key={s.strategy}><td>{NAMES[s.strategy] ?? s.strategy}</td><td>{ratioPct(s.cagr, 1, true)}</td><td>{num(s.sharpe)}</td><td>{ratioPct(s.max_drawdown, 1)}</td><td>{num(s.p_value, 3)}</td><td>{s.survives_correction ? "Yes" : "No"}</td></tr>)}</tbody></table></Panel>}
      {r && <>
        <Panel title="Results" meta={res?.meta}>
          <table className="t mono">{HEAD}<tbody><MetricRow label={`${NAMES[r.strategy] ?? r.strategy} (in-sample)`} m={r.metrics} /><MetricRow label="Buy and hold" m={r.benchmark} />{r.walk_forward && <MetricRow label="Walk-forward, out-of-sample" m={r.walk_forward.out_of_sample} />}{r.walk_forward && <MetricRow label="Buy and hold, same period" m={r.walk_forward.benchmark} />}</tbody></table>
          <div className="notice">{r.trades} entries, {ratioPct(r.exposure, 0)} time in market. Judge the out-of-sample row, not the in-sample row.</div>
        </Panel>
        <div className="grid-2">
          <Panel title="Equity curve"><EChart height={260} option={lineOption([{ name: "Strategy", points: r.curve.map((c) => [c.date, +c.equity.toFixed(3)]) }, { name: "Buy and hold", points: r.curve.map((c) => [c.date, +c.benchmark.toFixed(3)]) }])} /></Panel>
          <Panel title="Drawdown"><EChart height={260} option={lineOption([{ name: "Drawdown %", points: r.curve.map((c) => [c.date, +(c.drawdown * 100).toFixed(2)]) }])} /></Panel>
        </div>
        {r.walk_forward && <Panel title="Walk-forward folds" style={{ maxHeight: 240 }}><table className="t mono"><thead><tr><th>Test from</th><th>Test to</th><th className="l">Parameters chosen on prior data</th><th>Prior Sharpe</th><th>Unseen return</th></tr></thead><tbody>{r.walk_forward.folds.map((f) => <tr key={f.from}><td>{f.from}</td><td>{f.to}</td><td className="l">{JSON.stringify(f.params)}</td><td>{num(f.in_sample_sharpe)}</td><td>{ratioPct(f.oos_return, 1, true)}</td></tr>)}</tbody></table></Panel>}
      </>}
      {mc && <Panel title="Monte Carlo, 1 year block bootstrap" meta={mc.meta}>
        <div className="grid-4"><Stat k="Chance of loss" v={ratioPct(mc.data.prob_loss, 1)} /><Stat k="5th percentile" v={ratioPct(mc.data.final_p5, 1, true)} /><Stat k="Median" v={ratioPct(mc.data.final_p50, 1, true)} /><Stat k="95th percentile" v={ratioPct(mc.data.final_p95, 1, true)} /></div>
        <EChart height={220} option={{ color: SERIES, tooltip, legend, xAxis: { type: "category", data: mc.data.bands.map((b) => b.day), ...axisBase, splitLine: { show: false } }, yAxis: { type: "value", scale: true, ...axisBase }, series: (["p95", "p75", "p50", "p25", "p5"] as const).map((k) => ({ name: k.toUpperCase(), type: "line", showSymbol: false, data: mc.data.bands.map((b) => +b[k].toFixed(3)), lineStyle: { width: k === "p50" ? 2 : 1 } })) }} />
      </Panel>}
      <div className="grid-2">
        <Panel title="Portfolio optimiser" meta={opt?.meta} actions={<><input className="input mono" aria-label="Assets" value={assets} onChange={(e) => setAssets(e.target.value)} /><select className="input" aria-label="Objective" value={objective} onChange={(e) => setObjective(e.target.value)}><option value="risk_parity">Risk parity</option><option value="min_variance">Min variance</option><option value="max_sharpe">Max Sharpe</option></select><button className="btn" disabled={busy} onClick={() => guard(async () => setOpt(await send("/api/quant/optimise", "POST", { symbols: assets.split(",").map((s) => s.trim()), objective })))}>Solve</button></>}>
          {opt ? <><div className="grid-3"><Stat k="Historical return" v={ratioPct(opt.data.expected_return)} /><Stat k="Volatility" v={ratioPct(opt.data.volatility)} /><Stat k="Sharpe" v={num(opt.data.sharpe)} /></div><table className="t mono"><tbody>{Object.entries(opt.data.weights).map(([k, v]) => <tr key={k}><td>{k}</td><td>{ratioPct(v)}</td></tr>)}</tbody></table></> : <div className="notice muted">Long-only weights from the last five years.</div>}
        </Panel>
        <Panel title="Factor exposure" meta={fac?.meta}>
          {fac ? <><div className="grid-3"><Stat k="Annual alpha" v={ratioPct(fac.data.alpha_annual)} s={`t = ${num(fac.data.alpha_t)}`} /><Stat k="R squared" v={num(fac.data.r_squared)} /><Stat k="Observations" v={fac.data.n} /></div><table className="t mono"><tbody>{Object.entries(fac.data.betas).map(([k, v]) => <tr key={k}><td>{k}</td><td>{num(v.beta)}</td><td className="muted">t = {num(v.t)}</td></tr>)}</tbody></table></> : <div className="notice muted">Regress the symbol on market, size, value and momentum ETF proxies.</div>}
        </Panel>
      </div>
    </div>
  );
}
