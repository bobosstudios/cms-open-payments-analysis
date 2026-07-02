# Entity-Relationship Diagram

`stg_general_payments` is the source-shaped staging landing table. The four normalized tables below are built from it.

```mermaid
erDiagram
    manufacturer ||--o{ payment : "makes"
    recipient    ||--o{ payment : "receives"
    payment      ||--o{ payment_product : "relates to"

    manufacturer {
        TEXT manufacturer_id PK
        TEXT manufacturer_name
        TEXT manufacturer_state
        TEXT manufacturer_country
    }

    recipient {
        TEXT recipient_id PK
        TEXT recipient_type
        TEXT covered_recipient_profile_id
        TEXT recipient_npi
        TEXT teaching_hospital_id
        TEXT teaching_hospital_ccn
        TEXT recipient_name
        TEXT recipient_city
        TEXT recipient_state
        TEXT recipient_zip_code
        TEXT recipient_country
        TEXT primary_specialty
    }

    payment {
        TEXT record_id PK
        TEXT manufacturer_id FK
        TEXT recipient_id FK
        REAL payment_amount
        TEXT payment_date
        INTEGER number_of_payments
        INTEGER program_year
        TEXT publication_date
        TEXT nature_of_payment
        TEXT form_of_payment
        TEXT change_type
        TEXT dispute_status
        TEXT related_product_indicator
    }

    payment_product {
        INTEGER payment_product_id PK
        TEXT record_id FK
        INTEGER product_number
        TEXT product_name
        TEXT product_category
        TEXT covered_indicator
        TEXT product_type
        TEXT ndc
        TEXT pdi
    }
```

## Pipeline flow

```
CSV distribution ──stream+filter──> stg_general_payments ──build_final_tables.sql──> manufacturer
                                                                                     recipient
                                                                                     payment
                                                                                     payment_product
```
