from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import engine, get_db
from app import models, schemas, crud

# Автоматически создаем таблицы в базе при первом запуске
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Game Store API")

@app.post("/api/orders", response_model=schemas.OrderResponse)
def create_order(order_data: schemas.OrderCreate, db: Session = Depends(get_db)):
    if not crud.check_stock(db, order_data.sku):
        raise HTTPException(status_code=400, detail="Out of stock")
    order = crud.create_order(db, order_data.sku)
    return order

@app.get("/api/orders/{order_id}", response_model=schemas.OrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.post("/webhook/payment")
def payment_webhook(payload: schemas.PaymentWebhook, db: Session = Depends(get_db)):
    # 1. Переводим order_id из строки в целое число
    try:
        order_id = int(payload.order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order_id")

    # 2. Защита от двойной выдачи: если платеж уже был получен, мы повторно не обрабатываем
    existing_payment = db.query(models.Payment).filter(
        models.Payment.event_id == payload.event_id
    ).first()

    if existing_payment:
        # Платеж уже обработан, возвращаем 200 (успех), чтобы платежная система не повторяла запрос
        return {"status": "already_processed", "order_id": order_id}

    # 3. Получаем заказ
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # 4. Записываем платеж в таблицу, чтобы зафиксировать уникальный event_id
    db.add(models.Payment(
        order_id=order_id,
        event_id=payload.event_id,
        status=payload.status,
        amount=payload.amount,
        currency=payload.currency
    ))
    db.commit()

    # 5. Если оплата прошла, переходим к выдачи
    if payload.status == "paid":
        order.status = models.OrderStatus.PAID
        db.commit()

    return {"status": "accepted", "order_id": order_id}

@app.get("/")
def root():
    return {"message": "Game Store API is running"}