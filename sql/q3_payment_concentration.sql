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
