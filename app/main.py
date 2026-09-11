from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import engine, get_db
from app import models, schemas, crud

# Создаём таблицы
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Game Store API")


# ============================================================
# СОЗДАНИЕ И ПРОСМОТР ЗАКАЗА
# ============================================================

@app.post("/api/orders", response_model=schemas.OrderDetailedResponse)
def create_order(order_data: schemas.OrderCreate, db: Session = Depends(get_db)):
    order = crud.create_order_with_items(db, order_data.model_dump())
    return schemas.OrderDetailedResponse(
        id=order.id,
        status=order.status.value,
        total_amount=order.total_amount,
        items=[
            schemas.OrderItemResponse(
                id=item.id, sku=item.sku,
                status=item.status.value, code=item.code
            )
            for item in order.items
        ]
    )


@app.get("/api/orders/{order_id}", response_model=schemas.OrderDetailedResponse)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return schemas.OrderDetailedResponse(
        id=order.id,
        status=order.status.value,
        total_amount=order.total_amount,
        items=[
            schemas.OrderItemResponse(
                id=item.id, sku=item.sku,
                status=item.status.value, code=item.code
            )
            for item in order.items
        ]
    )


# ============================================================
# ВЕБХУК ОПЛАТЫ (ИДЕМПОТЕНТНОСТЬ)
# ============================================================

@app.post("/webhook/payment")
def payment_webhook(payload: schemas.PaymentWebhook, db: Session = Depends(get_db)):
    try:
        order_id = int(payload.order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order_id")

    # Идемпотентность: если event_id уже обработан — не делаем ничего
    existing = db.query(models.Payment).filter(
        models.Payment.event_id == payload.event_id
    ).first()
    if existing:
        return {"status": "already_processed", "order_id": order_id}

    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    db.add(models.Payment(
        order_id=order_id,
        event_id=payload.event_id,
        status=payload.status,
        amount=payload.amount,
        currency=payload.currency
    ))
    db.commit()

    if payload.status == "paid":
        order.status = models.OrderStatus.PAID
        db.commit()
        # Пишем событие в журнал
        crud.log_order_event(db, order_id, "paid", {"amount": payload.amount})

    return {"status": "accepted", "order_id": order_id}


# ============================================================
# ВЫДАЧА ТОВАРОВ (с проверкой оплаты)
# ============================================================

@app.post("/api/orders/{order_id}/deliver", response_model=dict)
def deliver_order(order_id: int, db: Session = Depends(get_db)):
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Проверяем, что заказ оплачен
    paid = db.query(models.Payment).filter(
        models.Payment.order_id == order_id,
        models.Payment.status == "paid"
    ).first()
    if not paid:
        raise HTTPException(status_code=400, detail="Order is not paid")

    results = crud.deliver_order_items(db, order_id)
    if not results:
        raise HTTPException(status_code=404, detail="Order not found or already delivered")
    return {"status": "delivery_completed", "items": results}


# ============================================================
# ЗАДАЧА 3: ОЧЕРЕДЬ
# ============================================================

@app.post("/api/orders/{order_id}/queue")
def add_to_queue(order_id: int, priority: int = 0, db: Session = Depends(get_db)):
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    queue_entry = crud.queue_order(db, order_id, priority=priority)
    return {
        "status": "queued",
        "order_id": order_id,
        "queue_id": queue_entry.id,
        "priority": queue_entry.priority
    }


@app.post("/api/queue/process", response_model=dict)
def process_queue(max_per_minute: int = 10, db: Session = Depends(get_db)):
    results = crud.process_order_queue(db, max_per_minute=max_per_minute)
    return {
        "status": "process_completed",
        "processed_count": len(results),
        "orders": results
    }


# ============================================================
# ЗАДАЧА 4: ВОССТАНОВЛЕНИЕ СОСТОЯНИЯ
# ============================================================

@app.get("/api/orders/{order_id}/state-at")
def get_order_state(order_id: int, at_time: str, db: Session = Depends(get_db)):
    try:
        at_datetime = datetime.fromisoformat(at_time)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")

    state = crud.get_order_state_at(db, order_id, at_datetime)
    if "error" in state:
        raise HTTPException(status_code=404, detail=state["error"])
    return state


@app.get("/api/money/state-at")
def get_money_state(at_time: str, db: Session = Depends(get_db)):
    try:
        at_datetime = datetime.fromisoformat(at_time)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")

    return crud.get_money_state_at(db, at_datetime)


@app.get("/")
def root():
    return {"message": "Game Store API is running"}