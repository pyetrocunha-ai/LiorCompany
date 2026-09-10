"""Cálculo e serialização server-side de pedidos."""
from __future__ import annotations

from typing import Any

try:
    from .validation import clean_text
except ImportError:
    from validation import clean_text

PRODUCT_PRICES = {
    "dryfit-preta": 60, "alg-preta": 90, "alg-off": 90, "alg-branca": 90,
    "prem-preta": 120, "prem-branca": 120, "prem-cinza": 120,
    "over-marrom": 100, "over-branca": 100, "moletom-preto": 120,
    "comp-preto": 59, "comp-chumbo": 59, "comp-marinho": 59, "comp-branco": 59,
    "elas-branco": 45, "elas-preto": 45, "calca-preta": 70, "calca-cinza": 70,
    "cv-preta-sem": 100, "cv-chumbo-sem": 100, "cv-marinho-sem": 100,
    "cv-preta-forro": 100, "cv-verde-forro": 100,
}

SHIPPING_PRICES = {
    "pac": {"default": 24.90, "SC": 14.90, "SC:itajaí": 9.90, "PR": 18.90, "RS": 18.90,
            "SP": 22.90, "RJ": 22.90, "MG": 22.90, "ES": 22.90, "DF": 28.90,
            "GO": 28.90, "MS": 28.90, "MT": 28.90},
    "sedex": {"default": 39.90, "SC": 22.90, "SC:itajaí": 14.90, "PR": 29.90, "RS": 29.90,
              "SP": 36.90, "RJ": 36.90, "MG": 36.90, "ES": 36.90, "DF": 46.90,
              "GO": 46.90, "MS": 46.90, "MT": 46.90},
}


def calculate_freight(shipping: Any) -> float:
    """Calcula o frete a partir apenas da modalidade/destino, nunca do preço enviado."""
    if not isinstance(shipping, dict):
        return 0.0
    method = clean_text(shipping.get("type"), 12).lower()
    prices = SHIPPING_PRICES.get(method)
    if not prices:
        return 0.0
    destination = clean_text(shipping.get("destination"), 120).lower()
    state = destination.rsplit(" - ", 1)[-1].strip().upper() if " - " in destination else ""
    city = destination.rsplit(" - ", 1)[0].strip()
    return round(prices.get(f"{state}:{city}", prices.get(state, prices["default"])), 2)


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
    freight = calculate_freight(checkout.get("shipping"))
    total = max(0.01, round(subtotal - discount + freight, 2))
    return {
        "subtotal": round(subtotal, 2), "discount": round(discount, 2),
        "freight": freight, "total": total, "coupon": coupon, "items": clean_items,
    }
