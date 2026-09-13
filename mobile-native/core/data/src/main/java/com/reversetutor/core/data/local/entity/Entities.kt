package com.reversetutor.core.data.local.entity

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey
import com.reversetutor.core.model.Message
import com.reversetutor.core.model.MessageAttachment
import com.reversetutor.core.model.MessageQuote
import com.reversetutor.core.model.MessageRole
import com.reversetutor.core.model.Anchor
import com.reversetutor.core.model.ErrorLog
import com.reversetutor.core.model.ErrorLogOrigin
import com.reversetutor.core.model.GraphEdge
import com.reversetutor.core.model.GraphNode
import com.reversetutor.core.model.GraphNodeKind
import com.reversetutor.core.model.GraphNodeStatus
import com.reversetutor.core.model.LlmProfile
import com.reversetutor.core.model.LlmProviderKind
import com.reversetutor.core.model.MemoryItem
import com.reversetutor.core.model.MemoryItemKind
import com.reversetutor.core.model.Note
import com.reversetutor.core.model.SessionSettings
import com.reversetutor.core.model.Space
import com.reversetutor.core.model.SpaceKind
import com.reversetutor.core.model.TutorSession

@Entity(tableName = "spaces")
data class SpaceEntity(
    @PrimaryKey val id: String,
    val name: String,
    val kind: String,
    val createdAtEpochMillis: Long,
    val updatedAtEpochMillis: Long,
    val sourceImportId: String? = null
)

@Entity(
    tableName = "sessions",
    indices = [Index("spaceId"), Index("updatedAtEpochMillis"), Index("modelBindingId")]
)
data class SessionEntity(
    @PrimaryKey val id: String,
    val spaceId: String,
    val title: String,
    val createdAtEpochMillis: Long,
    val updatedAtEpochMillis: Long,
    val pinned: Boolean = false,
    val archived: Boolean = false,
    val llmProfileId: String? = null,
    val modelBindingId: String? = llmProfileId,
    val settingsId: String? = null,
    val sourceImportId: String? = null
)

@Entity(tableName = "messages", indices = [Index("spaceId"), Index("sessionId")])
data class MessageEntity(
    @PrimaryKey val id: String,
    val spaceId: String,
    val sessionId: String,
    val role: String,
    val text: String,
    val createdAtEpochMillis: Long,
    val parentMessageId: String? = null,
    val sourceImportId: String? = null
)

@Entity(tableName = "message_attachments", indices = [Index("spaceId"), Index("messageId")])
data class MessageAttachmentEntity(
    @PrimaryKey val id: String,
    val spaceId: String,
    val messageId: String,
    val name: String,
    val mimeType: String? = null,
    val uri: String? = null,
    val sourceId: String? = null
)

@Entity(tableName = "message_quotes", indices = [Index("spaceId"), Index("messageId")])
data class MessageQuoteEntity(
    @PrimaryKey val id: String,
    val spaceId: String,
    val messageId: String,
    val quotedMessageId: String,
    val excerpt: String
)

@Entity(tableName = "llm_profiles", indices = [Index("spaceId")])
data class LlmProfileEntity(
    @PrimaryKey val id: String,
    val spaceId: String,
    val name: String,
    val provider: String,
    val model: String,
    val secretRef: String? = null,
    val createdAtEpochMillis: Long,
    val updatedAtEpochMillis: Long,
    val baseUrl: String? = null,
    val enabled: Boolean = true
)

@Entity(
    tableName = "session_settings",
    indices = [Index("spaceId"), Index("sessionId"), Index("modelBindingId")]
)
data class SessionSettingsEntity(
    @PrimaryKey val id: String,
    val spaceId: String,
    val sessionId: String,
    val llmProfileId: String? = null,
    val modelBindingId: String? = llmProfileId,
    val systemPrompt: String? = null
)

@Entity(tableName = "anchors", indices = [Index("spaceId")])
data class AnchorEntity(
    @PrimaryKey val id: String,
    val spaceId: String,
    val title: String,
    val body: String,
    val createdAtEpochMillis: Long,
    val sourceMessageId: String? = null,
    val sourceId: String? = null
)

