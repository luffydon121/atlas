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

type Bank = { code: string; country: string; rate: number; as_of: string; last_change_date: string | null; last_change: number | null };
type Compare = { rows: { code: string; country: string; latest: number; period: string; previous: number | null; out_of_date: boolean; history: { date: string; value: number }[] }[]; missing: string[] };

function CountryCompare({ measure, title }: { measure: string; title: string }) {
  const { data, error, isLoading } = useEnvelope<Compare>(`/api/econ/compare/${measure}`);
  const current = data?.data.rows.filter((r) => !r.out_of_date) ?? [];
  const months = [...new Set(current.flatMap((r) => r.history.map((h) => h.date)))].sort();
  return (
    <Panel title={title} meta={data?.meta}>
      <State loading={isLoading && !data} error={error}>
        <EChart height={210} option={lineOption(current.map((r) => ({ name: r.country, points: months.map((m): [string, number | null] => [m, r.history.find((h) => h.date === m)?.value ?? null]) })))} />
        <table className="t"><tbody>{data?.data.rows.map((r) => <tr key={r.code}><td>{r.country}</td><td>{num(r.latest, 1)}%</td><td className="muted">{r.period}</td><td>{r.out_of_date ? <span className="tag">Out of date</span> : null}</td></tr>)}</tbody></table>
      </State>
    </Panel>
  );
}

export default function Economy() {
  const [region, setRegion] = useState("US");
  const [indicator, setIndicator] = useState("gdp_growth");
  const dash = useEnvelope<Dash>(`/api/econ/dashboard?region=${encodeURIComponent(region)}`);
  const curve = useEnvelope<Curve[]>("/api/econ/yield-curve");
  const rec = useEnvelope<Recession>("/api/econ/recession");
  const world = useEnvelope<Global>(`/api/econ/global?indicator=${indicator}`);
  const years = [...new Set(world.data?.data.countries.flatMap((c) => c.points.map((p) => p.year)))].sort();
  const top = world.data?.data.countries.slice(0, 8) ?? [];
  const banks = useEnvelope<Bank[]>("/api/econ/central-banks");

  return (
    <div className="page">
      <div className="row"><Toggle value={region} options={["US", "Australia", "Euro area"]} onChange={setRegion} /></div>
      <State loading={dash.isLoading} error={dash.error}>
        <div className="grid-4">{dash.data?.data.indicators.map((i) => <IndicatorChart key={i.id} row={i} height={120} />)}</div>
        {!!dash.data?.data.unavailable.length && <div className="notice" style={{ padding: 0 }}>{dash.data.data.unavailable.some((u) => u.reason.includes("FRED")) ? "Add a free FRED key in .env to unlock: " : "Unavailable: "}{dash.data.data.unavailable.map((u) => u.name).join(", ")}.</div>}
      </State>
      <Panel title="Central bank tracker" meta={banks.data?.meta}>
        <State loading={banks.isLoading && !banks.data} error={banks.error}>
          <table className="t"><thead><tr><th>Economy</th><th>Policy rate</th><th>Last change</th><th>Change</th></tr></thead><tbody>{banks.data?.data.map((b) => <tr key={b.code}><td>{b.country}</td><td>{num(b.rate, 2)}%</td><td>{b.last_change_date ?? "—"}</td><td>{b.last_change === null ? "—" : `${b.last_change > 0 ? "+" : ""}${num(b.last_change, 2)}`}</td></tr>)}</tbody></table>
        </State>
      </Panel>
      <div className="grid-2"><CountryCompare measure="inflation" title="Inflation by country" /><CountryCompare measure="unemployment" title="Unemployment by country" /></div>
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
