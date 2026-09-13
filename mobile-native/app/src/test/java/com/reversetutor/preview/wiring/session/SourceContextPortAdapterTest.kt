package com.reversetutor.preview.wiring.session

import com.reversetutor.core.data.local.dao.SourceChunkEmbeddingRow
import com.reversetutor.core.data.local.dao.SourceDao
import com.reversetutor.core.data.local.entity.SourceChunkEntity
import com.reversetutor.core.data.local.entity.SourceEntity
import com.reversetutor.core.data.sources.SourceEmbeddingCodec
import com.reversetutor.core.data.sources.SourceRepository
import com.reversetutor.core.domain.ConversationContextContract
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * NEWMP-V1-002 plan Task 1 · source revision and hot-update projection.
 *
 * Contracts pinned here:
 *  - reprocessing the same source yields a different `sourceRevision`;
 *  - the next context read uses the new revision, while an already-captured
 *    evidence snapshot keeps the old revision and old excerpt;
 *  - evidence ids embed the revision (`source:<id>:<rev>`);
 *  - sources of another space are never visible.
 */
class SourceContextPortAdapterTest {

    private class FakeSourceDao : SourceDao {
        val sources = linkedMapOf<String, SourceEntity>()
        val chunks = linkedMapOf<String, MutableList<SourceChunkEntity>>()

        override suspend fun insertSource(source: SourceEntity) {
            sources[source.id] = source
        }

        override suspend fun insertChunk(chunk: SourceChunkEntity) {
            chunks.getOrPut(chunk.sourceId) { mutableListOf() }.add(chunk)
        }

        override suspend fun getSourceById(id: String): SourceEntity? = sources[id]

        override suspend fun listSourcesBySpace(spaceId: String): List<SourceEntity> =
            sources.values.filter { it.spaceId == spaceId }

        override suspend fun listChunksForSource(sourceId: String): List<SourceChunkEntity> =
            chunks[sourceId].orEmpty().sortedBy { it.chunkIndex }

        override suspend fun deleteChunksForSource(sourceId: String): Int {
            val removed = chunks[sourceId].orEmpty().size
            chunks[sourceId] = mutableListOf()
            return removed
        }

        override suspend fun updateChunkEmbedding(chunkId: String, embedding: ByteArray) {
            chunks.values.forEach { list ->
                val index = list.indexOfFirst { it.id == chunkId }
                if (index >= 0) list[index] = list[index].copy(embedding = embedding)
            }
        }

        override suspend fun listChunkEmbeddingRows(spaceId: String): List<SourceChunkEmbeddingRow> =
            chunks.values.flatten()
                .filter { it.spaceId == spaceId }
                .mapNotNull { chunk -> chunk.embedding?.let { SourceChunkEmbeddingRow(chunk.id, it) } }
    }

    private fun sourceEntity(id: String, spaceId: String, createdAt: Long, title: String = "单调性讲义") =
        SourceEntity(
            id = id,
            spaceId = spaceId,
            title = title,
            type = "Text",
            parserStatus = "FullyLocal",
            createdAtEpochMillis = createdAt,
            extractedText = "正文 v@$createdAt"
        )

    private fun chunkOf(sourceId: String, spaceId: String, text: String) =
        SourceChunkEntity(
            id = "$sourceId-chunk-0",
            spaceId = spaceId,
            sourceId = sourceId,
            chunkIndex = 0,
            text = text
        )

    private fun chunkAt(
        sourceId: String,
        spaceId: String,
        chunkIndex: Int,
        text: String,
        embedding: ByteArray? = null
    ) = SourceChunkEntity(
        id = "$sourceId-chunk-$chunkIndex",
        spaceId = spaceId,
        sourceId = sourceId,
        chunkIndex = chunkIndex,
        text = text,
        embedding = embedding
    )

    // 1+2. 重新处理同一 sourceId → 新 revision；下一回合读取新版本
    @Test
    fun reprocessedSourceYieldsNewRevisionForNextTurn() = runBlocking {
        val dao = FakeSourceDao()
        val repo = SourceRepository(dao)
        val adapter = SourceContextPortAdapter(repo)
        dao.insertSource(sourceEntity("src-1", "space-a", createdAt = 1000L))
        dao.insertChunk(chunkOf("src-1", "space-a", "旧版正文"))

        val first = adapter.listSourceEvidence("space-a", "sess-1", 5).single()
        assertTrue("版本标识不得为空", first.sourceRevision.isNotBlank())
        assertTrue("版本必须由 sourceId + createdAt 构成", first.sourceRevision.contains("src-1"))

        // 重新处理：同 id，新 createdAt、新正文
        dao.insertSource(sourceEntity("src-1", "space-a", createdAt = 2000L))
        dao.deleteChunksForSource("src-1")
        dao.insertChunk(chunkOf("src-1", "space-a", "新版正文"))

        val second = adapter.listSourceEvidence("space-a", "sess-1", 5).single()
        assertNotEquals(first.sourceRevision, second.sourceRevision)
        assertEquals("新版正文", second.excerpt)
        assertTrue(second.sourceRevision.contains("2000"))
        // 旧快照对象不漂移（值语义）
        assertEquals("旧版正文", first.excerpt)
    }

