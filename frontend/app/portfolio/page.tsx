"use client";

import { useState } from "react";
import { EChart, lineOption } from "@/components/EChart";
import { Panel, Stat, State } from "@/components/ui";
import { send, upload, useApi, useEnvelope } from "@/lib/api";
import { num, pct, ratioPct, tone } from "@/lib/format";

type Portfolio = { id: number; name: string; kind: string; base_currency: string };
type Position = { symbol: string; quantity: number; avg_cost: number | null; currency: string; price: number | null; market_value_base: number | null; unrealised: number | null; unrealised_pct: number | null; day_change_pct: number | null; income: number; realised: number; weight: number | null; freshness: string };
type Detail = { name: string; kind: string; base_currency: string; positions: Position[]; market_value: number; cash: number | null; unrealised: number; realised: number; income: number;
  risk: { metrics: { volatility: number; sharpe: number | null; max_drawdown: number }; var_95_1d: number; beta: number; benchmark: string; curve: { date: string; portfolio: number; benchmark: number }[]; correlation: { symbols: string[]; matrix: number[][] } | null } | null;
  transactions: { id: number; ts: string; symbol: string; side: string; quantity: number; price: number; fee: number; currency: string; note: string | null }[] };

const today = () => new Date().toISOString().slice(0, 10);

