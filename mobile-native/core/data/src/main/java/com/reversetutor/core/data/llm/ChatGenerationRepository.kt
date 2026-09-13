package com.reversetutor.core.data.llm

import com.reversetutor.core.data.model.ExecutionModelConfiguration
import com.reversetutor.core.data.model.ExecutionModelResolver
import com.reversetutor.core.data.message.MessageRepository
import com.reversetutor.core.domain.TurnPlan
import com.reversetutor.core.llm.EmbeddingCallResult
import com.reversetutor.core.llm.LlmCapabilities
import com.reversetutor.core.llm.LlmGuidedTurnPlan
import com.reversetutor.core.llm.LlmAssistantReplyEnvelope
import com.reversetutor.core.llm.LlmAssistantTurnEnvelope
import com.reversetutor.core.llm.LlmAssistantReplyEnvelopeParser
import com.reversetutor.core.llm.timelineText
import com.reversetutor.core.llm.toVisibleTimelineText
import com.reversetutor.core.llm.LlmContextEvidence
import com.reversetutor.core.llm.LlmGenerationBlockReason
import com.reversetutor.core.llm.LlmGenerationPlan
import com.reversetutor.core.llm.LlmGenerationPlanner
import com.reversetutor.core.llm.LlmGenerationResult
import com.reversetutor.core.llm.LlmGenerationRuntime
import com.reversetutor.core.llm.LlmGenerationToken
import com.reversetutor.core.llm.LlmProfileCapabilityResolver
import com.reversetutor.core.llm.LlmSessionPolicyContext
import com.reversetutor.core.llm.OpenAiCompatibleEmbeddingRuntime
import com.reversetutor.core.model.Message
import com.reversetutor.core.model.MessageAttachment
import com.reversetutor.core.model.MessageRole
import com.reversetutor.core.model.LlmProfile
import com.reversetutor.core.model.LlmProviderKind
import com.reversetutor.core.model.ModelProtocol

