from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RiskPolicyResponse(BaseModel):
    reject_mock_location: bool
    reject_emulator: bool
    reject_debugger: bool
    reject_root: bool


class RegionResponse(BaseModel):
    id: int
    code: str
    name: str
    product_type: str
    province: Optional[str] = None
    city: Optional[str] = None
    center_lng: Optional[float] = None
    center_lat: Optional[float] = None


class BootstrapResponse(BaseModel):
    app_name: str
    register_enabled: bool
    location_required: bool
    risk_policy: RiskPolicyResponse
    regions: list[RegionResponse]


class LocationPayload(BaseModel):
    lng: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)
    accuracy: Optional[float] = Field(default=None, ge=0)
    provider: Optional[str] = Field(default=None, max_length=50)
    fix_time: str


class RiskFlagsPayload(BaseModel):
    is_mock: bool
    is_emulator: bool
    is_debugger: bool
    is_rooted: bool = False
    dev_options_enabled: bool = False


class DevicePayload(BaseModel):
    android_id_hash: str = Field(..., min_length=8, max_length=256)
    brand: Optional[str] = Field(default=None, max_length=100)
    model: Optional[str] = Field(default=None, max_length=100)
    os_version: Optional[str] = Field(default=None, max_length=100)


class AppPayload(BaseModel):
    version_name: Optional[str] = Field(default=None, max_length=50)
    version_code: Optional[int] = Field(default=None, ge=1)


class RegisterProductRequest(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=100)
    batch_no: str = Field(..., min_length=1, max_length=100)
    region_id: int = Field(..., ge=1)
    producer_name: str = Field(..., min_length=1, max_length=100)
    location: LocationPayload
    risk_flags: RiskFlagsPayload
    device: DevicePayload
    app: Optional[AppPayload] = None


class ValidateLocationRequest(BaseModel):
    region_id: int = Field(..., ge=1)
    location: LocationPayload
    risk_flags: RiskFlagsPayload


class ValidateLocationResponse(BaseModel):
    valid: bool
    validation_result: str
    message: str
    region_name: Optional[str] = None
    in_region: bool = False
    blocked_by_risk: bool = False


class RegisterProductResponse(BaseModel):
    accepted: bool
    register_result: str
    message: str
    product_id: Optional[int] = None
    product_code: Optional[str] = None
    token: Optional[str] = None
    trace_url: Optional[str] = None
    qr_code_url: Optional[str] = None
    region_name: Optional[str] = None


class TraceCertImageResponse(BaseModel):
    title: str
    image_url: str


class TraceProcessStepResponse(BaseModel):
    step_no: int
    title: str
    description: str
    time: str
    image_url: Optional[str] = None


class TraceGalleryImageResponse(BaseModel):
    title: str
    image_url: str


class TraceVideoInfoResponse(BaseModel):
    title: str
    cover_image: str
    video_url: str
    duration_seconds: int
    source_type: str = "local"
    description: Optional[str] = None


class TraceLogisticsLogResponse(BaseModel):
    time: str
    status: str
    location: str
    description: str


class TraceProductResponse(BaseModel):
    product_id: int
    product_code: str
    product_name: str
    product_image: Optional[str] = None
    batch_no: str
    region_name: str
    producer_name: str
    origin_lng: float
    origin_lat: float
    map_lng: Optional[float] = None
    map_lat: Optional[float] = None
    region_boundary_geojson: Optional[dict] = None
    origin_fix_time: str
    scan_count: int
    first_scan_time: Optional[str] = None
    last_scan_time: Optional[str] = None
    status: str
    risk_level: str
    cert_images: list[TraceCertImageResponse] = []
    process_steps: list[TraceProcessStepResponse] = []
    gallery_images: list[TraceGalleryImageResponse] = []
    video_info: Optional[TraceVideoInfoResponse] = None
    logistics_logs: list[TraceLogisticsLogResponse] = []


class ScanRecordRequest(BaseModel):
    scan_lng: Optional[float] = Field(default=None, ge=-180, le=180)
    scan_lat: Optional[float] = Field(default=None, ge=-90, le=90)
    scan_accuracy: Optional[float] = Field(default=None, ge=0)
    scan_time: Optional[str] = None
    device_info: Optional[str] = Field(default=None, max_length=1000)


class ScanRecordResponse(BaseModel):
    scan_id: int
    status: str
    message: str
    risk_detected: bool
    risk_level: str
    estimated_speed: Optional[float] = None


class DashboardSummaryResponse(BaseModel):
    today_registered: int
    today_scans: int
    today_rejected: int
    today_anomalies: int
    total_products: int
    total_scans: int


class DashboardEventResponse(BaseModel):
    event_id: str
    event_type: str
    event_time: str
    product_code: Optional[str] = None
    location: Optional[str] = None
    region_name: Optional[str] = None
    province: Optional[str] = None
    message: str
    risk_level: str = "none"
    speed: Optional[float] = None


class DashboardEventsListResponse(BaseModel):
    events: list[DashboardEventResponse]


class DashboardMapPointResponse(BaseModel):
    lng: float
    lat: float
    product_code: str
    region_name: Optional[str] = None
    province: Optional[str] = None
    scan_time: Optional[str] = None


class DashboardAnomalyLineResponse(BaseModel):
    from_lng: float
    from_lat: float
    to_lng: float
    to_lat: float
    product_code: str
    reason: str
    region_name: Optional[str] = None
    province: Optional[str] = None
    risk_level: str = "none"
    speed: Optional[float] = None


class DashboardRegionAnalysisResponse(BaseModel):
    name: str
    type: str
    province: Optional[str] = None
    todayCount: int
    anomalies: int
    totalScans: int


class DashboardMapDataResponse(BaseModel):
    register_points: list[DashboardMapPointResponse]
    scan_points: list[DashboardMapPointResponse]
    anomaly_lines: list[DashboardAnomalyLineResponse]
    regions: list[DashboardRegionAnalysisResponse]


class DashboardTrendsResponse(BaseModel):
    dates: list[str]
    registrations: list[int]
    scans: list[int]
    alerts: list[int]


class DashboardRegionListResponse(BaseModel):
    regions: list[DashboardRegionAnalysisResponse]
