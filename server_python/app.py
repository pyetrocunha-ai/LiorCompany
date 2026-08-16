#!/usr/bin/env python3
"""Servidor seguro LIOR (biblioteca padrão do Python).

- Arquivos estáticos
- Conta de cliente com SQLite, PBKDF2, cookie HttpOnly e CSRF
- Login Google validado no servidor
- Checkout Mercado Pago (Pix/crédito/débito) por API
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ENV_PATHS = [ROOT / "server_python" / ".env", ROOT / "server" / ".env"]
DB_PATH = Path(os.getenv("LIOR_DB_PATH", str(ROOT / "data" / "lior.db")))
PORT = int(os.getenv("PORT", "3000"))
SESSION_COOKIE = "lior_session"
SESSION_SECONDS = 60 * 60 * 24 * 14
MAX_BODY = 200_000
PASSWORD_ITERATIONS = 310_000

PRODUCT_PRICES = {
    "dryfit-preta": 60,
    "alg-preta": 90,
    "alg-off": 90,
    "alg-branca": 90,
    "prem-preta": 120,
    "prem-branca": 120,
    "prem-cinza": 120,
    "over-marrom": 100,
    "over-branca": 100,
    "moletom-preto": 120,
    "comp-preto": 59,
    "comp-chumbo": 59,
    "comp-marinho": 59,
    "comp-branco": 59,
    "elas-branco": 45,
    "elas-preto": 45,
    "calca-preta": 70,
    "calca-cinza": 70,
    "cv-preta-sem": 100,
    "cv-chumbo-sem": 100,
    "cv-marinho-sem": 100,
    "cv-preta-forro": 100,
    "cv-verde-forro": 100,
}


def load_env() -> None:
    for env_path in ENV_PATHS:
        if not env_path.exists():
            continue
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


load_env()
PORT = int(os.getenv("PORT", "3000"))
HOST = os.getenv("HOST", "127.0.0.1").strip() or "127.0.0.1"
DB_PATH = Path(os.getenv("LIOR_DB_PATH", str(ROOT / "data" / "lior.db")))
OPEN_BROWSER = os.getenv("OPEN_BROWSER", "1" if os.name == "nt" else "0").strip().lower() in {"1", "true", "yes", "sim"}
MP_PUBLIC_KEY = os.getenv("MP_PUBLIC_KEY", "").strip()
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "").strip()
MP_NOTIFICATION_URL = os.getenv("MP_NOTIFICATION_URL", "").strip()
MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET", "").strip()
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
SECURE_COOKIES = os.getenv("SECURE_COOKIES", "auto").lower()
PAYMENT_CONFIGURED = bool(
    MP_PUBLIC_KEY
    and MP_ACCESS_TOKEN
    and "COLOQUE" not in MP_PUBLIC_KEY.upper()
    and "COLOQUE" not in MP_ACCESS_TOKEN.upper()
)

DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=8)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              email TEXT NOT NULL UNIQUE COLLATE NOCASE,
              password_hash TEXT,
              google_sub TEXT UNIQUE,
              profile_json TEXT NOT NULL DEFAULT '{}',
              address_json TEXT NOT NULL DEFAULT '{}',
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
              token_hash TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              csrf_token TEXT NOT NULL,
              expires_at INTEGER NOT NULL,
              created_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
            """
        )


init_db()


def now_ts() -> int:
    return int(time.time())


def normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def valid_email(value: str) -> bool:
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value)) and len(value) <= 254


def digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def valid_cpf(value: Any) -> bool:
    cpf = digits(value)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    total = sum(int(cpf[i]) * (10 - i) for i in range(9))
    check = (total * 10) % 11
    check = 0 if check == 10 else check
    if check != int(cpf[9]):
        return False
    total = sum(int(cpf[i]) * (11 - i) for i in range(10))
    check = (total * 10) % 11
    check = 0 if check == 10 else check
    return check == int(cpf[10])


