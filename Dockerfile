FROM node:22-bookworm-slim AS web
WORKDIR /app/frontend
COPY frontend/package*.json ./
COPY frontend/scripts ./scripts
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_ATLAS_READ_ONLY=false ATLAS_API_URL=http://127.0.0.1:8000
RUN npm run build

FROM python:3.12-slim-bookworm
COPY --from=web /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
COPY backend/ ./backend/
RUN pip install --no-cache-dir ./backend
COPY --from=web /app/frontend ./frontend
COPY scripts/host.sh ./scripts/host.sh
ENV ATLAS_PUBLIC_READ_ONLY=true ATLAS_SCHEDULER_ENABLED=false ATLAS_DATA_DIR=/tmp/atlas-data NEXT_TELEMETRY_DISABLED=1 NODE_ENV=production PORT=10000 MALLOC_ARENA_MAX=2 MALLOC_TRIM_THRESHOLD_=65536 NODE_OPTIONS=--max-old-space-size=180
EXPOSE 10000
CMD ["bash", "scripts/host.sh"]
