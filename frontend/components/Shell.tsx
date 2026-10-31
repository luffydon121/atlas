"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { get, send, useApi } from "@/lib/api";
import { ago } from "@/lib/format";
import { GROUPS, NAV } from "@/lib/nav";
import { applyTheme } from "@/lib/theme";
import { Assistant } from "./Assistant";
import { warm } from "./Providers";
import { Icon } from "./ui";

type SearchRow = { symbol: string; name: string; exchange: string; type: string };
type Notifications = { unread: number; items: { id: number; title: string; body: string; severity: string; created_at: string }[] };
type Recent = { label: string; sub: string; href: string };
const RECENT_KEY = "atlas-recent";

function destination(row: SearchRow) {
  return row.type === "EQUITY" ? `/company?t=${encodeURIComponent(row.symbol)}` : `/chart?s=${encodeURIComponent(row.symbol)}`;
}

function readRecent(): Recent[] {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function Spotlight({ onClose, onAsk }: { onClose: () => void; onAsk: (q: string) => void }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<SearchRow[]>([]);
  const [cursor, setCursor] = useState(0);
  const [recent] = useState(readRecent);
  const text = q.trim().toLowerCase();

  useEffect(() => {
    if (!text) return;
    let live = true;
    const t = setTimeout(() => get(`/api/search?q=${encodeURIComponent(text)}`).then((r) => live && setRows(r.data)).catch(() => {}), 120);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [text]);

  const pages = text ? NAV.filter((n) => n.label.toLowerCase().includes(text)).map((p) => ({ key: p.href, label: p.label, sub: p.desc, href: p.href })) : [];
  const symbols = text ? rows.map((r) => ({ key: r.symbol, label: `${r.symbol}  ${r.name}`, sub: `${r.type} ${r.exchange}`, href: destination(r) })) : [];
  const history = text ? [] : recent.map((r) => ({ ...r, key: r.href }));
  const ask = text.length > 8 ? [{ key: "ask", label: `Ask the assistant: ${q.trim()}`, sub: "Cited answer", href: "" }] : [];
  const items = [...pages, ...symbols, ...history, ...ask];

  function go(item: (typeof items)[number]) {
    onClose();
    if (!item.href) return onAsk(q.trim());
    try {
      localStorage.setItem(RECENT_KEY, JSON.stringify([{ label: item.label, sub: item.sub, href: item.href }, ...recent.filter((r) => r.href !== item.href)].slice(0, 6)));
    } catch {
      /* Recent searches are a convenience. */
    }
    router.push(item.href);
  }

  return (
    <div className="spot-wrap" onClick={onClose}>
      <div className="spot" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Search">
        <input autoFocus placeholder="Search any ticker, company or page" value={q}
          onChange={(e) => { setQ(e.target.value); setCursor(0); }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setCursor(Math.min(cursor + 1, items.length - 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setCursor(Math.max(cursor - 1, 0)); }
            if (e.key === "Enter" && items[cursor]) go(items[cursor]);
            if (e.key === "Escape") onClose();
          }} />
        {(items.length > 0 || !text) && <div className="spot-list">
          {!text && <div className="muted" style={{ padding: "6px 14px", fontSize: 12 }}>{recent.length ? "Recent" : "Press g then a letter to jump to any page. Press ⌘J for the assistant."}</div>}
          {items.map((item, i) => (
            <button key={item.key} className={`spot-item ${i === cursor ? "on" : ""}`} onClick={() => go(item)} onMouseEnter={() => setCursor(i)}>
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.label}</span><span className="muted" style={{ whiteSpace: "nowrap" }}>{item.sub}</span>
            </button>
          ))}
        </div>}
      </div>
    </div>
  );
}

function Bell() {
  const [open, setOpen] = useState(false);
  const { data, mutate } = useApi<Notifications>("/api/notifications", { refreshInterval: 60_000 });
  return (
    <span style={{ position: "relative" }}>
      <button className="icon-btn" aria-label="Notifications" onClick={() => { setOpen(!open); if (!open && data?.unread) send("/api/notifications/read", "POST").then(() => mutate()).catch(() => {}); }}>{Icon.bell}{!!data?.unread && <span className="dot">{data.unread}</span>}</button>
      {open && <div className="pop">
        {data?.items.length ? data.items.map((n) => <div key={n.id} className="notice" style={{ borderBottom: "1px solid var(--line)" }}><b style={{ color: "var(--ink)" }}>{n.title}</b><div>{n.body}</div><div className="muted">{ago(n.created_at)}</div></div>) : <div className="notice muted">No notifications yet. Create a rule in Alerts.</div>}
      </div>}
    </span>
  );
}

function FullBleed(path: string) {
  return path === "/" || path === "/map" || path === "/workspace";
}

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [search, setSearch] = useState(false);
  const [ai, setAi] = useState(false);
  const [question, setQuestion] = useState<string | null>(null);
  const [menu, setMenu] = useState(false);
  const [fly, setFly] = useState<string | null>(null);
  const prefix = useRef(0);
  const flyTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const page = NAV.find((n) => n.href === path);

  const hover = (group: string | null) => {
    clearTimeout(flyTimer.current);
    flyTimer.current = setTimeout(() => setFly(group), group ? 90 : 160);
  };

  const onKey = useCallback((e: KeyboardEvent) => {
    const typing = /INPUT|TEXTAREA|SELECT/.test((e.target as HTMLElement).tagName);
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setSearch((v) => !v); return; }
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "j") { e.preventDefault(); setAi((v) => !v); return; }
    if (e.key === "Escape") { setFly(null); return; }
    if (typing || e.metaKey || e.ctrlKey) return;
    if (e.key === "/") { e.preventDefault(); setSearch(true); return; }
    if (Date.now() - prefix.current < 900) {
      const hit = NAV.find((n) => n.key === e.key);
      if (hit) router.push(hit.href);
      prefix.current = 0;
    } else if (e.key === "g") prefix.current = Date.now();
  }, [router]);

  useEffect(() => {
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onKey]);

  const items = NAV.filter((n) => n.group === fly);
  return (
    <>
      <header className="gnav" onMouseLeave={() => hover(null)}>
        <div className="gnav-in">
          <button className="icon-btn menu-btn" aria-label="Open menu" onClick={() => setMenu(!menu)}>{Icon.menu}</button>
          <Link href="/" className="logo" onMouseEnter={() => hover(null)}>ATLAS</Link>
          <nav aria-label="Modules" className={`gnav-links ${menu ? "open" : ""}`} style={{ display: menu ? undefined : "flex" }} onClick={() => setMenu(false)}>
            <Link href="/" className={`gnav-link ${path === "/" ? "on" : ""}`} onMouseEnter={() => hover(null)}>Today</Link>
            {GROUPS.map((g) => menu ? (
              <div key={g} style={{ margin: "10px 0" }}><div className="muted" style={{ fontSize: 12 }}>{g}</div>{NAV.filter((n) => n.group === g).map((n) => <Link key={n.href} href={n.href} style={{ display: "block", padding: "5px 0", fontSize: 19, fontWeight: 600 }}>{n.label}</Link>)}</div>
            ) : (
              <Link key={g} href={NAV.find((n) => n.group === g)!.href} className={`gnav-link ${page?.group === g ? "on" : ""}`} onMouseEnter={() => hover(g)} onFocus={() => hover(g)}>{g}</Link>
            ))}
            <Link href="/sources" className={`gnav-link ${page?.group === "System" ? "on" : ""}`} onMouseEnter={() => hover("System")}>{menu ? "Sources and settings" : "System"}</Link>
          </nav>
          <div className="gnav-right">
            <button className="icon-btn" aria-label="Search" onClick={() => setSearch(true)}>{Icon.search}</button>
            <Bell />
            <button className="icon-btn" aria-label="Switch theme" onClick={() => applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark")}><span className="only-dark">{Icon.sun}</span><span className="only-light">{Icon.moon}</span></button>
            <button className="icon-btn" aria-label="Assistant" onClick={() => setAi(!ai)}>{Icon.spark}</button>
          </div>
        </div>
        {fly && items.length > 0 && <div className="flyout" onMouseEnter={() => clearTimeout(flyTimer.current)} onClick={() => setFly(null)}>
          <div className="flyout-in">
            {items.map((n) => <Link key={n.href} href={n.href} onMouseEnter={() => warm(n.preload)}><b>{n.label}</b><span>{n.desc}</span></Link>)}
          </div>
        </div>}
      </header>
      {fly && <div className="scrim" onMouseEnter={() => setFly(null)} />}
      {page && !FullBleed(path) && <div className="hero" key={path}><h1>{page.tagline}</h1></div>}
      <main key={path}>{children}</main>
      {ai && <Assistant onClose={() => setAi(false)} initial={question} />}
      {search && <Spotlight onClose={() => setSearch(false)} onAsk={(q) => { setQuestion(q); setAi(true); }} />}
    </>
  );
}
