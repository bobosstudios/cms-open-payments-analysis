-- Build the normalized final tables from stg_general_payments.
--
-- Final tables are rebuilt from staging on every run so they always reflect the
-- current staging contents (staging is the durable checkpoint). All the
-- relational modeling — dimension keys, the MISSING- manufacturer fallback, the
-- CR-/TH- recipient keys, and product explode lives here in SQL.
--
-- Key expressions (manufacturer resolved key, recipient id) are repeated in the
-- dimension insert and the payment insert so foreign keys always resolve.

-- 1) Clear final tables in child -> parent order.
DELETE FROM payment_product;
DELETE FROM payment;
DELETE FROM recipient;
DELETE FROM manufacturer;

-- 2) Manufacturer dimension. Resolve a never-null key: the source id, else a
--    deterministic MISSING- key from the name, else a catch-all.
INSERT OR IGNORE INTO manufacturer (manufacturer_id, manufacturer_name, manufacturer_state, manufacturer_country)
SELECT
    COALESCE(
        NULLIF(TRIM(manufacturer_id), ''),
        'MISSING-' || UPPER(REPLACE(NULLIF(TRIM(manufacturer_name), ''), ' ', '_')),
        'MISSING-MANUFACTURER'
    ) AS manufacturer_id,
    COALESCE(
        NULLIF(TRIM(manufacturer_name), ''),
        NULLIF(TRIM(manufacturer_id), ''),
        'MISSING-MANUFACTURER'
    ) AS manufacturer_name,
    NULLIF(TRIM(manufacturer_state), ''),
    NULLIF(TRIM(manufacturer_country), '')
FROM stg_general_payments;

-- 3) Recipient dimension. Covered recipients (physicians and non-physician
--    practitioners) key on the profile id; teaching hospitals key on the
--    hospital id. Rows with neither identifier are left out (payment.recipient_id
--    stays NULL) rather than grouped under a fake recipient.
INSERT OR IGNORE INTO recipient (
    recipient_id, recipient_type, covered_recipient_profile_id, recipient_npi,
    teaching_hospital_id, teaching_hospital_ccn, recipient_name, recipient_city,
    recipient_state, recipient_zip_code, recipient_country, primary_specialty
)
SELECT
    CASE
        WHEN NULLIF(TRIM(covered_recipient_profile_id), '') IS NOT NULL
            THEN 'CR-' || TRIM(covered_recipient_profile_id)
        WHEN NULLIF(TRIM(teaching_hospital_id), '') IS NOT NULL
            THEN 'TH-' || TRIM(teaching_hospital_id)
    END AS recipient_id,
    COALESCE(NULLIF(TRIM(covered_recipient_type), ''), 'Unknown'),
    NULLIF(TRIM(covered_recipient_profile_id), ''),
    NULLIF(TRIM(covered_recipient_npi), ''),
    NULLIF(TRIM(teaching_hospital_id), ''),
    NULLIF(TRIM(teaching_hospital_ccn), ''),
    CASE
        WHEN NULLIF(TRIM(covered_recipient_profile_id), '') IS NOT NULL
            THEN NULLIF(TRIM(COALESCE(covered_recipient_first_name, '') || ' ' || COALESCE(covered_recipient_last_name, '')), '')
        WHEN NULLIF(TRIM(teaching_hospital_id), '') IS NOT NULL
            THEN NULLIF(TRIM(teaching_hospital_name), '')
    END AS recipient_name,
    NULLIF(TRIM(recipient_city), ''),
    NULLIF(TRIM(recipient_state), ''),
    NULLIF(TRIM(recipient_zip_code), ''),
    NULLIF(TRIM(recipient_country), ''),
    NULLIF(TRIM(covered_recipient_specialty_1), '')
FROM stg_general_payments
WHERE NULLIF(TRIM(covered_recipient_profile_id), '') IS NOT NULL
   OR NULLIF(TRIM(teaching_hospital_id), '') IS NOT NULL;

