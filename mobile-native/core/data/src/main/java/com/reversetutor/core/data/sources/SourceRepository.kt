package com.reversetutor.core.data.sources

import com.reversetutor.core.data.local.dao.SourceDao
import com.reversetutor.core.data.local.entity.SourceChunkEntity
import com.reversetutor.core.data.local.entity.SourceEntity
import com.reversetutor.core.data.session.SessionRepository
import com.reversetutor.core.model.SourceChunk
import com.reversetutor.core.model.SourceParserStatus
import com.reversetutor.core.model.SourceRecord
import com.reversetutor.core.model.SourceType

class SourceRepository(
    private val sourceDao: SourceDao,
    private val defaultSpaceId: String = SessionRepository.defaultSpaceId
) {
    suspend fun listSourcesWithChunks(spaceId: String = defaultSpaceId): List<SourceWithChunks> =
        sourceDao.listSourcesBySpace(spaceId).map { source ->
            SourceWithChunks(
                source = source.toDomain(),
                chunks = sourceDao.listChunksForSource(source.id).map { it.toDomain() }
            )
        }

    /** NEWMP-V1-024: persists semantic embedding vectors for freshly indexed chunks. */
    suspend fun updateChunkEmbeddings(chunkIds: List<String>, vectors: List<FloatArray>) {
        if (chunkIds.size != vectors.size) return
        chunkIds.zip(vectors).forEach { (chunkId, vector) ->
            sourceDao.updateChunkEmbedding(chunkId, SourceEmbeddingCodec.encode(vector))
        }
    }

    /** NEWMP-V1-024: loads all stored chunk embeddings for a space (chunk id -> vector). */
    suspend fun listChunkEmbeddings(spaceId: String = defaultSpaceId): Map<String, FloatArray> =
        sourceDao.listChunkEmbeddingRows(spaceId)
            .mapNotNull { row -> SourceEmbeddingCodec.decode(row.embedding)?.let { row.id to it } }
            .toMap()

    suspend fun importSource(
        input: SourceImportInput,
        nowEpochMillis: Long,
        spaceId: String = defaultSpaceId
    ): SourceImportResult {
        val parse = LocalSourceParser.parse(input)
        val sourceId = input.sourceId ?: stableSourceId(
            title = input.fileName,
            uri = input.uri,
            nowEpochMillis = nowEpochMillis
        )
        val source = SourceRecord(
            id = sourceId,
            spaceId = spaceId,
            title = input.fileName.ifBlank { "Untitled source" },
            type = parse.type,
            parserStatus = parse.status,
            createdAtEpochMillis = nowEpochMillis,
            uri = input.uri,
            extractedText = parse.extractedText,
            importBatchId = null
        )
        val chunks = parse.chunks.mapIndexed { index, text ->
            SourceChunk(
                id = "$sourceId-chunk-$index",
                spaceId = spaceId,
                sourceId = sourceId,
                chunkIndex = index,
                text = text,
                tokenEstimate = estimateTokens(text)
            )
        }

        sourceDao.insertSource(source.toEntity())
        sourceDao.deleteChunksForSource(sourceId)
        chunks.forEach { sourceDao.insertChunk(it.toEntity()) }

        return SourceImportResult(
            source = source,
            chunks = chunks,
            warnings = parse.warnings,
            errors = parse.errors
        )
    }

    suspend fun reprocessSource(
        sourceId: String,
        nowEpochMillis: Long
    ): SourceImportResult? {
        val existing = sourceDao.getSourceById(sourceId) ?: return null
        return importSource(
            input = SourceImportInput(
                requestId = nowEpochMillis,
                fileName = existing.title,
                mimeType = null,
                uri = existing.uri,
                text = existing.extractedText,
                sourceId = existing.id
            ),
            nowEpochMillis = nowEpochMillis,
            spaceId = existing.spaceId
        )
    }
}

data class SourceImportInput(
    val requestId: Long,
    val fileName: String,
    val mimeType: String? = null,
    val uri: String? = null,
    val text: String? = null,
    val sourceId: String? = null
)

data class SourceImportResult(
    val source: SourceRecord,
    val chunks: List<SourceChunk>,
    val warnings: List<String>,
    val errors: List<String>
) {
    val isUsable: Boolean
        get() = source.parserStatus in setOf(SourceParserStatus.FullyLocal, SourceParserStatus.PartiallyLocal)
}

