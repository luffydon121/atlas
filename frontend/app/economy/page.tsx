"use client";

import { useState } from "react";
import { EChart, SERIES, axisBase, legend, lineOption, tooltip } from "@/components/EChart";
import { Panel, Stat, State, Toggle } from "@/components/ui";
import { IndicatorChart } from "@/components/widgets";
import { useEnvelope } from "@/lib/api";
import { num } from "@/lib/format";

type Indicator = Parameters<typeof IndicatorChart>[0]["row"];
type Dash = { indicators: Indicator[]; unavailable: { id: string; name: string; reason: string }[] };
type Curve = { label: string; date: string; points: { tenor: string; value: number | null }[] };
type Recession = { spreads: { date: string; s10y2y: number; s10y3m: number }[]; latest: { date: string; s10y2y: number; s10y3m: number } | null; sahm: { sahm_gap: number; triggered: boolean; period: string } | null };
type Global = { name: string; unit: string; countries: { code: string; points: { year: string; value: number }[] }[]; choices: Record<string, string> };

export default function Economy() {
  const [region, setRegion] = useState("US");
  const [indicator, setIndicator] = useState("gdp_growth");
  const dash = useEnvelope<Dash>(`/api/econ/dashboard?region=${encodeURIComponent(region)}`);
  const curve = useEnvelope<Curve[]>("/api/econ/yield-curve");
  const rec = useEnvelope<Recession>("/api/econ/recession");
  const world = useEnvelope<Global>(`/api/econ/global?indicator=${indicator}`);
  const years = [...new Set(world.data?.data.countries.flatMap((c) => c.points.map((p) => p.year)))].sort();
  const top = world.data?.data.countries.slice(0, 8) ?? [];

  return (
    <div className="page">
      <div className="row"><Toggle value={region} options={["US", "Australia", "Euro area"]} onChange={setRegion} /></div>
      <State loading={dash.isLoading} error={dash.error}>
        <div className="grid-4">{dash.data?.data.indicators.map((i) => <IndicatorChart key={i.id} row={i} height={120} />)}</div>
        {!!dash.data?.data.unavailable.length && <div className="notice" style={{ padding: 0 }}>{dash.data.data.unavailable.some((u) => u.reason.includes("FRED")) ? "Add a free FRED key in .env to unlock: " : "Unavailable: "}{dash.data.data.unavailable.map((u) => u.name).join(", ")}.</div>}
      </State>
      <div className="grid-2">
        <Panel title="US Treasury yield curve" meta={curve.data?.meta}>
          <State loading={curve.isLoading} error={curve.error}>
            <EChart height={260} option={{ color: SERIES, tooltip, legend, xAxis: { type: "category", data: curve.data?.data[0]?.points.map((p) => p.tenor), ...axisBase, splitLine: { show: false } }, yAxis: { type: "value", scale: true, ...axisBase },
              series: curve.data?.data.map((c) => ({ name: `${c.label} (${c.date})`, type: "line", symbolSize: 6, connectNulls: true, data: c.points.map((p) => p.value), lineStyle: { width: 2 } })) }} />
          </State>
        </Panel>
        <Panel title="Recession indicators" meta={rec.data?.meta}>
          <State loading={rec.isLoading} error={rec.error}>
            <div className="grid-3"><Stat k="10Y - 2Y" v={num(rec.data?.data.latest?.s10y2y)} s={rec.data?.data.latest?.date} /><Stat k="10Y - 3M" v={num(rec.data?.data.latest?.s10y3m)} /><Stat k="Sahm-style gap" v={num(rec.data?.data.sahm?.sahm_gap)} s={rec.data?.data.sahm?.triggered ? "At or above 0.5" : "Below 0.5"} /></div>
            <EChart height={190} option={lineOption([{ name: "10Y - 2Y", points: rec.data?.data.spreads.map((s) => [s.date, s.s10y2y]) ?? [] }, { name: "10Y - 3M", points: rec.data?.data.spreads.map((s) => [s.date, s.s10y3m]) ?? [] }])} />
          </State>
        </Panel>
      </div>
      <Panel title={`Global: ${world.data?.data.name ?? ""} (${world.data?.data.unit ?? ""})`} meta={world.data?.meta} actions={<select className="input" aria-label="Global indicator" value={indicator} onChange={(e) => setIndicator(e.target.value)}>{Object.entries(world.data?.data.choices ?? { gdp_growth: "GDP growth" }).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>}>
        <State loading={world.isLoading} error={world.error}>
          <EChart height={300} option={lineOption(top.map((c) => ({ name: c.code, points: years.map((y): [string, number | null] => [y, c.points.find((p) => p.year === y)?.value ?? null]) })))} />
        </State>
      </Panel>
    </div>
  );
}
