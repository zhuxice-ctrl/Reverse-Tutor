from __future__ import annotations

from pathlib import Path
import json
import re


ROOT = Path(__file__).resolve().parents[1]


def test_update_check_has_timeout_cache_buster_and_fallback_feed():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "UPDATE_CHECK_TIMEOUT_MS" in html
    assert "fetchJsonWithTimeout" in html
    assert "AbortController" in html
    assert "cacheBustUrl" in html
    assert "GITHUB_LATEST_RELEASE_URL" in html
    assert "updateFeedCandidates" in html
    assert "api.github.com/repos/zhuxice-ctrl/Reverse-Tutor/releases/latest" in html


def test_frontend_update_version_matches_android_and_package_versions():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    package = json.loads((ROOT / "mobile" / "package.json").read_text(encoding="utf-8"))
    gradle = (ROOT / "mobile" / "android" / "app" / "build.gradle").read_text(encoding="utf-8")

    version_name = re.search(r'versionName "([^"]+)"', gradle).group(1)
    version_code = int(re.search(r"versionCode\s+(\d+)", gradle).group(1))

    assert package["version"] == version_name
    assert f"const APP_VERSION_NAME = '{version_name}';" in html
    assert f"const APP_VERSION_CODE = {version_code};" in html
    assert f"Reverse Tutor v{version_name}" in html
    sw = (ROOT / "static" / "app" / "sw.js").read_text(encoding="utf-8")
    assert f"rt-mobile-v{version_name}-{version_code}" in sw


def test_update_check_prefers_self_hosted_source_and_migrates_legacy_github_feed():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "LEGACY_UPDATE_FEED_URLS" in html
    assert "normalizeStoredUpdateFeedUrl" in html
    assert "ensureSelfHostedApkMirror" in html
    assert "https://dl.zeroxcore.tech/reverse-tutor/Reverse-Tutor-v${versionName}.apk" in html
    assert "默认使用自建高速更新源" in html
    assert "out.push({ label: '自建高速更新源', url: DEFAULT_UPDATE_FEED_URL })" in html


def test_manual_update_check_disables_button_until_finished():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "setUpdateChecking" in html
    assert "$('#update-check').disabled = checking" in html
    assert "await checkUpdate(false)" in html


def test_update_check_continues_to_fallback_when_primary_feed_is_stale():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "let freshestSeen = null" in html
    assert "freshestSeen = info" in html
    assert "continue;" in html
    assert "已检查所有更新源，当前为最新版本" in html
