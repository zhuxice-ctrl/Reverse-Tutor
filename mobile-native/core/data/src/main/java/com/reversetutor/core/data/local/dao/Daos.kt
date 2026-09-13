package com.reversetutor.core.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import com.reversetutor.core.data.local.entity.AnchorEntity
import com.reversetutor.core.data.local.entity.BackgroundJobEntity
import com.reversetutor.core.data.local.entity.ErrorLogEntity
import com.reversetutor.core.data.local.entity.ExportRecordEntity
import com.reversetutor.core.data.local.entity.GraphEdgeEntity
import com.reversetutor.core.data.local.entity.GraphNodeEntity
import com.reversetutor.core.data.local.entity.ImportBatchEntity
import com.reversetutor.core.data.local.entity.LlmProfileEntity
import com.reversetutor.core.data.local.entity.MemoryItemEntity
import com.reversetutor.core.data.local.entity.MessageAttachmentEntity
import com.reversetutor.core.data.local.entity.MessageEntity
import com.reversetutor.core.data.local.entity.MessageQuoteEntity
import com.reversetutor.core.data.local.entity.NoteEntity
import com.reversetutor.core.data.local.entity.SessionEntity
import com.reversetutor.core.data.local.entity.SessionSettingsEntity
import com.reversetutor.core.data.local.entity.SourceChunkEntity
import com.reversetutor.core.data.local.entity.SourceEntity
import com.reversetutor.core.data.local.entity.SpaceEntity
import com.reversetutor.core.data.local.entity.WindowEntity
import com.reversetutor.core.data.local.entity.WindowSnapshotEntity
import com.reversetutor.core.data.local.entity.WindowDeltaEntity
import com.reversetutor.core.data.local.entity.MergeCommitEntity
import com.reversetutor.core.data.local.entity.LearningFactReceiptEntity
import com.reversetutor.core.data.local.entity.ScopeSignalEntity
import com.reversetutor.core.data.local.entity.CompanionMemoryVersionEntity
import com.reversetutor.core.data.local.entity.MemoryObservationEntity
import com.reversetutor.core.data.local.entity.WindowHeartbeatEntity
import com.reversetutor.core.data.local.entity.AssistantReplyArtifactEntity
import com.reversetutor.core.data.local.entity.SessionDocumentEntity
import com.reversetutor.core.data.local.entity.SessionDocumentBlockEntity
import com.reversetutor.core.data.local.entity.SessionTableEntity
import com.reversetutor.core.data.local.entity.SessionTableColumnEntity
import com.reversetutor.core.data.local.entity.SessionTableRowEntity
import com.reversetutor.core.data.local.entity.ToolCallReceiptEntity

@Dao
interface SpaceDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(space: SpaceEntity)

    @Query("SELECT * FROM spaces WHERE id = :id")
    suspend fun getById(id: String): SpaceEntity?

    @Query("SELECT * FROM spaces ORDER BY updatedAtEpochMillis DESC")
    suspend fun listAll(): List<SpaceEntity>
}

@Dao
interface SessionDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(session: SessionEntity)

    @Query("SELECT * FROM sessions WHERE id = :id")
    suspend fun getById(id: String): SessionEntity?

    @Query("SELECT * FROM sessions WHERE spaceId = :spaceId AND archived = 0 ORDER BY pinned DESC, updatedAtEpochMillis DESC")
    suspend fun listBySpace(spaceId: String): List<SessionEntity>

    @Query("UPDATE sessions SET title = :title, updatedAtEpochMillis = :updatedAtEpochMillis WHERE id = :id")
    suspend fun rename(id: String, title: String, updatedAtEpochMillis: Long): Int

    @Query("UPDATE sessions SET pinned = :pinned, updatedAtEpochMillis = :updatedAtEpochMillis WHERE id = :id")
    suspend fun setPinned(id: String, pinned: Boolean, updatedAtEpochMillis: Long): Int

    @Query("UPDATE sessions SET archived = 1, updatedAtEpochMillis = :updatedAtEpochMillis WHERE id = :id")
    suspend fun archive(id: String, updatedAtEpochMillis: Long): Int

    @Query("UPDATE sessions SET modelBindingId = :modelBindingId WHERE id = :sessionId")
    suspend fun updateSessionModelBinding(sessionId: String, modelBindingId: String): Int

    @Query("UPDATE session_settings SET modelBindingId = :modelBindingId WHERE sessionId = :sessionId")
    suspend fun updateSessionSettingsModelBinding(sessionId: String, modelBindingId: String): Int

    @Transaction
    suspend fun setModelBinding(sessionId: String, modelBindingId: String): Boolean {
        val updated = updateSessionModelBinding(sessionId, modelBindingId)
        if (updated > 0) {
            updateSessionSettingsModelBinding(sessionId, modelBindingId)
        }
        return updated > 0
    }
}

