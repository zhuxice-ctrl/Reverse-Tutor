from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID_RES = ROOT / "mobile" / "android" / "app" / "src" / "main" / "res"


def test_android_launcher_uses_intro_icon_without_adaptive_override():
    manifest = (ROOT / "mobile" / "android" / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")

    assert 'android:icon="@mipmap/ic_launcher"' in manifest
    assert 'android:roundIcon="@mipmap/ic_launcher"' in manifest
    assert not (ANDROID_RES / "mipmap-anydpi-v26" / "ic_launcher.xml").exists()
    assert not (ANDROID_RES / "mipmap-anydpi-v26" / "ic_launcher_round.xml").exists()
    assert not (ANDROID_RES / "drawable-v24" / "ic_launcher_foreground.xml").exists()
    assert not (ANDROID_RES / "drawable" / "ic_launcher_background.xml").exists()
    assert not (ANDROID_RES / "values" / "ic_launcher_background.xml").exists()


def test_android_launcher_round_icons_match_primary_icons():
    for density in ["mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"]:
        base = ANDROID_RES / f"mipmap-{density}" / "ic_launcher.png"
        round_icon = ANDROID_RES / f"mipmap-{density}" / "ic_launcher_round.png"
        assert base.exists()
        assert round_icon.exists()
        assert round_icon.read_bytes() == base.read_bytes()


def test_readme_and_pwa_use_same_intro_icon_asset():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    manifest = (ROOT / "static" / "app" / "manifest.json").read_text(encoding="utf-8")
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "static/app/icon-192.png" in readme
    assert "./icon-192.png" in manifest
    assert '<link rel="apple-touch-icon" href="./icon-192.png">' in html
