import asyncio
import sqlite3

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import select

from atlas import db
from atlas.core import migrate
from atlas.core.envelope import Freshness, envelope, utcnow
from atlas.core.registry import REGISTRY, expected_seconds, reliability
from atlas.db import JobRun, session_scope
from atlas.main import app
from atlas.services import documents, jobs


def legacy_database(path):
    """A V2-shaped database: baseline tables and data, with no migration record."""
    url = f"sqlite:///{path}"
    command.upgrade(migrate.config(url), "0001")
    con = sqlite3.connect(path)
    con.execute("DROP TABLE alembic_version")
    con.execute("INSERT INTO watchlists (id, name) VALUES (7, 'Mine')")
    con.execute("INSERT INTO portfolios (id, name, kind, base_currency, starting_cash) VALUES (3, 'Keep me', 'real', 'AUD', 0)")
    con.commit()
    con.close()
    return url


def test_legacy_database_upgrades_with_data_intact_and_a_backup(tmp_path):
    path = tmp_path / "atlas.db"
    result = migrate.upgrade(legacy_database(path))
    assert result["from"] == "0001" and result["backup"]
    con = sqlite3.connect(path)
    assert con.execute("SELECT name FROM portfolios WHERE id=3").fetchone() == ("Keep me",)
    assert con.execute("SELECT count(*) FROM job_runs").fetchone() == (0,)
    saved = sqlite3.connect(tmp_path / "backups" / result["backup"])
    assert saved.execute("SELECT name FROM watchlists").fetchone() == ("Mine",)


def test_upgrade_twice_changes_nothing(tmp_path):
    url = f"sqlite:///{tmp_path / 'atlas.db'}"
    migrate.upgrade(url)
    assert migrate.upgrade(url)["backup"] is None


def test_migrations_match_the_models(tmp_path):
    url = f"sqlite:///{tmp_path / 'atlas.db'}"
    migrate.upgrade(url)
    command.check(migrate.config(url))


def test_downgrade_and_upgrade_round_trip(tmp_path):
    url = f"sqlite:///{tmp_path / 'atlas.db'}"
    migrate.upgrade(url)
    command.downgrade(migrate.config(url), "0001")
    migrate.upgrade(url)


def test_backups_are_capped(tmp_path):
    path = tmp_path / "atlas.db"
    sqlite3.connect(path).execute("CREATE TABLE t (a)").connection.commit()
    for _ in range(4):
        migrate.backup(path, "x", keep=2)
    assert len(list((tmp_path / "backups").glob("*.db"))) == 2


async def test_job_records_success():
    async def work():
        return 1

    assert await jobs.Runner([]).execute(jobs.Job("a", work, 60)) == "ok"
    with session_scope() as s:
        assert s.scalar(select(JobRun.status)) == "ok"


async def test_job_retries_then_succeeds():
    calls = []

    async def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise ValueError("first")

    assert await jobs.Runner([], backoff=0).execute(jobs.Job("a", flaky, 60, retries=1)) == "ok"
    assert len(calls) == 2


async def test_job_timeout_is_recorded():
    async def slow():
        await asyncio.sleep(5)

    assert await jobs.Runner([], backoff=0).execute(jobs.Job("a", slow, 60, timeout=0.01)) == "timeout"


async def test_one_failure_does_not_stop_other_jobs():
    done = []

    async def bad():
        raise RuntimeError("boom")

    async def good():
        done.append(1)

    runner = jobs.Runner([jobs.Job("bad", bad, 60, retries=0), jobs.Job("good", good, 60)], backoff=0)
    runner.recover()
    runner.next_due = dict.fromkeys(runner.jobs, 0)
    runner.tick()
    await asyncio.gather(*runner.running.values())
    assert done == [1]


async def test_concurrency_and_provider_limits():
    gate = asyncio.Event()

    async def wait():
        await gate.wait()

    runner = jobs.Runner([jobs.Job("a", wait, 60, provider="p"), jobs.Job("b", wait, 60, provider="p"), jobs.Job("c", wait, 60), jobs.Job("d", wait, 60), jobs.Job("e", wait, 60)], concurrency=3)
    runner.recover()
    runner.next_due = dict.fromkeys(runner.jobs, 0)
    runner.tick()
    assert set(runner.running) == {"a", "c", "d"}
    gate.set()
    await asyncio.gather(*runner.running.values())


async def test_shutdown_marks_running_job_interrupted():
    async def wait():
        await asyncio.sleep(30)

    runner = jobs.Runner([jobs.Job("a", wait, 60)])
    task = runner.start(runner.jobs["a"])
    await asyncio.sleep(0)
    await asyncio.sleep(0.01)
    await runner.stop()
    assert task.cancelled()
    with session_scope() as s:
        assert s.scalar(select(JobRun.status)) == "interrupted"


def test_recovery_closes_runs_left_open_and_keeps_schedule():
    with session_scope() as s:
        s.add(JobRun(job="a", status="running"))
        s.add(JobRun(job="b", status="ok", started_at=utcnow(), finished_at=utcnow()))

    async def work():
        return None

    runner = jobs.Runner([jobs.Job("a", work, 3600), jobs.Job("b", work, 3600)])
    assert runner.recover() == 1
    assert runner.next_due["b"] > runner.next_due["a"] + 3000


def test_old_data_is_never_called_live():
    from datetime import timedelta

    old = envelope([], source="binance", freshness=Freshness.LIVE, fetched_at=utcnow() - timedelta(minutes=5))
    assert old["meta"]["freshness"] == "delayed"
    assert envelope([], source="binance", freshness=Freshness.LIVE, stale=True)["meta"]["freshness"] == "delayed"
    assert envelope([], source="binance", freshness=Freshness.LIVE)["meta"]["freshness"] == "live"


def test_every_envelope_carries_licence_and_limitations():
    meta = envelope([], source="yahoo", freshness=Freshness.DELAYED)["meta"]
    assert meta["licence"] and meta["limitations"]


def test_every_source_has_a_refresh_expectation_or_is_on_demand():
    assert [s for s in REGISTRY if expected_seconds(s) is None and s not in {"fred", "gibs", "ollama"}] == []


def test_reliability_rule():
    assert reliability(REGISTRY["sec"], 1.0) == "high"
    assert reliability(REGISTRY["sec"], 0.5) == "medium"
    assert reliability(REGISTRY["gdelt"], 0.1) == "low"
    assert reliability(REGISTRY["yahoo"], None) == "medium"


def test_quality_endpoint_reports_every_source():
    body = TestClient(app, base_url="http://localhost").get("/api/quality").json()["data"]
    assert len(body["sources"]) == len(REGISTRY)
    assert all(s["licence"] and s["redistribution"] and s["reliability"] for s in body["sources"])
    assert next(s for s in body["sources"] if s["id"] == "yahoo")["redistribution"].startswith("Personal use")


def test_storage_and_jobs_endpoints():
    client = TestClient(app, base_url="http://localhost")
    assert client.get("/api/system/storage").json()["schema_version"]
    assert {j["name"] for j in client.get("/api/system/jobs").json()["jobs"]} >= {"market", "backup"}


def test_pdf_upload_needs_a_real_pdf_header():
    with pytest.raises(documents.DocumentError):
        documents.ingest("fake.pdf", b"not a pdf")
    with pytest.raises(documents.DocumentError):
        documents.ingest("fake.txt", b"\x00\x01binary")


def test_init_db_is_safe_to_repeat(tmp_path):
    url = f"sqlite:///{tmp_path / 'x.db'}"
    db.init_db(url)
    db.init_db(url)