def json_load(value: str | None) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def clean_text(value: Any, limit: int = 180) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]", "", str(value or "")).strip()
    return text[:limit]


def clean_profile(payload: dict[str, Any], current: dict[str, Any] | None = None) -> dict[str, Any]:
    base = dict(current or {})
    allowed = {
        "name": 160,
        "nickname": 60,
        "cpf": 14,
        "email": 254,
        "phone": 30,
        "birthDate": 20,
        "contactType": 20,
        "contact": 254,
        "maritalStatus": 40,
        "gender": 40,
        "preferredPayment": 40,
    }
    for key, limit in allowed.items():
        if key in payload:
            base[key] = clean_text(payload.get(key), limit)
    if base.get("email"):
        base["email"] = normalize_email(base["email"])
    if base.get("cpf"):
        base["cpf"] = digits(base["cpf"])
    if base.get("contactType") not in {"email", "phone"}:
        base["contactType"] = "email"
    if base.get("gender") not in {"Homem", "Mulher", "Prefiro não dizer", ""}:
        base["gender"] = ""
    return base


def clean_address(payload: dict[str, Any], current: dict[str, Any] | None = None) -> dict[str, Any]:
    base = dict(current or {})
    for key, limit in {
        "cep": 9,
        "recipient": 160,
        "street": 180,
        "number": 30,
        "complement": 120,
        "reference": 180,
        "district": 120,
        "city": 120,
    }.items():
        if key in payload:
            base[key] = clean_text(payload.get(key), limit)
    return base


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


def session_from_cookie(cookie_header: str | None) -> tuple[sqlite3.Row, sqlite3.Row] | None:
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
        return sqlite3.Row(sqlite3.Cursor(conn), tuple(session_row.values())) if False else (session_row, user_row)  # type: ignore[return-value]


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


