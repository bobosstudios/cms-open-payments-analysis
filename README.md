# cms-open-payments-analysis

A small, reproducible data pipeline that ingests **CMS Open Payments General Payment Data** from the public CMS CSV distribution, stages it, models it into a normalized SQLite schema, checks data quality, and answers business-style questions with SQL and python.

## Quickstart

```bash
git clone https://github.com/bobosstudios/cms-open-payments-analysis.git && cd cms-open-payments-analysis
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 main.py           # TX + NY, 250k records — results land in outputs/
```

That's it. The pipeline downloads the data, builds the database, runs all quality
checks, and writes the analysis CSVs and charts to `outputs/`. See
[How to Run](#how-to-run) for CLI options and the Docker path.


## Project Overview

Every year, drug and medical-device manufacturers (and group purchasing organizations) report the payments and transfers of value they make to physicians
and teaching hospitals. CMS publishes this under the Open Payments program. This project runs a clean `staging → final → data-quality → analysis` pipeline:

```
CSV distribution (stream + filter by state)
        ↓
stg_general_payments        (source-shaped landing, light typing)
        ↓  (SQL: build_final_tables.sql)
manufacturer · recipient · payment · payment_product   (normalized model)
        ↓
data-quality checks (staging → final → analysis outputs)
        ↓
analysis outputs (4 SQL questions + 1 pandas chart)
```

The whole thing runs from one command and rebuilds the database from scratch.

## Dataset

- **Source:** CMS Open Payments, General Payment Data, **Program Year 2025**.
- **Landing page & data dictionary:** <https://openpaymentsdata.cms.gov/dataset/fb0b1734-1410-429d-92f6-3f4b35218e5e>
- **Ingestion:** the full-year CSV distribution on `download.cms.gov`. The download
  URL is versioned by publication date, so the pipeline resolves it at runtime from
  the dataset's metastore item.


### Why this dataset

I picked CMS Open Payments because it fits the exercise and the healthcare/payment domain very well. The data is public, machine-readable, and large enough to be meaningful without needing a private login or paid API.

What I also liked about this dataset is that it is not already clean and perfectly modeled. It comes as a wide, denormalized file with repeated fields, like multiple specialties and up to five products tied to one payment record. That makes it a better data engineering exercise because I can show how I would take a real-world source file, land it in staging, apply data quality checks, and model it into cleaner relational tables for analysis.

In short, this dataset lets me show more than just loading a CSV. It lets me show ingestion, staging, normalization, idempotency, data quality, SQL analysis, and python-based visualization in one project.

### Why the CSV, not the API

CMS offers both an API and downloadable CSV distributions. This project streams the
CSV because it is the right tool for bulk local ingestion: the datastore query API is meant for small filtered lookups and degrades badly on deep offset pagination, whereas the CSV is a fast flat-file download. Streaming the CSV and
filtering to the selected states locally makes the pipeline faster and more reliable for a 250,000-record local SQLite load.


## Schema Design

A source-shaped staging table plus four normalized tables: a `payment` fact table,
two dimensions (`manufacturer`, `recipient`), and a `payment_product` child table
for the repeating product group. See [`schema.sql`](schema.sql), the build logic in
[`sql/build_final_tables.sql`](sql/build_final_tables.sql), and the ER diagram in
[`diagrams/er_diagram.md`](diagrams/er_diagram.md).

```
manufacturer ──< payment >── recipient
                    │
                    └──< payment_product
```

A few deliberate choices:

- **Staging vs final.** `stg_general_payments` is a source-shaped landing area.
  A `dq_flags` column records any row-level quality concerns, and `raw_payload`
  keeps the original row as JSON **only for flagged rows** (clean rows store
  `NULL`) — so the source is preserved for exactly the rows worth inspecting without bloating the table. Each normal run is a **full refresh**: staging is cleared and reloaded with exactly the requested
  states/limit, and the final tables are then **rebuilt from staging**. So a run
  always reflects precisely the slice you asked for — you can change `--states`
  between runs freely without mixing scopes. (`--reuse-staging` skips the refresh and rebuilds finals from whatever is already staged.)
  *Design note:* a scoped full refresh is the right trade-off for a local,CLI-driven SQLite tool — it keeps the database and outputs aligned with the run
  parameters and avoids stale-data footguns. In a production pipeline you'd
  instead keep an append-only raw/staging layer with run metadata and
  partitioning (see Future Improvements).
- **No intermediate layer.** With one source dataset and a small final model, a
  separate intermediate layer would be overkill. Staging gives traceability; the
  final tables give the relational model used for analysis.
- **Staging shares the database** using an `stg_` prefix, since SQLite has no
  schema namespaces (`CREATE SCHEMA`); in a warehouse it would live in a separate
  `staging` schema, distinct from the analytics/marts schema.
- **`record_id`** is the primary key of `payment` and the natural idempotency key.
- **Datatypes.** SQLite is flexible with types, but the schema intentionally casts
  analytical values to numeric types (amounts to `REAL`, counts/years to
  `INTEGER`) while keeping every identifier and code as `TEXT` (`record_id`,
  `manufacturer_id`, NPI, CCN, ZIP, NDC, PDI). This gives correct aggregations
  while avoiding formatting problems (leading zeros, ZIP+4) on identifiers.
- **Recipient keys:** physicians and non-physician practitioners share CMS's
  `profile_id` and are keyed `CR-<profile_id>`; teaching hospitals are keyed
  `TH-<teaching_hospital_id>`.
- **Dimension dedup** is first-observed-wins: recipient and manufacturer rows load
  idempotently by source identifier; if descriptive attributes vary across records,
  the first observed version is retained.
- Only the **first reported specialty** is stored (`primary_specialty`). The five
  additional specialty fields could be normalized into a `recipient_specialty`
  table as a future improvement.

  ## Scope

By default, the pipeline analyzes records for **Texas and New York**, limited to
**250,000 records** for local SQLite performance. The state list and record limit
are configurable through CLI arguments. A state-based slice (rather than a random
cap) keeps the analysis honest and gives it a clear business boundary. The record
budget is split evenly across the requested states so each is represented.

## How to Run

Prerequisites: python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Full default run: TX + NY, 250k records
python3 main.py

# Faster smoke run
python3 main.py --states TX --max-records 2000

# Rebuild the final tables and re-run the analysis from existing staging
python3 main.py --reuse-staging
```

The default run is intentionally bounded for local performance; actual runtime
depends on your network and machine.

### Run with Docker (optional)

```bash
docker build -t cms-open-payments .
docker run --rm cms-open-payments --states TX --max-records 2000
```

Arguments after the image name are passed straight through to `main.py`.

Running `python3 main.py` will, in order: create the SQLite database and schema,
stream and stage the CSV slice, run staging data-quality checks, rebuild the final
tables, run final data-quality checks, execute the analysis (printing tables and
writing CSVs + a chart), and run the analysis output checks.

### CLI options

| Flag | Default | Description |
|------|---------|-------------|
| `--states` | `TX NY` | Recipient states to include. |
| `--max-records` | `250000` | Max records to ingest, split across states. |
| `--db-path` | `data/open_payments.db` | SQLite database location. |
| `--reuse-staging` | off | Skip the download; rebuild final tables + analysis from existing staging. |


## Analysis Questions

1. **Top manufacturers by total payment amount** (SQL) — the largest financial
   relationships in the slice. → `outputs/top_manufacturers.csv`
2. **Payment breakdown by nature of payment** (SQL) — compares total dollars
   against payment count, separating many small transfers (food & beverage) from
   fewer high-value ones (consulting, royalties). → `outputs/payment_by_nature.csv`
3. **Payment concentration** (SQL, `NTILE` window function) — what share of total
   dollars comes from the top 1% of payments. → `outputs/payment_concentration.csv`
4. **Top products by associated payment value** (SQL, joins the `payment_product`
   child table) — which drugs and devices the money tracks to.
   → `outputs/top_products.csv`
5. **Top recipient specialties by total received** (pandas + matplotlib bar chart,
   using `recipient.primary_specialty`) — this is the python data-tooling question.
   → `outputs/top_specialties.csv`, `outputs/top_specialties.png`

A supporting chart, the **log-scaled histogram of payment amounts**
(`outputs/amount_distribution.png`), visualizes the long-tailed distribution behind
the concentration finding. The five SQL queries live in [`sql/`](sql/) and are
executed from python.

Note on Q4: a payment can list several products, and the payment amount is not
split across them, so this ranks the value *associated with* each product (totals
across products can exceed total spend). `payment_count` uses `DISTINCT record_id`.

## Key Findings

From the default **TX + NY, 250,000-record** slice (your numbers will match if you
run the default; a different scope will differ):

- **Spend is highly concentrated.** The **top 1% of payments account for ~57% of
  all dollars** — a small number of large transfers dominate total value, while
  the vast majority of payments are small.
- **Volume and value tell different stories.** *Food & beverage* is by far the
  most frequent payment type (~229k payments) but averages only ~$31 each. The
  largest dollar totals instead flow through *compensation for services*,
  *consulting fees*, and *royalties* — the last averaging ~$36k across just a few
  hundred payments. Ranking by count and by dollars surfaces very different
  categories.
- **Familiar names lead total spend.** Large device and pharma manufacturers
  (e.g. Smith+Nephew, Stryker, AbbVie, Boston Scientific, Intuitive Surgical) top
  the manufacturer ranking for the slice.
- **Orthopaedics dominates by specialty.** *Orthopaedic Surgery* receives the most
  total value (~$5.0M), ahead of *Internal Medicine* and *Dermatology* — consistent
  with device-heavy manufacturers leading the spend. The top products reflect this
  mix of devices and high-cost biologics/drugs (e.g. Arthrex, Dupixent, the Da Vinci
  Surgical System, Tremfya).
- **The amount distribution is strongly long-tailed** (see
  `outputs/amount_distribution.png`), consistent with the concentration finding.

These describe patterns in the selected slice only — see
[Assumptions & Limitations](#assumptions--limitations).

## Outputs

Written to `outputs/`: five result CSVs (`top_manufacturers`, `payment_by_nature`,
`payment_concentration`, `top_products`, `top_specialties`) and two PNG charts
(`top_specialties`, `amount_distribution`). These small artifacts are committed so
reviewers can see the results directly; the raw dataset and built database are not
(see `.gitignore`).

## Data Quality Checks

The pipeline includes lightweight data quality checks at both the staging and
final-table layers, plus a sanity check on the analysis outputs. Staging checks
validate required source fields such as `record_id`, payment amount, and the
selected states. Final-table checks validate uniqueness, that the payment row count
matches staging, non-negative amounts, foreign-key relationships, and the repeated
product normalization.

Critical checks fail the pipeline because they would make the analysis unreliable.
Non-critical completeness issues — such as a missing specialty or manufacturer id —
are logged as warnings, because public CMS records may have incomplete descriptive
fields. The checks are implemented in plain python and SQL
([`src/data_quality.py`](src/data_quality.py)) rather than an external framework, so
reviewers can easily see what is validated.

Rows with a row-level concern (missing manufacturer id, no buildable recipient key,
an unparseable date, a negative amount, or a product indicator with no product) are
tagged in `stg_general_payments.dq_flags`, and their original source row is kept in
`raw_payload` for inspection:

```sql
SELECT dq_flags, COUNT(*) FROM stg_general_payments
WHERE dq_flags IS NOT NULL GROUP BY dq_flags;
```

## Assumptions & Limitations

- This analysis describes payment **patterns in the selected dataset slice**. It
  makes **no causal claims** about provider behavior, prescribing, or medical
  decision-making.
- The slice is state- and count-bounded, so totals reflect the configured scope,
  not the entire national dataset.
- Records missing a usable recipient identifier are loaded with a `NULL` recipient
  (they still count toward payment totals but not recipient-level breakdowns).
  Records missing a `record_id` or amount are dropped at staging.
- **Data-quality note.** In the default slice, ~4,150 rows (~1.7%) have
  `related_product_indicator = 'Yes'` but no product details in the source. The
  pipeline flags these as `product_indicator_without_product` in
  `stg_general_payments.dq_flags` and keeps their original row in `raw_payload`
  for inspection. No other row-level flags trip on this slice, so the data is
  otherwise clean for the fields we use.


  ## Production Considerations

This project is deliberately scoped for a local, reproducible take-home: it streams
a bounded slice with connect-level retries into a single SQLite file. The choices
that would change at production scale — intentionally *not* built here — are:

- **Orchestration.** Run the ETL as an Airflow DAG — the extract, staging load,
  data-quality, build, and analysis steps map cleanly to tasks — with scheduling,
  retries, alerting, and backfills, instead of a single CLI entrypoint.
- **Incremental / CDC loads.** Replace the full refresh with incremental loads keyed
  on `record_id` + `change_type` (CMS marks records NEW/ADD/CHANGE/UNCHANGED), so only
  new or changed records are processed.
- **Resumable downloads.** For very large pulls, resume an interrupted stream via HTTP
  Range requests rather than restarting; connect-level retry is sufficient for a
  bounded slice from a CDN.
- **Append-only raw layer + partitioning.** Land immutable raw files partitioned by
  program year / state with an `etl_run` audit table (states, limits, row counts),
  keeping a durable history rather than a scoped refresh.
- **Scale-out storage.** Move from SQLite to a columnar warehouse
  (BigQuery / Snowflake) once volumes outgrow a single file.
- **Observability & data contracts.** Track the DQ check results over time and
  enforce schema/data contracts on the source.

## Future Improvements

- Normalize the additional specialty fields into a `recipient_specialty` table.
- Upsert dimension attributes (`ON CONFLICT DO UPDATE`) to keep the latest values.
- Parameterize the program year (each CMS year is a separate dataset).

## Tests

```bash
python3 -m pytest -q
```

Covers the transform logic (type/date parsing, column renames, `raw_payload`, row
dropping), the staging→final build (row counts, recipient keys, product explode,
no duplicate `record_id`, idempotency), the data quality checks, the extract
state-filtering (against an in-memory CSV, no network), and that the analysis
writes all expected outputs.

## Project Layout

```
.
├── main.py                  # CLI entrypoint: extract -> stage -> build -> analyze
├── schema.sql               # staging + final tables, constraints, indexes
├── requirements.txt
├── Dockerfile               # optional: run the pipeline in a container
├── LICENSE
├── .github/workflows/ci.yml # runs the tests on push / PR
├── src/
│   ├── config.py            # constants: dataset id, metastore URL, paths, defaults
│   ├── extract.py           # stream + filter the CMS CSV distribution
│   ├── transform.py         # raw row -> staging row (pure functions)
│   ├── load.py              # schema creation, staging load, final-table build
│   ├── data_quality.py      # staging / final / analysis checks
│   └── analysis.py          # run SQL questions + build the chart
├── sql/
│   ├── build_final_tables.sql   # staging -> normalized final tables
│   ├── q1_top_manufacturers.sql
│   ├── q2_payment_by_nature.sql
│   ├── q3_payment_concentration.sql
│   ├── q4_top_products.sql
│   └── q5_top_specialties.sql
├── outputs/                 # result CSVs + chart (committed)
├── diagrams/                # Mermaid ER diagram
└── tests/                   # pytest suite
```

## License

Code is released under the MIT License (see [`LICENSE`](LICENSE)). The underlying
data is public and provided by CMS Open Payments.
