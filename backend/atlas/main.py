import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, ORJSONResponse

from atlas.api import company, econ, market, research, world
from atlas.config import get_settings
from atlas.core.errors import SourceNotConfigured, SourceUnavailable
from atlas.core.fetcher import get_fetcher, set_fetcher
from atlas.db import init_db
from atlas.services import scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    task = asyncio.create_task(scheduler.run()) if get_settings().scheduler_enabled else None
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    await get_fetcher().close()
    set_fetcher(None)


app = FastAPI(title="ATLAS", version="2.0.0", lifespan=lifespan, default_response_class=ORJSONResponse)
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
# Rejecting other Host headers stops a malicious web page from reaching this API by DNS rebinding.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(SourceUnavailable)
async def source_unavailable(_request: Request, exc: SourceUnavailable) -> JSONResponse:
    code = 424 if isinstance(exc, SourceNotConfigured) else 503
    return JSONResponse(status_code=code, content={"detail": exc.reason, "source": exc.source, "freshness": "unavailable"})


for module in (market, company, econ, world, research):
    app.include_router(module.router)


@app.middleware("http")
async def public_read_only(request: Request, call_next):
    if get_settings().public_read_only:
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            return JSONResponse(status_code=403, content={"detail": "This public demo is read-only. Saving, uploads and interactive calculations are disabled."})
        private_paths = ("/api/portfolios", "/api/documents", "/api/alerts", "/api/notifications", "/api/layouts", "/api/watchlists", "/api/ai")
        if any(request.url.path == p or request.url.path.startswith(p + "/") for p in private_paths):
            return JSONResponse(status_code=403, content={"detail": "Personal workspace features are unavailable in the public demo."})
    return await call_next(request)
