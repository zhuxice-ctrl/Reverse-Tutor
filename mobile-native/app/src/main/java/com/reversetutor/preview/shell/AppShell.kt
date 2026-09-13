package com.reversetutor.preview.shell

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.core.app.NotificationManagerCompat
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.NavigationDrawerItemDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.TextButton
import androidx.compose.material3.Text
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.snapshotFlow
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.LifecycleOwner
import androidx.core.content.ContextCompat
import com.reversetutor.core.data.background.BackgroundGenerationRepository
import com.reversetutor.core.data.graph.GraphRepository
import com.reversetutor.core.data.llm.ChatGenerationRepository
import com.reversetutor.core.data.llm.LlmProfileRepository
import com.reversetutor.core.data.memory.MemoryRepository
import com.reversetutor.core.data.message.MessageRepository
import com.reversetutor.core.data.session.SessionRepository
import com.reversetutor.core.data.sources.SourceImportInput
import com.reversetutor.core.data.sources.SourceImportResult
import com.reversetutor.core.data.sources.SourceRepository
import com.reversetutor.core.data.preferences.AppPreferences
import com.reversetutor.core.data.memory.ErrorLogInput
import com.reversetutor.core.llm.LlmProviderPreset
import com.reversetutor.core.model.ErrorLogOrigin
import com.reversetutor.core.model.LlmProfile
import com.reversetutor.core.model.SearchTarget
import com.reversetutor.core.model.SearchTargetType
import com.reversetutor.feature.chat.ChatRoute
import com.reversetutor.feature.chat.ChatAttachmentKind
import com.reversetutor.feature.chat.ChatAttachmentReadiness
import com.reversetutor.feature.chat.ChatDraftAttachment
import com.reversetutor.feature.chat.ChatPermissionState
import com.reversetutor.feature.chat.ChatPendingDeletionSweeper
import com.reversetutor.feature.chat.ChatQueryHighlight
import com.reversetutor.feature.chat.ChatReferenceQueryRoute
import com.reversetutor.feature.chat.ChatReferenceQueryState
import com.reversetutor.feature.chat.ChatScrollMemory
import com.reversetutor.feature.chat.LearningOverviewPanel
import com.reversetutor.feature.chat.LearningOverviewUiAction
import com.reversetutor.feature.chat.LearningOverviewUiState
import com.reversetutor.feature.chat.NewSessionPrefillRequest
import com.reversetutor.feature.chat.SessionSource
import com.reversetutor.feature.chat.Task2B1NewSessionRoute
import com.reversetutor.feature.chat.SessionsRoute
import com.reversetutor.feature.chat.WindowBranchAction
import com.reversetutor.feature.chat.WindowBranchPanel
import com.reversetutor.feature.chat.WindowBranchPresenter
import com.reversetutor.feature.chat.WindowBranchResult
import com.reversetutor.feature.chat.WindowBranchUiState
import com.reversetutor.feature.chat.toSessionListItem
import com.reversetutor.feature.memory.ContextHubRoute
import com.reversetutor.feature.memory.GlobalGraphRoute
import com.reversetutor.core.domain.LearningOverviewScope
import com.reversetutor.feature.sources.SourcesRoute
import com.reversetutor.feature.settings.FirstLaunchImportPromptUiState
import com.reversetutor.feature.settings.FormalLlmConfigurationScreen
import com.reversetutor.feature.settings.LlmProfileSettingsUiState
import com.reversetutor.feature.settings.FormalSettingsScreen
import com.reversetutor.preview.background.GenerationDiagnosticPolicy
import com.reversetutor.preview.background.BackgroundGenerationWorker
import com.reversetutor.preview.theme.ReverseTutorDesign
import com.reversetutor.preview.theme.ReverseTutorStatusTone
import com.reversetutor.preview.ui.ReverseTutorActionButton
import com.reversetutor.preview.ui.ReverseTutorActionTone
import com.reversetutor.preview.ui.ReverseTutorConfirmationDialog
import com.reversetutor.preview.ui.ReverseTutorScaffold
import com.reversetutor.preview.ui.ReverseTutorScreenSurface
import com.reversetutor.preview.ui.ReverseTutorStatusStrip
import com.reversetutor.preview.ui.ReverseTutorTopAppBar
import com.reversetutor.preview.wiring.HybridAppGraph
import com.reversetutor.preview.wiring.SharedPreferencesChatSourceUsagePort
import com.reversetutor.preview.wiring.SharedPreferencesChatAttachmentOrderStore
import com.reversetutor.preview.wiring.SharedPreferencesChatDraftStore
import com.reversetutor.preview.wiring.SharedPreferencesChatPendingDeletionStore
import com.reversetutor.preview.wiring.SharedPreferencesChatRememberedMessageStore
import com.reversetutor.preview.wiring.SharedPreferencesSessionSettingsStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

internal fun shouldShowActivityAnnouncement(
    destination: AppDestination,
    dismissed: Boolean,
    firstLaunchImportPromptVisible: Boolean,
    challengeSessionPrefill: NewSessionPrefillRequest?
): Boolean = destination == AppDestination.NewSession &&
    !dismissed &&
    !firstLaunchImportPromptVisible &&
    challengeSessionPrefill == null

internal fun shouldClearChatEvidenceTarget(destination: AppDestination): Boolean =
    destination != AppDestination.Chat

internal fun shouldClearSourceEvidenceTarget(destination: AppDestination): Boolean =
    destination != AppDestination.Sources &&
        destination != AppDestination.SessionSettingsSources

internal sealed interface ChallengeNewSessionCloseDecision {
    data object Sessions : ChallengeNewSessionCloseDecision
    data class RestoreChallenge(
        val context: ChallengeReturnContext
    ) : ChallengeNewSessionCloseDecision
}

internal fun resolveChallengeNewSessionClose(
    challengeSessionPrefill: NewSessionPrefillRequest?,
    returnContext: ChallengeReturnContext?
): ChallengeNewSessionCloseDecision =
    if (challengeSessionPrefill != null && returnContext != null) {
        ChallengeNewSessionCloseDecision.RestoreChallenge(returnContext)
    } else {
        ChallengeNewSessionCloseDecision.Sessions
    }

