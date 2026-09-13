package com.reversetutor.preview.wiring.session

import com.reversetutor.core.data.graph.GraphRepository
import com.reversetutor.core.data.learning.LearningLedgerRepository
import com.reversetutor.core.data.learning.LearningRepositoryImpl
import com.reversetutor.core.data.llm.ChatGenerationRepository
import com.reversetutor.core.data.memory.MemoryRepository
import com.reversetutor.core.data.message.MessageRepository
import com.reversetutor.core.data.session.SessionRepository
import com.reversetutor.core.data.sources.SourceRepository
import com.reversetutor.core.domain.ConversationContextAssembler
import com.reversetutor.core.domain.ConversationContextContract
import com.reversetutor.core.domain.MessageContextPort
import com.reversetutor.core.domain.ConversationRunRepository
import com.reversetutor.core.domain.ConversationSessionCoordinator
import com.reversetutor.core.domain.LearningOverviewCoordinator
import com.reversetutor.core.domain.LearningOverviewScope
import com.reversetutor.core.domain.SessionPolicyInput
import com.reversetutor.feature.chat.ConversationMessageContract
import com.reversetutor.feature.chat.SessionConversationContract
import com.reversetutor.feature.chat.SessionConversationFacade
import com.reversetutor.core.domain.LearningOverviewContract

/**
 * Compose-free application wiring entry point for the session conversation and
 * home learning overview capabilities.
 *
 * This is the single production composition root that binds the non-frozen
 * domain ports to existing frozen repositories:
 *
 * ```
 * SessionConversationFacade
 *   -> ConversationSessionCoordinator
 *        -> ConversationContextAssembler -> context port adapters -> Repositories
 *        -> ChatGenerationPortAdapter   -> ChatGenerationRepository
 *        -> SessionTurnPersistencePortAdapter -> MessageRepository / run repo
 * ```
 *
 * The UI layer may ONLY consume [SessionConversationContract] and
 * [LearningOverviewContract] returned from here. It must not reach DAOs,
 * Entities, `ReverseTutorDatabase`, `SecretStore`, or protocol DTOs.
 *
 * This class imports no Compose type. Its outputs are the immutable
 * feature-chat contract and the immutable domain overview contract.
 */
