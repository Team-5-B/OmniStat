-- Store the businesses using OmniStat
CREATE TABLE businesses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- The base....Staging table for the Universal CSV Parser
CREATE TABLE raw_csv_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    upload_date TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    original_filename VARCHAR(255),
    raw_data JSONB NOT NULL,
    status VARCHAR(50) DEFAULT 'pending'
);

-- In order to Access control for employees and managers
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL, 
    role VARCHAR(50) DEFAULT 'employee',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- This is for the Store physical products
CREATE TABLE inventory_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    item_name VARCHAR(255) NOT NULL,
    current_stock INT NOT NULL DEFAULT 0,
    unit_price NUMERIC(10, 2) DEFAULT 0.00,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);