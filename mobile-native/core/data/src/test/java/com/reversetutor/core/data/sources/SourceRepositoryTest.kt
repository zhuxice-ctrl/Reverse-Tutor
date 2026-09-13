package com.reversetutor.core.data.sources

import com.reversetutor.core.data.local.dao.SourceChunkEmbeddingRow
import com.reversetutor.core.data.local.dao.SourceDao
import com.reversetutor.core.data.local.entity.SourceChunkEntity
import com.reversetutor.core.data.local.entity.SourceEntity
import com.reversetutor.core.model.SourceParserStatus
import com.reversetutor.core.model.SourceType
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SourceRepositoryTest {
    @Test
    fun textImportParsesLocallyAndCreatesChunks() = runBlocking {
        val dao = FakeSourceDao()
        val repository = SourceRepository(dao, defaultSpaceId = "space-1")

        val result = repository.importSource(
            input = SourceImportInput(
                requestId = 1L,
                fileName = "notes.txt",
                mimeType = "text/plain",
                text = "Alpha\n\nBeta",
                sourceId = "source-text"
            ),
            nowEpochMillis = 100L
        )

        assertEquals(SourceType.Text, result.source.type)
        assertEquals(SourceParserStatus.FullyLocal, result.source.parserStatus)
        assertEquals(listOf("Alpha", "Beta"), result.chunks.map { it.text })
        assertEquals("notes.txt", dao.getSourceById("source-text")?.title)
    }

    @Test
    fun markdownImportStripsLightweightSyntax() = runBlocking {
        val repository = SourceRepository(FakeSourceDao(), defaultSpaceId = "space-1")

        val result = repository.importSource(
            input = SourceImportInput(
                requestId = 1L,
                fileName = "guide.md",
                text = "# Title\nUse [source](https://example.com).",
                sourceId = "source-md"
            ),
            nowEpochMillis = 100L
        )

        assertEquals(SourceType.Markdown, result.source.type)
        assertEquals(SourceParserStatus.FullyLocal, result.source.parserStatus)
        assertTrue(result.source.extractedText?.contains("Title") == true)
        assertTrue(result.source.extractedText?.contains("[source]") == false)
    }

    @Test
    fun unreadableTextImportRemainsVisibleAsFailedSource() = runBlocking {
        val repository = SourceRepository(FakeSourceDao(), defaultSpaceId = "space-1")

        val result = repository.importSource(
            input = SourceImportInput(
                requestId = 1L,
                fileName = "empty.txt",
                mimeType = "text/plain",
                text = null,
                sourceId = "source-empty"
            ),
            nowEpochMillis = 100L
        )

        assertEquals(SourceParserStatus.Failed, result.source.parserStatus)
        assertEquals(listOf("source-empty"), repository.listSourcesWithChunks().map { it.source.id })
        assertTrue(result.errors.isNotEmpty())
    }


    @Test
    fun htmlImportIsPartialAndSanitized() = runBlocking {
        val repository = SourceRepository(FakeSourceDao(), defaultSpaceId = "space-1")

        val result = repository.importSource(
            input = SourceImportInput(
                requestId = 1L,
                fileName = "page.html",
                mimeType = "text/html",
                text = "<html><script>alert(1)</script><body><h1>Safe</h1><p>Body</p></body></html>",
                sourceId = "source-html"
            ),
            nowEpochMillis = 100L
        )

        assertEquals(SourceType.Html, result.source.type)
        assertEquals(SourceParserStatus.PartiallyLocal, result.source.parserStatus)
        assertTrue(result.source.extractedText?.contains("Safe") == true)
        assertTrue(result.source.extractedText?.contains("alert") == false)
        assertTrue(result.warnings.isNotEmpty())
    }

    @Test
    fun pdfWithExtractedTextLayerParsesLocally() = runBlocking {
        val repository = SourceRepository(FakeSourceDao(), defaultSpaceId = "space-1")

        val result = repository.importSource(
            input = SourceImportInput(
                requestId = 1L,
                fileName = "chapter.pdf",
                mimeType = "application/pdf",
                text = "Alpha content.\n\nBeta content.",
                sourceId = "source-pdf-text"
            ),
            nowEpochMillis = 100L
        )

        assertEquals(SourceType.Pdf, result.source.type)
        assertEquals(SourceParserStatus.PartiallyLocal, result.source.parserStatus)
        assertEquals(listOf("Alpha content.", "Beta content."), result.chunks.map { it.text })
        assertTrue(result.warnings.isNotEmpty())
    }

    @Test
    fun imageWithRecognizedOcrTextParsesLocally() = runBlocking {
        val repository = SourceRepository(FakeSourceDao(), defaultSpaceId = "space-1")

        val result = repository.importSource(
            input = SourceImportInput(
                requestId = 1L,
                fileName = "question.png",
                mimeType = "image/png",
                text = "Alpha question.\n\nBeta note.",
                sourceId = "source-image-text"
            ),
            nowEpochMillis = 100L
        )

        assertEquals(SourceType.Image, result.source.type)
        assertEquals(SourceParserStatus.PartiallyLocal, result.source.parserStatus)
        assertEquals(listOf("Alpha question.", "Beta note."), result.chunks.map { it.text })
        assertTrue(result.warnings.isNotEmpty())
    }

    @Test
    fun imageWithoutReadableTextStaysFutureAssisted() = runBlocking {
        val repository = SourceRepository(FakeSourceDao(), defaultSpaceId = "space-1")

        val result = repository.importSource(
            input = SourceImportInput(
                requestId = 1L,
                fileName = "diagram.png",
                mimeType = "image/png",
                text = null,
                sourceId = "source-image-blank"
            ),
            nowEpochMillis = 100L
        )

        assertEquals(SourceType.Image, result.source.type)
        assertEquals(SourceParserStatus.FutureAssisted, result.source.parserStatus)
        assertTrue(result.chunks.isEmpty())
    }

    @Test
    fun docxWithExtractedTextParsesLocally() = runBlocking {
        val repository = SourceRepository(FakeSourceDao(), defaultSpaceId = "space-1")

        val result = repository.importSource(
            input = SourceImportInput(
                requestId = 1L,
                fileName = "prd.docx",
                mimeType = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                text = "Alpha requirement.\n\nBeta scope.",
                sourceId = "source-docx-text"
            ),
            nowEpochMillis = 100L
        )

        assertEquals(SourceType.Docx, result.source.type)
        assertEquals(SourceParserStatus.PartiallyLocal, result.source.parserStatus)
        assertEquals(listOf("Alpha requirement.", "Beta scope."), result.chunks.map { it.text })
        assertTrue(result.warnings.isNotEmpty())
    }

    @Test
    fun docxWithoutReadableTextStaysFutureAssisted() = runBlocking {
        val repository = SourceRepository(FakeSourceDao(), defaultSpaceId = "space-1")

        val result = repository.importSource(
            input = SourceImportInput(
                requestId = 1L,
                fileName = "scanned.docx",
                mimeType = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                text = null,
                sourceId = "source-docx-blank"
            ),
            nowEpochMillis = 100L
        )

        assertEquals(SourceType.Docx, result.source.type)
        assertEquals(SourceParserStatus.FutureAssisted, result.source.parserStatus)
        assertTrue(result.chunks.isEmpty())
    }

    @Test
    fun pptxWithExtractedTextParsesLocally() = runBlocking {
        val repository = SourceRepository(FakeSourceDao(), defaultSpaceId = "space-1")

        val result = repository.importSource(
            input = SourceImportInput(
                requestId = 1L,
                fileName = "deck.pptx",
                mimeType = "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                text = "Slide one title.\n\nSlide two agenda.",
                sourceId = "source-pptx-text"
            ),
            nowEpochMillis = 100L
        )

        assertEquals(SourceType.Pptx, result.source.type)
        assertEquals(SourceParserStatus.PartiallyLocal, result.source.parserStatus)
        assertEquals(listOf("Slide one title.", "Slide two agenda."), result.chunks.map { it.text })
        assertTrue(result.warnings.isNotEmpty())
    }

    @Test
    fun epubWithExtractedTextParsesLocally() = runBlocking {
        val repository = SourceRepository(FakeSourceDao(), defaultSpaceId = "space-1")

        val result = repository.importSource(
            input = SourceImportInput(
                requestId = 1L,
                fileName = "book.epub",
                mimeType = "application/epub+zip",
                text = "Chapter one.\n\nChapter two.",
                sourceId = "source-epub-text"
            ),
            nowEpochMillis = 100L
        )

        assertEquals(SourceType.Epub, result.source.type)
        assertEquals(SourceParserStatus.PartiallyLocal, result.source.parserStatus)
        assertEquals(listOf("Chapter one.", "Chapter two."), result.chunks.map { it.text })
        assertTrue(result.warnings.isNotEmpty())
    }

    @Test
    fun unsupportedAndFutureParserFilesRemainVisible() = runBlocking {
        val repository = SourceRepository(FakeSourceDao(), defaultSpaceId = "space-1")

        val complexInputs = listOf(
            Triple("chapter.pdf", "application/pdf", SourceType.Pdf),
            Triple("notes.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", SourceType.Docx),
            Triple("slides.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation", SourceType.Pptx),
            Triple("book.epub", "application/epub+zip", SourceType.Epub),
            Triple("question.png", "image/png", SourceType.Image)
        )
        val complexResults = complexInputs.mapIndexed { index, (fileName, mimeType, _) ->
            repository.importSource(
                input = SourceImportInput(
                    requestId = index + 1L,
                    fileName = fileName,
                    mimeType = mimeType,
                    uri = "content://sources/$fileName",
                    sourceId = "source-${fileName.substringBefore('.')}"
                ),
                nowEpochMillis = 100L + index
            )
        }
        val unknown = repository.importSource(
            input = SourceImportInput(
                requestId = 20L,
                fileName = "archive.bin",
                sourceId = "source-bin"
            ),
            nowEpochMillis = 200L
        )

        assertEquals(complexInputs.map { it.third }, complexResults.map { it.source.type })
        assertEquals(
            List(complexInputs.size) { SourceParserStatus.FutureAssisted },
            complexResults.map { it.source.parserStatus }
        )
        assertEquals(SourceParserStatus.Unsupported, unknown.source.parserStatus)
        assertEquals(
            listOf("source-bin", "source-question", "source-book", "source-slides", "source-notes", "source-chapter"),
            repository.listSourcesWithChunks().map { it.source.id }
        )
    }

    @Test
    fun reprocessUsesExistingExtractedTextAndReplacesChunks() = runBlocking {
        val dao = FakeSourceDao()
        val repository = SourceRepository(dao, defaultSpaceId = "space-1")
        repository.importSource(
            input = SourceImportInput(
                requestId = 1L,
                fileName = "notes.txt",
                text = "First",
                sourceId = "source-text"
            ),
            nowEpochMillis = 100L
        )

        val result = repository.reprocessSource("source-text", nowEpochMillis = 200L)

        assertEquals(SourceParserStatus.FullyLocal, result?.source?.parserStatus)
        // Task 1 (hot-update): reprocessing stamps a newer creation time, so the
        // adapter-derived revision (rev-<id>-<createdAt>) changes for the next turn.
        assertEquals(200L, result?.source?.createdAtEpochMillis)
        assertEquals(listOf("First"), dao.listChunksForSource("source-text").map { it.text })
    }
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
        sources.values
            .filter { it.spaceId == spaceId }
            .sortedByDescending { it.createdAtEpochMillis }

    override suspend fun listChunksForSource(sourceId: String): List<SourceChunkEntity> =
        chunks.values
            .filter { it.sourceId == sourceId }
            .sortedBy { it.chunkIndex }

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
