from __future__ import annotations

import os
import shutil
from pathlib import Path
from urllib.parse import unquote
from uuid import uuid4

from .clock import utc_now
from .config import get_settings


def _backup_root() -> Path:
    root = Path(get_settings().backup_storage_dir)
    if not root.is_absolute():
        root = Path.cwd() / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def sqlite_database_path() -> Path:
    sqlite_url = get_settings().sqlite_url
    if not sqlite_url.startswith("sqlite:///"):
        raise ValueError("Database backup snapshots currently support SQLite only.")

    raw_path = unquote(sqlite_url.removeprefix("sqlite:///"))
    if raw_path in {"", ":memory:"}:
        raise ValueError("In-memory SQLite databases cannot be snapshotted.")

    database_path = Path(raw_path)
    if not database_path.is_absolute():
        database_path = Path.cwd() / database_path
    return database_path.resolve()


def build_backup_filename(scope_school_code: str) -> str:
    timestamp = utc_now().strftime("%Y%m%d-%H%M%S")
    return f"{scope_school_code}-{timestamp}-{uuid4().hex[:8]}.sqlite3"


def create_sqlite_backup(file_name: str) -> tuple[str, int]:
    database_path = sqlite_database_path()
    if not database_path.exists():
        raise FileNotFoundError(f"SQLite database file not found: {database_path}")

    destination = _backup_root() / file_name
    shutil.copy2(database_path, destination)
    return str(destination.resolve()), destination.stat().st_size


def restore_sqlite_backup(storage_path: str) -> None:
    backup_path = Path(storage_path)
    if not backup_path.is_absolute():
        backup_path = (Path.cwd() / backup_path).resolve()
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup snapshot not found: {backup_path}")

    database_path = sqlite_database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = database_path.with_name(f"{database_path.stem}.restore-{uuid4().hex[:6]}{database_path.suffix}")
    shutil.copy2(backup_path, temp_path)
    os.replace(temp_path, database_path)
