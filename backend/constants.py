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
    "Upakovka",
    "Tekshiruv",
    "Ombor",
    "Admin",
]

STAGE_DEPARTMENT_MAP = {
    "Kesish": "Kesish",
    "Svarka": "Svarka",
    "Kraska": "Kraska",
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
    "mes_terminal_packaging": False,
    "mes_terminal_warehouse": False,
    "mes_terminal_dispatch": False,
    "materials_view": False,
    "materials_edit": False,
    "export_view": False,
    "export_manage": False,
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