@Composable
fun AppShell(
    hybridAppGraph: HybridAppGraph,
    appPreferences: AppPreferences = AppPreferences.defaults,
    sessionRepository: SessionRepository,
    messageRepository: MessageRepository,
    llmProfileRepository: LlmProfileRepository,
    chatGenerationRepository: ChatGenerationRepository,
    backgroundGenerationRepository: BackgroundGenerationRepository? = null,
    sourceRepository: SourceRepository,
    memoryRepository: MemoryRepository,
    graphRepository: GraphRepository,
    firstLaunchImportPromptState: FirstLaunchImportPromptUiState = FirstLaunchImportPromptUiState.preview(),
    initialImportText: String? = null,
    initialImportFileName: String? = null,
    pendingOpenSessionId: String? = null,
    onOpenSessionConsumed: () -> Unit = {},
    onExitRequested: () -> Unit
) {
    var navigationState by remember { mutableStateOf(AppNavigationState()) }
    var activeSessionId by remember { mutableStateOf<String?>(null) }
    var activeSessionTitle by remember { mutableStateOf<String?>(null) }
    var activeSessionLearnerRole by remember { mutableStateOf("学习者") }
    var activeArticleSlug by remember { mutableStateOf("") }
    LaunchedEffect(pendingOpenSessionId) {
        val sessionId = pendingOpenSessionId ?: return@LaunchedEffect
        sessionRepository.getSession(sessionId)
            ?.toSessionListItem(appPreferences.globalAvatarVisible)
            ?.let { session ->
                activeSessionId = session.id
                activeSessionTitle = session.title
                activeSessionLearnerRole = session.learnerRole
                navigationState = navigationState.navigate(AppDestination.Chat)
            }
        onOpenSessionConsumed()
    }
    val chatScrollMemory = remember { ChatScrollMemory() }
    var figmaUiState by remember { mutableStateOf(FigmaAppUiState()) }
    var challengeEntryGeneration by remember { mutableStateOf(0L) }
    var challengeSessionPrefill by remember { mutableStateOf<NewSessionPrefillRequest?>(null) }
    var challengeCurrentReturnContext by remember { mutableStateOf(ChallengeReturnContext()) }
    var challengePrefillReturnContext by remember { mutableStateOf<ChallengeReturnContext?>(null) }
    var challengeRestoreContext by remember { mutableStateOf<ChallengeReturnContext?>(null) }
    var workspaceChromeObscuredPages by remember { mutableStateOf(emptySet<WorkspacePage>()) }
    var pageLocalActionDismissers by remember {
        mutableStateOf(emptyMap<WorkspacePage, () -> Unit>())
    }
    var showFirstLaunchImportPrompt by remember(firstLaunchImportPromptState) {
        mutableStateOf(firstLaunchImportPromptState.shouldShow)
    }
    val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
    val appScope = rememberCoroutineScope()
    val workspaceViewModelFactory = hybridAppGraph.frontend.workspaceViewModelFactory
    val workspaceViewModel = remember(workspaceViewModelFactory) {
        workspaceViewModelFactory.create()
    }
    val workspaceState by workspaceViewModel.uiState.collectAsState()
    val challengeRuntimeCoordinator = hybridAppGraph.challengeRuntimeCoordinator
    val challengeRuntimeState by challengeRuntimeCoordinator.state.collectAsState()
    val challengeJoinFlowCoordinator = remember(
        challengeRuntimeCoordinator,
        sessionRepository,
        hybridAppGraph.frontend.newSessionPersistence
    ) {
        ChallengeJoinFlowCoordinator(challengeRuntimeCoordinator) {
            sessionRepository.listSessions()
                .filterNot { it.archived }
                .map { session ->
                    val snapshot = hybridAppGraph.frontend.newSessionPersistence
                        .loadSessionSnapshot(session.id)
                    ChallengeSessionCandidate(
                        sessionId = session.id,
                        title = session.title,
                        learnerRole = snapshot?.learnerRole ?: "学习者",
                        updatedAtEpochMillis = session.updatedAtEpochMillis,
                        snapshot = snapshot
                    )
                }
        }
    }
    val learningOverviewViewModelFactory = hybridAppGraph.frontend.learningOverviewViewModelFactory
    val learningOverviewViewModel = remember(learningOverviewViewModelFactory, appScope) {
        learningOverviewViewModelFactory.create(
            scope = LearningOverviewScope(spaceId = SessionRepository.defaultSpaceId),
            coroutineScope = appScope
        )
    }
    val learningOverviewState by learningOverviewViewModel.uiState.collectAsState()
    val workspaceInteractions = remember(workspaceViewModel) {
        WorkspaceInteractionBindings(workspaceViewModel::onAction)
    }
    val lifecycleOwner = LocalContext.current as? LifecycleOwner

    fun openChallenge() {
        challengeRestoreContext = null
        challengeEntryGeneration += 1L
        workspaceViewModel.onAction(WorkspaceUiAction.SetChallengeExitBoundary(false))
        navigationState = navigationState.navigate(AppDestination.Challenge)
    }

    fun applyConfirmedChallengeJoin(
        launch: ChallengeSessionLaunchDecision,
        returnContext: ChallengeReturnContext
    ) {
        workspaceViewModel.onAction(
            WorkspaceUiAction.SelectVerticalPage(WorkspaceVerticalPage.SessionHome)
        )
        when (launch) {
            is ChallengeSessionLaunchDecision.Reuse -> {
                challengeSessionPrefill = null
                challengePrefillReturnContext = null
                challengeRestoreContext = null
                activeSessionId = launch.candidate.sessionId
                activeSessionTitle = launch.candidate.title
                activeSessionLearnerRole = launch.candidate.learnerRole
                navigationState = navigationState.navigate(AppDestination.Chat)
            }
            is ChallengeSessionLaunchDecision.Create -> {
                challengePrefillReturnContext = returnContext
                challengeSessionPrefill = launch.prefill
                figmaUiState = figmaUiState.dismissActivityAnnouncement()
                navigationState = navigationState.navigate(AppDestination.NewSession)
            }
        }
    }

    DisposableEffect(lifecycleOwner, workspaceViewModel) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP) {
                workspaceViewModel.onAction(WorkspaceUiAction.ReleaseHeavyResources)
            }
        }
        lifecycleOwner?.lifecycle?.addObserver(observer)
        onDispose {
            lifecycleOwner?.lifecycle?.removeObserver(observer)
        }
    }

    LaunchedEffect(challengeRuntimeCoordinator) {
        challengeRuntimeCoordinator.load()
    }

    WorkspaceBackHandler(
        navigationState = navigationState,
        workspaceState = workspaceState,
        pageLocalActionSurfaceActive =
            pageLocalActionDismissers.containsKey(workspaceState.currentPage),
        onDismissPageLocalActionSurface = {
            pageLocalActionDismissers[workspaceState.currentPage]?.invoke()
        },
        onExitGraphCanvas = {
            workspaceViewModel.onAction(WorkspaceUiAction.SetGraphCanvasModeActive(false))
        },
        onNavigationStateChange = { navigationState = it },
        onExitRequested = onExitRequested
    )

    LaunchedEffect(initialImportText, initialImportFileName) {
        if (!initialImportText.isNullOrBlank()) {
            navigationState = navigationState.navigate(AppDestination.ImportExport)
        }
    }

    LaunchedEffect(navigationState.current) {
        workspaceSelectionFor(navigationState.current)?.let { selection ->
            if (selection.horizontal != workspaceState.currentPage) {
                workspaceViewModel.onAction(WorkspaceUiAction.SelectPage(selection.horizontal))
            }
            selection.vertical?.let { verticalPage ->
                if (verticalPage != workspaceState.verticalPage) {
                    workspaceViewModel.onAction(WorkspaceUiAction.SelectVerticalPage(verticalPage))
                }
            }
        }
    }

    LaunchedEffect(navigationState.drawerOpen) {
        if (navigationState.drawerOpen) {
            drawerState.open()
        } else {
            drawerState.close()
        }
    }
    LaunchedEffect(drawerState) {
        snapshotFlow { drawerState.currentValue }
            .map { it == DrawerValue.Open }
            .distinctUntilChanged()
            .collect { open ->
                if (!open && navigationState.drawerOpen) {
                    navigationState = navigationState.closeDrawer()
                }
            }
    }

    ModalNavigationDrawer(
        drawerState = drawerState,
        gesturesEnabled = navigationState.drawerOpen,
        drawerContent = {
            AppDrawer(
                current = navigationState.current,
                onDestinationClick = {
                    navigationState = navigationState.navigate(it)
                },
                onImportExportClick = {
                    navigationState = navigationState.navigate(AppDestination.ImportExport)
                }
            )
        }
    ) {
        ReverseTutorScaffold(
            topBar = {
                if (!navigationState.current.ownsInContentTopBar()) {
                    PreviewTopBar(
                        destination = navigationState.current,
                        activeSessionTitle = activeSessionTitle,
                        onNavigationClick = {
                            if (navigationState.current.usesDrawerNavigation()) {
                                navigationState = navigationState.openDrawer()
                            } else {
                                val transition = navigationState.handleSystemBack()
                                navigationState = transition.state
                            }
                        },
                        onStatusClick = {
                            if (navigationState.current == AppDestination.Chat) {
                                navigationState =
                                    navigationState.navigate(AppDestination.SessionSettingsLibrary)
                            } else {
                                navigationState = navigationState.openModal(AppModal.Status)
                            }
                        },
                        onChallengeClick = {
                            openChallenge()
                        },
                        onNewSessionClick = {
                            navigationState = navigationState.navigate(AppDestination.NewSession)
                        }
                    )
                }
            }
        ) { innerPadding ->
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding)
            ) {
                val renderDestination: @Composable (AppDestination) -> Unit = { destination ->
                    DestinationContent(
                        destination = destination,
                        hybridAppGraph = hybridAppGraph,
                        appPreferences = appPreferences,
                        sessionRepository = sessionRepository,
                        messageRepository = messageRepository,
                        llmProfileRepository = llmProfileRepository,
                        chatGenerationRepository = chatGenerationRepository,
                        backgroundGenerationRepository = backgroundGenerationRepository,
                        sourceRepository = sourceRepository,
                        memoryRepository = memoryRepository,
                        graphRepository = graphRepository,
                        initialImportText = initialImportText,
                        initialImportFileName = initialImportFileName,
                        activeSessionId = activeSessionId,
                        activeSessionTitle = activeSessionTitle,
                        activeSessionLearnerRole = activeSessionLearnerRole,
                        activeArticleSlug = activeArticleSlug,
                        chatScrollMemory = chatScrollMemory,
                        challengeRuntimeState = challengeRuntimeState,
                        challengePageActive = navigationState.current == AppDestination.Challenge &&
                            workspaceState.verticalPage == WorkspaceVerticalPage.Challenge,
                        challengeEntryGeneration = challengeEntryGeneration,
                        challengeSessionPrefill = challengeSessionPrefill,
                        challengeRestoreContext = challengeRestoreContext,
                        challengeProgress = challengeRuntimeState.participation?.progress?.toInt()
                            ?: figmaUiState.challengeProgress,
                        challengeTotal = figmaUiState.challengeTotal,
                        learningOverviewState = learningOverviewState,
                        onLearningOverviewAction = learningOverviewViewModel::onAction,
                        onComposerFocusChanged = workspaceInteractions::onComposerFocusChanged,
                        onWidgetDragChanged = workspaceInteractions::onWidgetDragChanged,
                        onInnerHorizontalControlChanged = workspaceInteractions::onInnerHorizontalControlChanged,
                        onGraphInteractionChanged =
                            workspaceInteractions::onFullscreenGraphInteractionChanged,
                        graphCanvasModeActive = workspaceState.interactionLocks.graphCanvasModeActive,
                        onGraphCanvasModeChanged = workspaceInteractions::onGraphCanvasModeChanged,
                        onChallengeExitBoundaryChanged = { canReturnHome ->
                            workspaceViewModel.onAction(
                                WorkspaceUiAction.SetChallengeExitBoundary(canReturnHome)
                            )
                        },
                        onWorkspaceChromeObscuredChanged = { page, obscured ->
                            workspaceChromeObscuredPages = if (obscured) {
                                workspaceChromeObscuredPages + page
                            } else {
                                workspaceChromeObscuredPages - page
                            }
                        },
                        onPageLocalActionSurfaceChanged = { page, active, dismiss ->
                            pageLocalActionDismissers = if (active) {
                                pageLocalActionDismissers + (page to dismiss)
                            } else {
                                pageLocalActionDismissers - page
                            }
                        },
                        onOpenChat = {
                            navigationState = navigationState.navigate(AppDestination.Chat)
                        },
                        onOpenSession = { session ->
                            activeSessionId = session.id
                            activeSessionTitle = session.title
                            activeSessionLearnerRole = session.learnerRole
                            navigationState = navigationState.navigate(AppDestination.Chat)
                        },
                        onOpenContextHub = {
                            navigationState =
                                navigationState.navigate(AppDestination.ContextHub)
                        },
                        onOpenGlobalGraph = {
                            navigationState = navigationState.navigate(AppDestination.GlobalGraph)
                        },
                        onOpenSources = {
                            navigationState = navigationState.navigate(AppDestination.Sources)
                        },
                        onOpenSessions = {
                            navigationState = navigationState.navigate(AppDestination.Sessions)
                        },
                        onOpenChallenge = {
                            openChallenge()
                        },
                        onChallengeReturnContextChanged = {
                            challengeCurrentReturnContext = it
                        },
                        onChallengeRestoreConsumed = {
                            challengeRestoreContext = null
                        },
                        onChallengeJoined = {
                            val returnContext = challengeCurrentReturnContext.copy(detailOpen = true)
                            appScope.launch {
                                challengeJoinFlowCoordinator.join()?.let { launch ->
                                    applyConfirmedChallengeJoin(launch, returnContext)
                                }
                            }
                        },
                        onChallengeRetry = {
                            val returnContext = challengeCurrentReturnContext.copy(detailOpen = true)
                            appScope.launch {
                                challengeJoinFlowCoordinator.retry()?.let { launch ->
                                    applyConfirmedChallengeJoin(launch, returnContext)
                                }
                            }
                        },
                        onOpenNewSession = {
                            challengeSessionPrefill = null
                            challengePrefillReturnContext = null
                            challengeRestoreContext = null
                            navigationState = navigationState.navigate(AppDestination.NewSession)
                        },
                        onOpenPublicArticle = { slug ->
                            activeArticleSlug = slug
                            navigationState = navigationState.navigate(AppDestination.PublicArticle)
                        },
                        onOpenSearchTarget = { target ->
                            appScope.launch {
                                when (target.type) {
                                    SearchTargetType.Session,
                                    SearchTargetType.Message -> {
                                        val sessionId = target.sessionId ?: target.entityId
                                        sessionRepository.getSession(sessionId)?.let { session ->
                                            activeSessionId = session.id
                                            activeSessionTitle = session.title
                                            navigationState = navigationState.navigate(AppDestination.Chat)
                                        }
                                    }
                                    SearchTargetType.Source -> {
                                        navigationState = navigationState.navigate(AppDestination.Sources)
                                    }
                                    SearchTargetType.Memory,
                                    SearchTargetType.GraphNode -> {
                                        navigationState = navigationState.navigate(AppDestination.GlobalGraph)
                                    }
                                    SearchTargetType.StudyPlan -> {
                                        navigationState = navigationState.navigate(AppDestination.WeeklyDashboard)
                                    }
                                }
                            }
                        },
                        onSessionCreated = { session ->
                            challengeSessionPrefill = null
                            challengePrefillReturnContext = null
                            challengeRestoreContext = null
                            activeSessionId = session.id
                            activeSessionTitle = session.title
                            activeSessionLearnerRole = session.learnerRole
                            navigationState = navigationState.navigate(AppDestination.Chat)
                        },
                        onActiveSessionTitleChanged = { activeSessionTitle = it },
                        onActiveSessionLearnerRoleChanged = { activeSessionLearnerRole = it },
                        onActiveSessionDeleted = {
                            activeSessionId = null
                            activeSessionTitle = null
                            activeSessionLearnerRole = "学习者"
                            navigationState = navigationState.navigate(AppDestination.Sessions)
                        },
                        onCloseNewSession = {
                            val decision = resolveChallengeNewSessionClose(
                                challengeSessionPrefill,
                                challengePrefillReturnContext
                            )
                            challengeSessionPrefill = null
                            challengePrefillReturnContext = null
                            when (decision) {
                                is ChallengeNewSessionCloseDecision.RestoreChallenge -> {
                                    challengeRestoreContext = decision.context
                                    workspaceViewModel.onAction(
                                        WorkspaceUiAction.SelectVerticalPage(
                                            WorkspaceVerticalPage.Challenge
                                        )
                                    )
                                    navigationState = navigationState.navigate(
                                        AppDestination.Challenge
                                    )
                                }
                                ChallengeNewSessionCloseDecision.Sessions -> {
                                    challengeRestoreContext = null
                                    navigationState = navigationState.navigate(AppDestination.Sessions)
                                }
                            }
                        },
                        onOpenSettings = {
                            navigationState = navigationState.navigate(AppDestination.Settings)
                        },
                        onOpenImportExport = {
                            navigationState = navigationState.navigate(AppDestination.ImportExport)
                        },
                        onOpenAbout = {
                            navigationState = navigationState.navigate(AppDestination.About)
                        },
                        onNavigateDestination = { destination ->
                            navigationState = navigationState.navigate(destination)
                        }
                    )
                }
                if (navigationState.current.workspacePage != null) {
                    WorkspacePagerHost(
                        state = workspaceState.selectedForDestination(navigationState.current),
                        interactions = workspaceInteractions,
                        onPageSelected = { page ->
                            workspaceViewModel.onAction(WorkspaceUiAction.SelectPage(page))
                            if (navigationState.current != page.destination) {
                                navigationState = navigationState.navigate(page.destination)
                            }
                        },
                        onVerticalPageSelected = { page ->
                            workspaceViewModel.onAction(WorkspaceUiAction.SelectVerticalPage(page))
                            val destination = when (page) {
                                WorkspaceVerticalPage.Challenge -> AppDestination.Challenge
                                WorkspaceVerticalPage.SessionHome -> AppDestination.Sessions
                            }
                            if (navigationState.current != destination) {
                                navigationState = navigationState.navigate(destination)
                            }
                        },
                        showIndicator = workspaceChromeObscuredPages.isEmpty(),
                        onChallengeEntryStarted = {
                            challengeEntryGeneration += 1L
                            workspaceViewModel.onAction(
                                WorkspaceUiAction.SetChallengeExitBoundary(false)
                            )
                        },
                        challengeContent = {
                            renderDestination(AppDestination.Challenge)
                        },
                        pageContent = { page -> renderDestination(page.destination) }
                    )
                } else {
                    renderDestination(navigationState.current)
                }
            }
        }
    }

    if (navigationState.modal == AppModal.Status) {
        StatusDialog(
            destination = navigationState.current,
            onDismiss = {
                navigationState = navigationState.closeModal()
            }
        )
    }

    if (showFirstLaunchImportPrompt) {
        FirstLaunchImportPromptDialog(
            state = firstLaunchImportPromptState,
            onConfirm = {
                showFirstLaunchImportPrompt = false
                navigationState = navigationState.navigate(AppDestination.ImportExport)
            },
            onDismiss = {
                showFirstLaunchImportPrompt = false
            }
        )
    }

    if (shouldShowActivityAnnouncement(
            destination = navigationState.current,
            dismissed = figmaUiState.activityAnnouncementDismissed,
            firstLaunchImportPromptVisible = showFirstLaunchImportPrompt,
            challengeSessionPrefill = challengeSessionPrefill
        )
    ) {
        ActivityAnnouncementDialog(
            onDismiss = {
                figmaUiState = figmaUiState.dismissActivityAnnouncement()
            },
            onViewChallenge = {
                figmaUiState = figmaUiState.dismissActivityAnnouncement()
                openChallenge()
            }
        )
    }
}

