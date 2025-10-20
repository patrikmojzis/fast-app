## localization

Drop translations into JSON files and reach for them anywhere in my app with a tiny helper. The locale lives in context, so each request transparently picks up its own language without extra plumbing.

### Prepare translations
- Create a `lang/` directory (the default lookup path) next to my entry point or point the helper elsewhere with `set_locale_path()` or `LOCALE_PATH`.
- Add `<locale>.json` files such as `lang/en.json`. Dot keys map to nested dictionaries:

  ```json
  {
    "messages": {
      "welcome": "Welcome back, {name}!"
    },
    "cart_count": "You have {count} item",
    "cart_count_plural": "You have {count} items"
  }
  ```

### Pick the locale
- `LOCALE_DEFAULT` decides the starting locale (defaults to `en`). Override it in `.env` or at runtime with `set_locale("cs")`. The value is stored in a context variable, so each async task or request keeps its own setting.
- `LOCALE_FALLBACK` (defaults to `en`) provides a second chance when the active locale lacks a key.
- If the folder contents were changed on the fly, use `clear_cache()` to wipe cache.

### Translate in code
```python
from fast_app.core.localization import __, set_locale

set_locale("en")
message = __("messages.welcome", {"name": "Alice"}, default="Hello {name}")
```
- `__()` looks up the key using dot notation, applies the parameters with `str.format`, and falls back to the key (or `default=`) when nothing is found.
- Passing `locale="es"` lets me force a one-off translation without touching the global context.

### Handle plurals
- `trans_choice("cart_count", count, {"count": count})` automatically checks `cart_count_plural` when `count != 1` and otherwise reuses `cart_count`.

### Environment cheat sheet
- `LOCALE_PATH`: absolute or relative path to my JSON files (defaults to `<cwd>/lang`).
- `LOCALE_DEFAULT`: initial locale for new contexts.
- `LOCALE_FALLBACK`: locale used when the active one misses a key.

TLDR: 
- Drop JSON files in `app/lang` (e.g. `en.json`),
- Set the locale per request when necessary with `set_locale("en")` or env `LOCALE_DEFAULT`
- Call `__()` or `trans_choice()` wherever you need translated strings.
