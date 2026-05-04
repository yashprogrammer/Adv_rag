-- E-commerce seed data
-- Run after 001_create_users.sql.
-- Seeded identifiers are referenced by eval/seed_questions.yaml goldens
-- (e.g. ORD-2024-0042 in q-003, ABC-12345 in q-007, PROD-0099 in q-008/q-020).

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
    order_number VARCHAR(32) UNIQUE,
    customer_id INTEGER REFERENCES customers(id),
    total DECIMAL(10,2) NOT NULL,
    status VARCHAR(32) DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Idempotent ALTER for installs that pre-date the order_number column.
ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_number VARCHAR(32) UNIQUE;

CREATE TABLE IF NOT EXISTS returns (
    id SERIAL PRIMARY KEY,
    return_number VARCHAR(32) UNIQUE,
    order_id INTEGER REFERENCES orders(id),
    product_sku VARCHAR(64),
    reason VARCHAR(256),
    refund_amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(32) DEFAULT 'processing',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- Customers ----------
-- 4 of 7 are in Germany (golden q-018: "list customers in Germany").
INSERT INTO customers (name, email, country, tier) VALUES
    ('Acme Corp',       'acme@example.com',     'Germany',        'enterprise'),
    ('Beta Ltd',        'beta@example.com',     'France',         'standard'),
    ('Gamma Inc',       'gamma@example.com',    'Germany',        'enterprise'),
    ('Delta GmbH',      'delta@example.com',    'Germany',        'enterprise'),
    ('Echo Solutions',  'echo@example.com',     'United States',  'standard'),
    ('Foxtrot Trading', 'foxtrot@example.com',  'United Kingdom', 'standard'),
    ('Helios Retail',   'helios@example.com',   'Germany',        'standard')
ON CONFLICT (email) DO NOTHING;

-- ---------- Products ----------
-- ABC-12345 and PROD-0099 are featured in seed PDFs (warranty.txt, refund-policy.txt).
-- Required for goldens q-007, q-008, q-020.
INSERT INTO products (sku, name, price, category, stock) VALUES
    ('SKU-001',   'Wireless Mouse',                    29.99,   'electronics', 150),
    ('SKU-002',   'Mechanical Keyboard',               89.99,   'electronics',  80),
    ('SKU-003',   'USB-C Cable',                       12.99,   'accessories', 300),
    ('ABC-12345', 'Premium Wireless Headphones (Pro)', 249.99,  'electronics',  45),
    ('PROD-0099', 'Premium License Bundle',            499.00,  'software',    999),
    ('SKU-004',   'Ergonomic Chair',                   349.00,  'furniture',    22),
    ('SKU-005',   '4K Monitor 27in',                   419.00,  'electronics',  18)
ON CONFLICT (sku) DO NOTHING;

-- ---------- Orders ----------
-- Order numbers in ORD-YYYY-XXXX format. ORD-2024-0042 is the literal in golden q-003.
-- Mix of pending (q-017 count) and historical (q-019 last-month aggregation).
INSERT INTO orders (order_number, customer_id, total, status, created_at) VALUES
    ('ORD-2024-0040', 1,  119.98, 'completed', now() - INTERVAL '45 days'),
    ('ORD-2024-0041', 1,   29.99, 'completed', now() - INTERVAL '40 days'),
    ('ORD-2024-0042', 3,  249.99, 'shipped',   now() - INTERVAL '12 days'),
    ('ORD-2024-0043', 2,   89.99, 'pending',   now() - INTERVAL '2 days'),
    ('ORD-2024-0044', 4,  499.00, 'pending',   now() - INTERVAL '1 day'),
    ('ORD-2024-0045', 5,  419.00, 'pending',   now() - INTERVAL '1 day'),
    ('ORD-2024-0046', 6,   42.98, 'completed', now() - INTERVAL '20 days'),
    ('ORD-2024-0047', 1,  768.99, 'completed', now() - INTERVAL '18 days'),
    ('ORD-2024-0048', 7,  349.00, 'pending',   now() - INTERVAL '6 hours'),
    ('ORD-2024-0049', 3,  999.00, 'completed', now() - INTERVAL '15 days'),
    ('ORD-2024-0050', 4, 1247.00, 'shipped',   now() - INTERVAL '8 days')
ON CONFLICT (order_number) DO NOTHING;

-- ---------- Returns ----------
-- 8 returns spanning the last ~30 days. PROD-0099 has 3 returns (golden q-020).
-- Total last-30-day return count drives golden q-019.
INSERT INTO returns (return_number, order_id, product_sku, reason, refund_amount, status, created_at)
SELECT 'RET-2024-0001', o.id, 'SKU-001',   'changed mind',              29.99,  'refund-issued', now() - INTERVAL '25 days'
FROM orders o WHERE o.order_number = 'ORD-2024-0040'
UNION ALL SELECT 'RET-2024-0002', o.id, 'PROD-0099', 'license activation issue', 449.10, 'refund-issued', now() - INTERVAL '21 days'
FROM orders o WHERE o.order_number = 'ORD-2024-0049'
UNION ALL SELECT 'RET-2024-0003', o.id, 'ABC-12345', 'defective unit',           224.99, 'refund-issued', now() - INTERVAL '18 days'
FROM orders o WHERE o.order_number = 'ORD-2024-0042'
UNION ALL SELECT 'RET-2024-0004', o.id, 'SKU-002',   'wrong color',               80.99, 'refund-issued', now() - INTERVAL '15 days'
FROM orders o WHERE o.order_number = 'ORD-2024-0046'
UNION ALL SELECT 'RET-2024-0005', o.id, 'PROD-0099', 'duplicate purchase',       499.00, 'refund-issued', now() - INTERVAL '12 days'
FROM orders o WHERE o.order_number = 'ORD-2024-0047'
UNION ALL SELECT 'RET-2024-0006', o.id, 'SKU-005',   'screen flicker',           377.10, 'inspected',     now() - INTERVAL '9 days'
FROM orders o WHERE o.order_number = 'ORD-2024-0050'
UNION ALL SELECT 'RET-2024-0007', o.id, 'SKU-004',   'damaged on arrival',       349.00, 'received',      now() - INTERVAL '5 days'
FROM orders o WHERE o.order_number = 'ORD-2024-0048'
UNION ALL SELECT 'RET-2024-0008', o.id, 'PROD-0099', 'wrong tier',               449.10, 'processing',    now() - INTERVAL '3 days'
FROM orders o WHERE o.order_number = 'ORD-2024-0049'
ON CONFLICT (return_number) DO NOTHING;