@Dao
interface SessionSettingsDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(settings: SessionSettingsEntity)

    @Query("SELECT * FROM session_settings WHERE sessionId = :sessionId LIMIT 1")
    suspend fun getBySessionId(sessionId: String): SessionSettingsEntity?
}

@Dao
interface MessageDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(message: MessageEntity)

    @Query("SELECT * FROM messages WHERE sessionId = :sessionId ORDER BY createdAtEpochMillis ASC")
    suspend fun listBySession(sessionId: String): List<MessageEntity>

    @Query("DELETE FROM messages WHERE id = :id")
    suspend fun deleteById(id: String): Int
}

@Dao
interface MessageAttachmentDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(attachment: MessageAttachmentEntity)

    @Query("SELECT * FROM message_attachments WHERE messageId = :messageId ORDER BY name ASC")
    suspend fun listByMessageId(messageId: String): List<MessageAttachmentEntity>

    @Query("SELECT * FROM message_attachments WHERE messageId IN (:messageIds) ORDER BY messageId ASC, name ASC")
    suspend fun listByMessageIds(messageIds: List<String>): List<MessageAttachmentEntity>

    @Query("DELETE FROM message_attachments WHERE messageId = :messageId")
    suspend fun deleteByMessageId(messageId: String): Int
}

@Dao
interface MessageQuoteDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(quote: MessageQuoteEntity)

    @Query("SELECT * FROM message_quotes WHERE messageId = :messageId LIMIT 1")
    suspend fun getByMessageId(messageId: String): MessageQuoteEntity?

    @Query("DELETE FROM message_quotes WHERE messageId = :messageId")
    suspend fun deleteByMessageId(messageId: String): Int
}

@Dao
interface LlmProfileDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(profile: LlmProfileEntity)

    @Query("SELECT * FROM llm_profiles WHERE id = :id LIMIT 1")
    suspend fun getById(id: String): LlmProfileEntity?

    @Query("SELECT * FROM llm_profiles WHERE spaceId = :spaceId ORDER BY updatedAtEpochMillis DESC")
    suspend fun listBySpace(spaceId: String): List<LlmProfileEntity>

    @Query("SELECT * FROM llm_profiles ORDER BY updatedAtEpochMillis DESC")
    suspend fun listAll(): List<LlmProfileEntity>

    @Query("UPDATE llm_profiles SET enabled = CASE WHEN id = :enabledProfileId THEN 1 ELSE 0 END, updatedAtEpochMillis = :updatedAtEpochMillis WHERE spaceId = :spaceId")
    suspend fun setEnabledForSpace(spaceId: String, enabledProfileId: String, updatedAtEpochMillis: Long)

    @Query("DELETE FROM llm_profiles WHERE id = :id")
    suspend fun deleteById(id: String): Int
}

