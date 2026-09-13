package com.reversetutor.core.data.local

import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

object DatabaseSchema {
    const val version = 13
    const val exportSchema = true

    val migration1To2: Migration = object : Migration(1, 2) {
        override fun migrate(db: SupportSQLiteDatabase) {
            db.execSQL("ALTER TABLE background_jobs ADD COLUMN startedAtEpochMillis INTEGER")
            db.execSQL("ALTER TABLE background_jobs ADD COLUMN userMessageId TEXT")
            db.execSQL("ALTER TABLE background_jobs ADD COLUMN userText TEXT")
            db.execSQL("ALTER TABLE background_jobs ADD COLUMN generationToken TEXT")
            db.execSQL("ALTER TABLE background_jobs ADD COLUMN quoteExcerpt TEXT")
            db.execSQL("ALTER TABLE background_jobs ADD COLUMN imageAttachmentsPayload TEXT")
            db.execSQL("ALTER TABLE background_jobs ADD COLUMN contextEvidencePayload TEXT")
        }
    }

    val migration2To3: Migration = object : Migration(2, 3) {
        override fun migrate(db: SupportSQLiteDatabase) {
            db.execSQL("ALTER TABLE sessions ADD COLUMN modelBindingId TEXT")
            db.execSQL("UPDATE sessions SET modelBindingId = llmProfileId WHERE llmProfileId IS NOT NULL")
            db.execSQL("CREATE INDEX IF NOT EXISTS index_sessions_modelBindingId ON sessions(modelBindingId)")
            db.execSQL("ALTER TABLE session_settings ADD COLUMN modelBindingId TEXT")
            db.execSQL("UPDATE session_settings SET modelBindingId = llmProfileId WHERE llmProfileId IS NOT NULL")
            db.execSQL("CREATE INDEX IF NOT EXISTS index_session_settings_modelBindingId ON session_settings(modelBindingId)")
            db.execSQL("ALTER TABLE background_jobs ADD COLUMN modelBindingId TEXT")

            createHybridTables(db)
            migrateLegacyProfiles(db)
        }
    }

    val migration3To4: Migration = object : Migration(3, 4) {
        override fun migrate(db: SupportSQLiteDatabase) {
            worldTreeTableSql.forEach(db::execSQL)
            worldTreeIndexSql.forEach(db::execSQL)
        }
    }

    val migration4To5: Migration = object : Migration(4, 5) {
        override fun migrate(db: SupportSQLiteDatabase) {
            db.execSQL(
                "ALTER TABLE error_logs ADD COLUMN origin TEXT NOT NULL DEFAULT 'Learning'"
            )
            db.execSQL("ALTER TABLE error_logs ADD COLUMN code TEXT")
            db.execSQL(
                "CREATE INDEX IF NOT EXISTS index_error_logs_spaceId_origin_createdAtEpochMillis " +
                    "ON error_logs(spaceId, origin, createdAtEpochMillis)"
            )
        }
    }

    val migration5To6: Migration = object : Migration(5, 6) {
        override fun migrate(db: SupportSQLiteDatabase) {
            db.execSQL("ALTER TABLE background_jobs ADD COLUMN sessionPolicyPayload TEXT")
        }
    }

    val migration6To7: Migration = object : Migration(6, 7) {
        override fun migrate(db: SupportSQLiteDatabase) {
            windowTopologyTableSql.forEach(db::execSQL)
            windowTopologyIndexSql.forEach(db::execSQL)
            db.execSQL(
                """
                INSERT INTO windows (sessionId, spaceId, rootId, parentId, kind, createdAtEpochMillis)
                SELECT id, spaceId, id, NULL, 'TASK_ROOT', createdAtEpochMillis FROM sessions
                """.trimIndent()
            )
        }
    }

    val migration7To8: Migration = object : Migration(7, 8) {
        override fun migrate(db: SupportSQLiteDatabase) {
            learningLedgerTableSql.forEach(db::execSQL)
            learningLedgerIndexSql.forEach(db::execSQL)
        }
    }

