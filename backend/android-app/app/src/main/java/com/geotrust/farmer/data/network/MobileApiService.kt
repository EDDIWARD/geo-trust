package com.geotrust.farmer.data.network

import com.geotrust.farmer.data.model.BootstrapResponse
import com.geotrust.farmer.data.model.RegisterProductRequestDto
import com.geotrust.farmer.data.model.RegisterProductResponse
import com.geotrust.farmer.data.model.ValidateLocationRequestDto
import com.geotrust.farmer.data.model.ValidateLocationResponse
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part

interface MobileApiService {
    @GET("api/mobile/bootstrap")
    suspend fun getBootstrap(): BootstrapResponse

    @POST("api/mobile/validate-location")
    suspend fun validateLocation(
        @Body request: ValidateLocationRequestDto,
    ): ValidateLocationResponse

    @POST("api/mobile/register-product")
    suspend fun registerProduct(
        @Body request: RegisterProductRequestDto,
    ): RegisterProductResponse

    @Multipart
    @POST("api/mobile/register-product-with-images")
    suspend fun registerProductWithImages(
        @Part("payload") payload: RequestBody,
        @Part images: List<MultipartBody.Part>,
    ): RegisterProductResponse
}
