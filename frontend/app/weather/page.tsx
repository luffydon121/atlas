"use client";

import { useState } from "react";
import { Panel, State, Status, Toggle } from "@/components/ui";
import { PriceChart } from "@/components/PriceChart";
import { useEnvelope } from "@/lib/api";
import { num } from "@/lib/format";

type Region = { region: string; production_weight: number; stats: { available: boolean; rain_mm?: number; rain_normal_mm?: number; rain_pct_of_normal?: number; rain_z?: number; temp_c?: number; temp_normal_c?: number; temp_z?: number; window_end?: string }; forecast: { frost_days: number; heat_days: number }; risk: { level: string; drivers: string[] } };
type Risk = { commodity: string; ticker: string; overall: string; regions: Region[]; regions_unavailable: number };
type Alert = { event: string; area: string; severity: string; headline: string };
const LIST = ["coffee", "cocoa", "wheat", "corn", "soybeans", "natural_gas"];

export default function Weather() {
  const [c, setC] = useState("coffee");
  const { data, error, isLoading } = useEnvelope<Risk>(`/api/weather/commodity/${c}`);
  const alerts = useEnvelope<Alert[]>("/api/hazards/us-alerts");
  const d = data?.data;
  return (
    <div className="page">
      <div className="row"><Toggle value={c} options={LIST.map((v) => ({ value: v, label: v.replace("_", " ") }))} onChange={setC} />{d && <Status value={d.overall} />}</div>
      <Panel title="Growing-region weather screen" meta={data?.meta}>
        <State loading={isLoading} error={error}>
          <table className="t mono">
            <thead><tr><th>Region</th><th>Weight</th><th>Rain 30d</th><th>Normal</th><th>% normal</th><th>Rain z</th><th>Temp</th><th>Normal</th><th>Temp z</th><th>Frost days</th><th>Heat days</th><th className="l">Screen</th><th className="l">Drivers</th></tr></thead>
            <tbody>{d?.regions.map((r) => <tr key={r.region}><td>{r.region}</td><td>{num(r.production_weight * 100, 0)}%</td><td>{num(r.stats.rain_mm, 0)}</td><td>{num(r.stats.rain_normal_mm, 0)}</td><td>{num(r.stats.rain_pct_of_normal, 0)}</td><td>{num(r.stats.rain_z)}</td><td>{num(r.stats.temp_c, 1)}</td><td>{num(r.stats.temp_normal_c, 1)}</td><td>{num(r.stats.temp_z)}</td><td>{r.forecast.frost_days}</td><td>{r.forecast.heat_days}</td><td className="l"><Status value={r.risk.level} /></td><td className="wrap ink2">{r.risk.drivers.join("; ")}</td></tr>)}</tbody>
          </table>
          {!!d?.regions_unavailable && <div className="notice bad">{d.regions_unavailable} region(s) unavailable right now, probably rate limited. Retry shortly.</div>}
        </State>
      </Panel>
      <div className="grid-2">
        <section className="panel" style={{ height: 340 }}>{d && <PriceChart symbol={d.ticker} compact key={d.ticker} />}</section>
        <Panel title="US severe weather alerts" meta={alerts.data?.meta} style={{ height: 340 }}>
          <State loading={alerts.isLoading} error={alerts.error} empty={!alerts.data?.data.length}>
            <table className="t"><tbody>{alerts.data?.data.map((a, i) => <tr key={i}><td className="l">{a.event}</td><td className="wrap ink2">{a.area}</td><td>{a.severity}</td></tr>)}</tbody></table>
          </State>
        </Panel>
      </div>
    </div>
  );
}
