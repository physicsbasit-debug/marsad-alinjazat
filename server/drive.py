from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import urllib.parse
from pathlib import Path
from typing import Any

import requests
from cryptography.fernet import Fernet, InvalidToken

from .db import get_setting, set_setting

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_API = "https://www.googleapis.com/drive/v3"
DRIVE_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"
SCOPE = "https://www.googleapis.com/auth/drive.file"


def _cipher() -> Fernet:
    secret = os.getenv("APP_ENCRYPTION_KEY", "")
    if len(secret) < 24:
        raise RuntimeError("APP_ENCRYPTION_KEY مطلوب ويجب أن يكون سرًا طويلًا قبل ربط Google Drive.")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _cipher().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    try:
        return _cipher().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("تعذر فك بيانات ربط Google Drive. تحقق من APP_ENCRYPTION_KEY.") from exc


def oauth_configured() -> bool:
    return bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET") and os.getenv("GOOGLE_REDIRECT_URI") and len(os.getenv("APP_ENCRYPTION_KEY", "")) >= 24)


def is_connected() -> bool:
    return bool(get_setting("google_refresh_token"))


def create_oauth_state() -> str:
    state = secrets.token_urlsafe(32)
    set_setting("google_oauth_state_hash", hashlib.sha256(state.encode()).hexdigest())
    return state


def verify_oauth_state(state: str) -> bool:
    expected = get_setting("google_oauth_state_hash")
    if not expected:
        return False
    return secrets.compare_digest(expected, hashlib.sha256(state.encode()).hexdigest())


