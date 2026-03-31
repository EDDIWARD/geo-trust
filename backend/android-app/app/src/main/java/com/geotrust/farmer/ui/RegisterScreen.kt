package com.geotrust.farmer.ui

import android.net.Uri
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.LocationOn
import androidx.compose.material.icons.outlined.QrCode2
import androidx.compose.material.icons.outlined.Security
import androidx.compose.material.icons.outlined.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import coil.compose.AsyncImage
import com.geotrust.farmer.BuildConfig
import com.geotrust.farmer.data.model.RegionDto
import com.geotrust.farmer.ui.theme.ClayBrown
import com.geotrust.farmer.ui.theme.DangerRed
import com.geotrust.farmer.ui.theme.DeepForest
import com.geotrust.farmer.ui.theme.Mist
import com.geotrust.farmer.ui.theme.MossGreen
import com.geotrust.farmer.ui.theme.RicePaper
import com.geotrust.farmer.ui.theme.SkyTint
import com.geotrust.farmer.ui.theme.SuccessGreen
import com.geotrust.farmer.ui.theme.WarningAmber
import com.geotrust.farmer.ui.theme.WarmWhite

@Composable
fun RegisterScreen(
    viewModel: RegisterViewModel,
    locationPermissionGranted: Boolean,
    onRequestLocationPermission: () -> Unit,
) {
    val state by viewModel.uiState.collectAsState()
    val selectedRegion = state.regions.firstOrNull { it.id == state.selectedRegionId }
    val canInteract = !state.isLoading &&
        locationPermissionGranted &&
        state.bootstrapLoaded &&
        state.registerEnabled
    val canSubmitRegister = canInteract && state.registrationResult?.accepted != true
    var showQrDialog by rememberSaveable { mutableStateOf(false) }
    val registrationResult = state.registrationResult
    val showGeneratingCard = state.isGeneratingQr && registrationResult == null
    val resolvedQrCodeUrl = remember(registrationResult?.qr_code_url) {
        resolveBackendUrl(registrationResult?.qr_code_url)
    }

    Scaffold(containerColor = Color.Transparent) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    brush = Brush.verticalGradient(
                        colors = listOf(WarmWhite, RicePaper, SkyTint),
                    ),
                ),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 16.dp, vertical = 20.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                HeroCard(
                    title = state.appName,
                    registerEnabled = state.registerEnabled,
                    locationPermissionGranted = locationPermissionGranted,
                    selectedRegion = selectedRegion,
                )

                StepStrip()

                if (state.isLoading) {
                    LinearProgressIndicator(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(999.dp)),
                    )
                }

                if (!locationPermissionGranted) {
                    MessageCard(
                        title = "需要定位权限",
                        content = "登记前必须获取当前位置，系统会用它完成产区围栏校验。",
                        tone = MessageTone.Warning,
                        actionLabel = "申请定位权限",
                        onAction = onRequestLocationPermission,
                    )
                }

                state.bootstrapError?.let { error ->
                    MessageCard(
                        title = "初始化失败",
                        content = error,
                        tone = MessageTone.Danger,
                    )
                }

                FormCard(
                    state = state,
                    onRegionSelected = viewModel::updateSelectedRegionId,
                    onProductNameChanged = viewModel::updateProductName,
                    onBatchNoChanged = viewModel::updateBatchNo,
                    onProducerNameChanged = viewModel::updateProducerName,
                )

                StatusCard(
                    title = "定位状态",
                    content = state.locationSummary,
                    icon = Icons.Outlined.LocationOn,
                    tone = MessageTone.Info,
                )
                StatusCard(
                    title = "设备环境",
                    content = state.riskSummary,
                    icon = Icons.Outlined.Security,
                    tone = MessageTone.Info,
                )

                state.validationMessage?.let { message ->
                    val passed = state.validationResult?.valid == true
                    StatusCard(
                        title = if (passed) "校验通过" else "校验结果",
                        content = message,
                        icon = if (passed) Icons.Outlined.CheckCircle else Icons.Outlined.Warning,
                        tone = if (passed) MessageTone.Success else MessageTone.Warning,
                    )
                }

                AnimatedVisibility(
                    visible = showGeneratingCard,
                    enter = fadeIn() + slideInVertically(initialOffsetY = { it / 4 }) + expandVertically(),
                    exit = fadeOut() + shrinkVertically(),
                ) {
                    QrGeneratingCard()
                }

                AnimatedVisibility(
                    visible = registrationResult != null,
                    enter = fadeIn() + slideInVertically(initialOffsetY = { it / 3 }) + expandVertically(),
                    exit = fadeOut() + shrinkVertically(),
                ) {
                    registrationResult?.let { result ->
                        ResultCard(
                            accepted = result.accepted,
                            message = result.message,
                            qrCodeUrl = resolvedQrCodeUrl,
                            onOpenQrDialog = { showQrDialog = true },
                        )
                    }
                }

                ActionCard(
                    canInteract = canInteract,
                    canSubmitRegister = canSubmitRegister,
                    onValidate = viewModel::validateCurrentLocation,
                    onRegister = viewModel::registerProduct,
                )

                Text(
                    text = "演示环境：${BuildConfig.BASE_URL}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f),
                )
            }
        }
    }

    val qrCodeUrl = resolvedQrCodeUrl
    if (showQrDialog && qrCodeUrl != null) {
        QrPreviewDialog(
            qrCodeUrl = qrCodeUrl,
            onDismiss = { showQrDialog = false },
        )
    }
}

