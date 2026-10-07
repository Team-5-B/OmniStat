DROP TABLE IF EXISTS memberships CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS raw_csv_uploads CASCADE;
DROP TABLE IF EXISTS inventory_items CASCADE;
DROP TABLE IF EXISTS daily_sales_aggregates CASCADE;
DROP TABLE IF EXISTS businesses CASCADE;

CREATE TABLE businesses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL, 
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    role VARCHAR(50) DEFAULT 'employee', 
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, business_id) 
);

CREATE TABLE raw_csv_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    upload_date TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    original_filename VARCHAR(255),
    raw_data JSONB NOT NULL,
    status VARCHAR(50) DEFAULT 'pending'
);

CREATE TABLE inventory_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    item_name VARCHAR(255) NOT NULL,
    current_stock INT NOT NULL DEFAULT 0,
    unit_price NUMERIC(10, 2) DEFAULT 0.00,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE daily_sales_aggregates (
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    business_date DATE NOT NULL,
    total_revenue NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    total_profit NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    items_sold_count INT NOT NULL DEFAULT 0,
    PRIMARY KEY(business_id, business_date)
);