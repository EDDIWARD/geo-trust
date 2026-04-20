package com.geotrust.farmer.ui

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.material.icons.outlined.Collections
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
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import coil.compose.AsyncImage
import com.geotrust.farmer.BuildConfig
import com.geotrust.farmer.data.model.RegionDto
import com.geotrust.farmer.data.model.SelectedImage
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
    val context = LocalContext.current
    val state by viewModel.uiState.collectAsState()
    val selectedRegion = state.regions.firstOrNull { it.id == state.selectedRegionId }
    val canInteract = !state.isLoading && locationPermissionGranted && state.bootstrapLoaded && state.registerEnabled
    val canSubmitRegister = canInteract && state.registrationResult?.accepted != true
    var showQrDialog by rememberSaveable { mutableStateOf(false) }
    val registrationResult = state.registrationResult
    val resolvedQrCodeUrl = remember(registrationResult?.qr_code_url) {
        resolveBackendUrl(registrationResult?.qr_code_url)
    }
    val imagePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.PickMultipleVisualMedia(maxItems = 4),
    ) { uris ->
        viewModel.updateSelectedImages(
            uris.map { uri ->
                SelectedImage(uri = uri, displayName = resolveDisplayName(context, uri))
            },
        )
    }

    Scaffold(containerColor = Color.Transparent) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Brush.verticalGradient(listOf(WarmWhite, RicePaper, SkyTint))),
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
                        content = "登记前需要获取当前位置，用于校验是否处于所选区域内。",
                        tone = MessageTone.Warning,
                        actionLabel = "授权定位",
                        onAction = onRequestLocationPermission,
                    )
                }

                state.bootstrapError?.let { error ->
                    MessageCard(
                        title = "基础配置加载失败",
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
                    onPickImages = {
                        imagePickerLauncher.launch(
                            PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly),
                        )
                    },
                )

                StatusCard(
                    title = "定位信息",
                    content = state.locationSummary,
                    icon = Icons.Outlined.LocationOn,
                    tone = MessageTone.Info,
                )
                StatusCard(
                    title = "设备风险",
                    content = state.riskSummary,
                    icon = Icons.Outlined.Security,
                    tone = MessageTone.Info,
                )

                state.validationMessage?.let { message ->
                    val passed = state.validationResult?.valid == true
                    StatusCard(
                        title = if (passed) "位置校验通过" else "位置校验结果",
                        content = message,
                        icon = if (passed) Icons.Outlined.CheckCircle else Icons.Outlined.Warning,
                        tone = if (passed) MessageTone.Success else MessageTone.Warning,
                    )
                }

                AnimatedVisibility(
                    visible = registrationResult != null,
                    enter = fadeIn(),
                    exit = fadeOut(),
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
                    text = "后端地址：${BuildConfig.BASE_URL}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f),
                )
            }
        }
    }

    if (showQrDialog && resolvedQrCodeUrl != null) {
        QrPreviewDialog(
            qrCodeUrl = resolvedQrCodeUrl,
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
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(Brush.linearGradient(listOf(DeepForest, MossGreen, Color(0xFF4A5D3A))))
                .padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            StatusChip(label = "安卓端可信登记", tone = MessageTone.Info)
            Text(
                text = title,
                style = MaterialTheme.typography.headlineMedium,
                color = WarmWhite,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = "登记后自动生成二维码，消费者扫码即可进入对应的消费端溯源页。",
                style = MaterialTheme.typography.bodyMedium,
                color = WarmWhite.copy(alpha = 0.86f),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                HeroMetric(
                    modifier = Modifier.weight(1f),
                    label = "登记服务",
                    value = if (registerEnabled) "已开启" else "已关闭",
                )
                HeroMetric(
                    modifier = Modifier.weight(1f),
                    label = "定位授权",
                    value = if (locationPermissionGranted) "已授权" else "未授权",
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
                        Text("当前区域", style = MaterialTheme.typography.labelLarge, color = WarmWhite.copy(alpha = 0.72f))
                        Text(it.name, style = MaterialTheme.typography.titleMedium, color = WarmWhite)
                        Text(
                            text = listOfNotNull(it.product_type, it.province, it.city).joinToString(" / "),
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
private fun HeroMetric(
    modifier: Modifier = Modifier,
    label: String,
    value: String,
) {
    Surface(modifier = modifier, color = WarmWhite.copy(alpha = 0.12f), shape = RoundedCornerShape(18.dp)) {
        Column(modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp)) {
            Text(label, style = MaterialTheme.typography.labelLarge, color = WarmWhite.copy(alpha = 0.72f))
            Text(value, style = MaterialTheme.typography.titleMedium, color = WarmWhite)
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
    onPickImages: () -> Unit,
) {
    ElevatedCard(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.elevatedCardColors(containerColor = WarmWhite),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Text("登记表单", style = MaterialTheme.typography.titleLarge)
            Text(
                text = "消费端只保留安卓端登记生成的数据，所以这里的内容会直接决定扫码页展示结果。",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Surface(
                color = Color(0xFFFFFEFB),
                shape = RoundedCornerShape(26.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .border(1.dp, Mist, RoundedCornerShape(26.dp)),
            ) {
                Column(
                    modifier = Modifier.padding(14.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    FieldPanel(index = "01", title = "区域选择", hint = "选择当前产品所属产区。") {
                        RegionSelector(
                            selectedRegionId = state.selectedRegionId,
                            regions = state.regions,
                            onRegionSelected = onRegionSelected,
                        )
                    }
                    FieldPanel(index = "02", title = "产品名称", hint = "扫码页会直接展示这个名称。") {
                        StyledInputField(
                            value = state.productName,
                            onValueChange = onProductNameChanged,
                            label = "产品名称",
                            placeholder = "例如：潜江小龙虾",
                        )
                    }
                    FieldPanel(index = "03", title = "批次号", hint = "用于区分同一产品的不同登记批次。") {
                        StyledInputField(
                            value = state.batchNo,
                            onValueChange = onBatchNoChanged,
                            label = "批次号",
                            placeholder = "例如：20260416-A01",
                        )
                    }
                    FieldPanel(index = "04", title = "生产主体", hint = "扫码页会展示该生产主体。") {
                        StyledInputField(
                            value = state.producerName,
                            onValueChange = onProducerNameChanged,
                            label = "生产主体",
                            placeholder = "例如：Geo-Trust 农户合作社",
                        )
                    }
                    FieldPanel(index = "05", title = "现场图片", hint = "至少上传 1 张安卓端实拍照片，消费端将直接展示。") {
                        PhotoPickerField(
                            images = state.selectedImages,
                            onPickImages = onPickImages,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun PhotoPickerField(
    images: List<SelectedImage>,
    onPickImages: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Button(
            onClick = onPickImages,
            colors = ButtonDefaults.buttonColors(containerColor = MossGreen, contentColor = WarmWhite),
        ) {
            Icon(Icons.Outlined.Collections, contentDescription = null, modifier = Modifier.size(18.dp))
            Text(" 选择照片")
        }
        if (images.isEmpty()) {
            Text(
                text = "未选择任何图片。",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        } else {
            images.forEach { image ->
                Surface(color = RicePaper, shape = RoundedCornerShape(14.dp)) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        AsyncImage(
                            model = image.uri,
                            contentDescription = image.displayName,
                            modifier = Modifier
                                .size(60.dp)
                                .clip(RoundedCornerShape(12.dp)),
                        )
                        Text(
                            text = image.displayName,
                            style = MaterialTheme.typography.bodyMedium,
                            color = DeepForest,
                        )
                    }
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

    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = !expanded }) {
        OutlinedTextField(
            value = selectedRegion?.name ?: "",
            onValueChange = {},
            readOnly = true,
            modifier = Modifier.menuAnchor().fillMaxWidth(),
            label = { Text("所属区域") },
            placeholder = { Text("请选择区域") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            colors = inputFieldColors(),
            shape = RoundedCornerShape(18.dp),
        )

        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
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
    Surface(color = RicePaper, shape = RoundedCornerShape(22.dp), modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                Surface(color = ClayBrown, shape = RoundedCornerShape(999.dp)) {
                    Text(
                        text = index,
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                        style = MaterialTheme.typography.labelLarge,
                        color = WarmWhite,
                    )
                }
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(title, style = MaterialTheme.typography.titleMedium, color = DeepForest)
                    Text(hint, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
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
private fun ResultCard(
    accepted: Boolean,
    message: String,
    qrCodeUrl: String?,
    onOpenQrDialog: () -> Unit,
) {
    ElevatedCard(
        colors = CardDefaults.elevatedCardColors(
            containerColor = if (accepted) WarmWhite else Color(0xFFFFF6F4),
        ),
        shape = RoundedCornerShape(24.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Box(
                    modifier = Modifier
                        .size(44.dp)
                        .clip(CircleShape)
                        .background(if (accepted) SuccessGreen.copy(alpha = 0.12f) else DangerRed.copy(alpha = 0.12f)),
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
                        text = if (accepted) "登记成功" else "登记失败",
                        style = MaterialTheme.typography.titleLarge,
                    )
                    Text(text = message, style = MaterialTheme.typography.bodyMedium)
                }
            }

            if (accepted && qrCodeUrl != null) {
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
                        Text("扫码进入消费端", style = MaterialTheme.typography.titleMedium, color = DeepForest)
                        Surface(
                            modifier = Modifier.clickable(onClick = onOpenQrDialog),
                            shape = RoundedCornerShape(24.dp),
                            color = Color.White,
                            shadowElevation = 4.dp,
                        ) {
                            AsyncImage(
                                model = qrCodeUrl,
                                contentDescription = "二维码",
                                modifier = Modifier.size(220.dp).padding(14.dp),
                            )
                        }
                        Text(
                            text = "二维码对应 `/trace/{token}` 页面",
                            style = MaterialTheme.typography.bodySmall,
                            color = ClayBrown,
                        )
                    }
                }
                Button(
                    onClick = onOpenQrDialog,
                    colors = ButtonDefaults.buttonColors(containerColor = DeepForest, contentColor = WarmWhite),
                ) {
                    Text("放大查看二维码")
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
        Surface(shape = RoundedCornerShape(28.dp), color = WarmWhite, tonalElevation = 6.dp) {
            Column(
                modifier = Modifier.padding(20.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                Text("二维码预览", style = MaterialTheme.typography.titleLarge, color = DeepForest)
                Surface(
                    color = Color.White,
                    shape = RoundedCornerShape(24.dp),
                    modifier = Modifier.border(1.dp, Mist, RoundedCornerShape(24.dp)),
                ) {
                    AsyncImage(
                        model = qrCodeUrl,
                        contentDescription = "二维码预览",
                        modifier = Modifier.size(300.dp).padding(18.dp),
                    )
                }
                Button(
                    onClick = onDismiss,
                    colors = ButtonDefaults.buttonColors(containerColor = MossGreen, contentColor = WarmWhite),
                ) {
                    Text("关闭")
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
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.elevatedCardColors(containerColor = WarmWhite),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Button(
                onClick = onValidate,
                enabled = canInteract,
                modifier = Modifier.weight(1f),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 14.dp),
                colors = ButtonDefaults.buttonColors(containerColor = ClayBrown, contentColor = WarmWhite),
            ) {
                Text("位置校验")
            }
            Button(
                onClick = onRegister,
                enabled = canSubmitRegister,
                modifier = Modifier.weight(1f),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 14.dp),
                colors = ButtonDefaults.buttonColors(containerColor = MossGreen, contentColor = WarmWhite),
            ) {
                Text("提交登记")
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
                Icon(icon, contentDescription = null, tint = tone.color())
            }
            Column(modifier = Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(content, style = MaterialTheme.typography.bodyMedium)
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
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(title, style = MaterialTheme.typography.titleLarge)
            Text(content, style = MaterialTheme.typography.bodyMedium)
            if (actionLabel != null && onAction != null) {
                Button(onClick = onAction) { Text(actionLabel) }
            }
        }
    }
}

@Composable
private fun StatusChip(
    label: String,
    tone: MessageTone,
) {
    Surface(color = tone.color().copy(alpha = 0.16f), shape = RoundedCornerShape(999.dp)) {
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
    if (rawUrl.isNullOrBlank()) return null

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

private fun resolveDisplayName(context: Context, uri: Uri): String {
    val resolver = context.contentResolver
    resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
        val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
        if (nameIndex >= 0 && cursor.moveToFirst()) {
            return cursor.getString(nameIndex) ?: "现场照片"
        }
    }
    return uri.lastPathSegment ?: "现场照片"
}
