package com.reversetutor.preview.wiring.session

import com.reversetutor.core.data.background.BackgroundGenerationInput
import com.reversetutor.core.data.background.BackgroundGenerationJob
import com.reversetutor.core.model.BackgroundJobStatus
import com.reversetutor.core.domain.ConversationContextContract
import com.reversetutor.core.domain.ContextMessage
import com.reversetutor.core.model.MessageAttachment
import com.reversetutor.feature.chat.BackgroundTurnPreparationRequest
import com.reversetutor.feature.chat.BackgroundTurnPreparationResult
import com.reversetutor.feature.chat.NewSessionConfiguration
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BackgroundTurnPreparationCoordinatorTest {

    private val queuedInputs = mutableListOf<BackgroundGenerationInput>()
    private var directGenerationCalls = 0

    private val coordinator = BackgroundTurnPreparationCoordinator(
        isSessionDeleted = { false },
        assembleContext = { _, _, _ -> ConversationContextContract.empty("space-1", "session-1") },
        enqueueJob = { input, now ->
            queuedInputs.add(input)
            BackgroundGenerationJob(
                id = "job-\${queuedInputs.size}",
                spaceId = input.spaceId,
                sessionId = input.sessionId,
                userMessageId = input.userMessageId,
                userText = input.userText,
                token = input.token,
                modelBindingId = null,
                status = BackgroundJobStatus.Queued,
                createdAtEpochMillis = now,
                startedAtEpochMillis = null,
                completedAtEpochMillis = null,
                errorMessage = null,
                capabilities = null,
                quoteExcerpt = null,
                imageAttachments = input.imageAttachments,
                contextEvidence = input.contextEvidence,
                sessionPolicy = input.sessionPolicy
            )
        },
        nowEpochMillis = { 1000L }
    )

    private val deletedCoordinator = BackgroundTurnPreparationCoordinator(
        isSessionDeleted = { true },
        assembleContext = { _, _, _ -> ConversationContextContract.empty("space-1", "session-1") },
        enqueueJob = { input, _ ->
            queuedInputs.add(input)
            error("should not enqueue")
        },
        nowEpochMillis = { 1000L }
    )

    @Test
    fun prepared_generation_contains_only_the_window_visible_message_ids() = runBlocking {
        queuedInputs.clear()
        val hidden = ContextMessage("root-after-child-1", "user", "root-after-child-1", 30L)
        val visibleContext = ConversationContextContract(
            spaceId = "space-1",
            sessionId = "session-1",
            prerequisiteGaps = emptyList(),
            relatedMemory = emptyList(),
            sourceEvidence = emptyList(),
            historicalErrors = emptyList(),
            pendingReviewKnowledgePoints = emptyList(),
            recentMessages = listOf(
                ContextMessage("root-before", "user", "root-before", 10L),
                ContextMessage("child-2-local", "user", "child-2-local", 60L)
            ),
            warnings = emptyList()
        )
        val topologyAwareCoordinator = BackgroundTurnPreparationCoordinator(
            isSessionDeleted = { false },
            assembleContext = { _, _, _ -> visibleContext },
            enqueueJob = { input, now ->
                queuedInputs.add(input)
                BackgroundGenerationJob(
                    id = "job-visible",
                    spaceId = input.spaceId,
                    sessionId = input.sessionId,
                    userMessageId = input.userMessageId,
                    userText = input.userText,
                    token = input.token,
                    modelBindingId = null,
                    status = BackgroundJobStatus.Queued,
                    createdAtEpochMillis = now,
                    startedAtEpochMillis = null,
                    completedAtEpochMillis = null,
                    errorMessage = null,
                    capabilities = null,
                    quoteExcerpt = null,
                    imageAttachments = input.imageAttachments,
                    contextEvidence = input.contextEvidence,
                    sessionPolicy = input.sessionPolicy
                )
            },
            nowEpochMillis = { 1000L }
        )

        val result = topologyAwareCoordinator.prepareAndEnqueue(request("explain"))
        assertTrue(result is BackgroundTurnPreparationResult.Queued)

        val visibleIds = queuedInputs.single().contextEvidence
            .filter { it.kind == "Message" }
            .mapNotNull { it.sourceMessageId }
        assertEquals(listOf("root-before", "child-2-local"), visibleIds)
        assertFalse(visibleIds.contains(hidden.messageId))
    }

    private fun request(text: String) = BackgroundTurnPreparationRequest(
        spaceId = "space-1",
        sessionId = "session-1",
        userMessageId = "msg-1",
        userText = text,
        token = "token-1",
        quoteExcerpt = null,
        imageAttachments = emptyList<MessageAttachment>(),
        sessionSnapshot = null
    )

    @Test
    fun preparation_enqueues_once_without_direct_generation() = runBlocking {
        val result = coordinator.prepareAndEnqueue(request("\u89e3\u91ca\u4e00\u4e0b"))
        assertTrue(result is BackgroundTurnPreparationResult.Queued)
        assertEquals(1, queuedInputs.size)
        assertEquals(0, directGenerationCalls)
    }

    @Test
    fun image_only_turn_is_queued_not_rejected_as_blank() = runBlocking {
        val result = coordinator.prepareAndEnqueue(
            request(" ").copy(
                imageAttachments = listOf(
                    MessageAttachment(
                        id = "attachment-1",
                        spaceId = "space-1",
                        messageId = "msg-1",
                        name = "camera-test.jpg",
                        mimeType = "image/jpeg",
                        uri = "file:///data/local/tmp/chat-camera/camera-test.jpg"
                    )
                )
            )
        )
        assertTrue(result is BackgroundTurnPreparationResult.Queued)
        assertEquals(1, queuedInputs.size)
        assertEquals(1, queuedInputs.single().imageAttachments.size)
    }

    @Test
    fun blank_or_deleted_never_enqueues() = runBlocking {
        assertEquals(
            BackgroundTurnPreparationResult.BlankInput,
            coordinator.prepareAndEnqueue(request(" "))
        )
        assertEquals(
            BackgroundTurnPreparationResult.SessionUnavailable,
            deletedCoordinator.prepareAndEnqueue(request("\u95ee\u9898"))
        )
        assertTrue(queuedInputs.isEmpty())
    }

    @Test
    fun preparation_carries_bounded_template_context_into_generation_evidence() = runBlocking {
        queuedInputs.clear()
        val result = coordinator.prepareAndEnqueue(
            request("解释单调性").copy(
                sessionSnapshot = NewSessionConfiguration(
                    learnerRole = "谨慎的追问型学生",
                    learnerProfile = "容易漏步骤，喜欢反例",
                    goal = "掌握函数单调性",
                    plan = "先诊断，再例题",
                    dialogueStrategy = "每次追问一个为什么",
                    speakingTone = "自然"
                )
            )
        )

        assertTrue(result is BackgroundTurnPreparationResult.Queued)
        val templateEvidence = queuedInputs.single().contextEvidence.filter { it.kind == "Template" }
        assertEquals(1, templateEvidence.size)
        val body = templateEvidence.single().body
        assertTrue(body.contains("谨慎的追问型学生"))
        assertTrue(body.contains("掌握函数单调性"))
        assertTrue(body.contains("每次追问一个为什么"))
    }

    // Task 5: a failing signal read must never block a legitimate user turn.
    @Test
    fun signal_reader_failure_still_queues_with_empty_signals() = runBlocking {
        queuedInputs.clear()
        val flaky = BackgroundTurnPreparationCoordinator(
            isSessionDeleted = { false },
            assembleContext = { _, _, _ -> ConversationContextContract.empty("space-1", "session-1") },
            enqueueJob = { input, now ->
                queuedInputs.add(input)
                BackgroundGenerationJob(
                    id = "job-sig", spaceId = input.spaceId, sessionId = input.sessionId,
                    userMessageId = input.userMessageId, userText = input.userText,
                    token = input.token, modelBindingId = null,
                    status = BackgroundJobStatus.Queued, createdAtEpochMillis = now,
                    startedAtEpochMillis = null, completedAtEpochMillis = null,
                    errorMessage = null, capabilities = null, quoteExcerpt = null,
                    imageAttachments = input.imageAttachments,
                    contextEvidence = input.contextEvidence, sessionPolicy = input.sessionPolicy
                )
            },
            nowEpochMillis = { 1000L },
            loadRecentTurnSignals = { _, _ -> error("store unavailable") }
        )
        val result = flaky.prepareAndEnqueue(request("给我一点提示"))
        assertTrue(result is BackgroundTurnPreparationResult.Queued)
        // empty signals on failure: no forced hint-streak switch; the selector falls back
        // to its normal scoring path (unknown concept -> Diagnose first)
        assertEquals(com.reversetutor.core.domain.TeachingAction.Diagnose, queuedInputs.single().turnPlan!!.actionType)
    }

    // Task 5: consecutive-hint signals recovered from completed plans switch strategy.
    @Test
    fun consecutive_hint_signals_switch_the_current_plan_away_from_hint() = runBlocking {
        queuedInputs.clear()
        val withSignals = BackgroundTurnPreparationCoordinator(
            isSessionDeleted = { false },
            assembleContext = { _, _, _ -> ConversationContextContract.empty("space-1", "session-1") },
            enqueueJob = { input, now ->
                queuedInputs.add(input)
                BackgroundGenerationJob(
                    id = "job-hint", spaceId = input.spaceId, sessionId = input.sessionId,
                    userMessageId = input.userMessageId, userText = input.userText,
                    token = input.token, modelBindingId = null,
                    status = BackgroundJobStatus.Queued, createdAtEpochMillis = now,
                    startedAtEpochMillis = null, completedAtEpochMillis = null,
                    errorMessage = null, capabilities = null, quoteExcerpt = null,
                    imageAttachments = input.imageAttachments,
                    contextEvidence = input.contextEvidence, sessionPolicy = input.sessionPolicy
                )
            },
            nowEpochMillis = { 1000L },
            loadRecentTurnSignals = { _, _ ->
                com.reversetutor.core.domain.RecentTurnSignals(
                    lastAction = com.reversetutor.core.domain.TeachingAction.Hint,
                    askedForHintCount = 2
                )
            }
        )
        val result = withSignals.prepareAndEnqueue(request("给我一点提示"))
        assertTrue(result is BackgroundTurnPreparationResult.Queued)
        val action = queuedInputs.single().turnPlan!!.actionType
        assertTrue(
            "hint streak must switch strategy, got $action",
            action == com.reversetutor.core.domain.TeachingAction.SocraticQuestion ||
                action == com.reversetutor.core.domain.TeachingAction.WorkedExample
        )
    }

    // NEWMP-V1-006 Task 3: a turn already queued must keep the source
    // revision it snapshotted at enqueue time; only turns enqueued after an
    // import bind the new revision.
    @Test
    fun queued_turns_keep_snapshotted_source_revision_while_later_turns_bind_new_one() = runBlocking {
        queuedInputs.clear()
        var sourceRevision = "rev-src-1-100"
        val revisionAware = BackgroundTurnPreparationCoordinator(
            isSessionDeleted = { false },
            assembleContext = { _, _, _ ->
                ConversationContextContract(
                    spaceId = "space-1",
                    sessionId = "session-1",
                    prerequisiteGaps = emptyList(),
                    relatedMemory = emptyList(),
                    sourceEvidence = listOf(
                        com.reversetutor.core.domain.SourceReferenceContract(
                            id = "src-1",
                            title = "讲义",
                            excerpt = "片段",
                            sourceType = "Text",
                            relevanceScore = 0f,
                            sourceRevision = sourceRevision
                        )
                    ),
                    historicalErrors = emptyList(),
                    pendingReviewKnowledgePoints = emptyList(),
                    recentMessages = emptyList(),
                    warnings = emptyList()
                )
            },
            enqueueJob = { input, now ->
                queuedInputs.add(input)
                BackgroundGenerationJob(
                    id = "job-rev-${queuedInputs.size}",
                    spaceId = input.spaceId,
                    sessionId = input.sessionId,
                    userMessageId = input.userMessageId,
                    userText = input.userText,
                    token = input.token,
                    modelBindingId = null,
                    status = BackgroundJobStatus.Queued,
                    createdAtEpochMillis = now,
                    startedAtEpochMillis = null,
                    completedAtEpochMillis = null,
                    errorMessage = null,
                    capabilities = null,
                    quoteExcerpt = null,
                    imageAttachments = input.imageAttachments,
                    contextEvidence = input.contextEvidence,
                    sessionPolicy = input.sessionPolicy
                )
            },
            nowEpochMillis = { 1000L }
        )

        assertTrue(revisionAware.prepareAndEnqueue(request("第一问")) is BackgroundTurnPreparationResult.Queued)
        val firstEvidence = queuedInputs[0].contextEvidence

        // 模拟聊天内导入/重解析：同一份资料产生新 revision
        sourceRevision = "rev-src-1-900"
        assertTrue(
            revisionAware.prepareAndEnqueue(request("第二问").copy(userMessageId = "msg-2")) is
                BackgroundTurnPreparationResult.Queued
        )
        val secondEvidence = queuedInputs[1].contextEvidence

        // 已排队回合锁定入队时快照的旧 revision
        assertTrue(firstEvidence.any { it.id == "source:src-1:rev-src-1-100" })
        assertTrue(firstEvidence.none { it.id.contains("rev-src-1-900") })
        // 后续回合绑定导入后的新 revision
        assertTrue(secondEvidence.any { it.id == "source:src-1:rev-src-1-900" })
        assertTrue(secondEvidence.none { it.id == "source:src-1:rev-src-1-100" })
    }
}
