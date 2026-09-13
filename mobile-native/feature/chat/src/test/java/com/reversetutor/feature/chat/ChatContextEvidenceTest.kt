package com.reversetutor.feature.chat

import com.reversetutor.core.data.local.dao.MemoryDao
import com.reversetutor.core.data.local.dao.SourceChunkEmbeddingRow
import com.reversetutor.core.data.local.dao.SourceDao
import com.reversetutor.core.data.local.entity.AnchorEntity
import com.reversetutor.core.data.local.entity.ErrorLogEntity
import com.reversetutor.core.data.local.entity.MemoryItemEntity
import com.reversetutor.core.data.local.entity.NoteEntity
import com.reversetutor.core.data.local.entity.SourceChunkEntity
import com.reversetutor.core.data.local.entity.SourceEntity
import com.reversetutor.core.data.memory.AnchorInput
import com.reversetutor.core.data.memory.MemoryRepository
import com.reversetutor.core.data.sources.SourceImportInput
import com.reversetutor.core.data.sources.SourceRepository
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ChatContextEvidenceTest {
    @Test
    fun contextEvidenceUsesRelevantMemoryAndLocalSourceChunks() = runBlocking {
        val memoryRepository = MemoryRepository(FakeMemoryDao(), defaultSpaceId = "space-1")
        val sourceRepository = SourceRepository(FakeSourceDao(), defaultSpaceId = "space-1")
        memoryRepository.createAnchor(
            input = AnchorInput(
                title = "Factoring anchor",
                body = "Difference of squares is relevant.",
                sourceMessageId = "message-1",
                sourceId = "source-1"
            ),
            nowEpochMillis = 100L,
            anchorId = "anchor-1"
        )
        sourceRepository.importSource(
            input = SourceImportInput(
                requestId = 1L,
                fileName = "algebra.md",
                text = "Factoring difference of squares.\n\nUnrelated graph note.",
                sourceId = "source-1"
            ),
            nowEpochMillis = 90L
        )
        sourceRepository.importSource(
            input = SourceImportInput(
                requestId = 2L,
                fileName = "scan.pdf",
                mimeType = "application/pdf",
                sourceId = "source-pdf"
            ),
            nowEpochMillis = 80L
        )

        val evidence = buildChatContextEvidence(
            userText = "Help with factoring",
            memoryRepository = memoryRepository,
            sourceRepository = sourceRepository
        )

        assertEquals(listOf("Factoring anchor", "algebra.md"), evidence.map { it.title })
        assertTrue(evidence.none { it.id == "source-pdf" })
        assertEquals("message-1", evidence.first().sourceMessageId)
    }

    @Test
    fun contextEvidenceGracefullyReturnsEmptyWhenRepositoriesAreMissing() = runBlocking {
        val evidence = buildChatContextEvidence(
            userText = "anything",
            memoryRepository = null,
            sourceRepository = null
        )

        assertTrue(evidence.isEmpty())
    }

    @Test
    fun chatRouteEvidenceUsesLatestSnapshotAndOnlyItsSelectedSources() = runBlocking {
        val sourceRepository = SourceRepository(FakeSourceDao(), defaultSpaceId = "space-1")
        listOf("selected" to "selected body", "unselected" to "unselected body").forEachIndexed { index, (id, body) ->
            sourceRepository.importSource(
                SourceImportInput(index.toLong(), "$id.md", text = body, sourceId = id),
                nowEpochMillis = index.toLong()
            )
        }
        val snapshot = NewSessionConfiguration(
            learnerDisplayName = "小概",
            sourceSelections = listOf("selected")
        )

        val evidence = buildChatContextEvidence(
            userText = "body",
            memoryRepository = null,
            sourceRepository = sourceRepository,
            sessionSnapshot = snapshot,
            sessionId = "session-a"
        )

        assertEquals("session-settings-session-a", evidence.first().id)
        assertTrue(evidence.first().body.contains("小概"))
        assertTrue(evidence.any { it.id == "selected" })
        assertTrue(evidence.none { it.id == "unselected" })
    }

    @Test
    fun generationEvidenceRecordsOnlySelectedSourcesThatActuallyEnterContext() = runBlocking {
        val sourceRepository = SourceRepository(FakeSourceDao(), defaultSpaceId = "space-1")
        listOf("used" to "matching lesson", "not-used" to "other lesson").forEachIndexed { index, (id, body) ->
            sourceRepository.importSource(
                SourceImportInput(index.toLong(), "$id.md", text = body, sourceId = id),
                nowEpochMillis = index.toLong()
            )
        }
        val calls = mutableListOf<Triple<String, Set<String>, Long>>()
        val usagePort = ChatSourceUsagePort { sessionId, sourceIds, usedAt ->
            calls += Triple(sessionId, sourceIds, usedAt)
        }
        val snapshot = NewSessionConfiguration(sourceSelections = listOf("used", "not-used"))

        val pureEvidence = buildChatContextEvidence(
            userText = "matching",
            memoryRepository = null,
            sourceRepository = sourceRepository,
            sessionSnapshot = snapshot,
            sessionId = "session-a"
        )
        assertTrue(calls.isEmpty())

        val generationEvidence = buildGenerationChatContextEvidence(
            userText = "matching",
            memoryRepository = null,
            sourceRepository = sourceRepository,
            sessionSnapshot = snapshot,
            sessionId = "session-a",
            sourceUsagePort = usagePort,
            usedAtEpochMillis = 123L
        )

        assertEquals(pureEvidence, generationEvidence)
        assertEquals(listOf(Triple("session-a", setOf("used"), 123L)), calls)
    }
}

