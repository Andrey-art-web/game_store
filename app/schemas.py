from pydantic import BaseModel

class OrderCreate(BaseModel):
    sku: str

class OrderResponse(BaseModel):
    id: int
    sku: str
    status: str

class PaymentWebhook(BaseModel):
    event_id: str
    order_id: str
    status: str
    amount: int
    currency: str
    created_at: str