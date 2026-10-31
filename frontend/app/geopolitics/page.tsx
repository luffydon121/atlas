"use client";

import { useState } from "react";
import { Panel, State, Toggle } from "@/components/ui";
import { useEnvelope } from "@/lib/api";

type Event = { title: string; url: string; publisher: string; theme: string; tier: string; time: string | null; place: string | null };
const TIERS = ["all", "official", "automated"] as const;

export default function Geopolitics() {
  const [tier, setTier] = useState<(typeof TIERS)[number]>("all");
  const { data, error, isLoading } = useEnvelope<{ events: Event[]; unavailable: string[] }>("/api/geo/events", { refreshInterval: 1_800_000 });
  const rows = data?.data.events.filter((e) => tier === "all" || e.tier === tier) ?? [];
  return (
    <div className="page">
      <div className="row"><Toggle value={tier} options={TIERS} onChange={setTier} />{data?.data.unavailable.length ? <span className="muted">Rate limited or unavailable: {data.data.unavailable.join(", ")}. Cached results return when it recovers.</span> : null}</div>
      <Panel title="Global events" meta={data?.meta} style={{ flex: 1 }}>
        <State loading={isLoading} error={error} empty={!rows.length}>
          <table className="t"><thead><tr><th>Tier</th><th className="l">Theme</th><th className="l">Headline</th><th className="l">Place named</th><th className="l">Publisher</th><th>Date</th></tr></thead>
            <tbody>{rows.map((e) => <tr key={e.url}><td className="l"><span className="tag" style={e.tier === "official" ? { color: "var(--accent)", borderColor: "var(--accent)" } : undefined}>{e.tier === "official" ? "official" : "unverified"}</span></td><td className="l muted">{e.theme.replace("_", " ")}</td><td className="wrap"><a href={e.url} target="_blank" rel="noreferrer noopener">{e.title}</a></td><td className="l ink2">{e.place ?? "—"}</td><td className="l muted">{e.publisher}</td><td className="mono muted">{e.time?.slice(0, 10)}</td></tr>)}</tbody></table>
        </State>
      </Panel>
    </div>
  );
}
