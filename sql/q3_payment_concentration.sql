-- Q3. How concentrated is total spend?
-- Bucket every payment into 100 equal-count groups ordered by amount, then
-- report what share of total dollars falls in the top 1% of payments. A high
-- share means spend is driven by a small number of large transfers.
--
-- The grand total is computed in the same pass with SUM() OVER (), so the
-- payment table is scanned once.
WITH ranked_payments AS (
    SELECT
        payment_amount,
        NTILE(100) OVER (ORDER BY payment_amount DESC) AS payment_percentile,
        SUM(payment_amount) OVER () AS total_amount
    FROM payment
)
SELECT
    COUNT(*) AS payments_in_top_1pct,
    ROUND(SUM(payment_amount), 2) AS top_1pct_amount,
    ROUND(SUM(payment_amount) * 100.0 / MIN(total_amount), 2) AS percent_of_total_amount
FROM ranked_payments
WHERE payment_percentile = 1;
