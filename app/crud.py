from sqlalchemy.orm import Session
from app import models

def create_order(db: Session, sku: str) -> models.Order:
    order = models.Order(sku=sku, status=models.OrderStatus.CREATED)
    db.add(order)
    db.commit()
    db.refresh(order)
    return order

def get_order(db: Session, order_id: int):
    return db.query(models.Order).filter(models.Order.id == order_id).first()

def check_stock(db: Session, sku: str) -> bool:
    return True