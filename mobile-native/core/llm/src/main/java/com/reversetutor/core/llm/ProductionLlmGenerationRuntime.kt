package com.reversetutor.core.llm

import com.reversetutor.core.model.LlmProviderKind
import java.net.URI

class CompositeLlmGenerationRuntime(
    private val openAiCompatible: LlmGenerationRuntime,
    private val anthropicCompatible: LlmGenerationRuntime,
    private val geminiNative: LlmGenerationRuntime
) : LlmGenerationRuntime {
    override suspend fun generate(request: LlmGenerationRequest): LlmGenerationResult =
        when (request.provider.toProviderProtocol()) {
            LlmProviderProtocol.OpenAiCompatible -> openAiCompatible.generate(request)
            LlmProviderProtocol.AnthropicCompatible -> anthropicCompatible.generate(request)
            LlmProviderProtocol.GeminiNative -> geminiNative.generate(request)
        }

    companion object {
        fun production(
            transport: ProviderHttpTransport,
            secretResolver: LlmSecretResolver,
            imagePayloadResolver: LlmImagePayloadResolver? = null,
            timeoutMillis: Int = DefaultProviderTimeoutMillis
        ): CompositeLlmGenerationRuntime =
            CompositeLlmGenerationRuntime(
                openAiCompatible = ProductionLlmGenerationRuntime(
                    LlmProviderProtocol.OpenAiCompatible,
                    transport,
                    secretResolver,
                    timeoutMillis,
                    imagePayloadResolver
                ),
                anthropicCompatible = ProductionLlmGenerationRuntime(
                    LlmProviderProtocol.AnthropicCompatible,
                    transport,
                    secretResolver,
                    timeoutMillis,
                    imagePayloadResolver
                ),
                geminiNative = ProductionLlmGenerationRuntime(
                    LlmProviderProtocol.GeminiNative,
                    transport,
                    secretResolver,
                    timeoutMillis,
                    imagePayloadResolver
                )
            )
    }
}

