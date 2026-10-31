"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PERSONAL, READ_ONLY } from "@/lib/nav";

export function PublicDemo({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  if (!READ_ONLY || !PERSONAL.has(path)) return <>{children}</>;
  return (
    <div className="hero">
      <h1>Available in the personal edition.</h1>
      <p>This public demo explores market and world data. Personal records and interactive tools run on your own computer.</p>
      <div className="row" style={{ marginTop: 20 }}><Link className="btn on" href="/markets">Explore markets</Link></div>
    </div>
  );
}
