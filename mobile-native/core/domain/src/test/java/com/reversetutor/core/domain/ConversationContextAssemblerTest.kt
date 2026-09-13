package com.reversetutor.core.domain

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Tests for [ConversationContextAssembler]:
 * - session/space isolation,
 * - deterministic ordering,
 * - per-category limits,
 * - partial-failure degradation,
 * - text length caps,
 * - no secret-like fields.
 */
class ConversationContextAssemblerTest {

    // --- Fake ports for testing --------------------------------------------

    private class FakeMessagePort(
        val items: List<ContextMessage> = emptyList(),
        val shouldFail: Boolean = false
    ) : MessageContextPort {
        override suspend fun listRecentMessages(spaceId: String, sessionId: String, limit: Int): List<ContextMessage> {
            if (shouldFail) throw RuntimeException("connection error")
            return items.take(limit)
        }
    }

    private class FakeMemoryPort(
        val items: List<MemoryReferenceContract> = emptyList(),
        val shouldFail: Boolean = false
    ) : MemoryContextPort {
        override suspend fun listMemoryReferences(spaceId: String, sessionId: String, limit: Int): List<MemoryReferenceContract> {
            if (shouldFail) throw RuntimeException("db timeout")
            return items.take(limit)
        }
    }

    private class FakeErrorPort(
        val items: List<ErrorReferenceContract> = emptyList(),
        val shouldFail: Boolean = false
    ) : ErrorContextPort {
        override suspend fun listHistoricalErrors(spaceId: String, sessionId: String, limit: Int): List<ErrorReferenceContract> {
            if (shouldFail) throw RuntimeException("table missing")
            return items.take(limit)
        }
    }

    private class FakeGraphPort(
        val gaps: List<String> = emptyList(),
        val reviewPoints: List<String> = emptyList(),
        val shouldFailGaps: Boolean = false,
        val shouldFailReview: Boolean = false
    ) : GraphContextPort {
        override suspend fun listPrerequisiteGaps(spaceId: String, sessionId: String, limit: Int): List<String> {
            if (shouldFailGaps) throw RuntimeException("graph unreachable")
            return gaps.take(limit)
        }
        override suspend fun listPendingReviewPoints(spaceId: String, sessionId: String, limit: Int): List<String> {
            if (shouldFailReview) throw RuntimeException("graph unreachable")
            return reviewPoints.take(limit)
        }
    }

    private class FakeSourcePort(
        val items: List<SourceReferenceContract> = emptyList(),
        val shouldFail: Boolean = false
    ) : SourceContextPort {
        override suspend fun listSourceEvidence(spaceId: String, sessionId: String, limit: Int, queryText: String): List<SourceReferenceContract> {
            if (shouldFail) throw RuntimeException("network down")
            return items.take(limit)
        }
    }

    private class FakeMasteryFactPort(
        val items: List<LearningFactReceipt> = emptyList(),
        val shouldFail: Boolean = false
    ) : MasteryFactContextPort {
        override suspend fun listMasteryFacts(
            spaceId: String,
            sessionId: String,
            limit: Int
        ): List<LearningFactReceipt> {
            if (shouldFail) throw RuntimeException("ledger unreadable")
            return items.take(limit)
        }
    }

    private class FakeDigestPort(
        val digest: String = "",
        val shouldFail: Boolean = false
    ) : SessionDigestContextPort {
        override suspend fun loadEarlyHistoryDigest(spaceId: String, sessionId: String): String {
            if (shouldFail) throw RuntimeException("prefs unreadable")
            return digest
        }
    }

    // --- Tests --------------------------------------------------------------

    @Test
    fun emptyContextWhenAllSourcesEmpty() = runBlocking {
        val assembler = ConversationContextAssembler(
            messagePort = FakeMessagePort(),
            memoryPort = FakeMemoryPort(),
            errorPort = FakeErrorPort(),
            graphPort = FakeGraphPort(),
            sourcePort = FakeSourcePort()
        )
        val ctx = assembler.assemble("space1", "session1")
        assertEquals("space1", ctx.spaceId)
        assertEquals("session1", ctx.sessionId)
        assertTrue(ctx.prerequisiteGaps.isEmpty())
        assertTrue(ctx.relatedMemory.isEmpty())
        assertTrue(ctx.sourceEvidence.isEmpty())
        assertTrue(ctx.historicalErrors.isEmpty())
        assertTrue(ctx.pendingReviewKnowledgePoints.isEmpty())
        assertTrue(ctx.recentMessages.isEmpty())
    }

