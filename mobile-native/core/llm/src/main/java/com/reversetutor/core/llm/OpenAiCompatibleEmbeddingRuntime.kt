package com.reversetutor.core.llm

import java.net.URI

/**
 * NEWMP-V1-024: OpenAI-compatible embeddings runtime.
 *
 * Calls the channel's `POST {baseUrl}/embeddings` endpoint (the same
 * OpenAI-compatible protocol the chat runtime uses) to turn source chunks and
 * user queries into float vectors for local cosine scoring. Failures are
 * non-fatal by contract: callers fall back to keyword retrieval, so every
 * failure mode here maps to a plain [EmbeddingCallResult.Failed] instead of an
 * exception.
 *
 * Batching: providers cap how many inputs one call accepts, so texts are
 * split into [BatchSize] chunks and the vectors are re-joined in input order.
 */
class OpenAiCompatibleEmbeddingRuntime(
    private val transport: ProviderHttpTransport,
    private val secretResolver: LlmSecretResolver,
    private val timeoutMillis: Int = DefaultEmbeddingTimeoutMillis
) {
    suspend fun embed(
        secretRef: String?,
        baseUrl: String?,
        model: String,
        texts: List<String>
    ): EmbeddingCallResult {
        if (texts.isEmpty()) return EmbeddingCallResult.Success(emptyList())
        val trimmedRef = secretRef?.trim().orEmpty()
        if (trimmedRef.isEmpty()) return EmbeddingCallResult.Failed
        val endpointBase = baseUrl?.trim()?.trimEnd('/').orEmpty()
        if (endpointBase.isEmpty()) return EmbeddingCallResult.Failed
        val endpoint = "$endpointBase/embeddings"
        if (!endpoint.isSafeHttpEndpoint()) return EmbeddingCallResult.Failed

        val secret = runCatching { secretResolver.resolve(trimmedRef) }
            .getOrNull()
            ?.takeIf { it.isNotBlank() }
            ?: return EmbeddingCallResult.Failed

        val vectors = mutableListOf<FloatArray>()
        texts.chunked(BatchSize).forEach { batch ->
            val request = ProviderHttpRequest(
                url = endpoint,
                headers = mapOf(
                    "Content-Type" to "application/json",
                    "Accept" to "application/json",
                    "Authorization" to "Bearer $secret"
                ),
                jsonBody = ProviderJson.stringify(
                    mapOf(
                        "model" to model,
                        "input" to batch,
                        "encoding_format" to "float"
                    )
                ),
                timeoutMillis = timeoutMillis,
                streaming = false
            )
            val result = runCatching { transport.execute(request) }.getOrNull()
                ?: return EmbeddingCallResult.Failed
            val response = result as? ProviderHttpResult.Response
                ?: return EmbeddingCallResult.Failed
            if (response.statusCode !in 200..299) return EmbeddingCallResult.Failed
            val batchVectors = parseEmbeddings(response.body, batch.size)
                ?: return EmbeddingCallResult.Failed
            if (batchVectors.size != batch.size) return EmbeddingCallResult.Failed
            vectors += batchVectors
        }
        return EmbeddingCallResult.Success(vectors.toList())
    }

    private fun parseEmbeddings(body: String, expectedCount: Int): List<FloatArray>? {
        val root = ProviderJson.parse(body) as? Map<*, *> ?: return null
        val data = root["data"] as? List<*> ?: return null
        val byIndex = mutableListOf<Pair<Int, FloatArray>?>()
        data.forEach { item ->
            val entry = item as? Map<*, *> ?: return null
            val index = (entry["index"] as? Number)?.toInt() ?: return null
            val raw = entry["embedding"] as? List<*> ?: return null
            val vector = FloatArray(raw.size) { position ->
                (raw[position] as? Number)?.toFloat() ?: return null
            }
            byIndex += index to vector
        }
        if (byIndex.size != expectedCount) return null
        return (0 until expectedCount).mapNotNull { wanted ->
            byIndex.firstOrNull { it?.first == wanted }?.second
        }.takeIf { it.size == expectedCount }
    }

    private fun String.isSafeHttpEndpoint(): Boolean {
        val uri = runCatching { URI(this) }.getOrNull() ?: return false
        return (uri.scheme == "http" || uri.scheme == "https") && !uri.host.isNullOrBlank()
    }

    private companion object {
        const val BatchSize = 10
        const val DefaultEmbeddingTimeoutMillis = 30_000
    }
}

/** Result of one embeddings call. [Failed] is intentionally coarse: callers only need "usable or not". */
sealed interface EmbeddingCallResult {
    data class Success(val vectors: List<FloatArray>) : EmbeddingCallResult
    data object Failed : EmbeddingCallResult
}
