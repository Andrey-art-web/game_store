from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, UniqueConstraint, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


# ============================================================
# СТАТУСЫ ЗАКАЗА И ТОВАРА
# ============================================================

class OrderStatus(str, enum.Enum):
    """Статусы заказа в целом."""
    CREATED = "created"
    PAID = "paid"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    PAYMENT_FAILED = "payment_failed"
    OUT_OF_STOCK = "out_of_stock"
    DELIVERY_FAILED = "delivery_failed"


class ItemStatus(str, enum.Enum):
    """Статусы отдельного товара в заказе."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    REFUNDED = "refunded"


# ============================================================
# ОСНОВНЫЕ МОДЕЛИ
# ============================================================

class Order(Base):
    """Заказ клиента (может содержать несколько товаров)."""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, index=True)  # Оставлено для совместимости
    status = Column(Enum(OrderStatus), default=OrderStatus.CREATED)
    total_amount = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = relationship("OrderItem", back_populates="order")
    payments = relationship("Payment", back_populates="order")


class OrderItem(Base):
    """Товар внутри заказа. Каждый товар может быть выдан отдельно."""
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    sku = Column(String)
    price = Column(Float, default=0.0)
    status = Column(Enum(ItemStatus), default=ItemStatus.PENDING)
    # Уникальный код (ключ), который выдал поставщик.
    # unique=True — ЭТО ГЛАВНАЯ ЗАЩИТА ОТ ДУБЛЕЙ ПОСТАВЩИКА.
    code = Column(String, unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="items")


class Payment(Base):
    """Платежи. event_id уникален — защита от повторных вебхуков."""
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint('event_id', name='unique_payment_event'),
    )

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    event_id = Column(String, nullable=False)
    status = Column(String)  # 'paid' или 'failed'
    amount = Column(Float)
    currency = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="payments")


class ProviderRequest(Base):
    """Запросы к поставщикам (для отладки и дедупликации)."""
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


# ============================================================
# ЗАДАЧА 3: ОЧЕРЕДЬ И ЛИМИТЫ
# ============================================================

class OrderQueue(Base):
    """Очередь заказов на выдачу (с приоритетами)."""
    __tablename__ = "order_queue"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    status = Column(String, default="waiting")  # waiting, processing, issued, failed
    priority = Column(Integer, default=0)  # 1 = оплаченные, 0 = остальные
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    order = relationship("Order")


class ProviderLimit(Base):
    """Контроль лимита поставщика (запросы в минуту)."""
    __tablename__ = "provider_limits"

    id = Column(Integer, primary_key=True)
    provider_name = Column(String, nullable=False, unique=True)
    minute_window = Column(DateTime, nullable=False)
    requests_count = Column(Integer, default=0)
    max_per_minute = Column(Integer, default=10)


# ============================================================
# ЗАДАЧА 4: ЖУРНАЛ СОБЫТИЙ (EVENT SOURCING)
# ============================================================

class OrderEvent(Base):
    """
    Журнал событий по заказам.
    История ТОЛЬКО ДОПОЛНЯЕТСЯ — задним числом ничего не перезаписывается.
    По этому журналу можно восстановить состояние заказа на любую дату.
    """
    __tablename__ = "order_events"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False)  # created, paid, delivered, failed
    event_data = Column(String, nullable=True)  # JSON со дополнительными данными
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    order = relationship("Order")