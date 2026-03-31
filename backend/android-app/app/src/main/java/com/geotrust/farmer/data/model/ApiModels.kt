package com.geotrust.farmer.data.model

data class BootstrapResponse(
    val app_name: String,
    val register_enabled: Boolean,
    val location_required: Boolean,
    val risk_policy: RiskPolicyDto,
    val regions: List<RegionDto>,
)

data class RiskPolicyDto(
    val reject_mock_location: Boolean,
    val reject_emulator: Boolean,
    val reject_debugger: Boolean,
    val reject_root: Boolean,
)

data class RegionDto(
    val id: Int,
    val code: String,
    val name: String,
    val product_type: String,
    val province: String?,
    val city: String?,
    val center_lng: Double?,
    val center_lat: Double?,
)

data class LocationPayloadDto(
    val lng: Double,
    val lat: Double,
    val accuracy: Double?,
    val provider: String?,
    val fix_time: String,
)

data class RiskFlagsPayloadDto(
    val is_mock: Boolean,
    val is_emulator: Boolean,
    val is_debugger: Boolean,
    val is_rooted: Boolean,
    val dev_options_enabled: Boolean,
)

data class DevicePayloadDto(
    val android_id_hash: String,
    val brand: String?,
    val model: String?,
    val os_version: String?,
)

data class AppPayloadDto(
    val version_name: String?,
    val version_code: Int?,
)

data class ValidateLocationRequestDto(
    val region_id: Int,
    val location: LocationPayloadDto,
    val risk_flags: RiskFlagsPayloadDto,
)

data class ValidateLocationResponse(
    val valid: Boolean,
    val validation_result: String,
    val message: String,
    val region_name: String?,
    val in_region: Boolean,
    val blocked_by_risk: Boolean,
)

data class RegisterProductRequestDto(
    val product_name: String,
    val batch_no: String,
    val region_id: Int,
    val producer_name: String,
    val location: LocationPayloadDto,
    val risk_flags: RiskFlagsPayloadDto,
    val device: DevicePayloadDto,
    val app: AppPayloadDto,
)

data class RegisterProductResponse(
    val accepted: Boolean,
    val register_result: String,
    val message: String,
    val product_id: Int?,
    val product_code: String?,
    val token: String?,
    val trace_url: String?,
    val qr_code_url: String?,
    val region_name: String?,
)
