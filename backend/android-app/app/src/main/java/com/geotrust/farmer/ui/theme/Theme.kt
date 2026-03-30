package com.geotrust.farmer.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColors = lightColorScheme(
    primary = SageGreen,
    secondary = EarthBrown,
    background = RicePaper,
    surface = RicePaper,
    onPrimary = RicePaper,
    onSecondary = RicePaper,
    onBackground = ForestInk,
    onSurface = ForestInk,
)

@Composable
fun GeoTrustTheme(
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = LightColors,
        typography = Typography,
        content = content,
    )
}