    @Test
    fun perCategoryLimitsAreEnforced() = runBlocking {
        val manyMessages = (1..20).map {
            ContextMessage("${it}", "user", "msg$it", it.toLong())
        }
        val manyMemory = (1..10).map {
            MemoryReferenceContract("m$it", "mem$it", 0.5f, it.toLong())
        }
        val assembler = ConversationContextAssembler(
            messagePort = FakeMessagePort(items = manyMessages),
            memoryPort = FakeMemoryPort(items = manyMemory),
            errorPort = FakeErrorPort(),
            graphPort = FakeGraphPort(),
            sourcePort = FakeSourcePort(),
            messageLimit = 5,
            memoryLimit = 3
        )
        val ctx = assembler.assemble("s", "se")
        assertEquals(5, ctx.recentMessages.size)
        assertEquals(3, ctx.relatedMemory.size)
    }

    @Test
    fun messagesAreSortedByTimestampDescending() = runBlocking {
        val messages = listOf(
            ContextMessage("a", "user", "old", 100),
            ContextMessage("b", "user", "new", 300),
            ContextMessage("c", "user", "mid", 200)
        )
        val assembler = ConversationContextAssembler(
            messagePort = FakeMessagePort(items = messages),
            memoryPort = FakeMemoryPort(),
            errorPort = FakeErrorPort(),
            graphPort = FakeGraphPort(),
            sourcePort = FakeSourcePort()
        )
        val ctx = assembler.assemble("s", "se")
        assertEquals("b", ctx.recentMessages[0].messageId)
        assertEquals("c", ctx.recentMessages[1].messageId)
        assertEquals("a", ctx.recentMessages[2].messageId)
    }

    @Test
    fun sourceEvidenceSortedByRelevanceDescending() = runBlocking {
        val sources = listOf(
            SourceReferenceContract("a", "Title A", "excerpt", "text", 0.3f),
            SourceReferenceContract("b", "Title B", "excerpt", "text", 0.9f),
            SourceReferenceContract("c", "Title C", "excerpt", "text", 0.6f)
        )
        val assembler = ConversationContextAssembler(
            messagePort = FakeMessagePort(),
            memoryPort = FakeMemoryPort(),
            errorPort = FakeErrorPort(),
            graphPort = FakeGraphPort(),
            sourcePort = FakeSourcePort(items = sources)
        )
        val ctx = assembler.assemble("s", "se")
        assertEquals("b", ctx.sourceEvidence[0].id)
        assertEquals("c", ctx.sourceEvidence[1].id)
        assertEquals("a", ctx.sourceEvidence[2].id)
    }

    @Test
    fun textLengthIsCapped() = runBlocking {
        val longText = "x".repeat(500)
        val messages = listOf(ContextMessage("m1", "user", longText, 1))
        val assembler = ConversationContextAssembler(
            messagePort = FakeMessagePort(items = messages),
            memoryPort = FakeMemoryPort(),
            errorPort = FakeErrorPort(),
            graphPort = FakeGraphPort(),
            sourcePort = FakeSourcePort(),
            textCap = 50
        )
        val ctx = assembler.assemble("s", "se")
        assertTrue(ctx.recentMessages[0].text.length <= 50)
    }

    @Test
    fun messageSourceFailureDegradesOnlyMessages() = runBlocking {
        val assembler = ConversationContextAssembler(
            messagePort = FakeMessagePort(shouldFail = true),
            memoryPort = FakeMemoryPort(items = listOf(MemoryReferenceContract("m1", "mem", 0.5f, 1))),
            errorPort = FakeErrorPort(),
            graphPort = FakeGraphPort(gaps = listOf("gap1")),
            sourcePort = FakeSourcePort()
        )
        val ctx = assembler.assemble("s", "se")
        // message failed → empty + warning
        assertTrue(ctx.recentMessages.isEmpty())
        // memory survived
        assertEquals(1, ctx.relatedMemory.size)
        // graph survived
        assertEquals(1, ctx.prerequisiteGaps.size)
        // warning recorded for message
        assertTrue(ctx.warnings.any { it.source == "message" })
    }

