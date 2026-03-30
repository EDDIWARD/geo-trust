PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS regions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    product_type TEXT NOT NULL,
    province TEXT,
    city TEXT,
    boundary_geojson TEXT NOT NULL,
    center_lng REAL,
    center_lat REAL,
    is_enabled INTEGER NOT NULL DEFAULT 1 CHECK (is_enabled IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_code TEXT NOT NULL UNIQUE,
    product_name TEXT NOT NULL,
    batch_no TEXT NOT NULL,
    region_id INTEGER NOT NULL,
    producer_name TEXT NOT NULL,
    origin_lng REAL NOT NULL,
    origin_lat REAL NOT NULL,
    origin_accuracy REAL,
    origin_provider TEXT,
    origin_fix_time TEXT NOT NULL,
    device_id_hash TEXT NOT NULL,
    device_brand TEXT,
    device_model TEXT,
    device_os_version TEXT,
    app_version_name TEXT,
    app_version_code INTEGER,
    risk_is_mock INTEGER NOT NULL DEFAULT 0 CHECK (risk_is_mock IN (0, 1)),
    risk_is_emulator INTEGER NOT NULL DEFAULT 0 CHECK (risk_is_emulator IN (0, 1)),
    risk_is_debugger INTEGER NOT NULL DEFAULT 0 CHECK (risk_is_debugger IN (0, 1)),
    risk_dev_options_enabled INTEGER NOT NULL DEFAULT 0 CHECK (risk_dev_options_enabled IN (0, 1)),
    token TEXT NOT NULL UNIQUE,
    signature TEXT NOT NULL,
    trace_url TEXT NOT NULL,
    qr_code_url TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (region_id) REFERENCES regions(id)
);

CREATE TABLE IF NOT EXISTS register_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    batch_no TEXT NOT NULL,
    region_id INTEGER,
    producer_name TEXT NOT NULL,
    request_lng REAL,
    request_lat REAL,
    request_accuracy REAL,
    request_provider TEXT,
    request_fix_time TEXT,
    risk_is_mock INTEGER NOT NULL DEFAULT 0 CHECK (risk_is_mock IN (0, 1)),
    risk_is_emulator INTEGER NOT NULL DEFAULT 0 CHECK (risk_is_emulator IN (0, 1)),
    risk_is_debugger INTEGER NOT NULL DEFAULT 0 CHECK (risk_is_debugger IN (0, 1)),
    risk_dev_options_enabled INTEGER NOT NULL DEFAULT 0 CHECK (risk_dev_options_enabled IN (0, 1)),
    device_id_hash TEXT,
    device_brand TEXT,
    device_model TEXT,
    device_os_version TEXT,
    app_version_name TEXT,
    app_version_code INTEGER,
    result TEXT NOT NULL CHECK (
        result IN (
            'accepted',
            'rejected_outside_region',
            'rejected_mock_location',
            'rejected_device_risk',
            'rejected_invalid_payload',
            'rejected_service_disabled'
        )
    ),
    reason_code TEXT,
    reason_message TEXT,
    created_product_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (region_id) REFERENCES regions(id),
    FOREIGN KEY (created_product_id) REFERENCES products(id)
);

CREATE INDEX IF NOT EXISTS idx_regions_enabled
    ON regions(is_enabled);

CREATE INDEX IF NOT EXISTS idx_products_region_id
    ON products(region_id);

CREATE INDEX IF NOT EXISTS idx_products_token
    ON products(token);

CREATE INDEX IF NOT EXISTS idx_register_attempts_region_id
    ON register_attempts(region_id);

CREATE INDEX IF NOT EXISTS idx_register_attempts_result
    ON register_attempts(result);

CREATE INDEX IF NOT EXISTS idx_register_attempts_created_at
    ON register_attempts(created_at);
