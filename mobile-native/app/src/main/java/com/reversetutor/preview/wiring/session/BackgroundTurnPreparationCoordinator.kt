package com.reversetutor.preview.wiring.session

import com.reversetutor.core.data.background.BackgroundGenerationInput
import com.reversetutor.core.data.background.BackgroundGenerationJob
import com.reversetutor.core.domain.ConversationContextContract
import com.reversetutor.core.domain.RecentTurnSignals
import com.reversetutor.core.domain.SessionTurnPolicy
import com.reversetutor.core.llm.LlmGenerationToken
import com.reversetutor.feature.chat.BackgroundTurnPreparationPort
import com.reversetutor.feature.chat.BackgroundTurnPreparationRequest
import com.reversetutor.feature.chat.BackgroundTurnPreparationResult
import com.reversetutor.feature.chat.ConversationMessageContract
import com.reversetutor.feature.chat.SessionConversationFacade
import kotlinx.coroutines.CancellationException

/**
 * Implements [BackgroundTurnPreparationPort] for production wiring.
 *
 * Strict execution order:
 * 1. Blank check \u2192 [BackgroundTurnPreparationResult.BlankInput]
 * 2. Session deleted check \u2192 [BackgroundTurnPreparationResult.SessionUnavailable]
 * 3. Assemble bounded context via [assembleContext]
 * 4. Normalize study policy via [SessionTurnPolicy.normalize]
 * 5. Enqueue exactly one background job via [enqueueJob]
 * 6. Project queued contract via [SessionConversationFacade.mapQueued]
 *
 * Never calls ChatGenerationRepository, Worker, or any message-write API.
 * [CancellationException] is rethrown; all other exceptions map to [BackgroundTurnPreparationResult.Failed].
 */
internal class BackgroundTurnPreparationCoordinator(
    private val isSessionDeleted: suspend (String) -> Boolean,
    private val assembleContext: suspend (String, String, String) -> ConversationContextContract,
    private val enqueueJob: suspend (BackgroundGenerationInput, Long) -> BackgroundGenerationJob,
    private val loadRecentTurnSignals: suspend (String, String) -> RecentTurnSignals = { _, _ -> RecentTurnSignals() },
    private val nowEpochMillis: () -> Long = System::currentTimeMillis,
    private val loadMessages: (String) -> List<ConversationMessageContract> = { emptyList() },
    private val facade: SessionConversationFacade = SessionConversationFacade()
) : BackgroundTurnPreparationPort {

    override suspend fun prepareAndEnqueue(
        request: BackgroundTurnPreparationRequest
    ): BackgroundTurnPreparationResult {
        try {
            if (request.userText.isBlank() && request.imageAttachments.isEmpty()) {
                return BackgroundTurnPreparationResult.BlankInput
            }
            if (isSessionDeleted(request.sessionId)) {
                return BackgroundTurnPreparationResult.SessionUnavailable
            }

            val context = assembleContext(request.spaceId, request.sessionId, request.userText)
            val baseGuidedInput = request.sessionSnapshot.toGuidedLearningTurnInput(
                spaceId = request.spaceId,
                sessionId = request.sessionId,
                context = context,
                // userText is passed only so the mapper's deterministic intent
                // classifier can categorize this turn; the guided input stores
                // just the categorized enum, never the raw text.
                userText = request.userText
            )
            val recentSignals = try {
                loadRecentTurnSignals(request.sessionId, baseGuidedInput.conceptKey)
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                // A read-only signal lookup can improve the next plan, but it
                // must never prevent a valid user turn from being queued.
                RecentTurnSignals()
            }
            val guidedInput = baseGuidedInput.copy(recentSignals = recentSignals).normalized()
            val turnPlan = request.turnPlan ?: guidedInput.selectGuidedLearningPlan()
            val policy = SessionTurnPolicy.normalize(
                request.sessionSnapshot.toSessionPolicyInput(request.userText)
            )

            val job = enqueueJob(
                BackgroundGenerationInput(
                    spaceId = request.spaceId,
                    sessionId = request.sessionId,
                    userMessageId = request.userMessageId,
                    userText = request.userText,
                    token = LlmGenerationToken(request.token),
                    quoteExcerpt = request.quoteExcerpt,
                    imageAttachments = request.imageAttachments,
                    contextEvidence = listOfNotNull(request.sessionSnapshot.toLlmTemplateEvidence()) +
                        context.toLlmContextEvidence(),
                    sessionPolicy = policy.toLlmSessionPolicyContext(),
                    turnPlan = turnPlan
                ),
                nowEpochMillis()
            )

            return BackgroundTurnPreparationResult.Queued(
                jobId = job.id,
                contract = facade.mapQueued(
                    sessionId = request.sessionId,
                    turnId = request.userMessageId,
                    policy = policy,
                    context = context,
                    messages = loadMessages(request.sessionId)
                )
            )
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            return BackgroundTurnPreparationResult.Failed
        }
    }
}