@Composable
private fun HeroCard(
    title: String,
    registerEnabled: Boolean,
    locationPermissionGranted: Boolean,
    selectedRegion: RegionDto?,
) {
    ElevatedCard(
        colors = CardDefaults.elevatedCardColors(containerColor = DeepForest),
        shape = RoundedCornerShape(28.dp),
        elevation = CardDefaults.elevatedCardElevation(defaultElevation = 8.dp),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(
                    brush = Brush.linearGradient(
                        colors = listOf(DeepForest, MossGreen, Color(0xFF4A5D3A)),
                    ),
                )
                .padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            StatusChip(
                label = "可信产地登记",
                tone = MessageTone.Info,
            )
            Text(
                text = title,
                style = MaterialTheme.typography.headlineMedium,
                color = WarmWhite,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = "可信登记闭环：启动拉取配置、定位围栏校验、提交登记、返回二维码。",
                style = MaterialTheme.typography.bodyMedium,
                color = WarmWhite.copy(alpha = 0.86f),
            )
            Row(
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                HeroMetric(
                    modifier = Modifier.weight(1f),
                    label = "登记状态",
                    value = if (registerEnabled) "开放" else "暂停",
                )
                HeroMetric(
                    modifier = Modifier.weight(1f),
                    label = "定位权限",
                    value = if (locationPermissionGranted) "已就绪" else "待授权",
                )
            }
            selectedRegion?.let {
                Surface(
                    color = WarmWhite.copy(alpha = 0.14f),
                    shape = RoundedCornerShape(18.dp),
                ) {
                    Column(
                        modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        Text(
                            text = "当前产区",
                            style = MaterialTheme.typography.labelLarge,
                            color = WarmWhite.copy(alpha = 0.72f),
                        )
                        Text(
                            text = it.name,
                            style = MaterialTheme.typography.titleMedium,
                            color = WarmWhite,
                        )
                        Text(
                            text = listOfNotNull(it.product_type, it.province, it.city).joinToString(" · "),
                            style = MaterialTheme.typography.bodySmall,
                            color = WarmWhite.copy(alpha = 0.82f),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun StepStrip() {
    ElevatedCard(
        colors = CardDefaults.elevatedCardColors(containerColor = WarmWhite),
        shape = RoundedCornerShape(22.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            StepBadge(modifier = Modifier.weight(1f), index = "01", title = "选择\n产区")
            StepBadge(modifier = Modifier.weight(1f), index = "02", title = "检验\n定位")
            StepBadge(modifier = Modifier.weight(1f), index = "03", title = "生成\n源码")
        }
    }
}

@Composable
private fun StepBadge(
    modifier: Modifier = Modifier,
    index: String,
    title: String,
) {
    Surface(
        modifier = modifier,
        color = RicePaper,
        shape = RoundedCornerShape(18.dp),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 14.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = index,
                style = MaterialTheme.typography.labelLarge,
                color = ClayBrown,
            )
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                color = DeepForest,
                maxLines = 2,
                textAlign = TextAlign.Center,
            )
        }
    }
}

@Composable
private fun HeroMetric(
    modifier: Modifier = Modifier,
    label: String,
    value: String,
) {
    Surface(
        modifier = modifier,
        color = WarmWhite.copy(alpha = 0.12f),
        shape = RoundedCornerShape(18.dp),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.labelLarge,
                color = WarmWhite.copy(alpha = 0.72f),
            )
            Text(
                text = value,
                style = MaterialTheme.typography.titleMedium,
                color = WarmWhite,
            )
        }
    }
}

@Composable
private fun FormCard(
    state: RegisterUiState,
    onRegionSelected: (Int) -> Unit,
    onProductNameChanged: (String) -> Unit,
    onBatchNoChanged: (String) -> Unit,
    onProducerNameChanged: (String) -> Unit,
) {
    ElevatedCard(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.elevatedCardColors(containerColor = WarmWhite),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Text(
                text = "登记信息",
                style = MaterialTheme.typography.titleLarge,
            )
            Text(
                text = "填写商品与生产者信息，系统会结合当前位置进行产地围栏校验。",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Surface(
                color = Color(0xFFFFFEFB),
                shape = RoundedCornerShape(26.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .border(
                        width = 1.dp,
                        color = Mist,
                        shape = RoundedCornerShape(26.dp),
                    ),
            ) {
                Column(
                    modifier = Modifier.padding(14.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    FieldPanel(
                        index = "01",
                        title = "产区选择",
                        hint = "先确定登记归属产区，后续定位会按这个范围校验。",
                    ) {
                        RegionSelector(
                            selectedRegionId = state.selectedRegionId,
                            regions = state.regions,
                            onRegionSelected = onRegionSelected,
                        )
                    }
                    FieldPanel(
                        index = "02",
                        title = "商品名称",
                        hint = "填写本次登记商品的标准名称。",
                    ) {
                        StyledInputField(
                            value = state.productName,
                            onValueChange = onProductNameChanged,
                            label = "商品名称",
                            placeholder = "例如：五常大米礼盒",
                        )
                    }
                    FieldPanel(
                        index = "03",
                        title = "批次号",
                        hint = "填写商品对应的生产或流转批次编号。",
                    ) {
                        StyledInputField(
                            value = state.batchNo,
                            onValueChange = onBatchNoChanged,
                            label = "批次号",
                            placeholder = "例如：2026-03-31-A01",
                        )
                    }
                    FieldPanel(
                        index = "04",
                        title = "生产者名称",
                        hint = "填写商品对应的生产主体名称。",
                    ) {
                        StyledInputField(
                            value = state.producerName,
                            onValueChange = onProducerNameChanged,
                            label = "生产者名称",
                            placeholder = "例如：张三合作社",
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ActionCard(
    canInteract: Boolean,
    canSubmitRegister: Boolean,
    onValidate: () -> Unit,
    onRegister: () -> Unit,
) {
    ElevatedCard(
        colors = CardDefaults.elevatedCardColors(containerColor = WarmWhite),
        shape = RoundedCornerShape(24.dp),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Text(
                text = "操作区",
                style = MaterialTheme.typography.titleLarge,
            )
            Text(
                text = "请先完成位置校验，再发起正式登记。",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Button(
                    onClick = onValidate,
                    enabled = canInteract,
                    modifier = Modifier.weight(1f),
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 14.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = ClayBrown,
                        contentColor = WarmWhite,
                    ),
                ) {
                    Text("校验当前位置")
                }
                Button(
                    onClick = onRegister,
                    enabled = canSubmitRegister,
                    modifier = Modifier.weight(1f),
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 14.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MossGreen,
                        contentColor = WarmWhite,
                    ),
                ) {
                    Text(if (canSubmitRegister) "提交登记" else "已完成登记")
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RegionSelector(
    selectedRegionId: Int?,
    regions: List<RegionDto>,
    onRegionSelected: (Int) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    val selectedRegion = regions.firstOrNull { it.id == selectedRegionId }

    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = !expanded },
    ) {
        OutlinedTextField(
            value = selectedRegion?.name ?: "",
            onValueChange = {},
            readOnly = true,
            modifier = Modifier
                .menuAnchor()
                .fillMaxWidth(),
            label = { Text("选择产区") },
            placeholder = { Text("请选择本次登记所属产区") },
            trailingIcon = {
                ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded)
            },
            colors = inputFieldColors(),
            shape = RoundedCornerShape(18.dp),
        )

        ExposedDropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
        ) {
            regions.forEach { region ->
                DropdownMenuItem(
                    text = { Text(region.name) },
                    onClick = {
                        expanded = false
                        onRegionSelected(region.id)
                    },
                )
            }
        }
    }
}

@Composable
private fun FieldPanel(
    index: String,
    title: String,
    hint: String,
    content: @Composable () -> Unit,
) {
    Surface(
        color = RicePaper,
        shape = RoundedCornerShape(22.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Surface(
                    color = ClayBrown,
                    shape = RoundedCornerShape(999.dp),
                ) {
                    Text(
                        text = index,
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                        style = MaterialTheme.typography.labelLarge,
                        color = WarmWhite,
                    )
                }
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.titleMedium,
                        color = DeepForest,
                    )
                    Text(
                        text = hint,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            content()
        }
    }
}

@Composable
private fun StyledInputField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    placeholder: String,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        modifier = Modifier.fillMaxWidth(),
        label = { Text(label) },
        placeholder = { Text(placeholder) },
        singleLine = true,
        shape = RoundedCornerShape(18.dp),
        colors = inputFieldColors(),
    )
}

@Composable
private fun inputFieldColors() = OutlinedTextFieldDefaults.colors(
    focusedContainerColor = WarmWhite,
    unfocusedContainerColor = RicePaper,
    disabledContainerColor = RicePaper,
    focusedBorderColor = MossGreen,
    unfocusedBorderColor = Mist,
    focusedLabelColor = MossGreen,
    unfocusedLabelColor = ClayBrown,
    cursorColor = MossGreen,
)

@Composable
private fun QrGeneratingCard() {
    ElevatedCard(
        colors = CardDefaults.elevatedCardColors(containerColor = WarmWhite),
        shape = RoundedCornerShape(26.dp),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 18.dp, vertical = 20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Box(
                modifier = Modifier
                    .size(72.dp)
                    .clip(CircleShape)
                    .background(SkyTint),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = Icons.Outlined.QrCode2,
                    contentDescription = null,
                    tint = DeepForest,
                    modifier = Modifier.size(32.dp),
                )
            }
            Text(
                text = "正在生成溯源码",
                style = MaterialTheme.typography.titleLarge,
                color = DeepForest,
            )
            Text(
                text = "系统正在生成本次登记对应的二维码，请稍候。",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            LinearProgressIndicator(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(999.dp)),
                color = MossGreen,
                trackColor = Mist,
            )
        }
    }
}

@Composable
private fun ResultCard(
    accepted: Boolean,
    message: String,
    qrCodeUrl: String?,
    onOpenQrDialog: () -> Unit,
) {
    var revealQr by remember(qrCodeUrl) { mutableStateOf(false) }
    val iconScale by animateFloatAsState(
        targetValue = if (accepted) 1f else 0.92f,
        animationSpec = tween(durationMillis = 450),
        label = "result-icon-scale",
    )

    LaunchedEffect(qrCodeUrl) {
        revealQr = qrCodeUrl != null
    }

    ElevatedCard(
        colors = CardDefaults.elevatedCardColors(
            containerColor = if (accepted) WarmWhite else Color(0xFFFFF6F4),
        ),
        shape = RoundedCornerShape(24.dp),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Box(
                    modifier = Modifier
                        .size(44.dp)
                        .scale(iconScale)
                        .clip(CircleShape)
                        .background(
                            if (accepted) {
                                SuccessGreen.copy(alpha = 0.12f)
                            } else {
                                DangerRed.copy(alpha = 0.12f)
                            },
                        ),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        imageVector = if (accepted) Icons.Outlined.QrCode2 else Icons.Outlined.Warning,
                        contentDescription = null,
                        tint = if (accepted) SuccessGreen else DangerRed,
                    )
                }
                Column {
                    Text(
                        text = if (accepted) "登记成功" else "登记被拒绝",
                        style = MaterialTheme.typography.titleLarge,
                    )
                    Text(
                        text = message,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }

            AnimatedVisibility(
                visible = accepted && revealQr && qrCodeUrl != null,
                enter = fadeIn() + scaleIn(initialScale = 0.82f),
                exit = fadeOut(),
            ) {
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(26.dp),
                        color = RicePaper,
                    ) {
                        Column(
                            modifier = Modifier.padding(14.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.spacedBy(10.dp),
                        ) {
                            Text(
                                text = "Geo-Trust 溯源码",
                                style = MaterialTheme.typography.titleMedium,
                                color = DeepForest,
                            )
                            Text(
                                text = "请扫码查看商品追溯信息",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Surface(
                                modifier = Modifier.clickable(onClick = onOpenQrDialog),
                                shape = RoundedCornerShape(24.dp),
                                color = Color.White,
                                shadowElevation = 4.dp,
                            ) {
                                AsyncImage(
                                    model = qrCodeUrl,
                                    contentDescription = "二维码",
                                    modifier = Modifier
                                        .size(220.dp)
                                        .padding(14.dp),
                                )
                            }
                            Text(
                                text = "点击二维码可放大查看",
                                style = MaterialTheme.typography.bodySmall,
                                color = ClayBrown,
                            )
                        }
                    }
                    Button(
                        onClick = onOpenQrDialog,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = DeepForest,
                            contentColor = WarmWhite,
                        ),
                    ) {
                        Text("放大查看二维码")
                    }
                }
            }
        }
    }
}

@Composable
private fun QrPreviewDialog(
    qrCodeUrl: String,
    onDismiss: () -> Unit,
) {
    Dialog(onDismissRequest = onDismiss) {
        Surface(
            shape = RoundedCornerShape(28.dp),
            color = WarmWhite,
            tonalElevation = 6.dp,
        ) {
            Column(
                modifier = Modifier.padding(20.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                Text(
                    text = "溯源码二维码",
                    style = MaterialTheme.typography.titleLarge,
                    color = DeepForest,
                )
                Text(
                    text = "扫码后进入对应商品的追溯入口。",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Surface(
                    color = Color.White,
                    shape = RoundedCornerShape(24.dp),
                    modifier = Modifier.border(
                        width = 1.dp,
                        color = Mist,
                        shape = RoundedCornerShape(24.dp),
                    ),
                ) {
                    AsyncImage(
                        model = qrCodeUrl,
                        contentDescription = "溯源码二维码大图",
                        modifier = Modifier
                            .size(300.dp)
                            .padding(18.dp),
                    )
                }
                Button(
                    onClick = onDismiss,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MossGreen,
                        contentColor = WarmWhite,
                    ),
                ) {
                    Text("关闭")
                }
            }
        }
    }
}

@Composable
private fun StatusCard(
    title: String,
    content: String,
    icon: ImageVector,
    tone: MessageTone,
) {
    ElevatedCard(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.elevatedCardColors(
            containerColor = when (tone) {
                MessageTone.Success -> Color(0xFFF3FAF2)
                MessageTone.Warning -> Color(0xFFFFF8EC)
                MessageTone.Danger -> Color(0xFFFFF3F1)
                MessageTone.Info -> WarmWhite
            },
        ),
        shape = RoundedCornerShape(22.dp),
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.Top,
        ) {
            Box(
                modifier = Modifier
                    .size(40.dp)
                    .clip(CircleShape)
                    .background(tone.color().copy(alpha = 0.12f)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = tone.color(),
                )
            }
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = content,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}

@Composable
private fun MessageCard(
    title: String,
    content: String,
    tone: MessageTone,
    actionLabel: String? = null,
    onAction: (() -> Unit)? = null,
) {
    ElevatedCard(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.elevatedCardColors(
            containerColor = when (tone) {
                MessageTone.Success -> Color(0xFFF3FAF2)
                MessageTone.Warning -> Color(0xFFFFF8EC)
                MessageTone.Danger -> Color(0xFFFFF3F1)
                MessageTone.Info -> WarmWhite
            },
        ),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleLarge,
            )
            Text(
                text = content,
                style = MaterialTheme.typography.bodyMedium,
            )
            if (actionLabel != null && onAction != null) {
                Button(onClick = onAction) {
                    Text(actionLabel)
                }
            }
        }
    }
}

@Composable
private fun StatusChip(
    label: String,
    tone: MessageTone,
) {
    Surface(
        color = tone.color().copy(alpha = 0.16f),
        shape = RoundedCornerShape(999.dp),
    ) {
        Text(
            text = label,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 7.dp),
            style = MaterialTheme.typography.labelLarge,
            color = tone.color(),
        )
    }
}

private enum class MessageTone {
    Success,
    Warning,
    Danger,
    Info,
}

private fun MessageTone.color(): Color {
    return when (this) {
        MessageTone.Success -> SuccessGreen
        MessageTone.Warning -> WarningAmber
        MessageTone.Danger -> DangerRed
        MessageTone.Info -> ClayBrown
    }
}

private fun resolveBackendUrl(rawUrl: String?): String? {
    if (rawUrl.isNullOrBlank()) {
        return null
    }

    val baseUrl = BuildConfig.BASE_URL.trimEnd('/')
    val baseUri = Uri.parse(baseUrl)
    val parsedUri = Uri.parse(rawUrl)

    if (parsedUri.scheme.isNullOrBlank()) {
        val normalizedPath = if (rawUrl.startsWith("/")) rawUrl else "/$rawUrl"
        return "$baseUrl$normalizedPath"
    }

    val host = parsedUri.host?.lowercase()
    if (host == "127.0.0.1" || host == "localhost" || host == "0.0.0.0") {
        return parsedUri.buildUpon()
            .scheme(baseUri.scheme)
            .encodedAuthority(baseUri.encodedAuthority)
            .build()
            .toString()
    }

    return rawUrl
}
