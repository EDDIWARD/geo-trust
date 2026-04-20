package com.geotrust.farmer.data.repository

import android.content.Context
import android.net.Uri
import com.geotrust.farmer.data.model.BootstrapResponse
import com.geotrust.farmer.data.model.RegisterProductRequestDto
import com.geotrust.farmer.data.model.RegisterProductResponse
import com.geotrust.farmer.data.model.ValidateLocationRequestDto
import com.geotrust.farmer.data.model.ValidateLocationResponse
import com.geotrust.farmer.data.network.MobileApiService
import com.google.gson.Gson
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File

class MobileRegisterRepository(
    private val api: MobileApiService,
) {
    suspend fun getBootstrap(): BootstrapResponse = api.getBootstrap()

    suspend fun validateLocation(request: ValidateLocationRequestDto): ValidateLocationResponse =
        api.validateLocation(request)

    suspend fun registerProduct(request: RegisterProductRequestDto): RegisterProductResponse =
        api.registerProduct(request)

    suspend fun registerProductWithImages(
        context: Context,
        request: RegisterProductRequestDto,
        imageUris: List<Uri>,
    ): RegisterProductResponse {
        if (imageUris.isEmpty()) {
            return registerProduct(request)
        }

        val payloadBody = Gson()
            .toJson(request)
            .toRequestBody("application/json; charset=utf-8".toMediaType())

        val imageParts = imageUris.mapIndexedNotNull { index, uri ->
            createImagePart(context, uri, index)
        }

        if (imageParts.isEmpty()) {
            return registerProduct(request)
        }

        return api.registerProductWithImages(payloadBody, imageParts)
    }

    private fun createImagePart(
        context: Context,
        uri: Uri,
        index: Int,
    ): MultipartBody.Part? {
        val resolver = context.contentResolver
        val inputStream = resolver.openInputStream(uri) ?: return null
        val mimeType = resolver.getType(uri) ?: "image/jpeg"
        val suffix = when (mimeType.lowercase()) {
            "image/png" -> ".png"
            "image/webp" -> ".webp"
            else -> ".jpg"
        }
        val tempFile = File.createTempFile("upload_${index}_", suffix, context.cacheDir)
        inputStream.use { input -> tempFile.outputStream().use(input::copyTo) }
        val requestBody = tempFile.asRequestBody(mimeType.toMediaType())
        return MultipartBody.Part.createFormData(
            name = "images",
            filename = tempFile.name,
            body = requestBody,
        )
    }
}
