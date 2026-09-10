"""Integração Mercado Pago e respostas seguras de pagamento."""
from __future__ import annotations

import hashlib
import hmac
import json
import urllib.error
import urllib.request
from typing import Any

try:
    from .config import MP_ACCESS_TOKEN, MP_WEBHOOK_SECRET, PAYMENT_CONFIGURED
    from .validation import clean_text
except ImportError:
    from config import MP_ACCESS_TOKEN, MP_WEBHOOK_SECRET, PAYMENT_CONFIGURED
    from validation import clean_text


def mp_request(endpoint: str, method: str = "GET", body: dict[str, Any] | None = None,
               idempotency: str | None = None) -> dict[str, Any]:
    if not PAYMENT_CONFIGURED:
        raise ValueError("O checkout ainda não está conectado à conta Mercado Pago da LIOR.")
    headers = {"Authorization": "Bearer " + MP_ACCESS_TOKEN, "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if idempotency:
        headers["X-Idempotency-Key"] = idempotency
    request = urllib.request.Request(f"https://api.mercadopago.com{endpoint}", data=data,
                                     headers=headers, method=method)
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


def safe_payment(payment: dict[str, Any]) -> dict[str, Any]:
    point = payment.get("point_of_interaction") or {}
    transaction = point.get("transaction_data") or {}
    return {
        "id": payment.get("id"), "status": payment.get("status"),
        "status_detail": payment.get("status_detail"), "payment_method_id": payment.get("payment_method_id"),
        "payment_type_id": payment.get("payment_type_id"), "transaction_amount": payment.get("transaction_amount"),
        "external_reference": payment.get("external_reference"), "date_approved": payment.get("date_approved"),
        "qr_code_base64": transaction.get("qr_code_base64"), "ticket_url": transaction.get("ticket_url"),
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
            key, value = part.strip().split("=", 1)
            parts[key] = value
    if not parts.get("ts") or not parts.get("v1") or not data_id or not request_id:
        return False
    manifest = f"id:{data_id};request-id:{request_id};ts:{parts['ts']};"
    digest = hmac.new(MP_WEBHOOK_SECRET.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, parts["v1"])
