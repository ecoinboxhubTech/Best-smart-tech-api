import hashlib
import hmac
import json
import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["PAYSTACK_SECRET_KEY"] = "sk_test_dummy"
os.environ["ADMIN_API_KEY"] = "adminkey"

import pytest
from fastapi.testclient import TestClient

from app import paystack
from app.main import app

ORDER = {
    "items": [{"product_id": 3, "qty": 2}, {"product_id": 5, "qty": 1}],
    "zone_id": "lagos",
    "customer": {"name": "Ada Obi", "email": "ada@example.com", "phone": "08012345678", "address": "12 Allen Avenue, Ikeja"},
}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(paystack, "initialize", lambda **k: {"authorization_url": "https://checkout.paystack.com/abc"})
    with TestClient(app) as c:
        yield c
    from app.database import engine
    engine.dispose()  # release the file before deleting it
    if os.path.exists("test.db"):
        os.remove("test.db")


def test_products_and_total_computed_server_side(client):
    assert len(client.get("/api/products").json()) == 8
    r = client.post("/api/orders", json=ORDER)
    assert r.status_code == 201
    assert r.json()["total"] == 8500 * 2 + 3500 + 3000  # items + Lagos delivery


def test_verify_marks_paid_once_and_reduces_stock(client, monkeypatch):
    ref = client.post("/api/orders", json=ORDER).json()["reference"]
    monkeypatch.setattr(paystack, "verify", lambda r: {"status": "success", "amount": 23500 * 100, "currency": "NGN", "id": 1})
    assert client.get(f"/api/orders/{ref}/verify").json()["status"] == "paid"
    assert client.get(f"/api/orders/{ref}/verify").json()["status"] == "paid"
    stock = [p for p in client.get("/api/products").json() if p["id"] == 3]
    assert stock  # still listed


def test_wrong_amount_is_rejected(client, monkeypatch):
    ref = client.post("/api/orders", json=ORDER).json()["reference"]
    monkeypatch.setattr(paystack, "verify", lambda r: {"status": "success", "amount": 100, "currency": "NGN", "id": 2})
    assert client.get(f"/api/orders/{ref}/verify").json()["status"] == "failed"


def test_webhook_signature(client):
    ref = client.post("/api/orders", json=ORDER).json()["reference"]
    body = json.dumps({"event": "charge.success", "data": {"reference": ref, "status": "success", "amount": 23500 * 100, "currency": "NGN", "id": 9}}).encode()
    assert client.post("/api/paystack/webhook", content=body, headers={"x-paystack-signature": "bad"}).status_code == 401
    sig = hmac.new(b"sk_test_dummy", body, hashlib.sha512).hexdigest()
    assert client.post("/api/paystack/webhook", content=body, headers={"x-paystack-signature": sig}).status_code == 200
    assert client.get(f"/api/orders/{ref}").json()["status"] == "paid"


def test_admin_requires_key(client):
    assert client.get("/api/admin/orders").status_code == 401
    assert client.get("/api/admin/orders", headers={"X-Admin-Key": "adminkey"}).status_code == 200
