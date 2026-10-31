"use client";

import { useEffect } from "react";
import { preload, SWRConfig, useSWRConfig } from "swr";
import { get } from "@/lib/api";
import { applyTheme, themeChoice } from "@/lib/theme";

const KEY = "atlas-swr-v3";
// Only small, frequently shown responses are remembered, so a reload paints immediately.
const KEEP = /^\/api\/(today|market\/overview|market\/quotes|watchlists|calendar|news|crypto\/live)/;

function cacheProvider() {
  const map = new Map<string, any>();
  if (typeof window === "undefined") return map;
  window.addEventListener("pagehide", () => {
    try {
      const text = JSON.stringify([...map.entries()].filter(([k]) => KEEP.test(k)).map(([k, v]) => [k, v.data]));
      localStorage.setItem(KEY, text.length < 2_000_000 ? text : "[]");
    } catch {
      /* Storage may be full or blocked. */
    }
  });
  return map;
}

// Runs after hydration: restoring earlier would make the first render differ from the server's HTML.
function Restore() {
  const { mutate } = useSWRConfig();
  useEffect(() => {
    try {
      for (const [key, data] of JSON.parse(localStorage.getItem(KEY) ?? "[]")) mutate(key, (current: unknown) => current ?? data, { revalidate: false });
    } catch {
      /* A remembered cache is optional. */
    }
  }, [mutate]);
  return null;
}

export const warm = (urls?: string[]) => urls?.forEach((u) => { preload(u, get).catch(() => {}); });

export function Providers({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const follow = () => { if (themeChoice() === "system") applyTheme("system"); };
    media.addEventListener("change", follow);
    return () => media.removeEventListener("change", follow);
  }, []);
  return <SWRConfig value={{ provider: cacheProvider, keepPreviousData: true, dedupingInterval: 4000 }}><Restore />{children}</SWRConfig>;
}
