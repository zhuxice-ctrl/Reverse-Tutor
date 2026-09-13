package com.reversetutor.core.domain

/**
 * Bounded, deterministic conversation context assembler.
 *
 * Reads from non-frozen source ports, applying:
 * - spaceId/sessionId isolation (ports receive both, never cross sessions);
 * - per-category list limits;
 * - text length caps;
 * - stable deterministic sorting (by timestamp descending, then id);
 * - partial-failure degradation: a single source failure returns an empty
 *   category and a safe [ContextWarning], without blocking other sources.
 *
 * This assembler does not call LLM, Repository internals, or Android APIs.
 */
class ConversationContextAssembler(
    private val messagePort: MessageContextPort,
    private val memoryPort: MemoryContextPort,
    private val errorPort: ErrorContextPort,
    private val graphPort: GraphContextPort,
    private val sourcePort: SourceContextPort,
    private val masteryFactPort: MasteryFactContextPort? = null,
    private val digestPort: SessionDigestContextPort? = null,
    private val messageLimit: Int = 10,
    private val memoryLimit: Int = 5,
    private val errorLimit: Int = 5,
    private val gapLimit: Int = 5,
    private val sourceLimit: Int = 5,
    private val reviewLimit: Int = 5,
    private val masteryFactLimit: Int = 200,
    private val masterySnapshotLimit: Int = 10,
    private val textCap: Int = 200,
    /** NEWMP-V1-024: source excerpts carry more context than other categories. */
    private val sourceTextCap: Int = 900,
    private val digestCap: Int = 1200
) {

    suspend fun assemble(
        spaceId: String,
        sessionId: String,
        queryText: String = ""
    ): ConversationContextContract {
        val warnings = mutableListOf<ContextWarning>()

        // Each source is read independently; failure degrades only that category.
        val messages = safeRead("message", warnings) {
            messagePort.listRecentMessages(spaceId, sessionId, messageLimit)
                .sortedWith(compareByDescending<ContextMessage> { it.timestampEpochMillis }
                    .thenBy { it.messageId })
                .map { it.copy(text = SessionTurnContracts.sanitizeContractText(it.text, textCap)) }
        }

        val memory = safeRead("memory", warnings) {
            memoryPort.listMemoryReferences(spaceId, sessionId, memoryLimit)
                .sortedWith(compareByDescending<MemoryReferenceContract> { it.updatedAtEpochMillis }
                    .thenBy { it.id })
                .map {
                    it.copy(
                        summary = SessionTurnContracts.sanitizeContractText(it.summary, textCap)
                    )
                }
        }

        val errors = safeRead("error", warnings) {
            errorPort.listHistoricalErrors(spaceId, sessionId, errorLimit)
                .sortedWith(compareByDescending<ErrorReferenceContract> { it.timestampEpochMillis }
                    .thenBy { it.id })
                .map {
                    it.copy(
                        errorType = SessionTurnContracts.sanitizeContractText(it.errorType, maxLength = 80),
                        description = SessionTurnContracts.sanitizeContractText(it.description, textCap)
                    )
                }
        }

        val gaps = safeRead("graph_gaps", warnings) {
            graphPort.listPrerequisiteGaps(spaceId, sessionId, gapLimit)
                .map { SessionTurnContracts.sanitizeContractText(it, textCap) }
                .filter { it.isNotBlank() }
        }

        val reviewPoints = safeRead("graph_review", warnings) {
            graphPort.listPendingReviewPoints(spaceId, sessionId, reviewLimit)
                .map { SessionTurnContracts.sanitizeContractText(it, textCap) }
                .filter { it.isNotBlank() }
        }

        val sources = safeRead("source", warnings) {
            sourcePort.listSourceEvidence(spaceId, sessionId, sourceLimit, queryText)
                .sortedWith(compareByDescending<SourceReferenceContract> { it.relevanceScore }
                    .thenBy { it.id })
                .map {
                    it.copy(
                        title = SessionTurnContracts.sanitizeContractText(it.title, textCap),
                        excerpt = SessionTurnContracts.sanitizeContractText(it.excerpt, sourceTextCap)
                    )
                }
        }

        // Optional mastery read-model: absent port => empty projections with
        // no warning; failing port => empty projections + warning, like every
        // other category.
        val mastery = masteryFactPort?.let { port ->
            safeRead("mastery", warnings) {
                MasteryLedgerProjection(snapshotLimit = masterySnapshotLimit)
                    .project(port.listMasteryFacts(spaceId, sessionId, masteryFactLimit))
            }
        } ?: emptyList()

        // Optional early-history digest (NEWMP-V1-017): absent port => blank
        // digest without warning; failing port => blank digest + warning,
        // mirroring the mastery degradation contract.
        val digest = digestPort?.let { port ->
            safeReadValue("digest", warnings) {
                SessionTurnContracts.sanitizeContractText(
                    port.loadEarlyHistoryDigest(spaceId, sessionId),
                    digestCap
                )
            }
        } ?: ""

        return ConversationContextContract(
            spaceId = spaceId,
            sessionId = sessionId,
            prerequisiteGaps = gaps,
            relatedMemory = memory,
            sourceEvidence = sources,
            historicalErrors = errors,
            pendingReviewKnowledgePoints = reviewPoints,
            recentMessages = messages,
            warnings = warnings,
            masteryProjections = mastery,
            earlyHistoryDigest = digest
        )
    }

    /**
     * Calls [block] and returns its result, or an empty list + warning on failure.
     * Only the failing category is affected; other categories proceed.
     */
    private suspend fun <T> safeRead(
        source: String,
        warnings: MutableList<ContextWarning>,
        block: suspend () -> List<T>
    ): List<T> = try {
        block()
    } catch (_: Exception) {
        warnings += ContextWarning(source, "source_unavailable")
        emptyList()
    }

    /**
     * Value-level sibling of [safeRead] for the digest source: returns the
     * block result, or an empty string + warning on failure.
     */
    private suspend fun safeReadValue(
        source: String,
        warnings: MutableList<ContextWarning>,
        block: suspend () -> String
    ): String = try {
        block()
    } catch (_: Exception) {
        warnings += ContextWarning(source, "source_unavailable")
        ""
    }
}
