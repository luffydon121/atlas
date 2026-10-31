"use client";

import { Panel, Stat, State, Status } from "@/components/ui";
import { send, useApi, useEnvelope } from "@/lib/api";
import { ago, compact, ratioPct } from "@/lib/format";

type Row = { id: string; provider: string; domain: string; url: string; state: string; freshness: string; age_seconds: number | null; last_success: string | null; last_error: string | null; success_rate: number | null; reliability: string; licence: string; redistribution: string; limitations: string };
type Quality = { summary: Record<string, number>; sources: Row[]; stale_after: string };
type Job = { name: string; label: string; every_seconds: number; running: boolean; next_in_seconds: number | null; last_status: string | null; last_started: string | null; last_error: string | null; recent: string[] };
type Jobs = { scheduler_running: boolean; jobs: Job[] };
type Storage = { schema_version: string; database_bytes: number; backup_count: number; latest_backup: string | null; tables: Record<string, number>; restore_hint: string };
const STATE: Record<string, string> = { fresh: "ok", stale: "watch", degraded: "degraded", failing: "down", unused: "idle" };
const JOB: Record<string, string> = { ok: "ok", failed: "down", timeout: "degraded", interrupted: "watch", running: "idle" };
const every = (s: number) => (s >= 86400 ? `${Math.round(s / 86400)} d` : s >= 3600 ? `${Math.round(s / 3600)} h` : `${Math.round(s / 60)} min`);

export default function QualityPage() {
  const { data, error, isLoading } = useEnvelope<Quality>("/api/quality", { refreshInterval: 30_000 });
  const jobs = useApi<Jobs>("/api/system/jobs", { refreshInterval: 15_000 });
  const storage = useApi<Storage>("/api/system/storage");
  const s = data?.data.summary;
  return (
    <div className="page">
      <section className="panel"><div className="stat-row"><Stat k="Fresh" v={s?.fresh ?? "—"} /><Stat k="Stale" v={s?.stale ?? "—"} /><Stat k="Degraded" v={s?.degraded ?? "—"} /><Stat k="Failing" v={s?.failing ?? "—"} /><Stat k="Not used yet" v={s?.unused ?? "—"} /></div></section>
      <Panel title="Sources" meta={data?.meta} csv="atlas-sources">
        <State loading={isLoading && !data} error={error}>
          <table className="t sticky"><thead><tr><th>Provider</th><th className="l">State</th><th className="l">Reliability</th><th>Last success</th><th>Success</th><th className="l">Redistribution</th><th className="l">Limitations</th></tr></thead>
            <tbody>{data?.data.sources.map((r) => <tr key={r.id} title={r.last_error ?? r.licence}><td>{r.url ? <a href={r.url} target="_blank" rel="noreferrer noopener" style={{ textDecoration: "underline" }}>{r.provider}</a> : r.provider}</td><td className="l"><Status value={STATE[r.state] ?? "idle"} /></td><td className="l" style={{ textTransform: "capitalize" }}>{r.reliability}</td><td>{ago(r.last_success)}</td><td>{ratioPct(r.success_rate, 0)}</td><td className="wrap ink2">{r.redistribution}</td><td className="wrap ink2">{r.limitations}</td></tr>)}</tbody></table>
        </State>
      </Panel>
      {!jobs.error && <Panel title="Background jobs" actions={jobs.data && !jobs.data.scheduler_running ? <span className="tag">Off</span> : undefined}>
        <table className="t sticky"><thead><tr><th>Job</th><th>Every</th><th className="l">Last</th><th>Started</th><th className="l">History</th><th /></tr></thead>
          <tbody>{jobs.data?.jobs.map((j) => <tr key={j.name} title={j.last_error ?? undefined}><td>{j.label}</td><td>{every(j.every_seconds)}</td><td className="l">{j.running ? "Running" : j.last_status ? <Status value={JOB[j.last_status] ?? "idle"} /> : "Not run"}</td><td>{ago(j.last_started)}</td><td className="l mono muted">{j.recent.map((r) => (r === "ok" ? "●" : "○")).join("")}</td><td><button className="btn" disabled={j.running || !jobs.data?.scheduler_running} onClick={() => send(`/api/system/jobs/${j.name}/run`, "POST").then(() => jobs.mutate()).catch(() => {})}>Run now</button></td></tr>)}</tbody></table>
      </Panel>}
      {!storage.error && storage.data && <Panel title="Storage" actions={<button className="btn" onClick={() => send("/api/system/backup", "POST").then(() => storage.mutate()).catch(() => {})}>Back up now</button>}>
        <div className="stat-row"><Stat k="Database" v={compact(storage.data.database_bytes)} s="bytes" /><Stat k="Backups" v={storage.data.backup_count} s={storage.data.latest_backup ?? "None yet"} /><Stat k="Schema" v={storage.data.schema_version} /></div>
        <table className="t"><tbody>{Object.entries(storage.data.tables).map(([k, v]) => <tr key={k}><td>{k.replace(/_/g, " ")}</td><td>{v.toLocaleString()}</td></tr>)}</tbody></table>
        <div className="panel-foot">{storage.data.restore_hint} Automatic clean-up only removes expired caches and old job history.</div>
      </Panel>}
    </div>
  );
}
