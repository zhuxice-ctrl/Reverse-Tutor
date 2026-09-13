package com.reversetutor.core.llm

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * NEWMP-V1-024: OpenAI-compatible embeddings runtime contracts.
 *
 * Pins: request shape (URL, auth header, batching), response parsing with
 * reorder-by-index, and every failure mode degrading to
 * [EmbeddingCallResult.Failed] instead of an exception.
 */
class OpenAiCompatibleEmbeddingRuntimeTest {

    private class RecordingTransport(vararg responses: ProviderHttpResult) : ProviderHttpTransport {
        val requests = mutableListOf<ProviderHttpRequest>()
        private val queue = responses.toMutableList()
        override suspend fun execute(request: ProviderHttpRequest): ProviderHttpResult {
            requests += request
            return queue.removeFirstOrNull() ?: ProviderHttpResult.Failure
        }
    }

    private val resolver = LlmSecretResolver { "secret-1" }

    private fun body(vectors: List<List<Float>>, indices: List<Int>): String {
        val data = vectors.indices.joinToString(",") { i ->
            val vec = vectors[i].joinToString(",", prefix = "[", postfix = "]")
            "{\"index\":${indices[i]},\"embedding\":$vec}"
        }
        return "{\"data\":[$data]}"
    }

    @Test
    fun successReturnsVectorsInInputOrder() = runBlocking {
        // Response deliberately lists index 1 before index 0.
        val transport = RecordingTransport(
            ProviderHttpResult.Response(
                200,
                body(listOf(listOf(0.5f), listOf(0.25f)), listOf(1, 0))
            )
        )
        val runtime = OpenAiCompatibleEmbeddingRuntime(transport, resolver)

        val result = runtime.embed(
            secretRef = "ref-1",
            baseUrl = "https://api.example.com/v1",
            model = "text-embedding-v3",
            texts = listOf("a", "b")
        )

        val vectors = (result as EmbeddingCallResult.Success).vectors
        assertEquals(2, vectors.size)
        assertEquals(0.25f, vectors[0][0], 0.0001f)
        assertEquals(0.5f, vectors[1][0], 0.0001f)
        assertEquals(1, transport.requests.size)
        val request = transport.requests.single()
        assertTrue(request.url.endsWith("/embeddings"))
        assertEquals("Bearer secret-1", request.headers["Authorization"])
        assertTrue(request.jsonBody.contains("\"model\":\"text-embedding-v3\""))
        assertTrue(request.jsonBody.contains("\"encoding_format\":\"float\""))
    }

    @Test
    fun batchesRequestsBeyondTenTexts() = runBlocking {
        val transport = RecordingTransport(
            ProviderHttpResult.Response(
                200,
                body((0 until 10).map { listOf(it.toFloat()) }, (0 until 10).toList())
            ),
            ProviderHttpResult.Response(200, body(listOf(listOf(10f)), listOf(0)))
        )
        val runtime = OpenAiCompatibleEmbeddingRuntime(transport, resolver)

        val result = runtime.embed("ref-1", "https://api.example.com/v1", "m", (0..10).map { "t$it" })

        val vectors = (result as EmbeddingCallResult.Success).vectors
        assertEquals(11, vectors.size)
        assertEquals(2, transport.requests.size)
    }

    @Test
    fun nonSuccessStatusFails() = runBlocking {
        val transport = RecordingTransport(ProviderHttpResult.Response(401, "{}"))
        val runtime = OpenAiCompatibleEmbeddingRuntime(transport, resolver)

        val result = runtime.embed("ref-1", "https://api.example.com/v1", "m", listOf("a"))

        assertTrue(result is EmbeddingCallResult.Failed)
    }

    @Test
    fun timeoutFails() = runBlocking {
        val transport = RecordingTransport(ProviderHttpResult.Timeout)
        val runtime = OpenAiCompatibleEmbeddingRuntime(transport, resolver)

        val result = runtime.embed("ref-1", "https://api.example.com/v1", "m", listOf("a"))

        assertTrue(result is EmbeddingCallResult.Failed)
    }

    @Test
    fun blankSecretRefFailsWithoutARequest() = runBlocking {
        val transport = RecordingTransport()
        val runtime = OpenAiCompatibleEmbeddingRuntime(transport, resolver)

        val result = runtime.embed("", "https://api.example.com/v1", "m", listOf("a"))

        assertTrue(result is EmbeddingCallResult.Failed)
        assertTrue(transport.requests.isEmpty())
    }

    @Test
    fun blankBaseUrlFailsWithoutARequest() = runBlocking {
        val transport = RecordingTransport()
        val runtime = OpenAiCompatibleEmbeddingRuntime(transport, resolver)

        val result = runtime.embed("ref-1", "  ", "m", listOf("a"))

        assertTrue(result is EmbeddingCallResult.Failed)
        assertTrue(transport.requests.isEmpty())
    }

    @Test
    fun unsafeEndpointFails() = runBlocking {
        val transport = RecordingTransport()
        val runtime = OpenAiCompatibleEmbeddingRuntime(transport, resolver)

        val result = runtime.embed("ref-1", "file:///etc/passwd", "m", listOf("a"))

        assertTrue(result is EmbeddingCallResult.Failed)
        assertTrue(transport.requests.isEmpty())
    }

    @Test
    fun emptyTextsSucceedWithoutARequest() = runBlocking {
        val transport = RecordingTransport()
        val runtime = OpenAiCompatibleEmbeddingRuntime(transport, resolver)

        val result = runtime.embed("ref-1", "https://api.example.com/v1", "m", emptyList())

        assertTrue(result is EmbeddingCallResult.Success)
        assertTrue((result as EmbeddingCallResult.Success).vectors.isEmpty())
        assertTrue(transport.requests.isEmpty())
    }

    @Test
    fun countMismatchFails() = runBlocking {
        val transport = RecordingTransport(
            ProviderHttpResult.Response(200, body(listOf(listOf(1f)), listOf(0)))
        )
        val runtime = OpenAiCompatibleEmbeddingRuntime(transport, resolver)

        val result = runtime.embed("ref-1", "https://api.example.com/v1", "m", listOf("a", "b"))

        assertTrue(result is EmbeddingCallResult.Failed)
    }
}
