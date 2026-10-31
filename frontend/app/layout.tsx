import "./globals.css";
import type { Metadata, Viewport } from "next";
import { Suspense } from "react";
import { Providers } from "@/components/Providers";
import { PublicDemo } from "@/components/PublicDemo";
import { Shell } from "@/components/Shell";
import { THEME_SCRIPT } from "@/lib/theme";

export const metadata: Metadata = { title: "ATLAS", description: "Local-first financial and global intelligence", applicationName: "ATLAS" };
export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover", themeColor: [{ media: "(prefers-color-scheme: dark)", color: "#000000" }, { media: "(prefers-color-scheme: light)", color: "#f5f5f7" }] };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} /></head>
      <body>
        <Providers><Shell><Suspense><PublicDemo>{children}</PublicDemo></Suspense></Shell></Providers>
      </body>
    </html>
  );
}
