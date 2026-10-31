"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { EChart, SERIES, axisBase, legend, tooltip } from "@/components/EChart";
import { PriceChart } from "@/components/PriceChart";
import { Panel, Stat, State, Toggle } from "@/components/ui";
import { NewsPanel } from "@/components/widgets";
import { get, send, useEnvelope, type Envelope } from "@/lib/api";
import { compact, num, pct, ratioPct, tone } from "@/lib/format";

type Row = Record<string, number | string | null>;
type Company = {
  ticker: string; name: string; cik: number; industry: string; exchanges: string[]; fiscal_year_end: string; website: string;
  quote: { price: number; change_pct: number; currency: string; freshness: string } | null; shares: { value: number; as_of: string } | null;
  multiples: Record<string, number | null>; annual: Row[]; ratios: Row[]; dividends: { time: number; amount: number }[]; splits: { time: number; ratio: string }[];
  earnings: { past: { date: string; url: string }[]; next_estimate: string | null; estimate_passed: boolean };
};
type Filing = { form: string; filed: string; description: string; url: string; accession: string };
type Insider = { transactions: { owner: string; title: string | null; date: string; code: string; shares: number | null; price: number | null; acquired_disposed: string; url: string }[]; filings: Filing[] };
type Dcf = { per_share: number; market_price: number | null; upside: number | null; enterprise_value: number; terminal_share_of_ev: number; assumptions: string[]; inputs: { base_fcf: number; net_debt: number; shares: number };
  scenarios: { label: string; growth: number; discount_rate: number; per_share: number }[]; sensitivity: { discount_rates: number[]; terminal_growths: number[]; per_share: (number | null)[][] } };

const STATEMENTS: Record<string, [string, string][]> = {
  Income: [["revenue", "Revenue"], ["cost_of_revenue", "Cost of revenue"], ["gross_profit", "Gross profit"], ["rnd", "R&D"], ["operating_income", "Operating income"], ["net_income", "Net income"], ["eps_diluted", "Diluted EPS"]],
  Balance: [["assets", "Total assets"], ["current_assets", "Current assets"], ["cash", "Cash & equivalents"], ["liabilities", "Total liabilities"], ["current_liabilities", "Current liabilities"], ["long_term_debt", "Long-term debt"], ["short_term_debt", "Short-term debt"], ["equity", "Shareholders' equity"]],
  "Cash flow": [["cfo", "Operating cash flow"], ["capex", "Capital expenditure"], ["dividends_paid", "Dividends paid"], ["buybacks", "Share buybacks"], ["depreciation", "Depreciation & amortisation"]],
};
const RATIOS: [string, string, (v: number | null) => string][] = [["revenue_growth", "Revenue growth", (v) => ratioPct(v, 1, true)], ["net_income_growth", "Earnings growth", (v) => ratioPct(v, 1, true)], ["gross_margin", "Gross margin", ratioPct], ["operating_margin", "Operating margin", ratioPct], ["net_margin", "Net margin", ratioPct], ["fcf_margin", "FCF margin", ratioPct], ["roe", "Return on equity", ratioPct], ["roa", "Return on assets", ratioPct], ["debt_to_equity", "Debt / equity", (v) => num(v)], ["current_ratio", "Current ratio", (v) => num(v)], ["free_cash_flow", "Free cash flow", (v) => compact(v, "$")]];

function DcfPanel({ ticker }: { ticker: string }) {
  const [form, setForm] = useState({ growth: 8, terminal_growth: 2.5, discount_rate: 9, years: 10 });
  const [result, setResult] = useState<Envelope<Dcf> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const run = () => send("/api/company/dcf/run", "POST", { ticker, growth: form.growth / 100, terminal_growth: form.terminal_growth / 100, discount_rate: form.discount_rate / 100, years: form.years }).then((r) => { setResult(r); setError(null); }).catch((e) => setError(e.message));
  const d = result?.data;
  return (
    <Panel title="Discounted cash flow (estimate)" meta={result?.meta}>
      <div className="row" style={{ padding: 8 }}>
        {([["growth", "FCF growth %"], ["terminal_growth", "Terminal %"], ["discount_rate", "Discount %"], ["years", "Years"]] as const).map(([k, l]) => <label key={k} className="row muted">{l}<input type="number" step="0.5" className="input mono" style={{ width: 64 }} value={form[k]} onChange={(e) => setForm({ ...form, [k]: +e.target.value })} /></label>)}
        <button className="btn on" onClick={run}>Run DCF</button>
      </div>
      {error && <div className="notice bad">{error}</div>}
      {d && <>
        <div className="grid-4"><Stat k="Estimated value per share" v={num(d.per_share)} /><Stat k="Market price" v={num(d.market_price)} /><Stat k="Implied gap" v={ratioPct(d.upside, 1, true)} cls={tone(d.upside)} /><Stat k="Terminal share of EV" v={ratioPct(d.terminal_share_of_ev, 0)} /></div>
        <div className="grid-2">
          <table className="t mono"><thead><tr><th>Scenario</th><th>Growth</th><th>Discount</th><th>Per share</th></tr></thead><tbody>{d.scenarios.map((s) => <tr key={s.label}><td>{s.label}</td><td>{ratioPct(s.growth)}</td><td>{ratioPct(s.discount_rate)}</td><td>{num(s.per_share)}</td></tr>)}</tbody></table>
          <table className="t mono"><thead><tr><th>Discount \ terminal</th>{d.sensitivity.terminal_growths.map((g) => <th key={g}>{ratioPct(g)}</th>)}</tr></thead><tbody>{d.sensitivity.discount_rates.map((r, i) => <tr key={r}><td>{ratioPct(r)}</td>{d.sensitivity.per_share[i].map((v, j) => <td key={j}>{num(v, 0)}</td>)}</tr>)}</tbody></table>
        </div>
        <div className="notice">Assumptions: {d.assumptions.join(". ")}. Base FCF {compact(d.inputs.base_fcf, "$")}, net debt {compact(d.inputs.net_debt, "$")}, shares {compact(d.inputs.shares)}.</div>
      </>}
    </Panel>
  );
}

