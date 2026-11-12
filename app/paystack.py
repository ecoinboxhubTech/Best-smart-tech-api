"""Thin Paystack client (https://paystack.com/docs/api)."""
import hashlib
import hmac

import httpx
from fastapi import HTTPException

from .config import settings


def _headers():
    if not settings.paystack_secret_key:
        raise HTTPException(503, "Payments are not configured yet.")
    return {"Authorization": f"Bearer {settings.paystack_secret_key}"}


def initialize(email: str, amount_naira: int, reference: str, callback_url: str, metadata: dict) -> dict:
    payload = {
        "email": email,
        "amount": amount_naira * 100,  # Paystack uses kobo
        "currency": "NGN",
        "reference": reference,
        "callback_url": callback_url,
        "metadata": metadata,
    }
    try:
        r = httpx.post(f"{settings.paystack_base_url}/transaction/initialize", json=payload, headers=_headers(), timeout=20)
        r.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(502, "Could not reach the payment provider. Please try again.")
    return r.json()["data"]


def verify(reference: str) -> dict:
    try:
        r = httpx.get(f"{settings.paystack_base_url}/transaction/verify/{reference}", headers=_headers(), timeout=20)
        r.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(502, "Could not verify payment right now.")
    return r.json()["data"]


def valid_signature(raw_body: bytes, signature: str | None) -> bool:
    if not signature or not settings.paystack_secret_key:
        return False
    digest = hmac.new(settings.paystack_secret_key.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(digest, signature)
