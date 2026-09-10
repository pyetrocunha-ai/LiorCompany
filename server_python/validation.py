"""Normalização e validações compartilhadas pelas rotas."""
from __future__ import annotations

import json
import re
from typing import Any


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
        "name": 160, "nickname": 60, "cpf": 14, "email": 254, "phone": 30,
        "birthDate": 20, "contactType": 20, "contact": 254, "maritalStatus": 40,
        "gender": 40, "preferredPayment": 40,
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
        "cep": 9, "recipient": 160, "street": 180, "number": 30,
        "complement": 120, "reference": 180, "district": 120, "city": 120,
    }.items():
        if key in payload:
            base[key] = clean_text(payload.get(key), limit)
    return base
