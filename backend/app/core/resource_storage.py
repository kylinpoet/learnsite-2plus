from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from pathlib import PurePosixPath
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


def _interactive_school_dir(school_code: str) -> Path:
    directory = _school_dir(school_code) / "interactive"
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


def _validate_zip_member(member_name: str) -> PurePosixPath:
    member_path = PurePosixPath(member_name)
    if member_path.is_absolute() or ".." in member_path.parts:
        raise ValueError("Interactive package contains an unsafe file path.")
    return member_path


async def save_uploaded_interactive_package(upload: UploadFile, school_code: str) -> tuple[str, str, str, int]:
    suffix = Path(upload.filename or "").suffix.lower()
    package_id = uuid4().hex
    package_dir = _interactive_school_dir(school_code) / package_id
    package_dir.mkdir(parents=True, exist_ok=True)

    if suffix in {".html", ".htm"}:
        destination = package_dir / "index.html"
        file_size = 0
        with destination.open("wb") as output:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                file_size += len(chunk)
        await upload.close()
        return f"{school_code}/interactive/{package_id}", "index.html", upload.filename or "index.html", file_size

    if suffix != ".zip":
        await upload.close()
        raise ValueError("Interactive activity upload only supports .html or .zip packages.")

    archive_path = package_dir / "__upload.zip"
    archive_size = 0
    with archive_path.open("wb") as output:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            archive_size += len(chunk)
    await upload.close()

    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            member_path = _validate_zip_member(member.filename)
            target_path = package_dir.joinpath(*member_path.parts)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target_path.open("wb") as target:
                shutil.copyfileobj(source, target)

    archive_path.unlink(missing_ok=True)

    default_entry = package_dir / "index.html"
    if default_entry.exists():
        entry_file = "index.html"
    else:
        html_files = sorted(path.relative_to(package_dir).as_posix() for path in package_dir.rglob("*.html"))
        if not html_files:
            raise ValueError("Interactive package must contain an index.html or another .html entry file.")
        entry_file = html_files[0]

    return f"{school_code}/interactive/{package_id}", entry_file, upload.filename or "interactive.zip", archive_size


def resolve_interactive_asset_path(storage_key: str, asset_path: str) -> Path:
    normalized_asset = PurePosixPath(asset_path or "")
    if normalized_asset.is_absolute() or ".." in normalized_asset.parts:
        raise ValueError("Interactive asset path is invalid.")
    return resolve_resource_path(storage_key).joinpath(*normalized_asset.parts)
