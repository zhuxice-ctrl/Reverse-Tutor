package com.reversetutor.core.data

import androidx.room.testing.MigrationTestHelper
import androidx.sqlite.db.framework.FrameworkSQLiteOpenHelperFactory
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.reversetutor.core.data.local.DatabaseSchema
import com.reversetutor.core.data.local.ReverseTutorDatabase
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * NEWMP-V1-024: the 12 -> 13 migration adds the nullable `embedding` column
 * to `source_chunks` without losing pre-existing source or chunk rows; old
 * chunks keep reading with a null embedding (keyword-retrieval compatible).
 */
@RunWith(AndroidJUnit4::class)
class ReverseTutorDatabaseMigration12To13Test {
    @get:Rule
    val helper = MigrationTestHelper(
        InstrumentationRegistry.getInstrumentation(),
        ReverseTutorDatabase::class.java.canonicalName,
        FrameworkSQLiteOpenHelperFactory()
    )

    @Test
    fun migratesTwelveToThirteenWithoutLosingExistingRows() {
        helper.createDatabase(TestDatabase, 12).apply {
            execSQL(
                "INSERT INTO spaces (id, name, kind, createdAtEpochMillis, updatedAtEpochMillis) " +
                    "VALUES ('space-1', 'Space', 'Personal', 1, 1)"
            )
            execSQL(
                "INSERT INTO sources (id, spaceId, title, type, parserStatus, createdAtEpochMillis) " +
                    "VALUES ('src-1', 'space-1', 'lecture', 'Text', 'FullyLocal', 100)"
            )
            execSQL(
                "INSERT INTO source_chunks (id, spaceId, sourceId, chunkIndex, text, tokenEstimate) " +
                    "VALUES ('chunk-1', 'space-1', 'src-1', 0, 'existing text', NULL)"
            )
            execSQL(
                "INSERT INTO source_chunks (id, spaceId, sourceId, chunkIndex, text, tokenEstimate) " +
                    "VALUES ('chunk-2', 'space-1', 'src-1', 1, 'second text', NULL)"
            )
            close()
        }

        val database = helper.runMigrationsAndValidate(
            TestDatabase, 13, true, DatabaseSchema.migration12To13
        )

        // existing chunk rows survive
        database.query("SELECT COUNT(*) FROM source_chunks WHERE sourceId = 'src-1'").use {
            assertTrue(it.moveToFirst())
            assertEquals(2, it.getInt(0))
        }

        // new nullable column exists and old chunks read with NULL embedding
        database.query("PRAGMA table_info(source_chunks)").use { cursor ->
            val names = mutableListOf<String>()
            while (cursor.moveToNext()) names += cursor.getString(cursor.getColumnIndexOrThrow("name"))
            assertTrue("embedding column must exist", "embedding" in names)
        }
        database.query("SELECT embedding FROM source_chunks WHERE id = 'chunk-1'").use {
            assertTrue(it.moveToFirst())
            assertTrue("legacy chunk must have a null embedding", it.isNull(0))
        }
        database.close()
    }

    private companion object {
        const val TestDatabase = "reverse-tutor-migration-12-to-13"
    }
}
