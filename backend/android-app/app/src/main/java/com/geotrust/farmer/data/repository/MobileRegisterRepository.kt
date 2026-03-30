package com.geotrust.farmer.data.repository

import com.geotrust.farmer.data.model.BootstrapResponse
import com.geotrust.farmer.data.model.RegisterProductRequestDto
import com.geotrust.farmer.data.model.RegisterProductResponse
import com.geotrust.farmer.data.model.ValidateLocationRequestDto
import com.geotrust.farmer.data.model.ValidateLocationResponse
import com.geotrust.farmer.data.network.MobileApiService

class MobileRegisterRepository(
    private val api: MobileApiService,
) {
    suspend fun getBootstrap(): BootstrapResponse = api.getBootstrap()

    suspend fun validateLocation(request: ValidateLocationRequestDto): ValidateLocationResponse =
        api.validateLocation(request)

    suspend fun registerProduct(request: RegisterProductRequestDto): RegisterProductResponse =
        api.registerProduct(request)
}
