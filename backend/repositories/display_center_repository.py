from sqlalchemy.orm import Session


class DisplayCenterRepository:
    """Small reusable repository; keeps router code independent of SQLAlchemy queries."""
    def __init__(self, db: Session): self.db = db
    def list(self, model, *order): return self.db.query(model).order_by(*order).all()
    def get(self, model, entity_id: int): return self.db.get(model, entity_id)
    def save(self, entity):
        self.db.add(entity); self.db.commit(); self.db.refresh(entity); return entity
    def delete(self, entity): self.db.delete(entity); self.db.commit()
