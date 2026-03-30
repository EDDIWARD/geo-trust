package com.geotrust.farmer.location

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Build
import android.os.CancellationSignal
import android.os.Looper
import androidx.core.content.ContextCompat
import androidx.core.location.LocationCompat
import java.time.Instant
import kotlin.coroutines.resume
import kotlinx.coroutines.suspendCancellableCoroutine

data class DeviceLocation(
    val lng: Double,
    val lat: Double,
    val accuracy: Float?,
    val provider: String?,
    val fixTime: String,
    val isMock: Boolean,
)

class LocationProvider(
    private val context: Context,
) {
    @SuppressLint("MissingPermission")
    suspend fun getCurrentLocation(): Result<DeviceLocation> {
        val hasFinePermission = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_FINE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED
        if (!hasFinePermission) {
            return Result.failure(IllegalStateException("缺少定位权限"))
        }

        val locationManager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        val provider = resolveProvider(locationManager)
            ?: return Result.failure(IllegalStateException("设备未开启定位服务"))
        val gpsLocation = locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER)
        val networkLocation = locationManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
        val chosen = listOfNotNull(gpsLocation, networkLocation).maxByOrNull { it.time }

        if (chosen != null && System.currentTimeMillis() - chosen.time <= FRESH_LOCATION_WINDOW_MS) {
            return Result.success(chosen.toDeviceLocation())
        }

        val currentLocation = requestCurrentLocation(locationManager, provider)
        if (currentLocation != null) {
            return Result.success(currentLocation.toDeviceLocation())
        }

        if (chosen != null) {
            return Result.success(chosen.toDeviceLocation())
        }

        return Result.failure(IllegalStateException("暂未获取到定位，请稍后重试"))
    }

    private fun resolveProvider(locationManager: LocationManager): String? {
        return when {
            locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER) -> LocationManager.GPS_PROVIDER
            locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER) -> LocationManager.NETWORK_PROVIDER
            else -> null
        }
    }

    @SuppressLint("MissingPermission")
    private suspend fun requestCurrentLocation(
        locationManager: LocationManager,
        provider: String,
    ): Location? = suspendCancellableCoroutine { continuation ->
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val cancellationSignal = CancellationSignal()
            continuation.invokeOnCancellation { cancellationSignal.cancel() }
            locationManager.getCurrentLocation(
                provider,
                cancellationSignal,
                context.mainExecutor,
            ) { location ->
                continuation.resume(location)
            }
        } else {
            val listener = object : LocationListener {
                override fun onLocationChanged(location: Location) {
                    locationManager.removeUpdates(this)
                    continuation.resume(location)
                }

                @Deprecated("Deprecated in Java")
                override fun onProviderDisabled(provider: String) {
                    locationManager.removeUpdates(this)
                    if (continuation.isActive) {
                        continuation.resume(null)
                    }
                }
            }
            continuation.invokeOnCancellation { locationManager.removeUpdates(listener) }
            locationManager.requestSingleUpdate(provider, listener, Looper.getMainLooper())
        }
    }

    private fun Location.toDeviceLocation(): DeviceLocation {
        return DeviceLocation(
            lng = longitude,
            lat = latitude,
            accuracy = accuracy,
            provider = provider,
            fixTime = Instant.ofEpochMilli(time).toString(),
            isMock = LocationCompat.isMock(this),
        )
    }

    private companion object {
        const val FRESH_LOCATION_WINDOW_MS = 2 * 60 * 1000L
    }
}
