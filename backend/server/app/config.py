from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str
    base_url: str
    database_path: Path
    schema_path: Path
    sample_regions_path: Path
    static_dir: Path
    qrcode_dir: Path
    trace_path_prefix: str
    register_enabled: bool
    location_required: bool
    reject_mock_location: bool
    reject_emulator: bool
    reject_debugger: bool
    signing_secret: str


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_settings() -> Settings:
    server_dir = Path(__file__).resolve().parents[1]
    backend_dir = server_dir.parent
    database_dir = backend_dir / "database"
    static_dir = server_dir / "static"
    qrcode_dir = static_dir / "qrcodes"

    return Settings(
        app_name=os.getenv("APP_NAME", "Geo-Trust Farmer"),
        base_url=os.getenv("BASE_URL", "http://127.0.0.1:8000"),
        database_path=Path(os.getenv("DATABASE_PATH", database_dir / "android_backend.db")),
        schema_path=Path(os.getenv("SCHEMA_PATH", database_dir / "android_backend_schema.sql")),
        sample_regions_path=Path(os.getenv("SAMPLE_REGIONS_PATH", database_dir / "sample_regions.json")),
        static_dir=static_dir,
        qrcode_dir=qrcode_dir,
        trace_path_prefix=os.getenv("TRACE_PATH_PREFIX", "/trace"),
        register_enabled=_as_bool(os.getenv("REGISTER_ENABLED"), True),
        location_required=_as_bool(os.getenv("LOCATION_REQUIRED"), True),
        reject_mock_location=_as_bool(os.getenv("REJECT_MOCK_LOCATION"), True),
        reject_emulator=_as_bool(os.getenv("REJECT_EMULATOR"), True),
        reject_debugger=_as_bool(os.getenv("REJECT_DEBUGGER"), True),
        signing_secret=os.getenv("SIGNING_SECRET", "replace-me-before-production"),
    )
