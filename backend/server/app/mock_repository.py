from __future__ import annotations

import json
import sqlite3
from functools import lru_cache

from .config import get_settings


def _get_connection() -> sqlite3.Connection | None:
    database_path = get_settings().database_path
    if not database_path.exists():
        return None

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


@lru_cache(maxsize=1)
def load_mock_dataset() -> dict | None:
    connection = _get_connection()
    if connection is None:
        return None

    try:
        if not _table_exists(connection, "mock_product_families"):
            return None

        family_rows = connection.execute(
            """
            SELECT family_id, payload_json
            FROM mock_product_families
            ORDER BY family_id
            """
        ).fetchall()
        if not family_rows:
            return None

        cities: list[str] = []
        if _table_exists(connection, "mock_city_profiles"):
            cities = [
                row["city"]
                for row in connection.execute(
                    """
                    SELECT city
                    FROM mock_city_profiles
                    ORDER BY city
                    """
                ).fetchall()
            ]

        return {
            "cities": cities,
            "base_products": [json.loads(row["payload_json"]) for row in family_rows],
        }
    finally:
        connection.close()


@lru_cache(maxsize=1)
def load_city_profiles() -> dict[str, dict] | None:
    connection = _get_connection()
    if connection is None:
        return None

    try:
        if not _table_exists(connection, "mock_city_profiles"):
            return None

        rows = connection.execute(
            """
            SELECT city, profile_json
            FROM mock_city_profiles
            ORDER BY city
            """
        ).fetchall()
        if not rows:
            return None

        return {
            row["city"]: json.loads(row["profile_json"])
            for row in rows
        }
    finally:
        connection.close()


@lru_cache(maxsize=1)
def load_analytics_weights() -> dict | None:
    connection = _get_connection()
    if connection is None:
        return None

    try:
        if not _table_exists(connection, "mock_analytics_weights"):
            return None

        rows = connection.execute(
            """
            SELECT section, payload_json
            FROM mock_analytics_weights
            ORDER BY section
            """
        ).fetchall()
        if not rows:
            return None

        return {
            row["section"]: json.loads(row["payload_json"])
            for row in rows
        }
    finally:
        connection.close()


def _load_payload_rows(table_name: str, order_field: str) -> list[dict] | None:
    connection = _get_connection()
    if connection is None:
        return None

    try:
        if not _table_exists(connection, table_name):
            return None

        rows = connection.execute(
            f"""
            SELECT payload_json
            FROM {table_name}
            ORDER BY {order_field}
            """
        ).fetchall()
        if not rows:
            return None

        return [json.loads(row["payload_json"]) for row in rows]
    finally:
        connection.close()


@lru_cache(maxsize=1)
def load_rag_documents() -> list[dict] | None:
    return _load_payload_rows("mock_rag_documents", "doc_id")


@lru_cache(maxsize=1)
def load_rag_cards() -> list[dict] | None:
    return _load_payload_rows("mock_rag_knowledge_cards", "doc_id")


@lru_cache(maxsize=1)
def load_rag_chunks() -> list[dict] | None:
    return _load_payload_rows("mock_rag_chunks", "chunk_id")


@lru_cache(maxsize=1)
def load_rag_insights() -> list[dict] | None:
    return _load_payload_rows("mock_rag_insights", "insight_id")
