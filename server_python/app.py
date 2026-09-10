#!/usr/bin/env python3
"""Servidor HTTP da LIOR.

Este módulo contém somente o adaptador HTTP. Configuração, banco, validação,
autenticação, checkout e Mercado Pago vivem nos módulos especializados.
"""
from __future__ import annotations

import hmac
import json
import mimetypes
import re
import secrets
import sqlite3
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

try:
    from . import auth, config, database, orders, payments, validation
    from .auth import (
        create_session, now_ts, password_hash, password_verify, rate_allowed,
        session_from_cookie, verify_google_token,
    )
    from .config import (
        GOOGLE_CLIENT_ID, HOST, MAX_BODY, MP_NOTIFICATION_URL, PORT,
        MP_PUBLIC_KEY, OPEN_BROWSER, PAYMENT_CONFIGURED, ROOT, SECURE_COOKIES,
        SESSION_COOKIE, SESSION_SECONDS,
    )
    from .database import db, init_db
    from .orders import calculate_checkout
    from .payments import mp_request, safe_payment, verify_mp_signature
    from .validation import (
        clean_address, clean_profile, clean_text, digits, json_load,
        normalize_email, valid_cpf, valid_email,
    )
except ImportError:
    import auth
    import config
    import database
    import orders
    import payments
    import validation
    from auth import (
        create_session, now_ts, password_hash, password_verify, rate_allowed,
        session_from_cookie, verify_google_token,
    )
    from config import (
        GOOGLE_CLIENT_ID, HOST, MAX_BODY, MP_NOTIFICATION_URL, PORT,
        MP_PUBLIC_KEY, OPEN_BROWSER, PAYMENT_CONFIGURED, ROOT, SECURE_COOKIES,
        SESSION_COOKIE, SESSION_SECONDS,
    )
    from database import db, init_db
    from orders import calculate_checkout
    from payments import mp_request, safe_payment, verify_mp_signature
    from validation import (
        clean_address, clean_profile, clean_text, digits, json_load,
        normalize_email, valid_cpf, valid_email,
    )

init_db()

def payment_order_status(status: str) -> str:
    return {
        "approved": "paid",
        "pending": "pending_payment",
        "in_process": "pending_payment",
        "rejected": "rejected",
        "cancelled": "cancelled",
        "refunded": "refunded",
        "charged_back": "refunded",
    }.get(clean_text(status, 30).lower(), "pending_payment")


