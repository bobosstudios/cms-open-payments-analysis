from pathlib import Path

DATASET_ID = "fb0b1734-1410-429d-92f6-3f4b35218e5e"
PROGRAM_YEAR = 2025
METASTORE_ITEM_URL = (
    f"https://openpaymentsdata.cms.gov/api/1/metastore/schemas/dataset/items/{DATASET_ID}"
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
SQL_DIR = PROJECT_ROOT / "sql"
SCHEMA_PATH = PROJECT_ROOT / "schema.sql"
BUILD_FINAL_SQL_PATH = SQL_DIR / "build_final_tables.sql"
DB_PATH = DATA_DIR / "open_payments.db"
DEFAULT_STATES = ["TX", "NY"]
DEFAULT_MAX_RECORDS = 250_000
