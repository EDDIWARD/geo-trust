from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path
from urllib.parse import quote

import qrcode
from shapely.geometry import Point, shape

from .config import Settings
from .schemas import (
    DashboardAnomalyLineResponse,
    DashboardEventResponse,
    DashboardEventsListResponse,
    TraceGalleryImageResponse,
    DashboardMapDataResponse,
    DashboardMapPointResponse,
    DashboardRegionAnalysisResponse,
    DashboardRegionListResponse,
    DashboardSummaryResponse,
    DashboardTrendsResponse,
    RegisterProductRequest,
    RegisterProductResponse,
    ScanRecordRequest,
    ScanRecordResponse,
    TraceCertImageResponse,
    TraceLogisticsLogResponse,
    TraceProcessStepResponse,
    TraceProductResponse,
    TraceVideoInfoResponse,
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


DEMO_TRACE_TOKEN = "demo-token"

MEDIA_KEY_ALIASES = {
    "湛江小龙虾": "潜江小龙虾",
}

REGION_GEO_COORDS = {
    "恩施高山茶区": (30.272, 109.488),
    "赤壁砖茶产区": (29.716, 113.900),
    "神农架林区": (31.500, 110.500),
    "秭归脐橙核心产区": (30.823, 110.978),
    "宜昌高山柚产带": (30.691, 111.286),
    "罗田山地板栗产区": (30.783, 115.399),
    "武汉湖区莲藕基地": (30.593, 114.305),
    "潜江虾稻产区": (30.402, 112.899),
    "武汉近郊菜薹产区": (30.500, 114.400),
    "梁子湖生态水域": (30.253, 114.609),
    "随州香菇产区": (31.717, 113.382),
    "孝感米酒产区": (30.750, 113.900),
    "绍兴黄酒产区": (30.100, 120.500),
    "西湖龙井核心产区": (30.242, 120.130),
    "阳澄湖核心湖区": (31.419, 120.755),
}


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
        _insert_register_event(connection, payload, decision)
        return _to_response(decision)

    risk_decision = _reject_for_risk_if_needed(payload, settings)
    if risk_decision is not None:
        _insert_attempt(connection, payload, risk_decision)
        _insert_register_event(connection, payload, risk_decision)
        return _to_response(risk_decision)

    region = _get_enabled_region(connection, payload.region_id)
    if region is None:
        decision = RegisterDecision(
            accepted=False,
            result="rejected_invalid_payload",
            message="所选产区不存在或未启用。",
        )
        _insert_attempt(connection, payload, decision)
        _insert_register_event(connection, payload, decision)
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
        _insert_register_event(connection, payload, decision)
        return _to_response(decision)

    existing_product = _find_existing_product_by_product_and_batch(
        connection,
        payload.product_name.strip(),
        payload.batch_no.strip(),
    )
    if existing_product is not None:
        decision = RegisterDecision(
            accepted=False,
            result="rejected_invalid_payload",
            message="该商品名称与批次号组合已登记，请检查后再试。",
        )
        _insert_attempt(connection, payload, decision)
        _insert_register_event(connection, payload, decision)
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
    _insert_register_event(connection, payload, decision)
    return _to_response(decision)


def get_trace_product(connection: sqlite3.Connection, token: str) -> TraceProductResponse | None:
    if token == DEMO_TRACE_TOKEN:
        return _build_demo_trace_product()

    product = _get_product_with_region_by_token(connection, token)
    if product is None:
        return None

    scan_stats = _get_scan_stats(connection, product["id"])
    status, risk_level = _derive_trace_state(
        scan_stats["scan_count"],
        scan_stats["latest_risk_level"],
    )
    map_lng, map_lat = _resolve_region_map_coords(product)
    media_payload = _load_trace_media(connection, product["id"], product["product_name"])
    logistics_logs = _build_trace_logistics_logs(connection, product)

    return TraceProductResponse(
        product_id=product["id"],
        product_code=product["product_code"],
        product_name=product["product_name"],
        product_image=media_payload["product_image"],
        batch_no=product["batch_no"],
        region_name=product["region_name"],
        producer_name=product["producer_name"],
        origin_lng=product["origin_lng"],
        origin_lat=product["origin_lat"],
        map_lng=map_lng,
        map_lat=map_lat,
        region_boundary_geojson=_parse_boundary_geojson(product["boundary_geojson"]),
        origin_fix_time=_normalize_datetime_string(product["origin_fix_time"]),
        scan_count=scan_stats["scan_count"],
        first_scan_time=scan_stats["first_scan_time"],
        last_scan_time=scan_stats["last_scan_time"],
        status=status,
        risk_level=risk_level,
        cert_images=media_payload["cert_images"],
        process_steps=media_payload["process_steps"],
        gallery_images=media_payload["gallery_images"],
        video_info=media_payload["video_info"],
        logistics_logs=logistics_logs,
    )


def record_scan(
    connection: sqlite3.Connection,
    token: str,
    payload: ScanRecordRequest,
) -> ScanRecordResponse | None:
    if token == DEMO_TRACE_TOKEN:
        return ScanRecordResponse(
            scan_id=0,
            status="opened",
            message="Demo token scan recorded",
            risk_detected=False,
            risk_level="none",
            estimated_speed=None,
        )

    product = _get_product_with_region_by_token(connection, token)
    if product is None:
        return None

    previous_scan = _get_latest_scan(connection, product["id"])
    scan_time = _normalize_datetime_string(payload.scan_time)
    current_dt = _parse_datetime(scan_time)

    distance_from_last = None
    time_from_last = None
    estimated_speed = None
    risk_level = "none"
    risk_detected = False

    if (
        previous_scan is not None
        and payload.scan_lng is not None
        and payload.scan_lat is not None
        and previous_scan["scan_lng"] is not None
        and previous_scan["scan_lat"] is not None
    ):
        previous_dt = _parse_datetime(previous_scan["scan_time"])
        time_from_last = max((current_dt - previous_dt).total_seconds(), 0)
        distance_from_last = _haversine_distance_meters(
            previous_scan["scan_lng"],
            previous_scan["scan_lat"],
            payload.scan_lng,
            payload.scan_lat,
        )
        if time_from_last > 0:
            estimated_speed = round((distance_from_last / time_from_last) * 3.6, 2)
            if estimated_speed > 800:
                risk_level = "high"
                risk_detected = True
            elif estimated_speed > 300:
                risk_level = "medium"
                risk_detected = True

    is_first_scan = previous_scan is None
    if risk_detected:
        status = "risky"
        message = (
            f"检测到异常异地扫码，推定移动速度 {estimated_speed:.2f} km/h，"
            "请谨慎辨别商品真伪。"
        )
    elif is_first_scan:
        status = "normal"
        message = "首次扫码验证通过，当前未发现异常风险。"
    else:
        status = "opened"
        message = "该商品已存在扫码记录，本次未发现明显异常。"

    with connection:
        cursor = connection.execute(
            """
            INSERT INTO scan_records (
                product_id,
                scan_time,
                scan_lng,
                scan_lat,
                scan_accuracy,
                device_info,
                is_first_scan,
                distance_from_last,
                time_from_last,
                estimated_speed,
                risk_level,
                risk_detected
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product["id"],
                scan_time,
                payload.scan_lng,
                payload.scan_lat,
                payload.scan_accuracy,
                payload.device_info,
                1 if is_first_scan else 0,
                distance_from_last,
                time_from_last,
                estimated_speed,
                risk_level,
                1 if risk_detected else 0,
            ),
        )
        scan_id = cursor.lastrowid

    event_type = "scan_anomaly" if risk_detected else ("scan_normal" if is_first_scan else "scan_repeat")
    _insert_scan_event(
        connection=connection,
        product=product,
        event_type=event_type,
        event_time=scan_time,
        scan_lng=payload.scan_lng,
        scan_lat=payload.scan_lat,
        message=message,
        risk_level=risk_level,
        estimated_speed=estimated_speed,
        previous_scan=previous_scan,
    )

    return ScanRecordResponse(
        scan_id=scan_id,
        status=status,
        message=message,
        risk_detected=risk_detected,
        risk_level=risk_level,
        estimated_speed=estimated_speed,
    )


def get_dashboard_summary(connection: sqlite3.Connection) -> DashboardSummaryResponse:
    today_registered = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM products
        WHERE DATE(created_at, 'localtime') = DATE('now', 'localtime')
        """
    ).fetchone()["count"]
    today_scans = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM scan_records
        WHERE DATE(scan_time, 'localtime') = DATE('now', 'localtime')
        """
    ).fetchone()["count"]
    today_rejected = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM register_attempts
        WHERE result != 'accepted'
          AND DATE(created_at, 'localtime') = DATE('now', 'localtime')
        """
    ).fetchone()["count"]
    today_anomalies = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM scan_records
        WHERE risk_detected = 1
          AND DATE(scan_time, 'localtime') = DATE('now', 'localtime')
        """
    ).fetchone()["count"]
    total_products = connection.execute("SELECT COUNT(*) AS count FROM products").fetchone()["count"]
    total_scans = connection.execute("SELECT COUNT(*) AS count FROM scan_records").fetchone()["count"]

    return DashboardSummaryResponse(
        today_registered=today_registered,
        today_scans=today_scans,
        today_rejected=today_rejected,
        today_anomalies=today_anomalies,
        total_products=total_products,
        total_scans=total_scans,
    )


def list_dashboard_events(
    connection: sqlite3.Connection,
    limit: int = 50,
    event_type: str | None = None,
) -> DashboardEventsListResponse:
    params: list[object] = []
    query = """
        SELECT
            de.id,
            de.event_type,
            de.event_time,
            de.product_code,
            de.message,
            de.risk_level,
            de.estimated_speed,
            r.name AS region_name,
            r.province AS province
        FROM dashboard_events de
        LEFT JOIN products p ON p.id = de.product_id
        LEFT JOIN regions r ON r.id = p.region_id
    """
    if event_type:
        query += " WHERE de.event_type = ?"
        params.append(event_type)
    query += " ORDER BY de.event_time DESC, de.id DESC LIMIT ?"
    params.append(limit)

    rows = connection.execute(query, params).fetchall()
    if not rows:
        return DashboardEventsListResponse(events=_build_fallback_events(connection, limit))

    return DashboardEventsListResponse(
        events=[
            DashboardEventResponse(
                event_id=f"EVT-{row['id']}",
                event_type=row["event_type"],
                event_time=_normalize_datetime_string(row["event_time"]),
                product_code=row["product_code"],
                location=row["region_name"],
                region_name=row["region_name"],
                province=row["province"],
                message=row["message"],
                risk_level=row["risk_level"],
                speed=row["estimated_speed"],
            )
            for row in rows
        ]
    )


def get_dashboard_map_data(connection: sqlite3.Connection) -> DashboardMapDataResponse:
    register_points = connection.execute(
        """
        SELECT
            p.origin_lng AS lng,
            p.origin_lat AS lat,
            p.product_code,
            r.name AS region_name,
            r.province AS province
        FROM products p
        JOIN regions r ON r.id = p.region_id
        ORDER BY p.created_at DESC, p.id DESC
        LIMIT 200
        """
    ).fetchall()
    scan_points = connection.execute(
        """
        SELECT
            sr.scan_lng AS lng,
            sr.scan_lat AS lat,
            p.product_code,
            r.name AS region_name,
            r.province AS province,
            sr.scan_time
        FROM scan_records sr
        JOIN products p ON p.id = sr.product_id
        JOIN regions r ON r.id = p.region_id
        WHERE sr.scan_lng IS NOT NULL AND sr.scan_lat IS NOT NULL
        ORDER BY sr.scan_time DESC, sr.id DESC
        LIMIT 200
        """
    ).fetchall()
    anomaly_lines = connection.execute(
        """
        SELECT
            de.product_code,
            de.related_lng AS from_lng,
            de.related_lat AS from_lat,
            de.location_lng AS to_lng,
            de.location_lat AS to_lat,
            de.message,
            de.risk_level,
            de.estimated_speed,
            r.name AS region_name,
            r.province AS province
        FROM dashboard_events de
        LEFT JOIN products p ON p.id = de.product_id
        LEFT JOIN regions r ON r.id = p.region_id
        WHERE de.event_type = 'scan_anomaly'
          AND de.related_lng IS NOT NULL
          AND de.related_lat IS NOT NULL
          AND de.location_lng IS NOT NULL
          AND de.location_lat IS NOT NULL
        ORDER BY de.event_time DESC, de.id DESC
        LIMIT 100
        """
    ).fetchall()

    return DashboardMapDataResponse(
        register_points=[
            DashboardMapPointResponse(
                lng=row["lng"],
                lat=row["lat"],
                product_code=row["product_code"],
                region_name=row["region_name"],
                province=row["province"],
            )
            for row in register_points
        ],
        scan_points=[
            DashboardMapPointResponse(
                lng=row["lng"],
                lat=row["lat"],
                product_code=row["product_code"],
                region_name=row["region_name"],
                province=row["province"],
                scan_time=_normalize_datetime_string(row["scan_time"]),
            )
            for row in scan_points
        ],
        anomaly_lines=[
            DashboardAnomalyLineResponse(
                from_lng=row["from_lng"],
                from_lat=row["from_lat"],
                to_lng=row["to_lng"],
                to_lat=row["to_lat"],
                product_code=row["product_code"],
                reason=row["message"],
                region_name=row["region_name"],
                province=row["province"],
                risk_level=row["risk_level"],
                speed=row["estimated_speed"],
            )
            for row in anomaly_lines
        ],
        regions=list_region_analysis(connection).regions,
    )


def get_dashboard_trends(connection: sqlite3.Connection, days: int = 7) -> DashboardTrendsResponse:
    safe_days = min(max(days, 1), 30)
    today = datetime.now().date()
    date_items = [today - timedelta(days=offset) for offset in reversed(range(safe_days))]
    label_items = [item.strftime("%m-%d") for item in date_items]

    register_rows = _query_counts_by_date(connection, "products", "created_at", safe_days)
    scan_rows = _query_counts_by_date(connection, "scan_records", "scan_time", safe_days)
    alert_rows = _query_counts_by_date(
        connection,
        "scan_records",
        "scan_time",
        safe_days,
        extra_where="risk_detected = 1",
    )

    return DashboardTrendsResponse(
        dates=label_items,
        registrations=[register_rows.get(item.isoformat(), 0) for item in date_items],
        scans=[scan_rows.get(item.isoformat(), 0) for item in date_items],
        alerts=[alert_rows.get(item.isoformat(), 0) for item in date_items],
    )


def list_region_analysis(connection: sqlite3.Connection) -> DashboardRegionListResponse:
    rows = connection.execute(
        """
        SELECT
            r.name,
            r.product_type,
            r.province,
            COALESCE(region_products.product_count, 0) AS product_count,
            COALESCE(region_scans.total_scans, 0) AS total_scans,
            COALESCE(region_scans.anomalies, 0) AS anomalies
        FROM regions r
        LEFT JOIN (
            SELECT region_id, COUNT(*) AS product_count
            FROM products
            GROUP BY region_id
        ) AS region_products ON region_products.region_id = r.id
        LEFT JOIN (
            SELECT p.region_id,
                   COUNT(sr.id) AS total_scans,
                   SUM(CASE WHEN sr.risk_detected = 1 THEN 1 ELSE 0 END) AS anomalies
            FROM products p
            LEFT JOIN scan_records sr ON sr.product_id = p.id
            GROUP BY p.region_id
        ) AS region_scans ON region_scans.region_id = r.id
        WHERE r.is_enabled = 1
        ORDER BY r.id ASC
        """
    ).fetchall()

    return DashboardRegionListResponse(
        regions=[
            DashboardRegionAnalysisResponse(
                name=row["name"],
                type=row["product_type"],
                province=row["province"],
                todayCount=row["product_count"],
                anomalies=row["anomalies"],
                totalScans=row["total_scans"],
            )
            for row in rows
        ]
    )


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

    if settings.reject_root and payload.risk_flags.is_rooted:
        return RegisterDecision(
            accepted=False,
            result="rejected_device_risk",
            message="检测到 ROOT 环境，拒绝生成溯源码。",
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


def _build_demo_trace_product() -> TraceProductResponse:
    return TraceProductResponse(
        product_id=10001,
        product_code="GTM001001",
        product_name="恩施玉露·轻礼盒",
        product_image="https://example.com/static/products/gtm001001/main.jpg",
        batch_no="P002-202604-001",
        region_name="恩施高山茶区",
        producer_name="恩施玉露 Origin Foods",
        origin_lng=109.4882,
        origin_lat=30.2722,
        map_lng=109.4882,
        map_lat=30.2722,
        origin_fix_time="2026-04-10T08:30:00",
        scan_count=3,
        first_scan_time="2026-04-11T09:12:00",
        last_scan_time="2026-04-13T10:46:00",
        status="opened",
        risk_level="none",
        cert_images=[
            TraceCertImageResponse(
                title="地理标志认证",
                image_url="https://example.com/static/certs/gtm001001-cert-1.jpg",
            ),
            TraceCertImageResponse(
                title="质量检测报告",
                image_url="https://example.com/static/certs/gtm001001-cert-2.jpg",
            ),
        ],
        process_steps=[
            TraceProcessStepResponse(
                step_no=1,
                title="茶园采摘",
                description="春季头采，采摘时间和批次已登记。",
                time="2026-04-08T06:20:00",
                image_url="https://example.com/static/gallery/gtm001001-1.jpg",
            ),
            TraceProcessStepResponse(
                step_no=2,
                title="鲜叶摊青",
                description="采后鲜叶进入初制环节，控制温湿度。",
                time="2026-04-08T09:00:00",
                image_url="https://example.com/static/gallery/gtm001001-2.jpg",
            ),
            TraceProcessStepResponse(
                step_no=3,
                title="杀青整形",
                description="完成核心制茶工艺并记录生产批次。",
                time="2026-04-08T13:40:00",
                image_url="https://example.com/static/gallery/gtm001001-3.jpg",
            ),
            TraceProcessStepResponse(
                step_no=4,
                title="包装入库",
                description="礼盒包装完成，生成溯源码并入库。",
                time="2026-04-09T15:10:00",
                image_url="https://example.com/static/products/gtm001001/main.jpg",
            ),
        ],
        gallery_images=[
            TraceGalleryImageResponse(
                title="商品展示",
                image_url="https://example.com/static/gallery/gtm001001-1.jpg",
            ),
            TraceGalleryImageResponse(
                title="基地环境",
                image_url="https://example.com/static/gallery/gtm001001-2.jpg",
            ),
            TraceGalleryImageResponse(
                title="生产现场",
                image_url="https://example.com/static/gallery/gtm001001-3.jpg",
            ),
        ],
        video_info=TraceVideoInfoResponse(
            title="恩施玉露产地与制茶过程",
            cover_image="https://example.com/static/video/gtm001001-cover.jpg",
            video_url="https://example.com/static/video/gtm001001.mp4",
            duration_seconds=96,
            source_type="local",
            description="展示恩施玉露核心产区与制茶流程。",
        ),
        logistics_logs=[
            TraceLogisticsLogResponse(
                time="2026-04-09T18:20:00",
                status="已出库",
                location="恩施州仓",
                description="商品完成质检并出库。",
            ),
            TraceLogisticsLogResponse(
                time="2026-04-10T06:45:00",
                status="运输中",
                location="武汉中转中心",
                description="干线运输正常。",
            ),
            TraceLogisticsLogResponse(
                time="2026-04-10T14:30:00",
                status="已签收",
                location="上海浦东",
                description="订单已完成签收。",
            ),
        ],
    )


def _get_enabled_region(connection: sqlite3.Connection, region_id: int) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT id, name, boundary_geojson
        FROM regions
        WHERE id = ? AND is_enabled = 1
        """,
        (region_id,),
    ).fetchone()