private class FakeMemoryDao : MemoryDao {
    private val anchors = linkedMapOf<String, AnchorEntity>()
    private val notes = linkedMapOf<String, NoteEntity>()
    private val errors = linkedMapOf<String, ErrorLogEntity>()
    private val memoryItems = linkedMapOf<String, MemoryItemEntity>()

    override suspend fun insertAnchor(anchor: AnchorEntity) {
        anchors[anchor.id] = anchor
    }

    override suspend fun insertNote(note: NoteEntity) {
        notes[note.id] = note
    }

    override suspend fun insertError(error: ErrorLogEntity) {
        errors[error.id] = error
    }

    override suspend fun insertMemoryItem(memoryItem: MemoryItemEntity) {
        memoryItems[memoryItem.id] = memoryItem
    }

    override suspend fun listAnchorsBySpace(spaceId: String): List<AnchorEntity> =
        anchors.values.filter { it.spaceId == spaceId }

    override suspend fun listNotesBySpace(spaceId: String): List<NoteEntity> =
        notes.values.filter { it.spaceId == spaceId }

    override suspend fun listErrorsBySpace(spaceId: String): List<ErrorLogEntity> =
        errors.values.filter { it.spaceId == spaceId }

    override suspend fun listMemoryItemsBySpace(spaceId: String): List<MemoryItemEntity> =
        memoryItems.values.filter { it.spaceId == spaceId }

    override suspend fun updateNote(id: String, title: String, body: String): Int = 0
    override suspend fun deleteNote(id: String): Int = 0
    override suspend fun deleteAnchor(id: String): Int = 0
    override suspend fun setErrorResolved(id: String, resolved: Boolean): Int = 0
    override suspend fun deleteError(id: String): Int = if (errors.remove(id) == null) 0 else 1
    override suspend fun deleteMemoryItem(id: String): Int = if (memoryItems.remove(id) == null) 0 else 1
}

private class FakeSourceDao : SourceDao {
    private val sources = linkedMapOf<String, SourceEntity>()
    private val chunks = linkedMapOf<String, SourceChunkEntity>()

    override suspend fun insertSource(source: SourceEntity) {
        sources[source.id] = source
    }

    override suspend fun insertChunk(chunk: SourceChunkEntity) {
        chunks[chunk.id] = chunk
    }

    override suspend fun getSourceById(id: String): SourceEntity? = sources[id]

    override suspend fun listSourcesBySpace(spaceId: String): List<SourceEntity> =
        sources.values.filter { it.spaceId == spaceId }.sortedByDescending { it.createdAtEpochMillis }

    override suspend fun listChunksForSource(sourceId: String): List<SourceChunkEntity> =
        chunks.values.filter { it.sourceId == sourceId }.sortedBy { it.chunkIndex }

    override suspend fun deleteChunksForSource(sourceId: String): Int {
        val ids = chunks.values.filter { it.sourceId == sourceId }.map { it.id }
        ids.forEach { chunks.remove(it) }
        return ids.size
    }

    override suspend fun updateChunkEmbedding(chunkId: String, embedding: ByteArray) {
        chunks[chunkId]?.let { chunks[chunkId] = it.copy(embedding = embedding) }
    }

    override suspend fun listChunkEmbeddingRows(spaceId: String): List<SourceChunkEmbeddingRow> =
        chunks.values
            .filter { it.spaceId == spaceId && it.embedding != null }
            .map { SourceChunkEmbeddingRow(it.id, it.embedding!!) }
}