    val migration8To9: Migration = object : Migration(8, 9) {
        override fun migrate(db: SupportSQLiteDatabase) {
            companionHeartbeatTableSql.forEach(db::execSQL)
            companionHeartbeatIndexSql.forEach(db::execSQL)
        }
    }

    val migration9To10: Migration = object : Migration(9, 10) {
        override fun migrate(db: SupportSQLiteDatabase) {
            db.execSQL("ALTER TABLE background_jobs ADD COLUMN assistantTurnEnvelopePayload TEXT")
        }
    }

    /** P6 rich-reply artifacts and session-scoped document/table tool state. */
    val migration10To11: Migration = object : Migration(10, 11) {
        override fun migrate(db: SupportSQLiteDatabase) {
            sessionAgentTableSql.forEach(db::execSQL)
            sessionAgentIndexSql.forEach(db::execSQL)
        }
    }

    val migration11To12: Migration = object : Migration(11, 12) {
        override fun migrate(db: SupportSQLiteDatabase) {
            db.execSQL("ALTER TABLE assistant_reply_artifacts ADD COLUMN checkPlanPayload TEXT")
        }
    }

    /** NEWMP-V1-024: optional per-chunk embedding vectors for semantic retrieval. */
    val migration12To13: Migration = object : Migration(12, 13) {
        override fun migrate(db: SupportSQLiteDatabase) {
            db.execSQL("ALTER TABLE source_chunks ADD COLUMN embedding BLOB")
        }
    }

    val migrations: Array<Migration> = arrayOf(
        migration1To2,
        migration2To3,
        migration3To4,
        migration4To5,
        migration5To6,
        migration6To7,
        migration7To8,
        migration8To9,
        migration9To10,
        migration10To11,
        migration11To12,
        migration12To13
    )

    private fun createHybridTables(db: SupportSQLiteDatabase) {
        hybridTableSql.forEach(db::execSQL)
        hybridIndexSql.forEach(db::execSQL)
    }

    private fun migrateLegacyProfiles(db: SupportSQLiteDatabase) {
        db.execSQL(
            """
            INSERT INTO provider_connections (
                id, spaceId, name, protocol, providerName, baseUrl, secretRef, enabled,
                createdAtEpochMillis, updatedAtEpochMillis
            )
            SELECT
                'connection-' || id,
                spaceId,
                name,
                CASE
                    WHEN provider = 'AnthropicCompatible' THEN 'AnthropicCompatible'
                    WHEN provider IN ('Gemini', 'GeminiNative') THEN 'GeminiNative'
                    ELSE 'OpenAiCompatible'
                END,
                provider,
                baseUrl,
                secretRef,
                enabled,
                createdAtEpochMillis,
                updatedAtEpochMillis
            FROM llm_profiles
            """.trimIndent()
        )
        db.execSQL(
            """
            INSERT INTO model_bindings (
                id, spaceId, connectionId, modelId, displayName, availability, isDefault, enabled,
                lastCheckedAtEpochMillis, lastUsedAtEpochMillis, createdAtEpochMillis, updatedAtEpochMillis
            )
            SELECT
                id,
                spaceId,
                'connection-' || id,
                model,
                model,
                'Untested',
                enabled,
                enabled,
                NULL,
                NULL,
                createdAtEpochMillis,
                updatedAtEpochMillis
            FROM llm_profiles
            """.trimIndent()
        )
    }

