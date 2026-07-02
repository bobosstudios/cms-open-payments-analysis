from __future__ import annotations
import json
from datetime import datetime
from typing import Optional

MAX_PRODUCTS = 5

SCALAR_SOURCE = {
    "record_id": "record_id",
    "change_type": "change_type",
    "covered_recipient_type": "covered_recipient_type",
    "teaching_hospital_id": "teaching_hospital_id",
    "teaching_hospital_ccn": "teaching_hospital_ccn",
    "teaching_hospital_name": "teaching_hospital_name",
    "covered_recipient_profile_id": "covered_recipient_profile_id",
    "covered_recipient_npi": "covered_recipient_npi",
    "covered_recipient_first_name": "covered_recipient_first_name",
    "covered_recipient_last_name": "covered_recipient_last_name",
    "recipient_city": "recipient_city",
    "recipient_state": "recipient_state",
    "recipient_zip_code": "recipient_zip_code",
    "recipient_country": "recipient_country",
    "covered_recipient_specialty_1": "covered_recipient_specialty_1",
    "manufacturer_id": "applicable_manufacturer_or_applicable_gpo_making_payment_id",
    "manufacturer_name": "applicable_manufacturer_or_applicable_gpo_making_payment_name",
    "manufacturer_state": "applicable_manufacturer_or_applicable_gpo_making_payment_state",
    "manufacturer_country": "applicable_manufacturer_or_applicable_gpo_making_payment_country",
    "form_of_payment": "form_of_payment_or_transfer_of_value",
    "nature_of_payment": "nature_of_payment_or_transfer_of_value",
    "dispute_status": "dispute_status_for_publication",
    "related_product_indicator": "related_product_indicator"
}

PRODUCT_SOURCE = {
    "product_name": "name_of_drug_or_biological_or_device_or_medical_supply_{n}",
    "product_category": "product_category_or_therapeutic_area_{n}",
    "covered_indicator": "covered_or_noncovered_indicator_{n}",
    "product_type": "indicate_drug_or_biological_or_device_or_medical_supply_{n}",
    "ndc": "associated_drug_or_biological_ndc_{n}",
    "pdi": "associated_device_or_medical_supply_pdi_{n}"
}


def _clean(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_iso_date(value) -> Optional[str]:
    text = _clean(value)
    if not text:
        return None
    try:
        return datetime.strptime(text, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def _to_float(value) -> Optional[float]:
    text = _clean(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_int(value) -> Optional[int]:
    text = _clean(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _has_any_product(row: dict) -> bool:
    return any(
        row.get(f"{field}_{n}")
        for n in range(1, MAX_PRODUCTS + 1)
        for field in ("product_name", "product_category", "product_type", "ndc", "pdi")
    )


def _quality_flags(raw: dict, row: dict) -> list[str]:
    flags = []
    if not _clean(raw.get("applicable_manufacturer_or_applicable_gpo_making_payment_id")):
        flags.append("missing_manufacturer_id")
    if not _clean(raw.get("covered_recipient_profile_id")) and not _clean(raw.get("teaching_hospital_id")):
        flags.append("unbuildable_recipient")
    if _clean(raw.get("date_of_payment")) and row["date_of_payment"] is None:
        flags.append("unparsed_payment_date")
    if row["total_amount_of_payment_usdollars"] < 0:
        flags.append("negative_amount")
    if (row["related_product_indicator"] or "").lower() == "yes" and not _has_any_product(row):
        flags.append("product_indicator_without_product")
    return flags


def to_staging_row(raw: dict) -> Optional[dict]:
    record_id = _clean(raw.get("record_id"))
    amount = _to_float(raw.get("total_amount_of_payment_usdollars"))
    if not record_id or amount is None:
        return None

    row = {column: _clean(raw.get(source)) for column, source in SCALAR_SOURCE.items()}
    row["total_amount_of_payment_usdollars"] = amount
    row["date_of_payment"] = _to_iso_date(raw.get("date_of_payment"))
    row["number_of_payments"] = _to_int(raw.get("number_of_payments_included_in_total_amount"))
    row["program_year"] = _to_int(raw.get("program_year"))
    row["payment_publication_date"] = _to_iso_date(raw.get("payment_publication_date"))

    for n in range(1, MAX_PRODUCTS + 1):
        for field, template in PRODUCT_SOURCE.items():
            row[f"{field}_{n}"] = _clean(raw.get(template.format(n=n)))
        # print(field)

    flags = _quality_flags(raw, row)
    row["dq_flags"] = ",".join(flags) if flags else None
    row["raw_payload"] = json.dumps(raw, separators=(",", ":")) if flags else None

    return row
