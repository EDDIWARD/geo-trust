from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import quote


REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "backend" / "database" / "android_backend.db"
STATIC_ROOT = REPO_ROOT / "backend" / "server" / "static"
PRODUCT_MEDIA_ROOT = STATIC_ROOT / "product-media"

DEMO_BINDINGS = {
    "恩施玉露路自饮简装": [
        ("产品图", PRODUCT_MEDIA_ROOT / "恩施玉露" / "产品图片.jpeg"),
        ("证书图", PRODUCT_MEDIA_ROOT / "恩施玉露" / "卫生证明.jpg"),
    ],
    "潜江小龙虾路家庭分享装": [
        ("产品图", PRODUCT_MEDIA_ROOT / "潜江小龙虾" / "产品展示.webp"),
        ("证书图", PRODUCT_MEDIA_ROOT / "潜江小龙虾" / "卫生证明.jpg"),
    ],
}


def as_static_url(path: Path) -> str:
    relative = path.relative_to(STATIC_ROOT)
    return "/static/" + "/".join(quote(part) for part in relative.parts)


def ensure_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS product_upload_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            image_url TEXT NOT NULL,
            original_name TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_product_upload_images_product
            ON product_upload_images(product_id, sort_order, id)
        """
    )


def seed_demo_uploads() -> None:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    with connection:
        ensure_table(connection)

        for product_name, bindings in DEMO_BINDINGS.items():
            product = connection.execute(
                """
                SELECT id, product_code, token
                FROM products
                WHERE product_name = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (product_name,),
            ).fetchone()
            if product is None:
                continue

            connection.execute(
                "DELETE FROM product_upload_images WHERE product_id = ?",
                (product["id"],),
            )

            for sort_order, (label, file_path) in enumerate(bindings):
                if not file_path.exists():
                    continue
                connection.execute(
                    """
                    INSERT INTO product_upload_images (
                        product_id,
                        image_url,
                        original_name,
                        sort_order
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        product["id"],
                        as_static_url(file_path),
                        f"{label}-{file_path.name}",
                        sort_order,
                    ),
                )

            print(
                f"seeded product_id={product['id']} product_code={product['product_code']} token={product['token']}"
            )


if __name__ == "__main__":
    seed_demo_uploads()
