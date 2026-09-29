"""Production workflow constants."""

PRODUCTION_STAGES = [
    "Kesish",
    "Svarka",
    "Kraska",
    "Upakovka",
    "Tekshiruv",
    "Tayyor",
]

DEPARTMENTS = [
    "Kesish",
    "Svarka",
    "Kraska",
    "Yig‘ish",
    "Upakovka",
    "Tekshiruv",
    "Ombor",
    "Admin",
]

STAGE_DEPARTMENT_MAP = {
    "Kesish": "Kesish",
    "Svarka": "Svarka",
    "Kraska": "Kraska",
    "Yig‘ish": "Yig‘ish",
    "Upakovka": "Upakovka",
    "Tekshiruv": "Tekshiruv",
    "Tayyor": "Ombor",
}

FIRST_STAGE = "Kesish"
FINAL_STAGE = "Tayyor"
INSPECTION_STAGE = "Tekshiruv"

PERMISSION_MODULES = [
    "orders",
    "production",
    "warehouse",
    "tasks",
    "finance",
    "chat",
    "settings",
]

LLP_PERMISSIONS = [
    "llp_view",
    "llp_download",
    "llp_upload",
    "llp_edit",
    "llp_delete",
    "llp_read_confirm",
]

MATERIALS_PERMISSIONS = [
    "materials_view",
    "materials_edit",
]

EXPORT_PERMISSIONS = [
    "export_view",
    "export_manage",
]

GPS_PERMISSIONS = [
    "gps_trip_view",
    "gps_trip_track",
]

PLATFORM_ADMIN_PERMISSIONS = [
    "platform_admin_view",
    "platform_admin_manage",
    "platform_admin_roles",
    "platform_admin_audit",
    "platform_admin_backup",
    "platform_admin_security",
]

DISPLAY_CENTER_PERMISSIONS = [
    "display_center_view",
    "display_center_manage",
]

PRODUCTION_PROJECT_PERMISSIONS = [
    "production_projects_view",
    "production_projects_edit",
    "production_projects_release",
    "production_projects_cancel",
    "production_projects_forecast",
    "production_projects_execute",
    "production_projects_stock_reserve",
    "production_projects_quality_approve",
    "production_projects_package",
    "production_projects_dispatch",
]

# Canonical Logistics master-data permissions.  The registry deliberately
# reuses the existing User/identity and MesTrip/GPS authorities instead of
# introducing a parallel driver or vehicle permission model.
LOGISTICS_PERMISSIONS = [
    "logistics_vehicle_manage",
    "logistics_driver_manage",
    "logistics_gps_bind",
    "logistics_loading_correct",
    "logistics_trip_transfer",
]

TRACEABILITY_PERMISSIONS = [
    "traceability_view",
    "traceability_generate_qr",
    "traceability_print_labels",
    "traceability_view_public_token",
]

PRODUCTION_PROJECT_STATUSES = [
    "draft", "planned", "released", "in_production", "partially_ready",
    "ready_to_ship", "shipped", "partially_delivered", "delivered", "completed", "cancelled",
]

PRODUCTION_PROJECT_TRANSITIONS = {
    "draft": {"planned", "cancelled"},
    "planned": {"draft", "released", "cancelled"},
    "released": {"in_production", "cancelled"},
    "in_production": {"partially_ready", "ready_to_ship", "cancelled"},
    "partially_ready": {"in_production", "ready_to_ship", "cancelled"},
    "ready_to_ship": {"shipped"},
    "shipped": {"partially_delivered", "delivered", "completed"},
    "partially_delivered": {"delivered", "completed"},
    "delivered": {"completed"},
    "completed": set(),
    "cancelled": set(),
}

