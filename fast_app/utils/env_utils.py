import logging
import os
from typing import Optional

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