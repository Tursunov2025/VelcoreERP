import os

from database import SessionLocal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import engine, Base
from models import Order, User

app = FastAPI(title="Azmus CRM API")

Base.metadata.create_all(bind=engine)

_cors_origins_env = os.getenv("CORS_ORIGINS", "*").strip()
_cors_origins = (
    ["*"]
    if _cors_origins_env == "*"
    else [origin.strip() for origin in _cors_origins_env.split(",") if origin.strip()]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "azmus-crm"}




class OrderCreate(BaseModel):
    client: str
    phone: str
    amount: str
class LoginData(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: str
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
@app.post("/login")
def login(data: LoginData):

    db = SessionLocal()

    user = db.query(User).filter(
        User.username == data.username,
        User.password == data.password
    ).first()

    if user:
        return {
    "success": True,
    "role": user.role,
    "username": user.username
}

    return {"success": False}
@app.get("/create-admin")
def create_admin():

    db = SessionLocal()

    user = User(
        username="admin",
        password="1234",
        role="admin"
    )

    db.add(user)

    db.commit()

    return {"message": "Admin created"}
@app.get("/create-operator")
def create_operator():

    db = SessionLocal()

    user = User(
        username="operator1",
        password="1111",
        role="operator"
    )

    db.add(user)

    db.commit()

    return {"message": "Operator created"}

@app.get("/users")
def get_users():

    db = SessionLocal()

    try:

        users = db.query(User).all()

        return [
            {
                "username": user.username,
                "role": user.role
            }
            for user in users
        ]

    except Exception as e:

        return {
            "error": str(e)
        }


@app.post("/create-user")
def create_user(user: UserCreate):

    db = SessionLocal()

    try:
        existing = db.query(User).filter(
            User.username == user.username
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="User already exists")

        if user.role not in ("admin", "operator"):
            raise HTTPException(status_code=400, detail="Invalid role")

        new_user = User(
            username=user.username,
            password=user.password,
            role=user.role,
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return {
            "success": True,
            "username": new_user.username,
            "role": new_user.role,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e

    finally:
        db.close()
    
@app.on_event("startup")
def startup():

    db = SessionLocal()

    admin = db.query(User).filter(
        User.username == "admin"
    ).first()

    if not admin:

        user = User(
            username="admin",
            password="1234",
            role="admin"
        )

        db.add(user)

        db.commit()

    operator = db.query(User).filter(
        User.username == "operator1"
    ).first()

    if not operator:

        user = User(
            username="operator1",
            password="1111",
            role="operator"
        )

        db.add(user)

        db.commit()