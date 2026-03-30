package com.geotrust.farmer.ui

import android.content.Context
import android.os.Build
import android.provider.Settings
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.geotrust.farmer.data.model.AppPayloadDto
import com.geotrust.farmer.data.model.DevicePayloadDto
import com.geotrust.farmer.data.model.LocationPayloadDto
import com.geotrust.farmer.data.model.RegionDto
import com.geotrust.farmer.data.model.RegisterProductRequestDto
import com.geotrust.farmer.data.model.RegisterProductResponse
import com.geotrust.farmer.data.model.RiskFlagsPayloadDto
import com.geotrust.farmer.data.model.ValidateLocationRequestDto
import com.geotrust.farmer.data.network.NetworkModule
import com.geotrust.farmer.data.repository.MobileRegisterRepository
import com.geotrust.farmer.location.DeviceLocation
import com.geotrust.farmer.location.LocationProvider
import com.geotrust.farmer.risk.DeviceRiskCollector
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.security.MessageDigest

data class RegisterUiState(
    val bootstrapLoaded: Boolean = false,
    val bootstrapError: String? = null,
    val regions: List<RegionDto> = emptyList(),
    val selectedRegionId: Int? = null,
    val productName: String = "",
    val batchNo: String = "",
    val producerName: String = "",
    val locationPermissionGranted: Boolean = false,
    val locationSummary: String = "尚未获取定位",
    val riskSummary: String = "尚未检测设备环境",
    val latestLocation: DeviceLocation? = null,
    val validationMessage: String? = null,
    val registrationResult: RegisterProductResponse? = null,
    val isLoading: Boolean = false,
)

