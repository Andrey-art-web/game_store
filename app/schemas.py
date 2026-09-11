from pydantic import BaseModel, Field
from typing import List, Optional


class OrderItemCreate(BaseModel):
    sku: str
    price: float = Field(default=0.0)


class OrderCreate(BaseModel):
    items: List[OrderItemCreate]  # Теперь принимаем СПИСОК товаров
    total_amount: float = Field(default=0.0)


class OrderResponse(BaseModel):
    id: int
    status: str
    total_amount: float


class OrderItemResponse(BaseModel):
    id: int
    sku: str
    status: str
    code: Optional[str] = None


class OrderDetailedResponse(BaseModel):
    id: int
    status: str
    total_amount: float
    items: List[OrderItemResponse]


class PaymentWebhook(BaseModel):
    event_id: str
    order_id: str
    status: str
    amount: float
    currency: str
    created_at: str