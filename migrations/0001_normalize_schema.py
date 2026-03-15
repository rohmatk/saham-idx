"""Migration 0001: Normalize schema to expected app columns.

This migration is designed to run once and ensure that the table:
- has lowercase column names (so `df["share_code"]` works)
- has all expected columns used by the app
- has a primary key on `id`
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

name = "0001_normalize_schema"

EXPECTED_COLUMNS = {
    "id": "BIGSERIAL PRIMARY KEY",
    "source_file": "TEXT",
    "snapshot_date": "DATE",
    "share_code": "TEXT",
    "issuer_name": "TEXT",
    "investor_name": "TEXT",
    "investor_type": "TEXT",
    "local_foreign": "TEXT",
    "nationality": "TEXT",
    "domicile": "TEXT",
    "holdings_scripless": "BIGINT",
    "holdings_scrip": "BIGINT",
    "total_holding_shares": "BIGINT",
    "percentage": "NUMERIC(12,4)",
    "uploaded_at": "TIMESTAMP DEFAULT NOW()",
}


def _normalize_columns(engine: Engine, schema: str, table: str) -> None:
    inspector = inspect(engine)
    columns = inspector.get_columns(table, schema=schema)

    with engine.begin() as conn:
        for col in columns:
            name = col["name"]
            lower = name.lower()
            if name != lower:
                conn.execute(text(f'ALTER TABLE {schema}.{table} RENAME COLUMN "{name}" TO "{lower}"'))


def _ensure_expected_columns(engine: Engine, schema: str, table: str) -> None:
    inspector = inspect(engine)
    columns = inspector.get_columns(table, schema=schema)
    existing = {col["name"] for col in columns}

    with engine.begin() as conn:
        for col, ddl_type in EXPECTED_COLUMNS.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE {schema}.{table} ADD COLUMN {col} {ddl_type}"))

        pk = inspector.get_pk_constraint(table, schema=schema)
        if not pk or not pk.get("constrained_columns"):
            if "id" in existing or "id" in EXPECTED_COLUMNS:
                try:
                    conn.execute(text(f"ALTER TABLE {schema}.{table} ADD PRIMARY KEY (id)"))
                except Exception:
                    pass


def upgrade(engine: Engine) -> None:
    # Update these values if your app uses a different schema/table name.
    schema = "public"
    table = "shareholders"

    _normalize_columns(engine, schema, table)
    _ensure_expected_columns(engine, schema, table)
