from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


DATABASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = DATABASE_DIR.parent.parent
MOCK_DATA_DIR = REPO_ROOT / 'backend' / 'server' / 'mock_data'
SCHEMA_PATH = DATABASE_DIR / "android_backend_schema.sql"
DEFAULT_OUTPUT_PATH = DATABASE_DIR / "android_backend.db"

CITY_COORDS: dict[str, tuple[float, float]] = {
    "??": (114.3055, 30.5928),
    "??": (121.4737, 31.2304),
    "??": (120.1551, 30.2741),
    "??": (114.0579, 22.5431),
    "??": (112.9388, 28.2282),
    "??": (117.2272, 31.8206),
    "??": (115.8582, 28.6820),
    "??": (116.4074, 39.9042),
    "??": (117.2000, 39.1333),
    "??": (118.7969, 32.0603),
    "??": (120.5853, 31.2989),
    "??": (121.5503, 29.8746),
    "??": (119.2965, 26.0745),
    "??": (118.0894, 24.4798),
    "??": (113.2644, 23.1291),
    "??": (108.3669, 22.8170),
    "??": (110.3312, 20.0319),
    "??": (113.6254, 34.7466),
    "??": (108.9398, 34.3416),
    "??": (104.0665, 30.5728),
    "??": (106.5516, 29.5630),
    "??": (102.8329, 24.8801),
    "??": (106.6302, 26.6470),
    "??": (117.1201, 36.6512),
    "??": (120.3826, 36.0671),
    "??": (123.4315, 41.8057),
    "??": (121.6147, 38.9140),
    "???": (126.6424, 45.7567),
    "??": (125.3235, 43.8171),
    "???": (114.5149, 38.0428),
    "??": (112.5492, 37.8570),
    "??": (103.8343, 36.0611),
    "??": (101.7782, 36.6171),
    "??": (106.2309, 38.4872),
    "????": (87.6168, 43.8256),
}

REGION_CENTERS: list[tuple[float, float]] = [
    (109.4882, 30.2722),
    (113.9004, 29.7244),
    (110.6715, 31.7444),
    (110.9767, 30.8239),
    (111.2865, 30.6919),
    (115.3999, 30.7817),
    (114.3055, 30.5928),
    (112.8993, 30.4015),
    (114.3860, 30.5050),
    (114.5940, 30.2350),
    (113.3738, 31.7175),
    (113.9169, 30.9246),
    (120.5821, 29.9971),
    (120.1184, 30.2285),
    (120.7800, 31.4210),
]

CITY_COORD_LIST = list(CITY_COORDS.values())

PRODUCER_SUFFIXES = [
    " Cooperative",
    " Agro Tech",
    " Origin Foods",
    " Farm Group",
]


def stable_seed(*parts: object) -> int:
    raw = "|".join(str(part) for part in parts)
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16], 16)