    private val hybridTableSql = listOf(
        """
        CREATE TABLE IF NOT EXISTS provider_connections (
            id TEXT NOT NULL,
            spaceId TEXT NOT NULL,
            name TEXT NOT NULL,
            protocol TEXT NOT NULL,
            providerName TEXT,
            baseUrl TEXT,
            secretRef TEXT,
            enabled INTEGER NOT NULL,
            createdAtEpochMillis INTEGER NOT NULL,
            updatedAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(id)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS model_bindings (
            id TEXT NOT NULL,
            spaceId TEXT NOT NULL,
            connectionId TEXT NOT NULL,
            modelId TEXT NOT NULL,
            displayName TEXT NOT NULL,
            availability TEXT NOT NULL,
            isDefault INTEGER NOT NULL,
            enabled INTEGER NOT NULL,
            lastCheckedAtEpochMillis INTEGER,
            lastUsedAtEpochMillis INTEGER,
            createdAtEpochMillis INTEGER NOT NULL,
            updatedAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(id),
            FOREIGN KEY(connectionId) REFERENCES provider_connections(id) ON UPDATE NO ACTION ON DELETE CASCADE
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS context_snapshots (
            id TEXT NOT NULL,
            spaceId TEXT NOT NULL,
            sessionId TEXT NOT NULL,
            turnId TEXT NOT NULL,
            version INTEGER NOT NULL,
            messageIdsPayload TEXT NOT NULL,
            parentTurnId TEXT,
            maxSequence INTEGER NOT NULL,
            createdAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(id)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS turn_runs (
            id TEXT NOT NULL,
            spaceId TEXT NOT NULL,
            turnId TEXT NOT NULL,
            sessionId TEXT NOT NULL,
            userMessageId TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            contextVersion INTEGER NOT NULL,
            modelBindingId TEXT NOT NULL,
            parentTurnId TEXT,
            contextSnapshotId TEXT,
            attempt INTEGER NOT NULL,
            state TEXT NOT NULL,
            createdAtEpochMillis INTEGER NOT NULL,
            startedAtEpochMillis INTEGER,
            completedAtEpochMillis INTEGER,
            resultMessageId TEXT,
            errorCode TEXT,
            errorRetryable INTEGER,
            errorSafeMessage TEXT,
            errorUserAction TEXT,
            PRIMARY KEY(id),
            FOREIGN KEY(modelBindingId) REFERENCES model_bindings(id) ON UPDATE NO ACTION ON DELETE RESTRICT
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS study_plan_tasks (
            id TEXT NOT NULL,
            spaceId TEXT NOT NULL,
            title TEXT NOT NULL,
            detail TEXT,
            state TEXT NOT NULL,
            dueAtEpochMillis INTEGER,
            completedAtEpochMillis INTEGER,
            sourceSessionId TEXT,
            sourceMessageId TEXT,
            revision INTEGER NOT NULL,
            createdAtEpochMillis INTEGER NOT NULL,
            updatedAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(id)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS weekly_summaries (
            id TEXT NOT NULL,
            spaceId TEXT NOT NULL,
            weekStartEpochMillis INTEGER NOT NULL,
            weekEndEpochMillis INTEGER NOT NULL,
            sourceRevision INTEGER NOT NULL,
            generatorVersion TEXT NOT NULL,
            summary TEXT NOT NULL,
            generatedAtEpochMillis INTEGER NOT NULL,
            stale INTEGER NOT NULL,
            PRIMARY KEY(id)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS token_usage_records (
            id TEXT NOT NULL,
            spaceId TEXT NOT NULL,
            turnId TEXT NOT NULL,
            attempt INTEGER NOT NULL,
            modelBindingId TEXT,
            providerUsageId TEXT,
            inputTokens INTEGER NOT NULL,
            outputTokens INTEGER NOT NULL,
            cachedTokens INTEGER NOT NULL,
            reasoningTokens INTEGER NOT NULL,
            totalTokens INTEGER NOT NULL,
            estimated INTEGER NOT NULL,
            createdAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(id)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS widget_layout_preferences (
            spaceId TEXT NOT NULL,
            widgetId TEXT NOT NULL,
            `order` INTEGER NOT NULL,
            hidden INTEGER NOT NULL,
            size TEXT NOT NULL,
            updatedAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(spaceId, widgetId)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS search_documents (
            id TEXT NOT NULL,
            spaceId TEXT NOT NULL,
            entityType TEXT NOT NULL,
            entityId TEXT NOT NULL,
            sessionId TEXT,
            parentEntityId TEXT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            normalizedText TEXT NOT NULL,
            updatedAtEpochMillis INTEGER NOT NULL,
            rebuildRequired INTEGER NOT NULL,
            PRIMARY KEY(id)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS sync_outbox (
            id TEXT NOT NULL,
            spaceId TEXT NOT NULL,
            entityId TEXT NOT NULL,
            entityType TEXT NOT NULL,
            ownerId TEXT NOT NULL,
            deviceId TEXT NOT NULL,
            revision INTEGER NOT NULL,
            idempotencyKey TEXT NOT NULL,
            ownership TEXT NOT NULL,
            operation TEXT NOT NULL,
            payload TEXT,
            updatedAtEpochMillis INTEGER NOT NULL,
            deletedAtEpochMillis INTEGER,
            retryCount INTEGER NOT NULL,
            nextAttemptAtEpochMillis INTEGER NOT NULL,
            status TEXT NOT NULL,
            lastError TEXT,
            PRIMARY KEY(id)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS sync_cursors (
            id TEXT NOT NULL,
            spaceId TEXT NOT NULL,
            entityType TEXT NOT NULL,
            cursor TEXT,
            revision INTEGER NOT NULL,
            updatedAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(id)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS sync_conflicts (
            id TEXT NOT NULL,
            spaceId TEXT NOT NULL,
            entityId TEXT NOT NULL,
            entityType TEXT NOT NULL,
            localRevision INTEGER NOT NULL,
            remoteRevision INTEGER NOT NULL,
            localPayload TEXT,
            remotePayload TEXT,
            state TEXT NOT NULL,
            resolution TEXT,
            createdAtEpochMillis INTEGER NOT NULL,
            resolvedAtEpochMillis INTEGER,
            PRIMARY KEY(id)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS entity_tombstones (
            id TEXT NOT NULL,
            spaceId TEXT NOT NULL,
            entityType TEXT NOT NULL,
            entityId TEXT NOT NULL,
            revision INTEGER NOT NULL,
            deletedAtEpochMillis INTEGER NOT NULL,
            idempotencyKey TEXT,
            PRIMARY KEY(id)
        )
        """.trimIndent()
    )