@Composable
private fun PreviewTopBar(
    destination: AppDestination,
    activeSessionTitle: String?,
    onNavigationClick: () -> Unit,
    onStatusClick: () -> Unit,
    onChallengeClick: () -> Unit,
    onNewSessionClick: () -> Unit
) {
    val title = if (destination == AppDestination.Chat && !activeSessionTitle.isNullOrBlank()) {
        activeSessionTitle
    } else {
        destination.title
    }

    ReverseTutorTopAppBar(
        title = title,
        subtitle = destination.status,
        navigationLabel = if (destination.usesDrawerNavigation()) "菜单" else "返回",
        onNavigationClick = onNavigationClick,
        actionLabel = when (destination) {
            AppDestination.Chat -> "⚙"
            AppDestination.NewSession,
            AppDestination.ChatReferences,
            AppDestination.SessionSettingsLibrary,
            AppDestination.SessionSettingsSources,
            AppDestination.SessionSettingsGraph,
            AppDestination.SessionSettingsPersona,
            AppDestination.SessionSettingsPersonalization -> "⋮"
            else -> null
        },
        onActionClick = onStatusClick,
        actions = {
            if (destination == AppDestination.Sessions) {
                ReverseTutorActionButton(
                    label = "挑战",
                    onClick = onChallengeClick,
                    tone = ReverseTutorActionTone.Quiet
                )
                ReverseTutorActionButton(
                    label = "新建",
                    onClick = onNewSessionClick
                )
            }
        }
    )
}

@Composable
private fun AppDrawer(
    current: AppDestination,
    onDestinationClick: (AppDestination) -> Unit,
    onImportExportClick: () -> Unit
) {
    val spacing = ReverseTutorDesign.spacing
    val selectedDestination = when (current) {
        AppDestination.LlmConfiguration,
        AppDestination.ImportExport,
        AppDestination.About,
        AppDestination.TokenUsage,
        AppDestination.Update -> AppDestination.Settings
        AppDestination.GlobalSearch,
        AppDestination.PublicArticle -> AppDestination.Sessions
        else -> current
    }

    ModalDrawerSheet(
        modifier = Modifier.width(304.dp),
        drawerContainerColor = MaterialTheme.colorScheme.surface
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(vertical = spacing.space4),
            verticalArrangement = Arrangement.spacedBy(spacing.space1)
        ) {
            Column(
                modifier = Modifier.padding(horizontal = spacing.space5, vertical = spacing.space3),
                verticalArrangement = Arrangement.spacedBy(spacing.space2)
            ) {
                Text(
                    text = "反转家教",
                    color = MaterialTheme.colorScheme.onSurface,
                    style = MaterialTheme.typography.titleLarge
                )
                Surface(
                    color = MaterialTheme.colorScheme.surfaceVariant,
                    contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
                    shape = MaterialTheme.shapes.small
                ) {
                    Text(
                        text = "默认空间",
                        modifier = Modifier.padding(horizontal = spacing.space3, vertical = spacing.space2),
                        style = MaterialTheme.typography.labelMedium
                    )
                }
            }
            AppDestination.drawerItems.forEach { item ->
                NavigationDrawerItem(
                    label = { Text(if (item.enabled) item.label else "${item.label}（暂未开放）") },
                    selected = item.enabled && item.destination == selectedDestination,
                    onClick = {
                        if (item.enabled) {
                            onDestinationClick(item.destination)
                        }
                    },
                    modifier = Modifier.padding(horizontal = spacing.space3),
                    colors = NavigationDrawerItemDefaults.colors(
                        selectedContainerColor = MaterialTheme.colorScheme.primaryContainer,
                        selectedTextColor = MaterialTheme.colorScheme.onPrimaryContainer,
                        unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                )
            }
            Spacer(modifier = Modifier.weight(1f))
            Surface(
                color = MaterialTheme.colorScheme.surfaceVariant,
                contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = spacing.space5, vertical = spacing.space3),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "数据管理",
                        style = MaterialTheme.typography.labelMedium
                    )
                    TextButton(onClick = onImportExportClick) {
                        Text("导入/导出")
                    }
                }
            }
        }
    }
}

