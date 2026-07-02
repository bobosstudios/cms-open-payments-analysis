SELECT
    p.nature_of_payment,
    COUNT(*) AS payment_count,
    ROUND(SUM(p.payment_amount), 2) AS total_payment_amount,
    ROUND(AVG(p.payment_amount), 2) AS avg_payment_amount
FROM payment p
GROUP BY p.nature_of_payment
ORDER BY total_payment_amount DESC
LIMIT 15;