class ProductionLlmGenerationRuntime(
    private val protocol: LlmProviderProtocol,
    private val transport: ProviderHttpTransport,
    private val secretResolver: LlmSecretResolver,
    private val timeoutMillis: Int = DefaultProviderTimeoutMillis,
    private val imagePayloadResolver: LlmImagePayloadResolver? = null
) : LlmGenerationRuntime {
    override suspend fun generate(request: LlmGenerationRequest): LlmGenerationResult {
        val secretRef = request.secretRef?.trim().orEmpty()
        if (secretRef.isEmpty()) return MissingCredential

        val secret = runCatching { secretResolver.resolve(secretRef) }
            .getOrNull()
            ?.takeIf { it.isNotBlank() }
            ?: return MissingCredential
        val executionRequest = if (request.imageAttachments.isEmpty()) {
            request
        } else {
            val resolver = imagePayloadResolver ?: return LlmGenerationResult.Failure(
                message = "Provider configuration is invalid.", retryable = false
            )
            val images = request.imageAttachments.map { resolver.resolve(it) }
            if (images.any { it == null }) return LlmGenerationResult.Failure(
                message = "Provider configuration is invalid.", retryable = false
            )
            request.copy(resolvedImages = images.filterNotNull())
        }
        val providerRequest = buildHttpRequest(executionRequest, secret)
            ?: return LlmGenerationResult.Failure(
                message = "Provider configuration is invalid.",
                retryable = false
            )

        return when (val result = runCatching {
            if (request.streaming) {
                transport.executeStreaming(providerRequest) { line ->
                    line.sseData().mapNotNull(::parseText).forEach { text ->
                        request.onStreamChunk?.invoke(text)
                    }
                }
            } else {
                transport.execute(providerRequest)
            }
        }.getOrNull()) {
            is ProviderHttpResult.Response -> parseResponse(result, request.streaming)
            ProviderHttpResult.Timeout -> LlmGenerationResult.Timeout
            ProviderHttpResult.Failure, null -> LlmGenerationResult.Failure(
                message = "Provider request failed.",
                retryable = true
            )
        }
    }

    private fun buildHttpRequest(
        request: LlmGenerationRequest,
        secret: String
    ): ProviderHttpRequest? {
        val payload = when (protocol) {
            LlmProviderProtocol.OpenAiCompatible ->
                OpenAiCompatibleGenerationRuntime().buildPayload(request)
            LlmProviderProtocol.AnthropicCompatible ->
                AnthropicCompatibleGenerationRuntime().buildPayload(request)
            LlmProviderProtocol.GeminiNative -> buildGeminiPayload(request)
        }
        if (!payload.endpoint.isSafeHttpEndpoint()) return null

        val headers = buildMap<String, String> {
            put("Content-Type", "application/json")
            put("Accept", if (request.streaming) "text/event-stream" else "application/json")
            // Disable HttpURLConnection transparent gzip for SSE: a gzip layer
            // can buffer the whole event stream and only deliver it when the
            // connection completes, which defeats incremental streaming.
            if (request.streaming) put("Accept-Encoding", "identity")
            when (protocol) {
                LlmProviderProtocol.OpenAiCompatible -> {
                    put("Authorization", "Bearer $secret")
                }
                LlmProviderProtocol.AnthropicCompatible -> {
                    put("x-api-key", secret)
                    put("anthropic-version", AnthropicApiVersion)
                }
                LlmProviderProtocol.GeminiNative -> {
                    put("x-goog-api-key", secret)
                }
            }
        }
        return ProviderHttpRequest(
            url = payload.endpoint,
            headers = headers,
            jsonBody = ProviderJson.stringify(payload.body),
            timeoutMillis = timeoutMillis,
            streaming = request.streaming
        )
    }

    private fun parseResponse(
        response: ProviderHttpResult.Response,
        streaming: Boolean
    ): LlmGenerationResult {
        if (response.statusCode !in 200..299) {
            return response.statusCode.toSafeFailure()
        }
        val chunks = if (streaming) {
            response.body.sseData().mapNotNull(::parseText).toList()
        } else {
            listOfNotNull(parseText(response.body))
        }
        if (chunks.isEmpty()) {
            return LlmGenerationResult.Failure(
                message = "Provider returned an invalid response.",
                retryable = true
            )
        }
        return if (streaming) {
            LlmGenerationResult.Streamed(chunks)
        } else {
            LlmGenerationResult.Success(chunks.joinToString(separator = ""))
        }
    }

    private fun parseText(json: String): String? {
        val root = ProviderJson.parse(json) as? Map<*, *> ?: return null
        val text = when (protocol) {
            LlmProviderProtocol.OpenAiCompatible -> root.openAiText()
            LlmProviderProtocol.AnthropicCompatible -> root.anthropicText()
            LlmProviderProtocol.GeminiNative -> root.geminiText()
        }
        return text?.takeIf { it.isNotEmpty() }
    }
}

private fun buildGeminiPayload(request: LlmGenerationRequest): LlmProviderPayload {
    val operation = if (request.streaming) "streamGenerateContent?alt=sse" else "generateContent"
    val endpoint = request.baseUrl.orEmpty().trimEnd('/') +
        "/models/${encodePathSegment(request.model)}:$operation"
    return LlmProviderPayload(
        protocol = LlmProviderProtocol.GeminiNative,
        endpoint = endpoint,
        body = mapOf(
            "contents" to listOf(
                mapOf(
                    "role" to "user",
                    "parts" to buildList {
                        add(mapOf("text" to request.productionUserText()))
                        request.resolvedImages.forEach { image ->
                            add(mapOf(
                                "inline_data" to mapOf(
                                    "mime_type" to image.mimeType,
                                    "data" to image.base64Data
                                )
                            ))
                            Unit
                        }
                    }
                )
            )
        )
    )
}

private fun LlmGenerationRequest.productionUserText(): String {
    val context = buildList {
        reverseTutorStudentPromptBlock()?.let { add(it) }
        sessionPolicyPromptBlock()?.let { add(it) }
        guidedLearningPlanPromptBlock()?.let { add(it) }
        quoteExcerpt?.takeIf { it.isNotBlank() }?.let { add("Quote: ${it.trim()}") }
        if (contextEvidence.isNotEmpty()) {
            add(
                buildString {
                    append("Context evidence:")
                    contextEvidence.forEachIndexed { index, evidence ->
                        append("\n[${index + 1}] ${evidence.kind} - ${evidence.title}: ${evidence.body}")
                    }
                    if (contextEvidence.any { it.kind == "Source" }) {
                        append("\n资料片段优先相信：与你的既有知识冲突时，以资料为准。")
                    }
                }
            )
        }
    }
    return (context + userText).joinToString(separator = "\n\n")
}

