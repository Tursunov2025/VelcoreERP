import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import Base, engine, run_migrations
from models import (
    Expense,
    Income,
    Material,
    Order,
    OrderHistory,
    ShipmentArchive,
    StockMovement,
    User,
    WarehouseItem,
)
from routers import (
    admin_router,
    analytics_router,
    auth_router,
    finance_router,
    operators_router,
    orders_router,
    production_router,
    shipping_router,
    uploads_router,
    users_router,
    warehouse_router,
)
from services.seed import seed_defaults
from database import SessionLocal

app = FastAPI(title="Azmus CRM ERP API", version="2.0.0")

Base.metadata.create_all(bind=engine)
run_migrations()

_cors_origins_env = os.getenv("CORS_ORIGINS", "*").strip()
_cors_origins = (
    ["*"]
    if _cors_origins_env == "*"
    else [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

upload_path = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(upload_path, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=upload_path), name="uploads")

app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(orders_router.router)
app.include_router(warehouse_router.router)
app.include_router(production_router.router)
app.include_router(operators_router.router)
app.include_router(analytics_router.router)
app.include_router(finance_router.router)
app.include_router(uploads_router.router)
app.include_router(shipping_router.router)
app.include_router(admin_router.router)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "azmus-crm-erp", "version": "2.0.0"}


@app.on_event("startup")
def startup():
    db = SessionLocal()
    try:
        seed_defaults(db)
    finally:
        db.close()


# Legacy compatibility for older frontends
from fastapi import Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas import LoginRequest
from routers.auth_router import login as jwt_login


@app.post("/login")
def legacy_login(data: LoginRequest, db: Session = Depends(get_db)):
    return jwt_login(data, db)