class ChatGenerationRepository(
    private val messageRepository: MessageRepository,
    private val llmProfileRepository: LlmProfileRepository,
    private val runtime: LlmGenerationRuntime,
    private val modelConnectionRepository: ExecutionModelResolver? = null,
    /** NEWMP-V1-018: consulted per generateReply call; summaries deliberately stay offline. */
    private val webSearchPreference: suspend () -> Boolean = { false },
    /** NEWMP-V1-024: optional embeddings runtime for semantic source retrieval. */
    private val embeddingRuntime: OpenAiCompatibleEmbeddingRuntime? = null,
    private val embeddingModelName: String = "text-embedding-v3"
) {
    suspend fun generateReply(
        input: ChatGenerationInput,
        nowEpochMillis: Long,
        isTokenCurrent: (LlmGenerationToken) -> Boolean,
        canPersistResult: suspend () -> Boolean = { true },
        onChunk: (String) -> Unit = {}
    ): ChatGenerationOutcome {
        if (!isTokenCurrent(input.token)) {
            return ChatGenerationOutcome.Stale
        }

        val activeProfile = resolveExecutionProfile(input)
            ?: return ChatGenerationOutcome.NoModelConfigured
        val plan = LlmGenerationPlanner.plan(
            sessionId = input.sessionId,
            userMessageId = input.userMessageId,
            userText = input.userText,
            profile = activeProfile,
            capabilities = input.capabilities ?: LlmProfileCapabilityResolver.infer(activeProfile),
            token = input.token,
            quoteExcerpt = input.quoteExcerpt,
            imageAttachments = input.imageAttachments,
            contextEvidence = input.contextEvidence,
            sessionPolicy = input.sessionPolicy,
            assistantTurnEnvelope = input.assistantTurnEnvelope,
            guidedTurnPlan = input.turnPlan?.toLlmGuidedTurnPlan(),
            onStreamChunk = { chunk ->
                if (isTokenCurrent(input.token)) onChunk(chunk.toVisibleTimelineText())
            },
            allowPlanDrivenOpening = input.allowPlanDrivenOpening,
            webSearchEnabled = webSearchPreference()
        )

        val request = when (plan) {
            is LlmGenerationPlan.Blocked -> return plan.reason.toOutcome()
            is LlmGenerationPlan.Ready -> plan.request
        }

        val result = runtime.generate(request)
        if (!isTokenCurrent(input.token) || !canPersistResult()) {
            return ChatGenerationOutcome.Stale
        }

        return when (result) {
            is LlmGenerationResult.Success,
            is LlmGenerationResult.Streamed -> {
                val replyText = result.visibleText
                if (replyText.isBlank()) {
                    ChatGenerationOutcome.ProviderFailed("Empty response")
                } else {
                    val parsedReply = LlmAssistantReplyEnvelopeParser.parseValidated(
                        rawText = replyText,
                        allowedEvidenceIds = input.contextEvidence.mapNotNull { it.normalized()?.id }.toSet()
                    )
                    val timelineText = parsedReply?.timelineText() ?: replyText.toVisibleTimelineText()
                    val assistantMessageId = "assistant-${input.token.value}"
                    messageRepository.saveMessage(
                        Message(
                            id = assistantMessageId,
                            spaceId = input.spaceId?.trim()?.ifEmpty { null } ?: activeProfile.spaceId,
                            sessionId = input.sessionId,
                            role = MessageRole.Assistant,
                            text = timelineText,
                            createdAtEpochMillis = nowEpochMillis
                        )
                    )
                    ChatGenerationOutcome.Generated(assistantMessageId, parsedReply)
                }
            }
            is LlmGenerationResult.Failure -> {
                ChatGenerationOutcome.ProviderFailed(result.message.toSafeProviderFailureCode())
            }
            LlmGenerationResult.Timeout -> {
                ChatGenerationOutcome.ProviderFailed("llm_provider_timeout")
            }
        }
    }

    /**
     * NEWMP-V1-017: auxiliary summarizer entry point. Runs the same planner /
     * runtime pipeline as [generateReply] but never persists an assistant
     * message — the caller owns storing the summary text. The prompt travels
     * as a raw user turn with no session policy, guided plan, or evidence, so
     * the reverse-tutor student persona block is never attached and the
     * summarizer persona stays fully separated from the teaching persona.
     */
    suspend fun generateSessionSummary(
        sessionId: String,
        promptText: String
    ): SessionSummaryOutcome {
        val profile = resolveProfileForSession(sessionId, requestedBindingId = null)
            ?: return SessionSummaryOutcome.NoModelConfigured
        val plan = LlmGenerationPlanner.plan(
            sessionId = sessionId,
            userMessageId = null,
            userText = promptText,
            profile = profile,
            capabilities = LlmProfileCapabilityResolver.infer(profile),
            token = LlmGenerationToken("summary-" + profile.id + "-" + System.nanoTime())
        )
        val request = when (plan) {
            is LlmGenerationPlan.Blocked -> return plan.reason.toSummaryOutcome()
            is LlmGenerationPlan.Ready -> plan.request.copy(streaming = false)
        }
        return when (val result = runtime.generate(request)) {
            is LlmGenerationResult.Success,
            is LlmGenerationResult.Streamed -> {
                val summaryText = result.visibleText
                if (summaryText.isBlank()) {
                    SessionSummaryOutcome.ProviderFailed("llm_provider_invalid_response")
                } else {
                    SessionSummaryOutcome.Generated(summaryText)
                }
            }
            is LlmGenerationResult.Failure ->
                SessionSummaryOutcome.ProviderFailed(result.message.toSafeProviderFailureCode())
            LlmGenerationResult.Timeout ->
                SessionSummaryOutcome.ProviderFailed("llm_provider_timeout")
        }
    }

    /**
     * NEWMP-V1-020: auxiliary vision transcription entry point for image
     * sources whose on-device OCR returned no usable text (pure diagrams,
     * geometry figures, function graphs, chemistry structures). Runs the same
     * planner / runtime pipeline but never persists an assistant message —
     * the caller owns the returned text. Vision capabilities are forced here
     * because the user explicitly opted in per import; when the configured
     * model cannot actually see images the provider call fails and the caller
     * falls back to the existing FutureAssisted state.
     */
    suspend fun describeImageForSource(
        sessionId: String,
        image: MessageAttachment,
        visionModelName: String
    ): SourceVisionOutcome {
        val resolvedProfile = resolveProfileForSession(sessionId, requestedBindingId = null)
            ?: return SourceVisionOutcome.NoModelConfigured
        val profile = if (visionModelName.isNotBlank()) {
            resolvedProfile.copy(model = visionModelName.trim())
        } else {
            resolvedProfile
        }
        val plan = LlmGenerationPlanner.plan(
            sessionId = sessionId,
            userMessageId = null,
            userText = SOURCE_VISION_TRANSCRIPTION_PROMPT,
            profile = profile,
            capabilities = LlmCapabilities(supportsVision = true),
            token = LlmGenerationToken("vision-" + profile.id + "-" + System.nanoTime()),
            imageAttachments = listOf(image)
        )
        val request = when (plan) {
            is LlmGenerationPlan.Blocked -> return plan.reason.toVisionOutcome()
            is LlmGenerationPlan.Ready -> plan.request.copy(streaming = false)
        }
        return when (val result = runtime.generate(request)) {
            is LlmGenerationResult.Success,
            is LlmGenerationResult.Streamed -> {
                val descriptionText = result.visibleText
                if (descriptionText.isBlank()) {
                    SourceVisionOutcome.ProviderFailed("llm_provider_invalid_response")
                } else {
                    SourceVisionOutcome.Generated(descriptionText)
                }
            }
            is LlmGenerationResult.Failure ->
                SourceVisionOutcome.ProviderFailed(result.message.toSafeProviderFailureCode())
            LlmGenerationResult.Timeout ->
                SourceVisionOutcome.ProviderFailed("llm_provider_timeout")
        }
    }

    /**
     * NEWMP-V1-024: embeds source-chunk texts for semantic retrieval. Null when
     * no runtime is wired, the active channel cannot serve OpenAI-compatible
     * embeddings, or the call fails — callers then fall back to keywords.
     */
    suspend fun embedSourceTexts(texts: List<String>): List<FloatArray>? = embedTexts(texts)

    /** NEWMP-V1-024: embeds the current user query for semantic retrieval. */
    suspend fun embedQueryText(text: String): FloatArray? = embedTexts(listOf(text))?.firstOrNull()

    private suspend fun embedTexts(texts: List<String>): List<FloatArray>? {
        if (texts.isEmpty()) return emptyList()
        val runtime = embeddingRuntime ?: return null
        val profile = activeLegacyProfile() ?: return null
        if (!profileSupportsEmbeddings(profile)) return null
        return when (
            val result = runtime.embed(
                secretRef = profile.secretRef,
                baseUrl = profile.baseUrl,
                model = embeddingModelName,
                texts = texts
            )
        ) {
            is EmbeddingCallResult.Success -> result.vectors
            EmbeddingCallResult.Failed -> null
        }
    }

    private fun profileSupportsEmbeddings(profile: LlmProfile): Boolean =
        profile.provider != LlmProviderKind.AnthropicCompatible &&
            profile.provider != LlmProviderKind.Gemini

    private suspend fun resolveExecutionProfile(input: ChatGenerationInput): LlmProfile? =
        resolveProfileForSession(
            sessionId = input.sessionId,
            requestedBindingId = input.modelBindingId
        )

    /**
     * Session-level profile resolution shared by [generateReply] and
     * [generateSessionSummary]: the execution resolver first, then the legacy
     * enabled profile when no new-style configuration exists.
     */
    private suspend fun resolveProfileForSession(
        sessionId: String,
        requestedBindingId: String?
    ): LlmProfile? {
        val resolver = modelConnectionRepository ?: return activeLegacyProfile()
        val resolved = resolver.resolveForExecution(
            sessionId = sessionId,
            requestedBindingId = requestedBindingId
        )
        if (resolved != null) return resolved.toExecutionProfile()

        val hasExplicitRequest = !requestedBindingId.isNullOrBlank()
        if (hasExplicitRequest || resolver.hasNewConfigurationForSession(sessionId)) {
            return null
        }
        return activeLegacyProfile()
    }

    private suspend fun activeLegacyProfile(): LlmProfile? =
        llmProfileRepository.listProfiles().firstOrNull { it.enabled }
}

