"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { EChart, lineOption } from "@/components/EChart";
import { Panel, Stat, State } from "@/components/ui";
import { type Quote, symbolHref } from "@/components/widgets";
import { useEnvelope } from "@/lib/api";
import { num, pct, ratioPct, tone } from "@/lib/format";

type Row = { symbol: string; name: string; sector: string; price: number; chg_1d: number; chg_1m: number | null; chg_3m: number | null; chg_1y: number | null; ytd: number | null; vol_30d: number | null; rsi: number; above_50: boolean | null; above_200: boolean | null; rel_volume: number | null; pct_from_high: number };
type Screener = { rows: Row[]; breadth: { universe: number; above_50dma: number | null; above_200dma: number | null; advancers: number; decliners: number }; unavailable: string[] };
type Compare = { series: { symbol: string; points: { date: string; value: number }[]; return: number; vol_30d: number | null }[]; correlation: { symbols: string[]; matrix: (number | null)[][] }; unavailable: string[] };

function heat(chg: number | null) {
  if (chg === null) return "var(--panel-2)";
  const a = Math.min(Math.abs(chg) / 3, 1);
  const [r, g, b] = chg >= 0 ? [47, 191, 113] : [239, 95, 87];
  return `rgba(${r},${g},${b},${0.14 + a * 0.5})`;
}

const COLUMNS: [keyof Row, string, (v: never) => string][] = [
  ["chg_1d", "1D", (v) => ratioPct(v, 2, true)], ["chg_1m", "1M", (v) => ratioPct(v, 1, true)], ["chg_3m", "3M", (v) => ratioPct(v, 1, true)], ["ytd", "YTD", (v) => ratioPct(v, 1, true)], ["chg_1y", "1Y", (v) => ratioPct(v, 1, true)],
  ["vol_30d", "Vol 30D", (v) => ratioPct(v, 0)], ["rsi", "RSI", (v) => num(v, 0)], ["rel_volume", "Rel vol", (v) => num(v, 1)], ["pct_from_high", "From high", (v) => ratioPct(v, 1)],
];

export default function Markets() {
  const router = useRouter();
  const overview = useEnvelope<Record<string, Quote[]>>("/api/market/overview");
  const screen = useEnvelope<Screener>("/api/market/screener");
  const [sort, setSort] = useState<keyof Row>("chg_1d");
  const [sector, setSector] = useState("");
  const [symbols, setSymbols] = useState("AAPL,MSFT,NVDA,^GSPC");
  const [input, setInput] = useState(symbols);
  const compare = useEnvelope<Compare>(`/api/market/compare?symbols=${encodeURIComponent(symbols)}&range=1y`);

  const rows = useMemo(() => [...(screen.data?.data.rows ?? [])].filter((r) => !sector || r.sector === sector).sort((a, b) => (Number(b[sort]) || 0) - (Number(a[sort]) || 0)), [screen.data, sort, sector]);
  const sectors = [...new Set(screen.data?.data.rows.map((r) => r.sector))].sort();
  const b = screen.data?.data.breadth;
  const corr = compare.data?.data.correlation;

  return (
    <div className="page">
      <Panel title="Sector heatmap" meta={overview.data?.meta}>
        <State loading={overview.isLoading} error={overview.error}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: 8, padding: "4px 16px 16px" }}>
            {overview.data?.data.sectors.map((q) => <div key={q.symbol} className="heat" style={{ background: heat(q.change_pct) }} onClick={() => router.push(symbolHref(q.symbol))}><span style={{ fontWeight: 600, fontSize: 13 }}>{q.label}</span><span className="mono" style={{ fontSize: 18, fontWeight: 600 }}>{pct(q.change_pct)}</span></div>)}
          </div>
        </State>
      </Panel>
      <section className="panel"><div className="grid-4">
        <Stat k={`Above 50-day average (${b?.universe ?? "—"} large caps)`} v={ratioPct(b?.above_50dma, 0)} /><Stat k="Above 200-day average" v={ratioPct(b?.above_200dma, 0)} /><Stat k="Advancers" v={b?.advancers ?? "—"} cls="up" /><Stat k="Decliners" v={b?.decliners ?? "—"} cls="down" />
      </div></section>
      <Panel title="Screener" csv="atlas-screener" meta={screen.data?.meta} style={{ maxHeight: 520 }} actions={<select className="input" aria-label="Filter sector" value={sector} onChange={(e) => setSector(e.target.value)}><option value="">All sectors</option>{sectors.map((s) => <option key={s}>{s}</option>)}</select>}>
        <State loading={screen.isLoading} error={screen.error}>
          <table className="t mono">
            <thead><tr><th>Symbol</th><th className="l">Name</th><th className="l">Sector</th><th>Price</th>{COLUMNS.map(([k, label]) => <th key={k} style={{ cursor: "pointer", color: sort === k ? "var(--accent)" : undefined }} onClick={() => setSort(k)}>{label}</th>)}</tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.symbol} style={{ cursor: "pointer" }} onClick={() => router.push(`/company?t=${r.symbol}`)}>
                <td>{r.symbol}</td><td className="l ink2">{r.name}</td><td className="l muted">{r.sector}</td><td>{num(r.price)}</td>
                {COLUMNS.map(([k, , f]) => <td key={k} className={k.startsWith("chg") || k === "ytd" ? tone(r[k] as number) : ""}>{f(r[k] as never)}</td>)}
              </tr>))}</tbody>
          </table>
        </State>
      </Panel>
      <div className="grid-2">
        <Panel title="Comparison" meta={compare.data?.meta} actions={<form className="row" onSubmit={(e) => { e.preventDefault(); setSymbols(input.replace(/\s/g, "").toUpperCase()); }}><input className="input" style={{ width: 200 }} aria-label="Symbols to compare" value={input} onChange={(e) => setInput(e.target.value)} /><button className="btn">Compare</button></form>}>
          <State loading={compare.isLoading} error={compare.error}>
            <EChart height={280} option={lineOption((compare.data?.data.series ?? []).map((s) => ({ name: s.symbol, points: s.points.map((p) => [p.date, +p.value.toFixed(2)]) })))} />
          </State>
        </Panel>
        <Panel title="Correlation of daily returns">
          <State loading={compare.isLoading} error={compare.error}>
            {corr && <table className="t mono"><thead><tr><th />{corr.symbols.map((s) => <th key={s}>{s}</th>)}</tr></thead>
              <tbody>{corr.symbols.map((s, i) => <tr key={s}><td>{s}</td>{corr.matrix[i].map((v, j) => <td key={j} style={{ background: v === null ? undefined : v >= 0 ? `rgba(57,135,229,${v * 0.55})` : `rgba(217,89,38,${-v * 0.55})` }}>{num(v)}</td>)}</tr>)}</tbody></table>}
          </State>
        </Panel>
      </div>
    </div>
  );
}