def mp_request(endpoint: str, method: str = "GET", body: dict[str, Any] | None = None, idempotency: str | None = None) -> dict[str, Any]:
    if not PAYMENT_CONFIGURED:
        raise ValueError("O checkout ainda não está conectado à conta Mercado Pago da LIOR.")
    headers = {"Authorization": f"Bearer {MP_ACCESS_TOKEN}", "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if idempotency:
        headers["X-Idempotency-Key"] = idempotency
    request = urllib.request.Request(f"https://api.mercadopago.com{endpoint}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"message": "Falha no processador de pagamento."}
        message = payload.get("message") or "Não foi possível processar o pagamento."
        causes = payload.get("cause")
        if isinstance(causes, list) and causes and isinstance(causes[0], dict):
            message = causes[0].get("description") or message
        raise ValueError(clean_text(message, 220)) from exc


def calculate_checkout(checkout: dict[str, Any]) -> dict[str, Any]:
    items = checkout.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("A sacola está vazia.")
    subtotal = 0.0
    clean_items = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Um produto da sacola não é válido.")
        product_id = clean_text(item.get("id"), 60)
        unit = PRODUCT_PRICES.get(product_id)
        if unit is None:
            raise ValueError("Um produto da sacola não é válido.")
        try:
            qty = max(1, min(6, int(item.get("qty", 1))))
        except (ValueError, TypeError):
            qty = 1
        subtotal += unit * qty
        clean_items.append({"id": product_id, "qty": qty, "size": clean_text(item.get("size"), 12), "unitPrice": unit})
    coupon = clean_text(checkout.get("coupon"), 30).upper()
    discount = subtotal * 0.10 if coupon == "LIOR10" else 0.0
    try:
        freight = max(0.0, min(200.0, round(float(checkout.get("freight", 0) or 0), 2)))
    except (ValueError, TypeError):
        freight = 0.0
    total = max(0.01, round(subtotal - discount + freight, 2))
    return {
        "subtotal": round(subtotal, 2),
        "discount": round(discount, 2),
        "freight": freight,
        "total": total,
        "coupon": coupon,
        "items": clean_items,
    }


def safe_payment(payment: dict[str, Any]) -> dict[str, Any]:
    point = payment.get("point_of_interaction") or {}
    transaction = point.get("transaction_data") or {}
    return {
        "id": payment.get("id"),
        "status": payment.get("status"),
        "status_detail": payment.get("status_detail"),
        "payment_method_id": payment.get("payment_method_id"),
        "payment_type_id": payment.get("payment_type_id"),
        "transaction_amount": payment.get("transaction_amount"),
        "external_reference": payment.get("external_reference"),
        "date_approved": payment.get("date_approved"),
        "qr_code_base64": transaction.get("qr_code_base64"),
        "ticket_url": transaction.get("ticket_url"),
    }


def verify_mp_signature(headers: Any, query: dict[str, list[str]]) -> bool:
    if not MP_WEBHOOK_SECRET:
        return True
    signature = headers.get("x-signature", "")
    request_id = headers.get("x-request-id", "")
    data_id = (query.get("data.id") or [""])[0]
    parts = {}
    for part in signature.split(","):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            parts[k] = v
    if not parts.get("ts") or not parts.get("v1") or not data_id or not request_id:
        return False
    manifest = f"id:{data_id};request-id:{request_id};ts:{parts['ts']};"
    digest = hmac.new(MP_WEBHOOK_SECRET.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, parts["v1"])


def verify_google_token(credential: str) -> dict[str, Any]:
    params = urllib.parse.urlencode({"id_token": credential})
    request = urllib.request.Request(f"https://oauth2.googleapis.com/tokeninfo?{params}", headers={"Accept": "application/json"})
    try:
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


class LiorHandler(BaseHTTPRequestHandler):
    server_version = "LIOR/9"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{datetime.now().isoformat(timespec='seconds')}] {self.client_address[0]} {fmt % args}")

    @property
    def path_only(self) -> str:
        return urllib.parse.urlsplit(self.path).path

    @property
    def query(self) -> dict[str, list[str]]:
        return urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query, keep_blank_values=True)

    def client_ip(self) -> str:
        forwarded = self.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        return forwarded or self.client_address[0]

    def is_https(self) -> bool:
        if SECURE_COOKIES == "true":
            return True
        if SECURE_COOKIES == "false":
            return False
        return self.headers.get("X-Forwarded-Proto", "").lower() == "https"

    def security_headers(self) -> dict[str, str]:
        csp = (
            "default-src 'self'; "
            "script-src 'self' https://sdk.mercadopago.com https://accounts.google.com https://www.gstatic.com; "
            "style-src 'self' 'unsafe-inline' https://accounts.google.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https://api.mercadopago.com https://*.mercadopago.com https://accounts.google.com https://oauth2.googleapis.com https://viacep.com.br; "
            "frame-src https://*.mercadopago.com https://*.mercadolibre.com https://accounts.google.com; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'self'; form-action 'self'"
        )
        headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "SAMEORIGIN",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(self)",
            "Content-Security-Policy": csp,
            "Cross-Origin-Opener-Policy": "same-origin-allow-popups",
        }
        if self.is_https():
            headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return headers

    def end_headers(self) -> None:
        for key, value in self.security_headers().items():
            self.send_header(key, value)
        super().end_headers()

    def send_json(self, status: int, payload: dict[str, Any], extra: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_text(self, status: int, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Tamanho de requisição inválido.")
        if length < 0 or length > MAX_BODY:
            raise ValueError("Requisição muito grande.")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("JSON inválido.") from exc
        if not isinstance(parsed, dict):
            raise ValueError("JSON inválido.")
        return parsed

    def require_same_origin(self) -> None:
        origin = self.headers.get("Origin")
        if not origin:
            return
        host = self.headers.get("Host", "")
        parsed = urllib.parse.urlsplit(origin)
        if parsed.netloc != host:
            raise PermissionError("Origem não autorizada.")

    def current_session(self) -> tuple[dict[str, Any], sqlite3.Row] | None:
        return session_from_cookie(self.headers.get("Cookie"))

    def require_user(self, csrf: bool = False) -> tuple[dict[str, Any], sqlite3.Row]:
        current = self.current_session()
        if not current:
            raise LookupError("Faça login para continuar.")
        session_row, user = current
        if csrf:
            token = self.headers.get("X-CSRF-Token", "")
            if not token or not hmac.compare_digest(token, str(session_row["csrf_token"])):
                raise PermissionError("Sessão inválida. Atualize a página e tente novamente.")
        return session_row, user

    def set_session_cookie(self, token: str) -> str:
        parts = [f"{SESSION_COOKIE}={token}", "Path=/", "HttpOnly", "SameSite=Lax", f"Max-Age={SESSION_SECONDS}"]
        if self.is_https():
            parts.append("Secure")
        return "; ".join(parts)

    def clear_session_cookie(self) -> str:
        parts = [f"{SESSION_COOKIE}=", "Path=/", "HttpOnly", "SameSite=Lax", "Max-Age=0"]
        if self.is_https():
            parts.append("Secure")
        return "; ".join(parts)

    def user_payload(self, user: sqlite3.Row, csrf_token: str | None = None) -> dict[str, Any]:
        profile = json_load(user["profile_json"])
        address = json_load(user["address_json"])
        result = {
            "authenticated": True,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "provider": "google" if user["google_sub"] else "email",
                "profile": profile,
                "address": address,
            },
        }
        if csrf_token:
            result["csrfToken"] = csrf_token
        return result

    def do_GET(self) -> None:
        try:
            if self.path_only == "/api/health":
                self.send_json(200, {"ok": True, "paymentConfigured": PAYMENT_CONFIGURED, "googleConfigured": bool(GOOGLE_CLIENT_ID), "server": "python"})
                return
            if self.path_only == "/api/config":
                self.send_json(
                    200,
                    {
                        "configured": PAYMENT_CONFIGURED,
                        "publicKey": MP_PUBLIC_KEY if PAYMENT_CONFIGURED else None,
                        "googleClientId": GOOGLE_CLIENT_ID or None,
                        "message": None if PAYMENT_CONFIGURED else "Preencha as credenciais do Mercado Pago no arquivo server_python/.env.",
                    },
                )
                return
            if self.path_only == "/api/auth/me":
                current = self.current_session()
                if not current:
                    self.send_json(200, {"authenticated": False})
                    return
                session_row, user = current
                self.send_json(200, self.user_payload(user, str(session_row["csrf_token"])))
                return
            match = re.fullmatch(r"/api/payments/(\d+)", self.path_only)
            if match:
                if not rate_allowed(self.client_ip(), "payment-status", 120, 60):
                    self.send_json(429, {"error": "Muitas consultas. Aguarde alguns segundos."})
                    return
                payment = mp_request(f"/v1/payments/{match.group(1)}")
                self.send_json(200, safe_payment(payment))
                return
            if self.path_only.startswith("/api/"):
                self.send_json(404, {"error": "Rota não encontrada."})
                return
            self.serve_static()
        except Exception as exc:
            self.handle_error(exc)

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_POST(self) -> None:
        try:
            if self.path_only != "/api/webhooks/mercadopago":
                self.require_same_origin()
            ip = self.client_ip()
            if self.path_only == "/api/auth/register":
                if not rate_allowed(ip, "register", 6, 600):
                    self.send_json(429, {"error": "Muitas tentativas. Aguarde alguns minutos."})
                    return
                payload = self.read_json()
                name = clean_text(payload.get("name"), 160)
                nickname = clean_text(payload.get("nickname"), 60)
                cpf = digits(payload.get("cpf"))
                email = normalize_email(payload.get("email"))
                phone = clean_text(payload.get("phone"), 30)
                birth_date = clean_text(payload.get("birthDate"), 20)
                password = str(payload.get("password") or "")
                if len(name.split()) < 2:
                    raise ValueError("Informe o nome completo.")
                if not valid_cpf(cpf):
                    raise ValueError("Digite um CPF válido.")
                if not valid_email(email):
                    raise ValueError("Digite um e-mail válido.")
                if len(password) < 8 or len(password) > 128:
                    raise ValueError("A senha precisa ter entre 8 e 128 caracteres.")
                profile = clean_profile({"name": name, "nickname": nickname, "cpf": cpf, "email": email, "phone": phone, "birthDate": birth_date, "contactType": "email", "contact": email})
                now = now_ts()
                try:
                    with db() as conn:
                        cur = conn.execute(
                            "INSERT INTO users(email,password_hash,profile_json,address_json,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                            (email, password_hash(password), json.dumps(profile, ensure_ascii=False), "{}", now, now),
                        )
                        user_id = int(cur.lastrowid)
                except sqlite3.IntegrityError as exc:
                    raise ValueError("Já existe uma conta com esse e-mail.") from exc
                token, csrf = create_session(user_id)
                with db() as conn:
                    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
                self.send_json(201, self.user_payload(user, csrf), {"Set-Cookie": self.set_session_cookie(token)})
                return
            if self.path_only == "/api/auth/login":
                if not rate_allowed(ip, "login", 10, 600):
                    self.send_json(429, {"error": "Muitas tentativas. Aguarde alguns minutos."})
                    return
                payload = self.read_json()
                email = normalize_email(payload.get("email"))
                password = str(payload.get("password") or "")
                with db() as conn:
                    user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
                if not user or not password_verify(password, user["password_hash"]):
                    raise PermissionError("E-mail ou senha incorretos.")
                token, csrf = create_session(int(user["id"]))
                self.send_json(200, self.user_payload(user, csrf), {"Set-Cookie": self.set_session_cookie(token)})
                return
            if self.path_only == "/api/auth/google":
                if not rate_allowed(ip, "google-login", 12, 600):
                    self.send_json(429, {"error": "Muitas tentativas. Aguarde alguns minutos."})
                    return
                if not GOOGLE_CLIENT_ID:
                    raise ValueError("O login Google ainda não foi configurado.")
                credential = clean_text(self.read_json().get("credential"), 6000)
                data = verify_google_token(credential)
                email = normalize_email(data.get("email"))
                google_sub = clean_text(data.get("sub"), 160)
                name = clean_text(data.get("name") or data.get("given_name") or "Cliente LIOR", 160)
                now = now_ts()
                with db() as conn:
                    user = conn.execute("SELECT * FROM users WHERE email=? OR google_sub=?", (email, google_sub)).fetchone()
                    if user:
                        profile = json_load(user["profile_json"])
                        if not profile.get("name"):
                            profile["name"] = name
                        profile["email"] = email
                        conn.execute("UPDATE users SET google_sub=?,profile_json=?,updated_at=? WHERE id=?", (google_sub, json.dumps(profile, ensure_ascii=False), now, user["id"]))
                        user_id = int(user["id"])
                    else:
                        profile = clean_profile({"name": name, "nickname": clean_text(data.get("given_name"), 60), "email": email, "contactType": "email", "contact": email})
                        cur = conn.execute(
                            "INSERT INTO users(email,google_sub,profile_json,address_json,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                            (email, google_sub, json.dumps(profile, ensure_ascii=False), "{}", now, now),
                        )
                        user_id = int(cur.lastrowid)
                    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
                token, csrf = create_session(user_id)
                self.send_json(200, self.user_payload(user, csrf), {"Set-Cookie": self.set_session_cookie(token)})
                return
            if self.path_only == "/api/auth/logout":
                session_row, _user = self.require_user(csrf=True)
                with db() as conn:
                    conn.execute("DELETE FROM sessions WHERE token_hash=?", (session_row["token_hash"],))
                self.send_json(200, {"ok": True}, {"Set-Cookie": self.clear_session_cookie()})
                return
            if self.path_only == "/api/auth/change-password":
                session_row, user = self.require_user(csrf=True)
                if user["google_sub"] and not user["password_hash"]:
                    raise ValueError("Esta conta usa o login Google.")
                payload = self.read_json()
                current = str(payload.get("currentPassword") or "")
                new_password = str(payload.get("newPassword") or "")
                if not password_verify(current, user["password_hash"]):
                    raise PermissionError("A senha atual está incorreta.")
                if len(new_password) < 8 or len(new_password) > 128:
                    raise ValueError("A nova senha precisa ter entre 8 e 128 caracteres.")
                with db() as conn:
                    conn.execute("UPDATE users SET password_hash=?,updated_at=? WHERE id=?", (password_hash(new_password), now_ts(), user["id"]))
                    conn.execute("DELETE FROM sessions WHERE user_id=? AND token_hash<>?", (user["id"], session_row["token_hash"]))
                self.send_json(200, {"ok": True})
                return
            if self.path_only == "/api/account/profile":
                _session, user = self.require_user(csrf=True)
                payload = self.read_json()
                current = json_load(user["profile_json"])
                profile = clean_profile(payload, current)
                if profile.get("name") and len(profile["name"].split()) < 2:
                    raise ValueError("Informe o nome completo.")
                if profile.get("cpf") and not valid_cpf(profile["cpf"]):
                    raise ValueError("Digite um CPF válido.")
                contact = profile.get("contact", "")
                if profile.get("contactType") == "email" and contact and not valid_email(contact):
                    raise ValueError("Digite um e-mail de contato válido.")
                email = normalize_email(profile.get("email") or user["email"])
                if not valid_email(email):
                    email = user["email"]
                profile["email"] = email
                try:
                    with db() as conn:
                        conn.execute("UPDATE users SET email=?,profile_json=?,updated_at=? WHERE id=?", (email, json.dumps(profile, ensure_ascii=False), now_ts(), user["id"]))
                        updated = conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
                except sqlite3.IntegrityError as exc:
                    raise ValueError("Este e-mail já está em uso por outra conta.") from exc
                self.send_json(200, self.user_payload(updated, str(_session["csrf_token"])))
                return
            if self.path_only == "/api/account/address":
                session_row, user = self.require_user(csrf=True)
                address = clean_address(self.read_json(), json_load(user["address_json"]))
                if address.get("cep") and len(digits(address["cep"])) != 8:
                    raise ValueError("Digite um CEP válido.")
                with db() as conn:
                    conn.execute("UPDATE users SET address_json=?,updated_at=? WHERE id=?", (json.dumps(address, ensure_ascii=False), now_ts(), user["id"]))
                    updated = conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
                self.send_json(200, self.user_payload(updated, str(session_row["csrf_token"])))
                return
            if self.path_only == "/api/payments":
                if not rate_allowed(ip, "payment-create", 12, 300):
                    self.send_json(429, {"error": "Muitas tentativas de pagamento. Aguarde alguns minutos."})
                    return
                if not PAYMENT_CONFIGURED:
                    self.send_json(503, {"error": "O checkout ainda não está conectado à conta Mercado Pago da LIOR."})
                    return
                request_body = self.read_json()
                form_data = request_body.get("formData") or {}
                checkout = request_body.get("checkout") or {}
                if not isinstance(form_data, dict) or not isinstance(checkout, dict):
                    raise ValueError("Dados de pagamento inválidos.")
                calculated = calculate_checkout(checkout)
                method_id = clean_text(form_data.get("payment_method_id"), 60)
                if not method_id:
                    raise ValueError("Escolha uma forma de pagamento.")
                payer = form_data.get("payer") if isinstance(form_data.get("payer"), dict) else {}
                payer = dict(payer)
                buyer = checkout.get("buyer") if isinstance(checkout.get("buyer"), dict) else {}
                if not payer.get("email") and buyer.get("email"):
                    payer["email"] = buyer.get("email")
                if not valid_email(normalize_email(payer.get("email"))):
                    raise ValueError("Informe o e-mail do comprador no pagamento.")
                external_reference = f"LIOR-{int(time.time() * 1000)}-{secrets.token_hex(4)}"
                body = {
                    "transaction_amount": calculated["total"],
                    "description": f"Pedido LIOR ({len(calculated['items'])} item(ns))",
                    "payment_method_id": method_id,
                    "payer": payer,
                    "external_reference": external_reference,
                    "statement_descriptor": "LIOR COMPANY",
                    "metadata": {
                        "coupon": calculated["coupon"] or None,
                        "subtotal": calculated["subtotal"],
                        "discount": calculated["discount"],
                        "freight": calculated["freight"],
                    },
                }
                for src, dst in (("token", "token"), ("issuer_id", "issuer_id")):
                    if form_data.get(src):
                        body[dst] = form_data[src]
                if form_data.get("installments"):
                    body["installments"] = int(form_data["installments"])
                if MP_NOTIFICATION_URL:
                    body["notification_url"] = MP_NOTIFICATION_URL
                payment = mp_request("/v1/payments", method="POST", body=body, idempotency=secrets.token_hex(16))
                self.send_json(201, safe_payment(payment))
                return
            if self.path_only == "/api/webhooks/mercadopago":
                if not verify_mp_signature(self.headers, self.query):
                    self.send_text(401, "Assinatura inválida.")
                    return
                self.send_text(200, "ok")
                return
            if self.path_only.startswith("/api/"):
                self.send_json(404, {"error": "Rota não encontrada."})
                return
            self.send_text(405, "Método não permitido.")
        except Exception as exc:
            self.handle_error(exc)

    def handle_error(self, exc: Exception) -> None:
        if isinstance(exc, PermissionError):
            status = 403
        elif isinstance(exc, LookupError):
            status = 401
        elif isinstance(exc, ValueError):
            status = 400
        else:
            status = 500
            print("[LIOR ERROR]", repr(exc))
        message = str(exc) if status < 500 and str(exc) else "Não foi possível concluir a operação."
        self.send_json(status, {"error": clean_text(message, 220)})

    def serve_static(self) -> None:
        path = urllib.parse.unquote(self.path_only)
        relative = "index.html" if path == "/" else path.lstrip("/")
        candidate = (ROOT / relative).resolve()
        try:
            candidate.relative_to(ROOT)
        except ValueError:
            self.send_text(403, "Acesso negado.")
            return
        if not candidate.exists() or not candidate.is_file():
            candidate = ROOT / "index.html"
        mime = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        stat = candidate.stat()
        self.send_response(200)
        self.send_header("Content-Type", mime + ("; charset=utf-8" if mime.startswith("text/") or mime in {"application/javascript", "application/json"} else ""))
        self.send_header("Content-Length", str(stat.st_size))
        if candidate.suffix in {".html", ".js", ".css"}:
            self.send_header("Cache-Control", "no-cache")
        else:
            self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        if self.command != "HEAD":
            with candidate.open("rb") as fh:
                while chunk := fh.read(64 * 1024):
                    self.wfile.write(chunk)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), LiorHandler)
    browser_host = "127.0.0.1" if HOST in {"0.0.0.0", "::"} else HOST
    browser_url = f"http://{browser_host}:{PORT}"
    print(f"LIOR disponível em {browser_url}")
    print("Servidor Python seguro ativo.")
    print("Mantenha esta janela aberta enquanto estiver usando a loja.")
    print("Mercado Pago configurado." if PAYMENT_CONFIGURED else "Mercado Pago não configurado: preencha server_python/.env.")
    print("Google configurado." if GOOGLE_CLIENT_ID else "Google não configurado: preencha GOOGLE_CLIENT_ID.")
    if OPEN_BROWSER:
        threading.Timer(1.0, lambda: webbrowser.open(browser_url, new=2)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