    private val hybridIndexSql = listOf(
        "CREATE INDEX IF NOT EXISTS index_provider_connections_spaceId ON provider_connections(spaceId)",
        "CREATE INDEX IF NOT EXISTS index_provider_connections_protocol ON provider_connections(protocol)",
        "CREATE INDEX IF NOT EXISTS index_model_bindings_spaceId ON model_bindings(spaceId)",
        "CREATE INDEX IF NOT EXISTS index_model_bindings_connectionId ON model_bindings(connectionId)",
        "CREATE INDEX IF NOT EXISTS index_model_bindings_availability ON model_bindings(availability)",
        "CREATE INDEX IF NOT EXISTS index_model_bindings_spaceId_isDefault ON model_bindings(spaceId, isDefault)",
        "CREATE INDEX IF NOT EXISTS index_context_snapshots_spaceId ON context_snapshots(spaceId)",
        "CREATE INDEX IF NOT EXISTS index_context_snapshots_sessionId ON context_snapshots(sessionId)",
        "CREATE UNIQUE INDEX IF NOT EXISTS index_context_snapshots_turnId_version ON context_snapshots(turnId, version)",
        "CREATE INDEX IF NOT EXISTS index_turn_runs_spaceId ON turn_runs(spaceId)",
        "CREATE INDEX IF NOT EXISTS index_turn_runs_sessionId ON turn_runs(sessionId)",
        "CREATE INDEX IF NOT EXISTS index_turn_runs_state ON turn_runs(state)",
        "CREATE INDEX IF NOT EXISTS index_turn_runs_modelBindingId ON turn_runs(modelBindingId)",
        "CREATE UNIQUE INDEX IF NOT EXISTS index_turn_runs_turnId_attempt ON turn_runs(turnId, attempt)",
        "CREATE INDEX IF NOT EXISTS index_turn_runs_sessionId_sequence ON turn_runs(sessionId, sequence)",
        "CREATE INDEX IF NOT EXISTS index_study_plan_tasks_spaceId ON study_plan_tasks(spaceId)",
        "CREATE INDEX IF NOT EXISTS index_study_plan_tasks_state ON study_plan_tasks(state)",
        "CREATE INDEX IF NOT EXISTS index_study_plan_tasks_sourceSessionId ON study_plan_tasks(sourceSessionId)",
        "CREATE INDEX IF NOT EXISTS index_study_plan_tasks_updatedAtEpochMillis ON study_plan_tasks(updatedAtEpochMillis)",
        "CREATE INDEX IF NOT EXISTS index_weekly_summaries_spaceId ON weekly_summaries(spaceId)",
        "CREATE UNIQUE INDEX IF NOT EXISTS index_weekly_summaries_spaceId_weekStartEpochMillis_sourceRevision_generatorVersion ON weekly_summaries(spaceId, weekStartEpochMillis, sourceRevision, generatorVersion)",
        "CREATE INDEX IF NOT EXISTS index_token_usage_records_spaceId ON token_usage_records(spaceId)",
        "CREATE INDEX IF NOT EXISTS index_token_usage_records_modelBindingId ON token_usage_records(modelBindingId)",
        "CREATE UNIQUE INDEX IF NOT EXISTS index_token_usage_records_turnId_attempt ON token_usage_records(turnId, attempt)",
        "CREATE INDEX IF NOT EXISTS index_token_usage_records_createdAtEpochMillis ON token_usage_records(createdAtEpochMillis)",
        "CREATE INDEX IF NOT EXISTS index_widget_layout_preferences_spaceId_order ON widget_layout_preferences(spaceId, `order`)",
        "CREATE INDEX IF NOT EXISTS index_search_documents_spaceId ON search_documents(spaceId)",
        "CREATE INDEX IF NOT EXISTS index_search_documents_entityType ON search_documents(entityType)",
        "CREATE INDEX IF NOT EXISTS index_search_documents_sessionId ON search_documents(sessionId)",
        "CREATE UNIQUE INDEX IF NOT EXISTS index_search_documents_entityType_entityId ON search_documents(entityType, entityId)",
        "CREATE INDEX IF NOT EXISTS index_sync_outbox_spaceId ON sync_outbox(spaceId)",
        "CREATE INDEX IF NOT EXISTS index_sync_outbox_entityType ON sync_outbox(entityType)",
        "CREATE INDEX IF NOT EXISTS index_sync_outbox_nextAttemptAtEpochMillis ON sync_outbox(nextAttemptAtEpochMillis)",
        "CREATE INDEX IF NOT EXISTS index_sync_outbox_status ON sync_outbox(status)",
        "CREATE UNIQUE INDEX IF NOT EXISTS index_sync_outbox_idempotencyKey ON sync_outbox(idempotencyKey)",
        "CREATE INDEX IF NOT EXISTS index_sync_cursors_spaceId ON sync_cursors(spaceId)",
        "CREATE UNIQUE INDEX IF NOT EXISTS index_sync_cursors_spaceId_entityType ON sync_cursors(spaceId, entityType)",
        "CREATE INDEX IF NOT EXISTS index_sync_conflicts_spaceId ON sync_conflicts(spaceId)",
        "CREATE INDEX IF NOT EXISTS index_sync_conflicts_entityType ON sync_conflicts(entityType)",
        "CREATE INDEX IF NOT EXISTS index_sync_conflicts_state ON sync_conflicts(state)",
        "CREATE INDEX IF NOT EXISTS index_sync_conflicts_entityId ON sync_conflicts(entityId)",
        "CREATE INDEX IF NOT EXISTS index_entity_tombstones_spaceId ON entity_tombstones(spaceId)",
        "CREATE INDEX IF NOT EXISTS index_entity_tombstones_entityType ON entity_tombstones(entityType)",
        "CREATE INDEX IF NOT EXISTS index_entity_tombstones_entityId ON entity_tombstones(entityId)",
        "CREATE INDEX IF NOT EXISTS index_entity_tombstones_deletedAtEpochMillis ON entity_tombstones(deletedAtEpochMillis)"
    )

