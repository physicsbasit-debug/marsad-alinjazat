from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .db import DATA_DIR, DB_PATH
from .runtime_platform import persistent_default

MARSAD_MARKER_TABLES = {"teachers", "events", "upload_requests", "documents", "curriculum_plans", "achievement_assessments"}


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _safe_label(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.strip().lower())
    return cleaned.strip("-") or "manual"


def get_backup_dir() -> Path:
    return Path(os.getenv("APP_BACKUP_DIR", "").strip() or persistent_default("backups", DATA_DIR / "backups"))


def get_backup_keep() -> int:
    try:
        value = int(os.getenv("APP_BACKUP_KEEP", "14"))
    except ValueError:
        value = 14
    return max(1, min(value, 100))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_database_file(path: Path | str) -> dict[str, Any]:
    candidate = Path(path)
    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError(f"ملف النسخة غير موجود: {candidate}")
    if candidate.stat().st_size == 0:
        raise ValueError("ملف النسخة الاحتياطية فارغ.")

    connection = sqlite3.connect(str(candidate))
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError(f"فشل فحص سلامة SQLite: {integrity}")
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_keys:
            raise ValueError("تحتوي النسخة على مخالفات للمفاتيح الأجنبية.")
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if not (MARSAD_MARKER_TABLES & tables):
            raise ValueError("الملف SQLite سليم لكنه لا يحتوي جداول معروفة لمرصد الإنجازات.")
    finally:
        connection.close()

    return {
        "ok": True,
        "sizeBytes": candidate.stat().st_size,
        "sha256": _sha256(candidate),
        "tableCount": len(tables),
    }


def _prune_backups(backup_dir: Path, keep: int | None = None) -> None:
    keep_count = keep if keep is not None else get_backup_keep()
    files = sorted(backup_dir.glob("marsad-*.sqlite3"), key=lambda item: item.stat().st_mtime, reverse=True)
    for stale in files[keep_count:]:
        stale.unlink(missing_ok=True)


def create_database_backup(
    *,
    label: str = "manual",
    db_path: Path | str | None = None,
    backup_dir: Path | str | None = None,
    prune: bool = True,
) -> Path | None:
    source_path = Path(db_path) if db_path is not None else DB_PATH
    if not source_path.exists() or source_path.stat().st_size == 0:
        return None

    destination_dir = Path(backup_dir) if backup_dir is not None else get_backup_dir()
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"marsad-{_utc_stamp()}-{_safe_label(label)}.sqlite3"
    temporary = destination.with_suffix(".sqlite3.tmp")
    temporary.unlink(missing_ok=True)

    source = sqlite3.connect(str(source_path))
    target = sqlite3.connect(str(temporary))
    try:
        source.backup(target)
        target.commit()
    finally:
        target.close()
        source.close()

    validate_database_file(temporary)
    os.replace(temporary, destination)
    if prune:
        _prune_backups(destination_dir)
    return destination


def maybe_create_startup_backup() -> Path | None:
    enabled = os.getenv("APP_AUTO_BACKUP_ON_STARTUP", "true").strip().lower() not in {"0", "false", "no", "off"}
    if not enabled or not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        return None

    backup_dir = get_backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    try:
        interval_minutes = max(0, int(os.getenv("APP_STARTUP_BACKUP_MIN_INTERVAL_MINUTES", "60")))
    except ValueError:
        interval_minutes = 60
    newest = max(backup_dir.glob("marsad-*-startup.sqlite3"), key=lambda item: item.stat().st_mtime, default=None)
    if newest is not None and interval_minutes > 0:
        age_seconds = datetime.now(timezone.utc).timestamp() - newest.stat().st_mtime
        if age_seconds < interval_minutes * 60:
            return None
    return create_database_backup(label="startup")


def restore_database_backup(
    source: Path | str,
    *,
    confirmation: str,
    db_path: Path | str | None = None,
    backup_dir: Path | str | None = None,
) -> dict[str, Any]:
    if confirmation != "RESTORE":
        raise ValueError("الاستعادة مرفوضة. استخدم confirmation='RESTORE' بعد إيقاف الخادم.")

    source_path = Path(source)
    validation = validate_database_file(source_path)
    active_db = Path(db_path) if db_path is not None else DB_PATH
    active_db.parent.mkdir(parents=True, exist_ok=True)
    destination_backup_dir = Path(backup_dir) if backup_dir is not None else get_backup_dir()

    safety_backup = None
    if active_db.exists() and active_db.stat().st_size > 0:
        try:
            safety_backup = create_database_backup(
                label="pre-restore",
                db_path=active_db,
                backup_dir=destination_backup_dir,
                prune=False,
            )
        except Exception:
            # Recovery must remain possible even if the active database is already
            # damaged. Preserve a raw forensic copy before replacing it.
            destination_backup_dir.mkdir(parents=True, exist_ok=True)
            safety_backup = destination_backup_dir / f"marsad-{_utc_stamp()}-pre-restore-raw.sqlite3"
            shutil.copy2(active_db, safety_backup)

    temporary = active_db.with_suffix(".restore.tmp")
    temporary.unlink(missing_ok=True)
    shutil.copy2(source_path, temporary)
    validate_database_file(temporary)

    # Restore is intentionally an offline operation. Removing stale WAL/SHM files
    # prevents an old journal from being replayed onto the restored database.
    Path(f"{active_db}-wal").unlink(missing_ok=True)
    Path(f"{active_db}-shm").unlink(missing_ok=True)
    os.replace(temporary, active_db)
    restored = validate_database_file(active_db)
    _prune_backups(destination_backup_dir)

    return {
        "ok": True,
        "restored": restored,
        "source": validation,
        "safetyBackup": str(safety_backup) if safety_backup else None,
    }
