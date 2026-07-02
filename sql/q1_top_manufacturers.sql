-- Q1. Which manufacturers have the largest financial footprint in the slice?
-- Ranks making-payment entities by total dollars, with volume and average size
-- for context.
SELECT
    m.manufacturer_name,
    COUNT(*) AS payment_count,
    ROUND(SUM(p.payment_amount), 2) AS total_payment_amount,
    ROUND(AVG(p.payment_amount), 2) AS avg_payment_amount
FROM payment p
JOIN manufacturer m ON m.manufacturer_id = p.manufacturer_id
GROUP BY m.manufacturer_name
ORDER BY total_payment_amount DESC
LIMIT 10;
