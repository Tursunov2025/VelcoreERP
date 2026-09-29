# Production project execution sources

This layer keeps existing MES tables authoritative and adds
`project_production_operations` only as append-only, normalized quantity evidence
where legacy stage fields are shared or do not provide a stable project boundary.

| Stage | Authoritative operational record | Project reconciliation evidence |
| --- | --- | --- |
| LAZER | `mes_job_bom_lines.completed_quantity` and route timestamps | `lazer_completed` deltas |
| SVARKA | MES job BOM quantities and route timestamps | `svarka_completed`, `svarka_accepted`, `svarka_rejected` deltas |
| Painting | MES job BOM paint/accept/reject quantities | `painting_completed`, `painting_accepted`, `painting_rejected` deltas |
| Quality | MES job BOM dispositions and `mes_job_reworks` | `qc_approved`, `qc_rejected`, `rework_created`, `rework_completed` deltas |
| Packaging | `mes_job_packages` including product-unit `quantity` | Package rows; `packaged` operation is audit evidence |
| Finished warehouse | `mes_finished_goods_inventory` and inventory movements | Inventory rows and package quantities |
| Trip assignment/loading | `mes_shipment_items`, `mes_finished_goods_placements`, and `mes_loading_plan_placements` | Snapshot quantities, conditional placement claims, saved millimetre geometry, and `trip_loaded` evidence |
| Loading/shipping | `mes_trips`, existing `mes_dispatches`/`mes_dispatch_packages`, and inventory movements | Trip commands, dispatch-package states, package quantities, and `trip_dispatched` evidence |
| Delivery/acceptance | `mes_shipment_items` dispositions and `mes_trip_evidence` | Balanced delivered/accepted/damaged/missing quantities plus `trip_delivered`/`trip_accepted` evidence |
| Materials | Existing material reservations/consumptions | Existing material services remain authoritative |
| Reusable details | Warehouse stock/transactions plus project allocations | Allocation consumed/released quantities; reserved OUT is atomic |

Project-line counters are a cache. `reconcile_project_line` deterministically
rebuilds them from the records above, and `synchronize_project` derives lifecycle
state from the reconciled facts. Stock coverage and actual production remain
separate quantities.

Checkpoint C commands use `mes_trip_commands` as a payload-hashed idempotency
journal. Unknown gross weight and dimensions remain SQL `NULL` in shipment
snapshots. Loading-plan coordinates and dimensions use millimetres. The optional
automatic layout is deterministic first-fit candidate-edge packing ordered by
rectangle area; it is a starting arrangement, not an optimality claim.

Overall progress is quantity-weighted across all project lines and then stage
weighted: production 45%, quality 20%, packaging 15%, finished warehouse 10%,
shipping 10%.

Forecasts require at least five operations spanning at least one day. Shorter
evidence windows, stock/material blockers, or missing throughput return no dates
and stable reason codes. Available forecasts use a conservative completion range,
not an exact timestamp.

The additive migration can add nullable links to existing SQLite tables, but
SQLite cannot safely retrofit all foreign-key constraints with `ALTER TABLE`.
Application validation therefore protects legacy rows. PostgreSQL deployments
should add reviewed `NOT VALID` foreign keys and validate them after an orphan
audit in a separate production migration.