    private val worldTreeTableSql = listOf(
        """
        CREATE TABLE IF NOT EXISTS world_tree_drafts (
            id TEXT NOT NULL,
            spaceId TEXT NOT NULL,
            sessionId TEXT,
            templateId TEXT,
            title TEXT NOT NULL,
            mode TEXT NOT NULL,
            schemaVersion INTEGER NOT NULL,
            state TEXT NOT NULL,
            createdAtEpochMillis INTEGER NOT NULL,
            updatedAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(id),
            FOREIGN KEY(spaceId) REFERENCES spaces(id) ON UPDATE NO ACTION ON DELETE CASCADE,
            FOREIGN KEY(sessionId) REFERENCES sessions(id) ON UPDATE NO ACTION ON DELETE SET NULL
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS world_tree_sections (
            id TEXT NOT NULL,
            draftId TEXT NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            orderIndex INTEGER NOT NULL,
            payloadJson TEXT NOT NULL,
            required INTEGER NOT NULL,
            completed INTEGER NOT NULL,
            updatedAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(id),
            FOREIGN KEY(draftId) REFERENCES world_tree_drafts(id) ON UPDATE NO ACTION ON DELETE CASCADE
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS world_tree_source_cross_ref (
            draftId TEXT NOT NULL,
            sourceId TEXT NOT NULL,
            orderIndex INTEGER NOT NULL,
            PRIMARY KEY(draftId, sourceId),
            FOREIGN KEY(draftId) REFERENCES world_tree_drafts(id) ON UPDATE NO ACTION ON DELETE CASCADE,
            FOREIGN KEY(sourceId) REFERENCES sources(id) ON UPDATE NO ACTION ON DELETE RESTRICT
        )
        """.trimIndent()
    )