data class SourceWithChunks(
    val source: SourceRecord,
    val chunks: List<SourceChunk>
)

object LocalSourceParser {
    fun parse(input: SourceImportInput): SourceParseOutcome {
        val type = detectType(input.fileName, input.mimeType)
        val text = input.text.orEmpty()
        return when (type) {
            SourceType.Text -> parsePlainText(type, text)
            SourceType.Markdown -> parseMarkdown(text)
            SourceType.Html -> parseHtml(text)
            SourceType.JsonExport -> SourceParseOutcome(
                type = type,
                status = SourceParserStatus.FutureAssisted,
                extractedText = null,
                chunks = emptyList(),
                warnings = listOf("JSON exports belong to Import/export. The file stays visible here as a reference.")
            )
            SourceType.Pdf -> parsePdf(type, text)
            SourceType.Image -> parseImage(type, text)
            SourceType.Docx -> parseDocx(type, text)
            SourceType.Pptx -> parsePptx(type, text)
            SourceType.Epub -> parseEpub(type, text)
            SourceType.Other -> SourceParseOutcome(
                type = type,
                status = SourceParserStatus.Unsupported,
                extractedText = null,
                chunks = emptyList(),
                warnings = listOf("This file type is not supported in the current native preview.")
            )
        }
    }

    private fun parsePlainText(
        type: SourceType,
        text: String
    ): SourceParseOutcome {
        val normalized = normalizeText(text)
        if (normalized.isBlank()) {
            return SourceParseOutcome(
                type = type,
                status = SourceParserStatus.Failed,
                extractedText = null,
                chunks = emptyList(),
                errors = listOf("No readable text was found.")
            )
        }
        return SourceParseOutcome(
            type = type,
            status = SourceParserStatus.FullyLocal,
            extractedText = normalized,
            chunks = chunkText(normalized)
        )
    }

    private fun parsePdf(
        type: SourceType,
        text: String
    ): SourceParseOutcome {
        if (text.isBlank()) {
            return SourceParseOutcome(
                type = type,
                status = SourceParserStatus.FutureAssisted,
                extractedText = null,
                chunks = emptyList(),
                warnings = listOf("No readable text was extracted from this PDF (no text layer and on-device OCR found nothing); it stays as a reference.")
            )
        }
        val normalized = normalizeText(text)
        if (normalized.isBlank()) {
            return SourceParseOutcome(
                type = type,
                status = SourceParserStatus.FutureAssisted,
                extractedText = null,
                chunks = emptyList(),
                warnings = listOf("No readable text was extracted from this PDF (no text layer and on-device OCR found nothing); it stays as a reference.")
            )
        }
        return SourceParseOutcome(
            type = type,
            status = SourceParserStatus.PartiallyLocal,
            extractedText = normalized,
            chunks = chunkText(normalized),
            warnings = listOf("PDF text was extracted locally (text layer, or on-device OCR for scanned pages); handwriting and complex layouts may be inaccurate.")
        )
    }

    private fun parseImage(
        type: SourceType,
        text: String
    ): SourceParseOutcome {
        if (text.isBlank()) {
            return SourceParseOutcome(
                type = type,
                status = SourceParserStatus.FutureAssisted,
                extractedText = null,
                chunks = emptyList(),
                warnings = listOf("No readable text was recognized in this image; pure diagrams or handwriting wait for vision-assisted parsing.")
            )
        }
        val normalized = normalizeText(text)
        if (normalized.isBlank()) {
            return SourceParseOutcome(
                type = type,
                status = SourceParserStatus.FutureAssisted,
                extractedText = null,
                chunks = emptyList(),
                warnings = listOf("No readable text was recognized in this image; pure diagrams or handwriting wait for vision-assisted parsing.")
            )
        }
        return SourceParseOutcome(
            type = type,
            status = SourceParserStatus.PartiallyLocal,
            extractedText = normalized,
            chunks = chunkText(normalized),
            warnings = listOf("Image text was extracted with on-device OCR or cloud vision transcription; verify against the original image.")
        )
    }

