package com.geotrust.farmer.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColors = lightColorScheme(
    primary = MossGreen,
    secondary = ClayBrown,
    tertiary = TeaLeaf,
    background = RicePaper,
    surface = WarmWhite,
    surfaceVariant = Mist,
    onPrimary = WarmWhite,
    onSecondary = WarmWhite,
    onBackground = ForestInk,
    onSurface = ForestInk,
    onSurfaceVariant = DeepForest,
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