function Compare({ ticker }: { ticker: string }) {
  const [peers, setPeers] = useState("MSFT,GOOGL");
  const [input, setInput] = useState(peers);
  const list = [ticker, ...peers.split(",").filter((x) => x && x !== ticker)].join(",");
  const { data, error, isLoading } = useEnvelope<Row[]>(`/api/company?tickers=${encodeURIComponent(list)}`);
  return (
    <Panel title="Competitor comparison" meta={data?.meta} actions={<form className="row" onSubmit={(e) => { e.preventDefault(); setPeers(input.replace(/\s/g, "").toUpperCase()); }}><input className="input" aria-label="Peer tickers" value={input} onChange={(e) => setInput(e.target.value)} /><button className="btn">Set peers</button></form>}>
      <State loading={isLoading} error={error}>
        <table className="t mono"><thead><tr><th>Ticker</th><th>Mkt cap</th><th>Revenue</th><th>Growth</th><th>Op margin</th><th>Net margin</th><th>ROE</th><th>P/E</th><th>EV/EBITDA</th><th>FCF yield</th></tr></thead>
          <tbody>{data?.data.map((r) => r.available ? <tr key={String(r.ticker)}><td>{r.ticker}</td><td>{compact(r.market_cap as number, "$")}</td><td>{compact(r.revenue as number, "$")}</td><td>{ratioPct(r.revenue_growth as number, 1, true)}</td><td>{ratioPct(r.operating_margin as number)}</td><td>{ratioPct(r.net_margin as number)}</td><td>{ratioPct(r.roe as number)}</td><td>{num(r.pe as number, 1)}</td><td>{num(r.ev_ebitda as number, 1)}</td><td>{ratioPct(r.fcf_yield as number)}</td></tr> : <tr key={String(r.ticker)}><td>{r.ticker}</td><td colSpan={9} className="muted">No SEC data</td></tr>)}</tbody></table>
      </State>
    </Panel>
  );
}

