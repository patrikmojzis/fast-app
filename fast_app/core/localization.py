"""
Elegant localization for fast-app - Laravel-inspired with Beethoven's simplicity.

Like a perfect musical phrase, this module achieves maximum effect with minimal complexity.
Core principles:
- Direct module-level state (no unnecessary classes)
- Dot notation for nested keys: 'messages.welcome'
- Graceful fallbacks and parameter replacement
- Thread-safe context-aware locale switching

Usage:
    from fast_app.core.localization import __, set_locale, get_locale
    
    __('messages.welcome')                              # Basic translation
    __('messages.greeting', {'name': 'John'})          # With parameters  
    __('missing.key', default='Fallback')              # With default
    set_locale('es')                                   # Change locale
"""

import json
from contextvars import ContextVar
from pathlib import Path
from typing import Dict, Any, Optional
import os

# Module state - elegant simplicity
_translations: Dict[str, Dict[str, Any]] = {}
# Internal defaults without config dependency
_LOCALE_DEFAULT = os.getenv('LOCALE_DEFAULT', 'en')
_LOCALE_FALLBACK = os.getenv('LOCALE_FALLBACK', 'en')
_LOCALE_PATH = os.getenv('LOCALE_PATH', os.path.join(os.getcwd(), 'lang'))
_current_locale: ContextVar[str] = ContextVar('locale', default=_LOCALE_DEFAULT)


def _get_nested(data: Dict[str, Any], key: str) -> Optional[str]:
    """Navigate nested dict with dot notation. Pure function, no side effects."""
    current = data
    for part in key.split('.'):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _load_locale(locale: str) -> Dict[str, Any]:
    """Load and cache translations for a locale. Idempotent."""
    if locale in _translations:
        return _translations[locale]
    
    locale_file = Path(_LOCALE_PATH) / f"{locale}.json"
    translations = {}
    
    if locale_file.exists():
        try:
            with locale_file.open(encoding='utf-8') as f:
                translations = json.load(f)
        except (json.JSONDecodeError, OSError):
            # Fail silently - elegance in error handling
            pass
    
    _translations[locale] = translations
    return translations


def __(key: str, parameters: Optional[Dict[str, Any]] = None, 
      default: Optional[str] = None, locale: Optional[str] = None) -> str:
    """
    Translate with Laravel-style elegance. The heart of the localization system.
    
    Like a musical theme that can be played in any key, this function adapts
    gracefully to any locale while maintaining its essential character.
    
    Examples:
        __('messages.welcome')                      # Simple translation
        __('greet', {'name': 'John'})              # With parameters
        __('missing', default='Not found')         # With fallback
        __('title', locale='es')                   # Force locale
    """
    current_locale = locale or _current_locale.get()
    
    # Try current locale first
    translation = _get_nested(_load_locale(current_locale), key)
    
    # Fallback to default locale if needed and different
    if translation is None and current_locale != _LOCALE_FALLBACK:
        translation = _get_nested(_load_locale(_LOCALE_FALLBACK), key)
    
    # Final fallback to default or key itself
    if translation is None:
        translation = default or key
    
    # Apply parameters if provided - fail gracefully
    if parameters and isinstance(translation, str):
        try:
            translation = translation.format(**parameters)
        except (KeyError, ValueError):
            pass  # Silent grace - like a missed note that doesn't ruin the performance
    
    return str(translation)


def set_locale(locale: str) -> None:
    """Set the current locale. Simple, direct, effective."""
    _current_locale.set(locale)


def get_locale() -> str:
    """Get the current locale. Pure simplicity."""
    return _current_locale.get()


def clear_cache() -> None:
    """Clear translation cache. Sometimes you need a fresh start."""
    _translations.clear()


# Optional: allow tests or apps to override locale path at runtime
def set_locale_path(path: str) -> None:
    global _LOCALE_PATH
    _LOCALE_PATH = path


# Elegant aliases - variations on the theme
trans = __  # Direct alias - no wrapper overhead

def trans_choice(key: str, count: int, parameters: Optional[Dict[str, Any]] = None) -> str:
    """
    Pluralization with mathematical elegance.
    
    Like musical intervals, pluralization follows natural patterns.
    We compose the plural key and let the main function handle the complexity.
    """
    params = (parameters or {}).copy()
    params['count'] = count
    
    # Try plural form for count != 1
    if count != 1:
        plural_translation = __(f"{key}_plural", params, default=None)
        if plural_translation != f"{key}_plural":  # Found a real translation
            return plural_translation
    
    # Fallback to singular
    return __(key, params)