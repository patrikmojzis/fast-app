from typing import Any, Dict, List, Type, Optional, TYPE_CHECKING

import os
import sys

from fast_app.application import Application
from fast_app.core.storage import Storage
from fast_app.core.storage_drivers import get_builtin_storage_drivers
from fast_app.utils.autodiscovery.event_autodiscovery import autodiscover_events
from fast_app.utils.autodiscovery.model_autodiscovery import autodiscover_models
from fast_app.utils.env_utils import configure_env
from fast_app.utils.logging import setup_logging

if TYPE_CHECKING:
    from fast_app import Event, EventListener


def boot(*,
    autodiscovery: bool = True,
    events: Optional[Dict[Type['Event'], List[Type['EventListener']]]] = None,
    env_file_name: Optional[str] = None,
    storage_disks: Optional[Dict[str, Dict[str, Any]]] = None,
    storage_default_disk: Optional[str] = None,
    storage_custom_drivers: Optional[Dict[str, type]] = None,
    log_file_name: Optional[str] = None,
):
    """
    Sets up the application.
    - Loads environment variables if running in debug mode
    - Sets up logging
    - Runs observers and policies autodiscovery if enabled
    - Configures the event system
    
    Args:
        autodiscovery: Whether to run observers and policies autodiscovery.
        events: Optional events configuration. If None, tries autodiscovery from app.event_provider.
    """
    # Ensure project root is importable so user modules  can be resolved
    # in subprocesses (e.g., async_farm workers) during unpickling
    project_root = os.environ.get("PROJECT_ROOT") or os.getcwd()
    if project_root and project_root not in sys.path:
        sys.path.insert(0, project_root)

    app = Application()
    if app.is_booted():
        return
    
    app.set_boot_args(
        autodiscovery=autodiscovery,
        events=events,
        env_file_name=env_file_name,
        storage_disks=storage_disks,
        storage_default_disk=storage_default_disk,
    )
    
    configure_env(env_file_name)
    setup_logging(log_file_name)
    
    # Autodiscover and register observers and policies to models
    if autodiscovery:
        autodiscover_models()

    # Configure events
    if events is not None:
        app.configure_events(events)
    elif autodiscovery:
        if discovered_events := autodiscover_events():
            app.configure_events(discovered_events)

    # Configure Storage drivers and disks
    # 1) Register built-in drivers
    for name, driver_cls in get_builtin_storage_drivers().items():
        Storage.register_driver(name, driver_cls)

    # 2) Register custom drivers if provided by user
    if storage_custom_drivers:
        for name, driver_cls in storage_custom_drivers.items():
            Storage.register_driver(name, driver_cls)

    # 3) Configure disks (explicit params override config.py defaults)
    if storage_disks is not None or storage_default_disk is not None:
        disks = storage_disks if storage_disks is not None else {}
        default_disk = storage_default_disk if storage_default_disk is not None else "local"
        Storage.configure(disks=disks, default_disk=default_disk)

