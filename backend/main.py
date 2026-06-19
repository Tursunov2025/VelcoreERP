import os
from contextlib import asynccontextmanager

from config.logging_setup import configure_logging
from config.paths import DATA_ROOT, DB_PATH, LOG_PATH, UPLOAD_PATH
from config.database_guard import (
    DatabaseGuardError,
    get_database_health,
    validate_production_database_at_startup,
)

configure_logging()

import logging

_paths_log = logging.getLogger("azmus.paths")
_paths_log.info(
    "Data paths: DATA_ROOT=%s DB=%s UPLOADS=%s LOGS=%s",
    DATA_ROOT,
    DB_PATH,
    UPLOAD_PATH,
    LOG_PATH,
)

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
    crm_router,
    currency_router,
    dashboard_router,
    finance_router,
    forecast_router,
    gps_router,
    export_shipments_router,
    llp_router,
    mes_jobs_router,
    mes_lazer_terminal_router,
    mes_kraska_terminal_router,
    mes_monitor_router,
    mes_qc_terminal_router,
    mes_packaging_terminal_router,
    mes_warehouse_terminal_router,
    mes_dispatch_terminal_router,
    control_center_router,
    mes_router,
    mes_svarshik_terminal_router,
    migration_router,
    mobile_router,
    operators_router,
    orders_router,
    production_router,
    shipping_router,
    tasks_router,
    telegram_router,
    traceability_router,
    transport_router,
    printing_router,
    uploads_router,
    users_router,
    warehouse_router,
)
from routers.auth_router import login as jwt_login
from routers.materials_router import router as materials_router
from routers.uploads_router import UPLOAD_DIR as _UPLOAD_DIR
from schemas import LoginRequest
from services.scheduler import start_reminder_scheduler, stop_reminder_scheduler
from services.seed import seed_defaults
from auth.security import is_auth_configured

# Required P4 materials warehouse API paths (must appear in OpenAPI /docs).
_REQUIRED_MATERIALS_PATHS = (
    "/materials/dashboard",
    "/materials/categories",
    "/materials/items",
    "/materials/receipts",
    "/materials/issues",
    "/materials/adjustments",
    "/materials/movements",
)

# Phase 9 traceability API paths (must appear in OpenAPI /docs).
_REQUIRED_TRACEABILITY_PATHS = (
    "/traceability/dashboard",
    "/packages/{label_code}",
    "/track/package/{label_code}",
    "/mes/terminal/dispatch/scan-label",
    "/admin/settings/label-printers",
)

_REQUIRED_PRINTING_PATHS = (
    "/printing/jobs/pending",
    "/printing/jobs/{job_id}/label.png",
    "/printing/jobs/{job_id}/start",
    "/printing/jobs/{job_id}/complete",
    "/printing/jobs/{job_id}/failed",
    "/printing/agent/heartbeat",
    "/admin/printing/dashboard",
    "/printing/jobs/{job_id}/retry",
    "/packages/{label_code}/reprint",
)


def _app_paths(app: FastAPI) -> set[str]:
    return {getattr(route, "path", "") for route in app.routes if getattr(route, "path", None)}


def _router_declared_paths(router) -> set[str]:
    prefix = (getattr(router, "prefix", None) or "").rstrip("/")
    paths: set[str] = set()
    for route in getattr(router, "routes", ()):
        sub = getattr(route, "path", None)
        if not sub:
            continue
        if prefix and (sub == prefix or sub.startswith(f"{prefix}/")):
            paths.add(sub)
        elif prefix:
            paths.add(f"{prefix}{sub}" if sub.startswith("/") else f"{prefix}/{sub}")
        else:
            paths.add(sub)
    return paths


def _verify_materials_routes(app: FastAPI) -> None:
    router_paths = _router_declared_paths(materials_router)
    paths = _app_paths(app) | router_paths
    missing = [p for p in _REQUIRED_MATERIALS_PATHS if p not in paths]
    if missing:
        print("sorted(router_paths)", sorted(router_paths))
        print("sorted(paths)", sorted(paths))
        raise RuntimeError(
            "materials_router not registered — missing paths: "
            + ", ".join(missing)
            + f". router.routes={len(materials_router.routes)}"
            + "; ensure app.include_router(materials_router) runs before this check"
        )


def _verify_printing_routes(app: FastAPI) -> None:
    router_paths = _router_declared_paths(printing_router.router) | _router_declared_paths(
        printing_router.admin_router
    )
    paths = _app_paths(app) | router_paths
    missing = [p for p in _REQUIRED_PRINTING_PATHS if p not in paths]
    if missing:
        print("sorted(router_paths)", sorted(router_paths))
        print("sorted(paths)", sorted(paths))
        raise RuntimeError(
            "printing_router not registered — missing paths: "
            + ", ".join(missing)
            + f". router.routes={len(printing_router.router.routes)}"
            + f" admin_router.routes={len(printing_router.admin_router.routes)}"
            + "; ensure app.include_router(printing_router.router) and "
            "app.include_router(printing_router.admin_router) run before this check"
        )


