
from __future__ import annotations

import io
import json
import pytest

from src import analysis, config, data_quality, extract, load, transform

# source column names
PHYSICIAN_ROW = {
    "record_id": "1157125359",
    "change_type": "NEW",
    "covered_recipient_type": "Covered Recipient Physician",
    "covered_recipient_profile_id": "429303",
    "covered_recipient_npi": "1285959858",
    "covered_recipient_first_name": "Robert",
    "covered_recipient_last_name": "Durick",
    "recipient_city": "Youngstown",
    "recipient_state": "OH",
    "recipient_zip_code": "44512",
    "recipient_country": "United States",
    "covered_recipient_specialty_1": "Allopathic & Osteopathic Physicians|Internal Medicine",
    "applicable_manufacturer_or_applicable_gpo_making_payment_id": "100000191758",
    "applicable_manufacturer_or_applicable_gpo_making_payment_name": "Shockwave Medical, Inc",
    "applicable_manufacturer_or_applicable_gpo_making_payment_state": "CA",
    "applicable_manufacturer_or_applicable_gpo_making_payment_country": "United States",
    "total_amount_of_payment_usdollars": "119.00",
    "date_of_payment": "05/01/2025",
    "payment_publication_date": "06/30/2026",
    "number_of_payments_included_in_total_amount": "1",
    "nature_of_payment_or_transfer_of_value": "Food and Beverage",
    "form_of_payment_or_transfer_of_value": "In-kind items and services",
    "program_year": "2025",
    "name_of_drug_or_biological_or_device_or_medical_supply_1": "Shockwave C2 Catheter",
    "product_category_or_therapeutic_area_1": "Cardiology",
    "covered_or_noncovered_indicator_1": "Covered",
    "indicate_drug_or_biological_or_device_or_medical_supply_1": "Device",
}

# A teaching-hospital
HOSPITAL_ROW = {
    "record_id": "2000000001",
    "covered_recipient_type": "Covered Recipient Teaching Hospital",
    "teaching_hospital_id": "15820",
    "teaching_hospital_ccn": "050025",
    "teaching_hospital_name": "Langley Porter Psychiatric Hospital",
    "recipient_state": "CA",
    "applicable_manufacturer_or_applicable_gpo_making_payment_id": "100000000123",
    "applicable_manufacturer_or_applicable_gpo_making_payment_name": "Acme Pharma",
    "total_amount_of_payment_usdollars": "5000",
    "date_of_payment": "11/15/2025",
    "program_year": "2025",
}



def test_to_staging_row_parses_types_and_dates():
    row = transform.to_staging_row(PHYSICIAN_ROW)
    assert row is not None
    assert row["total_amount_of_payment_usdollars"] == 119.0 
    assert row["number_of_payments"] == 1 
    assert row["program_year"] == 2025
    assert row["date_of_payment"] == "2025-05-01"
    assert row["payment_publication_date"] == "2026-06-30"


def test_to_staging_row_renames_columns():
    row = transform.to_staging_row(PHYSICIAN_ROW)
    assert row["manufacturer_id"] == "100000191758" 
    assert row["product_name_1"] == "Shockwave C2 Catheter"
    assert row["product_type_1"] == "Device"


def test_clean_row_stores_no_raw_payload():
    row = transform.to_staging_row(PHYSICIAN_ROW)
    assert row["dq_flags"] is None
    assert row["raw_payload"] is None


def test_flagged_row_keeps_raw_payload():
    flagged = dict(PHYSICIAN_ROW)
    flagged["applicable_manufacturer_or_applicable_gpo_making_payment_id"] = ""
    row = transform.to_staging_row(flagged)
    assert "missing_manufacturer_id" in row["dq_flags"]
    assert json.loads(row["raw_payload"])["record_id"] == "1157125359"


def test_to_staging_row_drops_rows_without_id_or_amount():
    assert transform.to_staging_row({"record_id": "", "total_amount_of_payment_usdollars": "5"}) is None
    assert transform.to_staging_row({"record_id": "1", "total_amount_of_payment_usdollars": ""}) is None