@Entity(tableName = "notes", indices = [Index("spaceId")])
data class NoteEntity(
    @PrimaryKey val id: String,
    val spaceId: String,
    val title: String,
    val body: String,
    val createdAtEpochMillis: Long,
    val sourceMessageId: String? = null
)

@Entity(
    tableName = "error_logs",
    indices = [Index("spaceId"), Index(value = ["spaceId", "origin", "createdAtEpochMillis"])]
)
data class ErrorLogEntity(
    @PrimaryKey val id: String,
    val spaceId: String,
    val title: String,
    val detail: String,
    val createdAtEpochMillis: Long,
    val sourceMessageId: String? = null,
    val resolved: Boolean = false,
    val origin: String = ErrorLogOrigin.Learning.name,
    val code: String? = null
)

@Entity(tableName = "memory_items", indices = [Index("spaceId")])
data class MemoryItemEntity(
    @PrimaryKey val id: String,
    val spaceId: String,
    val kind: String,
    val title: String,
    val body: String,
    val createdAtEpochMillis: Long,
    val sourceMessageId: String? = null,
    val sourceId: String? = null
)

@Entity(tableName = "graph_nodes", indices = [Index("spaceId")])
data class GraphNodeEntity(
    @PrimaryKey val id: String,
    val spaceId: String,
    val label: String,
    val kind: String,
    val createdAtEpochMillis: Long,
    val status: String = "Active",
    val sourceMemoryId: String? = null
)

@Entity(tableName = "graph_edges", indices = [Index("spaceId"), Index("fromNodeId"), Index("toNodeId")])
data class GraphEdgeEntity(
    @PrimaryKey val id: String,
    val spaceId: String,
    val fromNodeId: String,
    val toNodeId: String,
    val relation: String,
    val createdAtEpochMillis: Long,
    val sourceMemoryId: String? = null
)

@Entity(tableName = "sources", indices = [Index("spaceId"), Index("type")])
data class SourceEntity(
    @PrimaryKey val id: String,
    val spaceId: String,
    val title: String,
    val type: String,
    val parserStatus: String,
    val createdAtEpochMillis: Long,
    val uri: String? = null,
    val extractedText: String? = null,
    val importBatchId: String? = null
)

@Entity(tableName = "source_chunks", indices = [Index("spaceId"), Index("sourceId")])
data class SourceChunkEntity(
    @PrimaryKey val id: String,
    val spaceId: String,
    val sourceId: String,
    val chunkIndex: Int,
    val text: String,
    val tokenEstimate: Int? = null,
    /** NEWMP-V1-024: optional local embedding vector for semantic retrieval. */
    val embedding: ByteArray? = null
)

@Entity(tableName = "background_jobs", indices = [Index("spaceId"), Index("sessionId"), Index("status")])
data class BackgroundJobEntity(
    @PrimaryKey val id: String,
    val spaceId: String,
    val kind: String,
    val status: String,
    val createdAtEpochMillis: Long,
    val sessionId: String? = null,
    val startedAtEpochMillis: Long? = null,
    val completedAtEpochMillis: Long? = null,
    val errorMessage: String? = null,
    val userMessageId: String? = null,
    val userText: String? = null,
    val generationToken: String? = null,
    val modelBindingId: String? = null,
    val quoteExcerpt: String? = null,
    val imageAttachmentsPayload: String? = null,
    val contextEvidencePayload: String? = null,
    val sessionPolicyPayload: String? = null,
    val assistantTurnEnvelopePayload: String? = null
)

// ---------------------------------------------------------------------------
// Session document / rich-reply artifacts (P6 10 -> 11).
// These rows store validated user-visible content and opaque handles only.
// ---------------------------------------------------------------------------

@Entity(tableName = "assistant_reply_artifacts", indices = [Index("sessionId")])
data class AssistantReplyArtifactEntity(
    @PrimaryKey val assistantMessageId: String,
    val sessionId: String,
    val blocksPayload: String,
    val evidenceReferencesPayload: String,
    val toolResultsPayload: String,
    val checkPlanPayload: String? = null,
    val createdAtEpochMillis: Long
)

