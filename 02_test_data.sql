-- 1. Create a brand new test business
INSERT INTO businesses (name) 
VALUES ('Thai Ocha');

-- 2. Add an owner account (using a real bcrypt hash for the password "Password123!")
INSERT INTO users (name, email, password_hash)
VALUES (
    'Siddartha Pagilla', 
    'owner@thaiochadenton.com', 
    '$2b$12$R9h/cIPz0gi.URNNX3rub.Facz9r2z1rc0LgD5N8A9EwBXYp8pY3y'
);

-- 3. Link the user to the business as an 'owner' using the memberships table
INSERT INTO memberships (user_id, business_id, role)
VALUES (
    (SELECT id FROM users WHERE email = 'owner@thaiochadenton.com' LIMIT 1),
    (SELECT id FROM businesses WHERE name = 'Thai Ocha' LIMIT 1),
    'owner'
);

-- 4. Add inventory items for Thai Ocha
INSERT INTO inventory_items (business_id, item_name, current_stock, unit_price)
VALUES 
    ((SELECT id FROM businesses WHERE name = 'Thai Ocha' LIMIT 1), 'Thai tea w Cream', 150, 4.50),
    ((SELECT id FROM businesses WHERE name = 'Thai Ocha' LIMIT 1), 'Mango Rice', 40, 7.00);

-- 5. Add some fake dashboard sales data for today
INSERT INTO daily_sales_aggregates (business_id, business_date, total_revenue, total_profit, items_sold_count)
VALUES (
    (SELECT id FROM businesses WHERE name = 'Thai Ocha' LIMIT 1), 
    CURRENT_DATE, 
    450.00, 
    310.00, 
    65
);

-- 6. Verify the data
SELECT * FROM businesses;
SELECT * FROM users;
SELECT * FROM memberships;
SELECT * FROM inventory_items;
SELECT * FROM daily_sales_aggregates;