def _get_product_with_region_by_token(connection: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT
            p.id,
            p.product_code,
            p.product_name,
            p.batch_no,
            p.producer_name,
            p.origin_lng,
            p.origin_lat,
            p.origin_fix_time,
            p.region_id,
            r.name AS region_name,
            r.center_lng AS map_lng,
            r.center_lat AS map_lat,
            r.boundary_geojson AS boundary_geojson
        FROM products p
        JOIN regions r ON r.id = p.region_id
        WHERE p.token = ?
        LIMIT 1
        """,
        (token,),
    ).fetchone()


def _parse_boundary_geojson(boundary_geojson: str | None) -> dict | None:
    if not boundary_geojson:
        return None
    try:
        return json.loads(boundary_geojson)
    except json.JSONDecodeError:
        return None


def _canonical_product_key(product_name: str) -> str:
    base_name = product_name.strip()
    for separator in ("路", "·", "-", "－", "|", "｜", "/"):
        if separator in base_name:
            base_name = base_name.split(separator, 1)[0].strip()
            break
    return MEDIA_KEY_ALIASES.get(base_name, base_name)


def _load_trace_media(connection: sqlite3.Connection, product_id: int, product_name: str) -> dict[str, object]:
    uploaded_rows = connection.execute(
        """
        SELECT image_url, original_name, sort_order
        FROM product_upload_images
        WHERE product_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (product_id,),
    ).fetchall()
    if uploaded_rows:
        product_image = uploaded_rows[0]["image_url"]
        gallery_images = [
            TraceGalleryImageResponse(
                title=row["original_name"] or f"现场图片 {index + 1}",
                image_url=row["image_url"],
            )
            for index, row in enumerate(uploaded_rows[:6])
        ]
        return {
            "product_image": product_image,
            "cert_images": [],
            "process_steps": [],
            "gallery_images": gallery_images,
            "video_info": None,
        }

    product_key = _canonical_product_key(product_name)
    media_rows = connection.execute(
        """
        SELECT media_type, title, file_url, sort_order
        FROM product_media_profiles
        WHERE product_key = ?
        ORDER BY media_type ASC, sort_order ASC, id ASC
        """,
        (product_key,),
    ).fetchall()
    process_rows = connection.execute(
        """
        SELECT step_no, title, description, image_url, time_text
        FROM product_process_profiles
        WHERE product_key = ?
        ORDER BY step_no ASC, id ASC
        """,
        (product_key,),
    ).fetchall()
    video_row = connection.execute(
        """
        SELECT title, video_url, cover_url, source_type, duration_seconds
        FROM product_video_profiles
        WHERE product_key = ?
        ORDER BY sort_order ASC, id ASC
        LIMIT 1
        """,
        (product_key,),
    ).fetchone()

    product_image = None
    cert_images: list[TraceCertImageResponse] = []
    gallery_images: list[TraceGalleryImageResponse] = []
    video_cover = None

    for row in media_rows:
        media_type = row["media_type"]
        if media_type == "product_image" and product_image is None:
            product_image = row["file_url"]
        elif media_type == "cert":
            cert_images.append(
                TraceCertImageResponse(
                    title=row["title"] or "资质证明",
                    image_url=row["file_url"],
                )
            )
        elif media_type == "gallery":
            gallery_images.append(
                TraceGalleryImageResponse(
                    title=row["title"] or "展示图片",
                    image_url=row["file_url"],
                )
            )
        elif media_type == "video_cover" and video_cover is None:
            video_cover = row["file_url"]

    process_steps = [
        TraceProcessStepResponse(
            step_no=row["step_no"],
            title=row["title"],
            description=row["description"],
            time=row["time_text"] or "",
            image_url=row["image_url"],
        )
        for row in process_rows
    ]

    video_info = None
    if video_row is not None:
        video_info = TraceVideoInfoResponse(
            title=video_row["title"],
            cover_image=video_row["cover_url"] or video_cover or product_image or "",
            video_url=video_row["video_url"],
            duration_seconds=video_row["duration_seconds"] or 0,
            source_type=video_row["source_type"] or "local",
            description=f"{product_key}产地溯源视频",
        )

    return {
        "product_image": product_image,
        "cert_images": cert_images[:3],
        "process_steps": process_steps[:4],
        "gallery_images": gallery_images[:3],
        "video_info": video_info,
    }


