"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Fresh, Panel, Skeleton, Sparkline, Status } from "@/components/ui";
import { ChangePill, NewsPanel, type Quote, QuoteRow, symbolHref } from "@/components/widgets";
import { get, send, useEnvelope } from "@/lib/api";
import { num } from "@/lib/format";

type Signal = { severity: string; area: string; title: string; detail: string; href: string };
type Event = { date: string; title: string; region: string; confirmed: boolean };
type Today = { date: string; headline: string; markets: Quote[]; watchlist: Quote[]; signals: Signal[]; events: Event[]; sentiment: { value: number; label: string } | null; alerts: { title: string; body: string }[] };

const TILES: Record<string, { label: string; span: number }> = {
  signals: { label: "Worth a look", span: 5 }, watchlist: { label: "Movers in your watchlist", span: 4 }, events: { label: "Coming up", span: 3 }, news: { label: "News", span: 8 }, sentiment: { label: "Crypto mood", span: 4 },
};
const DEFAULT_ORDER = Object.keys(TILES);
const LEAD = ["^GSPC", "^IXIC", "^AXJO", "CL=F", "GC=F", "BTC-USD"];
const LEVEL: Record<string, string> = { serious: "elevated", warning: "watch" };

function MarketTile({ q }: { q: Quote }) {
  const up = (q.change_pct ?? 0) >= 0;
  return (
    <section className="panel lift" style={{ "--span": 2 } as React.CSSProperties}>
      <Link href={symbolHref(q.symbol)} className="tile-link market-tile">
        <span className="name">{q.label}</span>
        <Sparkline data={q.spark} up={up} width={130} height={36} />
        <span><span className="price">{num(q.price)}</span><br /><ChangePill value={q.change_pct} /></span>
      </Link>
    </section>
  );
}

function Gauge({ value, label }: { value: number; label: string }) {
  return (
    <div className="stat" style={{ paddingBottom: 20 }}>
      <div className="v" style={{ fontSize: 48 }}>{value}</div>
      <div className="s" style={{ fontSize: 14 }}>{label}, on a scale of 0 to 100</div>
      <div style={{ marginTop: 14, height: 6, borderRadius: 3, background: "linear-gradient(90deg, var(--down-fill), var(--warn), var(--up-fill))", position: "relative" }}>
        <i style={{ position: "absolute", left: `calc(${value}% - 7px)`, top: -4, width: 14, height: 14, borderRadius: "50%", background: "var(--panel)", boxShadow: "0 1px 4px rgba(0,0,0,.4)" }} />
      </div>
    </div>
  );
}

