package com.reversetutor.preview.wiring

import android.content.Context
import com.reversetutor.core.data.DataModule
import com.reversetutor.core.data.agent.AssistantReplyArtifactRepository
import com.reversetutor.core.data.agent.RoomAssistantReplyArtifactStore
import com.reversetutor.core.data.background.BackgroundGenerationJob
import com.reversetutor.core.data.background.BackgroundGenerationRepository
import com.reversetutor.core.data.graph.GraphRepository
import com.reversetutor.core.data.heartbeat.WindowHeartbeatRepository
import com.reversetutor.core.data.learning.LearningLedgerRepository
import com.reversetutor.core.data.learning.LearningRepositoryImpl
import com.reversetutor.core.data.llm.ChatGenerationRepository
import com.reversetutor.core.llm.FakeLlmGenerationRuntime
import com.reversetutor.core.data.llm.LlmProfileRepository
import com.reversetutor.core.data.memory.MemoryRepository
import com.reversetutor.core.data.message.MessageRepository
import com.reversetutor.core.data.migration.NativeExportRepository
import com.reversetutor.core.data.migration.NativeImportRepository
import com.reversetutor.core.data.model.ModelConnectionRepositoryImpl
import com.reversetutor.core.data.online.OnlineActivityRepository
import com.reversetutor.core.data.online.ContractMockOnlineApi
import com.reversetutor.core.data.online.OnlineContentRepository
import com.reversetutor.core.data.online.OnlineInsightRepository
import com.reversetutor.core.data.online.OnlineSyncTransport
import com.reversetutor.core.data.online.OnlineUpdateRepository
import com.reversetutor.core.data.preferences.AppPreferencesRepository
import com.reversetutor.core.data.run.ConversationRunRepositoryImpl
import com.reversetutor.core.data.search.RoomGlobalSearchRepository
import com.reversetutor.core.data.session.SessionDeletionRepository
import com.reversetutor.core.data.session.SessionRepository
import com.reversetutor.core.data.sync.RoomSyncRepository
import com.reversetutor.core.data.sources.SourceRepository
import com.reversetutor.core.data.wipe.LocalDataWipeRepository
import com.reversetutor.core.data.window.WindowTopologyRepository
import com.reversetutor.core.domain.ConversationRunCoordinator
import com.reversetutor.core.domain.SyncCoordinator
import com.reversetutor.core.domain.WindowKind
import com.reversetutor.core.remote.AndroidOnlineAuthStateStore
import com.reversetutor.core.remote.HttpOnlineApi
import com.reversetutor.core.remote.OnlineAuthSessionManager
import com.reversetutor.core.remote.OnlineAuthTokenProvider
import com.reversetutor.core.remote.UrlConnectionOnlineHttpTransport
import com.reversetutor.feature.chat.BackgroundTurnPreparationPort
import com.reversetutor.feature.chat.HeartbeatTurnDispatchPort
import com.reversetutor.feature.chat.SessionRichReplyPort
import com.reversetutor.preview.wiring.session.DefaultHeartbeatTurnDispatchPort
import com.reversetutor.feature.chat.ChatRunsPortViewModelFactory
import com.reversetutor.feature.chat.ChatRunsViewModelFactory
import com.reversetutor.feature.chat.HomePortViewModelFactory
import com.reversetutor.feature.chat.HomeViewModelFactory
import com.reversetutor.feature.chat.LearningOverviewViewModelFactory
import com.reversetutor.feature.chat.LearningOverviewPortViewModelFactory
import com.reversetutor.feature.chat.NewSessionCreatePort
import com.reversetutor.feature.chat.NewSessionPersistence
import com.reversetutor.feature.chat.SessionHomePort
import com.reversetutor.feature.chat.TagLibraryPersistence
import com.reversetutor.feature.chat.WindowVisibleTimelinePort
import com.reversetutor.feature.chat.WindowBranchPort
import com.reversetutor.feature.chat.toSessionListItem
import com.reversetutor.feature.memory.WeeklyDashboardPortViewModelFactory
import com.reversetutor.feature.memory.WeeklyTokenUsageEntry
import com.reversetutor.feature.memory.WeeklyDashboardViewModelFactory
import com.reversetutor.feature.settings.ModelConnectionsPortViewModelFactory
import com.reversetutor.feature.settings.ModelConnectionsViewModelFactory
import com.reversetutor.preview.BuildConfig
import com.reversetutor.preview.shell.ChallengeRuntimeCoordinator
import com.reversetutor.preview.shell.DefaultWorkspaceViewModelFactory
import com.reversetutor.preview.shell.WorkspaceViewModelFactory
import com.reversetutor.preview.wiring.session.BackgroundTurnPreparationCoordinator
import com.reversetutor.preview.wiring.session.RecentTurnSignalsReader
import com.reversetutor.preview.wiring.session.SessionConversationAssembly
import com.reversetutor.preview.wiring.session.SharedPreferencesSessionSummaryStore
import com.reversetutor.preview.wiring.session.TopologyAwareMessageContextPort
import com.reversetutor.preview.wiring.session.WindowVisibleHistoryReader
import com.reversetutor.preview.wiring.session.WindowVisibleTimelinePortAdapter
import com.reversetutor.preview.wiring.session.WindowBranchCoordinator
import com.reversetutor.preview.wiring.session.SessionRichReplyPortAdapter