class SessionConversationAssembly(
    private val chatGenerationRepository: ChatGenerationRepository,
    private val messageRepository: MessageRepository,
    private val conversationRunRepository: ConversationRunRepository,
    private val sessionRepository: SessionRepository,
    private val memoryRepository: MemoryRepository,
    private val graphRepository: GraphRepository,
    private val sourceRepository: SourceRepository,
    private val learningRepository: LearningRepositoryImpl,
    private val learningLedgerRepository: LearningLedgerRepository? = null,
    private val messageContextPort: MessageContextPort = MessageContextPortAdapter(messageRepository),
    private val sessionSummaryStore: SessionSummaryStore? = null,
    private val nowEpochMillis: () -> Long = System::currentTimeMillis
) {

    private val persistencePort: SessionTurnPersistencePortAdapter =
        SessionTurnPersistencePortAdapter(
            saveUserMessage = { sessionId, text, now, messageId ->
                messageRepository.sendUserMessage(sessionId, text, now, messageId) != null
            },
            checkSessionDeleted = { sessionId -> conversationRunRepository.isSessionDeleted(sessionId) },
            checkTokenCurrent = { true },
            checkTurnCompleted = { turnId ->
                conversationRunRepository.findLatestRun(turnId)?.isTerminal ?: false
            }
        )

    private val generationPort: ChatGenerationPortAdapter =
        ChatGenerationPortAdapter(
            generate = { input, now, isTokenCurrent, canPersistResult ->
                chatGenerationRepository.generateReply(input, now, isTokenCurrent, canPersistResult)
            },
            readAssistantText = { sessionId, assistantMessageId ->
                messageRepository.listMessages(sessionId)
                    .firstOrNull { it.id == assistantMessageId }
                    ?.text ?: ""
            }
        )

    /**
     * NEWMP-V1-017: early-history summarizer. Old-parity trigger — the legacy
     * engine compressed early dialogue at the start of every turn; the native
     * production path funnels each turn's context preparation through
     * [assembleContext], so the trigger lives on that single choke point.
     */
    private val sessionSummarizer: SessionSummarizer? = sessionSummaryStore?.let { store ->
        SessionSummarizer(
            generateSummary = chatGenerationRepository::generateSessionSummary,
            listMessages = messageRepository::listMessages,
            store = store
        )
    }

    private val contextAssembler: ConversationContextAssembler = ConversationContextAssembler(
        messagePort = messageContextPort,
        memoryPort = MemoryContextPortAdapter(memoryRepository),
        errorPort = ErrorContextPortAdapter(memoryRepository),
        graphPort = GraphContextPortAdapter(
            graphRepository,
            learningLedgerRepository,
            nowEpochMillis
        ),
        sourcePort = SourceContextPortAdapter(
            sourceRepository,
            // NEWMP-V1-024: query embedding for semantic source ranking.
            chatGenerationRepository::embedQueryText
        ),
        masteryFactPort = learningLedgerRepository?.let { MasteryFactContextPortAdapter(it) },
        digestPort = sessionSummaryStore
    )

    private val coordinator: ConversationSessionCoordinator = ConversationSessionCoordinator(
        contextAssembler = contextAssembler,
        generationPort = generationPort,
        persistencePort = persistencePort,
        nowEpochMillis = nowEpochMillis
    )

    private val overviewCoordinator: LearningOverviewCoordinator = LearningOverviewCoordinator(
        sessionPort = LearningOverviewSessionPortAdapter(sessionRepository),
        progressPort = LearningOverviewProgressPortAdapter(learningRepository, nowEpochMillis),
        planPort = LearningOverviewPlanPortAdapter(learningRepository),
        threadPort = LearningOverviewThreadPortAdapter(learningRepository),
        weakPointPort = LearningOverviewWeakPointPortAdapter(memoryRepository),
        tokenPort = LearningOverviewTokenPortAdapter(
            listTokenUsage = learningRepository::listTokenUsage,
            sessionIdForTurn = { turnId ->
                conversationRunRepository.findLatestRun(turnId)?.sessionId
            },
            nowEpochMillis = nowEpochMillis
        ),
        nowEpochMillis = nowEpochMillis
    )

    private val facade: SessionConversationFacade = SessionConversationFacade()

    /**
     * Assemble bounded conversation context for the given session.
     * Delegates to the private [ConversationContextAssembler] without
     * running a generation turn.
     */
    suspend fun assembleContext(
        spaceId: String,
        sessionId: String,
        queryText: String = ""
    ): ConversationContextContract {
        // NEWMP-V1-017: compress early history first so this very turn's
        // assembled contract — and the evidence built from it — already
        // carries the fresh digest. Failures are swallowed inside and
        // retried on the next turn (old-parity behavior).
        sessionSummarizer?.maybeSummarize(sessionId)
        return contextAssembler.assemble(spaceId, sessionId, queryText)
    }

    /**
     * Run a single conversation turn and return the immutable
     * [SessionConversationContract] for the UI. Pure wiring: no Compose type
     * is produced or referenced.
     */
    suspend fun runTurn(
        spaceId: String,
        sessionId: String,
        turnId: String,
        userMessageId: String,
        userText: String,
        token: String,
        policyInput: SessionPolicyInput
    ): SessionConversationContract {
        val result = coordinator.executeTurn(
            spaceId = spaceId,
            sessionId = sessionId,
            turnId = turnId,
            userMessageId = userMessageId,
            userText = userText,
            token = token,
            policyInput = policyInput
        )
        val messages = messageRepository.listMessages(sessionId).map {
            ConversationMessageContract(it.id, it.role.name.lowercase(), it.text, it.createdAtEpochMillis)
        }
        return facade.mapResult(result, sessionId, turnId, messages)
    }

    /**
     * Build the home learning overview read model for the given scope.
     */
    suspend fun overview(scope: LearningOverviewScope): LearningOverviewContract =
        overviewCoordinator.generate(scope)
}
