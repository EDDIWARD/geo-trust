from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import qrcode


REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "backend" / "database" / "android_backend.db"
QRCODE_DIR = REPO_ROOT / "backend" / "server" / "static" / "qrcodes"
BASE_URL = "http://111.229.115.101:8000"
DEMO_TOKEN = "gt_mock_p001_001"


def main() -> None:
    base_url = sys.argv[1] if len(sys.argv) > 1 else BASE_URL
    base_url = base_url.rstrip("/")
    trace_url = f"{base_url}/trace/{DEMO_TOKEN}"
    qr_code_url = f"{base_url}/static/qrcodes/{DEMO_TOKEN}.png"

    QRCODE_DIR.mkdir(parents=True, exist_ok=True)
    qrcode.make(trace_url).save(QRCODE_DIR / f"{DEMO_TOKEN}.png")

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            UPDATE products
            SET trace_url = ?, qr_code_url = ?, updated_at = CURRENT_TIMESTAMP
            WHERE token = ?
            """,
            (trace_url, qr_code_url, DEMO_TOKEN),
        )
        connection.commit()

    print(f"trace_url={trace_url}")
    print(f"qr_code_url={qr_code_url}")


if __name__ == "__main__":
    main()