def _resolve_region_map_coords(product: sqlite3.Row) -> tuple[float | None, float | None]:
    if product["map_lng"] is not None and product["map_lat"] is not None:
        return product["map_lng"], product["map_lat"]
    mapped = REGION_GEO_COORDS.get(product["region_name"])
    if mapped is not None:
        lat, lng = mapped
        return lng, lat
    return product["map_lng"], product["map_lat"]


def _build_trace_logistics_logs(
    connection: sqlite3.Connection,
    product: sqlite3.Row,
) -> list[TraceLogisticsLogResponse]:
    rows = connection.execute(
        """
        SELECT
            sr.scan_time,
            sr.risk_detected,
            sr.risk_level,
            sr.is_first_scan,
            sr.scan_lng,
            sr.scan_lat
        FROM scan_records sr
        WHERE sr.product_id = ?
        ORDER BY sr.scan_time DESC, sr.id DESC
        LIMIT 3
        """,
        (product["id"],),
    ).fetchall()
    logs: list[TraceLogisticsLogResponse] = [
        TraceLogisticsLogResponse(
            time=_normalize_datetime_string(product["origin_fix_time"]),
            status="已登记",
            location=product["region_name"],
            description=f"{product['product_name']} 已完成产地登记并生成溯源码。",
        )
    ]
    for row in reversed(rows):
        if row["risk_detected"]:
            status = "异常预警"
            description = f"检测到{row['risk_level']}风险跨域扫码，请谨慎核验流转路径。"
        elif row["is_first_scan"]:
            status = "首次验真"
            description = "商品首次被扫码验真，流转记录开始写入。"
        else:
            status = "流转扫描"
            description = "商品流转节点扫码正常，未发现明显异常。"

        logs.append(
            TraceLogisticsLogResponse(
                time=_normalize_datetime_string(row["scan_time"]),
                status=status,
                location=_format_scan_location(row["scan_lng"], row["scan_lat"], product["region_name"]),
                description=description,
            )
        )
    return logs


