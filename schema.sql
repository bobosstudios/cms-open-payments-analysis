-- CMS Open Payments — SQLite schema
--
-- The CMS General Payment file is a wide, denormalized flat file. The pipeline
-- lands it in a source-shaped staging table (stg_general_payments) and then
-- builds a small star-style model from staging: a payment fact table, two
-- dimensions (manufacturer, recipient), and a child table for the repeating
-- product group. Staging is the durable checkpoint; the final tables are rebuilt
-- from it on every run (see sql/build_final_tables.sql).
--
-- Datatype principle: analytical measures are numeric (REAL / INTEGER), while
-- every identifier and code stays TEXT (record_id, manufacturer_id, NPI, CCN,
-- ZIP, NDC, PDI). We never do arithmetic on identifiers, and TEXT preserves
-- leading zeros and ZIP+4 formatting.
PRAGMA foreign_keys = ON;

-- Staging: a curated, renamed subset of the source columns with light typing.
-- dq_flags records any row-level data-quality concerns; raw_payload preserves the
-- original row as JSON, but only for flagged rows (clean rows store NULL), keeping
-- the table lean while retaining the source for exactly the rows worth inspecting.
CREATE TABLE IF NOT EXISTS stg_general_payments (
    record_id                          TEXT PRIMARY KEY,
    dq_flags                           TEXT, -- comma-separated row-level flags, else NULL
    raw_payload                        TEXT, -- original row as JSON, only when dq_flags is set    
    change_type                        TEXT,
    covered_recipient_type             TEXT,
    teaching_hospital_id               TEXT,
    teaching_hospital_ccn              TEXT,
    teaching_hospital_name             TEXT,
    covered_recipient_profile_id       TEXT,
    covered_recipient_npi              TEXT,
    covered_recipient_first_name       TEXT,
    covered_recipient_last_name        TEXT,
    recipient_city                     TEXT,
    recipient_state                    TEXT,
    recipient_zip_code                 TEXT,
    recipient_country                  TEXT,
    covered_recipient_specialty_1      TEXT,
    manufacturer_id                    TEXT,
    manufacturer_name                  TEXT,
    manufacturer_state                 TEXT,
    manufacturer_country               TEXT,
    total_amount_of_payment_usdollars  REAL,
    date_of_payment                    TEXT, -- ISO YYYY-MM-DD
    number_of_payments                 INTEGER,
    form_of_payment                    TEXT,
    nature_of_payment                  TEXT,
    dispute_status                     TEXT,
    related_product_indicator          TEXT,
    program_year                       INTEGER,
    payment_publication_date           TEXT, -- ISO YYYY-MM-DD
    product_name_1 TEXT, product_category_1 TEXT, covered_indicator_1 TEXT, product_type_1 TEXT, ndc_1 TEXT, pdi_1 TEXT,
    product_name_2 TEXT, product_category_2 TEXT, covered_indicator_2 TEXT, product_type_2 TEXT, ndc_2 TEXT, pdi_2 TEXT,
    product_name_3 TEXT, product_category_3 TEXT, covered_indicator_3 TEXT, product_type_3 TEXT, ndc_3 TEXT, pdi_3 TEXT,
    product_name_4 TEXT, product_category_4 TEXT, covered_indicator_4 TEXT, product_type_4 TEXT, ndc_4 TEXT, pdi_4 TEXT,
    product_name_5 TEXT, product_category_5 TEXT, covered_indicator_5 TEXT, product_type_5 TEXT, ndc_5 TEXT, pdi_5 TEXT,
    loaded_at                          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS manufacturer (
    manufacturer_id      TEXT PRIMARY KEY,
    manufacturer_name    TEXT NOT NULL,
    manufacturer_state   TEXT,
    manufacturer_country TEXT
);

CREATE TABLE IF NOT EXISTS recipient (
    recipient_id                 TEXT PRIMARY KEY, -- 'CR-<profile_id>' or 'TH-<hospital_id>'
    recipient_type               TEXT NOT NULL, -- physician / non-physician practitioner / teaching hospital
    covered_recipient_profile_id TEXT, -- physicians and non-physician practitioners
    recipient_npi                TEXT,
    teaching_hospital_id         TEXT, -- teaching hospitals
    teaching_hospital_ccn        TEXT,
    recipient_name               TEXT,
    recipient_city               TEXT,
    recipient_state              TEXT,
    recipient_zip_code           TEXT,
    recipient_country            TEXT,
    primary_specialty            TEXT -- first reported specialty (raw taxonomy string)
);

CREATE TABLE IF NOT EXISTS payment (
    record_id                 TEXT PRIMARY KEY, -- CMS record_id, used as the idempotency key
    manufacturer_id           TEXT,
    recipient_id              TEXT,
    payment_amount            REAL NOT NULL,
    payment_date              TEXT, -- ISO YYYY-MM-DD
    number_of_payments        INTEGER,
    program_year              INTEGER,
    publication_date          TEXT, -- ISO YYYY-MM-DD
    nature_of_payment         TEXT,
    form_of_payment           TEXT,
    change_type               TEXT, -- publication/versioning flag (NEW / ADD / CHANGE / ...)
    dispute_status            TEXT,
    related_product_indicator TEXT,
    FOREIGN KEY (manufacturer_id) REFERENCES manufacturer(manufacturer_id),
    FOREIGN KEY (recipient_id)    REFERENCES recipient(recipient_id),
    CHECK (payment_amount >= 0),
    CHECK (number_of_payments IS NULL OR number_of_payments >= 0),
    CHECK (program_year IS NULL OR program_year BETWEEN 2013 AND 2030)
);

CREATE TABLE IF NOT EXISTS payment_product (
    payment_product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id          TEXT NOT NULL,
    product_number     INTEGER NOT NULL, -- 1..5, position within the source row's product group
    product_name       TEXT,
    product_category   TEXT, -- product_category_or_therapeutic_area_N
    covered_indicator  TEXT, -- Covered / Non-Covered
    product_type       TEXT, -- Drug / Biological / Device / Medical Supply
    ndc                TEXT, -- associated_drug_or_biological_ndc_N
    pdi                TEXT, -- associated_device_or_medical_supply_pdi_N
    FOREIGN KEY (record_id) REFERENCES payment(record_id),
    UNIQUE (record_id, product_number),
    CHECK (product_number BETWEEN 1 AND 5)
);

-- Indexes aligned to the pipeline and the analytical queries.
CREATE INDEX IF NOT EXISTS idx_stg_state                   ON stg_general_payments(recipient_state);
CREATE INDEX IF NOT EXISTS idx_stg_program_year            ON stg_general_payments(program_year);
CREATE INDEX IF NOT EXISTS idx_payment_manufacturer        ON payment(manufacturer_id);
CREATE INDEX IF NOT EXISTS idx_payment_recipient           ON payment(recipient_id);
CREATE INDEX IF NOT EXISTS idx_payment_nature              ON payment(nature_of_payment);
CREATE INDEX IF NOT EXISTS idx_payment_amount              ON payment(payment_amount);
CREATE INDEX IF NOT EXISTS idx_payment_program_year_amount ON payment(program_year, payment_amount);
CREATE INDEX IF NOT EXISTS idx_payment_date                ON payment(payment_date);
CREATE INDEX IF NOT EXISTS idx_recipient_state             ON recipient(recipient_state);
CREATE INDEX IF NOT EXISTS idx_recipient_state_specialty   ON recipient(recipient_state, primary_specialty);
CREATE INDEX IF NOT EXISTS idx_product_record              ON payment_product(record_id);
CREATE INDEX IF NOT EXISTS idx_product_name                ON payment_product(product_name);
