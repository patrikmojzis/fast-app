from datetime import datetime
from typing import Dict, IO, List, Optional, Union

from fast_app import StorageDriver
from fast_app.utils.datetime_utils import now

class NewClass(StorageDriver):
    async def exists(self, path: str) -> bool:
        return False

    async def get(self, path: str) -> bytes:
        return b""

    async def put(self, path: str, content: Union[str, bytes, IO]) -> str:
        return path

    async def delete(self, path: Union[str, List[str]]) -> bool:
        return True

    async def copy(self, source: str, destination: str) -> bool:
        return True

    async def move(self, source: str, destination: str) -> bool:
        return True

    async def size(self, path: str) -> int:
        return 0

    async def last_modified(self, path: str) -> datetime:
        return now()

    async def files(self, directory: str = "", recursive: bool = False) -> List[str]:
        return []

    async def directories(self, directory: str = "", recursive: bool = False) -> List[str]:
        return []

    async def make_directory(self, path: str) -> bool:
        return True

    async def delete_directory(self, directory: str) -> bool:
        return True

    async def download(self, path: str, *, filename: Optional[str] = None, inline: bool = False, mimetype: Optional[str] = None, extra_headers: Optional[Dict[str, str]] = None, max_age: Optional[int] = None):
        from quart import Response
        return Response(status=204)


