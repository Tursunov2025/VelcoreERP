"""Explicit business-transfer scope. No application imports or startup side effects."""
from __future__ import annotations

FORMAT = "velcore-business-v1"
TABLE_KEYS = {
    "material_categories": ("code",),
    "materials": ("code",),
    "mes_product_categories": ("parent_id", "name"),
    "mes_product_templates": ("code",),
    "mes_product_parts": ("part_number",),
    "mes_production_routes": ("template_id", "name", "version"),
    "mes_route_steps": ("route_id", "step_order"),
    "mes_bom_lines": ("template_id", "part_id"),
    "material_bom_lines": ("part_id", "material_id"),
    "mes_job_packages": ("package_number",),
    "mes_dispatch_packages": ("package_id",),
    "package_labels": ("package_id",),
    "package_locations": ("package_id",),
    "product_passports": ("serial_number",),
    "product_passport_sequences": ("year",),
}
# These tables are READ ONLY lookup dependencies, never inserted or updated.
REFERENCE_KEYS = {
    "mes_production_stages": ("name",),
    "mes_production_jobs": ("job_number", "template_id"),
    "production_projects": ("project_code",),
    "production_project_lines": ("project_id", "product_id", "line_reference"),
    "project_release_snapshots": ("project_id", "revision", "checksum"),
    "mes_dispatches": ("dispatch_number", "job_id"),
    "mes_finished_goods_inventory": ("package_id", "job_id", "template_id"),
    "mes_warehouse_locations": ("code",),
}
# Historical additive SQLite migrations did not declare every ORM FK.
LOGICAL_FKS = {
    "materials": {"category_id": "material_categories"},
    "mes_product_categories": {"parent_id": "mes_product_categories"},
    "mes_product_templates": {"category_id": "mes_product_categories", "default_route_id": "mes_production_routes"},
    "mes_product_parts": {"material_id": "materials"},
    "mes_production_routes": {"template_id": "mes_product_templates"},
    "mes_route_steps": {"route_id": "mes_production_routes", "stage_id": "mes_production_stages"},
    "mes_bom_lines": {"template_id": "mes_product_templates", "part_id": "mes_product_parts"},
    "material_bom_lines": {"part_id": "mes_product_parts", "material_id": "materials"},
    "mes_job_packages": {"job_id": "mes_production_jobs", "location_id": "mes_warehouse_locations", "project_id": "production_projects", "project_line_id": "production_project_lines", "project_release_snapshot_id": "project_release_snapshots"},
    "mes_dispatch_packages": {"dispatch_id": "mes_dispatches", "package_id": "mes_job_packages", "inventory_id": "mes_finished_goods_inventory"},
    "package_labels": {"package_id": "mes_job_packages"},
    "package_locations": {"package_id": "mes_job_packages"},
    "product_passports": {"package_id": "mes_job_packages", "job_id": "mes_production_jobs", "project_id": "production_projects", "project_line_id": "production_project_lines", "template_id": "mes_product_templates"},
    "mes_production_jobs": {"template_id": "mes_product_templates"},
    "production_project_lines": {"project_id": "production_projects", "product_id": "mes_product_templates"},
    "project_release_snapshots": {"project_id": "production_projects"},
    "mes_dispatches": {"job_id": "mes_production_jobs"},
    "mes_finished_goods_inventory": {"package_id": "mes_job_packages", "job_id": "mes_production_jobs", "template_id": "mes_product_templates"},
}
# Operational counters must not overwrite target activity during master merge.
PRESERVE_ON_MATCH = {
    "materials": {"quantity"},
    "mes_bom_lines": {"produced_quantity", "accepted_quantity", "rejected_quantity"},
    "mes_route_steps": {"completed_parts_count", "started_at", "accepted_at", "completed_at"},
}
IMMUTABLE_MATCH_TABLES = {"mes_job_packages", "mes_dispatch_packages", "package_labels", "package_locations", "product_passports"}


def primary_key(table):
    return "year" if table == "product_passport_sequences" else "id"
