"""Autenticação, sessões e limitação de tentativas."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

try:
    from .config import GOOGLE_CLIENT_ID, PASSWORD_ITERATIONS, SESSION_COOKIE, SESSION_SECONDS
    from .database import db
    from .validation import clean_text
except ImportError:
    from config import GOOGLE_CLIENT_ID, PASSWORD_ITERATIONS, SESSION_COOKIE, SESSION_SECONDS
    from database import db
    from validation import clean_text


def now_ts() -> int:
    return int(time.time())


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def password_verify(password: str, stored: str | None) -> bool:
    try:
        algo, iterations, salt_b64, digest_b64 = (stored or "").split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(digest_b64.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def session_from_cookie(cookie_header: str | None):
    from http.cookies import SimpleCookie
    if not cookie_header:
        return None
    cookie = SimpleCookie()
    try:
        cookie.load(cookie_header)
    except Exception:
        return None
    morsel = cookie.get(SESSION_COOKIE)
    if not morsel:
        return None
    token_hash = hashlib.sha256(morsel.value.encode()).hexdigest()
    with db() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now_ts(),))
        row = conn.execute(
            "SELECT s.*, u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>=?",
            (token_hash, now_ts()),
        ).fetchone()
        if not row:
            return None
        session_row = {key: row[key] for key in ("token_hash", "user_id", "csrf_token", "expires_at", "created_at")}
        user_row = conn.execute("SELECT * FROM users WHERE id=?", (row["user_id"],)).fetchone()
        return session_row, user_row


def create_session(user_id: int) -> tuple[str, str]:
    token = secrets.token_urlsafe(36)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    csrf = secrets.token_urlsafe(28)
    now = now_ts()
    with db() as conn:
        conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        conn.execute(
            "INSERT INTO sessions(token_hash,user_id,csrf_token,expires_at,created_at) VALUES(?,?,?,?,?)",
            (token_hash, user_id, csrf, now + SESSION_SECONDS, now),
        )
    return token, csrf


@dataclass
class RateEntry:
    count: int
    reset_at: float


_rate_lock = threading.Lock()
_rate_entries: dict[tuple[str, str], RateEntry] = {}


def rate_allowed(ip: str, bucket: str, limit: int, window: int) -> bool:
    now = time.time()
    key = (ip, bucket)
    with _rate_lock:
        entry = _rate_entries.get(key)
        if not entry or entry.reset_at <= now:
            _rate_entries[key] = RateEntry(1, now + window)
            return True
        if entry.count >= limit:
            return False
        entry.count += 1
        return True


def verify_google_token(credential: str) -> dict[str, Any]:
    params = urllib.parse.urlencode({"id_token": credential})
    request = urllib.request.Request(f"https://oauth2.googleapis.com/tokeninfo?{params}", headers={"Accept": "application/json"})
    try:
        import json
        with urllib.request.urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise ValueError("Não foi possível validar a conta Google.") from exc
    if not GOOGLE_CLIENT_ID or data.get("aud") != GOOGLE_CLIENT_ID:
        raise ValueError("A conta Google não pertence a este site.")
    if str(data.get("email_verified", "")).lower() not in {"true", "1"}:
        raise ValueError("O e-mail Google ainda não foi verificado.")
    if int(data.get("exp", 0) or 0) < now_ts():
        raise ValueError("A autenticação Google expirou.")
    return data