    // 3. 证据 ID 必须包含来源版本
    @Test
    fun evidenceIdsEmbedTheSourceRevision() = runBlocking {
        val dao = FakeSourceDao()
        val repo = SourceRepository(dao)
        dao.insertSource(sourceEntity("src-9", "space-a", createdAt = 123L))
        dao.insertChunk(chunkOf("src-9", "space-a", "正文"))
        val contract = SourceContextPortAdapter(repo)
            .listSourceEvidence("space-a", "sess-1", 5)
            .single()

        val evidence = ConversationContextContract(
            spaceId = "space-a",
            sessionId = "sess-1",
            prerequisiteGaps = emptyList(),
            relatedMemory = emptyList(),
            sourceEvidence = listOf(contract),
            historicalErrors = emptyList(),
            pendingReviewKnowledgePoints = emptyList(),
            recentMessages = emptyList(),
            warnings = emptyList()
        ).toLlmContextEvidence()

        val sourceEvidence = evidence.single { it.kind == "Source" }
        assertEquals("source:src-9:${contract.sourceRevision}", sourceEvidence.id)
        assertEquals("src-9", sourceEvidence.sourceId)
    }

    // 4. 空间隔离：其他空间的来源不可见
    @Test
    fun sourcesOfAnotherSpaceAreNeverVisible() = runBlocking {
        val dao = FakeSourceDao()
        val repo = SourceRepository(dao)
        dao.insertSource(sourceEntity("src-a", "space-a", createdAt = 1L))
        dao.insertSource(sourceEntity("src-b", "space-b", createdAt = 1L))
        dao.insertChunk(chunkOf("src-a", "space-a", "A空间正文"))
        dao.insertChunk(chunkOf("src-b", "space-b", "B空间正文"))

        val visible = SourceContextPortAdapter(repo).listSourceEvidence("space-a", "sess-1", 5)
        assertEquals(listOf("src-a"), visible.map { it.id })
        assertTrue(visible.none { it.excerpt.contains("B空间") })
    }

    // NEWMP-V1-024 · 5. 向量检索优先：每份资料取最相关片段
    @Test
    fun vectorRankingPicksTheMostRelevantChunkPerSource() = runBlocking {
        val dao = FakeSourceDao()
        val repo = SourceRepository(dao)
        val adapter = SourceContextPortAdapter(
            sourceRepository = repo,
            embedQuery = { floatArrayOf(1f, 0f) }
        )
        dao.insertSource(sourceEntity("src-old", "space-a", createdAt = 100L))
        dao.insertChunk(
            chunkAt("src-old", "space-a", 0, "旧资料背景内容", embedding = SourceEmbeddingCodec.encode(floatArrayOf(0.6f, 0.8f)))
        )
        dao.insertSource(sourceEntity("src-new", "space-a", createdAt = 200L, title = "导数讲义"))
        dao.insertChunk(
            chunkAt("src-new", "space-a", 0, "无关前言", embedding = SourceEmbeddingCodec.encode(floatArrayOf(0f, 1f)))
        )
        dao.insertChunk(
            chunkAt("src-new", "space-a", 1, "导数的几何意义与切线斜率", embedding = SourceEmbeddingCodec.encode(floatArrayOf(0.9f, 0.1f)))
        )

        val evidence = adapter.listSourceEvidence("space-a", "sess-1", 5, queryText = "什么是导数的几何意义")
        assertEquals(listOf("src-new", "src-old"), evidence.map { it.id })
        assertEquals("导数的几何意义与切线斜率", evidence.first().excerpt)
        assertTrue(evidence.first().relevanceScore > evidence.last().relevanceScore)
    }

    // NEWMP-V1-024 · 6. 无向量可用 → 关键词兜底
    @Test
    fun missingEmbeddingsFallBackToKeywordRanking() = runBlocking {
        val dao = FakeSourceDao()
        val repo = SourceRepository(dao)
        var embedCalls = 0
        val adapter = SourceContextPortAdapter(
            sourceRepository = repo,
            embedQuery = {
                embedCalls += 1
                null
            }
        )
        dao.insertSource(sourceEntity("src-miss", "space-a", createdAt = 100L))
        dao.insertChunk(chunkOf("src-miss", "space-a", "完全无关的内容"))
        dao.insertSource(sourceEntity("src-hit", "space-a", createdAt = 50L))
        dao.insertChunk(chunkOf("src-hit", "space-a", "函数的单调性判定方法"))

        val evidence = adapter.listSourceEvidence("space-a", "sess-1", 5, queryText = "单调性 怎么 判定")
        assertEquals(listOf("src-hit"), evidence.map { it.id })
        assertEquals(0, embedCalls)
    }

    // NEWMP-V1-024 · 7. 空查询 → 维持最新优先的旧行为
    @Test
    fun blankQueryKeepsLegacyNewestFirstOrder() = runBlocking {
        val dao = FakeSourceDao()
        val repo = SourceRepository(dao)
        val adapter = SourceContextPortAdapter(repo)
        dao.insertSource(sourceEntity("src-1", "space-a", createdAt = 100L))
        dao.insertChunk(chunkOf("src-1", "space-a", "第一份"))
        dao.insertSource(sourceEntity("src-2", "space-a", createdAt = 200L))
        dao.insertChunk(chunkOf("src-2", "space-a", "第二份"))

        val evidence = adapter.listSourceEvidence("space-a", "sess-1", 5, queryText = "   ")
        assertEquals(listOf("src-2", "src-1"), evidence.map { it.id })
        assertTrue(evidence.all { it.relevanceScore == 0f })
    }
}
