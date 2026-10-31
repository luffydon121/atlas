"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { PriceChart } from "@/components/PriceChart";
import { MarketsPanel, WatchlistPanel } from "@/components/widgets";
import { READ_ONLY } from "@/lib/nav";

export default function ChartPage() {
  const params = useSearchParams();
  const router = useRouter();
  const symbol = (params.get("s") ?? "^GSPC").toUpperCase();
  const pick = (s: string) => router.push(`/chart?s=${encodeURIComponent(s)}`);
  return (
    <div className="page chart-page">
      <section className="panel chart-main"><PriceChart symbol={symbol} key={symbol} /></section>
      <div className="chart-side">{READ_ONLY ? <MarketsPanel selected={symbol} onSelect={pick} /> : <WatchlistPanel selected={symbol} onSelect={pick} />}</div>
    </div>
  );
}
