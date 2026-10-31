// MapLibre's module worker cannot go through the bundler, so it is served as a static file.
import { copyFileSync, mkdirSync, readdirSync } from "node:fs";

const dist = "node_modules/maplibre-gl/dist";
mkdirSync("public", { recursive: true });
for (const file of readdirSync(dist)) {
  if (/^maplibre-gl-(worker|shared)\.mjs$/.test(file)) copyFileSync(`${dist}/${file}`, `public/${file}`);
}
