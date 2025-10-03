## localization

Minimal i18n with context‑local current locale and graceful fallbacks.

### APIs
- **__(key, parameters=None, default=None, locale=None)**: translate dot key with optional params.
- **set_locale(locale)**, **get_locale()**
- **set_locale_path(path)**: directory containing `<locale>.json` (default: `<cwd>/lang`).
- **clear_cache()**

Plural helper: `trans_choice(key, count, parameters=None)` looks for `<key>_plural` when `count != 1`.

### Example
```python
from fast_app.core.localization import __, set_locale, set_locale_path

set_locale_path("./lang")
set_locale("en")
__('messages.greeting', {"name": "Alice"}, default="Hello {name}")
```
