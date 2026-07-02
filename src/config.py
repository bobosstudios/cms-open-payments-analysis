"""Project-wide configuration and constants.

Keeping paths and source details in one place avoids hard-coded strings scattered
through the pipeline and makes the defaults easy to see and change.
"""
from pathlib import Path


# CMS Open Payments source 
# Each program year is published as a separate CMS dataset. The UUID below is the
# 2025 General Payment Data dataset (verified live against the API).

DATASET_ID = "fb0b1734-1410-429d-92f6-3f4b35218e5e"
PROGRAM_YEAR = 2025

# We bulk-ingest the full-year CSV distribution (a flat file on a fast CDN),
# which is far quicker and more reliable than the paginated query API. Its
# download URL is versioned by publication date, so we resolve it at runtime from
# this metastore item rather than hard-coding it.
METASTORE_ITEM_URL = (
    f"https://openpaymentsdata.cms.gov/api/1/metastore/schemas/dataset/items/{DATASET_ID}"
)

# local paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
SQL_DIR = PROJECT_ROOT / "sql"
SCHEMA_PATH = PROJECT_ROOT / "schema.sql"
BUILD_FINAL_SQL_PATH = SQL_DIR / "build_final_tables.sql"
DB_PATH = DATA_DIR / "open_payments.db"

# Extraction defaults
# A state-based slice keeps the analysis honest and bounded for local SQLite.
DEFAULT_STATES = ["TX", "NY"]
DEFAULT_MAX_RECORDS = 250_000