export default function CompanyPage() {
  const params = useSearchParams();
  const router = useRouter();
  const ticker = (params.get("t") ?? "AAPL").toUpperCase();
  const [input, setInput] = useState(ticker);
  const [tab, setTab] = useState("Income");
  const { data, error, isLoading } = useEnvelope<Company>(`/api/company/${encodeURIComponent(ticker)}`);
  const filings = useEnvelope<Filing[]>(`/api/company/${encodeURIComponent(ticker)}/filings`);
  const insiders = useEnvelope<Insider>(`/api/company/${encodeURIComponent(ticker)}/insiders`);
  const [report, setReport] = useState<string | null>(null);
  const c = data?.data;
  const m = c?.multiples ?? {};
  const periods = c?.annual ?? [];

  return (
    <div className="page">
      <form className="row" onSubmit={(e) => { e.preventDefault(); router.push(`/company?t=${encodeURIComponent(input.trim().toUpperCase())}`); }}>
        <input className="input mono" aria-label="Ticker" value={input} onChange={(e) => setInput(e.target.value)} style={{ width: 110 }} /><button className="btn">Load</button>
        {c && <><b style={{ fontSize: 22, marginLeft: 8, letterSpacing: "-0.02em" }}>{c.name}</b><span className="muted">{c.industry} · {c.exchanges?.join(", ")} · CIK {c.cik}</span>
          <button type="button" className="btn" style={{ marginLeft: "auto" }} onClick={() => get(`/api/ai/report/${ticker}`).then((r) => setReport(r.markdown)).catch((e) => setReport(`Report unavailable: ${e.message}`))}>Research report</button></>}
      </form>
      <State loading={isLoading} error={error}>
        {c && <>
          {report && <Panel title="Research report" actions={<button className="btn" onClick={() => setReport(null)}>Close</button>}><pre className="notice" style={{ whiteSpace: "pre-wrap", margin: 0, fontFamily: "inherit" }}>{report}</pre></Panel>}
          <section className="panel"><div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(118px, 1fr))" }}>
            <Stat k="Price" v={num(c.quote?.price)} s={<span className={tone(c.quote?.change_pct)}>{pct(c.quote?.change_pct)} · {c.quote?.freshness}</span>} /><Stat k="Market cap" v={compact(m.market_cap, "$")} s={c.shares ? `shares ${c.shares.as_of}` : undefined} /><Stat k="EV" v={compact(m.enterprise_value, "$")} /><Stat k="P/E" v={num(m.pe, 1)} /><Stat k="P/S" v={num(m.ps, 1)} /><Stat k="P/B" v={num(m.pb, 1)} /><Stat k="EV/EBITDA" v={num(m.ev_ebitda, 1)} /><Stat k="FCF yield" v={ratioPct(m.fcf_yield)} /><Stat k="Dividend yield" v={ratioPct(m.dividend_yield, 2)} />
          </div></section>
          <div className="grid-2">
            <section className="panel" style={{ height: 340 }}><PriceChart symbol={ticker} compact key={ticker} /></section>
            <Panel title="Revenue and net income" meta={data?.meta} style={{ height: 340 }}>
              <EChart height={300} option={{ color: SERIES, tooltip, legend, xAxis: { type: "category", data: periods.map((p) => String(p.period_end).slice(0, 4)), ...axisBase, splitLine: { show: false } }, yAxis: { type: "value", ...axisBase, axisLabel: { ...axisBase.axisLabel, formatter: (v: number) => compact(v) } },
                series: [["Revenue", "revenue"], ["Net income", "net_income"]].map(([name, k]) => ({ name, type: "bar", barGap: "10%", barMaxWidth: 16, itemStyle: { borderRadius: [2, 2, 0, 0] }, data: periods.map((p) => p[k]) })) }} />
            </Panel>
          </div>
          <Panel title="Financial statements" csv={`${ticker}-statements`} actions={<Toggle value={tab} options={[...Object.keys(STATEMENTS), "Ratios"]} onChange={setTab} />}>
            <table className="t mono">
              <thead><tr><th>Fiscal year end</th>{periods.map((p) => <th key={String(p.period_end)}>{String(p.period_end)}</th>)}</tr></thead>
              <tbody>
                {tab === "Ratios" ? RATIOS.map(([k, l, f]) => <tr key={k}><td className="ink2">{l}</td>{c.ratios.map((r, i) => <td key={i}>{f(r[k] as number | null)}</td>)}</tr>)
                  : STATEMENTS[tab].map(([k, l]) => <tr key={k}><td className="ink2">{l}</td>{periods.map((p, i) => <td key={i}>{k === "eps_diluted" ? num(p[k] as number) : compact(p[k] as number, "$")}</td>)}</tr>)}
              </tbody>
            </table>
          </Panel>
          <DcfPanel ticker={ticker} />
          <Compare ticker={ticker} />
          <div className="grid-3">
            <Panel title="Filings" meta={filings.data?.meta} style={{ height: 320 }}>
              <table className="t"><tbody>{filings.data?.data.map((f) => <tr key={f.accession}><td><a href={f.url} target="_blank" rel="noreferrer noopener" style={{ textDecoration: "underline" }}>{f.form}</a></td><td className="wrap ink2">{f.description && f.description !== f.form ? f.description : ""}</td><td className="mono muted">{f.filed}</td></tr>)}</tbody></table>
            </Panel>
            <Panel title="Insider disclosures" meta={insiders.data?.meta} style={{ height: 320 }}>
              {insiders.data?.data.transactions.length ? <table className="t mono"><tbody>{insiders.data.data.transactions.map((t, i) => <tr key={i}><td>{t.date}</td><td className="l ink2">{t.owner}</td><td>{t.code}</td><td>{compact(t.shares)}</td><td>{num(t.price)}</td></tr>)}</tbody></table>
                : <table className="t"><tbody>{insiders.data?.data.filings.map((f) => <tr key={f.accession}><td><a href={f.url} target="_blank" rel="noreferrer noopener" style={{ textDecoration: "underline" }}>Form {f.form}</a></td><td className="mono muted">{f.filed}</td></tr>)}</tbody></table>}
            </Panel>
            <Panel title="Earnings and dividends" style={{ height: 320 }}>
              <div className="notice">Next results date (<b>estimate</b>, last + 91 days): <span className="mono">{c.earnings.next_estimate ?? "—"}</span>{c.earnings.estimate_passed ? " — this date has passed, so results may already be out." : ""}</div>
              <table className="t mono"><thead><tr><th>Results 8-K</th></tr></thead><tbody>{c.earnings.past.map((p) => <tr key={p.date}><td><a href={p.url} target="_blank" rel="noreferrer noopener">{p.date}</a></td></tr>)}</tbody></table>
              <table className="t mono"><thead><tr><th>Dividend date</th><th>Amount</th></tr></thead><tbody>{c.dividends.slice(-8).reverse().map((d) => <tr key={d.time}><td>{new Date(d.time * 1000).toISOString().slice(0, 10)}</td><td>{num(d.amount, 3)}</td></tr>)}</tbody></table>
            </Panel>
          </div>
          <div style={{ maxHeight: 340, display: "flex", flexDirection: "column" }}><NewsPanel hideEmpty q={c.name.split(" ")[0]} /></div>
        </>}
      </State>
    </div>
  );
}
