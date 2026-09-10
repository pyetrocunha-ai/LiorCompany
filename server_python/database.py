"""Persistência SQLite e inicialização do schema."""
from __future__ import annotations

import sqlite3

try:
    from .config import DB_PATH
except ImportError:
    from config import DB_PATH

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
            CREATE TABLE IF NOT EXISTS orders (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              public_id TEXT NOT NULL UNIQUE,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              status TEXT NOT NULL DEFAULT 'pending_payment',
              subtotal REAL NOT NULL,
              discount REAL NOT NULL DEFAULT 0,
              freight REAL NOT NULL DEFAULT 0,
              total REAL NOT NULL,
              coupon TEXT NOT NULL DEFAULT '',
              shipping_json TEXT NOT NULL DEFAULT '{}',
              address_json TEXT NOT NULL DEFAULT '{}',
              payment_id TEXT,
              payment_status TEXT,
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_orders_user_created ON orders(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_orders_payment ON orders(payment_id);
            CREATE TABLE IF NOT EXISTS order_items (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
              product_id TEXT NOT NULL,
              size TEXT NOT NULL DEFAULT '',
              quantity INTEGER NOT NULL,
              unit_price REAL NOT NULL,
              product_name TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
            CREATE TABLE IF NOT EXISTS payments (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              payment_id TEXT NOT NULL UNIQUE,
              order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
              status TEXT NOT NULL DEFAULT 'pending',
              status_detail TEXT NOT NULL DEFAULT '',
              external_reference TEXT NOT NULL DEFAULT '',
              raw_json TEXT NOT NULL DEFAULT '{}',
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id);
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version INTEGER PRIMARY KEY,
              applied_at INTEGER NOT NULL
            );
            """
        )
        # Schema v2 adds server-side order snapshots and payment linkage.
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(2, strftime('%s','now'))"
        )
        conn.execute("PRAGMA user_version = 2")
