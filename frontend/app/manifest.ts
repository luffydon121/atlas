import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return { name: "ATLAS", short_name: "ATLAS", start_url: "/", display: "standalone", background_color: "#000000", theme_color: "#000000", icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml" }] };
}
