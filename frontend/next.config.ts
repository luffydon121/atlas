import type { NextConfig } from "next";

const api = process.env.ATLAS_API_URL ?? "http://127.0.0.1:8000";

const config: NextConfig = {
  devIndicators: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
};

export default config;
