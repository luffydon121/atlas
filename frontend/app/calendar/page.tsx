"use client";

import { Panel, State } from "@/components/ui";
import { useEnvelope } from "@/lib/api";

type Event = { date: string; title: string; region: string; kind: string; confirmed: boolean; url: string | null; ticker?: string };

function when(iso: string) {
  return new Date(iso).toLocaleDateString("en-AU", { weekday: "short", day: "numeric", month: "long", timeZone: "UTC" });
}

export default function CalendarPage() {
  const { data, error, isLoading } = useEnvelope<{ events: Event[]; unavailable: string[] }>("/api/calendar");
  const months = [...new Set(data?.data.events.map((e) => e.date.slice(0, 7)))];
  return (
    <div className="page">
      <State loading={isLoading && !data} error={error} empty={!data?.data.events.length}>
        {months.map((m) => (
          <Panel key={m} title={new Date(`${m}-01`).toLocaleDateString("en-AU", { month: "long", year: "numeric", timeZone: "UTC" })}>
            <table className="t"><tbody>{data?.data.events.filter((e) => e.date.startsWith(m)).map((e) => (
              <tr key={e.date + e.title}><td style={{ width: 180 }}>{when(e.date)}</td><td className="l">{e.url ? <a href={e.url} target="_blank" rel="noreferrer noopener">{e.title}</a> : e.title}</td><td className="l muted">{e.region}</td><td><span className="tag">{e.confirmed ? "Official" : "Estimate"}</span></td></tr>
            ))}</tbody></table>
          </Panel>
        ))}
      </State>
      <div className="notice" style={{ padding: 0 }}>{data?.meta.note} Earnings cover companies in your watchlists.{data?.data.unavailable.length ? ` Unavailable: ${data.data.unavailable.join(", ")}.` : ""}</div>
    </div>
  );
}
