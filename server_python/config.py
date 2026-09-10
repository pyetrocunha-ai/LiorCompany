"""Configuração central do servidor LIOR."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATHS = [ROOT / "server_python" / ".env", ROOT / "server" / ".env"]


def load_env() -> None:
    for env_path in ENV_PATHS:
        if not env_path.exists():
            continue
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()
PORT = int(os.getenv("PORT", "3000"))
HOST = "0.0.0.0" if os.getenv("PORT") else (os.getenv("HOST", "127.0.0.1").strip() or "127.0.0.1")
DB_PATH = Path(os.getenv("LIOR_DB_PATH", str(ROOT / "data" / "lior.db")))
try:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
except OSError:
    DB_PATH = Path("/tmp/lior.db")
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

SESSION_COOKIE = "lior_session"
SESSION_SECONDS = 60 * 60 * 24 * 14
MAX_BODY = 200_000
PASSWORD_ITERATIONS = 310_000