    private val worldTreeIndexSql = listOf(
        "CREATE INDEX IF NOT EXISTS index_world_tree_drafts_spaceId ON world_tree_drafts(spaceId)",
        "CREATE UNIQUE INDEX IF NOT EXISTS index_world_tree_drafts_sessionId ON world_tree_drafts(sessionId)",
        "CREATE INDEX IF NOT EXISTS index_world_tree_sections_draftId ON world_tree_sections(draftId)",
        "CREATE UNIQUE INDEX IF NOT EXISTS index_world_tree_sections_draftId_orderIndex ON world_tree_sections(draftId, orderIndex)",
        "CREATE INDEX IF NOT EXISTS index_world_tree_source_cross_ref_sourceId ON world_tree_source_cross_ref(sourceId)",
        "CREATE UNIQUE INDEX IF NOT EXISTS index_world_tree_source_cross_ref_draftId_orderIndex ON world_tree_source_cross_ref(draftId, orderIndex)"
    )

    private val windowTopologyTableSql = listOf(
        """
        CREATE TABLE IF NOT EXISTS windows (
            sessionId TEXT NOT NULL,
            spaceId TEXT NOT NULL,
            rootId TEXT NOT NULL,
            parentId TEXT,
            kind TEXT NOT NULL,
            createdAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(sessionId)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS window_snapshots (
            windowId TEXT NOT NULL,
            ancestorRevision INTEGER NOT NULL,
            forkedAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(windowId)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS window_deltas (
            id TEXT NOT NULL,
            windowId TEXT NOT NULL,
            deltaId TEXT NOT NULL,
            payloadHandle TEXT NOT NULL,
            sourceRevision INTEGER NOT NULL,
            PRIMARY KEY(id)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS merge_commits (
            id TEXT NOT NULL,
            childId TEXT NOT NULL,
            parentId TEXT NOT NULL,
            deltaId TEXT NOT NULL,
            sourceRevision INTEGER NOT NULL,
            spaceId TEXT NOT NULL,
            PRIMARY KEY(id)
        )
        """.trimIndent()
    )

