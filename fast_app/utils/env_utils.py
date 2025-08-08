import os
from dotenv import load_dotenv
from typing import Dict, List, Type, Optional
from fast_app.application import Application
from fast_app.event_base import Event
from fast_app.event_listener_base import EventListener
from fast_app.utils.autodiscovery.event_autodiscovery import autodiscover_events


def configure_env(env_file_name: Optional[str] = None) -> None:
    """
    Configure the application's environment.
    
    Args:
        env_file_name: Optional environment file name. If None, tries to load from .env.
    """
    if env_file_name is not None:
        load_dotenv(env_file_name, override=True)
        return

    if os.getenv("ENV", "debug") == "debug":
        print("🐞 Running on debug mode")

        for env_file in [".env.debug", ".env"]:
            load_dotenv(env_file, override=True)
            if os.getenv("ENV") is not None:
                print(f"☑️ Loaded {env_file} file successfully")
                break
            
        if os.getenv("ENV") is None:
            print("🚫 Loading env file failed. Create .env.debug file in your project root.")