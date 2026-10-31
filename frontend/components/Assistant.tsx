"use client";

import { useEffect, useRef, useState } from "react";
import { send, useApi } from "@/lib/api";
import { ago } from "@/lib/format";
import { Markdown, Skeleton } from "./ui";

type Citation = { n: number; title: string; source: string; as_of: string | null; url: string | null };
type Answer = { answer: string; mode: string; model: string | null; warning: string | null; citations: Citation[]; tools: string[]; missing: string[] };
type Turn = { q: string; a?: Answer; error?: string };

const EXAMPLES = ["What is happening in the global oil market?", "Compare Apple and Microsoft financial performance.", "Show major drought risks affecting coffee production.", "Summarize the latest available economic indicators for Australia."];

export function Assistant({ onClose, initial }: { onClose: () => void; initial?: string | null }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const { data: status } = useApi<{ available: boolean; selected: string | null }>("/api/ai/status");
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Braces matter: newer Chrome returns a Promise here, and React would call it as a cleanup.
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);
  const asked = useRef(false);
  useEffect(() => {
    if (initial && !asked.current) {
      asked.current = true;
      send("/api/ai/ask", "POST", { question: initial }).then((a: Answer) => setTurns([{ q: initial, a }])).catch((e) => setTurns([{ q: initial, error: e.message }]));
    }
  }, [initial]);

  async function ask(q: string) {
    if (!q.trim() || busy) return;
    setText("");
    setBusy(true);
    setTurns((t) => [...t, { q }]);
    try {
      const a: Answer = await send("/api/ai/ask", "POST", { question: q });
      setTurns((t) => [...t.slice(0, -1), { q, a }]);
    } catch (e) {
      setTurns((t) => [...t.slice(0, -1), { q, error: (e as Error).message }]);
    }
    setBusy(false);
  }

  return (
    <aside className="sheet" aria-label="Assistant">
      <header className="panel-head" style={{ paddingBottom: 12, borderBottom: "1px solid var(--line)" }}><span className="panel-title">Assistant</span><span className="tag">{status?.selected ?? "Evidence mode"}</span><button className="btn" style={{ marginLeft: "auto" }} onClick={onClose}>Done</button></header>
      <div className="panel-body" style={{ padding: 16 }}>
        {!turns.length && <>
          <p className="ink2" style={{ marginTop: 0 }}>Answers come only from connected sources, with citations. {status?.selected ? "Your local model writes them up." : "No local model is running, so you see the retrieved evidence directly."}</p>
          {EXAMPLES.map((q) => <button key={q} className="btn" style={{ display: "block", width: "100%", whiteSpace: "normal", textAlign: "left", marginBottom: 6, borderRadius: 14, padding: "10px 14px" }} onClick={() => ask(q)}>{q}</button>)}
        </>}
        {turns.map((t, i) => (
          <div key={i} style={{ marginBottom: 18 }}>
            <div className="bubble">{t.q}</div>
            {t.error && <div className="notice bad" style={{ padding: 0 }}>{t.error}</div>}
            {!t.a && !t.error && <Skeleton lines={3} />}
            {t.a && <>
              {t.a.warning && <div className="notice bad" style={{ padding: "0 0 8px" }}>{t.a.warning}</div>}
              <Markdown text={t.a.answer} />
              {t.a.missing.length > 0 && <div className="notice bad" style={{ padding: "6px 0" }}>Missing: {t.a.missing.join("; ")}</div>}
              {t.a.citations.length > 0 && <ol style={{ margin: "10px 0 0", padding: 0, listStyle: "none", fontSize: 12 }}>
                {t.a.citations.map((c) => <li key={c.n} className="muted">[{c.n}] {c.url ? <a href={c.url} target="_blank" rel="noreferrer noopener" style={{ textDecoration: "underline" }}>{c.title}</a> : c.title} · {c.source}{c.as_of ? ` · ${c.as_of.includes("T") ? ago(c.as_of) : c.as_of}` : ""}</li>)}
              </ol>}
            </>}
          </div>
        ))}
        <div ref={end} />
      </div>
      <form style={{ padding: 12, borderTop: "1px solid var(--line)", display: "flex", gap: 8 }} onSubmit={(e) => { e.preventDefault(); ask(text); }}>
        <input autoFocus className="input" style={{ flex: 1, borderRadius: 18, padding: "8px 14px" }} placeholder="Ask about markets or the world" value={text} onChange={(e) => setText(e.target.value)} />
        <button className="btn on" disabled={busy}>Ask</button>
      </form>
    </aside>
  );
}