@Entity(tableName = "session_documents", indices = [Index("spaceId"), Index("sessionId")])
data class SessionDocumentEntity(
    @PrimaryKey val id: String,
    val spaceId: String,
    val sessionId: String,
    val title: String,
    val kind: String,
    val createdAtEpochMillis: Long,
    val updatedAtEpochMillis: Long
)

@Entity(tableName = "session_document_blocks", indices = [Index("documentId")])
data class SessionDocumentBlockEntity(
    @PrimaryKey val id: String,
    val documentId: String,
    val ordinal: Int,
    val kind: String,
    val payload: String,
    val updatedAtEpochMillis: Long
)

@Entity(tableName = "session_tables", indices = [Index("documentId")])
data class SessionTableEntity(
    @PrimaryKey val id: String,
    val documentId: String,
    val title: String,
    val createdAtEpochMillis: Long,
    val updatedAtEpochMillis: Long
)

@Entity(tableName = "session_table_columns", indices = [Index("tableId")])
data class SessionTableColumnEntity(
    @PrimaryKey val id: String,
    val tableId: String,
    val ordinal: Int,
    val name: String,
    val valueType: String
)

@Entity(tableName = "session_table_rows", indices = [Index("tableId")])
data class SessionTableRowEntity(
    @PrimaryKey val id: String,
    val tableId: String,
    val rowKey: String,
    val cellsPayload: String,
    val updatedAtEpochMillis: Long
)

@Entity(tableName = "tool_call_receipts", indices = [Index("sessionId"), Index("toolName")])
data class ToolCallReceiptEntity(
    @PrimaryKey val callId: String,
    val sessionId: String,
    val toolName: String,
    val status: String,
    val safeResultPayload: String,
    val completedAtEpochMillis: Long
)

@Entity(tableName = "import_batches", indices = [Index("spaceId"), Index("status")])
data class ImportBatchEntity(
    @PrimaryKey val id: String,
    val spaceId: String,
    val sourceFileName: String,
    val sourceSchema: String,
    val mode: String,
    val status: String,
    val startedAtEpochMillis: Long,
    val completedAtEpochMillis: Long? = null,
    val insertedCountsJson: String = "{}",
    val skippedCountsJson: String = "{}",
    val warningsJson: String = "[]",
    val errorsJson: String = "[]"
)

@Entity(tableName = "export_records", indices = [Index("spaceId"), Index("status")])
data class ExportRecordEntity(
    @PrimaryKey val id: String,
    val spaceId: String,
    val schema: String,
    val targetFileName: String,
    val status: String,
    val createdAtEpochMillis: Long,
    val completedAtEpochMillis: Long? = null,
    val warningsJson: String = "[]"
)

fun Space.toEntity(): SpaceEntity = SpaceEntity(
    id = id,
    name = name,
    kind = kind.name,
    createdAtEpochMillis = createdAtEpochMillis,
    updatedAtEpochMillis = updatedAtEpochMillis,
    sourceImportId = sourceImportId
)

fun SpaceEntity.toDomain(): Space = Space(
    id = id,
    name = name,
    kind = SpaceKind.valueOf(kind),
    createdAtEpochMillis = createdAtEpochMillis,
    updatedAtEpochMillis = updatedAtEpochMillis,
    sourceImportId = sourceImportId
)

fun TutorSession.toEntity(): SessionEntity = SessionEntity(
    id = id,
    spaceId = spaceId,
    title = title,
    createdAtEpochMillis = createdAtEpochMillis,
    updatedAtEpochMillis = updatedAtEpochMillis,
    pinned = pinned,
    archived = archived,
    llmProfileId = llmProfileId,
    modelBindingId = modelBindingId,
    settingsId = settingsId,
    sourceImportId = sourceImportId
)

fun SessionEntity.toDomain(): TutorSession = TutorSession(
    id = id,
    spaceId = spaceId,
    title = title,
    createdAtEpochMillis = createdAtEpochMillis,
    updatedAtEpochMillis = updatedAtEpochMillis,
    pinned = pinned,
    archived = archived,
    llmProfileId = llmProfileId,
    modelBindingId = modelBindingId,
    settingsId = settingsId,
    sourceImportId = sourceImportId
)

