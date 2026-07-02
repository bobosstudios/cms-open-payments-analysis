"""
DQ
"""
from __future__ import annotations
import logging
import sqlite3
from pathlib import Path
from . import config

log = logging.getLogger(__name__)


def run_count_check(conn: sqlite3.Connection, name: str, sql: str, expected: int = 0) -> None:
    actual = conn.execute(sql).fetchone()[0]
    if actual != expected:
        raise ValueError(f"[FAIL] {name}: expected {expected}, got {actual}")
    log.info("[PASS] %s", name)


def run_zero_row_check(conn: sqlite3.Connection, name: str, sql: str) -> None:
    rows = conn.execute(sql).fetchall()
    if rows:
        raise ValueError(f"[FAIL] {name}: {len(rows)} failing rows")
    log.info("[PASS] %s", name)


def run_warning_check(conn: sqlite3.Connection, name: str, sql: str) -> int:
    count = conn.execute(sql).fetchone()[0]
    if count:
        log.warning("[WARN] %s: %d rows", name, count)
    else:
        log.info("[PASS] %s", name)
    return count


def run_staging_quality_checks(conn: sqlite3.Connection, states: list[str]) -> None:
    log.info("Running staging data quality checks")
    run_count_check(
        conn, "staging.record_id not null",
        "SELECT COUNT(*) FROM stg_general_payments WHERE record_id IS NULL OR TRIM(record_id) = ''",
    )
    run_zero_row_check(
        conn, "staging.record_id unique",
        "SELECT record_id FROM stg_general_payments GROUP BY record_id HAVING COUNT(*) > 1",
    )
    run_count_check(
        conn, "staging.amount present and non-negative",
        "SELECT COUNT(*) FROM stg_general_payments "
        "WHERE total_amount_of_payment_usdollars IS NULL OR total_amount_of_payment_usdollars < 0",
    )
    placeholders = ", ".join("?" for _ in states)
    bad_states = conn.execute(
        f"SELECT COUNT(*) FROM stg_general_payments "
        f"WHERE recipient_state IS NULL OR recipient_state NOT IN ({placeholders})",
        [s.upper() for s in states],
    ).fetchone()[0]
    if bad_states:
        raise ValueError(f"[FAIL] staging.state in selected: {bad_states} rows outside {states}")
    log.info("[PASS] staging.state in selected")

    # Warnings — incomplete descriptive fields are expected in public data.
    run_warning_check(
        conn, "staging.manufacturer id present",
        "SELECT COUNT(*) FROM stg_general_payments WHERE manufacturer_id IS NULL OR TRIM(manufacturer_id) = ''",
    )
    run_warning_check(
        conn, "staging.recipient key buildable",
        "SELECT COUNT(*) FROM stg_general_payments "
        "WHERE (covered_recipient_profile_id IS NULL OR TRIM(covered_recipient_profile_id) = '') "
        "AND (teaching_hospital_id IS NULL OR TRIM(teaching_hospital_id) = '')",
    )
    # flags raw -> stag
    flagged = conn.execute(
        "SELECT COUNT(*) FROM stg_general_payments WHERE dq_flags IS NOT NULL"
    ).fetchone()[0]
    log.info("Retained raw_payload for %d flagged row(s); inspect via dq_flags", flagged)


def run_final_quality_checks(conn: sqlite3.Connection) -> None:
    """Validate the normalized tables built from staging."""
    log.info("Running final-table data quality checks")
    run_count_check(
        conn, "final.payment count matches staging",
        "SELECT (SELECT COUNT(*) FROM stg_general_payments) - (SELECT COUNT(*) FROM payment)",
    )
    run_zero_row_check(
        conn, "final.payment record_id unique",
        "SELECT record_id FROM payment GROUP BY record_id HAVING COUNT(*) > 1",
    )
    run_count_check(
        conn, "final.payment amount valid",
        "SELECT COUNT(*) FROM payment WHERE payment_amount IS NULL OR payment_amount < 0",
    )
    run_count_check(
        conn, "final.no orphan manufacturer fk",
        "SELECT COUNT(*) FROM payment p LEFT JOIN manufacturer m ON p.manufacturer_id = m.manufacturer_id "
        "WHERE p.manufacturer_id IS NOT NULL AND m.manufacturer_id IS NULL",
    )
    run_count_check(
        conn, "final.no orphan recipient fk",
        "SELECT COUNT(*) FROM payment p LEFT JOIN recipient r ON p.recipient_id = r.recipient_id "
        "WHERE p.recipient_id IS NOT NULL AND r.recipient_id IS NULL",
    )
    run_count_check(
        conn, "final.product_number in range",
        "SELECT COUNT(*) FROM payment_product WHERE product_number NOT BETWEEN 1 AND 5",
    )
    run_zero_row_check(
        conn, "final.payment_product unique",
        "SELECT record_id, product_number FROM payment_product "
        "GROUP BY record_id, product_number HAVING COUNT(*) > 1",
    )


def run_analysis_quality_checks(
    conn: sqlite3.Connection, output_dir: Path = config.OUTPUT_DIR
) -> None:
    """Sanity-check the analysis outputs after they are written."""
    log.info("Running analysis output checks")
    expected_files = [
        "top_manufacturers.csv",
        "payment_by_nature.csv",
        "payment_concentration.csv",
        "top_products.csv",
        "top_specialties.csv",
        "top_specialties.png",
        "amount_distribution.png",
    ]
    for name in expected_files:
        path = output_dir / name
        if not path.exists() or path.stat().st_size == 0:
            raise ValueError(f"[FAIL] analysis.output present: {name} missing or empty")
    log.info("[PASS] analysis.outputs present")

    total = conn.execute("SELECT COALESCE(SUM(payment_amount), 0) FROM payment").fetchone()[0]
    if total <= 0:
        raise ValueError(f"[FAIL] analysis.total positive: total payment amount is {total}")
    log.info("[PASS] analysis.total positive")

    pct = conn.execute(
        "WITH ranked AS (SELECT payment_amount, NTILE(100) OVER (ORDER BY payment_amount DESC) AS p FROM payment) "
        "SELECT SUM(payment_amount) * 100.0 / (SELECT SUM(payment_amount) FROM payment) FROM ranked WHERE p = 1"
    ).fetchone()[0]
    if pct is None or not 0 <= pct <= 100:
        raise ValueError(f"[FAIL] analysis.concentration in range: top-1% share is {pct}")
    log.info("[PASS] analysis.concentration in range (top 1%% = %.1f%%)", pct)