def _verify_traceability_routes(app: FastAPI) -> None:
    router_paths = _router_declared_paths(traceability_router.router) | _router_declared_paths(
        traceability_router.public_router
    )
    paths = _app_paths(app) | router_paths
    missing = [p for p in _REQUIRED_TRACEABILITY_PATHS if p not in paths]
    if missing:
        print("sorted(router_paths)", sorted(router_paths))
        print("sorted(paths)", sorted(paths))
        raise RuntimeError(
            "traceability_router not registered — missing paths: "
            + ", ".join(missing)
            + f". router.routes={len(traceability_router.router.routes)}"
            + f" public_router.routes={len(traceability_router.public_router.routes)}"
            + "; ensure app.include_router(traceability_router.router) and "
            "app.include_router(traceability_router.public_router) run before this check"
        )


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

    materials_paths = sorted(p for p in _app_paths(app) if p.startswith("/materials"))
    startup_log.info(
        "Materials API registered: %s paths (%s)",
        len(materials_paths),
        ", ".join(materials_paths[:6]) + ("..." if len(materials_paths) > 6 else ""),
    )
    trace_paths = sorted(
        p
        for p in _app_paths(app)
        if p.startswith("/traceability")
        or p.startswith("/packages")
        or p.startswith("/track/package")
    )
    startup_log.info(
        "Traceability API registered: %s paths (%s)",
        len(trace_paths),
        ", ".join(trace_paths) if trace_paths else "none",
    )

    # Validate production DB before any schema bootstrap (never auto-create empty DB).
    try:
        validate_production_database_at_startup()
    except DatabaseGuardError as exc:
        startup_log.critical("Database guard blocked startup: %s", exc)
        raise SystemExit(1) from exc

    # Run schema setup here (not at import time) so uvicorn --reload workers
    # do not fight over SQLite write locks while the previous worker shuts down.
    Base.metadata.create_all(bind=engine)
    run_migrations()

    db = SessionLocal()
    try:
        seed_defaults(db)
        from services.settings_cache import refresh_settings_cache

        refresh_settings_cache(db)
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


_production = os.getenv("ENVIRONMENT", "").lower() in ("production", "prod") or os.getenv(
    "PRODUCTION", ""
).lower() in ("1", "true", "yes")

app = FastAPI(
    title="Azmus CRM ERP API",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=None if _production else "/docs",
    redoc_url=None if _production else "/redoc",
    openapi_url=None if _production else "/openapi.json",
)

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

upload_path = str(UPLOAD_PATH)
UPLOAD_PATH.mkdir(parents=True, exist_ok=True)

app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(orders_router.router)
app.include_router(warehouse_router.router)
app.include_router(materials_router)
app.include_router(production_router.router)
app.include_router(operators_router.router)
app.include_router(analytics_router.router)
app.include_router(finance_router.router)
app.include_router(export_shipments_router.router)
app.include_router(currency_router.router)
app.include_router(transport_router.router)
app.include_router(crm_router.router)
app.include_router(dashboard_router.router)
app.include_router(forecast_router.router)
app.include_router(gps_router.router)
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
app.include_router(mes_svarshik_terminal_router.router)
app.include_router(mes_monitor_router.router)
app.include_router(mes_kraska_terminal_router.router)
app.include_router(mes_qc_terminal_router.router)
app.include_router(mes_qc_terminal_router.admin_router)
app.include_router(mes_packaging_terminal_router.router)
app.include_router(mes_warehouse_terminal_router.router)
app.include_router(mes_warehouse_terminal_router.admin_router)
app.include_router(mes_dispatch_terminal_router.router)
app.include_router(control_center_router.router)
app.include_router(migration_router.router)
app.include_router(mobile_router.router)
app.include_router(traceability_router.router)
app.include_router(traceability_router.public_router)
app.include_router(printing_router.router)
app.include_router(printing_router.admin_router)
app.include_router(admin_router.router)

_verify_materials_routes(app)
_verify_traceability_routes(app)
_verify_printing_routes(app)

# Static file serving MUST be after upload API routes (POST /uploads/file).
app.mount("/uploads", StaticFiles(directory=upload_path), name="uploads")


@app.get("/")
def health_check():
    paths = _app_paths(app)
    materials_paths = sorted(p for p in paths if p.startswith("/materials"))
    mes_paths = sorted(p for p in paths if p.startswith("/mes"))
    db_health = get_database_health()
    return {
        "status": "ok",
        "service": "azmus-crm-erp",
        "version": "2.0.0",
        "auth_configured": is_auth_configured(),
        "data_root": str(DATA_ROOT),
        "database": str(DB_PATH),
        **db_health,
        "uploads": str(UPLOAD_PATH),
        "logs": str(LOG_PATH),
        "modules": {
            "materials": {
                "registered": all(p in paths for p in _REQUIRED_MATERIALS_PATHS),
                "path_count": len(materials_paths),
                "paths": materials_paths,
            },
            "mes": {
                "registered": bool(mes_paths),
                "path_count": len(mes_paths),
            },
            "traceability": {
                "registered": all(p in paths for p in _REQUIRED_TRACEABILITY_PATHS),
                "path_count": len(
                    [
                        p
                        for p in paths
                        if p.startswith("/traceability")
                        or p.startswith("/packages")
                        or p.startswith("/track/package")
                        or p == "/mes/terminal/dispatch/scan-label"
                        or p.startswith("/admin/settings/label-printers")
                    ]
                ),
                "paths": sorted(
                    p
                    for p in paths
                    if p in _REQUIRED_TRACEABILITY_PATHS
                    or p.startswith("/packages/{label_code}")
                    or p.startswith("/track/package")
                ),
            },
        },
    }


# Legacy compatibility for older frontends
@app.post("/login")
def legacy_login(data: LoginRequest, db: Session = Depends(get_db)):
    return jwt_login(data, db)
