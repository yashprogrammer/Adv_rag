-- E-commerce seed data
-- Run after 001_create_users.sql

CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    email VARCHAR(128) UNIQUE NOT NULL,
    country VARCHAR(64),
    tier VARCHAR(16) DEFAULT 'standard',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(256) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    category VARCHAR(64),
    stock INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    total DECIMAL(10,2) NOT NULL,
    status VARCHAR(32) DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed customers
INSERT INTO customers (name, email, country, tier) VALUES
    ('Acme Corp', 'acme@example.com', 'Germany', 'enterprise'),
    ('Beta Ltd', 'beta@example.com', 'France', 'standard'),
    ('Gamma Inc', 'gamma@example.com', 'Germany', 'enterprise'),
    ('Delta GmbH', 'delta@example.com', 'Germany', 'enterprise')
ON CONFLICT (email) DO NOTHING;

-- Seed products
INSERT INTO products (sku, name, price, category, stock) VALUES
    ('SKU-001', 'Wireless Mouse', 29.99, 'electronics', 150),
    ('SKU-002', 'Mechanical Keyboard', 89.99, 'electronics', 80),
    ('SKU-003', 'USB-C Cable', 12.99, 'accessories', 300)
ON CONFLICT (sku) DO NOTHING;

-- Seed orders
INSERT INTO orders (customer_id, total, status) VALUES
    (1, 119.98, 'completed'),
    (1, 29.99, 'completed'),
    (2, 89.99, 'pending'),
    (3, 42.98, 'completed')
ON CONFLICT DO NOTHING;