private fun LlmProviderKind.toProviderProtocol(): LlmProviderProtocol =
    when (this) {
        LlmProviderKind.AnthropicCompatible -> LlmProviderProtocol.AnthropicCompatible
        LlmProviderKind.Gemini -> LlmProviderProtocol.GeminiNative
        LlmProviderKind.OpenAiCompatible,
        LlmProviderKind.DeepSeek,
        LlmProviderKind.FreeGlm,
        LlmProviderKind.Local,
        LlmProviderKind.Custom -> LlmProviderProtocol.OpenAiCompatible
    }

private fun Map<*, *>.openAiText(): String? {
    val choice = (this["choices"] as? List<*>)?.firstOrNull() as? Map<*, *> ?: return null
    val delta = choice["delta"] as? Map<*, *>
    val message = choice["message"] as? Map<*, *>
    return (delta?.get("content") ?: message?.get("content")) as? String
}

private fun Map<*, *>.anthropicText(): String? {
    val delta = this["delta"] as? Map<*, *>
    val deltaText = delta?.get("text") as? String
    if (deltaText != null) return deltaText
    return (this["content"] as? List<*>)
        ?.mapNotNull { (it as? Map<*, *>)?.get("text") as? String }
        ?.joinToString(separator = "")
}

private fun Map<*, *>.geminiText(): String? =
    (this["candidates"] as? List<*>)
        ?.mapNotNull { it as? Map<*, *> }
        ?.flatMap { candidate ->
            val content = candidate["content"] as? Map<*, *> ?: return@flatMap emptyList()
            (content["parts"] as? List<*>)
                ?.mapNotNull { (it as? Map<*, *>)?.get("text") as? String }
                .orEmpty()
        }
        ?.joinToString(separator = "")

private fun String.sseData(): Sequence<String> =
    lineSequence()
        .map(String::trim)
        .filter { it.startsWith("data:") }
        .map { it.removePrefix("data:").trim() }
        .filter { it.isNotEmpty() && it != "[DONE]" }

private fun Int.toSafeFailure(): LlmGenerationResult.Failure =
    when (this) {
        401 -> LlmGenerationResult.Failure(
            message = "Provider rejected the credential.",
            retryable = false
        )
        403 -> LlmGenerationResult.Failure(
            message = "Provider denied access.",
            retryable = false
        )
        404 -> LlmGenerationResult.Failure(
            message = "Provider endpoint or model was not found.",
            retryable = false
        )
        408 -> LlmGenerationResult.Failure(
            message = "Provider request timed out.",
            retryable = true
        )
        429 -> LlmGenerationResult.Failure(
            message = "Provider rate limit reached.",
            retryable = true
        )
        in 500..599 -> LlmGenerationResult.Failure(
            message = "Provider is temporarily unavailable.",
            retryable = true
        )
        else -> LlmGenerationResult.Failure(
            message = "Provider request was rejected.",
            retryable = false
        )
    }

private fun String.isSafeHttpEndpoint(): Boolean {
    val uri = runCatching { URI(this) }.getOrNull() ?: return false
    return (uri.scheme == "http" || uri.scheme == "https") && !uri.host.isNullOrBlank()
}

private fun encodePathSegment(value: String): String =
    value.trim().replace(Regex("[^A-Za-z0-9._-]")) {
        "%%%02X".format(it.value[0].code)
    }

private val MissingCredential = LlmGenerationResult.Failure(
    message = "Provider credential is unavailable.",
    retryable = false
)

private const val AnthropicApiVersion = "2023-06-01"
private const val DefaultProviderTimeoutMillis = 60_000

internal object ProviderJson {
    fun stringify(value: Any?): String = buildString { appendValue(value) }

    fun parse(json: String): Any? = runCatching { Parser(json).parse() }.getOrNull()

