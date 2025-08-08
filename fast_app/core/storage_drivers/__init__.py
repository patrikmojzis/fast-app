"""Built-in storage drivers shipped with FastApp."""

from typing import Dict, Type

from fast_app.contracts.storage_driver import StorageDriver
from .disk_driver import DiskDriver


def get_builtin_storage_drivers() -> Dict[str, Type[StorageDriver]]:
    """Return built-in storage drivers mapping.

    Keys are driver identifiers used in configuration, values are driver classes.
    """
    return {
        "disk": DiskDriver,
    }


