
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from atlas.core.envelope import Freshness, envelope, iso, utcnow
from atlas.core.migrate import backup
from atlas.core.registry import REGISTRY, expected_seconds, redistribution, reliability
from atlas.db import SourceStatus, session_scope
from atlas.services import jobs, maintenance, scheduler

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/system/jobs")
def job_status():
    runner = jobs.get_runner()
    return {"scheduler_running": bool(runner), "concurrency": runner.concurrency if runner else None, "jobs": jobs.status(scheduler.job_list())}


@router.post("/system/jobs/{name}/run", status_code=202)
async def run_job(name: str):
    runner = jobs.get_runner()
    job = next((j for j in scheduler.job_list() if j.name == name), None)
    if job is None:
        raise HTTPException(404, "Unknown job")
    if runner is None:
        raise HTTPException(409, "Background jobs are switched off")
    if name in runner.running:
        raise HTTPException(409, "That job is already running")
    runner.start(job)
    return {"started": name}


@router.get("/system/storage")
def storage():
    return maintenance.storage()


@router.post("/system/backup", status_code=201)
async def backup_now():
    saved = backup(maintenance.db_file(), "manual")
    return {"backup": saved.name if saved else None}


@router.get("/quality")
def quality():
    """Per-source freshness, reliability, licence and redistribution, from recorded fetches only."""
    now = utcnow()
    with session_scope() as db:
        status = {s.source_id: s for s in db.scalars(select(SourceStatus))}
        rows = []
        for spec in REGISTRY.values():
            st = status.get(spec.id)
            total = st.success_count + st.failure_count if st else 0
            rate = st.success_count / total if st and total else None
            window = expected_seconds(spec.id)
            age = (now - st.last_success).total_seconds() if st and st.last_success else None
            state = "unused" if st is None or st.last_attempt is None else "failing" if st.last_error and age is None else "degraded" if st.last_error else "stale" if age is not None and window and age > window * 3 else "fresh"
            rows.append({"id": spec.id, "provider": spec.provider, "domain": spec.domain, "url": spec.url, "state": state, "freshness": spec.freshness, "expected_refresh_seconds": window, "age_seconds": round(age) if age is not None else None,
                         "last_success": iso(st.last_success) if st else None, "last_error": st.last_error if st else None, "success_rate": rate, "reliability": reliability(spec, rate), "licence": spec.licence,
                         "redistribution": redistribution(spec.id), "limitations": spec.limitations, "coverage": spec.coverage})
    summary = {k: sum(1 for r in rows if r["state"] == k) for k in ("fresh", "stale", "degraded", "failing", "unused")}
    return envelope({"summary": summary, "sources": rows, "stale_after": "three times the expected refresh"}, source="atlas", freshness=Freshness.REFERENCE,
                    note="Reliability is a stated rule: the source's tier, lowered if recent fetches fail. It is not a statistical accuracy measure.")