@Dao
interface MemoryDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAnchor(anchor: AnchorEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertNote(note: NoteEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertError(error: ErrorLogEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertMemoryItem(memoryItem: MemoryItemEntity)

    @Query("SELECT * FROM anchors WHERE spaceId = :spaceId ORDER BY createdAtEpochMillis DESC")
    suspend fun listAnchorsBySpace(spaceId: String): List<AnchorEntity>

    @Query("SELECT * FROM notes WHERE spaceId = :spaceId ORDER BY createdAtEpochMillis DESC")
    suspend fun listNotesBySpace(spaceId: String): List<NoteEntity>

    @Query("SELECT * FROM error_logs WHERE spaceId = :spaceId ORDER BY createdAtEpochMillis DESC")
    suspend fun listErrorsBySpace(spaceId: String): List<ErrorLogEntity>

    @Query("SELECT * FROM memory_items WHERE spaceId = :spaceId ORDER BY createdAtEpochMillis DESC")
    suspend fun listMemoryItemsBySpace(spaceId: String): List<MemoryItemEntity>

    @Query("UPDATE notes SET title = :title, body = :body WHERE id = :id")
    suspend fun updateNote(id: String, title: String, body: String): Int

    @Query("DELETE FROM notes WHERE id = :id")
    suspend fun deleteNote(id: String): Int

    @Query("DELETE FROM anchors WHERE id = :id")
    suspend fun deleteAnchor(id: String): Int

    @Query("UPDATE error_logs SET resolved = :resolved WHERE id = :id")
    suspend fun setErrorResolved(id: String, resolved: Boolean): Int

    @Query("DELETE FROM error_logs WHERE id = :id")
    suspend fun deleteError(id: String): Int

    @Query("DELETE FROM memory_items WHERE id = :id")
    suspend fun deleteMemoryItem(id: String): Int
}

@Dao
interface GraphDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertNode(node: GraphNodeEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertEdge(edge: GraphEdgeEntity)

    @Query("SELECT * FROM graph_nodes WHERE spaceId = :spaceId ORDER BY label ASC")
    suspend fun listNodesBySpace(spaceId: String): List<GraphNodeEntity>

    @Query(
        """
        SELECT DISTINCT graph_nodes.*
        FROM graph_nodes
        INNER JOIN memory_items
            ON memory_items.id = graph_nodes.sourceMemoryId
        INNER JOIN messages
            ON messages.id = memory_items.sourceMessageId
        WHERE messages.sessionId = :sessionId
        ORDER BY graph_nodes.label ASC
        """
    )
    suspend fun listNodesBySession(sessionId: String): List<GraphNodeEntity>

    @Query("SELECT * FROM graph_edges WHERE spaceId = :spaceId ORDER BY createdAtEpochMillis ASC")
    suspend fun listEdgesBySpace(spaceId: String): List<GraphEdgeEntity>
}

@Dao
interface SourceDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertSource(source: SourceEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertChunk(chunk: SourceChunkEntity)

    @Query("SELECT * FROM sources WHERE id = :id LIMIT 1")
    suspend fun getSourceById(id: String): SourceEntity?

    @Query("SELECT * FROM sources WHERE spaceId = :spaceId ORDER BY createdAtEpochMillis DESC")
    suspend fun listSourcesBySpace(spaceId: String): List<SourceEntity>

    @Query("SELECT * FROM source_chunks WHERE sourceId = :sourceId ORDER BY chunkIndex ASC")
    suspend fun listChunksForSource(sourceId: String): List<SourceChunkEntity>

    @Query("DELETE FROM source_chunks WHERE sourceId = :sourceId")
    suspend fun deleteChunksForSource(sourceId: String): Int

    @Query("UPDATE source_chunks SET embedding = :embedding WHERE id = :chunkId")
    suspend fun updateChunkEmbedding(chunkId: String, embedding: ByteArray)

    @Query("SELECT id, embedding FROM source_chunks WHERE spaceId = :spaceId AND embedding IS NOT NULL")
    suspend fun listChunkEmbeddingRows(spaceId: String): List<SourceChunkEmbeddingRow>
}

/** NEWMP-V1-024: lightweight projection of a stored chunk embedding. */
data class SourceChunkEmbeddingRow(
    val id: String,
    val embedding: ByteArray
)

@Dao
interface BackgroundJobDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(job: BackgroundJobEntity)

    @Query("SELECT * FROM background_jobs WHERE id = :id")
    suspend fun getById(id: String): BackgroundJobEntity?

    /** Atomically claims a queued job so only one Worker can invoke the Provider. */
    @Query(
        """
        UPDATE background_jobs
        SET status = :runningStatus,
            startedAtEpochMillis = :startedAtEpochMillis,
            errorMessage = NULL
        WHERE id = :id AND status = :queuedStatus
        """
    )
    suspend fun claimQueued(
        id: String,
        queuedStatus: String,
        runningStatus: String,
        startedAtEpochMillis: Long
    ): Int

    @Query("SELECT * FROM background_jobs WHERE kind IN ('Generation', 'Initiative') AND status IN (:statuses) ORDER BY createdAtEpochMillis ASC")
    suspend fun listGenerationByStatuses(statuses: List<String>): List<BackgroundJobEntity>

    @Query("SELECT * FROM background_jobs WHERE kind IN ('Generation', 'Initiative') AND sessionId = :sessionId ORDER BY createdAtEpochMillis ASC")
    suspend fun listGenerationBySession(sessionId: String): List<BackgroundJobEntity>

}

@Dao
interface ImportBatchDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(batch: ImportBatchEntity)

    @Query("SELECT * FROM import_batches WHERE id = :id")
    suspend fun getById(id: String): ImportBatchEntity?
}