    private val windowTopologyIndexSql = listOf(
        "CREATE INDEX IF NOT EXISTS index_windows_spaceId ON windows(spaceId)",
        "CREATE INDEX IF NOT EXISTS index_windows_rootId ON windows(rootId)",
        "CREATE INDEX IF NOT EXISTS index_windows_parentId ON windows(parentId)",
        "CREATE INDEX IF NOT EXISTS index_window_snapshots_windowId ON window_snapshots(windowId)",
        "CREATE INDEX IF NOT EXISTS index_window_deltas_windowId ON window_deltas(windowId)",
        "CREATE INDEX IF NOT EXISTS index_merge_commits_childId ON merge_commits(childId)",
        "CREATE INDEX IF NOT EXISTS index_merge_commits_parentId ON merge_commits(parentId)",
        "CREATE INDEX IF NOT EXISTS index_merge_commits_spaceId ON merge_commits(spaceId)"
    )

    private val learningLedgerTableSql = listOf(
        """
        CREATE TABLE IF NOT EXISTS learning_fact_receipts (
            id TEXT NOT NULL,
            spaceId TEXT NOT NULL,
            knowledgePoint TEXT NOT NULL,
            evidenceType TEXT NOT NULL,
            result TEXT NOT NULL,
            confidence REAL NOT NULL,
            sourceWindowId TEXT NOT NULL,
            sourceTurnId TEXT NOT NULL,
            occurredAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(id)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS scope_signals (
            id TEXT NOT NULL,
            windowId TEXT NOT NULL,
            spaceId TEXT NOT NULL,
            category TEXT NOT NULL,
            count INTEGER NOT NULL,
            sourceTurnId TEXT NOT NULL,
            occurredAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(id)
        )
        """.trimIndent()
    )

    private val learningLedgerIndexSql = listOf(
        "CREATE INDEX IF NOT EXISTS index_learning_fact_receipts_spaceId ON learning_fact_receipts(spaceId)",
        "CREATE INDEX IF NOT EXISTS index_learning_fact_receipts_knowledgePoint ON learning_fact_receipts(knowledgePoint)",
        "CREATE INDEX IF NOT EXISTS index_learning_fact_receipts_sourceWindowId ON learning_fact_receipts(sourceWindowId)",
        "CREATE INDEX IF NOT EXISTS index_scope_signals_windowId ON scope_signals(windowId)",
        "CREATE INDEX IF NOT EXISTS index_scope_signals_spaceId ON scope_signals(spaceId)"
    )

    private val companionHeartbeatTableSql = listOf(
        """
        CREATE TABLE IF NOT EXISTS companion_memory_versions (
            id TEXT NOT NULL,
            windowId TEXT NOT NULL,
            spaceId TEXT NOT NULL,
            partition TEXT NOT NULL,
            value TEXT NOT NULL,
            origin TEXT NOT NULL,
            promotedAtEpochMillis INTEGER NOT NULL,
            revision INTEGER NOT NULL,
            PRIMARY KEY(id)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS memory_observations (
            id TEXT NOT NULL,
            windowId TEXT NOT NULL,
            spaceId TEXT NOT NULL,
            domain TEXT NOT NULL,
            partition TEXT,
            normalizedValue TEXT NOT NULL,
            sourceClass TEXT NOT NULL,
            observedAtEpochMillis INTEGER NOT NULL,
            confidence REAL NOT NULL,
            provenanceHandle TEXT NOT NULL,
            PRIMARY KEY(id)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS window_heartbeats (
            windowId TEXT NOT NULL,
            spaceId TEXT NOT NULL,
            enabled INTEGER NOT NULL,
            minCooldownMillis INTEGER NOT NULL,
            cooldownUntilEpochMillis INTEGER NOT NULL DEFAULT 0,
            pendingJobId TEXT,
            updatedAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(windowId)
        )
        """.trimIndent()
    )

