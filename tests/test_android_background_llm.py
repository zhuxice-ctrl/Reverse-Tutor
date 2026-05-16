from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "mobile" / "android" / "app" / "src" / "main"
JAVA = ANDROID / "java" / "com" / "reversetutor" / "app"


def test_android_manifest_declares_background_llm_service_and_permissions():
    manifest = (ANDROID / "AndroidManifest.xml").read_text(encoding="utf-8")

    assert "android.permission.POST_NOTIFICATIONS" in manifest
    assert "android.permission.REQUEST_INSTALL_PACKAGES" in manifest
    assert "android.permission.FOREGROUND_SERVICE" in manifest
    assert "android.permission.FOREGROUND_SERVICE_DATA_SYNC" in manifest
    assert 'android:name=".BackgroundLlmService"' in manifest
    assert 'android:name=".ApkUpdateService"' in manifest
    assert 'android:foregroundServiceType="dataSync"' in manifest


def test_android_background_llm_plugin_sources_exist_and_are_registered():
    main = (JAVA / "MainActivity.java").read_text(encoding="utf-8")
    plugin = (JAVA / "BackgroundLlmPlugin.java").read_text(encoding="utf-8")
    service = (JAVA / "BackgroundLlmService.java").read_text(encoding="utf-8")
    apk_service = (JAVA / "ApkUpdateService.java").read_text(encoding="utf-8")

    assert "registerPlugin(BackgroundLlmPlugin.class)" in main
    assert '@CapacitorPlugin(' in plugin
    assert 'name = "BackgroundLlm"' in plugin
    assert "enqueueTurn" in plugin
    assert "getCompletedTurns" in plugin
    assert "clearCompletedTurn" in plugin
    assert "requestNotificationPermission" in plugin
    assert "downloadAndInstallApk" in plugin
    assert "ApkUpdateService.class" in plugin
    assert "ApkUpdateService.EXTRA_URLS_JSON" in plugin
    assert 'ret.put("background", true)' in plugin
    assert 'ret.put("queued", true)' in plugin
    assert "ACTION_MANAGE_UNKNOWN_APP_SOURCES" in plugin
    assert "@PermissionCallback" in plugin
    assert "requestPermissionForAlias" in plugin
    assert "public class ApkUpdateService extends Service" in apk_service
    assert "startForeground" in apk_service
    assert "START_REDELIVER_INTENT" in apk_service
    assert "HttpURLConnection" in apk_service
    assert "setProgress" in apk_service
    assert "downloadWithMirrors" in apk_service
    assert "FileProvider.getUriForFile" in apk_service
    assert "application/vnd.android.package-archive" in apk_service
    assert "Intent.FLAG_GRANT_READ_URI_PERMISSION" in apk_service
    assert "NotificationCompat.CATEGORY_PROGRESS" in apk_service
    assert "tryOpenInstaller" in apk_service
    assert "startForeground" in service
    assert "HttpURLConnection" in service
    assert "rt-native-background-llm-completed" in service
    assert "extractJsonObject" in service
    assert "strictJsonSystem" in service
    assert "LLM did not return valid JSON after background retry" in service
    assert "fallbackReplyJson" in service
    assert "extractReplyText" in service
    assert "background_fallback" in service
    assert "postAnthropic" in service
    assert "postWithRetry" in service
    assert "isTransientNetworkError" in service
    assert "SocketException" in service
    assert "SocketTimeoutException" in service
    assert "buildAnthropicPayload" in service
    assert "contentFromAnthropicResponse" in service
    assert '"/v1/messages"' in service
    assert '"x-api-key"' in service
    assert '"anthropic-version"' in service
    assert 'item.put("turn_id"' in service
    assert 'item.put("reply_to_message_id"' in service
    assert "START_REDELIVER_INTENT" in service
    assert "PENDING_KEY" in plugin
    assert "storePending" in plugin
    assert "clearPending" in service
    assert "readPending" in service
    assert "replyPreviewFromRawContent" in service
    assert 'root.optString("reply", "")' in service
    assert "String replyPreview = replyPreviewFromRawContent(rawContent)" in service
    assert "NotificationCompat.BigTextStyle().bigText(text)" in service
    assert "RESULT_CHANNEL_ID" in service
    assert "NotificationManager.IMPORTANCE_HIGH" in service
    assert "NotificationCompat.PRIORITY_HIGH" in service
    assert "打开应用查看后台生成的回复。" not in service


def test_mobile_frontend_enqueues_and_imports_native_background_turns():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "NativeBackgroundLlm" in html
    assert "enqueueTurn" in html
    assert "importNativeBackgroundTurns" in html
    assert "requestNotificationPermission" in html
    assert "native_background_job_id" in html
    assert "cleanEvaluation" in html
    assert "native background llm failed" in html
    assert "await DB.put('messages', pending)" in html
    assert "await add_message(job.sid, 'assistant', `后台回复失败" not in html


def test_mobile_update_download_opens_native_installer_when_available():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "downloadAndInstallApk" in html
    assert "downloadAndInstallApkNative" in html
    assert "nativeInstaller" in html
    assert "NativeBackgroundLlm.requestNotificationPermission()" in html
    assert "urls: downloadUrls" in html
    assert "nativeInstaller.queued || nativeInstaller.background" in html
    assert "已转入后台" in html
    assert "后台下载新版" in html
    assert "已打开安装页面" in html
    assert "APK 已下载，请在通知栏或文件管理器中打开安装" not in html