private fun AppDestination.usesDrawerNavigation(): Boolean =
    AppDestination.drawerItems.any { it.enabled && it.destination == this }

private fun AppDestination.ownsInContentTopBar(): Boolean =
    workspacePage != null ||
        this == AppDestination.Chat ||
        this == AppDestination.ChatReferences ||
        this == AppDestination.NewSession ||
        this == AppDestination.Settings ||
        this == AppDestination.LlmConfiguration ||
        this == AppDestination.GlobalSearch ||
        this == AppDestination.PublicArticle ||
        this == AppDestination.ImportExport ||
        this == AppDestination.About ||
        this == AppDestination.TokenUsage ||
        this == AppDestination.Update ||
        this == AppDestination.SessionSettings ||
        this == AppDestination.SessionSettingsLibrary ||
        this == AppDestination.SessionSettingsSources ||
        this == AppDestination.SessionSettingsGraph ||
        this == AppDestination.SessionSettingsPersona ||
        this == AppDestination.SessionSettingsPersonalization

@Composable
private fun DestinationContent(
    destination: AppDestination,
    hybridAppGraph: HybridAppGraph,
    appPreferences: AppPreferences,
    sessionRepository: SessionRepository,
    messageRepository: MessageRepository,
    llmProfileRepository: LlmProfileRepository,
    chatGenerationRepository: ChatGenerationRepository,
    backgroundGenerationRepository: BackgroundGenerationRepository?,
    sourceRepository: SourceRepository,
    memoryRepository: MemoryRepository,
    graphRepository: GraphRepository,
    initialImportText: String?,
    initialImportFileName: String?,
    activeSessionId: String?,
    activeSessionTitle: String?,
    activeSessionLearnerRole: String,
    activeArticleSlug: String,
    chatScrollMemory: ChatScrollMemory,
    challengeRuntimeState: ChallengeRuntimeState,
    challengePageActive: Boolean,
    challengeEntryGeneration: Long,
    challengeSessionPrefill: NewSessionPrefillRequest?,
    challengeRestoreContext: ChallengeReturnContext?,
    challengeProgress: Int,
    challengeTotal: Int,
    learningOverviewState: LearningOverviewUiState,
    onLearningOverviewAction: (LearningOverviewUiAction) -> Unit,
    onComposerFocusChanged: (Boolean) -> Unit,
    onWidgetDragChanged: (Boolean) -> Unit,
    onInnerHorizontalControlChanged: (Boolean) -> Unit,
    onGraphInteractionChanged: (Boolean) -> Unit,
    graphCanvasModeActive: Boolean,
    onGraphCanvasModeChanged: (Boolean) -> Unit,
    onChallengeExitBoundaryChanged: (Boolean) -> Unit,
    onChallengeReturnContextChanged: (ChallengeReturnContext) -> Unit,
    onChallengeRestoreConsumed: () -> Unit,
    onWorkspaceChromeObscuredChanged: (WorkspacePage, Boolean) -> Unit,
    onPageLocalActionSurfaceChanged: (WorkspacePage, Boolean, () -> Unit) -> Unit,
    onOpenChat: () -> Unit,
    onOpenSession: (com.reversetutor.feature.chat.SessionListItem) -> Unit,
    onOpenContextHub: () -> Unit,
    onOpenGlobalGraph: () -> Unit,
    onOpenSources: () -> Unit,
    onOpenSessions: () -> Unit,
    onOpenChallenge: () -> Unit,
    onChallengeJoined: () -> Unit,
    onChallengeRetry: () -> Unit,
    onOpenNewSession: () -> Unit,
    onOpenPublicArticle: (String) -> Unit,
    onOpenSearchTarget: (SearchTarget) -> Unit,
    onSessionCreated: (com.reversetutor.feature.chat.SessionListItem) -> Unit,
    onActiveSessionTitleChanged: (String) -> Unit,
    onActiveSessionLearnerRoleChanged: (String) -> Unit,
    onActiveSessionDeleted: () -> Unit,
    onCloseNewSession: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenImportExport: () -> Unit,
    onOpenAbout: () -> Unit,
    onNavigateDestination: (AppDestination) -> Unit
) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current

    // NEWMP-V1-024: fire-and-forget semantic indexing of a freshly imported
    // source. Failures are swallowed: the source stays on keyword retrieval.
    fun indexSourceAsync(imported: SourceImportResult) {
        scope.launch {
            val texts = imported.chunks.map { it.text }
            if (texts.isEmpty()) return@launch
            val vectors = chatGenerationRepository.embedSourceTexts(texts)
            if (vectors == null || vectors.size != imported.chunks.size) return@launch
            sourceRepository.updateChunkEmbeddings(imported.chunks.map { it.id }, vectors)
        }
    }
    val sessionSettingsStore = remember(context) { SharedPreferencesSessionSettingsStore(context) }
    val chatSourceUsagePort = remember(sessionSettingsStore) {
        SharedPreferencesChatSourceUsagePort(sessionSettingsStore)
    }
    var llmProfiles by remember { mutableStateOf(emptyList<LlmProfile>()) }
    var pendingSourceImport by remember { mutableStateOf<SourceImportInput?>(null) }
    var sessionSettingsSources by remember(activeSessionId) { mutableStateOf(emptyList<SessionSource>()) }
    var pickedSessionSource by remember(activeSessionId) { mutableStateOf<PickedSessionSource?>(null) }
    var sessionSettingsPickerActive by remember { mutableStateOf(false) }
    var chatSourcePickerActive by remember { mutableStateOf(false) }
    var sessionSettingsReplaceTarget by remember { mutableStateOf<String?>(null) }
    var failedSessionSettingsReplaceTarget by remember { mutableStateOf<String?>(null) }
    var invalidChatSourceReselectRequest by remember {
        mutableStateOf<com.reversetutor.feature.chat.ChatInvalidSourceReselectRequest?>(null)
    }
    var sessionSettingsImportError by remember { mutableStateOf<String?>(null) }
    var sessionSettingsRefreshKey by remember { mutableStateOf(0) }
    val chatDraftStore = remember(context) { SharedPreferencesChatDraftStore(context) }
    val chatAttachmentOrderStore = remember(context) { SharedPreferencesChatAttachmentOrderStore(context) }
    val chatPendingDeletionStore = remember(context) { SharedPreferencesChatPendingDeletionStore(context) }
    val chatRememberedMessageStore = remember(context) { SharedPreferencesChatRememberedMessageStore(context) }
    var pendingDeletionSweepGeneration by remember { mutableStateOf(0) }
    val chatClipboardPort = remember(context) { AndroidChatClipboardPort(context) }
    val chatImageMediaPort = remember(context) { AndroidChatImageMediaPort(context.applicationContext) }
    val chatMessageActionPort = remember(memoryRepository, graphRepository) {
        RepositoryChatMessageActionPort(memoryRepository, graphRepository)
    }
    val chatMessageDeletePort = remember(messageRepository) {
        RepositoryChatMessageDeletePort(messageRepository)
    }
    val chatPermissionPreferences = remember(context) {
        context.getSharedPreferences("reverse-tutor-chat-permissions", Context.MODE_PRIVATE)
    }
    var pendingChatAttachments by remember { mutableStateOf(emptyList<ChatDraftAttachment>()) }
    var pendingChatAttachmentNotice by remember { mutableStateOf<String?>(null) }
    var pendingChatEvidenceTarget by remember { mutableStateOf<String?>(null) }
    var pendingGraphEvidenceTarget by remember { mutableStateOf<String?>(null) }
    var pendingSourceEvidenceTarget by remember { mutableStateOf<String?>(null) }
    var windowBranchUiState by remember(activeSessionId) { mutableStateOf<WindowBranchUiState?>(null) }
    LaunchedEffect(destination) {
        // Evidence targets are one-time: clear them once the consuming screen is left
        // so a stale id cannot re-highlight on a later visit. Navigation is unchanged.
        if (shouldClearChatEvidenceTarget(destination)) {
            pendingChatEvidenceTarget = null
        }
        if (shouldClearSourceEvidenceTarget(destination)) {
            pendingSourceEvidenceTarget = null
        }
    }

    var chatReferenceQueryState by remember(activeSessionId) { mutableStateOf(ChatReferenceQueryState()) }
    var cameraPermissionState by remember(context) {
        mutableStateOf(
            if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                ChatPermissionState.Granted
            } else if (chatPermissionPreferences.getBoolean("camera-requested", false) &&
                (context as? Activity)?.shouldShowRequestPermissionRationale(Manifest.permission.CAMERA) != true
            ) {
                ChatPermissionState.PermanentlyDenied
            } else {
                ChatPermissionState.Requestable
            }
        )
    }
    val destinationLifecycleOwner = context as? LifecycleOwner
    DisposableEffect(destinationLifecycleOwner, context, destination) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                pendingDeletionSweepGeneration += 1
                cameraPermissionState = if (
                    ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
                ) {
                    ChatPermissionState.Granted
                } else {
                    if (cameraPermissionState == ChatPermissionState.Granted) {
                        ChatPermissionState.Requestable
                    } else {
                        cameraPermissionState
                    }
                }
            }
        }
        destinationLifecycleOwner?.lifecycle?.addObserver(observer)
        onDispose { destinationLifecycleOwner?.lifecycle?.removeObserver(observer) }
    }
    LaunchedEffect(chatPendingDeletionStore, messageRepository, pendingDeletionSweepGeneration) {
        val sweeper = ChatPendingDeletionSweeper(
            chatPendingDeletionStore,
            chatMessageDeletePort
        )
        while (true) {
            val now = System.currentTimeMillis()
            val result = sweeper.sweep(now)
            val next = result.nextSweepAtEpochMillis ?: break
            val remaining = next - System.currentTimeMillis()
            if (remaining > 0L) kotlinx.coroutines.delay(remaining)
        }
    }
    val sourceFileLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri != null) {
            scope.launch {
                runCatching {
                    val mimeType = context.contentResolver.getType(uri)
                    val requestId = System.currentTimeMillis()
                    val fileName = uri.lastPathSegment?.substringAfterLast('/') ?: "selected-source"
                    val input = buildSourceImportInput(
                        requestId = requestId,
                        fileName = fileName,
                        mimeType = mimeType,
                        uri = uri.toString(),
                        readText = {
                            if (isPdfSource(fileName, mimeType)) {
                                extractPdfSourceText(context, uri)
                            } else if (isDocxSource(fileName, mimeType)) {
                                // NEWMP-V1-021: Word 正文按文档顺序还原；
                                // 嵌入图片在原位置转写（本地 OCR 优先，
                                // 多模态兜底——V1-022 起永久开启）。
                                extractDocxSourceText(context, uri) { embedded ->
                                    transcribeDocxEmbeddedImage(
                                        context = context,
                                        repository = chatGenerationRepository,
                                        sessionId = activeSessionId,
                                        visionAssistEnabled = true,
                                        visionModelName = appPreferences.visionModelName,
                                        image = embedded
                                    )
                                }
                            } else if (isPptxSource(fileName, mimeType)) {
                                // NEWMP-V1-023: PPT 按页还原文字，
                                // 嵌入图片转写链与 Word 共用。
                                extractPptxSourceText(context, uri) { embedded ->
                                    transcribeDocxEmbeddedImage(
                                        context = context,
                                        repository = chatGenerationRepository,
                                        sessionId = activeSessionId,
                                        visionAssistEnabled = true,
                                        visionModelName = appPreferences.visionModelName,
                                        image = embedded
                                    )
                                }
                            } else if (isEpubSource(fileName, mimeType)) {
                                // NEWMP-V1-023: 电子书按章节顺序还原，
                                // 插图转写链与 Word 共用。
                                extractEpubSourceText(context, uri) { embedded ->
                                    transcribeDocxEmbeddedImage(
                                        context = context,
                                        repository = chatGenerationRepository,
                                        sessionId = activeSessionId,
                                        visionAssistEnabled = true,
                                        visionModelName = appPreferences.visionModelName,
                                        image = embedded
                                    )
                                }
                            } else if (isImageSource(fileName, mimeType)) {
                                // NEWMP-V1-020: OCR first (free, offline); when it
                                // finds no readable text, transcribe via the
                                // multimodal model so pure diagrams become
                                // usable. NEWMP-V1-022: always on, no toggle.
                                val ocrText = extractImageSourceText(context, uri)
                                if (ocrText == null && activeSessionId != null) {
                                    describeSourceImageWithVision(
                                        repository = chatGenerationRepository,
                                        sessionId = activeSessionId,
                                        fileName = fileName,
                                        mimeType = mimeType,
                                        uri = uri.toString(),
                                        visionModelName = appPreferences.visionModelName
                                    )
                                } else {
                                    ocrText
                                }
                            } else {
                                context.contentResolver.openInputStream(uri)
                                    ?.bufferedReader(Charsets.UTF_8)
                                    ?.use { readSourceTextWithinLimit(it) }
                            }
                        }
                    )
                    if (sessionSettingsPickerActive) {
                        context.tryPersistReadPermission(uri)
                        val imported = sourceRepository.importSource(input, requestId)
                        indexSourceAsync(imported)
                        val sessionId = activeSessionId
                        if (sessionId != null) {
                            when (val outcome = mapSessionSettingsImport(
                                result = imported,
                                currentSessionId = sessionId,
                                replacingSourceId = sessionSettingsReplaceTarget,
                                lastUsedAtEpochMillis = requestId
                            )) {
                                is SessionSourceImportOutcome.Usable -> {
                                    pickedSessionSource = outcome.picked
                                    sessionSettingsImportError = null
                                    failedSessionSettingsReplaceTarget = null
                                }
                                is SessionSourceImportOutcome.Rejected -> {
                                    sessionSettingsImportError = outcome.message
                                    failedSessionSettingsReplaceTarget = outcome.replacingSourceId
                                }
                            }
                        }
                    } else if (chatSourcePickerActive) {
                        context.tryPersistReadPermission(uri)
                        val imported = sourceRepository.importSource(input, requestId)
                        indexSourceAsync(imported)
                        val currentSessionSnapshot = activeSessionId?.let { sessionId ->
                            hybridAppGraph.frontend.newSessionPersistence.loadSessionSnapshot(sessionId)
                        }
                        // NEWMP-V1-006 Task 3: the pick-import projection is
                        // extracted to mapChatSourcePickImport so JVM tests
                        // pin the session-binding and notice contracts.
                        when (
                            val outcome = mapChatSourcePickImport(
                                imported = imported,
                                sessionId = activeSessionId,
                                currentSnapshot = currentSessionSnapshot
                            )
                        ) {
                            is ChatSourcePickImportOutcome.Bound -> {
                                val currentSessionId = requireNotNull(activeSessionId)
                                hybridAppGraph.frontend.newSessionPersistence.saveSessionSnapshot(
                                    currentSessionId,
                                    outcome.snapshot
                                )
                                sessionSettingsRefreshKey += 1
                                pendingChatAttachmentNotice = outcome.notice
                            }
                            is ChatSourcePickImportOutcome.Rejected ->
                                pendingChatAttachmentNotice = outcome.notice
                            null -> Unit
                        }
                    } else {
                        pendingSourceImport = input
                    }
                }.onFailure {
                    if (sessionSettingsPickerActive) {
                        sessionSettingsImportError = "资料导入失败，请重试。"
                        failedSessionSettingsReplaceTarget = sessionSettingsReplaceTarget
                    } else if (chatSourcePickerActive) {
                        pendingChatAttachmentNotice = "资料导入失败，请重试。"
                    }
                }
                sessionSettingsPickerActive = false
                chatSourcePickerActive = false
                sessionSettingsReplaceTarget = null
            }
        } else {
            sessionSettingsPickerActive = false
            chatSourcePickerActive = false
            sessionSettingsReplaceTarget = null
        }
    }
    fun acceptPlatformAttachment(input: ChatAttachmentPlatformInput) {
        val next = reduceChatAttachmentActivityResult(
            currentAttachments = pendingChatAttachments,
            input = input,
            currentNotice = pendingChatAttachmentNotice
        )
        pendingChatAttachments = next.attachments
        pendingChatAttachmentNotice = next.notice
    }
    val chatImageLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenMultipleDocuments()
    ) { uris ->
        scope.launch {
            val batchId = System.currentTimeMillis()
            val inputs = withContext(Dispatchers.IO) {
                uris.mapIndexed { index, uri ->
                    context.readChatAttachmentInput(
                        uri = uri,
                        id = "image-$batchId-$index"
                    )
                }
            }
            inputs.forEach(::acceptPlatformAttachment)
        }
    }
    val chatCameraLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicturePreview()
    ) { bitmap ->
        if (bitmap != null) {
            val id = "camera-${System.currentTimeMillis()}"
            acceptPlatformAttachment(context.persistCameraAttachment(bitmap, id))
        }
    }
    val chatCameraPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        val activity = context as? Activity
        cameraPermissionState = mapCameraPermissionResult(
            granted = granted,
            shouldShowRationale = activity?.shouldShowRequestPermissionRationale(Manifest.permission.CAMERA) == true
        )
        if (granted) chatCameraLauncher.launch(null)
    }
    val notificationStartupPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        scope.launch {
            hybridAppGraph.appPreferencesRepository
                .setBackgroundGenerationNotificationEnabled(granted)
        }
    }
    LaunchedEffect(Unit) {
        // Ask for the notification permission once on first launch so that
        // background generation completion notices can actually reach the user.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.POST_NOTIFICATIONS
            ) != PackageManager.PERMISSION_GRANTED &&
            !chatPermissionPreferences.getBoolean("notification-permission-requested", false)
        ) {
            chatPermissionPreferences.edit()
                .putBoolean("notification-permission-requested", true)
                .apply()
            notificationStartupPermissionLauncher.launch(
                Manifest.permission.POST_NOTIFICATIONS
            )
        }
    }
    val llmProfileState = LlmProfileSettingsUiState.from(
        profiles = llmProfiles,
        presets = LlmProviderPreset.defaults,
        connectionResult = null
    )
    LaunchedEffect(destination) {
        if (destination == AppDestination.Settings) {
            llmProfiles = llmProfileRepository.listProfiles()
        }
    }
    LaunchedEffect(destination, activeSessionId, sessionSettingsRefreshKey) {
        val currentSessionId = activeSessionId
        if (destination in setOf(
                AppDestination.Chat,
                AppDestination.ChatReferences,
                AppDestination.SessionSettings,
                AppDestination.SessionSettingsSources
            ) && currentSessionId != null
        ) {
            val sessions = sessionRepository.listSessions()
            val persistence = hybridAppGraph.frontend.newSessionPersistence
            val snapshots = sessions.associate { it.id to persistence.loadSessionSnapshot(it.id) }
            val favorites = persistence.loadFavorites()
            val catalog = buildSessionSettingsSourceCatalog(
                currentSessionId = currentSessionId,
                sessions = sessions,
                sessionSnapshots = snapshots,
                favorites = favorites,
                sources = sourceRepository.listSourcesWithChunks(),
                lastUsedAt = sessionSettingsStore.sourceLastUsedAt(currentSessionId)
            )
            sessionSettingsSources = invalidChatSourceReselectRequest
                ?.takeIf { it.sessionId == currentSessionId }
                ?.let { prepareInvalidChatSourceReplacement(catalog, it, System.currentTimeMillis()) }
                ?: catalog
        }
    }

    LaunchedEffect(destination, activeSessionId) {
        val sessionId = activeSessionId
        if (destination == AppDestination.WindowBranches && sessionId != null) {
            windowBranchUiState = runCatching {
                WindowBranchPresenter.present(hybridAppGraph.windowBranchPort.load(sessionId))
            }.getOrNull()
        }
    }

    val activeSessionSnapshot = remember(activeSessionId, sessionSettingsRefreshKey) {
        activeSessionId?.let(hybridAppGraph.frontend.newSessionPersistence::loadSessionSnapshot)
    }
    val chatReferenceQueryPort = remember(
        sessionRepository,
        messageRepository,
        sourceRepository,
        graphRepository,
        hybridAppGraph.frontend.newSessionPersistence
    ) {
        RepositoryChatReferenceQueryPort(
            sessionRepository = sessionRepository,
            messageRepository = messageRepository,
            sourceRepository = sourceRepository,
            graphRepository = graphRepository,
            sourceIdsForSession = { sessionId ->
                hybridAppGraph.frontend.newSessionPersistence
                    .loadSessionSnapshot(sessionId)
                    ?.sourceSelections
                    ?.toSet()
                    .orEmpty()
            },
            offline = { !context.hasNetworkConnection() }
        )
    }
    val availableChatSourceAttachments = remember(sessionSettingsSources) {
        sessionSettingsSources
            .filter { it.currentSessionReferenced && it.readState == com.reversetutor.feature.chat.SourceReadState.Ready }
            .map { source ->
                ChatDraftAttachment(
                    id = "source-${source.id}",
                    kind = ChatAttachmentKind.Source,
                    name = source.displayName,
                    sourceId = source.id,
                    readiness = ChatAttachmentReadiness.Ready
                )
            }
    }

    ReverseTutorScreenSurface {
        if (destination == AppDestination.Sessions) {
            SessionsRoute(
                sessionHomePort = hybridAppGraph.frontend.sessionHomePort,
                contentRepository = hybridAppGraph.online?.contentRepository,
                avatarVisible = appPreferences.globalAvatarVisible,
                challengeJoined = challengeRuntimeState.joined,
                challengeProgress = challengeProgress,
                challengeTotal = challengeTotal,
                onOpenSession = onOpenSession,
                onNewSession = onOpenNewSession,
                onOpenChallenge = onOpenChallenge,
                onOpenPublicContent = { content ->
                    if (content.canOpen) onOpenPublicArticle(content.slug)
                },
                onOpenWeekly = { onNavigateDestination(AppDestination.WeeklyDashboard) },
                showSpatialIndicator = false,
                onWorkspaceChromeObscuredChanged = { obscured ->
                    onWorkspaceChromeObscuredChanged(WorkspacePage.SessionHome, obscured)
                }
            )
            return@ReverseTutorScreenSurface
        }
        if (destination == AppDestination.NewSession) {
            Task2B1NewSessionRoute(
                createPort = hybridAppGraph.frontend.newSessionCreatePort,
                persistence = hybridAppGraph.frontend.newSessionPersistence,
                tagLibraryPersistence = hybridAppGraph.frontend.tagLibraryPersistence,
                onCreated = onSessionCreated,
                onBack = onCloseNewSession,
                initialPrefill = challengeSessionPrefill
            )
            return@ReverseTutorScreenSurface
        }
        if (destination == AppDestination.Challenge) {
            ChallengeRoute(
                joined = challengeRuntimeState.joined,
                progress = challengeProgress,
                total = challengeTotal,
                onBack = onOpenSessions,
                onJoin = onChallengeJoined,
                runtimeState = challengeRuntimeState,
                onRetry = onChallengeRetry,
                active = challengePageActive,
                onExitBoundaryChanged = onChallengeExitBoundaryChanged,
                entryGeneration = challengeEntryGeneration,
                restoreContext = challengeRestoreContext,
                onRestoreConsumed = onChallengeRestoreConsumed,
                onReturnContextChanged = onChallengeReturnContextChanged
            )
            return@ReverseTutorScreenSurface
        }
        if (destination == AppDestination.Chat && activeSessionId != null && activeSessionTitle != null) {
            ChatRoute(
                messageRepository = messageRepository,
                visibleTimelinePort = hybridAppGraph.visibleTimelinePort,
                chatGenerationRepository = chatGenerationRepository,
                backgroundGenerationRepository = backgroundGenerationRepository,
                backgroundTurnPreparationPort = hybridAppGraph.backgroundTurnPreparationPort,
                memoryRepository = memoryRepository,
                sourceRepository = sourceRepository,
                sourceUsagePort = chatSourceUsagePort,
                messageActionPort = chatMessageActionPort,
                messageDeletePort = chatMessageDeletePort,
                pendingDeletionStore = chatPendingDeletionStore,
                clipboardPort = chatClipboardPort,
                imageMediaPort = chatImageMediaPort,
                rememberedMessageStore = chatRememberedMessageStore,
                sessionId = activeSessionId,
                sessionTitle = activeSessionTitle,
                learnerRole = activeSessionLearnerRole,
                sessionSnapshot = activeSessionSnapshot,
                pendingAttachment = pendingChatAttachments.firstOrNull(),
                attachmentNotice = pendingChatAttachmentNotice,
                availableSourceAttachments = availableChatSourceAttachments,
                draftStore = chatDraftStore,
                attachmentOrderStore = chatAttachmentOrderStore,
                cameraPermissionState = cameraPermissionState,
                evidenceTargetMessageId = pendingChatEvidenceTarget,
                onPickImage = {
                    chatImageLauncher.launch(arrayOf("image/*"))
                },
                onPickLocalSource = {
                    chatSourcePickerActive = true
                    sourceFileLauncher.launch(
                        arrayOf(
                            "text/plain", "text/markdown", "text/html", "application/pdf",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                            "application/epub+zip", "image/*", "*/*"
                        )
                    )
                },
                onTakePhoto = { chatCameraLauncher.launch(null) },
                onRequestCameraPermission = {
                    chatPermissionPreferences.edit().putBoolean("camera-requested", true).apply()
                    chatCameraPermissionLauncher.launch(Manifest.permission.CAMERA)
                },
                onOpenCameraSettings = {
                    context.startActivity(
                        Intent(
                            Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                            Uri.parse("package:${context.packageName}")
                        )
                    )
                },
                onRetryAttachment = { attachment ->
                    val uri = attachment.uri?.let(Uri::parse)
                    if (uri != null) {
                        scope.launch {
                            acceptPlatformAttachment(
                                withContext(Dispatchers.IO) {
                                    context.readChatAttachmentInput(uri, attachment.id, attachment.kind)
                                }
                            )
                        }
                    } else {
                        pendingChatAttachments = pendingChatAttachments + attachment.copy(
                            readiness = ChatAttachmentReadiness.Failed("无法重试，请重新选择。", retryable = true)
                        )
                    }
                },
                onAttachmentConsumed = {
                    pendingChatAttachments = pendingChatAttachments.drop(1)
                },
                onAttachmentNoticeConsumed = {
                    pendingChatAttachmentNotice = null
                },
                onBackgroundGenerationQueued = { jobId ->
                    BackgroundGenerationWorker.enqueue(context, jobId)
                },
                onProviderGenerationFailed = { sourceMessageId ->
                    val diagnostic = GenerationDiagnosticPolicy.providerFailure()
                    scope.launch {
                        memoryRepository.logError(
                            input = ErrorLogInput(
                                title = diagnostic.title,
                                detail = diagnostic.detail,
                                sourceMessageId = sourceMessageId
                            ),
                            nowEpochMillis = System.currentTimeMillis(),
                            errorId = "diagnostic-provider-$sourceMessageId",
                            origin = ErrorLogOrigin.Generation,
                            code = diagnostic.code
                        )
                    }
                },
                onComposerFocusChanged = onComposerFocusChanged,
                webSearchEnabled = appPreferences.webSearchEnabled,
                onWebSearchChange = { enabled ->
                    scope.launch {
                        hybridAppGraph.appPreferencesRepository
                            .setWebSearchEnabled(enabled)
                    }
                },
                onOpenContextHub = onOpenContextHub,
                onOpenWindowBranches = {
                    onNavigateDestination(AppDestination.WindowBranches)
                },
                onOpenSearch = { onNavigateDestination(AppDestination.ChatReferences) },
                onOpenSessionSources = { onNavigateDestination(AppDestination.SessionSettingsSources) },
                onOpenSessionSource = { sourceId ->
                    if (sourceId == null) {
                        onNavigateDestination(AppDestination.ChatReferences)
                    } else {
                        pendingSourceEvidenceTarget = sourceId
                        onNavigateDestination(AppDestination.SessionSettingsSources)
                    }
                },
                onReselectInvalidSource = { request ->
                    if (request.sessionId == activeSessionId) {
                        val now = System.currentTimeMillis()
                        invalidChatSourceReselectRequest = request
                        sessionSettingsSources = prepareInvalidChatSourceReplacement(
                            sessionSettingsSources,
                            request,
                            now
                        )
                        pendingSourceEvidenceTarget = request.sourceId
                        sessionSettingsImportError = null
                        failedSessionSettingsReplaceTarget = null
                        sessionSettingsPickerActive = true
                        sessionSettingsReplaceTarget = request.sourceId
                        onNavigateDestination(AppDestination.SessionSettingsSources)
                        sourceFileLauncher.launch(
                            arrayOf("text/*", "application/pdf", "image/*", "*/*")
                        )
                    }
                },
                onOpenExternalLink = { url ->
                    runCatching {
                        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                    }
                },
                onOpenMediaSettings = {
                    context.startActivity(
                        Intent(
                            Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                            Uri.parse("package:${context.packageName}")
                        )
                    )
                },
                onPendingDeletionChanged = { pendingDeletionSweepGeneration += 1 },
                onOpenSources = onOpenSources,
                onExport = {},
                onOpenModelSettings = onOpenSettings,
                onOpenSessionSettings = {
                    onNavigateDestination(AppDestination.SessionSettings)
                },
                initialScrollPosition = chatScrollMemory.restore(activeSessionId),
                onScrollPositionChanged = { chatScrollMemory.capture(activeSessionId, it) },
                onBack = onOpenSessions
            )
            return@ReverseTutorScreenSurface
        }
        if (destination == AppDestination.WindowBranches && activeSessionId != null) {
            val state = windowBranchUiState
            if (state == null) {
                Text("分支信息暂不可用")
            } else {
                WindowBranchPanel(
                    state = state,
                    onAction = { action ->
                        when (action) {
                            WindowBranchAction.Back -> onOpenChat()
                            WindowBranchAction.RequestDelete -> {
                                if (state.deleteEnabled) {
                                    windowBranchUiState = state.copy(deleteConfirmationVisible = true)
                                }
                            }
                            WindowBranchAction.CancelDelete -> {
                                windowBranchUiState = state.copy(deleteConfirmationVisible = false)
                            }
                            is WindowBranchAction.OpenWindow -> scope.launch {
                                sessionRepository.getSession(action.windowId)
                                    ?.toSessionListItem(appPreferences.globalAvatarVisible)
                                    ?.let(onOpenSession)
                                    ?: run {
                                        windowBranchUiState = state.copy(notice = "目标分支不可用，请返回后重试。")
                                    }
                            }
                            WindowBranchAction.Create -> scope.launch {
                                when (val result = hybridAppGraph.windowBranchPort.createChild(
                                    com.reversetutor.feature.chat.CreateWindowBranchRequest(
                                        parentWindowId = state.current.id,
                                        title = "${state.current.title} · 分支"
                                    )
                                )) {
                                    is WindowBranchResult.Created -> {
                                        sessionRepository.getSession(result.child.id)
                                            ?.toSessionListItem(appPreferences.globalAvatarVisible)
                                            ?.let(onOpenSession)
                                            ?: run {
                                                windowBranchUiState = state.copy(notice = "创建分支失败，请重试。")
                                            }
                                    }
                                    else -> windowBranchUiState = state.copy(notice = "创建分支失败，请重试。")
                                }
                            }
                            is WindowBranchAction.SetHeartbeat -> scope.launch {
                                val result = hybridAppGraph.windowBranchPort.setHeartbeat(
                                    state.current.id,
                                    action.enabled
                                )
                                windowBranchUiState = if (result == WindowBranchResult.HeartbeatUpdated) {
                                    WindowBranchPresenter.present(
                                        hybridAppGraph.windowBranchPort.load(state.current.id)
                                    )
                                } else {
                                    state.copy(notice = "主动对话状态更新失败，请重试。")
                                }
                            }
                            WindowBranchAction.ConfirmDelete -> scope.launch {
                                val result = hybridAppGraph.windowBranchPort.deleteChild(state.current.id)
                                if (result is WindowBranchResult.Deleted) {
                                    sessionRepository.getSession(result.parentWindowId)
                                        ?.toSessionListItem(appPreferences.globalAvatarVisible)
                                        ?.let(onOpenSession)
                                } else {
                                    windowBranchUiState = state.copy(
                                        deleteConfirmationVisible = false,
                                        notice = "删除能力暂不可用"
                                    )
                                }
                            }
                        }
                    }
                )
            }
            return@ReverseTutorScreenSurface
        }
        if (destination == AppDestination.ChatReferences && activeSessionId != null) {
            ChatReferenceQueryRoute(
                sessionId = activeSessionId,
                queryPort = chatReferenceQueryPort,
                initialState = chatReferenceQueryState,
                onStateChanged = { chatReferenceQueryState = it },
                onNavigate = { request ->
                    scope.launch {
                        when (val highlight = request.highlight) {
                            is ChatQueryHighlight.Message -> {
                                pendingChatEvidenceTarget = highlight.messageId
                                if (highlight.sessionId != activeSessionId) {
                                    sessionRepository.getSession(highlight.sessionId)
                                        ?.toSessionListItem(appPreferences.globalAvatarVisible)
                                        ?.let(onOpenSession)
                                } else {
                                    onOpenChat()
                                }
                            }
                            is ChatQueryHighlight.GraphNode -> {
                                pendingGraphEvidenceTarget = highlight.nodeId
                                if (highlight.sessionId != activeSessionId) {
                                    sessionRepository.getSession(highlight.sessionId)
                                        ?.toSessionListItem(appPreferences.globalAvatarVisible)
                                        ?.let(onOpenSession)
                                }
                                onNavigateDestination(AppDestination.SessionSettingsGraph)
                            }
                            is ChatQueryHighlight.Source -> {
                                pendingSourceEvidenceTarget = highlight.sourceId
                                val targetSessionId = highlight.sessionId
                                if (targetSessionId != null && targetSessionId != activeSessionId) {
                                    sessionRepository.getSession(targetSessionId)
                                        ?.toSessionListItem(appPreferences.globalAvatarVisible)
                                        ?.let(onOpenSession)
                                }
                                onNavigateDestination(AppDestination.SessionSettingsSources)
                            }
                        }
                    }
                },
                onBack = onOpenChat
            )
            return@ReverseTutorScreenSurface
        }
        if (destination == AppDestination.WeeklyDashboard) {
            LearningOverviewPanel(
                state = learningOverviewState,
                onRefresh = {
                    onLearningOverviewAction(LearningOverviewUiAction.Refresh)
                },
                onChangeScope = { scope ->
                    onLearningOverviewAction(LearningOverviewUiAction.ChangeScope(scope))
                },
                onOpenWeekly = {},
                onOpenWeakPoint = { onOpenGlobalGraph() },
                currentSessionId = null
            )
            return@ReverseTutorScreenSurface
        }
        if (destination == AppDestination.Community) {
            CommunityRoute(onBack = onOpenGlobalGraph)
            return@ReverseTutorScreenSurface
        }
        if (destination == AppDestination.ContextHub) {
            ContextHubRoute(
                memoryRepository = memoryRepository,
                graphRepository = graphRepository,
                sessionId = activeSessionId,
                sessionTitle = activeSessionTitle,
                onOpenChat = onOpenChat,
                onOpenSources = onOpenSources,
                onOpenChatEvidence = { messageId ->
                    pendingChatEvidenceTarget = messageId
                    onOpenChat()
                },
                onOpenSourceEvidence = { sourceId ->
                    pendingSourceEvidenceTarget = sourceId
                    onNavigateDestination(AppDestination.SessionSettingsSources)
                },
                onOpenSettings = onOpenSettings,
                onOpenGlobalGraph = onOpenGlobalGraph
            )
            return@ReverseTutorScreenSurface
        }
        if (destination == AppDestination.SessionSettingsGraph) {
            SessionWorldTreeRoute(
                graphRepository = graphRepository,
                sessionId = activeSessionId,
                sessionTitle = activeSessionTitle ?: "当前会话",
                onBack = onOpenChat,
                highlightedNodeId = pendingGraphEvidenceTarget,
                onGraphInteractionChanged = onGraphInteractionChanged
            )
            return@ReverseTutorScreenSurface
        }
        if (destination == AppDestination.SessionSettings ||
            destination == AppDestination.SessionSettingsSources ||
            destination == AppDestination.SessionSettingsLibrary ||
            destination == AppDestination.SessionSettingsPersona ||
            destination == AppDestination.SessionSettingsPersonalization
        ) {
            SessionSettingsRoute(
                destination = destination,
                sessionId = activeSessionId,
                sessionTitle = activeSessionTitle ?: "宏观经济学基础",
                sessionHomePort = hybridAppGraph.frontend.sessionHomePort,
                newSessionPersistence = hybridAppGraph.frontend.newSessionPersistence,
                tagLibraryPersistence = hybridAppGraph.frontend.tagLibraryPersistence,
                sessionSettingsStore = sessionSettingsStore,
                initialSources = sessionSettingsSources,
                highlightedSourceId = pendingSourceEvidenceTarget,
                pickedSource = pickedSessionSource,
                onPickedSourceConsumed = {
                    pickedSessionSource = null
                    invalidChatSourceReselectRequest = null
                },
                onSourcesChanged = { sessionSettingsRefreshKey += 1 },
                onSessionTitleChanged = onActiveSessionTitleChanged,
                onSessionLearnerRoleChanged = onActiveSessionLearnerRoleChanged,
                onSessionDeleted = onActiveSessionDeleted,
                onSelectDestination = onNavigateDestination,
                onOpenBrain = { onNavigateDestination(AppDestination.GlobalGraph) },
                onBack = onOpenChat,
                onPickSource = {
                    sourceFileLauncher.launch(
                        arrayOf("text/*", "application/pdf", "image/*", "*/*")
                    )
                },
                onPickManagedSource = { replacingSourceId ->
                    sessionSettingsImportError = null
                    failedSessionSettingsReplaceTarget = null
                    sessionSettingsPickerActive = true
                    sessionSettingsReplaceTarget = replacingSourceId
                    sourceFileLauncher.launch(
                        arrayOf("text/*", "application/pdf", "image/*", "*/*")
                    )
                },
                externalImportError = sessionSettingsImportError,
                onRetryImport = {
                    sessionSettingsImportError = null
                    sessionSettingsPickerActive = true
                    sessionSettingsReplaceTarget = failedSessionSettingsReplaceTarget
                    sourceFileLauncher.launch(arrayOf("text/*", "application/pdf", "image/*", "*/*"))
                }
            )
            return@ReverseTutorScreenSurface
        }
        if (destination == AppDestination.GlobalGraph) {
            GlobalGraphRoute(
                graphRepository = graphRepository,
                memoryRepository = memoryRepository,
                onOpenGraphChatEvidence = { messageId ->
                    pendingChatEvidenceTarget = messageId
                    onOpenChat()
                },
                onOpenGraphSourceEvidence = { sourceId ->
                    pendingSourceEvidenceTarget = sourceId
                    onOpenSources()
                },
                onOpenSettings = onOpenSettings,
                onBack = onOpenSessions,
                canvasModeActive = graphCanvasModeActive,
                onCanvasModeChange = onGraphCanvasModeChanged,
                onGraphInteractionChanged = onGraphInteractionChanged,
                onWorkspaceChromeObscuredChanged = { obscured ->
                    onWorkspaceChromeObscuredChanged(WorkspacePage.GlobalGraph, obscured)
                },
                onPageLocalActionSurfaceChanged = { active, dismiss ->
                    onPageLocalActionSurfaceChanged(
                        WorkspacePage.GlobalGraph,
                        active,
                        dismiss
                    )
                }
            )
            return@ReverseTutorScreenSurface
        }
        if (destination == AppDestination.Sources) {
            SourcesRoute(
                sourceRepository = sourceRepository,
                pendingImport = pendingSourceImport,
                onSourceIndexed = { indexSourceAsync(it) },
                highlightedSourceId = pendingSourceEvidenceTarget,
                onPickSource = {
                    sourceFileLauncher.launch(
                        arrayOf(
                            "text/plain",
                            "text/markdown",
                            "text/html",
                            "application/pdf",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                            "application/epub+zip",
                            "image/*",
                            "*/*"
                        )
                    )
                }
            )
            return@ReverseTutorScreenSurface
        }
        if (destination == AppDestination.GlobalSearch) {
            FormalGlobalSearchRoute(
                searchRepository = hybridAppGraph.globalSearchRepository,
                onBack = onOpenSessions,
                onTargetSelected = onOpenSearchTarget
            )
            return@ReverseTutorScreenSurface
        }
        if (destination == AppDestination.PublicArticle) {
            FormalPublicArticleRoute(
                contentRepository = hybridAppGraph.online?.contentRepository,
                slug = activeArticleSlug,
                onBack = onOpenSessions
            )
            return@ReverseTutorScreenSurface
        }
        if (destination == AppDestination.Settings) {
            val notificationPermissionLauncher = rememberLauncherForActivityResult(
                contract = ActivityResultContracts.RequestPermission()
            ) { granted ->
                scope.launch {
                    hybridAppGraph.appPreferencesRepository
                        .setBackgroundGenerationNotificationEnabled(granted)
                }
            }
            val postNotificationsGranted = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
                ContextCompat.checkSelfPermission(
                    context,
                    Manifest.permission.POST_NOTIFICATIONS
                ) == PackageManager.PERMISSION_GRANTED
            val notificationsEnabled = postNotificationsGranted && NotificationManagerCompat
                .from(context).areNotificationsEnabled()
            FormalSettingsScreen(
                llmProfileState = llmProfileState,
                onBack = onOpenSessions,
                onOpenLlmConfiguration = {
                    onNavigateDestination(AppDestination.LlmConfiguration)
                },
                onOpenStorage = onOpenAbout,
                onOpenImportExport = onOpenImportExport,
                onOpenAbout = onOpenAbout,
                challengeReminderEnabled = appPreferences.challengeReminderEnabled,
                hapticFeedbackEnabled = appPreferences.hapticFeedbackEnabled,
                onChallengeReminderChanged = { enabled ->
                    scope.launch {
                        hybridAppGraph.appPreferencesRepository
                            .setChallengeReminderEnabled(enabled)
                    }
                },
                onHapticFeedbackChanged = { enabled ->
                    scope.launch {
                        hybridAppGraph.appPreferencesRepository
                            .setHapticFeedbackEnabled(enabled)
                    }
                },
                backgroundGenerationNotificationEnabled = appPreferences.backgroundGenerationNotificationEnabled,
                notificationPermissionGranted = notificationsEnabled,
                onBackgroundGenerationNotificationChanged = { enabled ->
                    if (enabled) {
                        when {
                            Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU -> {
                                scope.launch {
                                    hybridAppGraph.appPreferencesRepository
                                        .setBackgroundGenerationNotificationEnabled(true)
                                }
                            }
                            postNotificationsGranted -> {
                                scope.launch {
                                    hybridAppGraph.appPreferencesRepository
                                        .setBackgroundGenerationNotificationEnabled(true)
                                }
                            }
                            (context as? Activity)?.shouldShowRequestPermissionRationale(
                                Manifest.permission.POST_NOTIFICATIONS
                            ) == true -> Unit
                            else -> notificationPermissionLauncher.launch(
                                Manifest.permission.POST_NOTIFICATIONS
                            )
                        }
                    } else {
                        scope.launch {
                            hybridAppGraph.appPreferencesRepository
                                .setBackgroundGenerationNotificationEnabled(false)
                        }
                    }
                },
                onOpenNotificationSettings = {
                    val intent = Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).apply {
                        putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)
                    }
                    context.startActivity(intent)
                }
            )
            return@ReverseTutorScreenSurface
        }
        if (destination == AppDestination.LlmConfiguration) {
            FormalLlmConfigurationScreen(
                state = llmProfileState,
                onBack = { onNavigateDestination(AppDestination.Settings) },
                onActivateProfile = { profileId ->
                    scope.launch {
                        llmProfileRepository.activateProfile(profileId, System.currentTimeMillis())
                        llmProfiles = llmProfileRepository.listProfiles()
                    }
                },
                onSaveProfile = { input ->
                    scope.launch {
                        llmProfileRepository.saveProfile(input, System.currentTimeMillis())
                        llmProfiles = llmProfileRepository.listProfiles()
                    }
                },
                onTestProfile = {}
            )
            return@ReverseTutorScreenSurface
        }
        if (destination == AppDestination.About) {
            FormalDiagnosticsRoute(
                hybridAppGraph = hybridAppGraph,
                onBack = { onNavigateDestination(AppDestination.Settings) }
            )
            return@ReverseTutorScreenSurface
        }
        if (destination == AppDestination.ImportExport) {
            FormalImportExportRoute(
                hybridAppGraph = hybridAppGraph,
                onBack = { onNavigateDestination(AppDestination.Settings) },
                initialImportText = initialImportText,
                initialImportFileName = initialImportFileName
            )
            return@ReverseTutorScreenSurface
        }
        if (destination == AppDestination.TokenUsage) {
            FormalTokenRoute(
                hybridAppGraph = hybridAppGraph,
                onBack = { onNavigateDestination(AppDestination.Settings) },
                onOpenSession = { sessionId ->
                    scope.launch {
                        sessionRepository.getSession(sessionId)?.toSessionListItem(appPreferences.globalAvatarVisible)?.let(onOpenSession)
                    }
                }
            )
            return@ReverseTutorScreenSurface
        }
        if (destination == AppDestination.Update) {
            FormalUpdateRoute(
                hybridAppGraph = hybridAppGraph,
                onBack = { onNavigateDestination(AppDestination.Settings) }
            )
            return@ReverseTutorScreenSurface
        }
        val spacing = ReverseTutorDesign.spacing
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(spacing.space6),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.Start
        ) {
            Text(
                text = "Reverse Tutor",
                color = MaterialTheme.colorScheme.primary,
                style = MaterialTheme.typography.displaySmall
            )
            Spacer(modifier = Modifier.height(spacing.space2))
            Text(
                text = if (destination == AppDestination.Chat && activeSessionTitle != null) {
                    activeSessionTitle
                } else {
                    destination.title
                },
                color = MaterialTheme.colorScheme.onSurface,
                style = MaterialTheme.typography.titleLarge
            )
            Spacer(modifier = Modifier.height(spacing.space3))
            ReverseTutorStatusStrip(
                title = "预览占位",
                message = "当前页面仍保留在 native 壳内，后续会继续补齐对应界面。",
                tone = ReverseTutorStatusTone.Info
            )
            Spacer(modifier = Modifier.height(spacing.space6))
            PreviewActions(
                destination = destination,
                onOpenChat = onOpenChat,
                onOpenContextHub = onOpenContextHub,
                onOpenSources = onOpenSources,
                onOpenSettings = onOpenSettings,
                onOpenImportExport = onOpenImportExport,
                onOpenAbout = onOpenAbout
            )
        }
    }
}

