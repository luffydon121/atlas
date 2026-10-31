"use client";

import { AreaSeries, CandlestickSeries, ColorType, createChart, CrosshairMode, HistogramSeries, LineSeries, PriceScaleMode, type Time } from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";
import { useEnvelope } from "@/lib/api";
import { num } from "@/lib/format";
import { useTheme } from "@/lib/theme";
import { SymbolActions } from "./SymbolActions";
import { Fresh, Skeleton, Toggle } from "./ui";

const FRAMES = {
  "1D": ["1d", "5m"], "5D": ["5d", "15m"], "1M": ["1mo", "1h"], "3M": ["3mo", "1d"], "6M": ["6mo", "1d"],
  "1Y": ["1y", "1d"], "5Y": ["5y", "1wk"], "10Y": ["10y", "1mo"],
} as const;
type Frame = keyof typeof FRAMES;
type Bar = { time: number; open: number; high: number; low: number; close: number; volume: number | null };
type Point = { time: number; value: number };
type Bars = { meta: { symbol: string; name?: string; currency?: string; exchange?: string; prev_close?: number }; bars: Bar[] };
type Indicators = Record<string, Point[]>;

const OVERLAYS: Record<string, { keys: string[]; color: string }> = {
  "SMA 20": { keys: ["sma20"], color: "#3987e5" },
  "SMA 50": { keys: ["sma50"], color: "#c98500" },
  "SMA 200": { keys: ["sma200"], color: "#d55181" },
  Bollinger: { keys: ["bb_upper", "bb_lower"], color: "#9085e9" },
};
const STUDIES = ["RSI", "MACD"] as const;

