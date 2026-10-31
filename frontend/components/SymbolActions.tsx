"use client";

import { useState } from "react";
import { send, useApi } from "@/lib/api";

type Watchlist = { id: number; name: string; symbols: string[] };

export function SymbolActions({ symbol, price }: { symbol: string; price?: number }) {
  const lists = useApi<Watchlist[]>("/api/watchlists");
  const [open, setOpen] = useState(false);
  const [level, setLevel] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const first = lists.data?.[0];
  const watched = !!first?.symbols.includes(symbol);

  async function toggle() {
    if (!first) return;
    if (watched) await send(`/api/watchlists/${first.id}/items/${encodeURIComponent(symbol)}`, "DELETE");
    else await send(`/api/watchlists/${first.id}/items`, "POST", { symbol });
    lists.mutate();
  }

  async function alert(kind: "price_above" | "price_below") {
    try {
      await send("/api/alerts", "POST", { kind, target: symbol, threshold: Number(level || price) });
      setNote(`Alert set for ${symbol}.`);
      setTimeout(() => { setOpen(false); setNote(null); }, 1200);
    } catch (e) {
      setNote((e as Error).message);
    }
  }

  return (
    <span className="row" style={{ position: "relative", gap: 4 }}>
      <button className={`btn ${watched ? "on" : ""}`} aria-pressed={watched} aria-label={watched ? `Remove ${symbol} from watchlist` : `Add ${symbol} to watchlist`} onClick={() => toggle().catch(() => {})}>{watched ? "★" : "☆"}</button>
      <button className="btn" onClick={() => setOpen(!open)}>Alert</button>
      {open && <div className="pop" style={{ width: 240, top: 38, padding: 14 }}>
        <label className="muted" style={{ fontSize: 12 }}>Alert when {symbol} crosses
          <input className="input" type="number" step="any" inputMode="decimal" style={{ width: "100%", marginTop: 4 }} placeholder={price?.toFixed(2)} value={level} onChange={(e) => setLevel(e.target.value)} />
        </label>
        <div className="row" style={{ marginTop: 8 }}><button className="btn" onClick={() => alert("price_above")}>Rises above</button><button className="btn" onClick={() => alert("price_below")}>Falls below</button></div>
        {note && <div className="muted" style={{ marginTop: 6, fontSize: 12 }}>{note}</div>}
      </div>}
    </span>
  );
}
