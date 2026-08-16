from __future__ import annotations

import os
from pathlib import Path


def railway_volume_root() -> Path | None:
    raw = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    return Path(raw) if raw else None


def persistent_default(relative: str, fallback: Path) -> Path:
    root = railway_volume_root()
    return (root / relative) if root else fallback


def persistent_configured(explicit_env_name: str) -> bool:
    return bool(os.getenv(explicit_env_name, "").strip()) or railway_volume_root() is not None


def public_url_default() -> str:
    explicit = os.getenv("APP_PUBLIC_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip().strip("/")
    if domain:
        return f"https://{domain}"
    return "http://localhost:8000"


def storage_mode() -> str:
    value = os.getenv("STORAGE_MODE", "auto").strip().lower() or "auto"
    if value == "drive":
        return "google_drive"
    if value in {"local", "auto", "google_drive"}:
        return value
    return "auto"
