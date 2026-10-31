"use client";

import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import type { Meta } from "@/lib/api";
import { ago, toCsv } from "@/lib/format";

const COLORS: Record<string, string> = {
  live: "var(--up-fill)", delayed: "var(--warn)", historical: "var(--muted)", estimated: "#7d7aff", reference: "var(--muted)", unavailable: "var(--down-fill)",
};

export function Fresh({ meta, freshness }: { meta?: Meta; freshness?: string }) {
  const f = freshness ?? meta?.freshness;
  if (!f) return null;
  const title = meta ? `${meta.source.join(", ")}${meta.as_of ? ` · as of ${meta.as_of}` : ""} · updated ${ago(meta.fetched_at)}` : undefined;
  return <span className="badge" title={title}><i style={{ background: meta?.stale ? "var(--serious)" : COLORS[f] }} />{meta?.stale ? "stale" : f}</span>;
}

export function Panel({ title, meta, actions, children, className, style, csv }: { title: ReactNode; meta?: Meta; actions?: ReactNode; children: ReactNode; className?: string; style?: React.CSSProperties; csv?: string }) {
  const body = useRef<HTMLDivElement>(null);
  function download() {
    const table = body.current?.querySelector("table");
    if (!table) return;
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([toCsv(table)], { type: "text/csv" }));
    link.download = `${csv}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }
  return (
    <section className={`panel ${className ?? ""}`} style={style}>
      <header className="panel-head">
        <span className="panel-title">{title}</span>
        <Fresh meta={meta} />
        <span style={{ marginLeft: "auto" }} className="row">{actions}{csv && <button className="btn" onClick={download}>Export</button>}</span>
      </header>
      <div className="panel-body" ref={body} tabIndex={csv || style?.maxHeight ? 0 : undefined}>{children}</div>
      {meta?.note && <footer className="panel-foot">{meta.note}</footer>}
    </section>
  );
}

export function Skeleton({ lines = 4 }: { lines?: number }) {
  return <div className="skel" aria-label="Loading" role="status">{Array.from({ length: lines }, (_, i) => <i key={i} />)}</div>;
}

export function State({ loading, error, empty, children }: { loading?: boolean; error?: Error; empty?: boolean; children?: ReactNode }) {
  if (error) return <div className="notice bad" role="alert">Unavailable right now. {error.message}</div>;
  if (loading) return <Skeleton />;
  if (empty) return <div className="notice muted">Nothing to show yet.</div>;
  return <>{children}</>;
}

export function Stat({ k, v, s, cls }: { k: string; v: ReactNode; s?: ReactNode; cls?: string }) {
  return <div className="stat"><div className="k">{k}</div><div className={`v ${cls ?? ""}`}>{v}</div>{s !== undefined && <div className="s">{s}</div>}</div>;
}

export function Toggle<T extends string>({ value, options, onChange }: { value: T; options: readonly (T | { value: T; label: string })[]; onChange: (v: T) => void }) {
  const host = useRef<HTMLSpanElement>(null);
  const [thumb, setThumb] = useState({ x: 0, w: 0 });
  useLayoutEffect(() => {
    const active = host.current?.querySelector<HTMLElement>("button.on");
    if (!active) return;
    const measure = () => setThumb({ x: active.offsetLeft, w: active.offsetWidth });
    measure();
    document.fonts?.ready.then(measure);
  }, [value, options.length]);
  return (
    <span className="seg" ref={host}>
      <span className="seg-thumb" style={{ width: thumb.w, transform: `translateX(${thumb.x}px)` }} />
      {options.map((o) => {
        const v = typeof o === "string" ? o : o.value;
        return <button key={v} className={v === value ? "on" : ""} aria-pressed={v === value} onClick={() => onChange(v)}>{typeof o === "string" ? o : o.label}</button>;
      })}
    </span>
  );
}

const STATUS: Record<string, [string, string]> = {
  normal: ["●", "var(--up)"], watch: ["▲", "var(--warn)"], elevated: ["■", "var(--down)"], unknown: ["○", "var(--muted)"],
  ok: ["●", "var(--up)"], degraded: ["▲", "var(--warn)"], down: ["■", "var(--down)"], idle: ["○", "var(--muted)"], not_configured: ["○", "var(--muted)"],
};

export function Status({ value }: { value: string }) {
  const [icon, color] = STATUS[value] ?? ["○", "var(--muted)"];
  return <span className="badge" style={{ color: "var(--ink-2)" }}><span style={{ color, fontSize: 9 }}>{icon}</span>{value.replace("_", " ")}</span>;
}

export function Sparkline({ data, up, width = 72, height = 30, fluid }: { data?: number[]; up?: boolean; width?: number; height?: number; fluid?: boolean }) {
  if (!data || data.length < 2) return <svg width={width} height={height} aria-hidden />;
  const lo = Math.min(...data), hi = Math.max(...data), span = hi - lo || 1;
  const pts = data.map((v, i) => `${((i / (data.length - 1)) * width).toFixed(1)},${(height - 2 - ((v - lo) / span) * (height - 4)).toFixed(1)}`);
  const color = up === undefined ? "var(--muted)" : up ? "var(--up-fill)" : "var(--down-fill)";
  return <svg width={fluid ? "100%" : width} height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden style={{ display: "block", overflow: "visible" }}><polyline points={pts.join(" ")} fill="none" stroke={color} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" /></svg>;
}

export function Flash({ value, children }: { value: number | null | undefined; children: ReactNode }) {
  const [state, setState] = useState({ last: value, cls: "", tick: 0 });
  if (value !== state.last) setState({ last: value, cls: value != null && state.last != null ? (value > state.last ? "flash-up" : "flash-down") : "", tick: state.tick + 1 });
  return <span key={state.tick} className={state.cls} style={{ borderRadius: 6 }}>{children}</span>;
}

export function Markdown({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let items: string[] = [];
  const flush = (key: number) => {
    if (items.length) blocks.push(<ul key={`list-${key}`} style={{ margin: "0 0 6px", padding: 0 }}>{items.map((item, i) => <li key={i}>{item}</li>)}</ul>);
    items = [];
  };
  text.split("\n").forEach((line, i) => {
    if (line.startsWith("- ")) {
      items.push(line.slice(2));
      return;
    }
    flush(i);
    const bold = line.match(/^\*\*(.+?)\*\*(.*)$/);
    if (line.startsWith("# ")) blocks.push(<h2 key={i} style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.02em", margin: "0 0 8px" }}>{line.slice(2)}</h2>);
    else if (line.startsWith("## ")) blocks.push(<h3 key={i} style={{ fontSize: 17, fontWeight: 600, margin: "18px 0 6px" }}>{line.slice(3)}</h3>);
    else if (bold) blocks.push(<p key={i} style={{ marginTop: 8 }}><b>{bold[1]}</b> <span className="muted">{bold[2]}</span></p>);
    else if (line) blocks.push(<p key={i}>{line}</p>);
  });
  flush(-1);
  return <div className="answer">{blocks}</div>;
}

export const Icon = {
  search: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden><circle cx="7" cy="7" r="5" /><path d="m11 11 3.5 3.5" strokeLinecap="round" /></svg>,
  bell: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden><path d="M8 1.8a4 4 0 0 0-4 4c0 4-1.6 5-1.6 5h11.2S12 9.8 12 5.8a4 4 0 0 0-4-4ZM6.6 13.4a1.5 1.5 0 0 0 2.8 0" strokeLinejoin="round" /></svg>,
  spark: <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden><path d="M8 1l1.5 4.5L14 7l-4.5 1.5L8 13 6.5 8.5 2 7l4.5-1.5L8 1Zm5 9 .7 1.8 1.8.7-1.8.7L13 15l-.7-1.8-1.8-.7 1.8-.7L13 10Z" /></svg>,
  sun: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" aria-hidden><circle cx="8" cy="8" r="3" /><path d="M8 1.5v1.6M8 12.9v1.6M1.5 8h1.6M12.9 8h1.6M3.4 3.4l1.1 1.1M11.5 11.5l1.1 1.1M3.4 12.6l1.1-1.1M11.5 4.5l1.1-1.1" /></svg>,
  moon: <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden><path d="M13.6 10.3A6 6 0 0 1 5.7 2.4a6 6 0 1 0 7.9 7.9Z" /></svg>,
  menu: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden><path d="M2 5h12M2 11h12" /></svg>,
};
