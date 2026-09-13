package com.reversetutor.core.data

import com.reversetutor.core.data.local.DatabaseSchema
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
import com.reversetutor.core.data.local.entity.WorldTreeDraftEntity
import com.reversetutor.core.data.local.entity.WorldTreeSectionEntity
import com.reversetutor.core.data.local.entity.WorldTreeSourceCrossRef
import com.reversetutor.core.data.local.entity.toDomain
import com.reversetutor.core.data.local.entity.toEntity
import com.reversetutor.core.model.Space
import com.reversetutor.core.model.SpaceKind
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SchemaPolicyTest {
    @Test
    fun databaseSchemaExportsVersionThirteenWithCompleteMigrationChain() {
        assertEquals(13, DatabaseSchema.version)
        assertTrue(DatabaseSchema.exportSchema)
        assertEquals(12, DatabaseSchema.migrations.size)
        assertEquals(listOf(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12), DatabaseSchema.migrations.map { it.startVersion })
        assertEquals(listOf(2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13), DatabaseSchema.migrations.map { it.endVersion })
    }

    @Test
    fun userOwnedEntitiesCarrySpaceId() {
        val entityTypes = listOf(
            SessionEntity::class.java,
            MessageEntity::class.java,
            MessageAttachmentEntity::class.java,
            MessageQuoteEntity::class.java,
            LlmProfileEntity::class.java,
            SessionSettingsEntity::class.java,
            AnchorEntity::class.java,
            NoteEntity::class.java,
            ErrorLogEntity::class.java,
            MemoryItemEntity::class.java,
            GraphNodeEntity::class.java,
            GraphEdgeEntity::class.java,
            SourceEntity::class.java,
            SourceChunkEntity::class.java,
            BackgroundJobEntity::class.java,
            ImportBatchEntity::class.java,
            ExportRecordEntity::class.java,
            WorldTreeDraftEntity::class.java
        )

        entityTypes.forEach { entityType ->
            assertTrue(
                "${entityType.simpleName} must expose spaceId",
                entityType.declaredFields.any { it.name == "spaceId" }
            )
        }
    }

    @Test
    fun backgroundJobPolicySnapshotRemainsOptionalForLegacyRows() {
        val policyPayload = BackgroundJobEntity::class.java.declaredFields
            .firstOrNull { it.name == "sessionPolicyPayload" }
        assertTrue(policyPayload != null)
        assertTrue(policyPayload?.type == String::class.java)
    }

    @Test
    fun worldTreeChildrenDeriveSpaceOwnershipFromDraft() {
        assertFalse(
            WorldTreeSectionEntity::class.java.declaredFields.any { it.name == "spaceId" }
        )
        assertFalse(
            WorldTreeSourceCrossRef::class.java.declaredFields.any { it.name == "spaceId" }
        )
    }

    @Test
    fun spaceEntityRoundTripsToDomainModel() {
        val domain = Space(
            id = "space-1",
            name = "Imported backup",
            kind = SpaceKind.Imported,
            createdAtEpochMillis = 100L,
            updatedAtEpochMillis = 200L,
            sourceImportId = "import-1"
        )

        val entity = domain.toEntity()
        val roundTrip = entity.toDomain()

        assertEquals(
            SpaceEntity(
                id = "space-1",
                name = "Imported backup",
                kind = "Imported",
                createdAtEpochMillis = 100L,
                updatedAtEpochMillis = 200L,
                sourceImportId = "import-1"
            ),
            entity
        )
        assertEquals(domain, roundTrip)
    }
}