class RegisterViewModel(
    private val appContext: Context,
    private val repository: MobileRegisterRepository,
    private val locationProvider: LocationProvider,
    private val deviceRiskCollector: DeviceRiskCollector,
) : ViewModel() {
    private val _uiState = MutableStateFlow(RegisterUiState())
    val uiState: StateFlow<RegisterUiState> = _uiState.asStateFlow()

    fun loadBootstrap() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, bootstrapError = null) }
            runCatching { repository.getBootstrap() }
                .onSuccess { bootstrap ->
                    _uiState.update {
                        it.copy(
                            bootstrapLoaded = true,
                            isLoading = false,
                            regions = bootstrap.regions,
                            selectedRegionId = bootstrap.regions.firstOrNull()?.id,
                        )
                    }
                }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            bootstrapError = error.message ?: "加载初始化配置失败",
                        )
                    }
                }
        }
    }

    fun onLocationPermissionChanged(granted: Boolean) {
        _uiState.update { it.copy(locationPermissionGranted = granted) }
    }

    fun updateProductName(value: String) {
        _uiState.update { it.copy(productName = value) }
    }

    fun updateBatchNo(value: String) {
        _uiState.update { it.copy(batchNo = value) }
    }

    fun updateProducerName(value: String) {
        _uiState.update { it.copy(producerName = value) }
    }

    fun updateSelectedRegionId(regionId: Int) {
        _uiState.update { it.copy(selectedRegionId = regionId) }
    }

    fun validateCurrentLocation() {
        val state = _uiState.value
        val regionId = state.selectedRegionId ?: return

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, validationMessage = null, registrationResult = null) }
            val locationResult = locationProvider.getCurrentLocation()
            locationResult.onSuccess { location ->
                val risk = deviceRiskCollector.collect()
                val riskSummary = buildRiskSummary(location, risk)
                runCatching {
                    repository.validateLocation(
                        ValidateLocationRequestDto(
                            region_id = regionId,
                            location = location.toLocationPayload(),
                            risk_flags = RiskFlagsPayloadDto(
                                is_mock = location.isMock,
                                is_emulator = risk.isEmulator,
                                is_debugger = risk.isDebugger,
                                dev_options_enabled = risk.devOptionsEnabled,
                            ),
                        ),
                    )
                }.onSuccess { validation ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            latestLocation = location,
                            locationSummary = buildLocationSummary(location),
                            riskSummary = riskSummary,
                            validationMessage = validation.message,
                        )
                    }
                }.onFailure { error ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            latestLocation = location,
                            locationSummary = buildLocationSummary(location),
                            riskSummary = riskSummary,
                            validationMessage = error.message ?: "位置校验失败",
                        )
                    }
                }
            }.onFailure { error ->
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        validationMessage = error.message ?: "获取定位失败",
                    )
                }
            }
        }
    }

    fun registerProduct() {
        val state = _uiState.value
        val regionId = state.selectedRegionId ?: return

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, registrationResult = null) }
            val location = state.latestLocation ?: locationProvider.getCurrentLocation().getOrNull()
            if (location == null) {
                _uiState.update {
                    it.copy(isLoading = false, validationMessage = "未获取到定位，无法登记")
                }
                return@launch
            }

            val risk = deviceRiskCollector.collect()
            val riskSummary = buildRiskSummary(location, risk)
            runCatching {
                repository.registerProduct(
                    RegisterProductRequestDto(
                        product_name = state.productName,
                        batch_no = state.batchNo,
                        region_id = regionId,
                        producer_name = state.producerName,
                        location = location.toLocationPayload(),
                        risk_flags = RiskFlagsPayloadDto(
                            is_mock = location.isMock,
                            is_emulator = risk.isEmulator,
                            is_debugger = risk.isDebugger,
                            dev_options_enabled = risk.devOptionsEnabled,
                        ),
                        device = DevicePayloadDto(
                            android_id_hash = androidIdHash(),
                            brand = Build.BRAND,
                            model = Build.MODEL,
                            os_version = Build.VERSION.RELEASE,
                        ),
                        app = AppPayloadDto(
                            version_name = "0.1.0",
                            version_code = 1,
                        ),
                    ),
                )
            }.onSuccess { response ->
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        latestLocation = location,
                        locationSummary = buildLocationSummary(location),
                        riskSummary = riskSummary,
                        registrationResult = response,
                        validationMessage = response.message,
                    )
                }
            }.onFailure { error ->
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        validationMessage = error.message ?: "登记失败",
                    )
                }
            }
        }
    }

    private fun DeviceLocation.toLocationPayload(): LocationPayloadDto {
        return LocationPayloadDto(
            lng = lng,
            lat = lat,
            accuracy = accuracy?.toDouble(),
            provider = provider,
            fix_time = fixTime,
        )
    }

    private fun buildLocationSummary(location: DeviceLocation): String {
        return "经度 %.6f，纬度 %.6f，精度 %s m，来源 %s".format(
            location.lng,
            location.lat,
            location.accuracy?.toInt()?.toString() ?: "-",
            location.provider ?: "-",
        )
    }

    private fun buildRiskSummary(
        location: DeviceLocation,
        risk: com.geotrust.farmer.risk.DeviceRiskSnapshot,
    ): String {
        return buildString {
            append("mock定位: ")
            append(if (location.isMock) "是" else "否")
            append(" | 模拟器: ")
            append(if (risk.isEmulator) "是" else "否")
            append(" | 调试器: ")
            append(if (risk.isDebugger) "是" else "否")
            append(" | 开发者选项: ")
            append(if (risk.devOptionsEnabled) "开" else "关")
        }
    }

    private fun androidIdHash(): String {
        val androidId = Settings.Secure.getString(
            appContext.contentResolver,
            Settings.Secure.ANDROID_ID,
        ) ?: "unknown"
        val digest = MessageDigest.getInstance("SHA-256")
        return digest.digest(androidId.toByteArray())
            .joinToString("") { byte -> "%02x".format(byte) }
    }

    class Factory(
        private val appContext: Context,
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return RegisterViewModel(
                appContext = appContext,
                repository = MobileRegisterRepository(NetworkModule.mobileApiService),
                locationProvider = LocationProvider(appContext),
                deviceRiskCollector = DeviceRiskCollector(appContext),
            ) as T
        }
    }
}
