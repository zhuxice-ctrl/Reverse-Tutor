package com.reversetutor.core.data

import android.content.Context
import androidx.room.Room
import androidx.datastore.preferences.preferencesDataStore
import com.reversetutor.core.data.graph.GraphRepository
import com.reversetutor.core.data.background.BackgroundGenerationRepository
import com.reversetutor.core.data.background.GenerationPartialStore
import com.reversetutor.core.data.learning.LearningRepositoryImpl
import com.reversetutor.core.data.learning.WidgetLayoutRepositoryImpl
import com.reversetutor.core.data.llm.AndroidKeystoreSecretStore
import com.reversetutor.core.data.llm.AndroidImagePayloadResolver
import com.reversetutor.core.data.llm.ChatGenerationRepository
import com.reversetutor.core.data.llm.LlmProfileRepository
import com.reversetutor.core.data.llm.SecretStore
import com.reversetutor.core.data.local.DatabaseSchema
import com.reversetutor.core.data.local.ReverseTutorDatabase
import com.reversetutor.core.data.migration.NativeExportRepository
import com.reversetutor.core.data.migration.NativeImportRepository
import com.reversetutor.core.data.migration.RoomNativeExportStore
import com.reversetutor.core.data.migration.RoomNativeImportStore
import com.reversetutor.core.data.memory.MemoryRepository
import com.reversetutor.core.data.message.MessageRepository
import com.reversetutor.core.data.preferences.AppPreferencesRepository
import com.reversetutor.core.data.model.ModelConnectionRepositoryImpl
import com.reversetutor.core.data.run.ConversationRunRepositoryImpl
import com.reversetutor.core.data.search.RoomGlobalSearchRepository
import com.reversetutor.core.data.session.SessionDeletionRepository
import com.reversetutor.core.data.session.SessionRepository
import com.reversetutor.core.data.sync.RoomSyncRepository
import com.reversetutor.core.data.sources.SourceRepository
import com.reversetutor.core.data.wipe.LocalDataWipeRepository
import com.reversetutor.core.data.wipe.RoomLocalDataWipeStore
import com.reversetutor.core.data.worldtree.RoomWorldTreeRepository
import com.reversetutor.core.llm.CompositeLlmGenerationRuntime
import com.reversetutor.core.llm.LlmGenerationRuntime
import com.reversetutor.core.llm.OpenAiCompatibleEmbeddingRuntime
import com.reversetutor.core.llm.LlmSecretResolver
import com.reversetutor.core.llm.UrlConnectionProviderHttpTransport

private val Context.appPreferencesDataStore by preferencesDataStore(
    name = "reverse_tutor_app_preferences"
)

object DataModule {
    const val databaseName = "reverse_tutor_native.db"
    @Volatile private var databaseInstance: ReverseTutorDatabase? = null
    private val generationPartialStore = GenerationPartialStore()

    fun appPreferencesRepository(context: Context): AppPreferencesRepository =
        AppPreferencesRepository(context.applicationContext.appPreferencesDataStore)

    fun database(context: Context): ReverseTutorDatabase =
        databaseInstance ?: synchronized(this) {
            databaseInstance ?: Room.databaseBuilder(
                context.applicationContext,
                ReverseTutorDatabase::class.java,
                databaseName
            ).addMigrations(*DatabaseSchema.migrations)
                .build()
                .also { databaseInstance = it }
        }

    fun sessionRepository(context: Context): SessionRepository {
        val database = database(context)
        return SessionRepository(
            spaceDao = database.spaceDao(),
            sessionDao = database.sessionDao(),
            sessionSettingsDao = database.sessionSettingsDao()
        )
    }

    fun messageRepository(context: Context): MessageRepository {
        val database = database(context)
        return MessageRepository(
            messageDao = database.messageDao(),
            messageAttachmentDao = database.messageAttachmentDao(),
            messageQuoteDao = database.messageQuoteDao()
        )
    }

    fun secretStore(context: Context): SecretStore =
        AndroidKeystoreSecretStore(context.applicationContext)

    fun llmProfileRepository(context: Context): LlmProfileRepository {
        val database = database(context)
        return LlmProfileRepository(
            llmProfileDao = database.llmProfileDao(),
            secretStore = secretStore(context)
        )
    }

