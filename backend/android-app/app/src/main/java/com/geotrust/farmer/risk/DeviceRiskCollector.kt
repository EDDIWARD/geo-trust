package com.geotrust.farmer.risk

import android.content.Context
import android.os.Build
import android.os.Debug
import android.provider.Settings

data class DeviceRiskSnapshot(
    val isEmulator: Boolean,
    val isDebugger: Boolean,
    val devOptionsEnabled: Boolean,
)

class DeviceRiskCollector(
    private val context: Context,
) {
    fun collect(): DeviceRiskSnapshot {
        return DeviceRiskSnapshot(
            isEmulator = isProbablyEmulator(),
            isDebugger = Debug.isDebuggerConnected(),
            devOptionsEnabled = isDeveloperOptionsEnabled(),
        )
    }

    private fun isDeveloperOptionsEnabled(): Boolean {
        return Settings.Global.getInt(
            context.contentResolver,
            Settings.Global.DEVELOPMENT_SETTINGS_ENABLED,
            0,
        ) == 1
    }

    private fun isProbablyEmulator(): Boolean {
        val fingerprint = Build.FINGERPRINT.lowercase()
        val model = Build.MODEL.lowercase()
        val product = Build.PRODUCT.lowercase()
        return fingerprint.contains("generic")
            || fingerprint.contains("emulator")
            || model.contains("sdk")
            || product.contains("sdk")
    }
}
