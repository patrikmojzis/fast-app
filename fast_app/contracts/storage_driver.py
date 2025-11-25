from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, IO, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from quart import Response


class StorageDriver(ABC):
    """Abstract interface for storage drivers.

    Keep the surface minimal and generic so users can implement custom drivers easily.
    Download concerns (URLs, signed URLs) are intentionally excluded.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    async def exists(self, path: str) -> bool:
        pass

    @abstractmethod
    async def get(self, path: str) -> bytes:
        """
        Raises:
            FileNotFoundError: If file does not exist
        """
        pass

    @abstractmethod
    async def put(self, path: str, content: Union[str, bytes, IO], **kwargs) -> str:
        pass

    @abstractmethod
    async def delete(self, path: Union[str, List[str]]) -> bool:
        pass

    @abstractmethod
    async def copy(self, source: str, destination: str) -> bool:
        pass

    @abstractmethod
    async def move(self, source: str, destination: str) -> bool:
        pass

    @abstractmethod
    async def size(self, path: str) -> int:
        pass

    @abstractmethod
    async def last_modified(self, path: str) -> datetime:
        pass

    @abstractmethod
    async def files(self, directory: str = "", recursive: bool = False) -> List[str]:
        pass

    @abstractmethod
    async def directories(self, directory: str = "", recursive: bool = False) -> List[str]:
        pass

    @abstractmethod
    async def make_directory(self, path: str) -> bool:
        pass

    @abstractmethod
    async def delete_directory(self, directory: str) -> bool:
        pass

    async def missing(self, path: str) -> bool:
        return not await self.exists(path)

    async def prepend(self, path: str, content: str) -> str:
        existing_content = ""
        if await self.exists(path):
            existing_content = (await self.get(path)).decode("utf-8")
        return await self.put(path, content + existing_content)

    async def append(self, path: str, content: str) -> str:
        existing_content = ""
        if await self.exists(path):
            existing_content = (await self.get(path)).decode("utf-8")
        return await self.put(path, existing_content + content)

    # Download API: Drivers return a Quart Response best-suited for the backend
    @abstractmethod
    async def download(
        self,
        path: str,
        *,
        filename: Optional[str] = None,
        inline: bool = False,
        mimetype: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        max_age: Optional[int] = None,
    ) -> "Response":
        pass