    private fun StringBuilder.appendValue(value: Any?) {
        when (value) {
            null -> append("null")
            is String -> appendQuoted(value)
            is Boolean, is Number -> append(value)
            is Map<*, *> -> {
                append('{')
                value.entries.forEachIndexed { index, entry ->
                    if (index > 0) append(',')
                    appendQuoted(entry.key.toString())
                    append(':')
                    appendValue(entry.value)
                }
                append('}')
            }
            is Iterable<*> -> {
                append('[')
                value.forEachIndexed { index, item ->
                    if (index > 0) append(',')
                    appendValue(item)
                }
                append(']')
            }
            else -> appendQuoted(value.toString())
        }
    }

    private fun StringBuilder.appendQuoted(value: String) {
        append('"')
        value.forEach { char ->
            when (char) {
                '"' -> append("\\\"")
                '\\' -> append("\\\\")
                '\b' -> append("\\b")
                '\u000C' -> append("\\f")
                '\n' -> append("\\n")
                '\r' -> append("\\r")
                '\t' -> append("\\t")
                else -> if (char.code < 0x20) {
                    append("\\u%04x".format(char.code))
                } else {
                    append(char)
                }
            }
        }
        append('"')
    }

    private class Parser(
        private val source: String
    ) {
        private var index = 0

        fun parse(): Any? {
            skipWhitespace()
            val value = parseValue()
            skipWhitespace()
            check(index == source.length)
            return value
        }

        private fun parseValue(): Any? {
            skipWhitespace()
            return when (source.getOrNull(index)) {
                '{' -> parseObject()
                '[' -> parseArray()
                '"' -> parseString()
                't' -> parseLiteral("true", true)
                'f' -> parseLiteral("false", false)
                'n' -> parseLiteral("null", null)
                '-', in '0'..'9' -> parseNumber()
                else -> error("Invalid JSON")
            }
        }

        private fun parseObject(): Map<String, Any?> {
            expect('{')
            skipWhitespace()
            if (consume('}')) return emptyMap()
            val result = linkedMapOf<String, Any?>()
            while (true) {
                skipWhitespace()
                val key = parseString()
                skipWhitespace()
                expect(':')
                result[key] = parseValue()
                skipWhitespace()
                if (consume('}')) return result
                expect(',')
            }
        }

        private fun parseArray(): List<Any?> {
            expect('[')
            skipWhitespace()
            if (consume(']')) return emptyList()
            val result = mutableListOf<Any?>()
            while (true) {
                result += parseValue()
                skipWhitespace()
                if (consume(']')) return result
                expect(',')
            }
        }

        private fun parseString(): String {
            expect('"')
            return buildString {
                while (index < source.length) {
                    val char = source[index++]
                    when (char) {
                        '"' -> return@buildString
                        '\\' -> append(parseEscape())
                        else -> append(char)
                    }
                }
                error("Unterminated string")
            }
        }

        private fun parseEscape(): Char =
            when (val escaped = source.getOrNull(index++) ?: error("Invalid escape")) {
                '"', '\\', '/' -> escaped
                'b' -> '\b'
                'f' -> '\u000C'
                'n' -> '\n'
                'r' -> '\r'
                't' -> '\t'
                'u' -> {
                    val end = index + 4
                    check(end <= source.length)
                    source.substring(index, end).toInt(16).toChar().also { index = end }
                }
                else -> error("Invalid escape")
            }

        private fun parseNumber(): Number {
            val start = index
            if (source.getOrNull(index) == '-') index += 1
            while (source.getOrNull(index)?.isDigit() == true) index += 1
            if (source.getOrNull(index) == '.') {
                index += 1
                while (source.getOrNull(index)?.isDigit() == true) index += 1
            }
            if (source.getOrNull(index) == 'e' || source.getOrNull(index) == 'E') {
                index += 1
                if (source.getOrNull(index) == '+' || source.getOrNull(index) == '-') index += 1
                while (source.getOrNull(index)?.isDigit() == true) index += 1
            }
            val number = source.substring(start, index)
            return number.toLongOrNull() ?: number.toDouble()
        }

        private fun <T> parseLiteral(text: String, value: T): T {
            check(source.regionMatches(index, text, 0, text.length))
            index += text.length
            return value
        }

        private fun expect(char: Char) {
            check(consume(char))
        }

        private fun consume(char: Char): Boolean {
            if (source.getOrNull(index) != char) return false
            index += 1
            return true
        }

        private fun skipWhitespace() {
            while (source.getOrNull(index)?.isWhitespace() == true) index += 1
        }
    }
}
