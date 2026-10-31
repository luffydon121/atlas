"""Backups and storage reporting. Automatic clean-up only ever touches caches and job history."""

import asyncio
from pathlib import Path

from sqlalchemy import inspect, text

from atlas.config import get_settings
from atlas.core import migrate
from atlas.db import Base, session_scope


def db_file() -> Path:
    return get_settings().resolved_data_dir / "atlas.db"


async def scheduled_backup() -> str | None:
    saved = await asyncio.to_thread(migrate.backup, db_file(), "daily")
    return saved.name if saved else None


def storage() -> dict:
    path = db_file()
    folder = path.parent / "backups"
    backups = sorted(folder.glob("*.db"), reverse=True) if folder.exists() else []
    files = [path, Path(f"{path}-wal"), Path(f"{path}-shm")]
    with session_scope() as db:
        version = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
        names = [t for t in inspect(db.get_bind()).get_table_names() if t in Base.metadata.tables]
        tables = {t: db.execute(text(f'SELECT count(*) FROM "{t}"')).scalar() for t in sorted(names)}  # noqa: S608
    return {"schema_version": version, "database_bytes": sum(f.stat().st_size for f in files if f.exists()), "backup_count": len(backups), "backup_bytes": sum(b.stat().st_size for b in backups),
            "latest_backup": backups[0].name if backups else None, "tables": tables, "restore_hint": migrate.restore_hint(path)}
