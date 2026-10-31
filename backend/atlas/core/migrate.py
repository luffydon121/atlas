"""Schema upgrades. Every upgrade of an existing database is preceded by a backup."""

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

log = logging.getLogger("atlas.migrate")
HERE = Path(__file__).resolve().parent.parent / "migrations"
BASELINE = "0001"
KEEP_BACKUPS = 14


def config(url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(HERE))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def backup(db_file: Path, reason: str, keep: int = KEEP_BACKUPS) -> Path | None:
    """Uses SQLite's online backup, so it is safe while ATLAS is running."""
    if not db_file.exists() or db_file.stat().st_size == 0:
        return None
    folder = db_file.parent / "backups"
    folder.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    target = folder / f"{db_file.stem}-{stamp}-{reason}.db"
    source = sqlite3.connect(db_file)
    copy = sqlite3.connect(target)
    try:
        with copy:
            source.backup(copy)
    finally:
        copy.close()
        source.close()
    for old in sorted(folder.glob(f"{db_file.stem}-*.db"))[:-keep]:
        old.unlink()
    log.info("Backed up database to %s", target.name)
    return target


def _state(url: str) -> tuple[str | None, bool]:
    engine = create_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
        legacy = "watchlists" in tables and "alembic_version" not in tables
        version = None
        if "alembic_version" in tables:
            with engine.connect() as conn:
                version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        return version, legacy
    finally:
        engine.dispose()


def upgrade(url: str) -> dict:
    """Brings any ATLAS database to the latest schema without touching existing records."""
    cfg = config(url)
    head = ScriptDirectory.from_config(cfg).get_current_head()
    version, legacy = _state(url)
    db_file = Path(url.removeprefix("sqlite:///"))
    saved = None
    if (legacy or (version and version != head)) and db_file.exists():
        saved = backup(db_file, f"before-{head}")
    if legacy:
        # A database from V1 or V2 already matches the baseline, so it is marked rather than rebuilt.
        command.stamp(cfg, BASELINE)
    command.upgrade(cfg, "head")
    return {"from": version or (BASELINE if legacy else None), "to": head, "backup": saved.name if saved else None}


def restore_hint(db_file: Path) -> str:
    return f"Stop ATLAS, then copy a file from {db_file.parent / 'backups'} over {db_file}."


__all__ = ["backup", "config", "restore_hint", "upgrade"]
