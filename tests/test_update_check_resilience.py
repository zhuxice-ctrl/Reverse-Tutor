from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_update_check_has_timeout_cache_buster_and_fallback_feed():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "UPDATE_CHECK_TIMEOUT_MS" in html
    assert "fetchJsonWithTimeout" in html
    assert "AbortController" in html
    assert "cacheBustUrl" in html
    assert "GITHUB_LATEST_RELEASE_URL" in html
    assert "updateFeedCandidates" in html
    assert "api.github.com/repos/zhuxice-ctrl/Back_Teacher/releases/latest" in html


def test_manual_update_check_disables_button_until_finished():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "setUpdateChecking" in html
    assert "$('#update-check').disabled = checking" in html
    assert "await checkUpdate(false)" in html