data class ChatGenerationInput(
    val sessionId: String,
    val userMessageId: String? = null,
    val userText: String? = null,
    val token: LlmGenerationToken,
    val allowPlanDrivenOpening: Boolean = false,
    val spaceId: String? = null,
    val modelBindingId: String? = null,
    val capabilities: LlmCapabilities? = null,
    val quoteExcerpt: String? = null,
    val imageAttachments: List<MessageAttachment> = emptyList(),
    val contextEvidence: List<LlmContextEvidence> = emptyList(),
    val sessionPolicy: LlmSessionPolicyContext? = null,
    val assistantTurnEnvelope: LlmAssistantTurnEnvelope? = null,
    /**
     * Optional bounded teaching plan produced by the domain selector
     * (NEWMP-V1-002 Task 2.4). It constrains model *expression* only; learning
     * state remains owned by the local verifier, and a null plan keeps the
     * exact legacy request shape.
     */
    val turnPlan: TurnPlan? = null
)

/**
 * Map the domain [TurnPlan] into the wire-only [LlmGuidedTurnPlan] snapshot.
 * Enum names become canonical lowercase wire tokens; `nextActionOnSuccess` /
 * `nextActionOnFailure` are deliberately *not* forwarded — they are domain
 * scheduling data and must never reach the provider prompt.
 */