@Dao
interface ExportRecordDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(record: ExportRecordEntity)

    @Query("SELECT * FROM export_records WHERE id = :id")
    suspend fun getById(id: String): ExportRecordEntity?
}

@Dao
interface WindowTopologyDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertWindow(window: WindowEntity)

    @Query("SELECT * FROM windows WHERE sessionId = :sessionId")
    suspend fun getWindow(sessionId: String): WindowEntity?

    @Query("SELECT * FROM windows WHERE spaceId = :spaceId ORDER BY createdAtEpochMillis ASC")
    suspend fun listWindows(spaceId: String): List<WindowEntity>

    @Query("DELETE FROM windows WHERE sessionId = :sessionId")
    suspend fun deleteWindow(sessionId: String): Int

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertSnapshot(snapshot: WindowSnapshotEntity)

    @Query("SELECT * FROM window_snapshots WHERE windowId = :windowId")
    suspend fun getSnapshot(windowId: String): WindowSnapshotEntity?

    @Query("DELETE FROM window_snapshots WHERE windowId = :windowId")
    suspend fun deleteSnapshots(windowId: String): Int

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertDelta(delta: WindowDeltaEntity)

    @Query("DELETE FROM window_deltas WHERE windowId = :windowId")
    suspend fun deleteDeltas(windowId: String): Int

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertMergeCommit(commit: MergeCommitEntity): Long

    @Query("SELECT * FROM merge_commits WHERE id = :id")
    suspend fun getMergeCommit(id: String): MergeCommitEntity?

    @Query("SELECT * FROM merge_commits WHERE childId = :childId ORDER BY sourceRevision ASC")
    suspend fun listMergeCommitsForChild(childId: String): List<MergeCommitEntity>
}

@Dao
interface LearningLedgerDao {
    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertReceipt(receipt: LearningFactReceiptEntity): Long

    @Query("SELECT * FROM learning_fact_receipts WHERE spaceId = :spaceId ORDER BY occurredAtEpochMillis ASC")
    suspend fun listFactsBySpace(spaceId: String): List<LearningFactReceiptEntity>

    @Query("SELECT * FROM learning_fact_receipts WHERE sourceWindowId = :windowId ORDER BY occurredAtEpochMillis ASC")
    suspend fun listFactsByWindow(windowId: String): List<LearningFactReceiptEntity>

    @Query("SELECT EXISTS(SELECT 1 FROM learning_fact_receipts WHERE sourceWindowId = :windowId AND sourceTurnId = :turnId)")
    suspend fun hasFactForTurn(windowId: String, turnId: String): Boolean

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertScopeSignal(signal: ScopeSignalEntity): Long

    @Query("SELECT * FROM scope_signals WHERE windowId = :windowId ORDER BY occurredAtEpochMillis ASC")
    suspend fun listScopeSignals(windowId: String): List<ScopeSignalEntity>

    @Query("SELECT * FROM scope_signals WHERE spaceId = :spaceId ORDER BY occurredAtEpochMillis ASC")
    suspend fun listScopeSignalsBySpace(spaceId: String): List<ScopeSignalEntity>
}

@Dao
interface CompanionMemoryDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertVersion(version: CompanionMemoryVersionEntity)

    @Query("SELECT * FROM companion_memory_versions WHERE windowId = :windowId")
    suspend fun listVersions(windowId: String): List<CompanionMemoryVersionEntity>

    @Query("SELECT * FROM companion_memory_versions WHERE windowId = :windowId AND partition = :partition")
    suspend fun getVersion(windowId: String, partition: String): CompanionMemoryVersionEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertObservation(observation: MemoryObservationEntity)

    @Query("SELECT * FROM memory_observations WHERE windowId = :windowId ORDER BY observedAtEpochMillis ASC")
    suspend fun listObservations(windowId: String): List<MemoryObservationEntity>

    @Query("SELECT * FROM memory_observations WHERE spaceId = :spaceId ORDER BY observedAtEpochMillis ASC")
    suspend fun listObservationsBySpace(spaceId: String): List<MemoryObservationEntity>
}

