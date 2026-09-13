package com.reversetutor.feature.sources

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.reversetutor.core.data.sources.SourceImportInput
import com.reversetutor.core.data.sources.SourceImportResult
import com.reversetutor.core.data.sources.SourceRepository
import com.reversetutor.core.data.sources.SourceWithChunks
import kotlinx.coroutines.launch

@Composable
fun SourcesRoute(
    sourceRepository: SourceRepository,
    pendingImport: SourceImportInput?,
    highlightedSourceId: String? = null,
    onPickSource: () -> Unit,
    onSourceIndexed: (SourceImportResult) -> Unit = {},
    modifier: Modifier = Modifier
) {
    val scope = rememberCoroutineScope()
    var sources by remember { mutableStateOf(emptyList<SourceWithChunks>()) }
    var lastImport by remember { mutableStateOf<SourceImportResult?>(null) }
    var refreshKey by remember { mutableIntStateOf(0) }

    fun reload() {
        refreshKey += 1
    }

    LaunchedEffect(refreshKey) {
        sources = sourceRepository.listSourcesWithChunks()
    }

    LaunchedEffect(pendingImport?.requestId) {
        val import = pendingImport ?: return@LaunchedEffect
        val imported = sourceRepository.importSource(
            input = import,
            nowEpochMillis = System.currentTimeMillis()
        )
        lastImport = imported
        // NEWMP-V1-024: kick off background semantic indexing.
        onSourceIndexed(imported)
        reload()
    }

    SourcesScreen(
        state = SourcesUiState.from(sources = sources, lastImport = lastImport),
        highlightedSourceId = highlightedSourceId,
        onPickSource = onPickSource,
        onReprocess = { sourceId ->
            scope.launch {
                val reprocessed = sourceRepository.reprocessSource(
                    sourceId = sourceId,
                    nowEpochMillis = System.currentTimeMillis()
                )
                lastImport = reprocessed
                // NEWMP-V1-024: re-index embeddings for the fresh chunks.
                reprocessed?.let(onSourceIndexed)
                reload()
            }
        },
        modifier = modifier
    )
}

@Composable
@OptIn(ExperimentalLayoutApi::class)
fun SourcesScreen(
    state: SourcesUiState,
    highlightedSourceId: String? = null,
    onPickSource: () -> Unit,
    onReprocess: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.Top,
        horizontalAlignment = Alignment.Start
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "资料库",
                    color = MaterialTheme.colorScheme.primary,
                    style = MaterialTheme.typography.headlineMedium,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = state.summary,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium
                )
                if (!highlightedSourceId.isNullOrBlank()) {
                    Text(
                        text = "证据定位：$highlightedSourceId",
                        color = MaterialTheme.colorScheme.primary,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Medium
                    )
                }
            }
            Button(
                onClick = onPickSource,
                modifier = Modifier
                    .heightIn(min = 48.dp)
                    .testTag("sources-add")
            ) {
                Text("添加资料")
            }
        }
        Spacer(modifier = Modifier.height(16.dp))
        ParserStatusLegend()
        Spacer(modifier = Modifier.height(12.dp))
        val importStatus = state.importStatusLabel
        if (importStatus != null) {
            Spacer(modifier = Modifier.height(14.dp))
            ImportStatusPanel(status = importStatus, lines = state.importDetailLines)
        }
        Spacer(modifier = Modifier.height(18.dp))
        if (state.isEmpty) {
            EmptySources(onPickSource = onPickSource, title = state.emptyTitle)
        } else {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                state.items.forEach { item ->
                    SourceCard(
                        item = item,
                        highlighted = item.id == highlightedSourceId,
                        onReprocess = { onReprocess(item.id) }
                    )
                }
            }
        }
    }
}

@Composable
@OptIn(ExperimentalLayoutApi::class)
private fun ParserStatusLegend() {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = MaterialTheme.colorScheme.primaryContainer,
        contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
        shape = RoundedCornerShape(8.dp)
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Text(text = "解析状态", style = MaterialTheme.typography.titleMedium)
            Text(
                text = "TXT 和 Markdown 可本地解析，HTML 会做安全清洗后部分提取。PDF、Word、PPT、电子书和图片会就地抽取正文与插图文字，抽取不到的会保留为等待能力的资料，不会被隐藏。",
                style = MaterialTheme.typography.bodyMedium
            )
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                listOf("已解析", "部分解析", "等待能力", "暂不支持", "失败").forEach { label ->
                    Text(text = label, style = MaterialTheme.typography.labelMedium)
                }
            }
        }
    }
}

