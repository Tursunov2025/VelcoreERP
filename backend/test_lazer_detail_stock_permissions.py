"""Route and authorization checks for the LAZER read-only detail stock view."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

test_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
test_root = Path(tempfile.mkdtemp(prefix="velcore-lazer-stock-permissions-"))
os.environ["DATABASE_URL"] = f"sqlite:///{test_db.replace(chr(92), '/')}"
os.environ["DB_PATH"] = test_db.replace(chr(92), "/")
os.environ["DATA_ROOT"] = str(test_root)
os.environ["UPLOAD_PATH"] = str(test_root / "uploads")
os.environ["BACKUP_PATH"] = str(test_root / "backups")
os.environ["LOG_PATH"] = str(test_root / "logs")
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-lazer-stock-permissions"

backend = Path(__file__).resolve().parent
sys.path.insert(0, str(backend))

from fastapi.testclient import TestClient  # noqa: E402
from auth.security import hash_password  # noqa: E402
from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import MesProductPart, User, WarehouseStock, WarehouseTransaction  # noqa: E402
from services.permissions import set_user_permissions  # noqa: E402


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def main() -> None:
    Base.metadata.create_all(bind=engine)
    run_migrations()
    db = SessionLocal()
    try:
        lazer = User(username="lazer-stock", password_hash=hash_password("1111"), role="operator", department="Kesish")
        warehouse = User(username="warehouse-stock", password_hash=hash_password("1111"), role="operator", department="Ombor")
        unauthorized = User(username="other-stock", password_hash=hash_password("1111"), role="operator", department="Kraska")
        db.add_all([lazer, warehouse, unauthorized])
        db.flush()
        set_user_permissions(db, lazer.id, {"mes_terminal_lazer": True})
        part = MesProductPart(part_number="DET-LAZER-01", name="Lazer detail", unit="dona", created_by="test")
        db.add(part)
        db.flush()
        stock = WarehouseStock(detail_id=part.id, detail_code="DET-LAZER-01", detail_name="Lazer detail", quantity=10, reserved_quantity=3, unit="dona", status="active")
        db.add(stock)
        db.flush()
        db.add_all([
            WarehouseTransaction(stock_id=stock.id, detail_id=part.id, quantity=10, operation="IN", reason="LAZER surplus", operator="lazer-stock", quantity_before=0, quantity_after=10),
            WarehouseTransaction(stock_id=stock.id, detail_id=part.id, quantity=1, operation="OUT", reason="warehouse issue", operator="warehouse-stock", quantity_before=10, quantity_after=9),
        ])
        db.commit()

        client = TestClient(app)
        lazer_headers = _login(client, "lazer-stock", "1111")
        warehouse_headers = _login(client, "warehouse-stock", "1111")
        other_headers = _login(client, "other-stock", "1111")

        response = client.get("/warehouse/stock", headers=lazer_headers, params={"q": "LAZER-01"})
        assert response.status_code == 200, response.text
        assert response.json()[0]["quantity"] == 10
        assert response.json()[0]["reserved_quantity"] == 3
        assert response.json()[0]["available_quantity"] == 7

        history = client.get("/warehouse/transactions", headers=lazer_headers, params={"operation": "IN"})
        assert history.status_code == 200, history.text
        assert len(history.json()) == 1
        assert history.json()[0]["operation"] == "IN"
        assert client.get("/warehouse/transactions", headers=lazer_headers).status_code == 403

        for operation in ("out", "reserve", "release", "adjustment"):
            params = {"stock_id": stock.id, "quantity": 1, "reason": "permission test"}
            response = client.post(f"/warehouse/stock/{operation}", headers=lazer_headers, params=params)
            assert response.status_code == 403, (operation, response.text)

        warehouse_history = client.get("/warehouse/transactions", headers=warehouse_headers)
        assert warehouse_history.status_code == 200
        assert {row["operation"] for row in warehouse_history.json()} == {"IN", "OUT"}
        assert client.post("/warehouse/stock/reserve", headers=warehouse_headers, params={"stock_id": stock.id, "quantity": 1}).status_code == 200
        assert client.get("/warehouse/stock", headers=other_headers).status_code == 403
        print("test_lazer_detail_stock_permissions: OK")
    finally:
        db.close()


if __name__ == "__main__":
    main()
