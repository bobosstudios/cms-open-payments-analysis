SELECT
    r.primary_specialty,
    COUNT(*) AS payment_count,
    ROUND(SUM(p.payment_amount), 2) AS total_payment_amount
FROM payment p
JOIN recipient r ON r.recipient_id = p.recipient_id
WHERE r.primary_specialty IS NOT NULL
GROUP BY r.primary_specialty
ORDER BY total_payment_amount DESC
LIMIT 10;