export default function PortfolioPage() {
  const list = useApi<Portfolio[]>("/api/portfolios");
  const [picked, setPicked] = useState<number | null>(null);
  const id = picked ?? list.data?.[0]?.id ?? null;
  const detail = useEnvelope<Detail>(id ? `/api/portfolios/${id}` : null);
  const [tx, setTx] = useState({ ts: today(), symbol: "", side: "buy", quantity: 1, price: 0, fee: 0, currency: "USD" });
  const [order, setOrder] = useState({ symbol: "", side: "buy", quantity: 1 });
  const [error, setError] = useState<string | null>(null);
  const act = (p: Promise<unknown>) => p.then(() => { setError(null); list.mutate(); detail.mutate(); }).catch((e) => setError(e.message));
  const d = detail.data?.data;

  function create(kind: string) {
    const name = window.prompt(`${kind === "paper" ? "Paper" : "Real"} portfolio name`);
    if (name) act(send("/api/portfolios", "POST", { name, kind, base_currency: "AUD", starting_cash: kind === "paper" ? 100000 : 0 }));
  }

  return (
    <div className="page">
      <div className="row">
        <select className="input" aria-label="Portfolio" value={id ?? ""} onChange={(e) => setPicked(+e.target.value)}>{list.data?.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.kind})</option>)}</select>
        <button className="btn" onClick={() => create("real")}>New portfolio</button><button className="btn" onClick={() => create("paper")}>New paper account</button>
        {id && <label className="btn">Import CSV<input type="file" accept=".csv" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) act(upload(`/api/portfolios/${id}/import`, f)); e.target.value = ""; }} /></label>}
        <span className="muted">CSV columns: date, symbol, side, quantity, price, optional fee, currency, note. All records stay on this Mac.</span>
      </div>
      {error && <div className="notice bad" role="alert">{error}</div>}
      {!id && <div className="notice">Create a portfolio or a paper account to begin.</div>}
      {id && <State loading={detail.isLoading} error={detail.error}>
        {d && <>
          <section className="panel"><div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))" }}>
            <Stat k={`Market value (${d.base_currency})`} v={num(d.market_value)} />{d.cash !== null && <Stat k="Paper cash" v={num(d.cash)} />}<Stat k="Unrealised" v={num(d.unrealised)} cls={tone(d.unrealised)} /><Stat k="Realised" v={num(d.realised)} cls={tone(d.realised)} /><Stat k="Dividends" v={num(d.income)} />
            {d.risk && <><Stat k="Volatility" v={ratioPct(d.risk.metrics.volatility)} /><Stat k={`Beta to ${d.risk.benchmark}`} v={num(d.risk.beta)} /><Stat k="1-day 95% VaR" v={ratioPct(d.risk.var_95_1d)} /><Stat k="Max drawdown" v={ratioPct(d.risk.metrics.max_drawdown)} /></>}
          </div></section>
          <Panel title="Positions" csv="atlas-positions" meta={detail.data?.meta}><State empty={!d.positions.length}>
            <table className="t mono"><thead><tr><th>Symbol</th><th>Qty</th><th>Avg cost</th><th>Price</th><th>Day</th><th>Value ({d.base_currency})</th><th>Weight</th><th>P&L</th><th>P&L %</th><th>Income</th></tr></thead>
              <tbody>{d.positions.map((p) => <tr key={p.symbol}><td>{p.symbol} <span className="muted">{p.currency}</span></td><td>{num(p.quantity, 2)}</td><td>{num(p.avg_cost)}</td><td>{num(p.price)}</td><td className={tone(p.day_change_pct)}>{pct(p.day_change_pct)}</td><td>{num(p.market_value_base)}</td><td>{ratioPct(p.weight)}</td><td className={tone(p.unrealised)}>{num(p.unrealised)}</td><td className={tone(p.unrealised_pct)}>{ratioPct(p.unrealised_pct, 1, true)}</td><td>{num(p.income)}</td></tr>)}</tbody></table>
          </State></Panel>
          <div className="grid-2">
            <Panel title="Today's holdings over time vs benchmark">
              {d.risk ? <><EChart height={230} option={lineOption([{ name: "Holdings", points: d.risk.curve.map((c) => [c.date, +c.portfolio.toFixed(3)]) }, { name: d.risk.benchmark, points: d.risk.curve.map((c) => [c.date, +c.benchmark.toFixed(3)]) }])} /><div className="notice">Holds today&apos;s quantities constant. This shows risk, not your actual past performance.</div></> : <div className="notice muted">Needs positions with price history.</div>}
            </Panel>
            <Panel title="Add entry">
              {d.kind === "paper" && <form className="row" style={{ padding: 8 }} onSubmit={(e) => { e.preventDefault(); act(send(`/api/portfolios/${id}/paper-order`, "POST", order)); }}>
                <span className="tag">paper order</span><input required className="input mono" style={{ width: 90 }} placeholder="Symbol" value={order.symbol} onChange={(e) => setOrder({ ...order, symbol: e.target.value.toUpperCase() })} />
                <select className="input" aria-label="Order side" value={order.side} onChange={(e) => setOrder({ ...order, side: e.target.value })}><option>buy</option><option>sell</option></select>
                <input type="number" min="0" step="any" className="input mono" style={{ width: 80 }} aria-label="Order quantity" value={order.quantity} onChange={(e) => setOrder({ ...order, quantity: +e.target.value })} /><button className="btn on">Simulate fill</button>
              </form>}
              <form className="row" style={{ padding: 8 }} onSubmit={(e) => { e.preventDefault(); act(send(`/api/portfolios/${id}/transactions`, "POST", { ...tx, ts: `${tx.ts}T00:00:00` })); }}>
                <input type="date" className="input" aria-label="Date" value={tx.ts} onChange={(e) => setTx({ ...tx, ts: e.target.value })} />
                <input required className="input mono" style={{ width: 90 }} placeholder="Symbol" value={tx.symbol} onChange={(e) => setTx({ ...tx, symbol: e.target.value.toUpperCase() })} />
                <select className="input" aria-label="Side" value={tx.side} onChange={(e) => setTx({ ...tx, side: e.target.value })}>{["buy", "sell", "dividend", "deposit", "withdraw"].map((s) => <option key={s}>{s}</option>)}</select>
                {(["quantity", "price", "fee"] as const).map((k) => <label key={k} className="row muted">{k}<input type="number" min="0" step="any" className="input mono" style={{ width: 80 }} value={tx[k]} onChange={(e) => setTx({ ...tx, [k]: +e.target.value })} /></label>)}
                <input className="input mono" style={{ width: 54 }} aria-label="Currency" value={tx.currency} onChange={(e) => setTx({ ...tx, currency: e.target.value.toUpperCase() })} /><button className="btn on">Add</button>
              </form>
            </Panel>
          </div>
          <Panel title="Transactions" csv="atlas-transactions" style={{ maxHeight: 320 }}><table className="t mono"><tbody>{d.transactions.map((t) => <tr key={t.id}><td>{t.ts.slice(0, 10)}</td><td className="l">{t.side}</td><td className="l">{t.symbol}</td><td>{num(t.quantity, 2)}</td><td>{num(t.price)}</td><td>{t.currency}</td><td className="wrap muted">{t.note}</td><td><button className="btn" onClick={() => act(send(`/api/portfolios/${id}/transactions/${t.id}`, "DELETE"))}>Delete</button></td></tr>)}</tbody></table></Panel>
        </>}
      </State>}
    </div>
  );
}
