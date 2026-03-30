from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import qrcode
from shapely.geometry import Point, shape

from .config import Settings
from .schemas import (
    RegisterProductRequest,
    RegisterProductResponse,
    ValidateLocationRequest,
    ValidateLocationResponse,
)


@dataclass
class RegisterDecision:
    accepted: bool
    result: str
    message: str
    product_id: int | None = None
    product_code: str | None = None
    token: str | None = None
    trace_url: str | None = None
    qr_code_url: str | None = None
    region_name: str | None = None


def list_enabled_regions(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT id, code, name, product_type, province, city, center_lng, center_lat
        FROM regions
        WHERE is_enabled = 1
        ORDER BY id ASC
        """
    ).fetchall()


def validate_location(
    connection: sqlite3.Connection,
    payload: ValidateLocationRequest,
    settings: Settings,
) -> ValidateLocationResponse:
    if not settings.register_enabled:
        return ValidateLocationResponse(
            valid=False,
            validation_result="rejected_service_disabled",
            message="当前系统未开放登记，请稍后重试。",
            in_region=False,
            blocked_by_risk=False,
        )

    risk_decision = _reject_for_risk_if_needed(payload, settings)
    if risk_decision is not None:
        return ValidateLocationResponse(
            valid=False,
            validation_result=risk_decision.result,
            message=risk_decision.message,
            in_region=False,
            blocked_by_risk=True,
        )

    region = _get_enabled_region(connection, payload.region_id)
    if region is None:
        return ValidateLocationResponse(
            valid=False,
            validation_result="rejected_invalid_payload",
            message="所选产区不存在或未启用。",
            in_region=False,
            blocked_by_risk=False,
        )

    in_region = _point_in_region(
        region["boundary_geojson"],
        payload.location.lng,
        payload.location.lat,
    )
    if not in_region:
        return ValidateLocationResponse(
            valid=False,
            validation_result="rejected_outside_region",
            message="当前定位不在合法产区范围内。",
            region_name=region["name"],
            in_region=False,
            blocked_by_risk=False,
        )

    return ValidateLocationResponse(
        valid=True,
        validation_result="accepted",
        message=f"当前位置位于{region['name']}，可发起登记。",
        region_name=region["name"],
        in_region=True,
        blocked_by_risk=False,
    )


def register_product(
    connection: sqlite3.Connection,
    payload: RegisterProductRequest,
    settings: Settings,
) -> RegisterProductResponse:
    if not settings.register_enabled:
        decision = RegisterDecision(
            accepted=False,
            result="rejected_service_disabled",
            message="当前系统未开放登记，请稍后重试。",
        )
        _insert_attempt(connection, payload, decision)
        return _to_response(decision)

    risk_decision = _reject_for_risk_if_needed(payload, settings)
    if risk_decision is not None:
        _insert_attempt(connection, payload, risk_decision)
        return _to_response(risk_decision)

    region = _get_enabled_region(connection, payload.region_id)

    if region is None:
        decision = RegisterDecision(
            accepted=False,
            result="rejected_invalid_payload",
            message="所选产区不存在或未启用。",
        )
        _insert_attempt(connection, payload, decision)
        return _to_response(decision)

    if not _point_in_region(
        region["boundary_geojson"],
        payload.location.lng,
        payload.location.lat,
    ):
        decision = RegisterDecision(
            accepted=False,
            result="rejected_outside_region",
            message="当前定位不在合法产区范围内，拒绝生成溯源码。",
        )
        _insert_attempt(connection, payload, decision)
        return _to_response(decision)

    product_code = _build_product_code(connection)
    token = f"gt_{secrets.token_hex(12)}"
    trace_url = f"{settings.base_url.rstrip('/')}{settings.trace_path_prefix}/{token}"
    signature = _build_signature(payload, token, settings.signing_secret)
    qr_code_url = _generate_qrcode(token, trace_url, settings.qrcode_dir, settings.base_url)

    with connection:
        cursor = connection.execute(
            """
            INSERT INTO products (
                product_code,
                product_name,
                batch_no,
                region_id,
                producer_name,
                origin_lng,
                origin_lat,
                origin_accuracy,
                origin_provider,
                origin_fix_time,
                device_id_hash,
                device_brand,
                device_model,
                device_os_version,
                app_version_name,
                app_version_code,
                risk_is_mock,
                risk_is_emulator,
                risk_is_debugger,
                risk_dev_options_enabled,
                token,
                signature,
                trace_url,
                qr_code_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product_code,
                payload.product_name,
                payload.batch_no,
                payload.region_id,
                payload.producer_name,
                payload.location.lng,
                payload.location.lat,
                payload.location.accuracy,
                payload.location.provider,
                payload.location.fix_time,
                payload.device.android_id_hash,
                payload.device.brand,
                payload.device.model,
                payload.device.os_version,
                payload.app.version_name if payload.app else None,
                payload.app.version_code if payload.app else None,
                int(payload.risk_flags.is_mock),
                int(payload.risk_flags.is_emulator),
                int(payload.risk_flags.is_debugger),
                int(payload.risk_flags.dev_options_enabled),
                token,
                signature,
                trace_url,
                qr_code_url,
            ),
        )
        product_id = cursor.lastrowid
        decision = RegisterDecision(
            accepted=True,
            result="accepted",
            message=f"定位坐标位于{region['name']}，登记成功。",
            product_id=product_id,
            product_code=product_code,
            token=token,
            trace_url=trace_url,
            qr_code_url=qr_code_url,
            region_name=region["name"],
        )
        _insert_attempt(connection, payload, decision)

    return _to_response(decision)