    @Test
    fun graphFailureDegradesOnlyGraph() = runBlocking {
        val assembler = ConversationContextAssembler(
            messagePort = FakeMessagePort(items = listOf(ContextMessage("m1", "user", "hi", 1))),
            memoryPort = FakeMemoryPort(),
            errorPort = FakeErrorPort(),
            graphPort = FakeGraphPort(shouldFailGaps = true),
            sourcePort = FakeSourcePort()
        )
        val ctx = assembler.assemble("s", "se")
        // graph failed → empty gaps
        assertTrue(ctx.prerequisiteGaps.isEmpty())
        // message survived
        assertEquals(1, ctx.recentMessages.size)
        // warning recorded
        assertTrue(ctx.warnings.any { it.source == "graph_gaps" })
    }

    @Test
    fun noSecretLikeFieldsExist() = runBlocking {
        val assembler = ConversationContextAssembler(
            messagePort = FakeMessagePort(),
            memoryPort = FakeMemoryPort(),
            errorPort = FakeErrorPort(),
            graphPort = FakeGraphPort(),
            sourcePort = FakeSourcePort()
        )
        val ctx = assembler.assemble("s", "se")
        // Contract fields must not contain sensitive identifiers
        val allStrings = buildList {
            addAll(ctx.prerequisiteGaps)
            addAll(ctx.pendingReviewKnowledgePoints)
            ctx.relatedMemory.forEach { addAll(listOf(it.id, it.summary)) }
            ctx.sourceEvidence.forEach { addAll(listOf(it.id, it.title, it.excerpt)) }
            ctx.historicalErrors.forEach { addAll(listOf(it.id, it.description)) }
            ctx.recentMessages.forEach { add(it.text) }
            ctx.warnings.forEach { addAll(listOf(it.source, it.message)) }
        }
        for (s in allStrings) {
            assertTrue("no sk- prefix: $s", !s.contains("sk-"))
            assertTrue("no Authorization: $s", !s.contains("Authorization"))
            assertTrue("no Bearer: $s", !s.contains("Bearer"))
        }
    }

    @Test
    fun contextTextRedactsCredentialAndUrlPatterns() = runBlocking {
        val assembler = ConversationContextAssembler(
            messagePort = object : MessageContextPort {
                override suspend fun listRecentMessages(spaceId: String, sessionId: String, limit: Int) =
                    listOf(ContextMessage("m1", "user", "Authorization: Bearer sk-secret https://provider.example", 1L))
            },
            memoryPort = FakeMemoryPort(),
            errorPort = FakeErrorPort(),
            graphPort = FakeGraphPort(),
            sourcePort = FakeSourcePort()
        )

        val text = assembler.assemble("s1", "se1").recentMessages.single().text
        assertTrue(text.contains("[redacted]"))
        assertTrue(!text.contains("sk-secret"))
        assertTrue(!text.contains("https://"))
    }

    @Test
    fun sessionIsolationInMessagePort() = runBlocking {
        val messages = listOf(
            ContextMessage("space1_sess1_a", "user", "msg A", 1),
            ContextMessage("space1_sess2_b", "user", "msg B", 2)
        )
        val assembler = ConversationContextAssembler(
            messagePort = object : MessageContextPort {
                override suspend fun listRecentMessages(spaceId: String, sessionId: String, limit: Int) =
                    messages.filter { it.messageId.startsWith("${spaceId}_${sessionId}_") }.take(limit)
            },
            memoryPort = FakeMemoryPort(),
            errorPort = FakeErrorPort(),
            graphPort = FakeGraphPort(),
            sourcePort = FakeSourcePort()
        )
        val ctx = assembler.assemble("space1", "sess1")
        // Only messages matching space1_sess1 should be returned
        assertEquals(1, ctx.recentMessages.size)
        assertEquals("space1_sess1_a", ctx.recentMessages[0].messageId)
    }

