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

from atlas.api import company, econ, impact, market, research, system, world
from atlas.config import get_settings
from atlas.core.errors import NotCovered, SourceNotConfigured, SourceUnavailable
from atlas.core.fetcher import get_fetcher, set_fetcher
from atlas.db import init_db
from atlas.services import jobs, public_mode, scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    runner = scheduler.build() if get_settings().scheduler_enabled else None
    task = asyncio.create_task(runner.run()) if runner else None
    yield
    if runner:
        await runner.stop()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        jobs.set_runner(None)
    await get_fetcher().close()
    set_fetcher(None)


app = FastAPI(title="ATLAS", version="3.0.0", lifespan=lifespan, default_response_class=ORJSONResponse)
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
# Rejecting other Host headers stops a malicious web page from reaching this API by DNS rebinding.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(SourceUnavailable)
async def source_unavailable(_request: Request, exc: SourceUnavailable) -> JSONResponse:
    code = 424 if isinstance(exc, SourceNotConfigured) else 404 if isinstance(exc, NotCovered) else 503
    return JSONResponse(status_code=code, content={"detail": exc.reason, "source": exc.source, "freshness": "unavailable"})


@app.middleware("http")
async def public_read_only(request: Request, call_next):
    if get_settings().public_read_only:
        blocked = public_mode.check(request.method, request.url.path, public_mode.client_id(request.headers, request.client.host if request.client else "unknown"))
        if blocked:
            return JSONResponse(status_code=blocked[0], content={"detail": blocked[1]})
    return await call_next(request)


for module in (market, company, econ, world, research, system, impact):
    app.include_router(module.router)
