from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from services.branding import get_branding

router = APIRouter(prefix="/branding", tags=["branding"])


@router.get("")
def public_branding(db: Session = Depends(get_db)):
    """Public branding config for login page and client theme."""
    return get_branding(db)