export default function TodayPage() {
  const { data, error } = useEnvelope<Today>("/api/today", { refreshInterval: 60_000 });
  const [layout, setLayout] = useState<{ order: string[]; hidden: string[] }>({ order: DEFAULT_ORDER, hidden: [] });
  const [editing, setEditing] = useState(false);
  const [dragging, setDragging] = useState<string | null>(null);
  const loaded = useRef(false);
  const d = data?.data;

  useEffect(() => {
    get("/api/layouts/today").then((r) => { if (r?.spec?.order) setLayout({ hidden: [], ...r.spec }); }).catch(() => {}).finally(() => { loaded.current = true; });
  }, []);

  const save = (next: typeof layout) => {
    setLayout(next);
    if (loaded.current) send("/api/layouts/today", "PUT", next).catch(() => {});
  };
  const drop = (target: string) => {
    if (!dragging || dragging === target) return;
    const order = layout.order.filter((k) => k !== dragging);
    order.splice(order.indexOf(target), 0, dragging);
    save({ ...layout, order });
  };

  const bodies: Record<string, React.ReactNode> = {
    signals: d?.signals.length ? d.signals.map((s, i) => (
      <Link key={i} href={s.href} className="qrow" style={{ gridTemplateColumns: "minmax(0,1fr) auto" }}><span><b>{s.title}</b><small style={{ whiteSpace: "normal" }}>{s.detail}</small></span>{LEVEL[s.severity] ? <Status value={LEVEL[s.severity]} /> : <span className="tag">{s.area}</span>}</Link>
    )) : <div className="notice muted">Nothing unusual in the connected data.</div>,
    watchlist: d?.watchlist.map((q) => <QuoteRow key={q.symbol} q={q} />),
    events: d?.events.length ? d.events.map((e) => (
      <div key={e.date + e.title} className="qrow" style={{ gridTemplateColumns: "54px minmax(0,1fr)", cursor: "default" }}>
        <span style={{ textAlign: "center" }}><small style={{ color: "var(--down)", fontWeight: 600 }}>{new Date(e.date).toLocaleDateString("en-AU", { month: "short", timeZone: "UTC" }).toUpperCase()}</small><b style={{ fontSize: 22, fontWeight: 400 }}>{new Date(e.date).getUTCDate()}</b></span>
        <span><b style={{ whiteSpace: "normal" }}>{e.title}</b><small>{e.region}{e.confirmed ? "" : " · estimate"}</small></span>
      </div>
    )) : <div className="notice muted">No scheduled events found.</div>,
    sentiment: d?.sentiment ? <Gauge {...d.sentiment} /> : <div className="notice muted">Unavailable right now.</div>,
  };

  const leads = LEAD.map((s) => d?.markets.find((m) => m.symbol === s)).filter((m): m is Quote => !!m);
  const visible = layout.order.filter((k) => TILES[k] && !layout.hidden.includes(k));
  const hidden = DEFAULT_ORDER.filter((k) => !visible.includes(k));
  const today = d ? new Date(`${d.date}T00:00:00`).toLocaleDateString("en-AU", { weekday: "long", day: "numeric", month: "long" }) : "Today";

  return (
    <>
      <div className="today-hero">
        <small>{today}</small>
        {error ? <h1 style={{ color: "var(--ink)", background: "none" }}>Markets are unavailable right now.</h1> : <h1>{d?.headline ?? " "}</h1>}
        <div className="row" style={{ marginTop: 16 }}><Fresh meta={data?.meta} /><span style={{ flex: 1 }} /><button className={`btn ${editing ? "on" : ""}`} onClick={() => setEditing(!editing)}>{editing ? "Done" : "Edit"}</button></div>
      </div>
      <div className="page">
        <div className="bento">
          {leads.length ? leads.map((q) => <MarketTile key={q.symbol} q={q} />) : !error && Array.from({ length: 6 }, (_, i) => <section key={i} className="panel" style={{ "--span": 2 } as React.CSSProperties}><Skeleton lines={3} /></section>)}
        </div>
        {editing && hidden.length > 0 && <div className="row"><span className="muted">Add back:</span>{hidden.map((k) => <button key={k} className="btn" onClick={() => save({ order: layout.order.includes(k) ? layout.order : [...layout.order, k], hidden: layout.hidden.filter((h) => h !== k) })}>{TILES[k].label}</button>)}</div>}
        <div className={`bento ${editing ? "editing" : ""}`}>
          {visible.map((k) => (
            <div key={k} style={{ "--span": TILES[k].span, position: "relative", minHeight: 0, height: k === "news" ? 420 : undefined } as React.CSSProperties} draggable={editing}
              onDragStart={() => setDragging(k)} onDragOver={(e) => e.preventDefault()} onDrop={() => drop(k)} onDragEnd={() => setDragging(null)}>
              {editing && <button className="tile-x" aria-label={`Hide ${TILES[k].label}`} onClick={() => save({ ...layout, hidden: [...layout.hidden, k] })}>×</button>}
              {k === "news" ? <NewsPanel /> : <Panel title={TILES[k].label} style={{ height: "100%" }}>{d ? bodies[k] : <Skeleton />}</Panel>}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
