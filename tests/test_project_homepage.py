from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_includes_qq_group_entry_and_asset():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    qq_asset = ROOT / "docs" / "assets" / "qq-group.jpg"

    assert "欢迎入qq群反馈给我更新动力" in readme
    assert "QQ 群：<strong>897804938</strong>" in readme
    assert "docs/assets/qq-group.jpg" in readme
    assert readme.index("## 当前状态") < readme.index("## 加入交流群")
    assert qq_asset.exists()
    assert qq_asset.stat().st_size > 50_000


def test_mobile_settings_footer_includes_qq_group_number():
    html = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")

    assert "欢迎入qq群反馈给我更新动力" in html
    assert "QQ群：897804938" in html
    assert "Reverse Tutor v0.17.6 · 移动 PWA" in html


def test_readme_showcase_text_uses_explicit_alignment():
    svg = (ROOT / "docs" / "assets" / "readme-showcase.svg").read_text(encoding="utf-8")

    assert 'text-anchor="middle"' in svg
    assert 'dominant-baseline="middle"' in svg
    assert '今天你想达成什么目标？' in svg
    assert '多协议 LLM' in svg
    assert 'viewBox="70 55 1060 548"' in svg
    assert 'OpenAI 与 Anthropic 可选' in svg
    assert '引用与回档' in svg
    assert '后台横幅通知与应用更新' in svg
    assert 'x="844" y="464"' in svg
    assert 'x="762" y="390" width="290"' in svg


def test_release_docs_summarize_current_major_changes():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    latest = (ROOT / "static" / "app" / "latest.json").read_text(encoding="utf-8")

    for text in (readme, changelog, latest):
        assert "v0.17.6" in text or "0.17.6" in text
        assert "Reverse Tutor" in text
        assert "Reverse-Tutor-v0.17.6.apk" in text
        assert "体验额度" in text
        assert "/api/trial" in text
        assert "反转家教" in text