@pytest.fixture
def db(tmp_path):
    """A fresh database built from the real schema, with the fixtures staged+built."""
    conn = load.create_database(tmp_path / "test.db", config.SCHEMA_PATH)
    load.load_staging(conn, [PHYSICIAN_ROW, HOSPITAL_ROW])
    load.build_final_tables(conn)
    yield conn
    conn.close()


def _count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_build_populates_final_tables(db):
    assert _count(db, "stg_general_payments") == 2
    assert _count(db, "payment") == 2
    assert _count(db, "manufacturer") == 2
    assert _count(db, "payment_product") == 1


def test_recipient_keys(db):
    ids = {r[0] for r in db.execute("SELECT recipient_id FROM recipient")}
    assert ids == {"CR-429303", "TH-15820"}


def test_payment_count_matches_staging(db):
    assert _count(db, "payment") == _count(db, "stg_general_payments")


def test_no_duplicate_record_ids(db):
    dupes = db.execute(
        "SELECT record_id FROM payment GROUP BY record_id HAVING COUNT(*) > 1"
    ).fetchall()
    assert dupes == []


def test_pipeline_is_idempotent(db):
    load.load_staging(db, [PHYSICIAN_ROW, HOSPITAL_ROW])
    load.build_final_tables(db) 
    assert _count(db, "payment") == 2
    assert _count(db, "payment_product") == 1


def test_reset_staging_gives_full_refresh(db):
    load.reset_staging(db)
    assert _count(db, "stg_general_payments") == 0
    load.load_staging(db, [HOSPITAL_ROW])
    load.build_final_tables(db)
    assert _count(db, "stg_general_payments") == 1
    assert _count(db, "payment") == 1


def test_quality_checks_pass_on_clean_data(db):
    data_quality.run_staging_quality_checks(db, ["OH", "CA"])
    data_quality.run_final_quality_checks(db)  # should not raise


def test_staging_check_catches_negative_amount(tmp_path):
    conn = load.create_database(tmp_path / "bad.db", config.SCHEMA_PATH)
    bad_row = dict(PHYSICIAN_ROW, record_id="9", total_amount_of_payment_usdollars="-5.00")
    load.load_staging(conn, [bad_row])
    with pytest.raises(ValueError, match="amount"):
        data_quality.run_staging_quality_checks(conn, ["OH"])
    conn.close()


class _FakeRaw(io.BytesIO):
    decode_content = False


class _FakeResponse:
    def __init__(self, data: bytes):
        self.raw = _FakeRaw(data)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass


def test_download_records_filters_by_state(monkeypatch):
    csv_text = (
        "Record_ID,Recipient_State,Total_Amount_of_Payment_USDollars\n"
        "1,TX,10\n2,NY,20\n3,TX,30\n4,CA,40\n"
    )
    monkeypatch.setattr(extract, "resolve_csv_url", lambda session: "http://fake/csv")
    monkeypatch.setattr(extract, "_get_with_retry", lambda session, url, **kw: _FakeResponse(csv_text.encode()))

    rows = list(extract.download_records(["TX"], max_records=10))
    assert {r["record_id"] for r in rows} == {"1", "3"} 
    assert all(r["recipient_state"] == "TX" for r in rows) 


def test_analysis_writes_all_outputs(tmp_path):
    db_path = tmp_path / "a.db"
    conn = load.create_database(db_path, config.SCHEMA_PATH)
    load.load_staging(conn, [PHYSICIAN_ROW, HOSPITAL_ROW])
    load.build_final_tables(conn)
    conn.close()

    output_dir = tmp_path / "outputs"
    analysis.run_analysis(db_path, output_dir)
    for name in (
        "top_manufacturers.csv", "payment_by_nature.csv", "payment_concentration.csv",
        "top_products.csv", "top_specialties.csv", "top_specialties.png", "amount_distribution.png",
    ):
        assert (output_dir / name).exists(), f"missing {name}"
