"""CMS Open Payments ETL + analysis pipeline.

Streams a state-based slice of the CMS Open Payments General Payment CSV, lands it
in a staging table, builds normalized final tables from staging, runs data quality
checks at each layer, and produces the analysis outputs.

    python3 main.py                              # defaults: TX + NY, 250k records
    python3 main.py --states TX NY CA --max-records 100000
    python3 main.py --reuse-staging              # rebuild final tables + analysis only
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src import analysis, config, data_quality, extract, load

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and analyze a CMS Open Payments SQLite database."
    )
    parser.add_argument(
        "--states", nargs="+", default=config.DEFAULT_STATES, metavar="ST",
        help="Recipient states to include (default: %(default)s).",
    )
    parser.add_argument(
        "--max-records", type=int, default=config.DEFAULT_MAX_RECORDS,
        help="Maximum records to ingest, split across states (default: %(default)s).",
    )
    parser.add_argument(
        "--db-path", type=Path, default=config.DB_PATH,
        help="Path to the SQLite database file (default: %(default)s).",
    )
    parser.add_argument(
        "--reuse-staging", action="store_true",
        help="Skip the CSV download and reuse the existing staging table; only "
             "rebuild the final tables and re-run the analysis.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s"
    )
    args = parse_args()

    conn = load.create_database(args.db_path)
    try:
        if args.reuse_staging:
            staged = conn.execute("SELECT COUNT(*) FROM stg_general_payments").fetchone()[0]
            if staged == 0:
                raise SystemExit("--reuse-staging set but staging is empty; run without it first.")
            logging.info("Reusing %d staged rows", staged)
        else:
            logging.info("Ingesting states=%s (max %d records)", args.states, args.max_records)
            load.reset_staging(conn)  # full refresh: each run reflects exactly this slice
            rows = extract.download_records(args.states, args.max_records)
            load.load_staging(conn, rows)
            data_quality.run_staging_quality_checks(conn, args.states)

        load.build_final_tables(conn)
        data_quality.run_final_quality_checks(conn)

        analysis.run_analysis(args.db_path)
        data_quality.run_analysis_quality_checks(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
