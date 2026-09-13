package com.reversetutor.preview.wiring.session

import com.reversetutor.core.data.graph.GraphRepository
import com.reversetutor.core.data.learning.LearningLedgerRepository
import com.reversetutor.core.data.memory.MemoryRepository
import com.reversetutor.core.data.message.MessageRepository
import com.reversetutor.core.data.sources.SourceRepository
import com.reversetutor.core.data.sources.SourceWithChunks
import com.reversetutor.core.domain.ContextMessage
import com.reversetutor.core.domain.ErrorContextPort
import com.reversetutor.core.domain.ErrorReferenceContract
import com.reversetutor.core.domain.GraphContextPort
import com.reversetutor.core.domain.LearningFactReceipt
import com.reversetutor.core.domain.MasteryFactContextPort
import com.reversetutor.core.domain.MasteryLedgerProjection
import com.reversetutor.core.domain.MemoryContextPort
import com.reversetutor.core.domain.MemoryReferenceContract
import com.reversetutor.core.domain.MessageContextPort
import com.reversetutor.core.domain.SourceContextPort
import com.reversetutor.core.domain.SourceReferenceContract
import com.reversetutor.core.model.SourceChunk
import com.reversetutor.core.model.SourceRecord
import com.reversetutor.core.model.GraphNodeKind
import com.reversetutor.core.model.GraphNodeStatus
import com.reversetutor.core.model.GraphScope
import com.reversetutor.core.model.GraphSnapshotResult
import com.reversetutor.core.model.MemoryItemKind

/**
 * Adapts existing repository read capabilities to the non-frozen conversation
 * context source ports. Each adapter translates frozen repository results into
 * the safe domain contracts defined in `core:domain`.
 *
 * Scoping caveats (see tasks/native-p2-007-api-fact-map.md §5): the frozen
 * `MemoryRepository` and `SourceRepository` are space-scoped, not
 * session-scoped. The adapters faithfully return the space's data and do not
 * fabricate session-level filtering. The assembler's bounded read + partial
 * failure semantics turn empty data into empty categories (never failures).
 */

class MessageContextPortAdapter(
    private val messageRepository: MessageRepository
) : MessageContextPort {
    override suspend fun listRecentMessages(
        spaceId: String,
        sessionId: String,
        limit: Int
    ): List<ContextMessage> =
        messageRepository.listMessages(sessionId)
            .takeLast(limit)
            .map { ContextMessage(it.id, it.role.name.lowercase(), it.text, it.createdAtEpochMillis) }
}

class MemoryContextPortAdapter(
    private val memoryRepository: MemoryRepository
) : MemoryContextPort {
    override suspend fun listMemoryReferences(
        spaceId: String,
        sessionId: String,
        limit: Int
    ): List<MemoryReferenceContract> =
        memoryRepository.snapshot(spaceId).items
            .filter { it.kind != MemoryItemKind.Error }
            .sortedByDescending { it.createdAtEpochMillis }
            .take(limit)
            .map { MemoryReferenceContract(it.id, it.title, 0f, it.createdAtEpochMillis) }
}

class ErrorContextPortAdapter(
    private val memoryRepository: MemoryRepository
) : ErrorContextPort {
    override suspend fun listHistoricalErrors(
        spaceId: String,
        sessionId: String,
        limit: Int
    ): List<ErrorReferenceContract> =
        memoryRepository.snapshot(spaceId).errors
            .filterNot { it.resolved }
            .sortedByDescending { it.createdAtEpochMillis }
            .take(limit)
            .map { ErrorReferenceContract(it.id, it.code ?: it.title, it.title, it.createdAtEpochMillis) }
}

class GraphContextPortAdapter(
    private val graphRepository: GraphRepository,
    private val learningLedgerRepository: LearningLedgerRepository? = null,
    private val nowEpochMillis: () -> Long = System::currentTimeMillis
) : GraphContextPort {

    private suspend fun sessionNodes(sessionId: String): List<com.reversetutor.core.model.GraphNode> =
        when (val result = graphRepository.snapshot(GraphScope.Session(sessionId))) {
            is GraphSnapshotResult.Ready -> result.snapshot.nodes
            is GraphSnapshotResult.Empty -> emptyList()
            is GraphSnapshotResult.Error -> emptyList()
        }

    override suspend fun listPrerequisiteGaps(
        spaceId: String,
        sessionId: String,
        limit: Int
    ): List<String> =
        sessionNodes(sessionId)
            .filter { it.kind == GraphNodeKind.Requirement || it.status == GraphNodeStatus.NeedsReview }
            .map { it.label }
            .distinct()
            .take(limit)

    override suspend fun listPendingReviewPoints(
        spaceId: String,
        sessionId: String,
        limit: Int
    ): List<String> {
        // Old-parity due-review selection (legacy `list_due_reviews`): the
        // deterministic mastery ladder decides which knowledge points are due
        // at read time; no persisted schedule and no new write side. Due
        // points come first (earliest-due ordering), then graph NeedsReview
        // labels, deduplicated and bounded by [limit].
        val due = learningLedgerRepository
            ?.let { repo ->
                MasteryLedgerProjection(snapshotLimit = DueProjectionSnapshotLimit)
                    .projectDue(repo.listLearningFacts(spaceId), nowEpochMillis())
            }
            .orEmpty()
        val graphLabels = sessionNodes(sessionId)
            .filter { it.status == GraphNodeStatus.NeedsReview }
            .map { it.label }
        return (due + graphLabels)
            .map { it.trim() }
            .filter { it.isNotBlank() }
            .distinct()
            .take(limit)
    }

    private companion object {
        // Wider than the assembler's top-10 evidence cap so low-score but
        // due knowledge points are not starved by the score sort before the
        // due filter runs; the caller still bounds the final list.
        const val DueProjectionSnapshotLimit = 50
    }
}

