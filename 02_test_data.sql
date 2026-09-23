-- 1. Create a brand new test business
INSERT INTO businesses (name) 
VALUES ('Thai Ocha');

--  Add an admin user for Thai Ocha location with a sample password (hashed in a real application)
INSERT INTO users (business_id, email, password_hash, role)
VALUES (
    (SELECT id FROM businesses WHERE name = 'Thai Ocha' LIMIT 1), 
    'admin@thaiochadenton.com', 
    'pagilla@76201', 
    'admin'
);

-- For the sample products i have Added inventory items for Thai Ocha
INSERT INTO inventory_items (business_id, item_name, current_stock, unit_price)
VALUES 
    ((SELECT id FROM businesses WHERE name = 'Thai Ocha' LIMIT 1), 'Thai tea w Cream', 150, 4.50),
    ((SELECT id FROM businesses WHERE name = 'Thai Ocha' LIMIT 1), 'Mango Rice', 40, 7.00);

-- I have added fake daily sales with inventeory info as well
INSERT INTO daily_sales_aggregates (business_id, business_date, total_revenue, total_profit, items_sold_count)
VALUES (
    (SELECT id FROM businesses WHERE name = 'Thai Ocha' LIMIT 1), 
    CURRENT_DATE, 
    450.00, 
    310.00, 
    65
);

-- This should generate visible data
SELECT * FROM businesses WHERE name = 'Thai Ocha';
SELECT * FROM users WHERE email = 'admin@thaiochadenton.com';
SELECT * FROM inventory_items WHERE item_name IN ('Thai tea w Cream', 'Mango Rice');
SELECT * FROM daily_sales_aggregates;