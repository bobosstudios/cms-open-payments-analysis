"""Create the schema, load rows into staging, and build the final tables.

Staging is the durable, idempotent checkpoint: rows land via ``INSERT OR IGNORE``
keyed on ``record_id``, so re-running never duplicates them. The normalized final
tables are then rebuilt from staging on every run (see build_final_tables.sql), so
they always reflect the current staging contents.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Iterable
from . import config, transform

log = logging.getLogger(__name__)

# Staging columns in insert order (loaded_at is omitted — it defaults to now).
# Product columns are generated to match the schema and the transform output.
_PRODUCT_FIELDS = [
    "product_name", 
    "product_category", 
    "covered_indicator", 
    "product_type", 
    "ndc", 
    "pdi"]

STAGING_COLUMNS = [
    "record_id", "dq_flags", "raw_payload", "change_type", "covered_recipient_type",
    "teaching_hospital_id", "teaching_hospital_ccn", "teaching_hospital_name",
    "covered_recipient_profile_id", "covered_recipient_npi",
    "covered_recipient_first_name", "covered_recipient_last_name",
    "recipient_city", "recipient_state", "recipient_zip_code", "recipient_country",
    "covered_recipient_specialty_1", "manufacturer_id", "manufacturer_name",
    "manufacturer_state", "manufacturer_country", "total_amount_of_payment_usdollars",
    "date_of_payment", "number_of_payments", "form_of_payment", "nature_of_payment",
    "dispute_status", "related_product_indicator", "program_year", "payment_publication_date",
] + [f"{field}_{n}" for n in range(1, transform.MAX_PRODUCTS + 1) for field in _PRODUCT_FIELDS]

_STAGING_INSERT = (
    f"INSERT OR IGNORE INTO stg_general_payments ({', '.join(STAGING_COLUMNS)}) "
    f"VALUES ({', '.join('?' for _ in STAGING_COLUMNS)})"
)


def connect(db_path: Path = config.DB_PATH) -> sqlite3.Connection:
    """Open a connection with foreign keys enforced and load-friendly pragmas."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def create_database(
    db_path: Path = config.DB_PATH, schema_path: Path = config.SCHEMA_PATH
) -> sqlite3.Connection:
    """Create the database file and apply ``schema.sql`` (idempotent)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    with conn:
        conn.executescript(schema_path.read_text())
    log.info("Schema ready at %s", db_path)
    return conn


def reset_staging(conn: sqlite3.Connection) -> None:
    """Empty the staging table so a run reflects exactly the requested slice.

    Staging is loaded as a full refresh: each normal run clears it and reloads
    the chosen states/limit, so changing --states between runs never mixes scopes.
    """
    with conn:
        conn.execute("DELETE FROM stg_general_payments")
    log.info("Cleared staging table")


def load_staging(
    conn: sqlite3.Connection, raw_rows: Iterable[dict], batch_size: int = 1000
) -> int:
    """Normalize raw rows and load them into staging in batched transactions.

    Returns the number of rows staged. Rows missing a record_id or amount are
    skipped and logged.
    """
    batch: list[tuple] = []
    staged = 0
    skipped = 0

    def flush() -> None:
        with conn:
            conn.executemany(_STAGING_INSERT, batch)
        batch.clear()

    for raw in raw_rows:
        row = transform.to_staging_row(raw)
        if row is None:
            skipped += 1
            continue
        batch.append(tuple(row.get(column) for column in STAGING_COLUMNS))
        staged += 1
        if len(batch) >= batch_size:
            flush()
            log.info("Staged %d rows", staged)

    if batch:
        flush()

    log.info("Staging complete: %d staged, %d skipped (missing id/amount)", staged, skipped)
    return staged


def build_final_tables(
    conn: sqlite3.Connection, sql_path: Path = config.BUILD_FINAL_SQL_PATH
) -> None:
    with conn:
        conn.executescript(sql_path.read_text())
    log.info("Final tables rebuilt from staging")
