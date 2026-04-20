from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from pydantic import BaseModel

from collections import defaultdict

from .analytics_demo import MODULE_NAME, build_demo_dashboard, build_demo_product_report
from .analytics_schemas import DemoDashboardResponse, DemoLlmAnalysisResponse, DemoProductReportResponse
from .config import get_settings
from .database import get_connection, initialize_database
from .rag_answer import build_llm_strategy_analysis
from .rag_search import search_rag
from .schemas import (
    BootstrapResponse,
    DashboardEventsListResponse,
    DashboardMapDataResponse,
    DashboardRegionListResponse,
    DashboardSummaryResponse,
    DashboardTrendsResponse,
    RegisterProductRequest,
    RegisterProductResponse,
    RiskPolicyResponse,
    RegionResponse,
    ScanRecordRequest,
    ScanRecordResponse,
    TraceProductResponse,
    ValidateLocationRequest,
    ValidateLocationResponse,
)
from .services import (
    get_dashboard_map_data,
    get_dashboard_summary,
    get_dashboard_trends,
    get_trace_product,
    list_dashboard_events,
    list_enabled_regions,
    list_region_analysis,
    record_scan,
    register_product,
    validate_location,
)

settings = get_settings()


class RagSearchResponse(BaseModel):
    query: str
    documents: list[dict]
    cards: list[dict]
    chunks: list[dict]
    insights: list[dict]


class LegacyProvinceMapItem(BaseModel):
    name: str
    type_count: int


class LegacyProvinceMapResponse(BaseModel):
    provinces: list[LegacyProvinceMapItem]


class LegacyRealtimeLogRecord(BaseModel):
    event_id: str
    event_time: str
    isClone: bool
    product_code: str | None = None
    product_name: str
    product_type: str | None = None
    originName: str
    originCoords: list[float]
    scanName: str
    scanCoords: list[float]
    message: str


class LegacyRealtimeLogsResponse(BaseModel):
    records: list[LegacyRealtimeLogRecord]


class LegacyProvinceSpecialtyItem(BaseModel):
    name: str
    type: str
    registerCount: int


class LegacyProvinceSpecialtyResponse(BaseModel):
    province: str
    items: list[LegacyProvinceSpecialtyItem]


