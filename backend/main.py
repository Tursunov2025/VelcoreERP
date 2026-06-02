import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine, get_db, run_migrations
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
    branding_router,
    chat_router,
    finance_router,
    llp_router,
    mes_jobs_router,
    mes_lazer_terminal_router,
    mes_router,
    migration_router,
    operators_router,
    orders_router,
    production_router,
    shipping_router,
    tasks_router,
    telegram_router,
    uploads_router,
    users_router,
    warehouse_router,
)
from routers.auth_router import login as jwt_login
from routers.uploads_router import UPLOAD_DIR as _UPLOAD_DIR
from schemas import LoginRequest
from services.scheduler import start_reminder_scheduler, stop_reminder_scheduler
from services.seed import seed_defaults
from auth.security import is_auth_configured


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging

    startup_log = logging.getLogger("azmus.main")
    if not is_auth_configured():
        startup_log.error(
            "JWT_SECRET_KEY is missing. Configure it in Render → Environment to enable login."
        )
    else:
        startup_log.info("JWT auth configured")

    # Run schema setup here (not at import time) so uvicorn --reload workers
    # do not fight over SQLite write locks while the previous worker shuts down.
    Base.metadata.create_all(bind=engine)
    run_migrations()

    db = SessionLocal()
    try:
        seed_defaults(db)
    finally:
        db.close()
    try:
        start_reminder_scheduler()
    except Exception:
        import logging

        logging.getLogger("azmus.main").exception("reminder scheduler failed to start")
    yield
    stop_reminder_scheduler()
    engine.dispose()


app = FastAPI(title="Azmus CRM ERP API", version="2.0.0", lifespan=lifespan)

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

upload_path = os.getenv("UPLOAD_DIR", str(_UPLOAD_DIR))
os.makedirs(upload_path, exist_ok=True)

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
app.include_router(chat_router.router)
app.include_router(tasks_router.router)
app.include_router(telegram_router.router)
app.include_router(branding_router.router)
app.include_router(llp_router.router)
app.include_router(mes_router.router)
app.include_router(mes_jobs_router.router)
app.include_router(mes_lazer_terminal_router.router)
app.include_router(migration_router.router)
app.include_router(admin_router.router)

# Static file serving MUST be after upload API routes (POST /uploads/file).
app.mount("/uploads", StaticFiles(directory=upload_path), name="uploads")


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "service": "azmus-crm-erp",
        "version": "2.0.0",
        "auth_configured": is_auth_configured(),
    }


# Legacy compatibility for older frontends
@app.post("/login")
def legacy_login(data: LoginRequest, db: Session = Depends(get_db)):
    return jwt_login(data, db)
