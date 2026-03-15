"""Simple migration runner for the app.

Migrations are Python scripts located under `migrations/`.
Each migration module should expose:

- `name`: a unique migration name (e.g. "0001_normalize_columns")
- `upgrade(engine)`: function that applies the migration.

The runner records applied migrations in `migrations_applied` table.
"""

from __future__ import annotations

import importlib
import os
from datetime import datetime
from pathlib import Path
from typing import List

from sqlalchemy import text
from sqlalchemy.engine import Engine

MIGRATIONS_DIR = Path(__file__).parent
MIGRATIONS_TABLE = "migrations_applied"


def _ensure_migrations_table(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} (
                    name TEXT PRIMARY KEY,
                    applied_at TIMESTAMP NOT NULL
                );
                """
            )
        )


def _get_applied_migrations(engine: Engine) -> List[str]:
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT name FROM {MIGRATIONS_TABLE} ORDER BY name"))
        return [row[0] for row in result]


def _record_migration(engine: Engine, name: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(f"INSERT INTO {MIGRATIONS_TABLE} (name, applied_at) VALUES (:name, :applied_at)"),
            {"name": name, "applied_at": datetime.utcnow()},
        )


def _find_migration_modules() -> List[str]:
    modules = []
    for path in sorted(MIGRATIONS_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        modules.append(path.stem)
    return modules


def run_migrations(engine: Engine) -> None:
    """Run any unapplied migrations."""
    _ensure_migrations_table(engine)
    applied = set(_get_applied_migrations(engine))

    for module_name in _find_migration_modules():
        module = importlib.import_module(f"migrations.{module_name}")
        name = getattr(module, "name", module_name)
        if name in applied:
            continue

        upgrade = getattr(module, "upgrade", None)
        if not callable(upgrade):
            continue

        upgrade(engine)
        _record_migration(engine, name)
