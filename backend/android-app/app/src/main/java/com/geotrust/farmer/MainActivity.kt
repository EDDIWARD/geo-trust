package com.geotrust.farmer

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import com.geotrust.farmer.ui.RegisterScreen
import com.geotrust.farmer.ui.RegisterViewModel
import com.geotrust.farmer.ui.theme.GeoTrustTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            GeoTrustTheme {
                val registerViewModel = viewModel<RegisterViewModel>(
                    factory = RegisterViewModel.Factory(applicationContext),
                )
                var locationPermissionGranted by remember {
                    mutableStateOf(
                        ContextCompat.checkSelfPermission(
                            applicationContext,
                            Manifest.permission.ACCESS_FINE_LOCATION,
                        ) == PackageManager.PERMISSION_GRANTED,
                    )
                }
                val permissionLauncher = rememberLauncherForActivityResult(
                    contract = ActivityResultContracts.RequestPermission(),
                ) { granted ->
                    locationPermissionGranted = granted
                    registerViewModel.onLocationPermissionChanged(granted)
                }

                LaunchedEffect(Unit) {
                    registerViewModel.loadBootstrap()
                    registerViewModel.onLocationPermissionChanged(locationPermissionGranted)
                }

                RegisterScreen(
                    viewModel = registerViewModel,
                    locationPermissionGranted = locationPermissionGranted,
                    onRequestLocationPermission = {
                        permissionLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
                    },
                )
            }
        }
    }
}