fun Message.toEntity(): MessageEntity = MessageEntity(
    id = id,
    spaceId = spaceId,
    sessionId = sessionId,
    role = role.name,
    text = text,
    createdAtEpochMillis = createdAtEpochMillis,
    parentMessageId = parentMessageId,
    sourceImportId = sourceImportId
)

fun MessageEntity.toDomain(): Message = Message(
    id = id,
    spaceId = spaceId,
    sessionId = sessionId,
    role = MessageRole.valueOf(role),
    text = text,
    createdAtEpochMillis = createdAtEpochMillis,
    parentMessageId = parentMessageId,
    sourceImportId = sourceImportId
)

fun MessageAttachment.toEntity(): MessageAttachmentEntity = MessageAttachmentEntity(
    id = id,
    spaceId = spaceId,
    messageId = messageId,
    name = name,
    mimeType = mimeType,
    uri = uri,
    sourceId = sourceId
)

fun MessageAttachmentEntity.toDomain(): MessageAttachment = MessageAttachment(
    id = id,
    spaceId = spaceId,
    messageId = messageId,
    name = name,
    mimeType = mimeType,
    uri = uri,
    sourceId = sourceId
)

fun MessageQuote.toEntity(): MessageQuoteEntity = MessageQuoteEntity(
    id = id,
    spaceId = spaceId,
    messageId = messageId,
    quotedMessageId = quotedMessageId,
    excerpt = excerpt
)

fun MessageQuoteEntity.toDomain(): MessageQuote = MessageQuote(
    id = id,
    spaceId = spaceId,
    messageId = messageId,
    quotedMessageId = quotedMessageId,
    excerpt = excerpt
)

fun LlmProfile.toEntity(): LlmProfileEntity = LlmProfileEntity(
    id = id,
    spaceId = spaceId,
    name = name,
    provider = provider.name,
    model = model,
    secretRef = secretRef,
    createdAtEpochMillis = createdAtEpochMillis,
    updatedAtEpochMillis = updatedAtEpochMillis,
    baseUrl = baseUrl,
    enabled = enabled
)

fun LlmProfileEntity.toDomain(): LlmProfile = LlmProfile(
    id = id,
    spaceId = spaceId,
    name = name,
    provider = runCatching { LlmProviderKind.valueOf(provider) }.getOrDefault(LlmProviderKind.Custom),
    model = model,
    secretRef = secretRef,
    createdAtEpochMillis = createdAtEpochMillis,
    updatedAtEpochMillis = updatedAtEpochMillis,
    baseUrl = baseUrl,
    enabled = enabled
)

fun SessionSettings.toEntity(): SessionSettingsEntity = SessionSettingsEntity(
    id = id,
    spaceId = spaceId,
    sessionId = sessionId,
    llmProfileId = llmProfileId,
    modelBindingId = modelBindingId,
    systemPrompt = systemPrompt
)

fun SessionSettingsEntity.toDomain(): SessionSettings = SessionSettings(
    id = id,
    spaceId = spaceId,
    sessionId = sessionId,
    llmProfileId = llmProfileId,
    modelBindingId = modelBindingId,
    systemPrompt = systemPrompt
)

fun Anchor.toEntity(): AnchorEntity = AnchorEntity(
    id = id,
    spaceId = spaceId,
    title = title,
    body = body,
    createdAtEpochMillis = createdAtEpochMillis,
    sourceMessageId = sourceMessageId,
    sourceId = sourceId
)

fun AnchorEntity.toDomain(): Anchor = Anchor(
    id = id,
    spaceId = spaceId,
    title = title,
    body = body,
    createdAtEpochMillis = createdAtEpochMillis,
    sourceMessageId = sourceMessageId,
    sourceId = sourceId
)

fun Note.toEntity(): NoteEntity = NoteEntity(
    id = id,
    spaceId = spaceId,
    title = title,
    body = body,
    createdAtEpochMillis = createdAtEpochMillis,
    sourceMessageId = sourceMessageId
)

fun NoteEntity.toDomain(): Note = Note(
    id = id,
    spaceId = spaceId,
    title = title,
    body = body,
    createdAtEpochMillis = createdAtEpochMillis,
    sourceMessageId = sourceMessageId
)

