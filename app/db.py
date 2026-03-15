import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, inspect, text

from app.parser_pdf import get_ticker_map
from migrations import run_migrations

@st.cache_resource
def get_engine():
    pg = st.secrets["postgres"]
    url = (
        f"postgresql+psycopg2://{pg['user']}:{pg['password']}"
        f"@{pg['host']}:{pg['port']}/{pg['database']}"
    )
    return create_engine(url, pool_pre_ping=True)


EXPECTED_SCHEMA = {
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


def _ensure_lowercase_columns(engine, schema, table):
    """Normalize column names so the app can query using lowercase names.

    Postgres treats unquoted identifiers as lowercase, but if a table was
    created with quoted uppercase names (e.g. "SHARE_CODE"), then
    `SELECT share_code` will fail. This helper renames columns to their
    lowercase variants when needed.
    """

    inspector = inspect(engine)
    columns = inspector.get_columns(table, schema=schema)
    existing = {col["name"] for col in columns}

    # Rename any column that isn't already lowercase
    with engine.begin() as conn:
        for col in columns:
            name = col["name"]
            lower = name.lower()
            if name != lower and lower not in existing:
                conn.execute(text(f'ALTER TABLE {schema}.{table} RENAME COLUMN "{name}" TO "{lower}"'))
                existing.add(lower)


def _migrate_table_schema(engine, schema, table):
    """Ensure the table schema matches the expected app schema.

    This is an explicit migration step that:
    1) Renames any columns that were created with quoted/uppercase names to
       lowercase (so Python code can refer to them naturally).
    2) Adds any missing columns that the app expects.
    3) Ensures the table has a primary key (id).
    """

    inspector = inspect(engine)

    # 1) Normalize column casing first
    _ensure_lowercase_columns(engine, schema, table)

    # Re-load columns after renaming
    columns = inspector.get_columns(table, schema=schema)
    existing = {col["name"] for col in columns}

    # 2) Add missing expected columns
    with engine.begin() as conn:
        for col, ddl_type in EXPECTED_SCHEMA.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE {schema}.{table} ADD COLUMN {col} {ddl_type}"))
                existing.add(col)

        # 3) Ensure a primary key exists on `id` if possible.
        pk = inspector.get_pk_constraint(table, schema=schema)
        if (not pk) or (not pk.get("constrained_columns")):
            # Only add PK if `id` exists (it should after the previous step)
            if "id" in existing:
                try:
                    conn.execute(text(f"ALTER TABLE {schema}.{table} ADD PRIMARY KEY (id)"))
                except Exception:
                    # Ignore if the constraint already exists or cannot be added.
                    pass


def init_db():
    engine = get_engine()
    schema = st.secrets["app"]["schema"]
    table = st.secrets["app"]["table"]

    ddl = f"""
    CREATE SCHEMA IF NOT EXISTS {schema};

    CREATE TABLE IF NOT EXISTS {schema}.{table} (
        id BIGSERIAL PRIMARY KEY,
        source_file TEXT,
        snapshot_date DATE,
        share_code TEXT,
        issuer_name TEXT,
        investor_name TEXT,
        investor_type TEXT,
        local_foreign TEXT,
        nationality TEXT,
        domicile TEXT,
        holdings_scripless BIGINT,
        holdings_scrip BIGINT,
        total_holding_shares BIGINT,
        percentage NUMERIC(12,4),
        uploaded_at TIMESTAMP DEFAULT NOW()
    );
    """

    with engine.begin() as conn:
        for stmt in ddl.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))

    # Run any pending migrations (schema normalization, etc.)
    run_migrations(engine)

def _fill_missing_share_code(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing share_code values using the ticker map (issuer_name -> share_code)."""

    if "share_code" not in df.columns or "issuer_name" not in df.columns:
        return df

    ticker_map = get_ticker_map()

    df["share_code"] = df["share_code"].astype(str).str.strip().str.upper()
    df["issuer_name"] = df["issuer_name"].astype(str).str.strip().str.upper()

    missing_mask = df["share_code"].isna() | (df["share_code"] == "")
    if missing_mask.any():
        df.loc[missing_mask, "share_code"] = (
            df.loc[missing_mask, "issuer_name"].map(lambda x: ticker_map.get(x))
        )

    return df


def replace_snapshot(df: pd.DataFrame, source_file: str, snapshot_date):
    engine = get_engine()
    schema = st.secrets["app"]["schema"]
    table = st.secrets["app"]["table"]

    df = _fill_missing_share_code(df)

    with engine.begin() as conn:
        conn.execute(
            text(f"""
                DELETE FROM {schema}.{table}
                WHERE source_file = :source_file
                   OR snapshot_date = :snapshot_date
            """),
            {"source_file": source_file, "snapshot_date": snapshot_date},
        )

    df.to_sql(
        name=table,
        con=engine,
        schema=schema,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=1000,
    )

@st.cache_data(ttl=600)
def load_data(limit: int = 5000):
    engine = get_engine()
    schema = st.secrets["app"]["schema"]
    table = st.secrets["app"]["table"]

    query = text(f"SELECT * FROM {schema}.{table} LIMIT :limit")

    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"limit": limit})

    # Normalize column names for consistent access in views
    df.columns = [c.lower() for c in df.columns]

    # Ensure share_code is populated using the ticker map when missing.
    if "share_code" in df.columns and "issuer_name" in df.columns:
        ticker_map = get_ticker_map()

        df["share_code"] = df["share_code"].fillna("").astype(str).str.strip().str.upper()
        df["issuer_name"] = df["issuer_name"].fillna("").astype(str).str.strip().str.upper()

        missing_mask = df["share_code"].isin(["", "NONE", "NAN"])
        if missing_mask.any():
            df.loc[missing_mask, "share_code"] = (
                df.loc[missing_mask, "issuer_name"].map(lambda x: ticker_map.get(x, ""))
            )

    return df

def clear_cache():
    load_data.clear()