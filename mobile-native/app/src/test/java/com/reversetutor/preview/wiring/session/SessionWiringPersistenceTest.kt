package com.reversetutor.preview.wiring.session

import com.reversetutor.core.data.llm.ChatGenerationOutcome
import com.reversetutor.core.domain.ConversationContextAssembler
import com.reversetutor.core.domain.ConversationContextContract
import com.reversetutor.core.domain.ContextMessage
import com.reversetutor.core.domain.ConversationSessionCoordinator
import com.reversetutor.core.domain.ErrorContextPort
import com.reversetutor.core.domain.ErrorReferenceContract
import com.reversetutor.core.domain.GraphContextPort
import com.reversetutor.core.domain.LearningOverviewContract
import com.reversetutor.core.domain.MemoryContextPort
import com.reversetutor.core.domain.MemoryReferenceContract
import com.reversetutor.core.domain.MessageContextPort
import com.reversetutor.core.domain.SessionActionContract
import com.reversetutor.core.domain.SessionEvaluationContract
import com.reversetutor.core.domain.SessionPolicyInput
import com.reversetutor.core.domain.SessionTurnResult
import com.reversetutor.core.domain.SourceContextPort
import com.reversetutor.core.domain.SourceReferenceContract
import com.reversetutor.feature.chat.SessionConversationContract
import com.reversetutor.feature.chat.SessionConversationFacade
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

/**
 * Wiring-level JVM tests covering NATIVE-P2-007 scenarios:
 * 3. Deleted session or stale token does not persist an assistant message.
 * 6. Facade / assembly output does not depend on any Compose/UI type.
 *
 * These tests construct a real [ConversationSessionCoordinator] with the real
 * [ChatGenerationPortAdapter] and [SessionTurnPersistencePortAdapter] (whose
 * functional seams receive controlled fakes) and a [ConversationContextAssembler]
 * backed by empty-returning fake ports — so no Room/DAO is required.
 */
class SessionWiringPersistenceTest {

    // -- Scenario 3: 删除会话或 token 失效时不落库 assistant ------------------

    @Test
    fun `session deleted prevents generation and returns SessionDeleted`() = runTest {
        var generateCalled = false
        val generationPort = ChatGenerationPortAdapter(
            generate = { _, _, _, _ ->
                generateCalled = true
                ChatGenerationOutcome.Generated("asst-x")
            },
            readAssistantText = { _, _ -> "should not happen" }
        )
        val persistencePort = SessionTurnPersistencePortAdapter(
            saveUserMessage = { _, _, _, _ -> true },
            checkSessionDeleted = { true } // session is deleted
        )
        val coordinator = ConversationSessionCoordinator(
            contextAssembler = emptyContextAssembler(),
            generationPort = generationPort,
            persistencePort = persistencePort,
            nowEpochMillis = { 1000L }
        )
        val result = coordinator.executeTurn(
            "space-1", "session-1", "turn-1", "user-1", "hi", "tok", SessionPolicyInput()
        )
        assertTrue(result is SessionTurnResult.SessionDeleted)
        assertFalse(
            "generation must not run when the session is deleted",
            generateCalled
        )
    }

    @Test
    fun `stale token skips generation and returns StaleToken without persisting`() = runTest {
        var generationCalled = false
        val generationPort = ChatGenerationPortAdapter(
            generate = { _, _, _, _ ->
                generationCalled = true
                ChatGenerationOutcome.Generated("asst-1")
            },
            readAssistantText = { _, _ -> "" }
        )
        val persistencePort = SessionTurnPersistencePortAdapter(
            saveUserMessage = { _, _, _, _ -> true },
            checkSessionDeleted = { false },
            checkTokenCurrent = { false } // token is stale
        )
        val coordinator = ConversationSessionCoordinator(
            contextAssembler = emptyContextAssembler(),
            generationPort = generationPort,
            persistencePort = persistencePort,
            nowEpochMillis = { 1000L }
        )
        val result = coordinator.executeTurn(
            "space-1", "session-1", "turn-1", "user-1", "hi", "tok", SessionPolicyInput()
        )
        assertFalse("an already-stale token must not enter frozen generation", generationCalled)
        assertTrue(result is SessionTurnResult.StaleToken)
    }

    // -- Scenario 6: Facade 输出不依赖任何 Compose/UI 类型 ---------------------

    @Test
    fun `facade output and contract types do not depend on compose types`() {
        val facade = SessionConversationFacade()
        val context = ConversationContextContract.empty("space-1", "session-1")
        val result = SessionTurnResult.Success(
            assistantMessageId = "asst-1",
            assistantText = "hi",
            evaluation = SessionEvaluationContract(),
            action = SessionActionContract(),
            context = context,
            processSummary = "ok"
        )
        val contract = facade.mapResult(result, "session-1", "turn-1", emptyList())
        assertNotNull(contract)
        assertEquals("session-1", contract.sessionId)
        assertEquals("turn-1", contract.turnId)

        // The contract types must not transitively reference any Compose type.
        assertNoComposeTypes(SessionConversationContract::class.java, mutableSetOf())
        assertNoComposeTypes(LearningOverviewContract::class.java, mutableSetOf())
        // The assembly entry point itself must not be a Compose-scoped class.
        assertFalse(
            "SessionConversationAssembly must not be a Compose-scoped class",
            SessionConversationAssembly::class.java.name.contains("compose", ignoreCase = true)
        )
    }

    // -- helpers -------------------------------------------------------------

    private fun emptyContextAssembler(): ConversationContextAssembler =
        ConversationContextAssembler(
            messagePort = object : MessageContextPort {
                override suspend fun listRecentMessages(
                    spaceId: String, sessionId: String, limit: Int
                ): List<ContextMessage> = emptyList()
            },
            memoryPort = object : MemoryContextPort {
                override suspend fun listMemoryReferences(
                    spaceId: String, sessionId: String, limit: Int
                ): List<MemoryReferenceContract> = emptyList()
            },
            errorPort = object : ErrorContextPort {
                override suspend fun listHistoricalErrors(
                    spaceId: String, sessionId: String, limit: Int
                ): List<ErrorReferenceContract> = emptyList()
            },
            graphPort = object : GraphContextPort {
                override suspend fun listPrerequisiteGaps(
                    spaceId: String, sessionId: String, limit: Int
                ): List<String> = emptyList()
                override suspend fun listPendingReviewPoints(
                    spaceId: String, sessionId: String, limit: Int
                ): List<String> = emptyList()
            },
            sourcePort = object : SourceContextPort {
                override suspend fun listSourceEvidence(
                    spaceId: String, sessionId: String, limit: Int, queryText: String
                ): List<SourceReferenceContract> = emptyList()
            }
        )

    private fun assertNoComposeTypes(clazz: Class<*>, seen: MutableSet<String>) {
        val name = clazz.name
        if (name in seen) return
        seen += name
        assertFalse(
            "$name must not be a Compose type",
            name.contains("compose", ignoreCase = true)
        )
        clazz.declaredFields.forEach { field ->
            assertNoComposeTypes(field.type, seen)
            val genericStr = field.genericType.typeName
            assertFalse(
                "$name.${field.name} generic type $genericStr must not be Compose",
                genericStr.contains("compose", ignoreCase = true)
            )
        }
    }
}
