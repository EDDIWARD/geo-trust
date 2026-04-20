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

CREATE TABLE IF NOT EXISTS scan_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    scan_time TEXT NOT NULL,
    scan_lng REAL,
    scan_lat REAL,
    scan_accuracy REAL,
    device_info TEXT,
    is_first_scan INTEGER NOT NULL DEFAULT 0 CHECK (is_first_scan IN (0, 1)),
    distance_from_last REAL,
    time_from_last REAL,
    estimated_speed REAL,
    risk_level TEXT NOT NULL DEFAULT 'none' CHECK (
        risk_level IN ('none', 'low', 'medium', 'high')
    ),
    risk_detected INTEGER NOT NULL DEFAULT 0 CHECK (risk_detected IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS dashboard_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    event_time TEXT NOT NULL,
    product_id INTEGER,
    product_code TEXT,
    location_lng REAL,
    location_lat REAL,
    related_lng REAL,
    related_lat REAL,
    message TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info' CHECK (
        severity IN ('info', 'warning', 'error')
    ),
    risk_level TEXT NOT NULL DEFAULT 'none' CHECK (
        risk_level IN ('none', 'low', 'medium', 'high')
    ),
    estimated_speed REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS product_media_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_key TEXT NOT NULL,
    display_name TEXT NOT NULL,
    media_type TEXT NOT NULL CHECK (
        media_type IN ('product_image', 'cert', 'gallery', 'video_cover')
    ),
    title TEXT,
    file_url TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_process_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_key TEXT NOT NULL,
    step_no INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    image_url TEXT,
    time_text TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_video_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_key TEXT NOT NULL,
    title TEXT NOT NULL,
    video_url TEXT NOT NULL,
    cover_url TEXT,
    source_type TEXT NOT NULL DEFAULT 'local' CHECK (
        source_type IN ('local', 'external')
    ),
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_upload_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    image_url TEXT NOT NULL,
    original_name TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
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

CREATE INDEX IF NOT EXISTS idx_scan_records_product_id
    ON scan_records(product_id);

CREATE INDEX IF NOT EXISTS idx_scan_records_scan_time
    ON scan_records(scan_time);

CREATE INDEX IF NOT EXISTS idx_dashboard_events_event_time
    ON dashboard_events(event_time);

CREATE INDEX IF NOT EXISTS idx_dashboard_events_event_type
    ON dashboard_events(event_type);

CREATE INDEX IF NOT EXISTS idx_product_media_profiles_key_type
    ON product_media_profiles(product_key, media_type, sort_order);

CREATE INDEX IF NOT EXISTS idx_product_process_profiles_key
    ON product_process_profiles(product_key, step_no);

CREATE INDEX IF NOT EXISTS idx_product_video_profiles_key
    ON product_video_profiles(product_key, sort_order);

CREATE INDEX IF NOT EXISTS idx_product_upload_images_product
    ON product_upload_images(product_id, sort_order, id);

CREATE TABLE IF NOT EXISTS mock_import_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mock_product_families (
    family_id TEXT PRIMARY KEY,
    family_name TEXT NOT NULL,
    category TEXT NOT NULL,
    region_name TEXT NOT NULL,
    season TEXT,
    tags_json TEXT NOT NULL,
    core_json TEXT NOT NULL,
    origin_json TEXT NOT NULL,
    reference_note TEXT,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mock_product_variants (
    variant_id TEXT PRIMARY KEY,
    family_id TEXT NOT NULL,
    variant_name TEXT NOT NULL,
    channel TEXT,
    price_band TEXT,
    unit_price REAL,
    launch_quantity INTEGER,
    presentation_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY (family_id) REFERENCES mock_product_families(family_id)
);

CREATE TABLE IF NOT EXISTS mock_city_profiles (
    city TEXT PRIMARY KEY,
    profile_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mock_analytics_weights (
    section TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mock_rag_documents (
    doc_id TEXT PRIMARY KEY,
    title TEXT,
    source_group TEXT,
    theme_path TEXT,
    source_path TEXT,
    file_type TEXT,
    text_length INTEGER,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mock_rag_chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_id TEXT,
    sequence INTEGER,
    title TEXT,
    theme_path TEXT,
    text_length INTEGER,
    is_conclusion_like INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mock_rag_insights (
    insight_id TEXT PRIMARY KEY,
    doc_id TEXT,
    source_chunk_id TEXT,
    title TEXT,
    insight_type TEXT,
    theme_path TEXT,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mock_rag_knowledge_cards (
    doc_id TEXT PRIMARY KEY,
    title TEXT,
    theme_path TEXT,
    source_path TEXT,
    payload_json TEXT NOT NULL
);