    @Test
    fun emptyContractHasCorrectIdentity() {
        val empty = ConversationContextContract.empty("s1", "se1")
        assertEquals("s1", empty.spaceId)
        assertEquals("se1", empty.sessionId)
        assertTrue(empty.prerequisiteGaps.isEmpty())
        assertTrue(empty.warnings.isEmpty())
    }

    @Test
    fun masteryFactsAreProjectedWhenPortWired() = runBlocking {
        val facts = listOf(
            LearningFactReceipt(
                knowledgePoint = "因式分解",
                evidenceType = "explanation",
                result = "passed",
                confidence = 0.8f,
                sourceWindowId = "w1",
                sourceTurnId = "t1",
                occurredAtEpochMillis = 1L
            )
        )
        val assembler = ConversationContextAssembler(
            messagePort = FakeMessagePort(),
            memoryPort = FakeMemoryPort(),
            errorPort = FakeErrorPort(),
            graphPort = FakeGraphPort(),
            sourcePort = FakeSourcePort(),
            masteryFactPort = FakeMasteryFactPort(items = facts)
        )
        val ctx = assembler.assemble("s", "se")
        assertEquals(1, ctx.masteryProjections.size)
        assertEquals("因式分解", ctx.masteryProjections[0].knowledgePoint)
        // 0.35 * 35 = 12.25, mirroring the legacy upsert_mastery fold.
        assertEquals(12.25f, ctx.masteryProjections[0].score, 0.001f)
        assertTrue(ctx.warnings.none { it.source == "mastery" })
    }

    @Test
    fun masteryPortFailureDegradesOnlyMastery() = runBlocking {
        val assembler = ConversationContextAssembler(
            messagePort = FakeMessagePort(items = listOf(ContextMessage("m1", "user", "hi", 1))),
            memoryPort = FakeMemoryPort(),
            errorPort = FakeErrorPort(),
            graphPort = FakeGraphPort(),
            sourcePort = FakeSourcePort(),
            masteryFactPort = FakeMasteryFactPort(shouldFail = true)
        )
        val ctx = assembler.assemble("s", "se")
        assertTrue(ctx.masteryProjections.isEmpty())
        assertEquals(1, ctx.recentMessages.size)
        assertTrue(ctx.warnings.any { it.source == "mastery" })
    }

    @Test
    fun masteryPortAbsentYieldsEmptyProjectionsWithoutWarning() = runBlocking {
        val assembler = ConversationContextAssembler(
            messagePort = FakeMessagePort(),
            memoryPort = FakeMemoryPort(),
            errorPort = FakeErrorPort(),
            graphPort = FakeGraphPort(),
            sourcePort = FakeSourcePort()
        )
        val ctx = assembler.assemble("s", "se")
        assertTrue(ctx.masteryProjections.isEmpty())
        assertTrue(ctx.warnings.none { it.source == "mastery" })
    }

    @Test
    fun digestPortSuppliesSanitizedEarlyHistoryDigest() = runBlocking {
        val assembler = ConversationContextAssembler(
            messagePort = FakeMessagePort(),
            memoryPort = FakeMemoryPort(),
            errorPort = FakeErrorPort(),
            graphPort = FakeGraphPort(),
            sourcePort = FakeSourcePort(),
            digestPort = FakeDigestPort(digest = "x".repeat(2_000)),
            digestCap = 1_200
        )
        val ctx = assembler.assemble("s", "se")
        assertTrue(ctx.earlyHistoryDigest.length <= 1_200)
        assertTrue(ctx.warnings.none { it.source == "digest" })
    }

    @Test
    fun digestPortFailureDegradesToEmptyDigestWithWarning() = runBlocking {
        val assembler = ConversationContextAssembler(
            messagePort = FakeMessagePort(),
            memoryPort = FakeMemoryPort(),
            errorPort = FakeErrorPort(),
            graphPort = FakeGraphPort(),
            sourcePort = FakeSourcePort(),
            digestPort = FakeDigestPort(shouldFail = true)
        )
        val ctx = assembler.assemble("s", "se")
        assertEquals("", ctx.earlyHistoryDigest)
        assertTrue(ctx.warnings.any { it.source == "digest" })
    }
}