data class HybridFrontendFactories(
    val workspaceViewModelFactory: WorkspaceViewModelFactory,
    val homeViewModelFactory: HomeViewModelFactory,
    val sessionHomePort: SessionHomePort,
    val newSessionCreatePort: NewSessionCreatePort,
    val newSessionPersistence: NewSessionPersistence,
    val tagLibraryPersistence: TagLibraryPersistence,
    val chatRunsViewModelFactory: ChatRunsViewModelFactory,
    val modelConnectionsViewModelFactory: ModelConnectionsViewModelFactory,
    val weeklyDashboardViewModelFactory: WeeklyDashboardViewModelFactory,
    val learningOverviewViewModelFactory: LearningOverviewViewModelFactory
)

enum class HybridLlmRuntimeMode { Fake, Production }

enum class HybridOnlineMode { LocalOnly, ContractMock, Http }

sealed interface HybridOnlineConfiguration {
    val mode: HybridOnlineMode

    data object LocalOnly : HybridOnlineConfiguration {
        override val mode = HybridOnlineMode.LocalOnly
    }

    data object ContractMock : HybridOnlineConfiguration {
        override val mode = HybridOnlineMode.ContractMock
    }

    data class Http(
        val baseUrl: String,
        val authTokenProvider: OnlineAuthTokenProvider? = null
    ) : HybridOnlineConfiguration {
        override val mode = HybridOnlineMode.Http
    }

    companion object {
        fun fromBaseUrl(baseUrl: String): HybridOnlineConfiguration {
            val normalized = baseUrl.trim().trimEnd('/')
            return if (normalized.isEmpty()) LocalOnly else Http(normalized)
        }
    }
}

data class HybridOnlineServices(
    val contentRepository: OnlineContentRepository,
    val activityRepository: OnlineActivityRepository,
    val insightRepository: OnlineInsightRepository,
    val syncCoordinator: SyncCoordinator,
    val updateRepository: OnlineUpdateRepository
)

private data class HybridHttpOnlineRuntime(
    val api: HttpOnlineApi,
    val authSessionManager: OnlineAuthSessionManager?
)