@Composable
private fun ImportStatusPanel(
    status: String,
    lines: List<String>
) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = MaterialTheme.colorScheme.surfaceVariant,
        contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
        shape = RoundedCornerShape(8.dp)
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Text(
                text = "最近导入：$status",
                color = MaterialTheme.colorScheme.onSurface,
                style = MaterialTheme.typography.titleMedium
            )
            lines.forEach { line ->
                Text(text = line, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
private fun EmptySources(
    title: String,
    onPickSource: () -> Unit
) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = MaterialTheme.colorScheme.surfaceVariant,
        contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
        shape = RoundedCornerShape(8.dp)
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text(
                text = title,
                color = MaterialTheme.colorScheme.onSurface,
                style = MaterialTheme.typography.titleMedium
            )
            Text(
                text = "选择 TXT、Markdown、HTML、PDF、DOCX、PPTX、EPUB、图片或其他文件。暂不支持的文件也会保留并显示状态。",
                style = MaterialTheme.typography.bodyMedium
            )
            TextButton(onClick = onPickSource, modifier = Modifier.heightIn(min = 48.dp)) {
                Text("选择文件")
            }
        }
    }
}

@Composable
@OptIn(ExperimentalLayoutApi::class)
private fun SourceCard(
    item: SourceCardUiItem,
    highlighted: Boolean,
    onReprocess: () -> Unit
) {
    val statusContainerColor = when (item.statusTone) {
        SourceStatusTone.Success -> MaterialTheme.colorScheme.secondaryContainer
        SourceStatusTone.Warning -> MaterialTheme.colorScheme.tertiaryContainer
        SourceStatusTone.Info -> MaterialTheme.colorScheme.primaryContainer
        SourceStatusTone.Disabled -> MaterialTheme.colorScheme.surface
        SourceStatusTone.Error -> MaterialTheme.colorScheme.errorContainer
    }
    val statusContentColor = when (item.statusTone) {
        SourceStatusTone.Success -> MaterialTheme.colorScheme.onSecondaryContainer
        SourceStatusTone.Warning -> MaterialTheme.colorScheme.onTertiaryContainer
        SourceStatusTone.Info -> MaterialTheme.colorScheme.onPrimaryContainer
        SourceStatusTone.Disabled -> MaterialTheme.colorScheme.onSurfaceVariant
        SourceStatusTone.Error -> MaterialTheme.colorScheme.onErrorContainer
    }
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("source-card-${item.id}")
            .semantics { selected = highlighted },
        color = if (highlighted) {
            MaterialTheme.colorScheme.primaryContainer
        } else {
            MaterialTheme.colorScheme.surfaceVariant
        },
        contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
        shape = RoundedCornerShape(8.dp)
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Top
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = item.title,
                        color = MaterialTheme.colorScheme.onSurface,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                    Text(text = item.typeLabel, style = MaterialTheme.typography.bodyMedium)
                }
                Surface(
                    color = statusContainerColor,
                    contentColor = statusContentColor,
                    shape = RoundedCornerShape(6.dp)
                ) {
                    Text(
                        text = item.statusLabel,
                        modifier = Modifier
                            .heightIn(min = 32.dp)
                            .testTag("source-status-${item.id}")
                            .padding(horizontal = 10.dp, vertical = 7.dp),
                        style = MaterialTheme.typography.labelMedium
                    )
                }
            }
            Text(text = item.impactMessage, style = MaterialTheme.typography.bodyMedium)
            Text(text = item.chunkCountLabel, style = MaterialTheme.typography.bodyMedium)
            if (item.snippets.isNotEmpty()) {
                Text(
                    text = "片段",
                    color = MaterialTheme.colorScheme.onSurface,
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold
                )
                item.snippets.forEach { snippet ->
                    Text(text = snippet, style = MaterialTheme.typography.bodyMedium)
                }
            } else {
                Text(
                    text = "尚无可引用片段。",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium
                )
            }
            Text(
                text = item.evidenceSummary,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodyMedium
            )
            if (item.recoveryEnabled && item.recoveryLabel != null) {
                TextButton(
                    onClick = onReprocess,
                    modifier = Modifier
                        .heightIn(min = 48.dp)
                        .testTag("source-action-${item.id}")
                ) {
                    Text(item.recoveryLabel)
                }
            } else {
                item.recoveryReason?.let { reason ->
                    Text(
                        text = reason,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            }
        }
    }
}
