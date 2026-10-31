"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { PriceChart } from "@/components/PriceChart";
import { WatchlistPanel } from "@/components/widgets";

export default function ChartPage() {
  const params = useSearchParams();
  const router = useRouter();
  const symbol = (params.get("s") ?? "^GSPC").toUpperCase();
  return (
    <div className="page chart-page">
      <section className="panel chart-main"><PriceChart symbol={symbol} key={symbol} /></section>
      <div className="chart-side"><WatchlistPanel selected={symbol} onSelect={(s) => router.push(`/chart?s=${encodeURIComponent(s)}`)} /></div>
    </div>
  );
}
