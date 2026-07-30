"""Read-only adapter layer between Display Center and existing ERP aggregates."""
from __future__ import annotations
from datetime import datetime, timedelta
from threading import Lock
from sqlalchemy import func
from models import Material, MaterialConsumption, MaterialIssue, MaterialReceipt, MesJobBomLine, MesJobRework, MesProductionJob, Order, Transport, User, Vehicle

class _Cache:
    value = None; expires = datetime.min; lock = Lock()
    @classmethod
    def get(cls, factory, seconds=15):
        with cls.lock:
            if cls.value is None or datetime.utcnow() >= cls.expires:
                cls.value = factory(); cls.expires = datetime.utcnow() + timedelta(seconds=seconds)
            return cls.value

class ProductionProvider:
    def __init__(self, db): self.db = db
    def data(self):
        jobs = self.db.query(MesProductionJob).all(); active = [j for j in jobs if str(j.status).lower() not in ("completed", "cancelled")]
        completed = [j for j in jobs if str(j.status).lower() == "completed"]
        by_department = {d: sum(1 for j in active if d.lower() in str(getattr(j, "status", "")).lower()) for d in ("Laser", "Welding", "Painting", "Packaging", "Loading")}
        total = len(jobs); return {"today_production": total, "in_progress": len(active), "completed": len(completed), "delayed": 0, "completion_percent": round(100 * len(completed) / total, 1) if total else 0, "by_department": by_department}
class WarehouseProvider:
    def __init__(self, db): self.db=db
    def data(self):
        materials=self.db.query(Material).all(); return {"material_stock": len(materials), "low_stock_alerts": sum(float(getattr(x,"quantity",0) or 0) <= float(getattr(x,"min_stock",0) or 0) for x in materials), "incoming": self.db.query(MaterialReceipt).count(), "outgoing": self.db.query(MaterialIssue).count(), "top_consumed_materials": []}
class OrdersProvider:
    def __init__(self, db): self.db=db
    def data(self):
        orders=self.db.query(Order).all(); status=lambda s: sum(str(x.status).lower()==s for x in orders); return {"today_orders": len(orders), "active": len(orders)-status("completed")-status("cancelled"), "completed": status("completed"), "delayed": 0, "cancelled": status("cancelled"), "average_processing_time": None}
class QualityProvider:
    def __init__(self, db): self.db=db
    def data(self):
        lines=self.db.query(MesJobBomLine).all(); rejected=sum(float(x.rejected_quantity or 0) for x in lines); accepted=sum(float(x.accepted_quantity or 0) for x in lines); return {"rejected_products": rejected, "quality_rate": round(100*accepted/(accepted+rejected),1) if accepted+rejected else 100, "rework": self.db.query(MesJobRework).filter(MesJobRework.status != "completed").count(), "inspection_queue": 0}
class EmployeesProvider:
    def __init__(self, db): self.db=db
    def data(self):
        users=self.db.query(User).filter(User.is_active == True).all(); return {"working_now": len(users), "absent": 0, "vacation": 0, "current_shift": "Current shift", "employee_of_month": None}
class LogisticsProvider:
    def __init__(self, db): self.db=db
    def data(self):
        vehicles=self.db.query(Vehicle).all(); transports=self.db.query(Transport).all(); return {"vehicles_available": sum(str(v.status)=="active" for v in vehicles), "loading": sum("load" in str(t.status).lower() for t in transports), "in_transit": sum("transit" in str(t.status).lower() for t in transports), "delivered_today": sum("deliver" in str(t.status).lower() for t in transports)}
class AnnouncementProvider:
    def __init__(self, db): self.db=db
    def data(self): return []  # ERP announcements are supplied by the existing chat/announcement service when configured.
class KPIProvider:
    def __init__(self, production, quality): self.production=production; self.quality=quality
    def data(self): return {"daily_plan_percent": self.production["completion_percent"], "monthly_plan_percent": self.production["completion_percent"], "efficiency": self.production["completion_percent"], "average_production_time": None, "delay_percent": 0, "quality_percent": self.quality["quality_rate"]}
def factory_dashboard(db):
    def build():
        production=ProductionProvider(db).data(); quality=QualityProvider(db).data()
        return {"production":production,"warehouse":WarehouseProvider(db).data(),"orders":OrdersProvider(db).data(),"quality":quality,"employees":EmployeesProvider(db).data(),"logistics":LogisticsProvider(db).data(),"announcements":AnnouncementProvider(db).data(),"kpi":KPIProvider(production,quality).data(),"generated_at":datetime.utcnow().isoformat()}
    return _Cache.get(build)
