package com.reversetutor.core.domain

/**
 * Conversation context contracts — safe, visual-agnostic read models for the
 * session assistant side-panel. These types carry only domain-safe data; they
 * never expose API keys, SecretStore references, raw Authorization headers,
 * Provider URLs, un-redacted exceptions, or internal DAO/Entity/protocol DTOs.
 *
 * Source ports are non-frozen domain interfaces. Concrete adapters backing
 * them may call existing frozen Repository methods but must translate results
 * into the safe contracts defined here before returning.
 */

// ---------------------------------------------------------------------------
// Safe read models
// ---------------------------------------------------------------------------

/** A bounded message reference for context display. */
data class ContextMessage(
    val messageId: String,
    val role: String,
    val text: String,
    val timestampEpochMillis: Long
)

/** A memory reference safe for UI display. */
data class MemoryReferenceContract(
    val id: String,
    val summary: String,
    val relevanceScore: Float,
    val updatedAtEpochMillis: Long
)

/** A historical error reference safe for UI display. */
data class ErrorReferenceContract(
    val id: String,
    val errorType: String,
    val description: String,
    val timestampEpochMillis: Long
)

/**
 * A source evidence reference safe for UI display.
 *
 * [sourceRevision] is a local, privacy-safe version token derived from the
 * source's identity and its (re-)import timestamp. Reprocessing or importing
 * the same logical source stamps a new revision so later turns can bind to the
 * newer material while already-captured snapshots keep the revision — and
 * therefore the content — they were built with. Defaulted so every pre-existing
 * construction site stays source-compatible.
 */
data class SourceReferenceContract(
    val id: String,
    val title: String,
    val excerpt: String,
    val sourceType: String,
    val relevanceScore: Float,
    val sourceRevision: String = ""
)

/** A safe warning emitted when a context source degrades. */
data class ContextWarning(
    val source: String,
    val message: String
)

/**
 * The full conversation context contract consumed by the side-panel.
 * Every list is bounded and deterministically sorted.
 *
 * [masteryProjections] carries the deterministic mastery read-model derived
 * from the append-only learning ledger (see [MasteryLedgerProjection]).
 * Defaulted so every pre-existing construction site stays compatible.
 */
data class ConversationContextContract(
    val spaceId: String,
    val sessionId: String,
    val prerequisiteGaps: List<String>,
    val relatedMemory: List<MemoryReferenceContract>,
    val sourceEvidence: List<SourceReferenceContract>,
    val historicalErrors: List<ErrorReferenceContract>,
    val pendingReviewKnowledgePoints: List<String>,
    val recentMessages: List<ContextMessage>,
    val warnings: List<ContextWarning>,
    val masteryProjections: List<MasterySnapshot> = emptyList(),
    /**
     * NEWMP-V1-017: compressed digest of the early conversation history
     * (legacy engine's early-dialogue summary). Defaulted so every
     * pre-existing construction site stays source-compatible; blank means
     * no summary has been generated yet.
     */
    val earlyHistoryDigest: String = ""
) {
    companion object {
        fun empty(spaceId: String, sessionId: String): ConversationContextContract =
            ConversationContextContract(
                spaceId = spaceId,
                sessionId = sessionId,
                prerequisiteGaps = emptyList(),
                relatedMemory = emptyList(),
                sourceEvidence = emptyList(),
                historicalErrors = emptyList(),
                pendingReviewKnowledgePoints = emptyList(),
                recentMessages = emptyList(),
                warnings = emptyList()
            )
    }
}

// ---------------------------------------------------------------------------
// Source ports (non-frozen domain interfaces)
// ---------------------------------------------------------------------------

/** Returns recent messages for a session, filtered by space+session. */
interface MessageContextPort {
    suspend fun listRecentMessages(
        spaceId: String,
        sessionId: String,
        limit: Int
    ): List<ContextMessage>
}

/** Returns memory references relevant to the session. */
interface MemoryContextPort {
    suspend fun listMemoryReferences(
        spaceId: String,
        sessionId: String,
        limit: Int
    ): List<MemoryReferenceContract>
}

/** Returns historical error references for the session. */
interface ErrorContextPort {
    suspend fun listHistoricalErrors(
        spaceId: String,
        sessionId: String,
        limit: Int
    ): List<ErrorReferenceContract>
}

/** Returns graph-derived prerequisite gaps and pending review points. */
interface GraphContextPort {
    suspend fun listPrerequisiteGaps(
        spaceId: String,
        sessionId: String,
        limit: Int
    ): List<String>

    suspend fun listPendingReviewPoints(
        spaceId: String,
        sessionId: String,
        limit: Int
    ): List<String>
}

/**
 * Returns source evidence references for the session.
 *
 * NEWMP-V1-024: [queryText] lets implementations rank sources by semantic or
 * keyword relevance to the current question; blank keeps the legacy
 * newest-first behavior. Defaulted so existing callers stay source-compatible.
 */
interface SourceContextPort {
    suspend fun listSourceEvidence(
        spaceId: String,
        sessionId: String,
        limit: Int,
        queryText: String = ""
    ): List<SourceReferenceContract>
}

/**
 * Returns recent learning-fact receipts backing the mastery read-model.
 *
 * The append-only ledger is space-scoped (mirroring [MemoryContextPort] and
 * [SourceContextPort] scoping caveats); adapters must translate repository
 * results into the domain [LearningFactReceipt] contract before returning.
 * The deterministic fold itself ([MasteryLedgerProjection]) isolates scores
 * per knowledge point.
 */
interface MasteryFactContextPort {
    suspend fun listMasteryFacts(
        spaceId: String,
        sessionId: String,
        limit: Int
    ): List<LearningFactReceipt>
}

/**
 * NEWMP-V1-017: returns the stored early-history digest for a session —
 * the compressed summary of the conversation prefix that is no longer
 * replayed verbatim. Adapters back it with lightweight local storage and
 * return an empty string when nothing is stored.
 */
interface SessionDigestContextPort {
    suspend fun loadEarlyHistoryDigest(
        spaceId: String,
        sessionId: String
    ): String
}