DEMO_REGION_PROVINCE_KEYWORDS = {
    "湖北": (
        "恩施",
        "赤壁",
        "神农架",
        "随州",
        "秭归",
        "武汉",
        "罗田",
        "孝感",
        "宜昌",
        "潜江",
        "梁子湖",
    ),
    "浙江": (
        "西湖",
        "绍兴",
    ),
    "江苏": (
        "阳澄湖",
    ),
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database(settings)
    yield


app = FastAPI(
    title="Geo-Trust Android Backend",
    version="0.1.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ai-analysis-report", include_in_schema=False)
def trusted_value_demo_page() -> FileResponse:
    return FileResponse(
        settings.static_dir / "insights" / "index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/admin", include_in_schema=False)
def admin_demo_page() -> FileResponse:
    return FileResponse(settings.static_dir / "admin-vue" / "index.html")


@app.get("/trace", include_in_schema=False)
def trace_page() -> FileResponse:
    return FileResponse(settings.static_dir / "consumer" / "index.html")


@app.get("/trace/{token}", include_in_schema=False)
def trace_token_page(token: str) -> FileResponse:
    return FileResponse(settings.static_dir / "consumer" / "index.html")


@app.get("/api/mobile/bootstrap", response_model=BootstrapResponse)
def mobile_bootstrap() -> BootstrapResponse:
    with get_connection(settings.database_path) as connection:
        regions = list_enabled_regions(connection)

    return BootstrapResponse(
        app_name=settings.app_name,
        register_enabled=settings.register_enabled,
        location_required=settings.location_required,
        risk_policy=RiskPolicyResponse(
            reject_mock_location=settings.reject_mock_location,
            reject_emulator=settings.reject_emulator,
            reject_debugger=settings.reject_debugger,
            reject_root=settings.reject_root,
        ),
        regions=[
            RegionResponse(
                id=row["id"],
                code=row["code"],
                name=row["name"],
                product_type=row["product_type"],
                province=row["province"],
                city=row["city"],
                center_lng=row["center_lng"],
                center_lat=row["center_lat"],
            )
            for row in regions
        ],
    )


@app.post("/api/mobile/register-product", response_model=RegisterProductResponse)
def mobile_register_product(payload: RegisterProductRequest) -> RegisterProductResponse:
    with get_connection(settings.database_path) as connection:
        return register_product(connection, payload, settings)


@app.post("/api/mobile/register-product-with-images", response_model=RegisterProductResponse)
async def mobile_register_product_with_images(
    payload: str = Form(...),
    images: list[UploadFile] | None = File(default=None),
) -> RegisterProductResponse:
    try:
        parsed_payload = RegisterProductRequest.model_validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    with get_connection(settings.database_path) as connection:
        response = register_product(connection, parsed_payload, settings)
        if response.accepted and response.product_id is not None and images:
            await _store_product_upload_images(
                connection=connection,
                product_id=response.product_id,
                images=images,
            )
    return response


@app.post("/api/mobile/validate-location", response_model=ValidateLocationResponse)
def mobile_validate_location(payload: ValidateLocationRequest) -> ValidateLocationResponse:
    with get_connection(settings.database_path) as connection:
        return validate_location(connection, payload, settings)


@app.get("/api/trace/{token}", response_model=TraceProductResponse)
def api_trace_product(token: str) -> TraceProductResponse:
    with get_connection(settings.database_path) as connection:
        trace = get_trace_product(connection, token)
    if trace is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return trace


@app.post("/api/scan/{token}", response_model=ScanRecordResponse)
def scan_product(token: str, payload: ScanRecordRequest) -> ScanRecordResponse:
    with get_connection(settings.database_path) as connection:
        result = record_scan(connection, token, payload)
    if result is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return result


@app.get("/api/dashboard/summary", response_model=DashboardSummaryResponse)
def dashboard_summary() -> DashboardSummaryResponse:
    with get_connection(settings.database_path) as connection:
        return get_dashboard_summary(connection)


@app.get("/api/dashboard/events", response_model=DashboardEventsListResponse)
def dashboard_events(limit: int = 50, event_type: str | None = None) -> DashboardEventsListResponse:
    safe_limit = min(max(limit, 1), 200)
    with get_connection(settings.database_path) as connection:
        return list_dashboard_events(connection, limit=safe_limit, event_type=event_type)


@app.get("/api/dashboard/map-data", response_model=DashboardMapDataResponse)
def dashboard_map_data() -> DashboardMapDataResponse:
    with get_connection(settings.database_path) as connection:
        return get_dashboard_map_data(connection)


@app.get("/api/dashboard/trends", response_model=DashboardTrendsResponse)
def dashboard_trends(days: int = 7) -> DashboardTrendsResponse:
    with get_connection(settings.database_path) as connection:
        return get_dashboard_trends(connection, days=days)


@app.get("/api/dashboard/regions", response_model=DashboardRegionListResponse)
def dashboard_regions() -> DashboardRegionListResponse:
    with get_connection(settings.database_path) as connection:
        return list_region_analysis(connection)


@app.get("/api/dashboard/trend", response_model=DashboardTrendsResponse)
def dashboard_trend_legacy(days: int = 7) -> DashboardTrendsResponse:
    with get_connection(settings.database_path) as connection:
        return get_dashboard_trends(connection, days=days)


@app.get("/api/dashboard/pie")
def dashboard_pie_legacy() -> list[dict[str, int | str]]:
    with get_connection(settings.database_path) as connection:
        regions = list_region_analysis(connection).regions

    grouped: dict[str, int] = {}
    for item in regions:
        key = item.type or "其他"
        grouped[key] = grouped.get(key, 0) + max(int(item.todayCount or 0), 0)

    if not grouped:
        return [
            {"name": "谷物类", "value": 38},
            {"name": "茶叶类", "value": 26},
            {"name": "酒水饮料", "value": 20},
            {"name": "生鲜水果", "value": 16},
        ]

    return [{"name": name, "value": value} for name, value in grouped.items()]


@app.get("/api/map/provinces", response_model=LegacyProvinceMapResponse)
def province_map_legacy() -> LegacyProvinceMapResponse:
    products = build_demo_dashboard().products
    province_totals: dict[str, int] = defaultdict(int)

    for product in products:
        province = _infer_demo_province(product.region_name)
        if not province:
            continue
        province_totals[province] += 1

    provinces = [
        LegacyProvinceMapItem(name=name, type_count=value)
        for name, value in sorted(province_totals.items(), key=lambda item: item[0])
    ]
    return LegacyProvinceMapResponse(provinces=provinces)


@app.get("/api/logs/realtime", response_model=LegacyRealtimeLogsResponse)
def realtime_logs_legacy(
    limit: int = 80,
    province: str | None = Query(default=None),
) -> LegacyRealtimeLogsResponse:
    safe_limit = min(max(limit, 1), 200)
    with get_connection(settings.database_path) as connection:
        events = list_dashboard_events(connection, limit=safe_limit).events
        map_data = get_dashboard_map_data(connection)

    register_by_product = {item.product_code: item for item in map_data.register_points}
    latest_scan_by_product: dict[str, object] = {}
    for item in map_data.scan_points:
        current = latest_scan_by_product.get(item.product_code)
        if current is None or (item.scan_time or "") >= (current.scan_time or ""):
            latest_scan_by_product[item.product_code] = item

    records: list[LegacyRealtimeLogRecord] = []
    normalized_filter = _normalize_province_name(province)
    fallback_scans = [
        ("??", [116.4, 39.9]),
        ("??", [121.47, 31.23]),
        ("??", [113.26, 23.13]),
        ("??", [104.06, 30.67]),
        ("??", [120.15, 30.28]),
        ("??", [118.78, 32.04]),
    ]
    cutoff = datetime.now() - timedelta(hours=24)

    for index, event in enumerate(events):
        normalized_time = (event.event_time or "").replace("Z", "+00:00")
        try:
            event_dt = datetime.fromisoformat(normalized_time)
        except ValueError:
            event_dt = None

        if event_dt is not None and event_dt.tzinfo is not None:
            event_dt = event_dt.astimezone().replace(tzinfo=None)

        if event_dt is not None and event_dt < cutoff:
            continue

        product_code = event.product_code or f"SN-{1000 + index}"
        register_point = register_by_product.get(product_code)
        scan_point = latest_scan_by_product.get(product_code)
        event_province = _normalize_province_name(event.province or (register_point.province if register_point else None))

        if normalized_filter and event_province != normalized_filter:
            continue

        fallback_name, fallback_coords = fallback_scans[index % len(fallback_scans)]
        is_clone = event.risk_level == "high" or event.event_type == "scan_anomaly"
        origin_coords = [register_point.lng, register_point.lat] if register_point else _province_center(event_province)
        scan_coords = [scan_point.lng, scan_point.lat] if scan_point else fallback_coords

        records.append(
            LegacyRealtimeLogRecord(
                event_id=event.event_id,
                event_time=event.event_time,
                isClone=is_clone,
                product_code=product_code,
                product_name=event.region_name or "Geo-Trust ????",
                product_type=None,
                originName=event_province or "??",
                originCoords=origin_coords,
                scanName=event.location or (scan_point.region_name if scan_point else fallback_name),
                scanCoords=scan_coords,
                message=event.message,
            )
        )

    return LegacyRealtimeLogsResponse(records=records)


@app.get("/api/province/specialties", response_model=LegacyProvinceSpecialtyResponse)
def province_specialties_legacy(province: str) -> LegacyProvinceSpecialtyResponse:
    normalized = _normalize_province_name(province)
    grouped: dict[tuple[str, str], int] = defaultdict(int)
    for product in build_demo_dashboard().products:
        row_province = _infer_demo_province(product.region_name)
        if row_province != normalized:
            continue
        grouped[(product.family_name, product.category)] += 1

    items = [
        LegacyProvinceSpecialtyItem(
            name=family_name,
            type=category or "其他",
            registerCount=count,
        )
        for (family_name, category), count in sorted(grouped.items(), key=lambda item: (-item[1], item[0][0]))
    ]
    return LegacyProvinceSpecialtyResponse(province=normalized, items=items)


@app.post("/api/ai/report/generate")
def ai_report_generate_legacy() -> dict[str, str]:
    return {"url": "/ai-analysis-report"}


@app.get("/api/analytics/demo/dashboard", response_model=DemoDashboardResponse)
def analytics_demo_dashboard() -> DemoDashboardResponse:
    return build_demo_dashboard()


@app.get("/api/analytics/demo/report/{product_id}", response_model=DemoProductReportResponse)
def analytics_demo_report(product_id: str) -> DemoProductReportResponse:
    try:
        return build_demo_product_report(product_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"{MODULE_NAME} does not contain product {product_id}") from exc


@app.get("/api/rag/search", response_model=RagSearchResponse)
def rag_search(query: str, top_k: int = 5) -> RagSearchResponse:
    return RagSearchResponse(**search_rag(query, top_k=top_k))


@app.get("/api/analytics/demo/llm-report/{product_id}", response_model=DemoLlmAnalysisResponse)
def analytics_demo_llm_report(product_id: str) -> DemoLlmAnalysisResponse:
    try:
        return build_llm_strategy_analysis(product_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"{MODULE_NAME} does not contain product {product_id}") from exc


PROVINCE_ALIAS_MAP = {
    "Province-01": "\u6e56\u5317",
    "Province-02": "\u6e56\u5317",
    "Province-03": "\u6e56\u5317",
    "Province-04": "\u6e56\u5317",
    "Province-05": "\u6e56\u5317",
    "Province-06": "\u6e56\u5317",
    "Province-07": "\u6e56\u5317",
    "Province-08": "\u6e56\u5317",
    "Province-09": "\u6e56\u5317",
    "Province-10": "\u6e56\u5317",
    "Province-11": "\u6e56\u5317",
    "Province-12": "\u6e56\u5317",
    "Province-13": "\u6d59\u6c5f",
    "Province-14": "\u6d59\u6c5f",
    "Province-15": "\u6c5f\u82cf",
}


def _normalize_province_name(name: str | None) -> str:
    if not name:
        return ""
    normalized = str(name).strip()
    normalized = normalized.replace("\u7701", "").replace("\u5e02", "")
    normalized = normalized.replace("\u81ea\u6cbb\u533a", "").replace("\u7279\u522b\u884c\u653f\u533a", "")
    normalized = normalized.replace("\u7ef4\u543e\u5c14", "").replace("\u56de\u65cf", "").replace("\u58ee\u65cf", "")
    return PROVINCE_ALIAS_MAP.get(normalized, normalized)


def _infer_demo_province(region_name: str | None) -> str:
    normalized_region = str(region_name or "").strip()
    if not normalized_region:
        return ""

    for province, keywords in DEMO_REGION_PROVINCE_KEYWORDS.items():
        if any(keyword in normalized_region for keyword in keywords):
            return province
    return ""


def _province_center(province: str | None) -> list[float]:
    centers = {
        "北京": [116.4074, 39.9042],
        "天津": [117.2, 39.1333],
        "河北": [114.5025, 38.0455],
        "山西": [112.5492, 37.857],
        "内蒙古": [111.6708, 40.8183],
        "辽宁": [123.4315, 41.8057],
        "吉林": [125.3245, 43.8868],
        "黑龙江": [126.6424, 45.756],
        "上海": [121.4737, 31.2304],
        "江苏": [118.7674, 32.0415],
        "浙江": [120.1551, 30.2741],
        "安徽": [117.283, 31.8612],
        "福建": [119.2965, 26.0745],
        "江西": [115.8922, 28.6765],
        "山东": [117.0009, 36.6758],
        "河南": [113.6654, 34.757],
        "湖北": [114.3054, 30.5931],
        "湖南": [112.9389, 28.2282],
        "广东": [113.2644, 23.1291],
        "广西": [108.3669, 22.817],
        "海南": [110.3312, 20.0311],
        "重庆": [106.5516, 29.563],
        "四川": [104.0665, 30.5723],
        "贵州": [106.7135, 26.5783],
        "云南": [102.7123, 25.0406],
        "西藏": [91.1322, 29.6604],
        "陕西": [108.9398, 34.3416],
        "甘肃": [103.8343, 36.0611],
        "青海": [101.7782, 36.6232],
        "宁夏": [106.2587, 38.4712],
        "新疆": [87.6177, 43.7928],
        "香港": [114.1694, 22.3193],
        "澳门": [113.5439, 22.1987],
        "台湾": [121.5654, 25.033],
    }
    return centers.get(province or "", [116.4, 39.9])


async def _store_product_upload_images(
    connection,
    product_id: int,
    images: list[UploadFile],
) -> None:
    product_dir = settings.upload_dir / "products" / str(product_id)
    product_dir.mkdir(parents=True, exist_ok=True)

    sort_order = 0
    for image in images:
        if not image.filename:
            continue
        if not (image.content_type or "").startswith("image/"):
            continue

        suffix = Path(image.filename).suffix.lower() or ".jpg"
        safe_name = _sanitize_filename(image.filename)
        file_name = f"{sort_order + 1:02d}_{safe_name}"
        file_path = product_dir / file_name
        content = await image.read()
        if not content:
            continue

        file_path.write_bytes(content)
        image_url = f"{settings.base_url.rstrip('/')}/static/uploads/products/{product_id}/{file_name}"
        with connection:
            connection.execute(
                """
                INSERT INTO product_upload_images (
                    product_id,
                    image_url,
                    original_name,
                    sort_order
                ) VALUES (?, ?, ?, ?)
                """,
                (product_id, image_url, image.filename, sort_order),
            )
        sort_order += 1


def _sanitize_filename(filename: str) -> str:
    keep = []
    for char in filename.strip():
        if char.isalnum() or char in {"-", "_", "."}:
            keep.append(char)
        else:
            keep.append("_")
    sanitized = "".join(keep).strip("._")
    return sanitized or "image.jpg"
