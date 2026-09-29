"""Schema-aware business import. Default: full transaction followed by ROLLBACK.

No app/database module imports, dotenv loading, migrations, users/config writes,
automatic parent creation outside the explicit scope, or blind source-ID copying.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, JSON, MetaData, Numeric, Table, create_engine, func, inspect, select, text
from sqlalchemy.exc import SQLAlchemyError

try:
    from .business_transfer import FORMAT, TABLE_KEYS, REFERENCE_KEYS, LOGICAL_FKS, PRESERVE_ON_MATCH, IMMUTABLE_MATCH_TABLES, primary_key
    from .export_local_business_data import checksum, write_new_json
except ImportError:
    from business_transfer import FORMAT, TABLE_KEYS, REFERENCE_KEYS, LOGICAL_FKS, PRESERVE_ON_MATCH, IMMUTABLE_MATCH_TABLES, primary_key
    from export_local_business_data import checksum, write_new_json


class TransferConflict(ValueError):
    pass


def validate_source(payload):
    if payload.get("format") != FORMAT:
        raise TransferConflict("Unsupported export format")
    body = {k: v for k, v in payload.items() if k != "sha256"}
    if checksum(body) != payload.get("sha256"):
        raise TransferConflict("Export checksum mismatch")
    if set(payload.get("tables", {})) != set(TABLE_KEYS):
        raise TransferConflict("Export table scope mismatch")
    if set(payload.get("references", {})) - set(REFERENCE_KEYS):
        raise TransferConflict("Reference scope mismatch")
    for name, rows in {**payload["tables"], **payload.get("references", {})}.items():
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
            raise TransferConflict(f"Invalid row collection: {name}")
        ids = [r.get(primary_key(name)) for r in rows]
        if any(type(x) is not int or x < 1 for x in ids) or len(set(ids)) != len(ids):
            raise TransferConflict(f"Invalid/duplicate source identity: {name}")
        if name in REFERENCE_KEYS:
            allowed = {"id", *REFERENCE_KEYS[name]}
            if any(set(row) != allowed for row in rows):
                raise TransferConflict(f"Invalid reference identity fields: {name}")


def normalize(value, column):
    if value is None:
        if not column.nullable and not column.primary_key:
            raise TransferConflict(f"NULL for required column {column.name}")
        return None
    typ = column.type
    if isinstance(typ, Boolean):
        if type(value) is bool:
            return value
        if type(value) is int and value in (0, 1):
            return bool(value)
        raise TransferConflict(f"Invalid boolean: {column.name}")
    if isinstance(typ, DateTime):
        try:
            result = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if result.tzinfo is not None and not typ.timezone:
                result = result.astimezone(timezone.utc).replace(tzinfo=None)
            return result
        except ValueError as exc:
            raise TransferConflict(f"Invalid timestamp: {column.name}") from exc
    if isinstance(typ, Date):
        return value if isinstance(value, date) else date.fromisoformat(str(value))
    if isinstance(typ, Integer):
        if type(value) is not int:
            raise TransferConflict(f"Invalid integer: {column.name}")
        return value
    if isinstance(typ, (Float, Numeric)):
        try:
            result = Decimal(str(value)) if isinstance(typ, Numeric) and not isinstance(typ, Float) else float(value)
            if not math.isfinite(result):
                raise ValueError()
            return result
        except (ValueError, TypeError, ArithmeticError) as exc:
            raise TransferConflict(f"Invalid numeric: {column.name}") from exc
    if isinstance(typ, JSON):
        return json.loads(value) if isinstance(value, str) else value
    if not isinstance(value, str):
        raise TransferConflict(f"Invalid text: {column.name}")
    if getattr(typ, "length", None) and len(value) > typ.length:
        raise TransferConflict(f"Text exceeds target length: {column.name}")
    return value


class Importer:
    def __init__(self, connection, payload):
        self.db, self.payload = connection, payload
        self.meta, self.tables, self.maps, self.processing, self.failed = MetaData(), {}, {}, set(), set()
        self.rows = {t: {r[primary_key(t)]: r for r in rows} for t, rows in {**payload["tables"], **payload.get("references", {})}.items()}
        self.report = {"mode": "dry-run", "target_dialect": connection.dialect.name,
                       "source_sha256": payload["sha256"], "preserve_production_config": True,
                       "tables": {}, "schema_differences": [], "events": [], "conflicts": [], "id_mapping": {},
                       "preserved_fields": {k: sorted(v) for k, v in PRESERVE_ON_MATCH.items()},
                       "external_dependencies": "MATCH only; never inserted or updated"}
        existing = set(inspect(connection).get_table_names())
        for name in (*TABLE_KEYS, *REFERENCE_KEYS):
            if name in existing:
                self.tables[name] = Table(name, self.meta, autoload_with=connection, resolve_fks=False)
        for name in TABLE_KEYS:
            table = self.tables.get(name)
            total = connection.scalar(select(func.count()).select_from(table)) if table is not None else None
            self.report["tables"][name] = {"SOURCE": len(self.rows[name]), "INSERTED": 0, "MATCHED": 0, "UPDATED": 0, "SKIPPED": 0, "FAILED": 0, "TARGET BEFORE": total, "TARGET TOTAL": total}
            if table is None:
                self.report["schema_differences"].append({"table": name, "code": "missing_target_table"})
                continue
            declared = payload["schema"].get(name, {}).get("columns", [])
            for col in declared:
                if col["name"] not in table.c:
                    self.report["schema_differences"].append({"table": name, "column": col["name"], "code": "missing_target_column"})
                else:
                    target_type = str(table.c[col["name"]].type)
                    if col["type"].upper() != target_type.upper():
                        self.report["schema_differences"].append({"table": name, "column": col["name"], "source_type": col["type"], "target_type": target_type, "code": "type_conversion"})

    def conflict(self, table, source_id, message):
        key = (table, source_id)
        if key not in self.failed:
            self.failed.add(key)
            self.report["conflicts"].append({"table": table, "source_id": source_id, "code": str(message)})
            if table in TABLE_KEYS:
                for event in self.report["events"]:
                    if event["table"] == table and event["source_id"] == source_id and event["action"] in ("MATCH", "INSERT", "UPDATE"):
                        self.report["tables"][table][{"MATCH": "MATCHED", "INSERT": "INSERTED", "UPDATE": "UPDATED"}[event["action"]]] -= 1
                        event["action"] = "FAILED_AFTER_MAPPING"
                self.report["tables"][table]["FAILED"] += 1

    def matching_keys(self, name, original, values):
        keys = TABLE_KEYS.get(name, REFERENCE_KEYS.get(name))
        # Two real legacy categories have no code. Use an explicit name + NULL
        # code fallback, never assign a generated code or overwrite a coded row.
        if name == "material_categories" and not values.get("code"):
            keys = ("name",)
        if name == "mes_production_routes":
            peers = [r for r in self.rows[name].values() if all(r.get(k) == original.get(k) for k in keys)]
            if len(peers) > 1:
                # Historical revisions can share name AND version. Their immutable
                # creation timestamp distinguishes them without copying local IDs.
                if not original.get("created_at") or sum(r.get("created_at") == original["created_at"] for r in peers) != 1:
                    raise TransferConflict("Ambiguous source route history")
                keys = (*keys, "created_at")
        return keys

    def foreign_keys(self, name):
        result = dict(LOGICAL_FKS.get(name, {}))
        # Unexpected FKs fail closed rather than silently copying source IDs.
        if name in TABLE_KEYS:
            for fk in self.payload["schema"][name]["foreign_keys"]:
                if fk["to"] != "id" or fk["seq"] != 0:
                    raise TransferConflict("Unsupported source foreign key")
                if fk["from"] in result and result[fk["from"]] != fk["table"]:
                    raise TransferConflict("Source FK contract mismatch")
                result[fk["from"]] = fk["table"]
            for fk in self.tables[name].foreign_keys:
                table, column = fk.target_fullname.split(".")[-2:]
                if column != "id" or (fk.parent.name in result and result[fk.parent.name] != table):
                    raise TransferConflict("Target FK contract mismatch")
                result[fk.parent.name] = table
        return result

    def resolve(self, name, source_id):
        key = (name, source_id)
        if key in self.maps:
            return self.maps[key]
        if key in self.failed:
            raise TransferConflict(f"Blocked dependency {name}:{source_id}")
        if key in self.processing:
            raise TransferConflict(f"Dependency cycle {name}:{source_id}")
        if name not in self.rows or source_id not in self.rows[name]:
            raise TransferConflict(f"Missing source dependency {name}:{source_id}")
        if name not in self.tables:
            raise TransferConflict(f"Missing target table {name}")
        self.processing.add(key)
        try:
            table, original = self.tables[name], self.rows[name][source_id]
            row = dict(original)
            if name == "mes_product_templates":
                row.pop("default_route_id", None)  # Restore after routes have mapped.
            for col, parent in self.foreign_keys(name).items():
                if col in row and row[col] is not None:
                    row[col] = self.resolve(parent, row[col])
            for col in row:
                if col not in table.c:
                    raise TransferConflict(f"Missing target column {name}.{col}")
            values = {k: normalize(v, table.c[k]) for k, v in row.items() if k != "id"}
            keys = self.matching_keys(name, original, values)
            if any(k not in values or values[k] is None or values[k] == "" for k in keys if k not in ("parent_id", "line_reference")):
                raise TransferConflict(f"Missing natural key {name}")
            matches = self.db.execute(select(table).where(*(table.c[k] == values[k] for k in keys))).mappings().all()
            if name == "material_categories" and keys == ("name",) and any(r["code"] != values.get("code") for r in matches):
                raise TransferConflict("Code-less source category matches coded target; explicit resolution required")
            if len(matches) > 1:
                raise TransferConflict(f"Ambiguous natural key {name}")
            if matches and any(t == name and sid != source_id and dest == matches[0][primary_key(name)] for (t, sid), dest in self.maps.items()):
                raise TransferConflict("Multiple source rows resolve to one target identity")
            if name in REFERENCE_KEYS:
                if not matches:
                    raise TransferConflict(f"Unresolved target dependency {name}:{source_id}")
                target_id = matches[0][primary_key(name)]
                self.maps[key] = target_id
                return target_id
            counters = self.report["tables"][name]
            with self.db.begin_nested():
                if matches:
                    old = matches[0]
                    target_id = old[primary_key(name)]
                    changed = {k: v for k, v in values.items() if k != primary_key(name) and k not in PRESERVE_ON_MATCH.get(name, set()) and old[k] != v}
                    if name == "product_passport_sequences":
                        wanted = max(old["next_value"], values["next_value"], self.serial_floor(values["year"]))
                        changed = {"next_value": wanted} if wanted != old["next_value"] else {}
                    if name in IMMUTABLE_MATCH_TABLES and changed:
                        raise TransferConflict("Existing transactional/QR identity differs; explicit resolution required: " + ",".join(sorted(changed)))
                    if changed:
                        self.db.execute(table.update().where(table.c[primary_key(name)] == target_id).values(**changed))
                    action = "UPDATE" if changed else "MATCH"
                else:
                    for col in table.c:
                        if col.name not in values and col.name != "id" and not col.nullable and col.server_default is None and col.default is None:
                            raise TransferConflict(f"Missing required target field {name}.{col.name}")
                    # Explicit IDs under table lock avoid nextval() leaking sequence
                    # changes through a PostgreSQL dry-run ROLLBACK.
                    if primary_key(name) == "id":
                        values["id"] = (self.db.scalar(select(func.max(table.c.id))) or 0) + 1
                    else:
                        values["next_value"] = max(values["next_value"], self.serial_floor(values["year"]))
                    self.db.execute(table.insert().values(**values))
                    target_id = values[primary_key(name)]
                    changed, action = {}, "INSERT"
            counters[{"INSERT": "INSERTED", "MATCH": "MATCHED", "UPDATE": "UPDATED"}[action]] += 1
            self.report["events"].append({"table": name, "source_id": source_id, "target_id": target_id, "action": action, "match_columns": list(keys), "changed_columns": sorted(changed)})
            self.maps[key] = target_id
            return target_id
        except (TransferConflict, ValueError, TypeError, SQLAlchemyError) as exc:
            # DB exceptions can embed entire QR/source payloads: report only type/code.
            message = str(exc) if isinstance(exc, TransferConflict) else type(exc).__name__
            self.conflict(name, source_id, message)
            raise TransferConflict(message) from None
        finally:
            self.processing.discard(key)

    def serial_floor(self, year):
        table = self.tables.get("product_passports")
        if table is None:
            return 1
        prefix = f"PRD-{year}-"
        serials = self.db.scalars(select(table.c.serial_number).where(table.c.serial_number.like(prefix + "%")))
        return max([0, *[int(s[len(prefix):]) for s in serials if s[len(prefix):].isdigit()]]) + 1

    def restore_defaults(self):
        table = self.tables.get("mes_product_templates")
        if table is None:
            return
        for source_id, row in self.rows["mes_product_templates"].items():
            if ("mes_product_templates", source_id) not in self.maps:
                continue
            try:
                route_id = self.resolve("mes_production_routes", row["default_route_id"]) if row.get("default_route_id") is not None else None
                if route_id is not None and self.rows["mes_production_routes"][row["default_route_id"]]["template_id"] != source_id:
                    raise TransferConflict("Default route belongs to another template")
                target_id = self.maps[("mes_product_templates", source_id)]
                old = self.db.scalar(select(table.c.default_route_id).where(table.c.id == target_id))
                if old != route_id:
                    self.db.execute(table.update().where(table.c.id == target_id).values(default_route_id=route_id))
                    self.report["events"].append({"table": "mes_product_templates", "source_id": source_id, "target_id": target_id, "action": "RESTORE_DEFAULT_ROUTE", "target_route_id": route_id})
            except TransferConflict as exc:
                self.conflict("mes_product_templates", source_id, str(exc))

    def reset_sequences(self):
        if self.db.dialect.name != "postgresql":
            return
        quote = self.db.dialect.identifier_preparer.quote
        for name in TABLE_KEYS:
            table = self.tables.get(name)
            if table is None or primary_key(name) != "id":
                continue
            sequence = self.db.scalar(text("SELECT pg_get_serial_sequence(:table, 'id')"), {"table": name})
            if not sequence:
                continue
            # Identifier comes from PostgreSQL catalog, not the JSON input.
            qualified = ".".join(quote(p.strip('"')) for p in sequence.split("."))
            last, called = self.db.execute(text(f"SELECT last_value, is_called FROM {qualified}")).one()
            next_id = max((self.db.scalar(select(func.max(table.c.id))) or 0) + 1, last + int(called))
            self.db.execute(text(f"ALTER SEQUENCE {qualified} RESTART WITH {int(next_id)}"))

    def execute(self):
        for name in TABLE_KEYS:
            for source_id in self.rows[name]:
                try:
                    self.resolve(name, source_id)
                except TransferConflict as exc:
                    self.conflict(name, source_id, str(exc))
        self.restore_defaults()
        for name, counters in self.report["tables"].items():
            if name in self.tables:
                counters["TARGET TOTAL"] = self.db.scalar(select(func.count()).select_from(self.tables[name]))
        self.report["id_mapping"] = {t: {str(s): d for (table, s), d in self.maps.items() if table == t} for t in TABLE_KEYS}
        if self.payload.get("dependency_errors"):
            self.report["conflicts"].extend(self.payload["dependency_errors"])
        if any(d["code"].startswith("missing_target") for d in self.report["schema_differences"]):
            self.report["conflicts"].append({"code": "Target schema missing source tables/columns; no automatic migration performed"})
        self.report["validation"] = "FAIL" if self.report["conflicts"] else "PASS"
        if self.report["validation"] == "PASS":
            self.reset_sequences()
        return self.report


def run_import(engine, payload, commit=False, allow_sqlite_test=False):
    validate_source(payload)
    if engine.dialect.name != "postgresql" and not (allow_sqlite_test and engine.dialect.name == "sqlite"):
        raise TransferConflict("Target must be PostgreSQL (SQLite only for explicit disposable tests)")
    with engine.connect() as db:
        if db.dialect.name == "sqlite":
            db.exec_driver_sql("PRAGMA foreign_keys=ON")
            db.commit()
            db.exec_driver_sql("BEGIN IMMEDIATE")
            transaction = db.get_transaction()
        else:
            transaction = db.begin()
        try:
            if db.dialect.name == "postgresql":
                db.execute(text("SET LOCAL lock_timeout = '5s'"))
                db.execute(text("SET LOCAL statement_timeout = '120s'"))
                db.execute(text("SELECT pg_advisory_xact_lock(826431907)"))
                available = set(inspect(db).get_table_names())
                for name in sorted(TABLE_KEYS):
                    if name in available:
                        db.execute(text(f'LOCK TABLE "{name}" IN SHARE ROW EXCLUSIVE MODE'))
            worker = Importer(db, payload)
            report = worker.execute()
            report["mode"] = "commit" if commit else "dry-run"
            if commit and report["validation"] == "PASS":
                transaction.commit()
                report["transaction"] = "COMMITTED"
            else:
                transaction.rollback()
                report["transaction"] = "ROLLED_BACK"
            report["target_counts_after_transaction"] = {name: db.scalar(select(func.count()).select_from(table)) for name, table in worker.tables.items() if name in TABLE_KEYS}
            return report
        finally:
            if transaction.is_active:
                transaction.rollback()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--commit", action="store_true")
    parser.add_argument("--preserve-production-config", action="store_true", help="Always enforced; flag documents operator intent")
    parser.add_argument("--target-env", default="DATABASE_URL", help="Name of preconfigured target URL env variable; never printed")
    parser.add_argument("--sqlite-test-target", type=Path, help="Existing disposable SQLite target; DRY RUN only")
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Report already exists; choose a new timestamped report")
    payload = json.loads(args.source.read_text(encoding="utf-8"))
    try:
        if args.sqlite_test_target:
            import tempfile
            target = args.sqlite_test_target.resolve(strict=True)
            if args.commit or not target.is_relative_to(Path(tempfile.gettempdir()).resolve()) or not target.name.startswith("business-transfer-test-"):
                raise TransferConflict("SQLite target must be a named disposable test DB under TEMP; no SQLite CLI commit")
            url = "sqlite:///" + target.as_posix()
        else:
            url = os.environ.get(args.target_env)
            if not url:
                raise TransferConflict(f"Required environment variable absent: {args.target_env}")
        engine = create_engine(url, echo=False)
        try:
            report = run_import(engine, payload, args.commit, bool(args.sqlite_test_target))
        finally:
            engine.dispose()
    except (TransferConflict, SQLAlchemyError) as exc:
        report = {"validation": "FAIL", "transaction": "NOT_COMMITTED", "error": str(exc) if isinstance(exc, TransferConflict) else type(exc).__name__}
    write_new_json(args.report, report)
    print(json.dumps({"report": str(args.report), "validation": report["validation"], "transaction": report["transaction"], "tables": report.get("tables", {}), "conflicts": report.get("conflicts", []), "error": report.get("error")}, indent=2))
    return 0 if report["validation"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