@Dao
interface WindowHeartbeatDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertHeartbeat(heartbeat: WindowHeartbeatEntity)

    @Query("SELECT * FROM window_heartbeats WHERE windowId = :windowId")
    suspend fun getHeartbeat(windowId: String): WindowHeartbeatEntity?

    @Query("SELECT * FROM window_heartbeats WHERE spaceId = :spaceId")
    suspend fun listBySpace(spaceId: String): List<WindowHeartbeatEntity>

    @Query("SELECT * FROM window_heartbeats")
    suspend fun listAll(): List<WindowHeartbeatEntity>

    @Query("DELETE FROM window_heartbeats WHERE windowId = :windowId")
    suspend fun deleteHeartbeat(windowId: String): Int
}

@Dao
interface SessionAgentDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertArtifact(artifact: AssistantReplyArtifactEntity)

    @Query("SELECT * FROM assistant_reply_artifacts WHERE assistantMessageId = :assistantMessageId AND sessionId = :sessionId")
    suspend fun getArtifact(sessionId: String, assistantMessageId: String): AssistantReplyArtifactEntity?

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertDocument(document: SessionDocumentEntity): Long

    @Query("SELECT * FROM session_documents WHERE id = :documentId AND sessionId = :sessionId")
    suspend fun getDocument(sessionId: String, documentId: String): SessionDocumentEntity?

    @Query("SELECT * FROM session_document_blocks WHERE id = :blockId AND documentId = :documentId")
    suspend fun getBlock(documentId: String, blockId: String): SessionDocumentBlockEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertBlock(block: SessionDocumentBlockEntity)

    @Query("SELECT * FROM session_document_blocks WHERE documentId = :documentId ORDER BY ordinal ASC")
    suspend fun listBlocks(documentId: String): List<SessionDocumentBlockEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertTable(table: SessionTableEntity)

    @Query("SELECT session_tables.* FROM session_tables INNER JOIN session_documents ON session_tables.documentId = session_documents.id WHERE session_tables.id = :tableId AND session_documents.sessionId = :sessionId")
    suspend fun getTable(sessionId: String, tableId: String): SessionTableEntity?

    @Query("SELECT * FROM session_table_columns WHERE tableId = :tableId ORDER BY ordinal ASC")
    suspend fun listColumns(tableId: String): List<SessionTableColumnEntity>

    @Query("SELECT * FROM session_table_rows WHERE tableId = :tableId ORDER BY rowKey ASC")
    suspend fun listRows(tableId: String): List<SessionTableRowEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertColumn(column: SessionTableColumnEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertRow(row: SessionTableRowEntity)

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertReceipt(receipt: ToolCallReceiptEntity): Long

    @Query("SELECT * FROM tool_call_receipts WHERE callId = :callId")
    suspend fun getReceipt(callId: String): ToolCallReceiptEntity?

    /**
     * The document and its receipt share one transaction: a failed document
     * insert must never leave a completed idempotency receipt behind.
     */
    @Transaction
    suspend fun createDocumentWithReceipt(
        document: SessionDocumentEntity,
        blocks: List<SessionDocumentBlockEntity>,
        receipt: ToolCallReceiptEntity
    ): Boolean {
        insertDocument(document)
        blocks.forEach { block -> upsertBlock(block) }
        insertReceipt(receipt)
        return true
    }

    @Transaction
    suspend fun replaceBlockWithReceipt(
        block: SessionDocumentBlockEntity,
        receipt: ToolCallReceiptEntity
    ): Boolean {
        upsertBlock(block)
        insertReceipt(receipt)
        return true
    }

    @Transaction
    suspend fun createTableWithReceipt(
        table: SessionTableEntity,
        columns: List<SessionTableColumnEntity>,
        receipt: ToolCallReceiptEntity
    ): Boolean {
        upsertTable(table)
        columns.forEach { column -> upsertColumn(column) }
        insertReceipt(receipt)
        return true
    }

    @Transaction
    suspend fun upsertRowWithReceipt(
        row: SessionTableRowEntity,
        receipt: ToolCallReceiptEntity
    ): Boolean {
        upsertRow(row)
        insertReceipt(receipt)
        return true
    }
}