class SourceContextPortAdapter(
    private val sourceRepository: SourceRepository,
    /**
     * NEWMP-V1-024: embeds the current query for semantic (vector) ranking.
     * Absent, or returning null (no runtime, unsupported channel, failed call),
     * degrades to keyword ranking, preserving the old behavior.
     */
    private val embedQuery: (suspend (String) -> FloatArray?)? = null
) : SourceContextPort {
    override suspend fun listSourceEvidence(
        spaceId: String,
        sessionId: String,
        limit: Int,
        queryText: String
    ): List<SourceReferenceContract> {
        val entries = sourceRepository.listSourcesWithChunks(spaceId)
        val ranked = vectorRankedEntries(spaceId, entries, queryText)
            ?: keywordRankedEntries(entries, queryText)
        return ranked
            .take(limit)
            .map { entry ->
                SourceReferenceContract(
                    id = entry.source.id,
                    title = entry.source.title,
                    excerpt = entry.chunk?.text ?: "",
                    sourceType = entry.source.type.name,
                    relevanceScore = entry.score,
                    // Local version token: import/reprocessing stamps a new
                    // createdAt, so the next turn binds the newer revision while
                    // already-saved snapshots keep the revision they captured.
                    sourceRevision = "rev-${entry.source.id}-${entry.source.createdAtEpochMillis}"
                )
            }
    }

    /**
     * NEWMP-V1-024: semantic ranking. Embeds the query, scores every chunk that
     * has a stored embedding by cosine similarity, keeps each source's best
     * chunk, and drops sources below [MinVectorScore]. Returns null whenever
     * vector retrieval is not usable so the caller falls back to keywords.
     */
    private suspend fun vectorRankedEntries(
        spaceId: String,
        entries: List<SourceWithChunks>,
        queryText: String
    ): List<RankedSourceEntry>? {
        val trimmed = queryText.trim()
        if (trimmed.isEmpty()) return null
        val embed = embedQuery ?: return null
        if (entries.isEmpty()) return null
        val embeddings = sourceRepository.listChunkEmbeddings(spaceId)
        if (embeddings.isEmpty()) return null
        val queryVector = embed(trimmed) ?: return null
        val ranked = entries.mapNotNull { entry ->
            entry.chunks
                .mapNotNull { chunk ->
                    val vector = embeddings[chunk.id] ?: return@mapNotNull null
                    if (vector.size != queryVector.size) return@mapNotNull null
                    val score = cosineSimilarity(queryVector, vector)
                    if (score < MinVectorScore) null else RankedSourceEntry(entry.source, chunk, score)
                }
                .maxByOrNull { it.score }
        }
        if (ranked.isEmpty()) return null
        return ranked.sortedWith(
            compareByDescending<RankedSourceEntry> { it.score }.thenBy { it.source.id }
        )
    }

    /**
     * NEWMP-V1-024: keyword fallback. A blank query keeps the legacy
     * newest-first ordering with a neutral score; otherwise each source is
     * scored by how many query terms its best chunk contains, and sources
     * matching nothing are dropped.
     */
    private fun keywordRankedEntries(
        entries: List<SourceWithChunks>,
        queryText: String
    ): List<RankedSourceEntry> {
        val terms = queryText.trim()
            .lowercase()
            .split(Regex("\\s+"))
            .filter { it.isNotBlank() }
        if (terms.isEmpty()) {
            return entries
                .sortedByDescending { it.source.createdAtEpochMillis }
                .map { RankedSourceEntry(it.source, it.chunks.firstOrNull(), 0f) }
        }
        return entries.mapNotNull { entry ->
            entry.chunks
                .map { chunk -> keywordScore(chunk.text.lowercase(), terms) to chunk }
                .filter { (score, _) -> score > 0f }
                .maxByOrNull { it.first }
                ?.let { RankedSourceEntry(entry.source, it.second, it.first) }
        }.sortedWith(
            compareByDescending<RankedSourceEntry> { it.score }.thenBy { it.source.id }
        )
    }

    private fun keywordScore(text: String, terms: List<String>): Float {
        var hits = 0
        terms.forEach { term ->
            if (text.contains(term)) hits += 1
        }
        return hits.toFloat()
    }

    private fun cosineSimilarity(a: FloatArray, b: FloatArray): Float {
        var dot = 0f
        var normA = 0f
        var normB = 0f
        for (index in a.indices) {
            dot += a[index] * b[index]
            normA += a[index] * a[index]
            normB += b[index] * b[index]
        }
        val denominator = kotlin.math.sqrt(normA) * kotlin.math.sqrt(normB)
        if (denominator <= 0f) return 0f
        return dot / denominator
    }

    private data class RankedSourceEntry(
        val source: SourceRecord,
        val chunk: SourceChunk?,
        val score: Float
    )

    private companion object {
        /** Similarity floor: weaker matches fall back to keyword ranking. */
        const val MinVectorScore = 0.30f
    }
}

class MasteryFactContextPortAdapter(
    private val learningLedgerRepository: LearningLedgerRepository
) : MasteryFactContextPort {
    override suspend fun listMasteryFacts(
        spaceId: String,
        sessionId: String,
        limit: Int
    ): List<LearningFactReceipt> =
        learningLedgerRepository.listLearningFacts(spaceId)
            // Space-scoped like Memory/Source adapters: the append-only ledger
            // is keyed by space, and the deterministic mastery fold isolates
            // scores per knowledge point. Newest receipts first so the bounded
            // read keeps the most recent evidence.
            .sortedByDescending { it.occurredAtEpochMillis }
            .take(limit)
}
