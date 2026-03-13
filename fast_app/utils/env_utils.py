import importlib
import json
import logging
import os
from typing import Final, Optional

from dotenv import load_dotenv


def configure_env(env_file_name: Optional[str] = None) -> None:
    """
    Configure the application's environment.
    
    Args:
        env_file_name: Optional environment file name. If None, tries to load from .env.
    """
    if env_file_name is not None:
        load_dotenv(env_file_name, override=True)
        return

    environment = os.getenv("ENV", "debug")

    for env_file in [f".env.{environment}", ".env"]:
        load_dotenv(env_file, override=True)
        if os.getenv("ENV") is not None:
            logging.debug(f"☑️ Loaded {env_file} file successfully")
            break

    if os.getenv("ENV") is None:
        print("🚫 Loading env file failed.")
        print(f"Create .env file in your project root.")
        print("For specific environment, create .env.<environment> file.")


def configure_env_from_app_config() -> None:
    """
    Configure environment files the same way FastApp boot does, without running full boot.

    This is intended for lightweight CLI commands that need project-specific env resolution
    (for example `app.app_config.env_file_name`) but should avoid autodiscovery and other
    boot-time side effects.
    """
    configure_env()

    try:
        spec = importlib.util.find_spec("app.app_config")
    except ModuleNotFoundError:
        return

    if spec is None:
        return

    config_module = importlib.import_module("app.app_config")
    env_file_name = getattr(config_module, "env_file_name", None)
    if env_file_name is not None:
        configure_env(env_file_name)


TRUE_VALUES: Final = frozenset(("1", "true", "yes", "on"))
_MISSING: Final = object()  # `undefined`

def _get_env_value(name: str, default=_MISSING):
    if name not in os.environ:
        if default is _MISSING:
            raise RuntimeError(f"Env value {name} is not defined.")
        return default, False
    return os.environ[name], True


def env_bool(name: str, default=_MISSING):
    value, is_defined = _get_env_value(name, default)
    if not is_defined:
        return value

    return value.strip().casefold() in TRUE_VALUES


def env_int(name: str, default=_MISSING):
    value, is_defined = _get_env_value(name, default)
    if not is_defined:
        return value

    try:
        return int(value.strip())
    except ValueError as exc:
        raise RuntimeError(f"Env value {name} must be a valid int.") from exc


def env_float(name: str, default=_MISSING):
    value, is_defined = _get_env_value(name, default)
    if not is_defined:
        return value

    try:
        return float(value.strip())
    except ValueError as exc:
        raise RuntimeError(f"Env value {name} must be a valid float.") from exc


def env_str(name: str, default=_MISSING):
    value, is_defined = _get_env_value(name, default)
    if not is_defined:
        return value
    return value


def env_list(name: str, default=_MISSING, sep: str = ","):
    value, is_defined = _get_env_value(name, default)
    if not is_defined:
        return value

    if not sep:
        raise ValueError("sep must not be an empty string.")

    raw = value.strip()
    if raw == "":
        return []

    return [item.strip() for item in raw.split(sep) if item.strip() != ""]


def env_json(name: str, default=_MISSING):
    value, is_defined = _get_env_value(name, default)
    if not is_defined:
        return value

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Env value {name} must be a valid JSON object.") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError(f"Env value {name} must be a JSON object (dict).")

    return parsed