def _format_scan_location(scan_lng: float | None, scan_lat: float | None, fallback: str) -> str:
    if scan_lng is None or scan_lat is None:
        return fallback
    return f"{fallback} ({scan_lng:.4f}, {scan_lat:.4f})"


def _find_existing_product_by_product_and_batch(
    connection: sqlite3.Connection,
    product_name: str,
    batch_no: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT id
        FROM products
        WHERE product_name = ? AND batch_no = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (product_name, batch_no),
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


def _insert_register_event(
    connection: sqlite3.Connection,
    payload: RegisterProductRequest,
    decision: RegisterDecision,
) -> None:
    event_type = "register_success" if decision.accepted else "register_rejected"
    severity = "info" if decision.accepted else "error"
    risk_level = "none" if decision.accepted else "high"
    product_code = decision.product_code if decision.accepted else None

    _insert_dashboard_event(
        connection=connection,
        event_type=event_type,
        event_time=_normalize_datetime_string(payload.location.fix_time),
        product_id=decision.product_id,
        product_code=product_code,
        location_lng=payload.location.lng,
        location_lat=payload.location.lat,
        related_lng=None,
        related_lat=None,
        message=decision.message,
        severity=severity,
        risk_level=risk_level,
        estimated_speed=None,
    )


def _insert_scan_event(
    connection: sqlite3.Connection,
    product: sqlite3.Row,
    event_type: str,
    event_time: str,
    scan_lng: float | None,
    scan_lat: float | None,
    message: str,
    risk_level: str,
    estimated_speed: float | None,
    previous_scan: sqlite3.Row | None,
) -> None:
    severity = "error" if event_type == "scan_anomaly" else "info"
    _insert_dashboard_event(
        connection=connection,
        event_type=event_type,
        event_time=event_time,
        product_id=product["id"],
        product_code=product["product_code"],
        location_lng=scan_lng,
        location_lat=scan_lat,
        related_lng=previous_scan["scan_lng"] if previous_scan is not None else None,
        related_lat=previous_scan["scan_lat"] if previous_scan is not None else None,
        message=message,
        severity=severity,
        risk_level=risk_level,
        estimated_speed=estimated_speed,
    )


def _insert_dashboard_event(
    connection: sqlite3.Connection,
    event_type: str,
    event_time: str,
    product_id: int | None,
    product_code: str | None,
    location_lng: float | None,
    location_lat: float | None,
    related_lng: float | None,
    related_lat: float | None,
    message: str,
    severity: str,
    risk_level: str,
    estimated_speed: float | None,
) -> None:
    with connection:
        connection.execute(
            """
            INSERT INTO dashboard_events (
                event_type,
                event_time,
                product_id,
                product_code,
                location_lng,
                location_lat,
                related_lng,
                related_lat,
                message,
                severity,
                risk_level,
                estimated_speed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_type,
                _normalize_datetime_string(event_time),
                product_id,
                product_code,
                location_lng,
                location_lat,
                related_lng,
                related_lat,
                message,
                severity,
                risk_level,
                estimated_speed,
            ),
        )


def _get_scan_stats(connection: sqlite3.Connection, product_id: int) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT
            COUNT(*) AS scan_count,
            MIN(scan_time) AS first_scan_time,
            MAX(scan_time) AS last_scan_time
        FROM scan_records
        WHERE product_id = ?
        """,
        (product_id,),
    ).fetchone()
    latest = _get_latest_scan(connection, product_id)
    return {
        "scan_count": row["scan_count"] or 0,
        "first_scan_time": _normalize_datetime_string(row["first_scan_time"]) if row["first_scan_time"] else None,
        "last_scan_time": _normalize_datetime_string(row["last_scan_time"]) if row["last_scan_time"] else None,
        "latest_risk_level": latest["risk_level"] if latest is not None else "none",
    }


def _get_latest_scan(connection: sqlite3.Connection, product_id: int) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT id, scan_time, scan_lng, scan_lat, risk_level, estimated_speed
        FROM scan_records
        WHERE product_id = ?
        ORDER BY scan_time DESC, id DESC
        LIMIT 1
        """,
        (product_id,),
    ).fetchone()


def _derive_trace_state(scan_count: int, latest_risk_level: str) -> tuple[str, str]:
    if latest_risk_level in {"medium", "high"}:
        return "risky", latest_risk_level
    if scan_count <= 0:
        return "normal", "none"
    return "opened", "none"


def _build_fallback_events(connection: sqlite3.Connection, limit: int) -> list[DashboardEventResponse]:
    rows = connection.execute(
        """
        SELECT
            id,
            result,
            created_at,
            reason_message,
            created_product_id
        FROM register_attempts
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    product_codes: dict[int, str] = {}
    if rows:
        product_ids = [row["created_product_id"] for row in rows if row["created_product_id"] is not None]
        if product_ids:
            placeholders = ",".join("?" for _ in product_ids)
            for product_row in connection.execute(
                f"SELECT id, product_code FROM products WHERE id IN ({placeholders})",
                product_ids,
            ).fetchall():
                product_codes[product_row["id"]] = product_row["product_code"]

    return [
        DashboardEventResponse(
            event_id=f"ATT-{row['id']}",
            event_type="register_success" if row["result"] == "accepted" else "register_rejected",
            event_time=_normalize_datetime_string(row["created_at"]),
            product_code=product_codes.get(row["created_product_id"]),
            location=None,
            message=row["reason_message"],
            risk_level="none" if row["result"] == "accepted" else "high",
            speed=None,
        )
        for row in rows
    ]


def _query_counts_by_date(
    connection: sqlite3.Connection,
    table: str,
    field: str,
    days: int,
    extra_where: str | None = None,
) -> dict[str, int]:
    where_parts = [f"DATE({field}, 'localtime') >= DATE('now', '-{days - 1} day', 'localtime')"]
    if extra_where:
        where_parts.append(extra_where)
    query = f"""
        SELECT DATE({field}, 'localtime') AS bucket, COUNT(*) AS count
        FROM {table}
        WHERE {' AND '.join(where_parts)}
        GROUP BY DATE({field}, 'localtime')
    """
    return {
        row["bucket"]: row["count"]
        for row in connection.execute(query).fetchall()
    }


def _haversine_distance_meters(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    earth_radius = 6371000
    lat1_rad, lng1_rad, lat2_rad, lng2_rad = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2_rad - lat1_rad
    dlng = lng2_rad - lng1_rad
    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlng / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return earth_radius * c


def _normalize_datetime_string(value: str | None) -> str:
    if not value:
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    return _parse_datetime(value).strftime("%Y-%m-%dT%H:%M:%S")


def _parse_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue

    raise ValueError(f"Unsupported datetime format: {value}")


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
