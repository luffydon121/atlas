"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { send, useApi, useEnvelope } from "@/lib/api";
import { ago, num, pct, tone } from "@/lib/format";
import { EChart, lineOption } from "./EChart";
import { Flash, Panel, Sparkline, State } from "./ui";

export type Quote = { symbol: string; label?: string; name?: string; price: number; change_pct: number | null; currency?: string; freshness: string; as_of: string | null; volume?: number | null; spark?: number[] };
type Watchlist = { id: number; name: string; symbols: string[] };
export type NewsRow = { title: string; url: string; publisher: string; tier: string; published_at: string | null };
type Indicator = { id: string; name: string; region: string; unit: string; latest: number; previous: number | null; period: string; history: { date: string; value: number }[] };

export const symbolHref = (s: string) => `/chart?s=${encodeURIComponent(s)}`;

export function ChangePill({ value }: { value: number | null | undefined }) {
  const cls = value == null || Math.abs(value) < 0.005 ? "flat" : value > 0 ? "up" : "down";
  return <span className={`pill ${cls}`}>{pct(value)}</span>;
}

export function QuoteRow({ q, selected, pick, draggable, ...drag }: { q: Quote; selected?: boolean; pick?: (s: string) => void; draggable?: boolean } & React.HTMLAttributes<HTMLDivElement>) {
  const inner = <>
    <span style={{ minWidth: 0 }}><b>{q.label ?? q.symbol}</b><small>{q.label ? q.symbol : q.name}</small></span>
    <Sparkline data={q.spark} up={(q.change_pct ?? 0) >= 0} />
    <span style={{ textAlign: "right" }}>
      <Flash value={q.price}><span className="mono" style={{ display: "block", fontWeight: 500 }}>{num(q.price)}</span></Flash>
      <ChangePill value={q.change_pct} />
    </span>
  </>;
  if (pick) return <div className={`qrow ${selected ? "sel" : ""}`} draggable={draggable} role="button" tabIndex={0} title={`${q.freshness}${q.as_of ? ` · ${q.as_of}` : ""}`} onClick={() => pick(q.symbol)} onKeyDown={(e) => e.key === "Enter" && pick(q.symbol)} {...drag}>{inner}</div>;
  return <Link className="qrow" href={symbolHref(q.symbol)} title={`${q.freshness}${q.as_of ? ` · ${q.as_of}` : ""}`}>{inner}</Link>;
}

export function QuoteTable({ rows, selected, onSelect }: { rows: Quote[]; selected?: string; onSelect?: (s: string) => void }) {
  return <div>{rows.map((q) => <QuoteRow key={q.symbol} q={q} selected={q.symbol === selected} pick={onSelect} />)}</div>;
}

export function WatchlistPanel({ selected, onSelect }: { selected?: string; onSelect?: (s: string) => void }) {
  const router = useRouter();
  const lists = useApi<Watchlist[]>("/api/watchlists");
  const [index, setIndex] = useState(0);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);
  const list = lists.data?.[Math.min(index, (lists.data?.length ?? 1) - 1)];
  const quotes = useEnvelope<{ quotes: Quote[]; unavailable: string[] }>(list?.symbols.length ? `/api/market/quotes?symbols=${encodeURIComponent(list.symbols.join(","))}` : null, { refreshInterval: 30_000 });
  const run = (p: Promise<unknown>) => p.then(() => { setError(null); return lists.mutate(); }).catch((e) => setError(e.message));
  const order = list?.symbols ?? [];
  const rows = order.map((s) => quotes.data?.data.quotes.find((q) => q.symbol === s)).filter((q): q is Quote => !!q);

  function drop(target: string) {
    if (!list || !dragging || dragging === target) return;
    const next = order.filter((s) => s !== dragging);
    next.splice(next.indexOf(target), 0, dragging);
    save(next);
  }

  function up(symbol: string) {
    const at = order.indexOf(symbol);
    if (at < 1) return;
    const next = [...order];
    [next[at - 1], next[at]] = [next[at], next[at - 1]];
    save(next);
  }

  function save(next: string[]) {
    if (!list) return;
    lists.mutate(lists.data?.map((w) => (w.id === list.id ? { ...w, symbols: next } : w)), { revalidate: false });
    run(send(`/api/watchlists/${list.id}/order`, "PUT", { symbols: next }));
  }

  return (
    <Panel title="Watchlist" meta={quotes.data?.meta} style={{ height: "100%" }} actions={
      <select className="input" aria-label="Choose watchlist" value={index} onChange={(e) => {
        if (e.target.value === "new") {
          const name = window.prompt("Watchlist name");
          if (name) run(send("/api/watchlists", "POST", { name }));
        } else setIndex(+e.target.value);
      }}>
        {lists.data?.map((w, i) => <option key={w.id} value={i}>{w.name}</option>)}
        <option value="new">New list…</option>
      </select>}>
      <form style={{ padding: "0 20px 12px" }} onSubmit={(e) => { e.preventDefault(); if (list && text.trim()) { run(send(`/api/watchlists/${list.id}/items`, "POST", { symbol: text.trim() })); setText(""); } }}>
        <input className="input" style={{ width: "100%" }} placeholder="Add a symbol, such as CBA.AX" value={text} onChange={(e) => setText(e.target.value)} aria-label="Add symbol" />
      </form>
      {error && <div className="notice bad">{error}</div>}
      <State loading={quotes.isLoading && !quotes.data} error={quotes.error}>
        {rows.map((q) => (
          <div key={q.symbol} style={{ position: "relative" }} className="wl">
            <QuoteRow q={q} selected={q.symbol === selected} draggable pick={onSelect ?? ((s) => router.push(symbolHref(s)))}
              onDragStart={() => setDragging(q.symbol)} onDragOver={(e) => e.preventDefault()} onDrop={() => drop(q.symbol)} onDragEnd={() => setDragging(null)} style={{ opacity: dragging === q.symbol ? 0.4 : 1 }} />
            <button className="wl-x wl-up" aria-label={`Move ${q.symbol} up`} onClick={() => up(q.symbol)}>↑</button>
            <button className="wl-x" aria-label={`Remove ${q.symbol}`} onClick={() => list && run(send(`/api/watchlists/${list.id}/items/${encodeURIComponent(q.symbol)}`, "DELETE"))}>×</button>
          </div>
        ))}
        {quotes.data?.data.unavailable.map((s) => <div key={s} className="notice muted">{s} is unavailable</div>)}
      </State>
    </Panel>
  );
}