def stable_random(*parts: object) -> random.Random:
    return random.Random(stable_seed(*parts))


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def isoformat(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def build_polygon(center_lng: float, center_lat: float, radius: float = 0.16) -> dict[str, Any]:
    return {
        "type": "Polygon",
        "coordinates": [[
            [round(center_lng - radius, 6), round(center_lat - radius, 6)],
            [round(center_lng + radius, 6), round(center_lat - radius, 6)],
            [round(center_lng + radius, 6), round(center_lat + radius, 6)],
            [round(center_lng - radius, 6), round(center_lat + radius, 6)],
            [round(center_lng - radius, 6), round(center_lat - radius, 6)],
        ]],
    }


def jitter_point(center_lng: float, center_lat: float, key: str, radius: float = 0.05) -> tuple[float, float]:
    rng = stable_random("point", key)
    lng = center_lng + (rng.random() - 0.5) * radius * 2
    lat = center_lat + (rng.random() - 0.5) * radius * 2
    return round(lng, 6), round(lat, 6)


def haversine_distance_meters(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    earth_radius = 6371000
    lat1_rad = math.radians(lat1)
    lng1_rad = math.radians(lng1)
    lat2_rad = math.radians(lat2)
    lng2_rad = math.radians(lng2)
    dlat = lat2_rad - lat1_rad
    dlng = lng2_rad - lng1_rad
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius * c


def create_extension_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
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
        """
    )


def import_extension_tables(connection: sqlite3.Connection) -> dict[str, Any]:
    trusted = read_json(MOCK_DATA_DIR / "trusted_value_demo_data.json")
    city_profiles = read_json(MOCK_DATA_DIR / "analytics_city_profiles.json")
    analytics_weights = read_json(MOCK_DATA_DIR / "analytics_weights.json")
    rag_documents = read_json(MOCK_DATA_DIR / "rag_corpus" / "documents.json")
    rag_cards = read_json(MOCK_DATA_DIR / "rag_corpus" / "knowledge_cards.json")

    with connection:
        connection.executemany(
            "INSERT INTO mock_import_meta (key, value) VALUES (?, ?)",
            [
                ("generated_at", isoformat(datetime.now())),
                ("source_dir", str(MOCK_DATA_DIR)),
                ("cities_count", str(len(trusted["cities"]))),
                ("base_products_count", str(len(trusted["base_products"]))),
            ],
        )

        for family in trusted["base_products"]:
            connection.execute(
                """
                INSERT INTO mock_product_families (
                    family_id, family_name, category, region_name, season, tags_json,
                    core_json, origin_json, reference_note, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    family["family_id"],
                    family["family_name"],
                    family["category"],
                    family["region_name"],
                    family.get("season"),
                    json.dumps(family.get("tags", []), ensure_ascii=False),
                    json.dumps(family.get("core", {}), ensure_ascii=False),
                    json.dumps(family.get("origin", {}), ensure_ascii=False),
                    family.get("reference_note"),
                    json.dumps(family, ensure_ascii=False),
                ),
            )

            for variant in family["variants"]:
                connection.execute(
                    """
                    INSERT INTO mock_product_variants (
                        variant_id, family_id, variant_name, channel, price_band,
                        unit_price, launch_quantity, presentation_json, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        variant["variant_id"],
                        family["family_id"],
                        variant["variant_name"],
                        variant.get("channel"),
                        variant.get("price_band"),
                        variant.get("unit_price"),
                        variant.get("launch_quantity"),
                        json.dumps(variant.get("presentation", {}), ensure_ascii=False),
                        json.dumps(variant, ensure_ascii=False),
                    ),
                )

        for city, payload in city_profiles.items():
            connection.execute(
                "INSERT INTO mock_city_profiles (city, profile_json) VALUES (?, ?)",
                (city, json.dumps(payload, ensure_ascii=False)),
            )

        for section, payload in analytics_weights.items():
            connection.execute(
                "INSERT INTO mock_analytics_weights (section, payload_json) VALUES (?, ?)",
                (section, json.dumps(payload, ensure_ascii=False)),
            )

        for item in rag_documents:
            connection.execute(
                """
                INSERT INTO mock_rag_documents (
                    doc_id, title, source_group, theme_path, source_path,
                    file_type, text_length, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["doc_id"],
                    item.get("title"),
                    item.get("source_group"),
                    item.get("theme_path"),
                    item.get("source_path"),
                    item.get("file_type"),
                    item.get("text_length"),
                    json.dumps(item, ensure_ascii=False),
                ),
            )

        for item in rag_cards:
            connection.execute(
                """
                INSERT INTO mock_rag_knowledge_cards (
                    doc_id, title, theme_path, source_path, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    item["doc_id"],
                    item.get("title"),
                    item.get("theme_path"),
                    item.get("source_path"),
                    json.dumps(item, ensure_ascii=False),
                ),
            )

        for filename, target_table in [("chunks.jsonl", "mock_rag_chunks"), ("insights.jsonl", "mock_rag_insights")]:
            path = MOCK_DATA_DIR / "rag_corpus" / filename
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    item = json.loads(line)
                    if target_table == "mock_rag_chunks":
                        connection.execute(
                            """
                            INSERT INTO mock_rag_chunks (
                                chunk_id, doc_id, sequence, title, theme_path,
                                text_length, is_conclusion_like, payload_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                item["chunk_id"],
                                item.get("doc_id"),
                                item.get("sequence"),
                                item.get("title"),
                                item.get("theme_path"),
                                item.get("text_length"),
                                1 if item.get("is_conclusion_like") else 0,
                                json.dumps(item, ensure_ascii=False),
                            ),
                        )
                    else:
                        connection.execute(
                            """
                            INSERT INTO mock_rag_insights (
                                insight_id, doc_id, source_chunk_id, title,
                                insight_type, theme_path, payload_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                item["insight_id"],
                                item.get("doc_id"),
                                item.get("source_chunk_id"),
                                item.get("title"),
                                item.get("insight_type"),
                                item.get("theme_path"),
                                json.dumps(item, ensure_ascii=False),
                            ),
                        )

    return trusted


def region_center(index: int) -> tuple[float, float]:
    if index < len(REGION_CENTERS):
        return REGION_CENTERS[index]
    rng = stable_random("region-center", index)
    return (108 + rng.random() * 15, 25 + rng.random() * 10)


def insert_regions(connection: sqlite3.Connection, families: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    region_map: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()

    with connection:
        for family in families:
            region_name = family["region_name"]
            if region_name in seen:
                continue
            seen.add(region_name)
            idx = len(seen) - 1
            center_lng, center_lat = region_center(idx)
            connection.execute(
                """
                INSERT INTO regions (
                    code, name, product_type, province, city, boundary_geojson,
                    center_lng, center_lat, is_enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    f"mock-region-{idx + 1:03d}",
                    region_name,
                    family["category"],
                    f"Province-{idx + 1:02d}",
                    f"City-{idx + 1:02d}",
                    json.dumps(build_polygon(center_lng, center_lat), ensure_ascii=False),
                    round(center_lng, 6),
                    round(center_lat, 6),
                ),
            )
            region_id = connection.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
            region_map[region_name] = {
                "id": region_id,
                "center_lng": round(center_lng, 6),
                "center_lat": round(center_lat, 6),
            }

    return region_map


def product_count_for_variant(launch_quantity: int, unit_price: float) -> int:
    launch_factor = launch_quantity / 220
    price_factor = 1.0 if unit_price <= 100 else (0.85 if unit_price <= 180 else 0.72)
    return int(clamp(round(launch_factor * price_factor), 4, 14))


def created_at_for(variant_id: str, serial: int) -> datetime:
    rng = stable_random("created-at", variant_id, serial)
    days_ago = int((rng.random() ** 1.7) * 75)
    hours_ago = rng.randint(0, 23)
    minutes_ago = rng.randint(0, 59)
    return datetime.now().replace(microsecond=0) - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)