internal fun TurnPlan.toLlmGuidedTurnPlan(): LlmGuidedTurnPlan = LlmGuidedTurnPlan(
    actionType = actionType.toWireToken(),
    secondaryAction = secondaryAction?.toWireToken().orEmpty(),
    learningObjective = learningObjective,
    conceptKey = conceptKey,
    expectedUserMove = expectedUserMove,
    responseFormat = responseFormat.toWireToken(),
    hintLevel = hintLevel,
    evidenceRequirement = evidenceRequirement.toWireToken()
)

/** `WorkedExample` -> `worked_example`: the canonical wire tokens the LLM whitelist accepts. */
private fun Enum<*>.toWireToken(): String = name
    .replace(Regex("(?<=[a-z0-9])([A-Z])")) { "_" + it.groupValues[1].lowercase() }
    .lowercase()

private fun ExecutionModelConfiguration.toExecutionProfile(): LlmProfile =
    LlmProfile(
        id = binding.id,
        spaceId = binding.spaceId,
        name = binding.displayName,
        provider = connection.protocol.toLegacyProvider(),
        model = binding.modelId,
        secretRef = connection.secretRef,
        createdAtEpochMillis = binding.createdAtEpochMillis,
        updatedAtEpochMillis = maxOf(binding.updatedAtEpochMillis, connection.updatedAtEpochMillis),
        baseUrl = connection.baseUrl,
        enabled = binding.enabled && connection.enabled
    )

private fun ModelProtocol.toLegacyProvider(): LlmProviderKind = when (this) {
    ModelProtocol.OpenAiCompatible -> LlmProviderKind.OpenAiCompatible
    ModelProtocol.AnthropicCompatible -> LlmProviderKind.AnthropicCompatible
    ModelProtocol.GeminiNative -> LlmProviderKind.Gemini
}

sealed interface ChatGenerationOutcome {
    data class Generated(
        val assistantMessageId: String,
        val replyEnvelope: LlmAssistantReplyEnvelope? = null
    ) : ChatGenerationOutcome
    data class ProviderFailed(val message: String) : ChatGenerationOutcome
    object NoModelConfigured : ChatGenerationOutcome
    object UnsupportedVision : ChatGenerationOutcome
    object BlankPrompt : ChatGenerationOutcome
    object Stale : ChatGenerationOutcome
}

