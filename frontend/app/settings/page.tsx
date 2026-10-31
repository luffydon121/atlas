"use client";

import { useState } from "react";
import { Panel, State, Toggle } from "@/components/ui";
import { send, upload, useApi } from "@/lib/api";
import { ago } from "@/lib/format";
import { applyTheme, themeChoice, type ThemeChoice } from "@/lib/theme";

type Settings = { sec_contact_set: boolean; fred_key_set: boolean; bls_key_set: boolean; ollama: { available: boolean; models: string[]; selected: string | null }; scheduler_enabled: boolean; alert_interval_seconds: number; macos_notifications: boolean; data_dir: string; bind: string };
type Doc = { id: number; filename: string; pages: number; chunks: number; uploaded_at: string };
const yes = (v: boolean, off: string) => (v ? "Configured" : off);

export default function SettingsPage() {
  const [choice, setChoice] = useState<ThemeChoice>(themeChoice);
  const s = useApi<Settings>("/api/settings");
  const docs = useApi<Doc[]>("/api/documents");
  const d = s.data;
  const rows: [string, string][] = d ? [
    ["SEC contact (ATLAS_SEC_CONTACT)", yes(d.sec_contact_set, "Not set: limited to built-in large caps, Form 4 parsing off")],
    ["FRED key (ATLAS_FRED_API_KEY)", yes(d.fred_key_set, "Not set: GDP, retail, housing and production series off")],
    ["BLS key (ATLAS_BLS_API_KEY)", yes(d.bls_key_set, "Not set: 25 queries a day, cached to fit")],
    ["Local AI", d.ollama.available ? `Ollama running, using ${d.ollama.selected ?? "no model"}` : "Ollama not running: assistant shows retrieved evidence directly"],
    ["Background jobs", d.scheduler_enabled ? `On, alerts every ${d.alert_interval_seconds} s` : "Off"],
    ["macOS notifications", d.macos_notifications ? "On" : "Off"],
    ["Network binding", `${d.bind} (this Mac only)`],
    ["Data folder", d.data_dir],
  ] : [];
  return (
    <div className="page">
      <Panel title="Appearance"><div className="row" style={{ padding: "4px 20px 16px" }}><Toggle value={choice} options={[{ value: "system", label: "Automatic" }, { value: "light", label: "Light" }, { value: "dark", label: "Dark" }] as const} onChange={(c: ThemeChoice) => { applyTheme(c); setChoice(c); }} /></div></Panel>
      <Panel title="Configuration">
        <State loading={s.isLoading} error={s.error}><table className="t"><tbody>{rows.map(([k, v]) => <tr key={k}><td>{k}</td><td className="wrap ink2">{v}</td></tr>)}</tbody></table>
          <div className="notice">Edit the .env file in the project root, then restart ATLAS. Keys are never shown here.</div></State>
      </Panel>
      <Panel title="Document library for the assistant" actions={<label className="btn">Upload<input type="file" hidden accept=".pdf,.txt,.md,.csv" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload("/api/documents", f).then(() => docs.mutate()).catch((err) => window.alert(err.message)); e.target.value = ""; }} /></label>}>
        <State loading={docs.isLoading} error={docs.error} empty={!docs.data?.length}>
          <table className="t mono"><tbody>{docs.data?.map((x) => <tr key={x.id}><td>{x.filename}</td><td>{x.pages} pages</td><td>{x.chunks} chunks</td><td>{ago(x.uploaded_at)}</td><td><button className="btn" onClick={() => send(`/api/documents/${x.id}`, "DELETE").then(() => docs.mutate())}>Delete</button></td></tr>)}</tbody></table>
        </State>
      </Panel>
    </div>
  );
}