fun ErrorLog.toEntity(): ErrorLogEntity = ErrorLogEntity(
    id = id,
    spaceId = spaceId,
    title = title,
    detail = detail,
    createdAtEpochMillis = createdAtEpochMillis,
    sourceMessageId = sourceMessageId,
    resolved = resolved,
    origin = origin.name,
    code = code
)

fun ErrorLogEntity.toDomain(): ErrorLog = ErrorLog(
    id = id,
    spaceId = spaceId,
    title = title,
    detail = detail,
    createdAtEpochMillis = createdAtEpochMillis,
    sourceMessageId = sourceMessageId,
    resolved = resolved,
    origin = runCatching { ErrorLogOrigin.valueOf(origin) }.getOrDefault(ErrorLogOrigin.Learning),
    code = code
)

fun MemoryItem.toEntity(): MemoryItemEntity = MemoryItemEntity(
    id = id,
    spaceId = spaceId,
    kind = kind.name,
    title = title,
    body = body,
    createdAtEpochMillis = createdAtEpochMillis,
    sourceMessageId = sourceMessageId,
    sourceId = sourceId
)

fun MemoryItemEntity.toDomain(): MemoryItem = MemoryItem(
    id = id,
    spaceId = spaceId,
    kind = runCatching { MemoryItemKind.valueOf(kind) }.getOrDefault(MemoryItemKind.Fact),
    title = title,
    body = body,
    createdAtEpochMillis = createdAtEpochMillis,
    sourceMessageId = sourceMessageId,
    sourceId = sourceId
)

fun GraphNode.toEntity(): GraphNodeEntity = GraphNodeEntity(
    id = id,
    spaceId = spaceId,
    label = label,
    kind = kind.name,
    createdAtEpochMillis = createdAtEpochMillis,
    status = status.name,
    sourceMemoryId = sourceMemoryId
)

fun GraphNodeEntity.toDomain(): GraphNode = GraphNode(
    id = id,
    spaceId = spaceId,
    label = label,
    kind = runCatching { GraphNodeKind.valueOf(kind) }.getOrDefault(GraphNodeKind.Other),
    createdAtEpochMillis = createdAtEpochMillis,
    status = runCatching { GraphNodeStatus.valueOf(status) }.getOrDefault(GraphNodeStatus.Active),
    sourceMemoryId = sourceMemoryId
)

fun GraphEdge.toEntity(): GraphEdgeEntity = GraphEdgeEntity(
    id = id,
    spaceId = spaceId,
    fromNodeId = fromNodeId,
    toNodeId = toNodeId,
    relation = relation,
    createdAtEpochMillis = createdAtEpochMillis,
    sourceMemoryId = sourceMemoryId
)

fun GraphEdgeEntity.toDomain(): GraphEdge = GraphEdge(
    id = id,
    spaceId = spaceId,
    fromNodeId = fromNodeId,
    toNodeId = toNodeId,
    relation = relation,
    createdAtEpochMillis = createdAtEpochMillis,
    sourceMemoryId = sourceMemoryId
)

// ---------------------------------------------------------------------------
// Window topology (P6 6 -> 7). Window identity == session identity.
// ---------------------------------------------------------------------------

@Entity(
    tableName = "windows",
    indices = [Index("spaceId"), Index("rootId"), Index("parentId")]
)
data class WindowEntity(
    @PrimaryKey val sessionId: String,
    val spaceId: String,
    val rootId: String,
    val parentId: String?,
    val kind: String,
    val createdAtEpochMillis: Long
)

@Entity(tableName = "window_snapshots", indices = [Index("windowId")])
data class WindowSnapshotEntity(
    @PrimaryKey val windowId: String,
    val ancestorRevision: Long,
    val forkedAtEpochMillis: Long
)

@Entity(tableName = "window_deltas", indices = [Index("windowId")])
data class WindowDeltaEntity(
    @PrimaryKey val id: String,
    val windowId: String,
    val deltaId: String,
    val payloadHandle: String,
    val sourceRevision: Long
)

