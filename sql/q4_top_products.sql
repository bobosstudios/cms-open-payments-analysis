-- Q4. Which products (drugs/devices) are associated with the most payment value?
-- Joins the payment fact to the payment_product child table, so it exercises the
-- normalized product group. 
-- Note: a payment can list several products, and the
-- payment amount is not split across them — so this is the payment value
-- associated with each product, and totals across products can exceed total
-- spend. payment_count uses DISTINCT record_id to stay unambiguous.
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
