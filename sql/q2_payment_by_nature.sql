-- Q2. How does spend break down by the nature of the payment?
-- Comparing total dollars against payment count separates the many small
-- transactions (e.g. food and beverage) from the fewer high-value ones
-- (e.g. consulting or royalties).
SELECT
    p.nature_of_payment,
    COUNT(*) AS payment_count,
    ROUND(SUM(p.payment_amount), 2) AS total_payment_amount,
    ROUND(AVG(p.payment_amount), 2) AS avg_payment_amount
FROM payment p
GROUP BY p.nature_of_payment
ORDER BY total_payment_amount DESC
LIMIT 15;
