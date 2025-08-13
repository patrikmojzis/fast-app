import json
import importlib
import pytest


def test_localization(tmp_path, monkeypatch):
    lang_dir = tmp_path / "lang"
    lang_dir.mkdir()
    (lang_dir / "en.json").write_text(json.dumps({"greeting": "Hello {name}"}))

    import fast_app.core.localization as localization
    localization.set_locale_path(str(lang_dir))
    importlib.reload(localization)

    clear_cache = localization.clear_cache
    __ = localization.__
    set_locale = localization.set_locale

    clear_cache()
    assert __("greeting", {"name": "Bob"}) == "Hello Bob"
    set_locale("fr")
    assert __("greeting", {"name": "Ana"}) == "Hello Ana"
    assert __("missing", default="fallback") == "fallback"