class HybridAppGraph private constructor(
    val appPreferencesRepository: AppPreferencesRepository,
    val sessionRepository: SessionRepository,
    val messageRepository: MessageRepository,
    val llmProfileRepository: LlmProfileRepository,
    val chatGenerationRepository: ChatGenerationRepository,
    val sessionConversationAssembly: SessionConversationAssembly,
    val visibleTimelinePort: WindowVisibleTimelinePort,
    val windowBranchPort: WindowBranchPort,
    val backgroundGenerationRepository: BackgroundGenerationRepository,
    val backgroundTurnPreparationPort: BackgroundTurnPreparationPort,
    val heartbeatTurnDispatchPort: HeartbeatTurnDispatchPort,
    val sessionRichReplyPort: SessionRichReplyPort,
    val sourceRepository: SourceRepository,
    val memoryRepository: MemoryRepository,
    val graphRepository: GraphRepository,
    val learningRepository: LearningRepositoryImpl,
    val conversationRunRepository: ConversationRunRepositoryImpl,
    val modelConnectionRepository: ModelConnectionRepositoryImpl,
    val globalSearchRepository: RoomGlobalSearchRepository,
    val syncRepository: RoomSyncRepository,
    val localDataWipeRepository: LocalDataWipeRepository,
    val nativeImportRepository: NativeImportRepository,
    val nativeExportRepository: NativeExportRepository,
    val online: HybridOnlineServices?,
    val challengeRuntimeCoordinator: ChallengeRuntimeCoordinator,
    val frontend: HybridFrontendFactories
) {
    companion object {
        fun create(
            context: Context,
            onlineConfiguration: HybridOnlineConfiguration = HybridOnlineConfiguration.LocalOnly,
            llmRuntimeMode: HybridLlmRuntimeMode = HybridLlmRuntimeMode.Fake
        ): HybridAppGraph {
            val appContext = context.applicationContext
            val sessionRepository = DataModule.sessionRepository(appContext)
            val messageRepository = DataModule.messageRepository(appContext)
            val sessionDeletionRepository = DataModule.sessionDeletionRepository(appContext)
            val conversationRunRepository = DataModule.conversationRunRepository(appContext)
            val modelConnectionRepository = DataModule.modelConnectionRepository(appContext)
            val learningRepository = DataModule.learningRepository(appContext)
            val syncRepository = DataModule.syncRepository(appContext)
            val runCoordinator = ConversationRunCoordinator(conversationRunRepository)
            val httpRuntime = (onlineConfiguration as? HybridOnlineConfiguration.Http)?.let {
                createHttpOnlineRuntime(appContext, it)
            }
            val onlineApi = when (onlineConfiguration) {
                HybridOnlineConfiguration.LocalOnly -> null
                HybridOnlineConfiguration.ContractMock -> ContractMockOnlineApi()
                is HybridOnlineConfiguration.Http -> requireNotNull(httpRuntime).api
            }
            val onlineServices = onlineApi?.let {
                HybridOnlineServices(
                    contentRepository = OnlineContentRepository(it),
                    activityRepository = OnlineActivityRepository(it),
                    insightRepository = OnlineInsightRepository(it),
                    syncCoordinator = SyncCoordinator(
                        repository = syncRepository,
                        transport = OnlineSyncTransport(it)
                    ),
                    updateRepository = OnlineUpdateRepository(it)
                )
            }
            val challengeRuntimeCoordinator = ChallengeRuntimeCoordinator(
                activityRepository = onlineServices?.activityRepository,
                identityProvider = { httpRuntime?.authSessionManager?.identity() }
            )

            val previewRuntime = FakeLlmGenerationRuntime()
            // NEWMP-V1-018: consult the web-search preference per reply so the
            // settings toggle takes effect without rebuilding the graph.
            val appPreferencesRepository = DataModule.appPreferencesRepository(appContext)
            val webSearchPreference: suspend () -> Boolean =
                appPreferencesRepository::currentWebSearchEnabled
            val chatGenerationRepository = when (llmRuntimeMode) {
                HybridLlmRuntimeMode.Fake ->
                    DataModule.chatGenerationRepository(
                        context = appContext,
                        runtime = previewRuntime,
                        webSearchPreference = webSearchPreference
                    )
                HybridLlmRuntimeMode.Production ->
                    DataModule.chatGenerationRepository(
                        context = appContext,
                        webSearchPreference = webSearchPreference,
                        // NEWMP-V1-024: semantic retrieval embedding runtime.
                        embeddingRuntime = DataModule.productionEmbeddingRuntime(appContext)
                    )
            }
            val backgroundGenerationRepository = when (llmRuntimeMode) {
                HybridLlmRuntimeMode.Fake ->
                    DataModule.backgroundGenerationRepository(appContext, runtime = previewRuntime)
                HybridLlmRuntimeMode.Production ->
                    DataModule.backgroundGenerationRepository(appContext)
            }
            val sourceRepository = DataModule.sourceRepository(appContext)
            val memoryRepository = DataModule.memoryRepository(appContext)
            val graphRepository = DataModule.graphRepository(appContext)
            val database = DataModule.database(appContext)
            val windowTopologyRepository = WindowTopologyRepository(database.windowTopologyDao())
            val windowHeartbeatRepository = WindowHeartbeatRepository(database.windowHeartbeatDao())
            val learningLedgerRepository = LearningLedgerRepository(database.learningLedgerDao())
            val recentTurnSignalsReader = RecentTurnSignalsReader(
                loadCompletedPlans = backgroundGenerationRepository::listCompletedTurnPlans,
                loadLearningFacts = learningLedgerRepository::listLearningFactsForWindow
            )
            val sessionRichReplyPort: SessionRichReplyPort = SessionRichReplyPortAdapter(
                AssistantReplyArtifactRepository(RoomAssistantReplyArtifactStore(database.sessionAgentDao()))
            )
            val newSessionPersistence = SharedPreferencesNewSessionPersistence(appContext)
            val visibleHistoryReader = WindowVisibleHistoryReader(
                readWindow = windowTopologyRepository::getWindow,
                readSnapshot = windowTopologyRepository::getSnapshot,
                listMessageRecords = messageRepository::listMessageRecords
            )
            val sessionSummaryStore = SharedPreferencesSessionSummaryStore(appContext)
            val sessionConversationAssembly = SessionConversationAssembly(
                chatGenerationRepository = chatGenerationRepository,
                messageRepository = messageRepository,
                conversationRunRepository = conversationRunRepository,
                sessionRepository = sessionRepository,
                memoryRepository = memoryRepository,
                graphRepository = graphRepository,
                sourceRepository = sourceRepository,
                learningRepository = learningRepository,
                learningLedgerRepository = learningLedgerRepository,
                messageContextPort = TopologyAwareMessageContextPort(visibleHistoryReader),
                sessionSummaryStore = sessionSummaryStore
            )
            val backgroundTurnPreparationPort: BackgroundTurnPreparationPort =
                BackgroundTurnPreparationCoordinator(
                    isSessionDeleted = { sessionId ->
                        conversationRunRepository.isSessionDeleted(sessionId)
                    },
                    assembleContext = { spaceId, sessionId, userText ->
                        sessionConversationAssembly.assembleContext(spaceId, sessionId, userText)
                    },
                    enqueueJob = { input, now ->
                        backgroundGenerationRepository.enqueueGenerationJob(input, now)
                    },
                    loadRecentTurnSignals = recentTurnSignalsReader::read
                )
            val windowBranchPort: WindowBranchPort = WindowBranchCoordinator(
                sessionExists = { sessionId -> sessionRepository.getSession(sessionId) != null },
                sessionTitle = { sessionId -> sessionRepository.getSession(sessionId)?.title },
                readWindow = windowTopologyRepository::getWindow,
                createTaskRoot = { sessionId, nowEpochMillis ->
                    windowTopologyRepository.createRootWindow(
                        sessionId = sessionId,
                        kind = WindowKind.TASK_ROOT,
                        nowEpochMillis = nowEpochMillis
                    )
                },
                listWindows = windowTopologyRepository::listWindows,
                loadSessionSnapshot = newSessionPersistence::loadSessionSnapshot,
                createSession = { snapshot, sessionId, nowEpochMillis ->
                    sessionRepository.createSession(
                        input = snapshot.toCoreDraft().toCreationInput(),
                        nowEpochMillis = nowEpochMillis,
                        sessionId = sessionId
                    )
                    true
                },
                saveSessionSnapshot = newSessionPersistence::saveSessionSnapshot,
                forkChild = { childId, parentId, revision, nowEpochMillis ->
                    windowTopologyRepository.forkChild(childId, parentId, revision, nowEpochMillis)
                    Unit
                },
                localMessageCount = { sessionId -> messageRepository.listMessageRecords(sessionId).size.toLong() },
                rollbackChildSession = { sessionId ->
                    sessionDeletionRepository.deleteSession(
                        sessionId = sessionId,
                        deletedAtEpochMillis = System.currentTimeMillis(),
                        revision = System.currentTimeMillis(),
                        idempotencyKey = "window-branch-create-rollback-$sessionId"
                    )
                    Unit
                },
                heartbeatFor = windowHeartbeatRepository::heartbeatFor,
                enableChildHeartbeat = windowHeartbeatRepository::enableChildHeartbeat,
                deleteHeartbeat = windowHeartbeatRepository::deleteHeartbeat,
                cancelSessionGenerationJobs = backgroundGenerationRepository::cancelSessionGenerationJobs,
                deleteBranch = { },
                deleteAvailable = false
            )
            return HybridAppGraph(
                appPreferencesRepository = appPreferencesRepository,
                sessionRepository = sessionRepository,
                messageRepository = messageRepository,
                llmProfileRepository = DataModule.llmProfileRepository(appContext),
                chatGenerationRepository = chatGenerationRepository,
                sessionConversationAssembly = sessionConversationAssembly,
                visibleTimelinePort = WindowVisibleTimelinePortAdapter(visibleHistoryReader),
                windowBranchPort = windowBranchPort,
                backgroundGenerationRepository = backgroundGenerationRepository,
                backgroundTurnPreparationPort = backgroundTurnPreparationPort,
                heartbeatTurnDispatchPort = DefaultHeartbeatTurnDispatchPort(backgroundGenerationRepository),
                sessionRichReplyPort = sessionRichReplyPort,
                sourceRepository = sourceRepository,
                memoryRepository = memoryRepository,
                graphRepository = graphRepository,
                learningRepository = learningRepository,
                conversationRunRepository = conversationRunRepository,
                modelConnectionRepository = modelConnectionRepository,
                globalSearchRepository = DataModule.globalSearchRepository(appContext),
                syncRepository = syncRepository,
                localDataWipeRepository = DataModule.localDataWipeRepository(appContext),
                nativeImportRepository = DataModule.nativeImportRepository(appContext),
                nativeExportRepository = DataModule.nativeExportRepository(appContext),
                online = onlineServices,
                challengeRuntimeCoordinator = challengeRuntimeCoordinator,
                frontend = createFrontendFactories(
                    context = appContext,
                    sessionRepository = sessionRepository,
                    messageRepository = messageRepository,
                    sessionDeletionRepository = sessionDeletionRepository,
                    conversationRunRepository = conversationRunRepository,
                    modelConnectionRepository = modelConnectionRepository,
                    learningRepository = learningRepository,
                    runCoordinator = runCoordinator,
                    sessionConversationAssembly = sessionConversationAssembly,
                    newSessionPersistence = newSessionPersistence,
                    findActiveJobForSession = backgroundGenerationRepository::findActiveJobForSession,
                    clearSessionSummary = sessionSummaryStore::clear
                )
            )
        }

        private fun createHttpOnlineRuntime(
            context: Context,
            configuration: HybridOnlineConfiguration.Http
        ): HybridHttpOnlineRuntime {
            val transport = UrlConnectionOnlineHttpTransport()
            val authSessionManager = when (val provider = configuration.authTokenProvider) {
                is OnlineAuthSessionManager -> provider
                null -> OnlineAuthSessionManager(
                    authApi = HttpOnlineApi(
                        baseUrl = configuration.baseUrl,
                        transport = transport
                    ),
                    stateStore = AndroidOnlineAuthStateStore(context.applicationContext),
                    appVersionCode = BuildConfig.VERSION_CODE.toLong()
                )
                else -> null
            }
            return HybridHttpOnlineRuntime(
                api = HttpOnlineApi(
                    baseUrl = configuration.baseUrl,
                    transport = transport,
                    authTokenProvider = requireNotNull(
                        configuration.authTokenProvider ?: authSessionManager
                    )
                ),
                authSessionManager = authSessionManager
            )
        }

        private fun createFrontendFactories(
            context: Context,
            sessionRepository: SessionRepository,
            messageRepository: MessageRepository,
            sessionDeletionRepository: SessionDeletionRepository,
            conversationRunRepository: ConversationRunRepositoryImpl,
            modelConnectionRepository: ModelConnectionRepositoryImpl,
            learningRepository: LearningRepositoryImpl,
            runCoordinator: ConversationRunCoordinator,
            sessionConversationAssembly: SessionConversationAssembly,
            newSessionPersistence: NewSessionPersistence,
            findActiveJobForSession: suspend (String) -> BackgroundGenerationJob?,
            clearSessionSummary: (String) -> Unit
        ): HybridFrontendFactories {
            val homePort = RepositoryHomePortAdapter {
                sessionRepository.listSessions()
            }
            val sessionHomePort = RepositorySessionHomePortAdapter(
                sessionRepository = sessionRepository,
                messageRepository = messageRepository,
                sessionDeletionRepository = sessionDeletionRepository,
                conversationRunRepository = conversationRunRepository,
                persistence = SharedPreferencesSessionHomePersistence(context),
                findActiveJobForSession = findActiveJobForSession,
                loadSessionSnapshot = newSessionPersistence::loadSessionSnapshot,
                clearSessionSummary = clearSessionSummary
            )
            val tagLibraryPersistence = SharedPreferencesTagLibraryPersistence(context)
            val newSessionCreatePort = RepositoryNewSessionCreatePortAdapter(
                createSession = { input, nowEpochMillis, sessionId ->
                    sessionRepository.createSession(input, nowEpochMillis, sessionId)
                        .session
                        .toSessionListItem(avatarVisible = true)
                },
                saveOpeningMessage = messageRepository::saveMessage
            )
            val chatRunsPort = RepositoryChatRunsPortAdapter(
                listRuns = conversationRunRepository::listBySession,
                findRun = conversationRunRepository::findRun,
                saveRun = conversationRunRepository::saveRun,
                isWritableAttempt = conversationRunRepository::isWritableAttempt,
                runCoordinator = runCoordinator,
                setModelBinding = sessionRepository::setModelBinding
            )
            val modelConnectionsPort = RepositoryModelConnectionsPortAdapter(
                listConnections = {
                    modelConnectionRepository.listConnections(SessionRepository.defaultSpaceId)
                },
                listBindings = {
                    modelConnectionRepository.listBindingsBySpace(SessionRepository.defaultSpaceId)
                },
                setModelBinding = sessionRepository::setModelBinding
            )
            val weeklyDashboardPort = RepositoryWeeklyDashboardPortAdapter(
                listSummaries = {
                    learningRepository.listWeeklySummaries(SessionRepository.defaultSpaceId)
                },
                listTasks = {
                    learningRepository.listTasks(SessionRepository.defaultSpaceId)
                },
                listTokenUsage = {
                    val turnToSession = buildMap {
                        sessionRepository.listSessions().forEach { session ->
                            conversationRunRepository.listBySession(session.id).forEach { run ->
                                put(run.turnId, session.id)
                            }
                        }
                    }
                    learningRepository.listTokenUsage(SessionRepository.defaultSpaceId).map { usage ->
                        WeeklyTokenUsageEntry(usage, turnToSession[usage.turnId])
                    }
                },
                saveTask = {
                    learningRepository.saveTask(it)
                }
            )

            val learningOverviewPort = RepositoryLearningOverviewPortAdapter(
                assembly = sessionConversationAssembly
            )
            val learningOverviewViewModelFactory = LearningOverviewPortViewModelFactory(
                port = learningOverviewPort
            )
            return HybridFrontendFactories(
                learningOverviewViewModelFactory = learningOverviewViewModelFactory,
                workspaceViewModelFactory = DefaultWorkspaceViewModelFactory,
                homeViewModelFactory = HomePortViewModelFactory(homePort),
                sessionHomePort = sessionHomePort,
                newSessionCreatePort = newSessionCreatePort,
                newSessionPersistence = newSessionPersistence,
                tagLibraryPersistence = tagLibraryPersistence,
                chatRunsViewModelFactory = ChatRunsPortViewModelFactory(chatRunsPort),
                modelConnectionsViewModelFactory =
                    ModelConnectionsPortViewModelFactory(modelConnectionsPort),
                weeklyDashboardViewModelFactory =
                    WeeklyDashboardPortViewModelFactory(
                        port = weeklyDashboardPort,
                        configurationStore = SharedPreferencesWeeklyDashboardConfigurationStore(context)
                    )
            )
        }
    }
}
