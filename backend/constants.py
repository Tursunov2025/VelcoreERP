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

ALL_PERMISSION_KEYS = PERMISSION_MODULES + LLP_PERMISSIONS

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