    private val companionHeartbeatIndexSql = listOf(
        "CREATE INDEX IF NOT EXISTS index_companion_memory_versions_windowId ON companion_memory_versions(windowId)",
        "CREATE INDEX IF NOT EXISTS index_companion_memory_versions_spaceId ON companion_memory_versions(spaceId)",
        "CREATE INDEX IF NOT EXISTS index_memory_observations_windowId ON memory_observations(windowId)",
        "CREATE INDEX IF NOT EXISTS index_memory_observations_spaceId ON memory_observations(spaceId)",
        "CREATE INDEX IF NOT EXISTS index_window_heartbeats_spaceId ON window_heartbeats(spaceId)"
    )

    private val sessionAgentTableSql = listOf(
        """
        CREATE TABLE IF NOT EXISTS assistant_reply_artifacts (
            assistantMessageId TEXT NOT NULL,
            sessionId TEXT NOT NULL,
            blocksPayload TEXT NOT NULL,
            evidenceReferencesPayload TEXT NOT NULL,
            toolResultsPayload TEXT NOT NULL,
            checkPlanPayload TEXT,
            createdAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(assistantMessageId)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS session_documents (
            id TEXT NOT NULL,
            spaceId TEXT NOT NULL,
            sessionId TEXT NOT NULL,
            title TEXT NOT NULL,
            kind TEXT NOT NULL,
            createdAtEpochMillis INTEGER NOT NULL,
            updatedAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(id)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS session_document_blocks (
            id TEXT NOT NULL,
            documentId TEXT NOT NULL,
            ordinal INTEGER NOT NULL,
            kind TEXT NOT NULL,
            payload TEXT NOT NULL,
            updatedAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(id)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS session_tables (
            id TEXT NOT NULL,
            documentId TEXT NOT NULL,
            title TEXT NOT NULL,
            createdAtEpochMillis INTEGER NOT NULL,
            updatedAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(id)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS session_table_columns (
            id TEXT NOT NULL,
            tableId TEXT NOT NULL,
            ordinal INTEGER NOT NULL,
            name TEXT NOT NULL,
            valueType TEXT NOT NULL,
            PRIMARY KEY(id)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS session_table_rows (
            id TEXT NOT NULL,
            tableId TEXT NOT NULL,
            rowKey TEXT NOT NULL,
            cellsPayload TEXT NOT NULL,
            updatedAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(id)
        )
        """.trimIndent(),
        """
        CREATE TABLE IF NOT EXISTS tool_call_receipts (
            callId TEXT NOT NULL,
            sessionId TEXT NOT NULL,
            toolName TEXT NOT NULL,
            status TEXT NOT NULL,
            safeResultPayload TEXT NOT NULL,
            completedAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(callId)
        )
        """.trimIndent()
    )

    private val sessionAgentIndexSql = listOf(
        "CREATE INDEX IF NOT EXISTS index_assistant_reply_artifacts_sessionId ON assistant_reply_artifacts(sessionId)",
        "CREATE INDEX IF NOT EXISTS index_session_documents_spaceId ON session_documents(spaceId)",
        "CREATE INDEX IF NOT EXISTS index_session_documents_sessionId ON session_documents(sessionId)",
        "CREATE INDEX IF NOT EXISTS index_session_document_blocks_documentId ON session_document_blocks(documentId)",
        "CREATE INDEX IF NOT EXISTS index_session_tables_documentId ON session_tables(documentId)",
        "CREATE INDEX IF NOT EXISTS index_session_table_columns_tableId ON session_table_columns(tableId)",
        "CREATE INDEX IF NOT EXISTS index_session_table_rows_tableId ON session_table_rows(tableId)",
        "CREATE INDEX IF NOT EXISTS index_tool_call_receipts_sessionId ON tool_call_receipts(sessionId)",
        "CREATE INDEX IF NOT EXISTS index_tool_call_receipts_toolName ON tool_call_receipts(toolName)"
    )
}

object MigrationIds {
    fun providerConnectionId(legacyProfileId: String): String = "connection-$legacyProfileId"

    fun modelBindingId(legacyProfileId: String): String = legacyProfileId
}
