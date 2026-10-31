"use client";

import { useSyncExternalStore } from "react";

export type ThemeChoice = "system" | "light" | "dark";
const KEY = "atlas-theme";

export function themeChoice(): ThemeChoice {
  try {
    return (localStorage.getItem(KEY) as ThemeChoice) ?? "system";
  } catch {
    return "system";
  }
}

export function applyTheme(choice: ThemeChoice) {
  const dark = choice === "dark" || (choice === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  try {
    localStorage.setItem(KEY, choice);
  } catch {
    /* A remembered theme is a convenience only. */
  }
}

function subscribe(callback: () => void) {
  const observer = new MutationObserver(callback);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => observer.disconnect();
}

export const useTheme = () => useSyncExternalStore(subscribe, () => document.documentElement.dataset.theme ?? "light", () => "light");

function subscribeWidth(callback: () => void) {
  const media = window.matchMedia("(max-width: 900px)");
  media.addEventListener("change", callback);
  return () => media.removeEventListener("change", callback);
}

export const useSmallScreen = () => useSyncExternalStore(subscribeWidth, () => window.matchMedia("(max-width: 900px)").matches, () => false);

// Runs before first paint so the page never flashes the wrong theme.
export const THEME_SCRIPT = `try{var c=localStorage.getItem("${KEY}")||"system";document.documentElement.dataset.theme=c==="dark"||(c==="system"&&matchMedia("(prefers-color-scheme: dark)").matches)?"dark":"light"}catch(e){document.documentElement.dataset.theme="light"}`;
