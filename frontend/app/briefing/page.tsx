"use client";

import { useState } from "react";
import { Markdown, Panel, Skeleton, State, Toggle } from "@/components/ui";
import { send, useApi, useEnvelope } from "@/lib/api";
import { ago } from "@/lib/format";

type Row = { id: number | null; kind: string; subject: string | null; title: string; created_at: string; markdown?: string };
const KINDS = [{ value: "daily", label: "Daily" }, { value: "weekly", label: "Weekly" }, { value: "asset", label: "Asset" }, { value: "country", label: "Country" }, { value: "commodity", label: "Commodity" }] as const;
const HINT: Record<string, string> = { asset: "Symbol, such as XOM", country: "US, Australia or Euro area", commodity: "Oil, gold or coffee" };

export default function BriefingPage() {
  const latest = useEnvelope<Row>("/api/briefings/latest");
  const list = useApi<Row[]>("/api/briefings", { shouldRetryOnError: false });
  const [kind, setKind] = useState<(typeof KINDS)[number]["value"]>("daily");
  const [subject, setSubject] = useState("");
  const [picked, setPicked] = useState<number | null>(null);
  const [custom, setCustom] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const opened = useApi<Row>(picked ? `/api/briefings/${picked}` : null);
  const shown = custom ?? opened.data ?? latest.data?.data;

  async function generate() {
    setBusy(true);
    setError(null);
    try {
      setCustom(await send("/api/briefings", "POST", { kind, subject: subject || null }));
      setPicked(null);
      list.mutate();
    } catch (e) {
      setError((e as Error).message);
    }
    setBusy(false);
  }

  return (
    <div className="page">
      <section className="panel no-print"><div className="row" style={{ padding: 14 }}>
        <Toggle value={kind} options={KINDS} onChange={setKind} />
        {HINT[kind] && <input className="input" aria-label="Subject" placeholder={HINT[kind]} value={subject} onChange={(e) => setSubject(e.target.value)} />}
        <button className="btn on" disabled={busy} onClick={generate}>{busy ? "Writing…" : "Generate"}</button>
      </div>{error && <div className="notice bad">{error}</div>}</section>
      <div className="impact-grid reverse">
        <Panel title={shown?.title ?? "Briefing"} actions={shown?.id ? <span className="row no-print"><a className="btn" href={`/api/briefings/${shown.id}/export?format=md`}>Markdown</a><a className="btn" href={`/api/briefings/${shown.id}/export?format=html`} target="_blank" rel="noreferrer">HTML</a><button className="btn" onClick={() => window.print()}>Print or PDF</button></span> : undefined}>
          <div style={{ padding: "4px 20px 20px" }}><State loading={latest.isLoading && !shown} error={shown ? undefined : latest.error}>{shown?.markdown ? <Markdown text={shown.markdown} /> : <Skeleton />}</State></div>
        </Panel>
        {!!list.data?.length && <Panel title="Saved briefings" className="no-print impact-feed">{list.data.map((b) => <button key={b.id} className={`feed-item ${b.id === shown?.id ? "sel" : ""}`} onClick={() => { setCustom(null); setPicked(b.id); }}><b>{b.title}</b><span className="feed-meta">{ago(b.created_at)}</span></button>)}</Panel>}
      </div>
    </div>
  );
}
