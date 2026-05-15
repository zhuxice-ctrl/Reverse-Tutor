from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "mobile" / "android" / "app" / "src" / "main"
JAVA = ANDROID / "java" / "com" / "reversetutor" / "app"


def test_android_manifest_declares_background_llm_service_and_permissions():
    manifest = (ANDROID / "AndroidManifest.xml").read_text(encoding="utf-8")

    assert "android.permission.POST_NOTIFICATIONS" in manifest
    assert "android.permission.FOREGROUND_SERVICE" in manifest
    assert "android.permission.FOREGROUND_SERVICE_DATA_SYNC" in manifest
    assert 'android:name=".BackgroundLlmService"' in manifest
    assert 'android:foregroundServiceType="dataSync"' in manifest


def test_android_background_llm_plugin_sources_exist_and_are_registered():
    main = (JAVA / "MainActivity.java").read_text(encoding="utf-8")
    plugin = (JAVA / "BackgroundLlmPlugin.java").read_text(encoding="utf-8")
    service = (JAVA / "BackgroundLlmService.java").read_text(encoding="utf-8")

    assert "registerPlugin(BackgroundLlmPlugin.class)" in main
    assert '@CapacitorPlugin(' in plugin
    assert 'name = "BackgroundLlm"' in plugin
    assert "enqueueTurn" in plugin
    assert "getCompletedTurns" in plugin
    assert "clearCompletedTurn" in plugin
    assert "requestNotificationPermission" in plugin
    assert "@PermissionCallback" in plugin
    assert "requestPermissionForAlias" in plugin
    assert "startForeground" in service
    assert "HttpURLConnection" in service
    assert "rt-native-background-llm-completed" in service
    assert "extractJsonObject" in service
    assert "strictJsonSystem" in service
    assert "LLM did not return valid JSON after background retry" in service


def test_mobile_frontend_enqueues_and_imports_native_background_turns():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "NativeBackgroundLlm" in html
    assert "enqueueTurn" in html
    assert "importNativeBackgroundTurns" in html
    assert "requestNotificationPermission" in html
    assert "native_background_job_id" in html
