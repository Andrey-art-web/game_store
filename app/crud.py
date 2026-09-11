from sqlalchemy.orm import Session
from app import models
from datetime import datetime, timedelta
import json


# ============================================================
# СОЗДАНИЕ ЗАКАЗА
# ============================================================

def create_order_with_items(db: Session, order_data: dict) -> models.Order:
    """Создает заказ с несколькими товарами."""
    order = models.Order(
        status=models.OrderStatus.CREATED,
        total_amount=order_data['total_amount']
    )
    db.add(order)
    db.flush()

    for item_data in order_data['items']:
        item = models.OrderItem(
            order_id=order.id,
            sku=item_data['sku'],
            price=item_data['price'],
            status=models.ItemStatus.PENDING
        )
        db.add(item)

    db.commit()
    db.refresh(order)

    # Записываем событие "created" в журнал
    log_order_event(db, order.id, "created", {
        "total_amount": order.total_amount,
        "items_count": len(order.items)
    })

    return order


def get_order(db: Session, order_id: int) -> models.Order:
    return db.query(models.Order).filter(models.Order.id == order_id).first()


# ============================================================
# ВЫДАЧА ТОВАРОВ (ЗАЩИТА ОТ ДУБЛЕЙ ПОСТАВЩИКА)
# ============================================================

def deliver_order_items(db: Session, order_id: int) -> list:
    """Выдаёт товары. Если поставщик выдал дубль — помечает как failed."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        return []

    results = []

    for item in order.items:
        if item.status == models.ItemStatus.DELIVERED:
            continue

        # ВАРИАНТ 1 (РЕАЛЬНЫЙ): уникальный код на основе item.id
        provider_code = f"CODE-{item.sku}-{item.id}"

        # ВАРИАНТ 2 (ТЕСТОВЫЙ, для проверки дублей):
        # provider_code = f"CODE-{item.sku}-1"

        if not check_for_unique_code(db, provider_code):
            item.status = models.ItemStatus.FAILED
            results.append({"sku": item.sku, "status": "failed", "reason": "duplicate_code"})
        else:
            item.code = provider_code
            item.status = models.ItemStatus.DELIVERED
            results.append({"sku": item.sku, "status": "delivered", "code": provider_code})

            # Пишем событие в журнал
            log_order_event(db, order_id, "delivered", {
                "sku": item.sku,
                "code": provider_code
            })

        db.commit()

    return results


def check_for_unique_code(db: Session, code: str) -> bool:
    """Проверяет, не занят ли код. False = дубль."""
    existing_item = db.query(models.OrderItem).filter(
        models.OrderItem.code == code
    ).first()
    return existing_item is None


# ============================================================
# ЗАДАЧА 3: ОЧЕРЕДЬ И ЛИМИТЫ
# ============================================================

def queue_order(db: Session, order_id: int, priority: int = 0) -> models.OrderQueue:
    """Добавляет заказ в очередь (если его там ещё нет)."""
    existing = db.query(models.OrderQueue).filter(
        models.OrderQueue.order_id == order_id,
        models.OrderQueue.status.in_(["waiting", "processing"])
    ).first()
    if existing:
        return existing

    queue_entry = models.OrderQueue(
        order_id=order_id,
        status="waiting",
        priority=priority
    )
    db.add(queue_entry)
    db.commit()
    db.refresh(queue_entry)
    return queue_entry


def process_order_queue(db: Session, max_per_minute: int = 10) -> list:
    """Обрабатывает очередь с учётом лимита и приоритетов."""
    one_minute_ago = datetime.utcnow() - timedelta(minutes=1)

    issued_count = db.query(models.OrderQueue).filter(
        models.OrderQueue.processed_at >= one_minute_ago,
        models.OrderQueue.status == "issued"
    ).count()

    available_slots = max_per_minute - issued_count
    if available_slots <= 0:
        return []

    waiting_orders = db.query(models.OrderQueue).filter(
        models.OrderQueue.status == "waiting"
    ).order_by(
        models.OrderQueue.priority.desc(),
        models.OrderQueue.created_at.asc()
    ).limit(available_slots).all()

    results = []
    for queue_entry in waiting_orders:
        queue_entry.status = "processing"
        db.commit()

        delivery_results = deliver_order_items(db, queue_entry.order_id)

        queue_entry.status = "issued"
        queue_entry.processed_at = datetime.utcnow()
        db.commit()

        results.append({
            "order_id": queue_entry.order_id,
            "delivery": delivery_results
        })

    return results


# ============================================================
# ЗАДАЧА 4: ЖУРНАЛ СОБЫТИЙ И ВОССТАНОВЛЕНИЕ
# ============================================================

def log_order_event(db: Session, order_id: int, event_type: str, event_data: dict = None):
    """Записывает событие в журнал (только INSERT, никогда не UPDATE)."""
    event = models.OrderEvent(
        order_id=order_id,
        event_type=event_type,
        event_data=json.dumps(event_data) if event_data else None
    )
    db.add(event)
    db.commit()
    return event


def get_order_state_at(db: Session, order_id: int, at_time: datetime) -> dict:
    """Восстанавливает состояние заказа на конкретный момент времени."""
    events = db.query(models.OrderEvent).filter(
        models.OrderEvent.order_id == order_id,
        models.OrderEvent.created_at <= at_time
    ).order_by(models.OrderEvent.created_at.asc()).all()

    if not events:
        return {"error": "No events found before this time"}

    state = {
        "order_id": order_id,
        "status": "unknown",
        "total_amount": 0.0,
        "items_delivered": 0,
        "items_failed": 0,
        "events_count": len(events)
    }

    for event in events:
        if event.event_type == "created":
            state["status"] = "created"
        elif event.event_type == "paid":
            state["status"] = "paid"
        elif event.event_type == "delivered":
            state["status"] = "delivered"
            state["items_delivered"] += 1
        elif event.event_type == "failed":
            state["status"] = "failed"
            state["items_failed"] += 1

    return state


def get_money_state_at(db: Session, at_time: datetime) -> dict:
    """Восстанавливает состояние денег на конкретный момент времени."""
    payments = db.query(models.Payment).filter(
        models.Payment.created_at <= at_time,
        models.Payment.status == "paid"
    ).all()

    total_paid = sum(p.amount for p in payments)

    return {
        "at_time": at_time.isoformat(),
        "total_paid": total_paid,
        "payments_count": len(payments)
    }