# Import `import fast_app.boot` on every fresh python entry point
# as the first line to load this config to the app

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Type

if TYPE_CHECKING:
    from fast_app import Event
    from fast_app import EventListener


# Whether to autoregister Observers and Policies autodiscovery on Models based on names
autodiscovery: bool = True

# Extend events
events: Optional[Dict[Type['Event'], List[Type['EventListener']]]] = None

# Override debug .env & .env.{os.getenv("ENV")} check
env_file_name: Optional[str] = None

# Add additional storage disks, programmatic Storage.configure
storage_disks: Optional[Dict[str, Dict[str, Any]]] = None

# Edit default disk
storage_default_disk: Optional[str] = None

# Add custom storage drivers, e.g. {"gcs": GCSDriver}
storage_custom_drivers: Optional[Dict[str, type]] = None

# Rename where to capture logs for this app. Default: app.log
log_file_name: Optional[str] = None

# Register custom serialisers mapping class -> callables returning serialisable payloads
serialisers: Optional[Dict[type[Any], Callable[[Any], Any]]] = None