def _reject_for_risk_if_needed(
    payload: RegisterProductRequest | ValidateLocationRequest,
    settings: Settings,
) -> RegisterDecision | None:
    if settings.reject_mock_location and payload.risk_flags.is_mock:
        return RegisterDecision(
            accepted=False,
            result="rejected_mock_location",
            message="检测到 mock 定位风险，拒绝生成溯源码。",
        )

    if (
        (settings.reject_emulator and payload.risk_flags.is_emulator)
        or (settings.reject_debugger and payload.risk_flags.is_debugger)
    ):
        return RegisterDecision(
            accepted=False,
            result="rejected_device_risk",
            message="检测到设备环境异常，拒绝生成溯源码。",
        )

    return None


def _get_enabled_region(connection: sqlite3.Connection, region_id: int) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT id, name, boundary_geojson
        FROM regions
        WHERE id = ? AND is_enabled = 1
        """,
        (region_id,),
    ).fetchone()


def _point_in_region(boundary_geojson: str, lng: float, lat: float) -> bool:
    geometry = shape(json.loads(boundary_geojson))
    return bool(geometry.covers(Point(lng, lat)))


def _build_product_code(connection: sqlite3.Connection) -> str:
    date_prefix = datetime.now().strftime("%Y%m%d")
    next_sequence = connection.execute(
        """
        SELECT COUNT(*) + 1 AS next_sequence
        FROM products
        WHERE strftime('%Y%m%d', created_at, 'localtime') = ?
        """,
        (date_prefix,),
    ).fetchone()["next_sequence"]
    return f"GT{date_prefix}{int(next_sequence):04d}"


def _build_signature(
    payload: RegisterProductRequest,
    token: str,
    signing_secret: str,
) -> str:
    sign_source = "|".join(
        [
            payload.product_name,
            payload.batch_no,
            str(payload.region_id),
            payload.producer_name,
            f"{payload.location.lng:.6f}",
            f"{payload.location.lat:.6f}",
            payload.location.fix_time,
            token,
        ]
    )
    return hmac.new(
        signing_secret.encode("utf-8"),
        sign_source.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _generate_qrcode(token: str, trace_url: str, qrcode_dir: Path, base_url: str) -> str:
    file_path = qrcode_dir / f"{token}.png"
    qr_image = qrcode.make(trace_url)
    qr_image.save(file_path)
    return f"{base_url.rstrip('/')}/static/qrcodes/{token}.png"


def _insert_attempt(
    connection: sqlite3.Connection,
    payload: RegisterProductRequest,
    decision: RegisterDecision,
) -> None:
    with connection:
        connection.execute(
            """
            INSERT INTO register_attempts (
                product_name,
                batch_no,
                region_id,
                producer_name,
                request_lng,
                request_lat,
                request_accuracy,
                request_provider,
                request_fix_time,
                risk_is_mock,
                risk_is_emulator,
                risk_is_debugger,
                risk_dev_options_enabled,
                device_id_hash,
                device_brand,
                device_model,
                device_os_version,
                app_version_name,
                app_version_code,
                result,
                reason_code,
                reason_message,
                created_product_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.product_name,
                payload.batch_no,
                payload.region_id,
                payload.producer_name,
                payload.location.lng,
                payload.location.lat,
                payload.location.accuracy,
                payload.location.provider,
                payload.location.fix_time,
                int(payload.risk_flags.is_mock),
                int(payload.risk_flags.is_emulator),
                int(payload.risk_flags.is_debugger),
                int(payload.risk_flags.dev_options_enabled),
                payload.device.android_id_hash,
                payload.device.brand,
                payload.device.model,
                payload.device.os_version,
                payload.app.version_name if payload.app else None,
                payload.app.version_code if payload.app else None,
                decision.result,
                decision.result,
                decision.message,
                decision.product_id,
            ),
        )


def _to_response(decision: RegisterDecision) -> RegisterProductResponse:
    return RegisterProductResponse(
        accepted=decision.accepted,
        register_result=decision.result,
        message=decision.message,
        product_id=decision.product_id,
        product_code=decision.product_code,
        token=decision.token,
        trace_url=decision.trace_url,
        qr_code_url=decision.qr_code_url,
        region_name=decision.region_name,
    )