-- 4) Payment fact. Same resolved keys as the dimensions so FKs always match.
INSERT OR IGNORE INTO payment (
    record_id, manufacturer_id, recipient_id, payment_amount, payment_date,
    number_of_payments, program_year, publication_date, nature_of_payment,
    form_of_payment, change_type, dispute_status, related_product_indicator
)
SELECT
    record_id,
    COALESCE(
        NULLIF(TRIM(manufacturer_id), ''),
        'MISSING-' || UPPER(REPLACE(NULLIF(TRIM(manufacturer_name), ''), ' ', '_')),
        'MISSING-MANUFACTURER'
    ),
    CASE
        WHEN NULLIF(TRIM(covered_recipient_profile_id), '') IS NOT NULL
            THEN 'CR-' || TRIM(covered_recipient_profile_id)
        WHEN NULLIF(TRIM(teaching_hospital_id), '') IS NOT NULL
            THEN 'TH-' || TRIM(teaching_hospital_id)
    END,
    total_amount_of_payment_usdollars,
    date_of_payment,
    number_of_payments,
    program_year,
    payment_publication_date,
    nature_of_payment,
    form_of_payment,
    change_type,
    dispute_status,
    related_product_indicator
FROM stg_general_payments;

-- 5) Payment product child table. Explode the five product slots, keeping only
--    slots with a real product (a lone covered indicator is not enough).
INSERT OR IGNORE INTO payment_product (record_id, product_number, product_name, product_category, covered_indicator, product_type, ndc, pdi)
    SELECT record_id, 1, NULLIF(TRIM(product_name_1), ''), NULLIF(TRIM(product_category_1), ''), NULLIF(TRIM(covered_indicator_1), ''), NULLIF(TRIM(product_type_1), ''), NULLIF(TRIM(ndc_1), ''), NULLIF(TRIM(pdi_1), '')
    FROM stg_general_payments
    WHERE COALESCE(NULLIF(TRIM(product_name_1), ''), NULLIF(TRIM(product_category_1), ''), NULLIF(TRIM(product_type_1), ''), NULLIF(TRIM(ndc_1), ''), NULLIF(TRIM(pdi_1), '')) IS NOT NULL
UNION ALL
    SELECT record_id, 2, NULLIF(TRIM(product_name_2), ''), NULLIF(TRIM(product_category_2), ''), NULLIF(TRIM(covered_indicator_2), ''), NULLIF(TRIM(product_type_2), ''), NULLIF(TRIM(ndc_2), ''), NULLIF(TRIM(pdi_2), '')
    FROM stg_general_payments
    WHERE COALESCE(NULLIF(TRIM(product_name_2), ''), NULLIF(TRIM(product_category_2), ''), NULLIF(TRIM(product_type_2), ''), NULLIF(TRIM(ndc_2), ''), NULLIF(TRIM(pdi_2), '')) IS NOT NULL
UNION ALL
    SELECT record_id, 3, NULLIF(TRIM(product_name_3), ''), NULLIF(TRIM(product_category_3), ''), NULLIF(TRIM(covered_indicator_3), ''), NULLIF(TRIM(product_type_3), ''), NULLIF(TRIM(ndc_3), ''), NULLIF(TRIM(pdi_3), '')
    FROM stg_general_payments
    WHERE COALESCE(NULLIF(TRIM(product_name_3), ''), NULLIF(TRIM(product_category_3), ''), NULLIF(TRIM(product_type_3), ''), NULLIF(TRIM(ndc_3), ''), NULLIF(TRIM(pdi_3), '')) IS NOT NULL
UNION ALL
    SELECT record_id, 4, NULLIF(TRIM(product_name_4), ''), NULLIF(TRIM(product_category_4), ''), NULLIF(TRIM(covered_indicator_4), ''), NULLIF(TRIM(product_type_4), ''), NULLIF(TRIM(ndc_4), ''), NULLIF(TRIM(pdi_4), '')
    FROM stg_general_payments
    WHERE COALESCE(NULLIF(TRIM(product_name_4), ''), NULLIF(TRIM(product_category_4), ''), NULLIF(TRIM(product_type_4), ''), NULLIF(TRIM(ndc_4), ''), NULLIF(TRIM(pdi_4), '')) IS NOT NULL
UNION ALL
    SELECT record_id, 5, NULLIF(TRIM(product_name_5), ''), NULLIF(TRIM(product_category_5), ''), NULLIF(TRIM(covered_indicator_5), ''), NULLIF(TRIM(product_type_5), ''), NULLIF(TRIM(ndc_5), ''), NULLIF(TRIM(pdi_5), '')
    FROM stg_general_payments
    WHERE COALESCE(NULLIF(TRIM(product_name_5), ''), NULLIF(TRIM(product_category_5), ''), NULLIF(TRIM(product_type_5), ''), NULLIF(TRIM(ndc_5), ''), NULLIF(TRIM(pdi_5), '')) IS NOT NULL;
