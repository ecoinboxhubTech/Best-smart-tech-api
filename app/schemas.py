from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    cat: str
    price: int
    was: int
    rating: float
    reviews: int
    desc: str
    tint: str
    mark: str
    image: str | None = None


class ProductIn(BaseModel):
    name: str
    cat: str
    price: int = Field(gt=0)
    was: int = Field(gt=0)
    rating: float = 0
    reviews: int = 0
    desc: str = ""
    tint: str = "#E3EDEA"
    mark: str = ""
    image: str | None = None
    stock: int = Field(default=100, ge=0)


class ProductPatch(BaseModel):
    name: str | None = None
    cat: str | None = None
    price: int | None = Field(default=None, gt=0)
    was: int | None = Field(default=None, gt=0)
    desc: str | None = None
    image: str | None = None
    stock: int | None = Field(default=None, ge=0)
    active: bool | None = None


class CartItem(BaseModel):
    product_id: int
    qty: int = Field(ge=1, le=100)


class Customer(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=40)
    address: str = Field(min_length=5, max_length=500)


class OrderIn(BaseModel):
    items: list[CartItem] = Field(min_length=1, max_length=50)
    zone_id: str
    customer: Customer


class PaymentInit(BaseModel):
    reference: str
    authorization_url: str
    total: int


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_id: int
    name: str
    unit_price: int
    qty: int


class OrderOut(BaseModel):
    """Public view: no address or contact details."""
    model_config = ConfigDict(from_attributes=True)
    reference: str
    status: str
    subtotal: int
    shipping: int
    total: int
    paid_at: datetime | None = None
    items: list[OrderItemOut]


class AdminOrderOut(OrderOut):
    customer_name: str
    email: str
    phone: str
    address: str
    zone_id: str
    created_at: datetime


class StatusPatch(BaseModel):
    status: str = Field(pattern="^(pending|paid|failed|shipped|delivered|cancelled)$")
