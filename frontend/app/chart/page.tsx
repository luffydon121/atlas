"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { PriceChart } from "@/components/PriceChart";
import { WatchlistPanel } from "@/components/widgets";

export default function ChartPage() {
  const params = useSearchParams();
  const router = useRouter();
  const symbol = (params.get("s") ?? "^GSPC").toUpperCase();
  return (
    <div className="page" style={{ flexDirection: "row", height: "calc(100dvh - 190px)", minHeight: 520, paddingBottom: 24 }}>
      <section className="panel" style={{ flex: 1, flexShrink: 1 }}><PriceChart symbol={symbol} key={symbol} /></section>
      <div style={{ width: 320, flex: "none" }}><WatchlistPanel selected={symbol} onSelect={(s) => router.push(`/chart?s=${encodeURIComponent(s)}`)} /></div>
    </div>
  );
}
