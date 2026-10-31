"use client";

import { useEffect, useRef, useState } from "react";
import { Group, Panel as Pane, Separator, useDefaultLayout } from "react-resizable-panels";
import { PriceChart } from "@/components/PriceChart";
import { Panel, State } from "@/components/ui";
import { MacroPanel, NewsPanel, type Quote, QuoteTable, WatchlistPanel } from "@/components/widgets";
import { get, send, useApi, useEnvelope } from "@/lib/api";
import { useSmallScreen } from "@/lib/theme";

type Overview = Record<string, Quote[]>;
const GROUPS = [["indices", "Indices"], ["rates", "Rates & vol"], ["commodities", "Commodities"], ["fx", "FX"], ["crypto", "Crypto"], ["sectors", "Sectors"]] as const;
const DEFAULTS = { symbol: "^GSPC", left: "indices", right: "news" };
// Panel sizes are a per-browser convenience. Pages render on the server first, where no storage exists.
const panelStorage = typeof window === "undefined" ? { getItem: () => null, setItem: () => {} } : window.localStorage;

export default function Workspace() {
  const { data, error, isLoading } = useEnvelope<Overview>("/api/market/overview", { refreshInterval: 300_000 });
  const [spec, setSpec] = useState(DEFAULTS);
  const loaded = useRef(false);

  useEffect(() => {
    get("/api/layouts/dashboard").then((r) => { if (r?.spec) setSpec({ ...DEFAULTS, ...r.spec }); }).catch(() => {}).finally(() => { loaded.current = true; });
  }, []);

  const update = (patch: Partial<typeof DEFAULTS>) => {
    const next = { ...spec, ...patch };
    setSpec(next);
    if (loaded.current) send("/api/layouts/dashboard", "PUT", next).catch(() => {});
  };

  const [name, setName] = useState("");
  const saved = useApi<string[]>("/api/layouts");
  const names = (saved.data ?? []).filter((n) => n.startsWith("workspace:")).map((n) => n.slice(10));
  const saveNamed = () => {
    if (name.trim()) send(`/api/layouts/${encodeURIComponent(`workspace:${name.trim()}`)}`, "PUT", spec).then(() => { setName(""); saved.mutate(); }).catch(() => {});
  };
  const openNamed = (n: string) => get(`/api/layouts/${encodeURIComponent(`workspace:${n}`)}`).then((r) => { if (r?.spec) update({ ...DEFAULTS, ...r.spec }); }).catch(() => {});
  const main = useDefaultLayout({ id: "atlas-main", storage: panelStorage });
  const left = useDefaultLayout({ id: "atlas-left", storage: panelStorage });
  const right = useDefaultLayout({ id: "atlas-right", storage: panelStorage });
  const select = spec.symbol;
  const small = useSmallScreen();
  const left_ = <Panel title={<select className="input" aria-label="Left panel content" value={spec.left} onChange={(e) => update({ left: e.target.value })}>{GROUPS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>} meta={data?.meta} style={{ height: "100%" }}>
    <State loading={isLoading} error={error}><QuoteTable rows={data?.data[spec.left] ?? []} selected={select} onSelect={(symbol) => update({ symbol })} /></State>
  </Panel>;
  if (small) {
    return (
      <div className="page" style={{ paddingTop: 16 }}>
        <section className="panel chart-box tall"><PriceChart symbol={select} key={select} /></section>
        {left_}
        <WatchlistPanel selected={select} onSelect={(symbol) => update({ symbol })} />
        <MacroPanel />
        <div style={{ maxHeight: 420, display: "flex", flexDirection: "column" }}><NewsPanel /></div>
      </div>
    );
  }
  return (
    <div style={{ height: "calc(100dvh - 48px)", padding: 12, maxWidth: 1800, margin: "0 auto", animation: "fade .4s both", display: "flex", flexDirection: "column", gap: 8 }}>
      <div className="row"><span className="muted">Layouts</span>{names.map((n) => <button key={n} className="btn" onClick={() => openNamed(n)}>{n}</button>)}<input className="input" style={{ width: 130 }} aria-label="Layout name" placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} /><button className="btn" disabled={!name.trim()} onClick={saveNamed}>Save layout</button></div>
      <Group orientation="horizontal" id="atlas-main" {...main} style={{ flex: 1, minHeight: 0 }}>
        <Pane defaultSize="24%" minSize="14%">
          <Group orientation="vertical" id="atlas-left" {...left}>
            <Pane defaultSize="60%" minSize="20%">
              {left_}
            </Pane>
            <Separator className="resize-v" />
            <Pane minSize="15%"><MacroPanel /></Pane>
          </Group>
        </Pane>
        <Separator className="resize-h" />
        <Pane defaultSize="50%" minSize="25%">
          <section className="panel" style={{ height: "100%" }}><PriceChart symbol={select} key={select} /></section>
        </Pane>
        <Separator className="resize-h" />
        <Pane defaultSize="26%" minSize="14%">
          <Group orientation="vertical" id="atlas-right" {...right}>
            <Pane defaultSize="48%" minSize="15%"><WatchlistPanel selected={select} onSelect={(symbol) => update({ symbol })} /></Pane>
            <Separator className="resize-v" />
            <Pane minSize="15%"><NewsPanel /></Pane>
          </Group>
        </Pane>
      </Group>
    </div>
  );
}
