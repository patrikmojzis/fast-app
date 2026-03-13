import asyncio
import importlib
import json

import pytest


def _load_localization(tmp_path, translations):
    lang_dir = tmp_path / "lang"
    lang_dir.mkdir()
    for locale, payload in translations.items():
        (lang_dir / f"{locale}.json").write_text(json.dumps(payload))

    import fast_app.core.localization as localization
    localization.set_locale_path(str(lang_dir))
    importlib.reload(localization)
    localization.set_locale_path(str(lang_dir))  # Reset after reload
    localization.clear_cache()
    localization.set_locale("en")
    return localization


def test_localization(tmp_path):
    localization = _load_localization(tmp_path, {"en": {"greeting": "Hello {name}"}})

    __ = localization.__
    set_locale = localization.set_locale

    assert __("greeting", {"name": "Bob"}) == "Hello Bob"
    set_locale("fr")
    assert __("greeting", {"name": "Ana"}) == "Hello Ana"
    assert __("missing", default="fallback") == "fallback"


def test_use_locale_restores_previous_locale(tmp_path):
    localization = _load_localization(
        tmp_path,
        {
            "en": {"title": "Hello"},
            "sk": {"title": "Ahoj"},
        },
    )

    assert localization.get_locale() == "en"

    with pytest.raises(RuntimeError):
        with localization.use_locale("sk"):
            assert localization.get_locale() == "sk"
            assert localization.__("title") == "Ahoj"
            raise RuntimeError("boom")

    assert localization.get_locale() == "en"
    assert localization.__("title") == "Hello"


@pytest.mark.asyncio
async def test_use_locale_isolated_between_parallel_tasks(tmp_path):
    localization = _load_localization(
        tmp_path,
        {
            "en": {},
            "sk": {"Welcome aboard": "Vitajte na palube"},
            "cs": {"Welcome aboard": "Vitejte na palube"},
        },
    )

    async def render(locale: str) -> tuple[str, str]:
        with localization.use_locale(locale):
            await asyncio.sleep(0)
            return localization.get_locale(), localization.__("Welcome aboard")

    sk_result, cs_result = await asyncio.gather(render("sk"), render("cs"))

    assert sk_result == ("sk", "Vitajte na palube")
    assert cs_result == ("cs", "Vitejte na palube")
    assert localization.get_locale() == "en"
