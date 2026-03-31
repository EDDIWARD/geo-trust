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