    fun chatGenerationRepository(
        context: Context,
        runtime: LlmGenerationRuntime? = null,
        webSearchPreference: (suspend () -> Boolean)? = null,
        embeddingRuntime: OpenAiCompatibleEmbeddingRuntime? = null
    ): ChatGenerationRepository =
        ChatGenerationRepository(
            messageRepository = messageRepository(context),
            llmProfileRepository = llmProfileRepository(context),
            runtime = runtime ?: productionGenerationRuntime(context),
            modelConnectionRepository = modelConnectionRepository(context),
            webSearchPreference = webSearchPreference ?: { false },
            embeddingRuntime = embeddingRuntime
        )

    fun backgroundGenerationRepository(
        context: Context,
        runtime: LlmGenerationRuntime? = null
    ): BackgroundGenerationRepository {
        val appContext = context.applicationContext
        val database = database(appContext)
        return BackgroundGenerationRepository(
            backgroundJobDao = database.backgroundJobDao(),
            sessionDao = database.sessionDao(),
            messageRepository = messageRepository(appContext),
            llmProfileRepository = llmProfileRepository(appContext),
            runtime = runtime ?: productionGenerationRuntime(appContext),
            modelConnectionRepository = modelConnectionRepository(appContext),
            partialStore = generationPartialStore
        )
    }

    private fun productionGenerationRuntime(context: Context): LlmGenerationRuntime {
        val secretStore = secretStore(context.applicationContext)
        return CompositeLlmGenerationRuntime.production(
            transport = UrlConnectionProviderHttpTransport(),
            secretResolver = LlmSecretResolver(secretStore::get),
            imagePayloadResolver = AndroidImagePayloadResolver(context.applicationContext)
        )
    }

    /** NEWMP-V1-024: embeddings runtime for semantic source retrieval. */
    fun productionEmbeddingRuntime(context: Context): OpenAiCompatibleEmbeddingRuntime {
        val secretStore = secretStore(context.applicationContext)
        return OpenAiCompatibleEmbeddingRuntime(
            transport = UrlConnectionProviderHttpTransport(),
            secretResolver = LlmSecretResolver(secretStore::get)
        )
    }

    fun modelConnectionRepository(context: Context): ModelConnectionRepositoryImpl =
        ModelConnectionRepositoryImpl(database(context.applicationContext))

    fun conversationRunRepository(context: Context): ConversationRunRepositoryImpl =
        ConversationRunRepositoryImpl(database(context.applicationContext))

    fun learningRepository(context: Context): LearningRepositoryImpl =
        LearningRepositoryImpl(database(context.applicationContext))

    fun widgetLayoutRepository(context: Context): WidgetLayoutRepositoryImpl =
        WidgetLayoutRepositoryImpl(database(context.applicationContext))

    fun globalSearchRepository(context: Context): RoomGlobalSearchRepository =
        RoomGlobalSearchRepository(database(context.applicationContext))

    fun syncRepository(context: Context): RoomSyncRepository =
        RoomSyncRepository(database(context.applicationContext))

    fun sessionDeletionRepository(context: Context): SessionDeletionRepository =
        SessionDeletionRepository(database(context.applicationContext))

    fun localDataWipeRepository(context: Context): LocalDataWipeRepository {
        val appContext = context.applicationContext
        return LocalDataWipeRepository(
            store = RoomLocalDataWipeStore(database(appContext)),
            secretStore = secretStore(appContext),
            resetPreferences = {
                appPreferencesRepository(appContext).resetToDefaults()
            }
        )
    }

    fun nativeImportRepository(context: Context): NativeImportRepository =
        NativeImportRepository(
            store = RoomNativeImportStore(database(context.applicationContext))
        )

    fun nativeExportRepository(context: Context): NativeExportRepository =
        NativeExportRepository(
            store = RoomNativeExportStore(database(context.applicationContext))
        )

    fun sourceRepository(context: Context): SourceRepository =
        SourceRepository(
            sourceDao = database(context.applicationContext).sourceDao()
        )

    fun memoryRepository(context: Context): MemoryRepository =
        MemoryRepository(
            memoryDao = database(context.applicationContext).memoryDao()
        )

    fun graphRepository(context: Context): GraphRepository {
        val database = database(context.applicationContext)
        return GraphRepository(
            graphDao = database.graphDao(),
            sessionDao = database.sessionDao()
        )
    }

    fun worldTreeRepository(context: Context): RoomWorldTreeRepository =
        RoomWorldTreeRepository(database(context.applicationContext))
}
