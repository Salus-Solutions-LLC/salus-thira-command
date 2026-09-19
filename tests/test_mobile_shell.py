from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


def test_mobile_shell_assets_are_loaded_last():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'name="viewport"' in html
    assert '<link rel="stylesheet" href="/static/mobile-shell.css" />' in html
    assert '<script src="/static/mobile-shell.js"></script>' in html
    assert html.index("readability.css") < html.index("mobile-shell.css")
    assert html.index("app.js") < html.index("mobile-shell.js")


def test_mobile_shell_navigation_is_accessible_and_dismissible():
    script = (STATIC / "mobile-shell.js").read_text(encoding="utf-8")
    for contract in (
        'aria-controls',
        'aria-expanded',
        'aria-hidden',
        'aria-label',
        'event.key === "Escape"',
        'button[data-view]',
        'matchMedia',
    ):
        assert contract in script


def test_mobile_shell_enforces_phone_layout_and_touch_targets():
    css = (STATIC / "mobile-shell.css").read_text(encoding="utf-8")
    for contract in (
        "@media (max-width: 760px)",
        "transform: translateX(-105%)",
        "body.mobile-nav-open .sidebar",
        "min-height: 44px",
        "font-size: 16px",
        "overflow-x: auto",
        "env(safe-area-inset-top)",
        "100dvh",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert contract in css
