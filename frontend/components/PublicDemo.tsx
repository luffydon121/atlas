"use client";
import { usePathname } from "next/navigation";
const disabled = new Set(["/portfolio", "/alerts", "/settings", "/quant", "/satellite", "/workspace", "/events", "/holdings"]);
export function PublicDemo({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  if (process.env.NEXT_PUBLIC_ATLAS_READ_ONLY !== "true") return <>{children}</>;
  return <><div role="status" style={{padding:"12px 20px",background:"#172554",color:"white",fontSize:14}}>Public read-only demo · Saving, uploads, assistant and interactive calculations are disabled. Data may take a minute to load after inactivity.</div>{disabled.has(path) ? <section style={{padding:40}}><h1>Available in the personal edition</h1><p>This free public demo lets you explore market and world data. Personal records and interactive tools are disabled.</p><a href="/markets">Explore markets →</a></section> : children}</>;
}