private fun Context.tryPersistReadPermission(uri: android.net.Uri) {
    runCatching {
        contentResolver.takePersistableUriPermission(
            uri,
            Intent.FLAG_GRANT_READ_URI_PERMISSION
        )
    }
}

@Composable
private fun FirstLaunchImportPromptDialog(
    state: FirstLaunchImportPromptUiState,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit
) {
    ReverseTutorConfirmationDialog(
        title = state.title,
        body = state.body,
        confirmLabel = state.confirmLabel,
        dismissLabel = state.dismissLabel,
        onConfirm = onConfirm,
        onDismiss = onDismiss,
        tone = ReverseTutorStatusTone.Info
    )
}

@Composable
@OptIn(ExperimentalLayoutApi::class)
private fun PreviewActions(
    destination: AppDestination,
    onOpenChat: () -> Unit,
    onOpenContextHub: () -> Unit,
    onOpenSources: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenImportExport: () -> Unit,
    onOpenAbout: () -> Unit
) {
    val spacing = ReverseTutorDesign.spacing

    FlowRow(
        horizontalArrangement = Arrangement.spacedBy(spacing.space2),
        verticalArrangement = Arrangement.spacedBy(spacing.space2)
    ) {
        if (destination != AppDestination.Chat) {
            ReverseTutorActionButton(label = "打开聊天", onClick = onOpenChat)
        }
        if (destination == AppDestination.Chat) {
            ReverseTutorActionButton(label = "打开脉络", onClick = onOpenContextHub)
        }
        if (destination != AppDestination.Sources) {
            ReverseTutorActionButton(
                label = "资料",
                onClick = onOpenSources,
                tone = ReverseTutorActionTone.Quiet
            )
        }
        if (destination != AppDestination.Settings) {
            ReverseTutorActionButton(
                label = "设置",
                onClick = onOpenSettings,
                tone = ReverseTutorActionTone.Quiet
            )
        }
        if (destination != AppDestination.ImportExport) {
            ReverseTutorActionButton(
                label = "导入与导出",
                onClick = onOpenImportExport,
                tone = ReverseTutorActionTone.Quiet
            )
        }
        if (destination != AppDestination.About) {
            ReverseTutorActionButton(
                label = "诊断",
                onClick = onOpenAbout,
                tone = ReverseTutorActionTone.Quiet
            )
        }
    }
}

@Composable
private fun StatusDialog(
    destination: AppDestination,
    onDismiss: () -> Unit
) {
    ReverseTutorConfirmationDialog(
        title = "预览状态",
        body = "当前页面：${destination.title}",
        confirmLabel = "关闭",
        dismissLabel = "返回",
        onConfirm = onDismiss,
        onDismiss = onDismiss,
        tone = ReverseTutorStatusTone.Info
    )
}

private fun Context.hasNetworkConnection(): Boolean {
    val manager = getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager ?: return false
    val network = manager.activeNetwork ?: return false
    val capabilities = manager.getNetworkCapabilities(network) ?: return false
    return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
        capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
}
