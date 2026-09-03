from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum

class OrderStatus(str, enum.Enum):
    CREATED = "created"
    PAID = "paid"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    PAYMENT_FAILED = "payment_failed"
    OUT_OF_STOCK = "out_of_stock"
    DELIVERY_FAILED = "delivery_failed"

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, index=True)
    status = Column(Enum(OrderStatus), default=OrderStatus.CREATED)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    sku = Column(String)
    quantity = Column(Integer, default=1)
    order = relationship("Order", back_populates="items")

class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint('event_id', name='unique_payment_event'),
    )
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    event_id = Column(String, nullable=False)
    status = Column(String)
    amount = Column(Integer)
    currency = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class ProviderRequest(Base):
    __tablename__ = "provider_requests"
    __table_args__ = (
        UniqueConstraint('request_id', name='unique_provider_request'),
    )
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    request_id = Column(String, nullable=False)
    provider_name = Column(String)
    status = Column(String)
    code = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)