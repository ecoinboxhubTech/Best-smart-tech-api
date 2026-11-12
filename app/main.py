import hmac
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import paystack
from .config import ZONES, settings
from .database import Base, SessionLocal, engine, get_db
from .models import Order, OrderItem, Product
from .schemas import (AdminOrderOut, OrderIn, OrderOut, PaymentInit, ProductIn,
                      ProductOut, ProductPatch, StatusPatch)
from .seed import seed_products

log = logging.getLogger("store")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_products(db)
    yield


app = FastAPI(title="Best Smartech Store API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_admin(x_admin_key: str = Header(default="")):
    if not hmac.compare_digest(x_admin_key, settings.admin_api_key):
        raise HTTPException(401, "Invalid admin key.")


# ---------------------------------------------------------------- public
@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/zones")
def zones():
    return [{"id": k, **v} for k, v in ZONES.items()]


@app.get("/api/products", response_model=list[ProductOut])
def list_products(category: str | None = None, q: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Product).where(Product.active.is_(True), Product.stock > 0)
    if category and category != "All":
        stmt = stmt.where(Product.cat == category)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Product.name.ilike(like) | Product.desc.ilike(like))
    return db.scalars(stmt.order_by(Product.id)).all()


@app.post("/api/orders", response_model=PaymentInit, status_code=201)
def create_order(body: OrderIn, db: Session = Depends(get_db)):
    """Prices and totals are always computed here, never trusted from the browser."""
    zone = ZONES.get(body.zone_id)
    if not zone:
        raise HTTPException(422, "Unknown delivery zone.")

    # merge duplicate lines
    qty_by_id: dict[int, int] = {}
    for it in body.items:
        qty_by_id[it.product_id] = qty_by_id.get(it.product_id, 0) + it.qty

    products = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(qty_by_id)))}
    lines, subtotal = [], 0
    for pid, qty in qty_by_id.items():
        p = products.get(pid)
        if not p or not p.active:
            raise HTTPException(422, f"Product {pid} is not available.")
        if qty > p.stock:
            raise HTTPException(422, f"Only {p.stock} of “{p.name}” left in stock.")
        lines.append(OrderItem(product_id=p.id, name=p.name, unit_price=p.price, qty=qty))
        subtotal += p.price * qty

    c = body.customer
    order = Order(
        reference=f"BS-{uuid.uuid4().hex[:12].upper()}",
        customer_name=c.name, email=c.email, phone=c.phone, address=c.address,
        zone_id=body.zone_id, subtotal=subtotal, shipping=zone["fee"], total=subtotal + zone["fee"],
        items=lines,
    )
    db.add(order)
    db.commit()

    data = paystack.initialize(
        email=c.email,
        amount_naira=order.total,
        reference=order.reference,
        callback_url=f"{settings.frontend_url.rstrip('/')}/",
        metadata={"customer_name": c.name, "phone": c.phone},
    )
    return PaymentInit(reference=order.reference, authorization_url=data["authorization_url"], total=order.total)


def _get_order(db: Session, reference: str) -> Order:
    order = db.scalar(select(Order).where(Order.reference == reference))
    if not order:
        raise HTTPException(404, "Order not found.")
    return order


def _apply_payment(db: Session, order: Order, txn: dict) -> Order:
    """Idempotent. Marks paid only if Paystack confirms the right amount."""
    if order.status != "pending":
        return order
    if txn.get("status") == "success":
        if txn.get("amount") != order.total * 100 or txn.get("currency") != "NGN":
            log.error("Amount mismatch for %s: %s", order.reference, txn.get("amount"))
            order.status = "failed"
        else:
            order.status = "paid"
            order.paid_at = datetime.now(timezone.utc)
            order.paystack_txn_id = str(txn.get("id", ""))
            for it in order.items:  # reduce stock once
                p = db.get(Product, it.product_id)
                if p:
                    p.stock = max(0, p.stock - it.qty)
    elif txn.get("status") in ("failed", "abandoned", "reversed"):
        order.status = "failed"
    db.commit()
    return order


@app.get("/api/orders/{reference}/verify", response_model=OrderOut)
def verify_order(reference: str, db: Session = Depends(get_db)):
    """Called by the frontend when the customer returns from Paystack."""
    order = _get_order(db, reference)
    if order.status == "pending":
        _apply_payment(db, order, paystack.verify(reference))
    return order


@app.get("/api/orders/{reference}", response_model=OrderOut)
def order_status(reference: str, db: Session = Depends(get_db)):
    return _get_order(db, reference)


@app.post("/api/paystack/webhook")
async def paystack_webhook(request: Request, x_paystack_signature: str | None = Header(default=None)):
    """Set this URL in the Paystack dashboard. Confirms payments even if the customer closes the tab."""
    raw = await request.body()
    if not paystack.valid_signature(raw, x_paystack_signature):
        raise HTTPException(401, "Bad signature.")
    event = json.loads(raw)
    if event.get("event") == "charge.success":
        ref = event["data"].get("reference")
        with SessionLocal() as db:
            order = db.scalar(select(Order).where(Order.reference == ref))
            if order:
                _apply_payment(db, order, event["data"])
    return {"received": True}


# ---------------------------------------------------------------- admin
admin = [Depends(require_admin)]


@app.get("/api/admin/orders", response_model=list[AdminOrderOut], dependencies=admin)
def admin_orders(status: str | None = Query(default=None), db: Session = Depends(get_db)):
    stmt = select(Order).order_by(Order.id.desc())
    if status:
        stmt = stmt.where(Order.status == status)
    return db.scalars(stmt).all()


@app.patch("/api/admin/orders/{reference}", response_model=AdminOrderOut, dependencies=admin)
def admin_update_order(reference: str, body: StatusPatch, db: Session = Depends(get_db)):
    order = _get_order(db, reference)
    order.status = body.status
    db.commit()
    return order


@app.post("/api/admin/products", response_model=ProductOut, status_code=201, dependencies=admin)
def admin_create_product(body: ProductIn, db: Session = Depends(get_db)):
    p = Product(**body.model_dump())
    db.add(p)
    db.commit()
    return p


@app.patch("/api/admin/products/{product_id}", response_model=ProductOut, dependencies=admin)
def admin_update_product(product_id: int, body: ProductPatch, db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(404, "Product not found.")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    return p


@app.delete("/api/admin/products/{product_id}", status_code=204, dependencies=admin)
def admin_delete_product(product_id: int, db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(404, "Product not found.")
    p.active = False  # soft delete keeps old orders intact
    db.commit()