/**
 * NEWMP-V1-017: outcome of the auxiliary session-summary generation call.
 * Mirrors [ChatGenerationOutcome] block/failure semantics, but the Generated
 * branch carries the summary text itself because nothing is persisted here.
 */
sealed interface SessionSummaryOutcome {
    data class Generated(val summaryText: String) : SessionSummaryOutcome
    data class ProviderFailed(val message: String) : SessionSummaryOutcome
    object NoModelConfigured : SessionSummaryOutcome
    object UnsupportedVision : SessionSummaryOutcome
    object BlankPrompt : SessionSummaryOutcome
}

private fun LlmGenerationBlockReason.toSummaryOutcome(): SessionSummaryOutcome =
    when (this) {
        LlmGenerationBlockReason.NoModelConfigured -> SessionSummaryOutcome.NoModelConfigured
        LlmGenerationBlockReason.UnsupportedVision -> SessionSummaryOutcome.UnsupportedVision
        LlmGenerationBlockReason.BlankPrompt -> SessionSummaryOutcome.BlankPrompt
    }

/**
 * NEWMP-V1-020: outcome of the auxiliary source-image vision transcription
 * call. Mirrors [SessionSummaryOutcome] semantics — nothing is persisted and
 * the Generated branch carries the transcription text itself.
 */
sealed interface SourceVisionOutcome {
    data class Generated(val descriptionText: String) : SourceVisionOutcome
    data class ProviderFailed(val message: String) : SourceVisionOutcome
    object NoModelConfigured : SourceVisionOutcome
    object UnsupportedVision : SourceVisionOutcome
    object BlankPrompt : SourceVisionOutcome
}

private fun LlmGenerationBlockReason.toVisionOutcome(): SourceVisionOutcome =
    when (this) {
        LlmGenerationBlockReason.NoModelConfigured -> SourceVisionOutcome.NoModelConfigured
        LlmGenerationBlockReason.UnsupportedVision -> SourceVisionOutcome.UnsupportedVision
        LlmGenerationBlockReason.BlankPrompt -> SourceVisionOutcome.BlankPrompt
    }

/** NEWMP-V1-020: transcription prompt for image sources with no OCR text. */
internal const val SOURCE_VISION_TRANSCRIPTION_PROMPT =
    "请把这张学习资料图片完整转写成文字：包括题目、选项、图内标注和所有可见文字；" +
        "对纯图形（几何图、函数图像、结构式等）用简洁中文描述其关键信息。" +
        "只输出转写内容本身，不要解释、不要加标题。"

private fun LlmGenerationBlockReason.toOutcome(): ChatGenerationOutcome =
    when (this) {
        LlmGenerationBlockReason.NoModelConfigured -> ChatGenerationOutcome.NoModelConfigured
        LlmGenerationBlockReason.UnsupportedVision -> ChatGenerationOutcome.UnsupportedVision
        LlmGenerationBlockReason.BlankPrompt -> ChatGenerationOutcome.BlankPrompt
    }

/**
 * NEWMP-V1-002 Task 2.4: collapse provider diagnostics to stable safe codes.
 * Canonical runtime messages map to fixed codes; every unexpected diagnostic
 * collapses to one fixed code so raw exception detail can never reach the UI
 * or persistence.
 */
private fun String.toSafeProviderFailureCode(): String = when (trim().lowercase()) {
    "provider credential is unavailable." -> "llm_credential_unavailable"
    "provider rejected the credential." -> "llm_provider_unauthorized"
    "provider denied access." -> "llm_provider_forbidden"
    "provider endpoint or model was not found." -> "llm_provider_endpoint_unavailable"
    "provider request timed out." -> "llm_provider_timeout"
    "provider rate limit reached." -> "llm_provider_rate_limited"
    "provider is temporarily unavailable." -> "llm_provider_unavailable"
    "provider request was rejected." -> "llm_provider_rejected"
    "provider configuration is invalid." -> "llm_provider_configuration_invalid"
    "provider returned an invalid response." -> "llm_provider_invalid_response"
    "provider request failed." -> "llm_provider_request_failed"
    else -> "llm_provider_request_failed"
}