MES_PERMISSIONS = [
    "mes_view",
    "mes_edit",
    "mes_delete",
    "mes_routes_design",
    "mes_drawings_upload",
    "mes_jobs_view",
    "mes_jobs_manage",
    "mes_terminal_lazer",
    "mes_terminal_svarshik",
    "mes_terminal_kraska",
    "mes_terminal_qc",
    "mes_terminal_yigish",
    "mes_terminal_packaging",
    "mes_terminal_warehouse",
    "mes_terminal_dispatch",
]

MES_JOB_STATUSES = [
    "draft",
    "released",
    "in_progress",
    "on_hold",
    "completed",
    "cancelled",
]

MES_JOB_PRIORITIES = ["low", "normal", "high", "urgent"]

# Default custom MES route stages (seeded; admin can add more in Phase 3A-A4).
MES_DEFAULT_PRODUCTION_STAGES = [
    ("Lazer", "Kesish"),
    ("Teshish", "Kesish"),
    ("Bukish", "Kesish"),
    ("Svarshik", "Svarka"),
    ("Tozalash", "Kraska"),
    ("Kraska", "Kraska"),
    ("Quritish", "Kraska"),
    ("Yig‘ish", "Yig‘ish"),
    ("Nazorat", "Tekshiruv"),
    ("Upakovka", "Upakovka"),
    ("Sklad", "Ombor"),
    ("Yuklash", "Ombor"),
]

ALL_PERMISSION_KEYS = (
    PERMISSION_MODULES
    + LLP_PERMISSIONS
    + MES_PERMISSIONS
    + MATERIALS_PERMISSIONS
    + EXPORT_PERMISSIONS
    + GPS_PERMISSIONS
    + PLATFORM_ADMIN_PERMISSIONS
    + DISPLAY_CENTER_PERMISSIONS
    + PRODUCTION_PROJECT_PERMISSIONS
    + LOGISTICS_PERMISSIONS
    + TRACEABILITY_PERMISSIONS
)

DEFAULT_OPERATOR_PERMISSIONS = {
    "orders": True,
    "production": True,
    "warehouse": False,
    "tasks": True,
    "finance": False,
    "chat": True,
    "settings": False,
    "llp_view": True,
    "llp_download": True,
    "llp_upload": False,
    "llp_edit": False,
    "llp_delete": False,
    "llp_read_confirm": True,
    "mes_view": True,
    "mes_edit": False,
    "mes_delete": False,
    "mes_routes_design": False,
    "mes_drawings_upload": False,
    "mes_jobs_view": False,
    "mes_jobs_manage": False,
    "mes_terminal_lazer": False,
    "mes_terminal_svarshik": False,
    "mes_terminal_kraska": False,
    "mes_terminal_qc": False,
    "mes_terminal_yigish": False,
    "mes_terminal_packaging": False,
    "mes_terminal_warehouse": False,
    "mes_terminal_dispatch": False,
    "materials_view": False,
    "materials_edit": False,
    "export_view": False,
    "export_manage": False,
    "platform_admin_view": False,
    "platform_admin_manage": False,
    "platform_admin_roles": False,
    "platform_admin_audit": False,
    "platform_admin_backup": False,
    "platform_admin_security": False,
    **{key: False for key in PRODUCTION_PROJECT_PERMISSIONS},
}

NOTIFICATION_EVENTS = [
    "new_order",
    "order_completed",
    "new_task",
    "task_accepted",
    "task_completed",
    "task_overdue",
    "shipment_dispatched",
    "warehouse_events",
    "chat_messages",
    "llp_important",
]


def next_stage(current: str):
    if current not in PRODUCTION_STAGES:
        return FIRST_STAGE
    idx = PRODUCTION_STAGES.index(current)
    if idx >= len(PRODUCTION_STAGES) - 1:
        return None
    return PRODUCTION_STAGES[idx + 1]


def user_can_access_stage(user_department: str, user_role: str, stage: str) -> bool:
    if user_role == "admin" or user_department == "Admin":
        return True
    if user_department == "Ombor":
        return stage == "Tayyor"
    return user_department == stage
