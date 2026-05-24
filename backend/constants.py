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
