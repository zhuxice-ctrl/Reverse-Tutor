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


def test_android_launch_theme_uses_plain_background_before_web_splash():
    styles = (ANDROID_RES / "values" / "styles.xml").read_text(encoding="utf-8")
    colors = (ANDROID_RES / "values" / "colors.xml").read_text(encoding="utf-8")
    layout = (ANDROID_RES / "layout" / "activity_main.xml").read_text(encoding="utf-8")

    assert 'name="AppTheme.NoActionBarLaunch"' in styles
    launch_theme = styles.split('name="AppTheme.NoActionBarLaunch"', 1)[1]
    assert "@drawable/splash" not in launch_theme
    assert "@color/launch_background" in launch_theme
    assert "android:windowBackground" in launch_theme
    assert "android:background" in launch_theme
    assert "postSplashScreenTheme" in launch_theme
    assert 'name="launch_background">#c9c0b3' in colors
    assert 'android:background="@color/launch_background"' in layout


def test_mobile_web_applies_saved_theme_before_first_paint():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "document.documentElement.classList.toggle('theme-warm'" in html
    assert ":root.theme-warm" in html
