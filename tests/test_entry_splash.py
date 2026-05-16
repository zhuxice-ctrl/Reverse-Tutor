from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID_RES = ROOT / "mobile" / "android" / "app" / "src" / "main" / "res"


def test_mobile_web_has_branded_entry_animation_overlay():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert 'id="entry-splash"' in html
    assert "entry-splash-hide" in html
    assert "@keyframes entryPulse" in html
    assert "requestAnimationFrame" in html
    assert "document.body.classList.add('entry-ready')" in html


def test_android_launch_theme_uses_project_splash_assets():
    styles = (ANDROID_RES / "values" / "styles.xml").read_text(encoding="utf-8")

    assert 'name="AppTheme.NoActionBarLaunch"' in styles
    assert "@drawable/splash" in styles
    assert (ANDROID_RES / "drawable" / "splash.png").exists()
    assert (ANDROID_RES / "drawable-port-xxxhdpi" / "splash.png").exists()
    assert (ANDROID_RES / "drawable-land-xxxhdpi" / "splash.png").exists()