def producer_name_for(region_name: str, family_name: str, serial: int) -> str:
    suffix = PRODUCER_SUFFIXES[stable_seed(region_name, family_name, serial) % len(PRODUCER_SUFFIXES)]
    return f"{family_name}{suffix}"


def batch_no_for(variant_id: str, created_at: datetime, serial: int) -> str:
    return f"{variant_id}-{created_at:%Y%m}-{serial:03d}"


def token_for(variant_id: str, serial: int) -> str:
    return f"gt_mock_{variant_id.lower()}_{serial:03d}"


def product_code_for(variant_id: str, serial: int) -> str:
    return f"GTM{variant_id[-3:]}{serial:03d}"


def signature_for(*parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def category_city(city_name: str) -> tuple[float, float]:
    direct = CITY_COORDS.get(city_name)
    if direct is not None:
        return direct

    fallback_index = stable_seed('fallback-city', city_name) % len(CITY_COORD_LIST)
    return CITY_COORD_LIST[fallback_index]


def pick_city_coords(*parts: object) -> tuple[float, float]:
    return CITY_COORD_LIST[stable_seed('city-coords', *parts) % len(CITY_COORD_LIST)]


def scan_profile_for(category: str, unit_price: float, launch_quantity: int, key: str) -> tuple[int, float]:
    rng = stable_random("scan-profile", key)
    base_count = 1 + int(clamp(round(launch_quantity / 900), 0, 4))
    premium_bonus = 1 if unit_price >= 150 else 0
    category_bonus = 1 if category in {"姘翠骇", "椴滄灉", "钄彍"} else 0
    total_scans = int(clamp(base_count + premium_bonus + category_bonus + rng.randint(0, 2), 1, 6))
    anomaly_rate = 0.1 + (0.08 if category in {"姘翠骇", "椴滄灉"} else 0.03) + (0.05 if unit_price >= 180 else 0)
    return total_scans, clamp(anomaly_rate, 0.08, 0.26)


def scan_message(product_code: str, risk_level: str, speed: float | None, is_first_scan: bool) -> tuple[str, str]:
    if risk_level in {"medium", "high"}:
        return "scan_anomaly", f"{product_code} abnormal cross-region scan, estimated speed {speed:.2f} km/h"
    if is_first_scan:
        return "scan_normal", f"{product_code} first scan verified"
    return "scan_repeat", f"{product_code} repeat scan with no obvious anomaly"


def generate_scans(
    connection: sqlite3.Connection,
    cities: list[str],
    family: dict[str, Any],
    variant: dict[str, Any],
    product_id: int,
    product_code: str,
    origin_lng: float,
    origin_lat: float,
    created_at: datetime,
) -> None:
    serial = int(product_code[-3:])
    total_scans, anomaly_rate = scan_profile_for(family["category"], variant["unit_price"], variant["launch_quantity"], product_code)
    rng = stable_random("scan-sequence", product_code)
    previous_lng = None
    previous_lat = None
    previous_time = None

    for step in range(1, total_scans + 1):
        if step == 1:
            scan_time = created_at + timedelta(days=rng.randint(0, 4), hours=rng.randint(1, 20))
            scan_lng, scan_lat = jitter_point(origin_lng, origin_lat, f"scan-{product_code}-{step}", radius=0.06)
        else:
            is_anomaly = rng.random() < anomaly_rate
            if is_anomaly and previous_time is not None:
                city_lng, city_lat = pick_city_coords('anomaly', product_code, step)
                scan_lng, scan_lat = jitter_point(city_lng, city_lat, f"remote-{product_code}-{step}", radius=0.08)
                scan_time = previous_time + timedelta(minutes=rng.randint(25, 160))
            else:
                city_lng, city_lat = pick_city_coords('normal', product_code, step)
                blend = 0.25 if family["category"] in {"缁胯尪", "榛戣尪", "骞茶揣", "楗搧"} else 0.12
                base_lng = origin_lng * (1 - blend) + city_lng * blend
                base_lat = origin_lat * (1 - blend) + city_lat * blend
                scan_lng, scan_lat = jitter_point(base_lng, base_lat, f"blend-{product_code}-{step}", radius=0.05)
                scan_time = previous_time + timedelta(days=rng.randint(1, 10), hours=rng.randint(2, 18))

        is_first_scan = 1 if step == 1 else 0
        distance_from_last = None
        time_from_last = None
        estimated_speed = None
        risk_level = "none"
        risk_detected = 0

        if previous_time is not None and previous_lng is not None and previous_lat is not None:
            distance_from_last = round(haversine_distance_meters(previous_lng, previous_lat, scan_lng, scan_lat), 2)
            time_from_last = round(max((scan_time - previous_time).total_seconds(), 0), 2)
            if time_from_last > 0:
                estimated_speed = round((distance_from_last / time_from_last) * 3.6, 2)
                if estimated_speed > 800:
                    risk_level = "high"
                    risk_detected = 1
                elif estimated_speed > 300:
                    risk_level = "medium"
                    risk_detected = 1

        event_type, message = scan_message(product_code, risk_level, estimated_speed, is_first_scan == 1)

        connection.execute(
            """
            INSERT INTO scan_records (
                product_id, scan_time, scan_lng, scan_lat, scan_accuracy, device_info,
                is_first_scan, distance_from_last, time_from_last, estimated_speed,
                risk_level, risk_detected, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product_id,
                isoformat(scan_time),
                scan_lng,
                scan_lat,
                15.0 if risk_detected else 8.0,
                f"MockScanner/{variant['variant_id']}",
                is_first_scan,
                distance_from_last,
                time_from_last,
                estimated_speed,
                risk_level,
                risk_detected,
                isoformat(scan_time),
            ),
        )

        connection.execute(
            """
            INSERT INTO dashboard_events (
                event_type, event_time, product_id, product_code, location_lng, location_lat,
                related_lng, related_lat, message, severity, risk_level, estimated_speed, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_type,
                isoformat(scan_time),
                product_id,
                product_code,
                scan_lng,
                scan_lat,
                previous_lng,
                previous_lat,
                message,
                "error" if risk_detected else "info",
                risk_level,
                estimated_speed,
                isoformat(scan_time),
            ),
        )

        previous_lng = scan_lng
        previous_lat = scan_lat
        previous_time = scan_time


def generate_business_data(connection: sqlite3.Connection, trusted: dict[str, Any], region_map: dict[str, dict[str, Any]]) -> None:
    cities = trusted["cities"]

    with connection:
        for family in trusted["base_products"]:
            region = region_map[family["region_name"]]
            for variant in family["variants"]:
                product_total = product_count_for_variant(variant["launch_quantity"], variant["unit_price"])
                for serial in range(1, product_total + 1):
                    created_at = created_at_for(variant["variant_id"], serial)
                    token = token_for(variant["variant_id"], serial)
                    product_code = product_code_for(variant["variant_id"], serial)
                    product_name = f"{family['family_name']}路{variant['variant_name']}"
                    batch_no = batch_no_for(variant["variant_id"], created_at, serial)
                    producer_name = producer_name_for(family["region_name"], family["family_name"], serial)
                    origin_lng, origin_lat = jitter_point(region["center_lng"], region["center_lat"], f"{product_code}-origin")
                    device_hash = signature_for("device", variant["variant_id"], serial)[:32]
                    trace_url = f"http://111.229.115.101:8000/trace/{token}"

                    connection.execute(
                        """
                        INSERT INTO products (
                            product_code, product_name, batch_no, region_id, producer_name,
                            origin_lng, origin_lat, origin_accuracy, origin_provider, origin_fix_time,
                            device_id_hash, device_brand, device_model, device_os_version,
                            app_version_name, app_version_code, risk_is_mock, risk_is_emulator,
                            risk_is_debugger, risk_dev_options_enabled, token, signature,
                            trace_url, qr_code_url, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            product_code,
                            product_name,
                            batch_no,
                            region["id"],
                            producer_name,
                            origin_lng,
                            origin_lat,
                            6.0,
                            "gps",
                            isoformat(created_at),
                            device_hash,
                            "GeoTrust",
                            "MockDevice",
                            "Android 14",
                            "1.0.0",
                            1,
                            token,
                            signature_for(product_code, token, batch_no),
                            trace_url,
                            f"http://111.229.115.101:8000/static/qrcodes/{token}.png",
                            isoformat(created_at),
                            isoformat(created_at),
                        ),
                    )
                    product_id = connection.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

                    connection.execute(
                        """
                        INSERT INTO register_attempts (
                            product_name, batch_no, region_id, producer_name, request_lng,
                            request_lat, request_accuracy, request_provider, request_fix_time,
                            risk_is_mock, risk_is_emulator, risk_is_debugger, risk_dev_options_enabled,
                            device_id_hash, device_brand, device_model, device_os_version,
                            app_version_name, app_version_code, result, reason_code, reason_message,
                            created_product_id, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, ?, ?, ?, ?, ?, ?, 'accepted', 'accepted', ?, ?, ?)
                        """,
                        (
                            product_name,
                            batch_no,
                            region["id"],
                            producer_name,
                            origin_lng,
                            origin_lat,
                            6.0,
                            "gps",
                            isoformat(created_at),
                            device_hash,
                            "GeoTrust",
                            "MockDevice",
                            "Android 14",
                            "1.0.0",
                            1,
                            f"registered from region {family['region_name']}",
                            product_id,
                            isoformat(created_at),
                        ),
                    )

                    connection.execute(
                        """
                        INSERT INTO dashboard_events (
                            event_type, event_time, product_id, product_code, location_lng, location_lat,
                            related_lng, related_lat, message, severity, risk_level, estimated_speed, created_at
                        ) VALUES ('register_success', ?, ?, ?, ?, ?, NULL, NULL, ?, 'info', 'none', NULL, ?)
                        """,
                        (
                            isoformat(created_at),
                            product_id,
                            product_code,
                            origin_lng,
                            origin_lat,
                            f"{product_code} registered successfully",
                            isoformat(created_at),
                        ),
                    )

                    if serial == 1:
                        rejected_at = created_at - timedelta(hours=3)
                        rejected_lng = round(origin_lng + 0.42, 6)
                        rejected_lat = round(origin_lat + 0.28, 6)
                        connection.execute(
                            """
                            INSERT INTO register_attempts (
                                product_name, batch_no, region_id, producer_name, request_lng,
                                request_lat, request_accuracy, request_provider, request_fix_time,
                                risk_is_mock, risk_is_emulator, risk_is_debugger, risk_dev_options_enabled,
                                device_id_hash, device_brand, device_model, device_os_version,
                                app_version_name, app_version_code, result, reason_code, reason_message,
                                created_product_id, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, ?, ?, ?, ?, ?, ?, 'rejected_outside_region',
                                'rejected_outside_region', ?, NULL, ?)
                            """,
                            (
                                product_name,
                                f"{batch_no}-X",
                                region["id"],
                                producer_name,
                                rejected_lng,
                                rejected_lat,
                                18.0,
                                "network",
                                isoformat(rejected_at),
                                device_hash,
                                "GeoTrust",
                                "MockDevice",
                                "Android 14",
                                "1.0.0",
                                1,
                                f"rejected outside region {family['region_name']}",
                                isoformat(rejected_at),
                            ),
                        )

                        connection.execute(
                            """
                            INSERT INTO dashboard_events (
                                event_type, event_time, product_id, product_code, location_lng, location_lat,
                                related_lng, related_lat, message, severity, risk_level, estimated_speed, created_at
                            ) VALUES ('register_rejected', ?, NULL, NULL, ?, ?, NULL, NULL, ?, 'error', 'high', NULL, ?)
                            """,
                            (
                                isoformat(rejected_at),
                                rejected_lng,
                                rejected_lat,
                                f"{product_name} rejected outside region",
                                isoformat(rejected_at),
                            ),
                        )

                    generate_scans(
                        connection,
                        cities,
                        family,
                        variant,
                        product_id,
                        product_code,
                        origin_lng,
                        origin_lat,
                        created_at,
                    )


def create_database(output_path: Path) -> None:
    from import_product_media import DEFAULT_SOURCE_DIR, DEFAULT_STATIC_DIR, import_media

    ensure_parent(output_path)
    if output_path.exists():
        output_path.unlink()

    with sqlite3.connect(output_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON;")
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        create_extension_tables(connection)
        trusted = import_extension_tables(connection)
        region_map = insert_regions(connection, trusted["base_products"])
        generate_business_data(connection, trusted, region_map)
        connection.commit()

    if DEFAULT_SOURCE_DIR.exists():
        import_media(output_path, DEFAULT_SOURCE_DIR, DEFAULT_STATIC_DIR)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a complete project database from mock_data.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Output SQLite path.")
    args = parser.parse_args()
    create_database(Path(args.output))


if __name__ == "__main__":
    main()



