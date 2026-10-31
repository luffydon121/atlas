"use client";

import { Panel, State, Status } from "@/components/ui";
import { useEnvelope } from "@/lib/api";
import { ago, ratioPct } from "@/lib/format";

type Source = { id: string; provider: string; domain: string; licence: string; coverage: string; refresh: string; limitations: string; freshness: string; quality: string; url: string; state: string; last_success: string | null; last_error: string | null; success_rate: number | null };

export default function Sources() {
  const { data, error, isLoading } = useEnvelope<Source[]>("/api/sources", { refreshInterval: 30_000 });
  return (
    <div className="page">
      <Panel title="Source registry" meta={data?.meta} style={{ flex: 1 }}>
        <State loading={isLoading} error={error}>
          <table className="t"><thead><tr><th>Provider</th><th className="l">Status</th><th className="l">Domain</th><th className="l">Quality</th><th className="l">Refresh</th><th>Last success</th><th>Success</th><th className="l">Coverage</th><th className="l">Licence</th><th className="l">Limitations</th></tr></thead>
            <tbody>{data?.data.map((s) => <tr key={s.id} title={s.last_error ?? undefined}><td>{s.url ? <a href={s.url} target="_blank" rel="noreferrer noopener" style={{ textDecoration: "underline" }}>{s.provider}</a> : s.provider}</td><td className="l"><Status value={s.state} /></td><td className="l muted">{s.domain}</td><td className="l"><span className="tag">{s.quality}</span></td><td className="l muted">{s.refresh}</td><td className="mono">{ago(s.last_success)}</td><td className="mono">{ratioPct(s.success_rate, 0)}</td><td className="wrap ink2">{s.coverage}</td><td className="wrap ink2">{s.licence}</td><td className="wrap ink2">{s.limitations}</td></tr>)}</tbody></table>
        </State>
      </Panel>
    </div>
  );
}
