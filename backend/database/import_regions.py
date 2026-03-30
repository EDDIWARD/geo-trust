from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python import_regions.py <geojson-or-json-file> [database_path]")
        return 1

    source_path = Path(sys.argv[1]).resolve()
    database_path = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path(__file__).resolve().parent / "android_backend.db"

    if not source_path.exists():
        print(f"Input file not found: {source_path}")
        return 1

    payload = json.loads(source_path.read_text(encoding="utf-8"))
    regions = _normalize_regions(payload)
    if not regions:
        print("No region records found in input.")
        return 1

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        for region in regions:
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
                ON CONFLICT(code) DO UPDATE SET
                    name = excluded.name,
                    product_type = excluded.product_type,
                    province = excluded.province,
                    city = excluded.city,
                    boundary_geojson = excluded.boundary_geojson,
                    center_lng = excluded.center_lng,
                    center_lat = excluded.center_lat,
                    is_enabled = excluded.is_enabled,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    region["code"],
                    region["name"],
                    region["product_type"],
                    region.get("province"),
                    region.get("city"),
                    json.dumps(region["boundary_geojson"], ensure_ascii=False),
                    region.get("center_lng"),
                    region.get("center_lat"),
                    1 if region.get("is_enabled", True) else 0,
                ),
            )
        connection.commit()

    print(f"Imported {len(regions)} region(s) into {database_path}")
    return 0


def _normalize_regions(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [_normalize_region_item(item) for item in payload]

    if isinstance(payload, dict) and payload.get("type") == "FeatureCollection":
        return [_normalize_feature(feature) for feature in payload.get("features", [])]

    if isinstance(payload, dict):
        return [_normalize_region_item(payload)]

    raise ValueError("Unsupported JSON format.")


def _normalize_feature(feature: dict[str, Any]) -> dict[str, Any]:
    properties = feature.get("properties", {})
    geometry = feature.get("geometry")
    if geometry is None:
        raise ValueError("GeoJSON feature missing geometry.")

    code = properties.get("code") or properties.get("region_code")
    name = properties.get("name") or properties.get("region_name")
    product_type = properties.get("product_type") or properties.get("product")

    if not code or not name or not product_type:
        raise ValueError("GeoJSON feature properties must include code, name, and product_type.")

    return {
        "code": code,
        "name": name,
        "product_type": product_type,
        "province": properties.get("province"),
        "city": properties.get("city"),
        "center_lng": properties.get("center_lng"),
        "center_lat": properties.get("center_lat"),
        "is_enabled": properties.get("is_enabled", True),
        "boundary_geojson": geometry,
    }


def _normalize_region_item(item: dict[str, Any]) -> dict[str, Any]:
    required = ["code", "name", "product_type", "boundary_geojson"]
    for field in required:
        if field not in item:
            raise ValueError(f"Region item missing required field: {field}")
    return item


if __name__ == "__main__":
    raise SystemExit(main())
