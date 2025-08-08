import os
from typing import Any, Dict, Optional, Union, List, IO, Type
from datetime import datetime

from fast_app.contracts.storage_driver import StorageDriver
from fast_app.core.storage_drivers import get_builtin_storage_drivers


class Storage:
    """Minimal storage facade with driver registry and programmatic configuration."""
    
    _driver_instances: Dict[str, StorageDriver] = {}
    _driver_registry: Dict[str, Type[StorageDriver]] = {}
    _default_disk: Optional[str] = None
    _disks_config: Optional[Dict[str, Dict[str, Any]]] = None
    
    @classmethod
    def register_driver(cls, name: str, driver_class: Type[StorageDriver]) -> None:
        """Register a driver class under a type name (e.g. 'disk', 'boto3', 'gcs')."""
        cls._driver_registry[name] = driver_class
    
    @classmethod
    def configure(cls, disks: Dict[str, Dict[str, Any]], default_disk: str = "local") -> None:
        """Configure named disks and a default disk. Clears cached instances.

        If 'disks' is empty, keep current (or default) configuration and only update default disk.
        """
        if not disks:
            # Preserve existing or load defaults
            cls._load_default_config()
        else:
            cls._disks_config = disks
        cls._default_disk = default_disk
        cls._driver_instances.clear()
    
    @classmethod
    def _load_default_config(cls) -> None:
        if cls._disks_config is not None:
            return
        try:
            from fast_app.config import STORAGE_DISKS, STORAGE_DEFAULT_DISK
            cls._disks_config = STORAGE_DISKS
            cls._default_disk = STORAGE_DEFAULT_DISK
        except Exception:
            # Minimal sensible default
            cls._disks_config = {
                "local": {
                    "driver": "disk",
                    "root": os.path.join(os.getcwd(), "storage", "local"),
                    "permissions": {
                        "file": {"public": 0o644, "private": 0o600},
                        "dir": {"public": 0o755, "private": 0o700},
                    },
                }
            }
            cls._default_disk = "local"
    
    @classmethod
    def disk(cls, name: Optional[str] = None) -> StorageDriver:
        cls._load_default_config()
        assert cls._disks_config is not None
        disk_name = name or (cls._default_disk or "local")

        # Ensure built-in drivers are available if nothing registered yet
        if not cls._driver_registry:
            for driver_name, driver_cls in get_builtin_storage_drivers().items():
                cls.register_driver(driver_name, driver_cls)

        if disk_name in cls._driver_instances:
            return cls._driver_instances[disk_name]

        if disk_name not in cls._disks_config:
            raise ValueError(f"Storage disk '{disk_name}' is not configured")

        disk_cfg = cls._disks_config[disk_name]
        driver_type = disk_cfg.get("driver")
        if not driver_type:
            raise ValueError(f"Disk '{disk_name}' missing 'driver' in configuration")

        driver_cls = cls._driver_registry.get(driver_type)
        if driver_cls is None:
            raise ValueError(
                f"Driver '{driver_type}' is not registered. Register it via Storage.register_driver()."
            )

        instance = driver_cls(disk_cfg)
        cls._driver_instances[disk_name] = instance
        return instance
    
    # Convenience methods for default disk
    @classmethod
    async def exists(cls, path: str) -> bool:
        return await cls.disk().exists(path)
    
    @classmethod
    async def get(cls, path: str) -> bytes:
        return await cls.disk().get(path)
    
    @classmethod
    async def put(cls, path: str, content: Union[str, bytes, IO], visibility: Optional[str] = None) -> str:
        return await cls.disk().put(path, content, visibility)
    
    @classmethod
    async def delete(cls, path: Union[str, List[str]]) -> bool:
        return await cls.disk().delete(path)
    
    @classmethod
    async def copy(cls, source: str, destination: str) -> bool:
        return await cls.disk().copy(source, destination)
    
    @classmethod
    async def move(cls, source: str, destination: str) -> bool:
        return await cls.disk().move(source, destination)
    
    @classmethod
    async def size(cls, path: str) -> int:
        return await cls.disk().size(path)
    
    @classmethod
    async def last_modified(cls, path: str) -> datetime:
        return await cls.disk().last_modified(path)

    # Download helpers
    @classmethod
    async def download(
        cls,
        path: str,
        *,
        disk: Optional[str] = None,
        filename: Optional[str] = None,
        inline: bool = False,
        mimetype: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        max_age: Optional[int] = None,
    ):
        return await cls.disk(disk).download(
            path,
            filename=filename,
            inline=inline,
            mimetype=mimetype,
            extra_headers=extra_headers,
            max_age=max_age,
        )