    private fun parseDocx(
        type: SourceType,
        text: String
    ): SourceParseOutcome {
        if (text.isBlank()) {
            return SourceParseOutcome(
                type = type,
                status = SourceParserStatus.FutureAssisted,
                extractedText = null,
                chunks = emptyList(),
                warnings = listOf("No readable text was extracted from this Word document; it stays as a reference.")
            )
        }
        val normalized = normalizeText(text)
        if (normalized.isBlank()) {
            return SourceParseOutcome(
                type = type,
                status = SourceParserStatus.FutureAssisted,
                extractedText = null,
                chunks = emptyList(),
                warnings = listOf("No readable text was extracted from this Word document; it stays as a reference.")
            )
        }
        return SourceParseOutcome(
            type = type,
            status = SourceParserStatus.PartiallyLocal,
            extractedText = normalized,
            chunks = chunkText(normalized),
            warnings = listOf("Word text and embedded images were extracted locally (on-device OCR or cloud vision transcription for images); verify complex layouts against the original document.")
        )
    }

    private fun parsePptx(
        type: SourceType,
        text: String
    ): SourceParseOutcome {
        if (text.isBlank()) {
            return SourceParseOutcome(
                type = type,
                status = SourceParserStatus.FutureAssisted,
                extractedText = null,
                chunks = emptyList(),
                warnings = listOf("No readable text was extracted from this presentation; it stays as a reference.")
            )
        }
        val normalized = normalizeText(text)
        if (normalized.isBlank()) {
            return SourceParseOutcome(
                type = type,
                status = SourceParserStatus.FutureAssisted,
                extractedText = null,
                chunks = emptyList(),
                warnings = listOf("No readable text was extracted from this presentation; it stays as a reference.")
            )
        }
        return SourceParseOutcome(
            type = type,
            status = SourceParserStatus.PartiallyLocal,
            extractedText = normalized,
            chunks = chunkText(normalized),
            warnings = listOf("Slide text and embedded images were extracted locally (on-device OCR or cloud vision transcription for images); verify complex slide layouts against the original presentation.")
        )
    }

    private fun parseEpub(
        type: SourceType,
        text: String
    ): SourceParseOutcome {
        if (text.isBlank()) {
            return SourceParseOutcome(
                type = type,
                status = SourceParserStatus.FutureAssisted,
                extractedText = null,
                chunks = emptyList(),
                warnings = listOf("No readable text was extracted from this ebook; it stays as a reference.")
            )
        }
        val normalized = normalizeText(text)
        if (normalized.isBlank()) {
            return SourceParseOutcome(
                type = type,
                status = SourceParserStatus.FutureAssisted,
                extractedText = null,
                chunks = emptyList(),
                warnings = listOf("No readable text was extracted from this ebook; it stays as a reference.")
            )
        }
        return SourceParseOutcome(
            type = type,
            status = SourceParserStatus.PartiallyLocal,
            extractedText = normalized,
            chunks = chunkText(normalized),
            warnings = listOf("Ebook text and embedded images were extracted locally (on-device OCR or cloud vision transcription for images); verify complex formatting against the original ebook.")
        )
    }

    private fun parseMarkdown(text: String): SourceParseOutcome {
        val stripped = normalizeText(text)
            .replace(Regex("`{1,3}"), "")
            .replace(Regex("^#{1,6}\\s*", RegexOption.MULTILINE), "")
            .replace(Regex("\\[(.+?)]\\((.+?)\\)"), "$1")
        return parsePlainText(SourceType.Markdown, stripped)
    }

    private fun parseHtml(text: String): SourceParseOutcome {
        if (text.isBlank()) {
            return SourceParseOutcome(
                type = SourceType.Html,
                status = SourceParserStatus.Failed,
                extractedText = null,
                chunks = emptyList(),
                errors = listOf("HTML file could not be read as text.")
            )
        }
        val safeText = text
            .replace(Regex("<script[\\s\\S]*?</script>", RegexOption.IGNORE_CASE), " ")
            .replace(Regex("<style[\\s\\S]*?</style>", RegexOption.IGNORE_CASE), " ")
            .replace(Regex("<!--([\\s\\S]*?)-->"), " ")
            .replace(Regex("<[^>]+>"), " ")
            .replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .let(::normalizeText)
        if (safeText.isBlank()) {
            return SourceParseOutcome(
                type = SourceType.Html,
                status = SourceParserStatus.Failed,
                extractedText = null,
                chunks = emptyList(),
                errors = listOf("No readable HTML body text was found after sanitization.")
            )
        }
        return SourceParseOutcome(
            type = SourceType.Html,
            status = SourceParserStatus.PartiallyLocal,
            extractedText = safeText,
            chunks = chunkText(safeText),
            warnings = listOf("HTML was sanitized locally; scripts, styles, and complex formatting were removed.")
        )
    }
}

