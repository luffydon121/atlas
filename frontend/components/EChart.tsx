"use client";

import { BarChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";
import { useTheme } from "@/lib/theme";

echarts.use([LineChart, BarChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

// Categorical slots in fixed order. Each theme uses its own validated steps.
const PALETTE = { light: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"], dark: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"] };
export const SERIES = PALETTE.dark;
const NEUTRAL = "#86868b";
export const axisBase = {
  axisLine: { show: false },
  axisTick: { show: false },
  axisLabel: { color: NEUTRAL, fontSize: 11 },
  splitLine: { lineStyle: { color: "rgba(134,134,139,0.16)" } },
};
export const tooltip = { trigger: "axis" as const, axisPointer: { lineStyle: { color: NEUTRAL, width: 1 } } };
export const legend = { top: 0, textStyle: { color: NEUTRAL, fontSize: 12 }, itemWidth: 12, itemHeight: 3, icon: "roundRect" };

type Option = Record<string, unknown>;

export function EChart({ option, height = 220, onClick }: { option: Option; height?: number | string; onClick?: (p: unknown) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const theme = useTheme();

  useEffect(() => {
    const instance = echarts.init(ref.current!, undefined, { renderer: "canvas" });
    chart.current = instance;
    const ro = new ResizeObserver(() => instance.resize());
    ro.observe(ref.current!);
    return () => {
      ro.disconnect();
      instance.dispose();
    };
  }, []);

  useEffect(() => {
    const dark = theme === "dark";
    const themed = {
      backgroundColor: "transparent", animationDuration: 500, animationEasing: "cubicOut" as const, grid: { left: 52, right: 18, top: 30, bottom: 26 }, ...option,
      color: dark ? PALETTE.dark : PALETTE.light,
      tooltip: option.tooltip ? { ...(option.tooltip as Option), backgroundColor: dark ? "rgba(44,44,46,0.92)" : "rgba(255,255,255,0.94)", borderWidth: 0, borderRadius: 12, padding: [8, 12], textStyle: { color: dark ? "#f5f5f7" : "#1d1d1f", fontSize: 12 }, extraCssText: "box-shadow:0 8px 30px rgba(0,0,0,.18);backdrop-filter:blur(20px)" } : undefined,
    };
    chart.current?.setOption(themed, true);
    chart.current?.off("click");
    if (onClick) chart.current?.on("click", onClick);
  }, [option, onClick, theme]);

  return <div ref={ref} style={{ width: "100%", height, padding: "0 8px 8px" }} />;
}

export function lineOption(series: { name: string; points: [string, number | null][] }[], opts: { yName?: string; scale?: boolean; zero?: boolean; compact?: boolean } = {}) {
  const single = series.length === 1;
  return {
    tooltip,
    legend: single ? undefined : legend,
    xAxis: { type: "category", data: series[0]?.points.map((p) => p[0]) ?? [], ...axisBase, splitLine: { show: false }, axisLabel: { ...axisBase.axisLabel, hideOverlap: true } },
    yAxis: { type: "value", scale: opts.scale ?? true, splitNumber: opts.compact ? 2 : 4, name: opts.yName, nameTextStyle: { color: NEUTRAL, fontSize: 11 }, ...axisBase },
    series: series.map((s) => ({ name: s.name, type: "line", data: s.points.map((p) => p[1]), showSymbol: false, connectNulls: true, lineStyle: { width: 2 }, areaStyle: single ? { opacity: 0.1 } : undefined })),
  };
}
