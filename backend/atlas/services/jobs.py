"""Background jobs: independent, bounded, timed, retried and recorded in the database."""

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, func, select, update

from atlas.core.envelope import iso, utcnow
from atlas.db import JobRun, session_scope

log = logging.getLogger("atlas.jobs")
HISTORY_DAYS = 30


@dataclass(frozen=True)
class Job:
    name: str
    fn: Callable[[], Awaitable[object]]
    every: float
    timeout: float = 120
    retries: int = 1
    provider: str | None = None
    label: str = ""


class Runner:
    def __init__(self, jobs: list[Job], concurrency: int = 3, backoff: float = 2.0):
        self.jobs = {j.name: j for j in jobs}
        self.concurrency = concurrency
        self.backoff = backoff
        self.next_due: dict[str, float] = {}
        self.running: dict[str, asyncio.Task] = {}
        self.stopping = False

    def recover(self) -> int:
        """Runs left open by a crash or power loss are closed, and each job resumes its own schedule."""
        with session_scope() as db:
            count = db.execute(update(JobRun).where(JobRun.status == "running").values(status="interrupted", finished_at=utcnow(), error="ATLAS stopped during this run")).rowcount
            last = dict(db.execute(select(JobRun.job, func.max(JobRun.started_at)).where(JobRun.status == "ok").group_by(JobRun.job)).all())
        now_wall, now = utcnow(), time.monotonic()
        for i, job in enumerate(self.jobs.values()):
            age = (now_wall - last[job.name]).total_seconds() if job.name in last else None
            self.next_due[job.name] = now + (i * 0.5 if age is None else max(job.every - age, i * 0.5))
        return count

    def _can_start(self, job: Job) -> bool:
        if job.name in self.running or len(self.running) >= self.concurrency:
            return False
        return job.provider is None or all(self.jobs[n].provider != job.provider for n in self.running)

    def tick(self) -> None:
        now = time.monotonic()
        for job in self.jobs.values():
            if self.next_due.get(job.name, 0) <= now and self._can_start(job):
                self.next_due[job.name] = now + job.every + random.uniform(0, min(job.every * 0.02, 5))
                self.start(job)

    def start(self, job: Job) -> asyncio.Task:
        task = asyncio.create_task(self.execute(job))
        self.running[job.name] = task
        task.add_done_callback(lambda _t: self.running.pop(job.name, None))
        return task

    async def execute(self, job: Job) -> str:
        with session_scope() as db:
            run = JobRun(job=job.name, status="running")
            db.add(run)
            db.flush()
            run_id = run.id
        status, error, attempts = "failed", None, 0
        try:
            for attempt in range(job.retries + 1):
                attempts = attempt + 1
                try:
                    await asyncio.wait_for(job.fn(), job.timeout)
                    status, error = "ok", None
                    break
                except TimeoutError:
                    status, error = "timeout", f"Stopped after {job.timeout:.0f} seconds"
                except Exception as exc:
                    status, error = "failed", f"{type(exc).__name__}: {exc}"[:500]
                    log.warning("Job %s failed: %s", job.name, error)
                if attempt < job.retries:
                    await asyncio.sleep(self.backoff * 2**attempt)
        except asyncio.CancelledError:
            status, error = "interrupted", "ATLAS shut down during this run"
            raise
        finally:
            with session_scope() as db:
                db.execute(update(JobRun).where(JobRun.id == run_id).values(status=status, error=error, attempts=attempts, finished_at=utcnow()))
        return status

    async def run(self) -> None:
        self.recover()
        while not self.stopping:
            self.tick()
            await asyncio.sleep(1)

    async def stop(self, grace: float = 5) -> None:
        self.stopping = True
        tasks = list(self.running.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.wait(tasks, timeout=grace)


_runner: Runner | None = None


def set_runner(runner: Runner | None) -> None:
    global _runner
    _runner = runner


def get_runner() -> Runner | None:
    return _runner


def status(jobs: list[Job]) -> list[dict]:
    now = time.monotonic()
    out = []
    with session_scope() as db:
        for job in jobs:
            rows = db.scalars(select(JobRun).where(JobRun.job == job.name).order_by(JobRun.started_at.desc()).limit(20)).all()
            last_ok = next((r for r in rows if r.status == "ok"), None)
            due = _runner.next_due.get(job.name) if _runner else None
            out.append({"name": job.name, "label": job.label or job.name, "every_seconds": job.every, "timeout_seconds": job.timeout, "retries": job.retries, "provider": job.provider,
                        "running": bool(_runner and job.name in _runner.running), "next_in_seconds": max(0, round(due - now)) if due else None,
                        "last_status": rows[0].status if rows else None, "last_started": iso(rows[0].started_at) if rows else None, "last_success": iso(last_ok.finished_at) if last_ok else None,
                        "last_error": next((r.error for r in rows if r.error), None) if rows and rows[0].status != "ok" else None,
                        "recent": [r.status for r in rows[:10]]})
    return out


def prune_history(days: int = HISTORY_DAYS) -> int:
    with session_scope() as db:
        return db.execute(delete(JobRun).where(JobRun.started_at < utcnow() - timedelta(days=days))).rowcount