data class SourceParseOutcome(
    val type: SourceType,
    val status: SourceParserStatus,
    val extractedText: String?,
    val chunks: List<String>,
    val warnings: List<String> = emptyList(),
    val errors: List<String> = emptyList()
)

private fun detectType(
    fileName: String,
    mimeType: String?
): SourceType {
    val normalizedName = fileName.lowercase()
    val ext = normalizedName.substringAfterLast('.', missingDelimiterValue = "")
    val normalizedMime = mimeType.orEmpty().lowercase()
    return when {
        ext == "txt" || normalizedMime == "text/plain" -> SourceType.Text
        ext in setOf("md", "markdown") || normalizedMime in setOf("text/markdown", "text/x-markdown") -> SourceType.Markdown
        ext in setOf("html", "htm") || normalizedMime == "text/html" -> SourceType.Html
        ext == "json" || normalizedMime == "application/json" -> SourceType.JsonExport
        ext == "pdf" || normalizedMime == "application/pdf" -> SourceType.Pdf
        ext == "docx" || normalizedMime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" -> SourceType.Docx
        ext == "pptx" || normalizedMime == "application/vnd.openxmlformats-officedocument.presentationml.presentation" -> SourceType.Pptx
        ext == "epub" || normalizedMime == "application/epub+zip" -> SourceType.Epub
        ext in setOf("png", "jpg", "jpeg", "webp", "gif") || normalizedMime.startsWith("image/") -> SourceType.Image
        else -> SourceType.Other
    }
}

private fun normalizeText(text: String): String =
    text.replace("\r\n", "\n")
        .replace('\r', '\n')
        .lines()
        .map { it.trim() }
        .joinToString("\n")
        .replace(Regex("\n{3,}"), "\n\n")
        .trim()

private fun chunkText(text: String): List<String> = SourceChunker.chunk(text)

private fun estimateTokens(text: String): Int =
    (text.length / 4).coerceAtLeast(1)

private fun stableSourceId(
    title: String,
    uri: String?,
    nowEpochMillis: Long
): String {
    val seed = "${uri ?: title}-$nowEpochMillis"
    val slug = title.lowercase()
        .replace(Regex("[^a-z0-9]+"), "-")
        .trim('-')
        .take(40)
        .ifBlank { "source" }
    return "source-$slug-${seed.hashCode().toUInt().toString(16)}"
}

private fun SourceRecord.toEntity(): SourceEntity =
    SourceEntity(
        id = id,
        spaceId = spaceId,
        title = title,
        type = type.name,
        parserStatus = parserStatus.name,
        createdAtEpochMillis = createdAtEpochMillis,
        uri = uri,
        extractedText = extractedText,
        importBatchId = importBatchId
    )

private fun SourceEntity.toDomain(): SourceRecord =
    SourceRecord(
        id = id,
        spaceId = spaceId,
        title = title,
        type = runCatching { SourceType.valueOf(type) }.getOrDefault(SourceType.Other),
        parserStatus = runCatching { SourceParserStatus.valueOf(parserStatus) }
            .getOrDefault(SourceParserStatus.Unsupported),
        createdAtEpochMillis = createdAtEpochMillis,
        uri = uri,
        extractedText = extractedText,
        importBatchId = importBatchId
    )

private fun SourceChunk.toEntity(): SourceChunkEntity =
    SourceChunkEntity(
        id = id,
        spaceId = spaceId,
        sourceId = sourceId,
        chunkIndex = chunkIndex,
        text = text,
        tokenEstimate = tokenEstimate
    )

private fun SourceChunkEntity.toDomain(): SourceChunk =
    SourceChunk(
        id = id,
        spaceId = spaceId,
        sourceId = sourceId,
        chunkIndex = chunkIndex,
        text = text,
        tokenEstimate = tokenEstimate
    )
