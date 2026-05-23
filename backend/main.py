from database import SessionLocal
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import engine, Base
from models import Order

app = FastAPI()

Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




class OrderCreate(BaseModel):
    client: str
    phone: str
    amount: str

@app.get("/orders")
def get_orders():

    db = SessionLocal()

    orders = db.query(Order).all()

    return orders


@app.post("/orders")
def add_order(order: OrderCreate):

    db = SessionLocal()

    new_order = Order(
        client=order.client,
        phone=order.phone,
        amount=order.amount,
        status="Yangi"
    )

    db.add(new_order)

    db.commit()

    db.refresh(new_order)

    return new_order
@app.delete("/orders/{order_id}")
def delete_order(order_id: int):

    db = SessionLocal()

    try:

        order = db.query(Order).filter(
            Order.id == order_id
        ).first()

        if not order:
            return {"error": "Order not found"}

        db.delete(order)

        db.commit()

        return {"message": "Deleted successfully"}

    except Exception as e:

        db.rollback()

        return {"error": str(e)}

    finally:

        db.close()
@app.put("/orders/{order_id}")
def update_order(order_id: int, status: str):

    db = SessionLocal()

    order = db.query(Order).filter(
        Order.id == order_id
    ).first()

    if order:

        order.status = status

        db.commit()

        db.refresh(order)

        return order

    return {"error": "Order not found"}