export function MarketsPanel({ selected, onSelect }: { selected?: string; onSelect: (s: string) => void }) {
  const { data, error, isLoading } = useEnvelope<Record<string, Quote[]>>("/api/market/overview", { refreshInterval: 120_000 });
  return (
    <Panel title="Markets" meta={data?.meta} style={{ height: "100%" }}>
      <State loading={isLoading && !data} error={error}><QuoteTable rows={[...(data?.data.indices ?? []), ...(data?.data.commodities ?? []).slice(0, 5)]} selected={selected} onSelect={onSelect} /></State>
    </Panel>
  );
}

export function NewsPanel({ q, hideEmpty }: { q?: string; hideEmpty?: boolean }) {
  const [tier, setTier] = useState("");
  const [text, setText] = useState("");
  const params = new URLSearchParams();
  if (tier) params.set("tier", tier);
  if (q || text.trim()) params.set("q", text.trim() || q!);
  const { data, error, isLoading } = useEnvelope<NewsRow[]>(`/api/news?${params}`, { refreshInterval: 900_000 });
  if (hideEmpty && data && !data.data.length) return null;
  return (
    <Panel title="News" meta={data?.meta} style={{ height: "100%" }} actions={<><input className="input" style={{ width: 120 }} placeholder="Filter" aria-label="Filter headlines" value={text} onChange={(e) => setText(e.target.value)} /><select className="input" aria-label="Filter news" value={tier} onChange={(e) => setTier(e.target.value)}><option value="">All</option><option value="official">Official</option><option value="media">Media</option></select></>}>
      <State loading={isLoading && !data} error={error} empty={!data?.data.length}>
        {data?.data.map((n) => (
          <a key={n.url} href={n.url} target="_blank" rel="noreferrer noopener" style={{ display: "block", padding: "10px 20px", borderTop: "1px solid var(--line)" }}>
            <div style={{ fontWeight: 500, letterSpacing: "-0.01em" }}>{n.title}</div>
            <div className="muted" style={{ fontSize: 11 }}>{n.publisher} · {ago(n.published_at)}{n.tier === "official" && <span className="tag" style={{ marginLeft: 6 }}>official</span>}</div>
          </a>
        ))}
      </State>
    </Panel>
  );
}

export function MacroPanel({ region = "US" }: { region?: string }) {
  const { data, error, isLoading } = useEnvelope<{ indicators: Indicator[] }>(`/api/econ/dashboard?region=${encodeURIComponent(region)}`);
  return (
    <Panel title={`${region} macro`} meta={data?.meta} style={{ height: "100%" }}>
      <State loading={isLoading} error={error}>
        <table className="t mono"><tbody>
          {data?.data.indicators.map((i) => <tr key={i.id} title={`${i.unit}, ${i.period}`}><td className="ink2">{i.name}</td><td>{num(i.latest, i.latest > 1000 ? 0 : 2)}</td></tr>)}
        </tbody></table>
      </State>
    </Panel>
  );
}

export function IndicatorChart({ row, height = 150 }: { row: Indicator; height?: number }) {
  const daily = row.history.length > 1 && row.history[0].date.slice(0, 7) === row.history[1].date.slice(0, 7);
  return (
    <Panel title={row.name}>
      <div className="stat" style={{ paddingTop: 0, paddingBottom: 4 }}><div className="v">{num(row.latest, row.latest > 1000 ? 0 : 2)} <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}>{row.unit}</span></div></div>
      <EChart height={height} option={lineOption([{ name: row.name, points: row.history.map((h) => [daily ? h.date.slice(5) : h.date.slice(0, 7), h.value]) }], { compact: true })} />
    </Panel>
  );
}