def build_auth_url() -> str:
    if not oauth_configured():
        raise RuntimeError("بيانات OAuth غير مكتملة.")
    params = {
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "redirect_uri": os.environ["GOOGLE_REDIRECT_URI"],
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": create_oauth_state(),
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code(code: str) -> dict[str, Any]:
    response = requests.post(
        TOKEN_URL,
        timeout=30,
        data={
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": os.environ["GOOGLE_REDIRECT_URI"],
        },
    )
    response.raise_for_status()
    payload = response.json()
    refresh_token = payload.get("refresh_token")
    if refresh_token:
        set_setting("google_refresh_token", encrypt_secret(refresh_token))
    elif not is_connected():
        raise RuntimeError("لم يعِد Google رمز تحديث. أعد الربط مع prompt=consent.")
    return payload


def get_access_token() -> str:
    encrypted = get_setting("google_refresh_token")
    if not encrypted:
        raise RuntimeError("Google Drive غير مربوط.")
    refresh_token = decrypt_secret(encrypted)
    response = requests.post(
        TOKEN_URL,
        timeout=30,
        data={
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def create_folder(name: str, parent_id: str | None = None) -> dict[str, str]:
    token = get_access_token()
    metadata: dict[str, Any] = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        metadata["parents"] = [parent_id]
    response = requests.post(
        f"{DRIVE_API}/files",
        timeout=30,
        headers={**_headers(token), "Content-Type": "application/json"},
        params={"fields": "id,name,webViewLink", "supportsAllDrives": "true"},
        json=metadata,
    )
    response.raise_for_status()
    return response.json()


def ensure_root_folder() -> str:
    stored = get_setting("google_drive_root_folder_id")
    if stored:
        return stored
    folder = create_folder(os.getenv("GOOGLE_DRIVE_ROOT_NAME", "مرصد الإنجازات"))
    set_setting("google_drive_root_folder_id", folder["id"])
    return folder["id"]


def find_child_folder(name: str, parent_id: str) -> str | None:
    token = get_access_token()
    escaped = name.replace("'", "\\'")
    query = (
        f"name = '{escaped}' and '{parent_id}' in parents and "
        "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    response = requests.get(
        f"{DRIVE_API}/files",
        timeout=30,
        headers=_headers(token),
        params={
            "q": query,
            "fields": "files(id,name)",
            "pageSize": "10",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        },
    )
    response.raise_for_status()
    files = response.json().get("files", [])
    return files[0]["id"] if files else None


def ensure_child_folder(name: str, parent_id: str) -> str:
    existing = find_child_folder(name, parent_id)
    if existing:
        return existing
    return create_folder(name, parent_id)["id"]


def upload_file(path: Path, filename: str, mime_type: str, academic_year: str, request_id: int) -> dict[str, Any]:
    token = get_access_token()
    root = ensure_root_folder()
    year_folder = ensure_child_folder(academic_year, root)
    inbox = ensure_child_folder("01 - صندوق الوارد", year_folder)
    request_folder = ensure_child_folder(f"طلب {request_id}", inbox)

    metadata = {
        "name": filename,
        "parents": [request_folder],
        "appProperties": {"scienceLeadRequestId": str(request_id)},
    }
    init = requests.post(
        f"{DRIVE_UPLOAD_API}/files",
        timeout=30,
        headers={
            **_headers(token),
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": mime_type or "application/octet-stream",
            "X-Upload-Content-Length": str(path.stat().st_size),
        },
        params={"uploadType": "resumable", "supportsAllDrives": "true", "fields": "id,name,webViewLink,size,mimeType"},
        data=json.dumps(metadata, ensure_ascii=False).encode("utf-8"),
    )
    init.raise_for_status()
    session_uri = init.headers.get("Location")
    if not session_uri:
        raise RuntimeError("لم يعِد Google جلسة رفع قابلة للاستئناف.")

    with path.open("rb") as handle:
        upload = requests.put(
            session_uri,
            timeout=120,
            headers={"Content-Type": mime_type or "application/octet-stream"},
            data=handle,
        )
    upload.raise_for_status()
    return upload.json()


def upload_event_file(path: Path, filename: str, mime_type: str, academic_year: str, event_id: int, event_title: str) -> dict[str, Any]:
    token = get_access_token()
    root = ensure_root_folder()
    year_folder = ensure_child_folder(academic_year, root)
    events_folder = ensure_child_folder("03 - الفعاليات والتوثيق", year_folder)
    safe_title = " ".join(event_title.replace("/", "-").replace("\\", "-").split())[:80] or "فعالية"
    event_folder = ensure_child_folder(f"فعالية {event_id} - {safe_title}", events_folder)

    metadata = {
        "name": filename,
        "parents": [event_folder],
        "appProperties": {"marsadEventId": str(event_id)},
    }
    init = requests.post(
        f"{DRIVE_UPLOAD_API}/files",
        timeout=30,
        headers={
            **_headers(token),
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": mime_type or "application/octet-stream",
            "X-Upload-Content-Length": str(path.stat().st_size),
        },
        params={"uploadType": "resumable", "supportsAllDrives": "true", "fields": "id,name,webViewLink,size,mimeType"},
        data=json.dumps(metadata, ensure_ascii=False).encode("utf-8"),
    )
    init.raise_for_status()
    session_uri = init.headers.get("Location")
    if not session_uri:
        raise RuntimeError("لم يعِد Google جلسة رفع قابلة للاستئناف للفعالية.")

    with path.open("rb") as handle:
        upload = requests.put(
            session_uri,
            timeout=120,
            headers={"Content-Type": mime_type or "application/octet-stream"},
            data=handle,
        )
    upload.raise_for_status()
    return upload.json()


def download_file(file_id: str) -> tuple[bytes, str]:
    token = get_access_token()
    metadata = requests.get(
        f"{DRIVE_API}/files/{file_id}",
        timeout=30,
        headers=_headers(token),
        params={"fields": "mimeType", "supportsAllDrives": "true"},
    )
    metadata.raise_for_status()
    mime_type = metadata.json().get("mimeType") or "application/octet-stream"
    response = requests.get(
        f"{DRIVE_API}/files/{file_id}",
        timeout=120,
        headers=_headers(token),
        params={"alt": "media", "supportsAllDrives": "true"},
    )
    response.raise_for_status()
    return response.content, mime_type


def delete_file(file_id: str) -> None:
    token = get_access_token()
    response = requests.delete(
        f"{DRIVE_API}/files/{file_id}",
        timeout=30,
        headers=_headers(token),
        params={"supportsAllDrives": "true"},
    )
    if response.status_code not in {204, 404}:
        response.raise_for_status()


def status() -> dict[str, Any]:
    return {
        "configured": oauth_configured(),
        "connected": is_connected(),
        "rootFolderId": get_setting("google_drive_root_folder_id"),
        "scope": SCOPE,
        "storageMode": os.getenv("STORAGE_MODE", "auto"),
    }
