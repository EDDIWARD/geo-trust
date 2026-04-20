package com.geotrust.farmer.risk

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Debug
import android.provider.Settings
import java.io.File

data class DeviceRiskSnapshot(
    val isEmulator: Boolean,
    val isDebugger: Boolean,
    val isRooted: Boolean,
    val devOptionsEnabled: Boolean,
)

class DeviceRiskCollector(
    private val context: Context,
) {
    fun collect(): DeviceRiskSnapshot {
        return DeviceRiskSnapshot(
            isEmulator = isProbablyEmulator(),
            isDebugger = Debug.isDebuggerConnected(),
            isRooted = isProbablyRooted(),
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

    private fun isProbablyRooted(): Boolean {
        return hasTestKeys() || hasSuBinary() || hasKnownRootPackages()
    }

    private fun hasTestKeys(): Boolean {
        return Build.TAGS?.contains("test-keys") == true
    }

    private fun hasSuBinary(): Boolean {
        val candidates = listOf(
            "/system/bin/su",
            "/system/xbin/su",
            "/sbin/su",
            "/system/sd/xbin/su",
            "/system/bin/failsafe/su",
            "/data/local/xbin/su",
            "/data/local/bin/su",
            "/data/local/su",
            "/su/bin/su",
            "/system/app/Superuser.apk",
        )
        return candidates.any { path -> File(path).exists() }
    }

    private fun hasKnownRootPackages(): Boolean {
        val packageManager = context.packageManager
        val knownPackages = listOf(
            "com.topjohnwu.magisk",
            "eu.chainfire.supersu",
            "com.koushikdutta.superuser",
            "com.thirdparty.superuser",
        )
        return knownPackages.any { packageName ->
            isPackageInstalled(packageManager, packageName)
        }
    }

    private fun isPackageInstalled(
        packageManager: PackageManager,
        packageName: String,
    ): Boolean {
        return try {
            packageManager.getPackageInfo(packageName, 0)
            true
        } catch (_: Exception) {
            false
        }
    }
}
