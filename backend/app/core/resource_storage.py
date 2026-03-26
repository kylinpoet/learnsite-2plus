from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from .config import get_settings


def _storage_root() -> Path:
    root = Path(get_settings().resource_storage_dir)
    if not root.is_absolute():
        root = Path.cwd() / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def _school_dir(school_code: str) -> Path:
    directory = _storage_root() / school_code
    directory.mkdir(parents=True, exist_ok=True)
    return directory


async def save_uploaded_resource(upload: UploadFile, school_code: str) -> tuple[str, int]:
    suffix = Path(upload.filename or "").suffix.lower()
    stored_name = f"{uuid4().hex}{suffix}"
    destination = _school_dir(school_code) / stored_name
    file_size = 0
    with destination.open("wb") as output:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            file_size += len(chunk)
    await upload.close()
    return f"{school_code}/{stored_name}", file_size


def resolve_resource_path(storage_key: str) -> Path:
    return _storage_root() / storage_key


def ensure_seed_resource_file(school_code: str, filename: str, content: str) -> tuple[str, int]:
    path = _school_dir(school_code) / filename
    if not path.exists():
        path.write_text(content, encoding="utf-8")
    return f"{school_code}/{filename}", path.stat().st_size
