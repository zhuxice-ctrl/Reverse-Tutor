from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mobile_llm_config_uses_native_preferences_for_long_term_storage():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "nativePreferences()" in html
    assert "saveLlmConfigNative" in html
    assert "loadLlmConfigNative" in html
    assert "Preferences.set" in html
    assert "Preferences.get" in html


def test_android_manifest_requests_notification_permission_only_for_background_llm():
    manifest = (ROOT / "mobile" / "android" / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")

    assert "android.permission.POST_NOTIFICATIONS" in manifest
    assert 'android:name=".BackgroundLlmService"' in manifest