@Entity(
    tableName = "merge_commits",
    indices = [Index("childId"), Index("parentId"), Index("spaceId")]
)
data class MergeCommitEntity(
    @PrimaryKey val id: String,
    val childId: String,
    val parentId: String,
    val deltaId: String,
    val sourceRevision: Long,
    val spaceId: String
)

// ---------------------------------------------------------------------------
// Global learning ledger + scope signals (P6 7 -> 8). No raw transcript.
// ---------------------------------------------------------------------------

@Entity(
    tableName = "learning_fact_receipts",
    indices = [Index("spaceId"), Index("knowledgePoint"), Index("sourceWindowId")]
)
data class LearningFactReceiptEntity(
    @PrimaryKey val id: String,
    val spaceId: String,
    val knowledgePoint: String,
    val evidenceType: String,
    val result: String,
    val confidence: Float,
    val sourceWindowId: String,
    val sourceTurnId: String,
    val occurredAtEpochMillis: Long
) {
    companion object {
        /** Only these columns may be persisted; no raw transcript / provider / secret. */
        val ALLOWED_PERSISTED_FIELDS: Set<String> = setOf(
            "id", "spaceId", "knowledgePoint", "evidenceType", "result",
            "confidence", "sourceWindowId", "sourceTurnId", "occurredAtEpochMillis"
        )
    }
}

@Entity(
    tableName = "scope_signals",
    indices = [Index("windowId"), Index("spaceId")]
)
data class ScopeSignalEntity(
    @PrimaryKey val id: String,
    val windowId: String,
    val spaceId: String,
    val category: String,
    val count: Int,
    val sourceTurnId: String,
    val occurredAtEpochMillis: Long
) {
    companion object {
        /** Only minimal provenance columns may be persisted; no raw user text. */
        val ALLOWED_PERSISTED_FIELDS: Set<String> = setOf(
            "id", "windowId", "spaceId", "category", "count", "sourceTurnId", "occurredAtEpochMillis"
        )
    }
}

// ---------------------------------------------------------------------------
// Companion memory versions + heartbeat (P6 8 -> 9).
// Companion memory is root-only; heartbeats are window-keyed (root enabled,
// child disabled until an explicit enable command). No raw transcript.
// ---------------------------------------------------------------------------

@Entity(
    tableName = "companion_memory_versions",
    indices = [Index("windowId"), Index("spaceId")]
)
data class CompanionMemoryVersionEntity(
    @PrimaryKey val id: String,
    val windowId: String,
    val spaceId: String,
    val partition: String,
    val value: String,
    val origin: String,
    val promotedAtEpochMillis: Long,
    val revision: Long
) {
    companion object {
        val ALLOWED_PERSISTED_FIELDS: Set<String> = setOf(
            "id", "windowId", "spaceId", "partition", "value", "origin",
            "promotedAtEpochMillis", "revision"
        )
    }
}

@Entity(
    tableName = "memory_observations",
    indices = [Index("windowId"), Index("spaceId")]
)
data class MemoryObservationEntity(
    @PrimaryKey val id: String,
    val windowId: String,
    val spaceId: String,
    val domain: String,
    val partition: String?,
    val normalizedValue: String,
    val sourceClass: String,
    val observedAtEpochMillis: Long,
    val confidence: Float,
    val provenanceHandle: String
) {
    companion object {
        val ALLOWED_PERSISTED_FIELDS: Set<String> = setOf(
            "id", "windowId", "spaceId", "domain", "partition", "normalizedValue",
            "sourceClass", "observedAtEpochMillis", "confidence", "provenanceHandle"
        )
    }
}

@Entity(
    tableName = "window_heartbeats",
    indices = [Index("spaceId")]
)
data class WindowHeartbeatEntity(
    @PrimaryKey val windowId: String,
    val spaceId: String,
    val enabled: Boolean,
    val minCooldownMillis: Long,
    val cooldownUntilEpochMillis: Long = 0L,
    val pendingJobId: String? = null,
    val updatedAtEpochMillis: Long
) {
    companion object {
        val ALLOWED_PERSISTED_FIELDS: Set<String> = setOf(
            "windowId", "spaceId", "enabled", "minCooldownMillis",
            "cooldownUntilEpochMillis", "pendingJobId", "updatedAtEpochMillis"
        )
    }
}
