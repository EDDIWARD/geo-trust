from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .config import Settings


def get_connection(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def initialize_database(settings: Settings) -> None:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    settings.static_dir.mkdir(parents=True, exist_ok=True)
    settings.qrcode_dir.mkdir(parents=True, exist_ok=True)

    schema_sql = settings.schema_path.read_text(encoding="utf-8")
    with get_connection(settings.database_path) as connection:
        connection.executescript(schema_sql)
        _seed_regions_if_needed(connection, settings.sample_regions_path)


def _seed_regions_if_needed(connection: sqlite3.Connection, sample_regions_path: Path) -> None:
    region_count = connection.execute("SELECT COUNT(*) AS count FROM regions").fetchone()["count"]
    if region_count > 0 or not sample_regions_path.exists():
        return

    region_items: list[dict[str, Any]] = json.loads(sample_regions_path.read_text(encoding="utf-8"))
    for item in region_items:
        connection.execute(
            """
            INSERT INTO regions (
                code,
                name,
                product_type,
                province,
                city,
                boundary_geojson,
                center_lng,
                center_lat,
                is_enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["code"],
                item["name"],
                item["product_type"],
                item.get("province"),
                item.get("city"),
                json.dumps(item["boundary_geojson"], ensure_ascii=False),
                item.get("center_lng"),
                item.get("center_lat"),
                1 if item.get("is_enabled", True) else 0,
            ),
        )
    connection.commit()
