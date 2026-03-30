package com.geotrust.farmer.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.geotrust.farmer.data.model.RegionDto

@Composable
fun RegisterScreen(
    viewModel: RegisterViewModel,
    locationPermissionGranted: Boolean,
    onRequestLocationPermission: () -> Unit,
) {
    val state by viewModel.uiState.collectAsState()

    Scaffold { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(
                text = "Geo-Trust 农户登记端",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "只覆盖安卓登记链路：拉产区、定位校验、提交登记。",
                style = MaterialTheme.typography.bodyMedium,
            )

            if (!locationPermissionGranted) {
                Button(onClick = onRequestLocationPermission) {
                    Text("申请定位权限")
                }
            }

            state.bootstrapError?.let { error ->
                StatusCard(title = "初始化失败", content = error)
            }

            RegionSelector(
                selectedRegionId = state.selectedRegionId,
                regions = state.regions,
                onRegionSelected = viewModel::updateSelectedRegionId,
            )

            OutlinedTextField(
                value = state.productName,
                onValueChange = viewModel::updateProductName,
                modifier = Modifier.fillMaxWidth(),
                label = { Text("商品名称") },
                singleLine = true,
            )
            OutlinedTextField(
                value = state.batchNo,
                onValueChange = viewModel::updateBatchNo,
                modifier = Modifier.fillMaxWidth(),
                label = { Text("批次号") },
                singleLine = true,
            )
            OutlinedTextField(
                value = state.producerName,
                onValueChange = viewModel::updateProducerName,
                modifier = Modifier.fillMaxWidth(),
                label = { Text("生产者名称") },
                singleLine = true,
            )

            StatusCard(title = "定位状态", content = state.locationSummary)
            StatusCard(title = "设备环境", content = state.riskSummary)

            state.validationMessage?.let { message ->
                StatusCard(title = "校验结果", content = message)
            }

            state.registrationResult?.let { result ->
                val detail = buildString {
                    appendLine(result.message)
                    result.product_code?.let { appendLine("商品编号: $it") }
                    result.token?.let { appendLine("Token: $it") }
                    result.trace_url?.let { appendLine("追溯链接: $it") }
                    result.qr_code_url?.let { appendLine("二维码地址: $it") }
                }
                StatusCard(title = "登记结果", content = detail.trim())
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Button(
                    onClick = viewModel::validateCurrentLocation,
                    enabled = !state.isLoading && locationPermissionGranted,
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
                ) {
                    Text("校验当前位置")
                }
                Button(
                    onClick = viewModel::registerProduct,
                    enabled = !state.isLoading && locationPermissionGranted,
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
                ) {
                    Text("提交登记")
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
            trailingIcon = {
                ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded)
            },
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
private fun StatusCard(
    title: String,
    content: String,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
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