def order_response(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    items = conn.execute(
        "SELECT product_id,size,quantity,unit_price,product_name FROM order_items WHERE order_id=? ORDER BY id",
        (row["id"],),
    ).fetchall()
    return {
        "id": row["public_id"], "status": row["status"], "subtotal": row["subtotal"],
        "discount": row["discount"], "freight": row["freight"], "total": row["total"],
        "coupon": row["coupon"], "shipping": json_load(row["shipping_json"]),
        "address": json_load(row["address_json"]), "paymentId": row["payment_id"],
        "createdAt": row["created_at"], "updatedAt": row["updated_at"],
        "items": [{"id": item["product_id"], "size": item["size"], "qty": item["quantity"],
                   "unitPrice": item["unit_price"], "name": item["product_name"]} for item in items],
    }


class LiorHandler(BaseHTTPRequestHandler):
    server_version = "LIOR/10"

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
            "img-src 'self' data: https:; font-src 'self' data:; "
            "connect-src 'self' https://api.mercadopago.com https://*.mercadopago.com "
            "https://accounts.google.com https://oauth2.googleapis.com https://viacep.com.br; "
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
        except ValueError as exc:
            raise ValueError("Tamanho de requisição inválido.") from exc
        if length < 0 or length > MAX_BODY:
            raise ValueError("Requisição muito grande.")
        try:
            parsed = json.loads((self.rfile.read(length) if length else b"{}").decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("JSON inválido.") from exc
        if not isinstance(parsed, dict):
            raise ValueError("JSON inválido.")
        return parsed

    def require_same_origin(self) -> None:
        origin = self.headers.get("Origin")
        if origin and urllib.parse.urlsplit(origin).netloc != self.headers.get("Host", ""):
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
        return self.set_session_cookie("").replace(f"Max-Age={SESSION_SECONDS}", "Max-Age=0")

    def user_payload(self, user: sqlite3.Row, csrf_token: str | None = None) -> dict[str, Any]:
        result = {
            "authenticated": True,
            "user": {
                "id": user["id"], "email": user["email"],
                "provider": "google" if user["google_sub"] else "email",
                "profile": json_load(user["profile_json"]),
                "address": json_load(user["address_json"]),
            },
        }
        if csrf_token:
            result["csrfToken"] = csrf_token
        return result

    def do_GET(self) -> None:
        try:
            if self.path_only == "/api/health":
                self.send_json(200, {"ok": True, "paymentConfigured": PAYMENT_CONFIGURED,
                                     "googleConfigured": bool(GOOGLE_CLIENT_ID), "server": "python"})
                return
            if self.path_only == "/api/config":
                self.send_json(200, {
                    "configured": PAYMENT_CONFIGURED,
                    "publicKey": MP_PUBLIC_KEY if PAYMENT_CONFIGURED else None,
                    "googleClientId": GOOGLE_CLIENT_ID or None,
                    "message": None if PAYMENT_CONFIGURED else
                    "Preencha as credenciais do Mercado Pago no arquivo server_python/.env.",
                })
                return
            if self.path_only == "/api/auth/me":
                current = self.current_session()
                if not current:
                    self.send_json(200, {"authenticated": False})
                else:
                    session_row, user = current
                    self.send_json(200, self.user_payload(user, str(session_row["csrf_token"])))
                return
            if self.path_only == "/api/orders":
                _, user = self.require_user()
                with db() as conn:
                    rows = conn.execute(
                        "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC, id DESC",
                        (user["id"],),
                    ).fetchall()
                    self.send_json(200, {"orders": [order_response(conn, row) for row in rows]})
                return
            match = re.fullmatch(r"/api/payments/(\d+)", self.path_only)
            if match:
                _, user = self.require_user()
                if not rate_allowed(self.client_ip(), "payment-status", 120, 60):
                    self.send_json(429, {"error": "Muitas consultas. Aguarde alguns segundos."})
                    return
                payment_id = match.group(1)
                linked_public_id = None
                with db() as conn:
                    local_payment = conn.execute(
                        "SELECT p.*,o.public_id,o.user_id FROM payments p JOIN orders o ON o.id=p.order_id "
                        "WHERE p.payment_id=?", (payment_id,),
                    ).fetchone()
                if local_payment and int(local_payment["user_id"]) != int(user["id"]):
                    raise PermissionError("Este pagamento não pertence à sua conta.")
                payment = mp_request(f"/v1/payments/{payment_id}")
                if not local_payment:
                    reference = clean_text(payment.get("external_reference"), 180)
                    with db() as conn:
                        linked = conn.execute(
                            "SELECT public_id,user_id FROM orders WHERE public_id=?",
                            (reference[5:].split("-", 1)[0],),
                        ).fetchone() if reference.startswith("LIOR-") else None
                    if not linked or int(linked["user_id"]) != int(user["id"]):
                        raise LookupError("Pagamento não encontrado para esta conta.")
                    linked_public_id = linked["public_id"]
                    with db() as conn:
                        order_row = conn.execute("SELECT id FROM orders WHERE public_id=?", (linked_public_id,)).fetchone()
                        if order_row:
                            now = now_ts()
                            conn.execute(
                                "INSERT OR IGNORE INTO payments(payment_id,order_id,status,status_detail,external_reference,"
                                "raw_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                                (payment_id, order_row["id"], clean_text(payment.get("status"), 40),
                                 clean_text(payment.get("status_detail"), 120), clean_text(payment.get("external_reference"), 180),
                                 json.dumps(payment, ensure_ascii=False), now, now),
                            )
                            conn.execute(
                                "UPDATE orders SET payment_id=COALESCE(payment_id,?),payment_status=?,status=?,updated_at=? WHERE id=?",
                                (payment_id, clean_text(payment.get("status"), 40),
                                 payment_order_status(payment.get("status", "")), now, order_row["id"]),
                            )
                result = safe_payment(payment)
                result["order_id"] = local_payment["public_id"] if local_payment else linked_public_id
                self.send_json(200, result)
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
                name, nickname = clean_text(payload.get("name"), 160), clean_text(payload.get("nickname"), 60)
                cpf, email = digits(payload.get("cpf")), normalize_email(payload.get("email"))
                phone, birth_date = clean_text(payload.get("phone"), 30), clean_text(payload.get("birthDate"), 20)
                password = str(payload.get("password") or "")
                if len(name.split()) < 2: raise ValueError("Informe o nome completo.")
                if not valid_cpf(cpf): raise ValueError("Digite um CPF válido.")
                if not valid_email(email): raise ValueError("Digite um e-mail válido.")
                if len(password) < 8 or len(password) > 128:
                    raise ValueError("A senha precisa ter entre 8 e 128 caracteres.")
                profile = clean_profile({"name": name, "nickname": nickname, "cpf": cpf, "email": email,
                                         "phone": phone, "birthDate": birth_date, "contactType": "email", "contact": email})
                now = now_ts()
                try:
                    with db() as conn:
                        user_id = int(conn.execute(
                            "INSERT INTO users(email,password_hash,profile_json,address_json,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                            (email, password_hash(password), json.dumps(profile, ensure_ascii=False), "{}", now, now),
                        ).lastrowid)
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
                email, password = normalize_email(payload.get("email")), str(payload.get("password") or "")
                with db() as conn:
                    user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
                if not user or not password_verify(password, user["password_hash"]):
                    raise PermissionError("E-mail ou senha incorretos.")
                token, csrf = create_session(int(user["id"]))
                self.send_json(200, self.user_payload(user, csrf), {"Set-Cookie": self.set_session_cookie(token)})
                return
            if self.path_only == "/api/auth/google":
                if not rate_allowed(ip, "google-login", 12, 600):
                    self.send_json(429, {"error": "Muitas tentativas. Aguarde alguns minutos."}); return
                if not GOOGLE_CLIENT_ID: raise ValueError("O login Google ainda não foi configurado.")
                data = verify_google_token(clean_text(self.read_json().get("credential"), 6000))
                email, google_sub = normalize_email(data.get("email")), clean_text(data.get("sub"), 160)
                name = clean_text(data.get("name") or data.get("given_name") or "Cliente LIOR", 160)
                now = now_ts()
                with db() as conn:
                    user = conn.execute("SELECT * FROM users WHERE email=? OR google_sub=?", (email, google_sub)).fetchone()
                    if user:
                        profile = json_load(user["profile_json"])
                        profile.update({"name": profile.get("name") or name, "email": email})
                        conn.execute("UPDATE users SET google_sub=?,profile_json=?,updated_at=? WHERE id=?",
                                     (google_sub, json.dumps(profile, ensure_ascii=False), now, user["id"]))
                        user_id = int(user["id"])
                    else:
                        profile = clean_profile({"name": name, "nickname": clean_text(data.get("given_name"), 60),
                                                 "email": email, "contactType": "email", "contact": email})
                        user_id = int(conn.execute(
                            "INSERT INTO users(email,google_sub,profile_json,address_json,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                            (email, google_sub, json.dumps(profile, ensure_ascii=False), "{}", now, now),
                        ).lastrowid)
                    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
                token, csrf = create_session(user_id)
                self.send_json(200, self.user_payload(user, csrf), {"Set-Cookie": self.set_session_cookie(token)})
                return
            if self.path_only == "/api/auth/logout":
                session, _ = self.require_user(csrf=True)
                with db() as conn: conn.execute("DELETE FROM sessions WHERE token_hash=?", (session["token_hash"],))
                self.send_json(200, {"ok": True}, {"Set-Cookie": self.clear_session_cookie()})
                return
            if self.path_only == "/api/auth/change-password":
                session, user = self.require_user(csrf=True)
                if user["google_sub"] and not user["password_hash"]: raise ValueError("Esta conta usa o login Google.")
                payload = self.read_json()
                current, new = str(payload.get("currentPassword") or ""), str(payload.get("newPassword") or "")
                if not password_verify(current, user["password_hash"]): raise PermissionError("A senha atual está incorreta.")
                if len(new) < 8 or len(new) > 128: raise ValueError("A nova senha precisa ter entre 8 e 128 caracteres.")
                with db() as conn:
                    conn.execute("UPDATE users SET password_hash=?,updated_at=? WHERE id=?", (password_hash(new), now_ts(), user["id"]))
                    conn.execute("DELETE FROM sessions WHERE user_id=? AND token_hash<>?", (user["id"], session["token_hash"]))
                self.send_json(200, {"ok": True})
                return
            if self.path_only == "/api/account/profile":
                session, user = self.require_user(csrf=True)
                profile = clean_profile(self.read_json(), json_load(user["profile_json"]))
                if profile.get("name") and len(profile["name"].split()) < 2: raise ValueError("Informe o nome completo.")
                if profile.get("cpf") and not valid_cpf(profile["cpf"]): raise ValueError("Digite um CPF válido.")
                if profile.get("contactType") == "email" and profile.get("contact") and not valid_email(profile["contact"]):
                    raise ValueError("Digite um e-mail de contato válido.")
                email = normalize_email(profile.get("email") or user["email"])
                if not valid_email(email): email = user["email"]
                profile["email"] = email
                try:
                    with db() as conn:
                        conn.execute("UPDATE users SET email=?,profile_json=?,updated_at=? WHERE id=?",
                                     (email, json.dumps(profile, ensure_ascii=False), now_ts(), user["id"]))
                        updated = conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
                except sqlite3.IntegrityError as exc:
                    raise ValueError("Este e-mail já está em uso por outra conta.") from exc
                self.send_json(200, self.user_payload(updated, str(session["csrf_token"])))
                return
            if self.path_only == "/api/account/address":
                session, user = self.require_user(csrf=True)
                address = clean_address(self.read_json(), json_load(user["address_json"]))
                if address.get("cep") and len(digits(address["cep"])) != 8: raise ValueError("Digite um CEP válido.")
                with db() as conn:
                    conn.execute("UPDATE users SET address_json=?,updated_at=? WHERE id=?",
                                 (json.dumps(address, ensure_ascii=False), now_ts(), user["id"]))
                    updated = conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
                self.send_json(200, self.user_payload(updated, str(session["csrf_token"])))
                return
            if self.path_only == "/api/orders":
                _, user = self.require_user(csrf=True)
                payload = self.read_json()
                checkout = payload.get("checkout") if isinstance(payload.get("checkout"), dict) else payload
                user_address = json_load(user["address_json"])
                checkout_address = checkout.get("address") if isinstance(checkout.get("address"), dict) else {}
                shipping_address = user_address if user_address.get("city") else checkout_address
                requested_shipping = checkout.get("shipping") if isinstance(checkout.get("shipping"), dict) else {}
                trusted_shipping = {
                    "type": clean_text(requested_shipping.get("type"), 12).lower(),
                    "destination": clean_text(shipping_address.get("city"), 120),
                    "cep": clean_text(shipping_address.get("cep"), 12),
                }
                canonical_checkout = dict(checkout)
                canonical_checkout["shipping"] = trusted_shipping
                calculated = calculate_checkout(canonical_checkout)
                public_id = f"PED{int(time.time() * 1000)}{secrets.token_hex(3).upper()}"
                shipping = {key: clean_text(trusted_shipping.get(key), 120) for key in ("type", "destination", "cep")}
                shipping["label"] = "SEDEX" if shipping["type"] == "sedex" else "PAC"
                address = shipping_address
                now = now_ts()
                with db() as conn:
                    order_db_id = int(conn.execute(
                        "INSERT INTO orders(public_id,user_id,status,subtotal,discount,freight,total,coupon,"
                        "shipping_json,address_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (public_id, user["id"], "pending_payment", calculated["subtotal"], calculated["discount"],
                         calculated["freight"], calculated["total"], calculated["coupon"],
                         json.dumps(shipping, ensure_ascii=False), json.dumps(address, ensure_ascii=False), now, now),
                    ).lastrowid)
                    conn.executemany(
                        "INSERT INTO order_items(order_id,product_id,size,quantity,unit_price,product_name) VALUES(?,?,?,?,?,?)",
                        [(order_db_id, item["id"], item["size"], item["qty"], item["unitPrice"], item["id"])
                         for item in calculated["items"]],
                    )
                    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_db_id,)).fetchone()
                    self.send_json(201, {"order": order_response(conn, row)})
                return
            if self.path_only == "/api/payments":
                _, user = self.require_user(csrf=True)
                if not rate_allowed(ip, "payment-create", 12, 300):
                    self.send_json(429, {"error": "Muitas tentativas de pagamento. Aguarde alguns minutos."}); return
                if not PAYMENT_CONFIGURED:
                    self.send_json(503, {"error": "O checkout ainda não está conectado à conta Mercado Pago da LIOR."}); return
                request_body = self.read_json()
                form_data = request_body.get("formData") or {}
                public_id = clean_text(request_body.get("orderId"), 80)
                if not isinstance(form_data, dict) or not public_id: raise ValueError("Pedido e dados de pagamento são obrigatórios.")
                with db() as conn:
                    order = conn.execute(
                        "SELECT * FROM orders WHERE public_id=? AND user_id=?", (public_id, user["id"]),
                    ).fetchone()
                    if not order:
                        raise LookupError("Pedido não encontrado para esta conta.")
                    if order["payment_id"] and order["status"] not in {"rejected", "cancelled"}:
                        raise ValueError("Este pedido já possui um pagamento.")
                    stored_items = conn.execute(
                        "SELECT product_id,size,quantity FROM order_items WHERE order_id=? ORDER BY id", (order["id"],)
                    ).fetchall()
                calculated = calculate_checkout({
                    "items": [{"id": item["product_id"], "size": item["size"], "qty": item["quantity"]}
                              for item in stored_items],
                    "coupon": order["coupon"],
                    "shipping": json_load(order["shipping_json"]),
                })
                with db() as conn:
                    conn.execute(
                        "UPDATE orders SET subtotal=?,discount=?,freight=?,total=?,updated_at=? WHERE id=?",
                        (calculated["subtotal"], calculated["discount"], calculated["freight"], calculated["total"],
                         now_ts(), order["id"]),
                    )
                method_id = clean_text(form_data.get("payment_method_id"), 60)
                if not method_id: raise ValueError("Escolha uma forma de pagamento.")
                payer = dict(form_data.get("payer") if isinstance(form_data.get("payer"), dict) else {})
                buyer = json_load(order["address_json"])
                profile = json_load(user["profile_json"])
                if not payer.get("email") and buyer.get("email"): payer["email"] = buyer["email"]
                if not payer.get("email") and profile.get("email"): payer["email"] = profile["email"]
                if not valid_email(normalize_email(payer.get("email"))): raise ValueError("Informe o e-mail do comprador no pagamento.")
                body = {"transaction_amount": calculated["total"],
                        "description": f"Pedido LIOR ({len(calculated['items'])} item(ns))",
                        "payment_method_id": method_id, "payer": payer,
                        "external_reference": f"LIOR-{public_id}",
                        "statement_descriptor": "LIOR COMPANY",
                        "metadata": {"coupon": calculated["coupon"] or None,
                                     "subtotal": calculated["subtotal"],
                                     "discount": calculated["discount"],
                                     "freight": calculated["freight"]}}
                for key in ("token", "issuer_id", "installments"):
                    if form_data.get(key): body[key] = int(form_data[key]) if key == "installments" else form_data[key]
                if MP_NOTIFICATION_URL: body["notification_url"] = MP_NOTIFICATION_URL
                retry_suffix = "-retry-" + secrets.token_hex(6) if order["payment_id"] else ""
                payment = mp_request("/v1/payments", method="POST", body=body,
                                     idempotency=f"order-{public_id}-{method_id}{retry_suffix}")
                payment_id = clean_text(payment.get("id"), 80)
                if not payment_id: raise ValueError("O processador não devolveu o identificador do pagamento.")
                payment_status = clean_text(payment.get("status"), 40)
                with db() as conn:
                    conn.execute(
                        "UPDATE orders SET payment_id=?,payment_status=?,status=?,updated_at=? WHERE id=?",
                        (payment_id, payment_status, payment_order_status(payment_status), now_ts(), order["id"]),
                    )
                    conn.execute(
                        "INSERT OR REPLACE INTO payments(payment_id,order_id,status,status_detail,external_reference,"
                        "raw_json,created_at,updated_at) VALUES(?,?,?,?,?,?,COALESCE((SELECT created_at FROM payments WHERE payment_id=?),?),?)",
                        (payment_id, order["id"], payment_status, clean_text(payment.get("status_detail"), 120),
                         clean_text(payment.get("external_reference"), 180), json.dumps(payment, ensure_ascii=False),
                         payment_id, now_ts(), now_ts()),
                    )
                result = safe_payment(payment)
                result["order_id"] = public_id
                self.send_json(201, result); return
            if self.path_only == "/api/webhooks/mercadopago":
                notification = self.read_json()
                query = dict(self.query)
                data = notification.get("data") if isinstance(notification.get("data"), dict) else {}
                payment_id = clean_text((query.get("data.id") or [""])[0] or data.get("id"), 80)
                if payment_id and not query.get("data.id"): query["data.id"] = [payment_id]
                if not verify_mp_signature(self.headers, query): self.send_text(401, "Assinatura inválida."); return
                if not payment_id or not payment_id.isdigit(): self.send_text(200, "ok"); return
                payment = mp_request(f"/v1/payments/{payment_id}")
                reference = clean_text(payment.get("external_reference"), 180)
                public_id = reference[5:] if reference.startswith("LIOR-") else ""
                with db() as conn:
                    linked_payment = conn.execute(
                        "SELECT order_id FROM payments WHERE payment_id=?", (payment_id,)
                    ).fetchone()
                    linked = conn.execute(
                        "SELECT * FROM orders WHERE id=?", (linked_payment["order_id"],)
                    ).fetchone() if linked_payment else None
                    if not linked and public_id:
                        linked = conn.execute(
                            "SELECT * FROM orders WHERE public_id=?", (public_id,)
                        ).fetchone()
                    if linked:
                        status = clean_text(payment.get("status"), 40)
                        now = now_ts()
                        conn.execute(
                            "INSERT OR REPLACE INTO payments(payment_id,order_id,status,status_detail,external_reference,"
                            "raw_json,created_at,updated_at) VALUES(?,?,?,?,?,?,COALESCE((SELECT created_at FROM payments WHERE payment_id=?),?),?)",
                            (payment_id, linked["id"], status, clean_text(payment.get("status_detail"), 120),
                             reference, json.dumps(payment, ensure_ascii=False), payment_id, now, now),
                        )
                        conn.execute(
                            "UPDATE orders SET payment_id=?,payment_status=?,status=?,updated_at=? WHERE id=?",
                            (payment_id, status, payment_order_status(status), now, linked["id"]),
                        )
                self.send_text(200, "ok"); return
            if self.path_only.startswith("/api/"): self.send_json(404, {"error": "Rota não encontrada."}); return
            self.send_text(405, "Método não permitido.")
        except Exception as exc:
            self.handle_error(exc)

    def handle_error(self, exc: Exception) -> None:
        status = 403 if isinstance(exc, PermissionError) else 401 if isinstance(exc, LookupError) else 400 if isinstance(exc, ValueError) else 500
        if status == 500: print("[LIOR ERROR]", repr(exc))
        message = str(exc) if status < 500 and str(exc) else "Não foi possível concluir a operação."
        self.send_json(status, {"error": clean_text(message, 220)})

    def serve_static(self) -> None:
        path = urllib.parse.unquote(self.path_only)
        candidate = (ROOT / ("index.html" if path == "/" else path.lstrip("/"))).resolve()
        try: candidate.relative_to(ROOT)
        except ValueError: self.send_text(403, "Acesso negado."); return
        if not candidate.exists() or not candidate.is_file(): candidate = ROOT / "index.html"
        mime = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", mime + ("; charset=utf-8" if mime.startswith("text/") or mime in {"application/javascript", "application/json"} else ""))
        self.send_header("Content-Length", str(candidate.stat().st_size))
        self.send_header("Cache-Control", "no-cache" if candidate.suffix in {".html", ".js", ".css"} else "public, max-age=86400")
        self.end_headers()
        if self.command != "HEAD":
            with candidate.open("rb") as stream:
                while chunk := stream.read(64 * 1024): self.wfile.write(chunk)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), LiorHandler)
    browser_host = "127.0.0.1" if HOST in {"0.0.0.0", "::"} else HOST
    browser_url = f"http://{browser_host}:{PORT}"
    print(f"LIOR disponível em {browser_url}")
    print("Servidor Python seguro ativo.")
    print("Mantenha esta janela aberta enquanto estiver usando a loja.")
    print("Mercado Pago configurado." if PAYMENT_CONFIGURED else "Mercado Pago não configurado: preencha server_python/.env.")
    print("Google configurado." if GOOGLE_CLIENT_ID else "Google não configurado: preencha GOOGLE_CLIENT_ID.")
    if OPEN_BROWSER: threading.Timer(1.0, lambda: webbrowser.open(browser_url, new=2)).start()
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == "__main__":
    main()
