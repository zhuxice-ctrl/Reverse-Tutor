package com.reversetutor.preview.wiring.session

import com.reversetutor.core.domain.ConversationContextAssembler
import com.reversetutor.core.domain.ContextMessage
import com.reversetutor.core.domain.ErrorContextPort
import com.reversetutor.core.domain.ErrorReferenceContract
import com.reversetutor.core.domain.GraphContextPort
import com.reversetutor.core.domain.MemoryContextPort
import com.reversetutor.core.domain.MemoryReferenceContract
import com.reversetutor.core.domain.MessageContextPort
import com.reversetutor.core.domain.SourceContextPort
import com.reversetutor.core.domain.SourceReferenceContract
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

/**
 * Scenario 5: 空数据不被错误标为数据源失败.
 *
 * The wiring's context adapters return empty lists when the underlying
 * repositories return empty data (no exception). The [ConversationContextAssembler]
 * turns an empty return into an empty category with **no** warning — only an
 * actual exception produces a `source_unavailable` warning. This test proves the
 * distinction: empty data is not a failure.
 */
class ConversationContextEmptyDataTest {

    @Test
    fun `empty port data yields empty categories with no warnings, not a failure`() = runTest {
        val assembler = ConversationContextAssembler(
            messagePort = emptyMessagePort(),
            memoryPort = emptyMemoryPort(),
            errorPort = emptyErrorPort(),
            graphPort = emptyGraphPort(),
            sourcePort = emptySourcePort()
        )
        val context = assembler.assemble("space-1", "session-1")
        // All categories are empty...
        assertTrue(context.prerequisiteGaps.isEmpty())
        assertTrue(context.relatedMemory.isEmpty())
        assertTrue(context.sourceEvidence.isEmpty())
        assertTrue(context.historicalErrors.isEmpty())
        assertTrue(context.pendingReviewKnowledgePoints.isEmpty())
        assertTrue(context.recentMessages.isEmpty())
        // ...but there are NO warnings — empty data is NOT flagged as a source failure.
        assertTrue(
            "empty data must not produce source_unavailable warnings",
            context.warnings.isEmpty()
        )
        assertEquals("space-1", context.spaceId)
        assertEquals("session-1", context.sessionId)
    }

    @Test
    fun `a port that throws degrades to empty category plus a warning, proving the distinction`() = runTest {
        val assembler = ConversationContextAssembler(
            messagePort = object : MessageContextPort {
                override suspend fun listRecentMessages(
                    spaceId: String, sessionId: String, limit: Int
                ): List<ContextMessage> = throw RuntimeException("storage unavailable")
            },
            memoryPort = emptyMemoryPort(),
            errorPort = emptyErrorPort(),
            graphPort = emptyGraphPort(),
            sourcePort = emptySourcePort()
        )
        val context = assembler.assemble("space-1", "session-1")
        // The throwing source degrades to empty...
        assertTrue(context.recentMessages.isEmpty())
        // ...and produces exactly one warning — an actual failure, distinct from empty data.
        assertEquals(1, context.warnings.size)
        assertEquals("message", context.warnings[0].source)
        assertEquals("source_unavailable", context.warnings[0].message)
    }

    private fun emptyMessagePort() = object : MessageContextPort {
        override suspend fun listRecentMessages(
            spaceId: String, sessionId: String, limit: Int
        ): List<ContextMessage> = emptyList()
    }

    private fun emptyMemoryPort() = object : MemoryContextPort {
        override suspend fun listMemoryReferences(
            spaceId: String, sessionId: String, limit: Int
        ): List<MemoryReferenceContract> = emptyList()
    }

    private fun emptyErrorPort() = object : ErrorContextPort {
        override suspend fun listHistoricalErrors(
            spaceId: String, sessionId: String, limit: Int
        ): List<ErrorReferenceContract> = emptyList()
    }

    private fun emptyGraphPort() = object : GraphContextPort {
        override suspend fun listPrerequisiteGaps(
            spaceId: String, sessionId: String, limit: Int
        ): List<String> = emptyList()
        override suspend fun listPendingReviewPoints(
            spaceId: String, sessionId: String, limit: Int
        ): List<String> = emptyList()
    }

    private fun emptySourcePort() = object : SourceContextPort {
        override suspend fun listSourceEvidence(
            spaceId: String, sessionId: String, limit: Int, queryText: String
        ): List<SourceReferenceContract> = emptyList()
    }
}