export function PriceChart({ symbol, defaultFrame = "1Y", compact = false }: { symbol: string; defaultFrame?: Frame; compact?: boolean }) {
  const [frame, setFrame] = useState<Frame>(defaultFrame);
  const [style, setStyle] = useState<"Line" | "Candles">("Line");
  const [log, setLog] = useState(false);
  const [on, setOn] = useState<string[]>([]);
  const [study, setStudy] = useState<string | null>(null);
  const [full, setFull] = useState(false);
  const [hover, setHover] = useState<{ value: number; time: string } | null>(null);
  const [range, interval] = FRAMES[frame];
  const daily = ["1d", "1wk", "1mo"].includes(interval);
  const theme = useTheme();
  const { data, error, isLoading } = useEnvelope<Bars>(`/api/market/bars/${encodeURIComponent(symbol)}?range=${range}&interval=${interval}`, { refreshInterval: 120_000 });
  const needs = daily && (on.length > 0 || study);
  const ind = useEnvelope<Indicators>(needs ? `/api/market/indicators/${encodeURIComponent(symbol)}?range=${range === "3mo" || range === "6mo" ? "2y" : range}&interval=${interval}` : null);
  const host = useRef<HTMLDivElement>(null);

  const bars = useMemo(() => (data?.data.bars ?? []).filter((b) => b.open != null && b.high != null && b.low != null), [data]);
  const first = bars[0]?.close;
  const last = bars[bars.length - 1]?.close;
  const shown = hover?.value ?? last;
  const change = shown != null && first ? ((shown - first) / first) * 100 : null;
  const rising = (last ?? 0) >= (first ?? 0);

  useEffect(() => {
    if (!host.current || !bars.length) return;
    const dark = theme === "dark";
    const up = dark ? "#30d158" : "#1f9d45", down = dark ? "#ff453a" : "#e0352b";
    const lineColor = rising ? up : down;
    const grid = dark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.05)";
    const chart = createChart(host.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#86868b", fontFamily: "-apple-system, BlinkMacSystemFont, Inter Variable, sans-serif", fontSize: 11, panes: { separatorColor: grid } },
      grid: { vertLines: { visible: false }, horzLines: { color: grid } },
      crosshair: { mode: CrosshairMode.Magnet, vertLine: { color: "#86868b", labelBackgroundColor: "#86868b" }, horzLine: { visible: false, labelVisible: false } },
      rightPriceScale: { borderVisible: false, mode: log ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal },
      timeScale: { borderVisible: false, timeVisible: !daily, fixLeftEdge: true, fixRightEdge: true },
    });
    const price = style === "Line"
      ? chart.addSeries(AreaSeries, { lineColor, lineWidth: 2, topColor: `${lineColor}38`, bottomColor: `${lineColor}00`, priceLineVisible: false, crosshairMarkerRadius: 4 })
      : chart.addSeries(CandlestickSeries, { upColor: up, downColor: down, borderVisible: false, wickUpColor: up, wickDownColor: down, priceLineVisible: false });
    price.setData(style === "Line" ? bars.map((b) => ({ time: b.time as Time, value: b.close })) : bars.map((b) => ({ ...b, time: b.time as Time })));
    const vol = chart.addSeries(HistogramSeries, { priceScaleId: "vol", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.88, bottom: 0 } });
    vol.setData(bars.filter((b) => b.volume).map((b) => ({ time: b.time as Time, value: b.volume!, color: dark ? "rgba(255,255,255,0.14)" : "rgba(0,0,0,0.1)" })));
    const start = bars[0].time;
    const clip = (p: Point[]) => p.filter((x) => x.time >= start).map((x) => ({ time: x.time as Time, value: x.value }));
    const lines = (keys: string[], color: string, pane = 0) => keys.forEach((k) => {
      if (ind.data?.data[k]) chart.addSeries(LineSeries, { color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }, pane).setData(clip(ind.data.data[k]));
    });
    if (daily && ind.data) {
      on.forEach((name) => lines(OVERLAYS[name].keys, OVERLAYS[name].color));
      if (study === "RSI") lines(["rsi14"], "#3987e5", 1);
      if (study === "MACD") {
        lines(["macd"], "#3987e5", 1);
        lines(["macd_signal"], "#c98500", 1);
      }
      if (study) chart.panes()[1]?.setHeight(110);
    }
    chart.subscribeCrosshairMove((p) => {
      const row = p.seriesData.get(price) as { value?: number; close?: number } | undefined;
      const value = row?.value ?? row?.close;
      if (value === undefined || p.time === undefined) return setHover(null);
      setHover({ value, time: new Date(Number(p.time) * 1000).toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric" }) });
    });
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [bars, ind.data, on, study, daily, style, log, theme, rising]);

  const toggle = (name: string) => setOn((v) => (v.includes(name) ? v.filter((x) => x !== name) : [...v, name]));
  const shell: React.CSSProperties = full ? { position: "fixed", inset: 0, zIndex: 70, background: "var(--panel)", display: "flex", flexDirection: "column", animation: "fade .25s both" } : { height: "100%", display: "flex", flexDirection: "column", minHeight: 0 };
  return (
    <div style={shell}>
      <div className="row" style={{ padding: "16px 20px 6px", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div style={{ minWidth: 0 }}>
          <div className="row" style={{ gap: 6 }}><b style={{ fontSize: 15 }}>{symbol}</b><span className="muted" style={{ maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{data?.data.meta.name}</span><Fresh meta={data?.meta} /></div>
          <div style={{ fontSize: 30, fontWeight: 600, letterSpacing: "-0.024em", fontVariantNumeric: "tabular-nums" }}>{num(shown)} <span className="muted" style={{ fontSize: 14, fontWeight: 400 }}>{data?.data.meta.currency}</span></div>
          <div className={change === null ? "muted" : change >= 0 ? "up" : "down"} style={{ fontVariantNumeric: "tabular-nums", minHeight: 20 }}>{change === null ? "" : `${change >= 0 ? "+" : ""}${change.toFixed(2)}%`} <span className="muted">{hover?.time ?? frame}</span></div>
        </div>
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <Toggle value={frame} options={Object.keys(FRAMES) as Frame[]} onChange={setFrame} />
          {!compact && <Toggle value={style} options={["Line", "Candles"] as const} onChange={setStyle} />}
          <SymbolActions symbol={symbol} price={last} />
          <button className="btn" onClick={() => setFull(!full)}>{full ? "Exit" : "Full screen"}</button>
        </div>
      </div>
      {!compact && <div className="row chips" style={{ padding: "2px 20px 6px" }}>
        <button className={`btn ${log ? "on" : ""}`} onClick={() => setLog(!log)}>Log</button>
        {daily && Object.keys(OVERLAYS).map((k) => <button key={k} className={`btn ${on.includes(k) ? "on" : ""}`} onClick={() => toggle(k)}>{k}</button>)}
        {daily && STUDIES.map((k) => <button key={k} className={`btn ${study === k ? "on" : ""}`} onClick={() => setStudy(study === k ? null : k)}>{k}</button>)}
      </div>}
      {error ? <div className="notice bad" role="alert">Unavailable right now. {error.message}</div> : isLoading ? <Skeleton lines={8} /> : <div ref={host} style={{ flex: 1, minHeight: 0 }} data-testid="price-chart" />}
    </div>
  );
}

