from __future__ import annotations
import logging
import sqlite3
from pathlib import Path
import matplotlib
import numpy as np
import pandas as pd
matplotlib.use("Agg")  # headless backend — we save PNGs, never open a window
import matplotlib.pyplot as plt 
from . import config

log = logging.getLogger(__name__)


SQL_QUESTIONS = [
    ("q1_top_manufacturers", "top_manufacturers", "Q1. Top manufacturers by total payment amount"),
    ("q2_payment_by_nature", "payment_by_nature", "Q2. Payment breakdown by nature of payment"),
    ("q3_payment_concentration", "payment_concentration", "Q3. Payment concentration (top 1% share)"),
    ("q4_top_products", "top_products", "Q4. Top products by total associated payment value"),
]


def _run_sql_file(conn: sqlite3.Connection, stem: str) -> pd.DataFrame:
    sql = (config.SQL_DIR / f"{stem}.sql").read_text()
    return pd.read_sql_query(sql, conn)


def _report(title: str, frame: pd.DataFrame) -> None:
    print(f"\n{title}\n{'=' * len(title)}")
    print(frame.to_string(index=False))


def _top_specialties(conn: sqlite3.Connection, output_dir: Path) -> Path:
    frame = _run_sql_file(conn, "q5_top_specialties")
    _report("Q5. Top recipient specialties by total received (pandas + chart)", frame)
    frame.to_csv(output_dir / "top_specialties.csv", index=False)

    top = frame.head(10).iloc[::-1]
    labels = top["primary_specialty"].str.slice(0, 45)
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(labels, top["total_payment_amount"], color="#55A868")
    ax.set_xlabel("Total payment amount (USD)")
    ax.set_title("Top recipient specialties by total payment received")
    fig.tight_layout()

    path = output_dir / "top_specialties.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    log.info("Wrote %s", path.name)
    return path


def _plot_amount_distribution(conn: sqlite3.Connection, output_dir: Path) -> Path:
    amounts = pd.read_sql_query(
        "SELECT payment_amount FROM payment WHERE payment_amount > 0", conn
    )["payment_amount"]

    bins = np.logspace(np.log10(amounts.min()), np.log10(amounts.max()), 50)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(amounts, bins=bins, color="#4C72B0", edgecolor="white")
    ax.set_xscale("log")
    ax.set_xlabel("Payment amount (USD, log scale)")
    ax.set_ylabel("Number of payments")
    ax.set_title("Distribution of general payment amounts")
    fig.tight_layout()

    path = output_dir / "amount_distribution.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    log.info("Wrote %s (%d payments)", path.name, len(amounts))
    return path


def run_analysis(db_path: Path = config.DB_PATH, output_dir: Path = config.OUTPUT_DIR) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        for sql_stem, out_stem, title in SQL_QUESTIONS:
            frame = _run_sql_file(conn, sql_stem)
            _report(title, frame)
            frame.to_csv(output_dir / f"{out_stem}.csv", index=False)
        _top_specialties(conn, output_dir)
        _plot_amount_distribution(conn, output_dir)
    finally:
        conn.close()
    print(f"\nSaved result tables and chart to {output_dir}/")
