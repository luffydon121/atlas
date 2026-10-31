"use client";

import { useState } from "react";
import { Panel, State } from "@/components/ui";
import { useEnvelope } from "@/lib/api";
import { compact, ratioPct } from "@/lib/format";

type Position = { issuer: string; cusip: string; title: string; value: number; shares: number; put_call: string | null; change?: number; change_pct?: number | null };
type Filing = { form: string; filed: string; period: string; accession: string; url: string };
type Data = { name: string; filings: Filing[]; positions: Position[]; changes: Record<"added" | "removed" | "increased" | "reduced", Position[]> | null; blocked: string | null };

function Change({ title, rows }: { title: string; rows: Position[] }) {
  return <Panel title={title}><State empty={!rows.length}><table className="t"><tbody>{rows.map((r) => <tr key={r.cusip + r.put_call}><td className="wrap">{r.issuer}{r.put_call ? ` (${r.put_call})` : ""}</td><td>{compact(r.change ?? r.shares)}</td><td>{ratioPct(r.change_pct, 0, true)}</td></tr>)}</tbody></table></State></Panel>;
}

export default function Holdings() {
  const filers = useEnvelope<{ cik: number; name: string }[]>("/api/holdings/filers");
  const [cik, setCik] = useState(1067983);
  const { data, error, isLoading } = useEnvelope<Data>(`/api/holdings/${cik}`);
  const d = data?.data;
  return (
    <div className="page">
      <div className="row"><select className="input" aria-label="Institution" value={cik} onChange={(e) => setCik(+e.target.value)}>{filers.data?.data.map((f) => <option key={f.cik} value={f.cik}>{f.name}</option>)}</select></div>
      <State loading={isLoading && !data} error={error}>
        {d && <>
          {d.blocked && <section className="panel"><div className="notice"><b style={{ color: "var(--ink)" }}>Add your SEC contact to see positions.</b> {d.blocked} SEC refuses these files without one. The filing list below works now.</div></section>}
          {d.positions.length > 0 && <Panel title={`Largest reported positions, ${d.filings[0]?.period}`} csv="atlas-13f" meta={data?.meta} style={{ maxHeight: 460 }}>
            <table className="t sticky"><thead><tr><th>Issuer</th><th className="l">Class</th><th>Value</th><th>Shares</th></tr></thead><tbody>{d.positions.map((p) => <tr key={p.cusip + p.put_call}><td className="wrap">{p.issuer}{p.put_call ? ` (${p.put_call})` : ""}</td><td className="l muted">{p.title}</td><td>{compact(p.value, "$")}</td><td>{compact(p.shares)}</td></tr>)}</tbody></table>
          </Panel>}
          {d.changes && <div className="grid-2"><Change title="New positions" rows={d.changes.added} /><Change title="Sold out" rows={d.changes.removed} /><Change title="Increased" rows={d.changes.increased} /><Change title="Reduced" rows={d.changes.reduced} /></div>}
          <Panel title={`${d.name}: filing history`} meta={data?.meta}><table className="t"><thead><tr><th>Quarter end</th><th>Filed</th><th className="l">Form</th><th /></tr></thead><tbody>{d.filings.map((f) => <tr key={f.accession}><td>{f.period}</td><td>{f.filed}</td><td className="l">{f.form}</td><td><a href={f.url} target="_blank" rel="noreferrer noopener" style={{ textDecoration: "underline" }}>Open</a></td></tr>)}</tbody></table></Panel>
        </>}
      </State>
    </div>
  );
}
