SELECT
    pp.product_name,
    pp.product_type,
    COUNT(DISTINCT pp.record_id) AS payment_count,
    ROUND(SUM(p.payment_amount), 2) AS total_associated_amount
FROM payment_product pp
JOIN payment p ON p.record_id = pp.record_id
WHERE pp.product_name IS NOT NULL
GROUP BY pp.product_name, pp.product_type
ORDER BY total_associated_amount DESC
LIMIT 10;
