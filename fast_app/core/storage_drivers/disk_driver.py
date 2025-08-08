import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, IO, List, Optional, Union

from fast_app.contracts.storage_driver import StorageDriver
from fast_app.utils.file_utils import get_mime_type, sanitize_filename
from quart import send_file


class DiskDriver(StorageDriver):
    """Local filesystem driver."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.root = Path(config.get("root", os.getcwd()))
        self.permissions = config.get(
            "permissions",
            {
                "file": {"public": 0o644, "private": 0o600},
                "dir": {"public": 0o755, "private": 0o700},
            },
        )
        self.root.mkdir(parents=True, exist_ok=True)

    def _full(self, path: str) -> Path:
        return self.root / path.lstrip("/")

    def _secure(self, path: str) -> str:
        path = path.replace("..", "").replace("//", "/")
        return path.strip("/")

    async def exists(self, path: str) -> bool:
        return self._full(self._secure(path)).exists()

    # Optional helper for frameworks to send files efficiently
    def absolute_path(self, path: str) -> Path:
        return self._full(self._secure(path))

    async def get(self, path: str) -> bytes:
        file_path = self._full(self._secure(path))
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return file_path.read_bytes()

    async def put(self, path: str, content: Union[str, bytes, IO], visibility: Optional[str] = None) -> str:
        secure = self._secure(path)
        file_path = self._full(secure)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(content, str):
            file_path.write_text(content, encoding="utf-8")
        elif isinstance(content, bytes):
            file_path.write_bytes(content)
        else:
            with open(file_path, "wb") as f:
                shutil.copyfileobj(content, f)

        if visibility:
            mode = self.permissions["file"].get(visibility, 0o644)
            file_path.chmod(mode)

        return secure

    async def delete(self, path: Union[str, List[str]]) -> bool:
        paths = [path] if isinstance(path, str) else path
        try:
            for p in paths:
                fp = self._full(self._secure(p))
                if fp.exists():
                    fp.unlink()
            return True
        except Exception:
            return False

    async def copy(self, source: str, destination: str) -> bool:
        try:
            src = self._full(self._secure(source))
            dst = self._full(self._secure(destination))
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            return True
        except Exception:
            return False

    async def move(self, source: str, destination: str) -> bool:
        try:
            src = self._full(self._secure(source))
            dst = self._full(self._secure(destination))
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dst)
            return True
        except Exception:
            return False

    async def size(self, path: str) -> int:
        fp = self._full(self._secure(path))
        if not fp.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return fp.stat().st_size

    async def last_modified(self, path: str) -> datetime:
        fp = self._full(self._secure(path))
        if not fp.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return datetime.fromtimestamp(fp.stat().st_mtime)

    async def files(self, directory: str = "", recursive: bool = False) -> List[str]:
        dir_path = self._full(self._secure(directory))
        if not dir_path.exists():
            return []
        pattern = "**/*" if recursive else "*"
        files: List[str] = []
        for item in dir_path.glob(pattern):
            if item.is_file():
                files.append(str(item.relative_to(self.root)))
        return sorted(files)

    async def directories(self, directory: str = "", recursive: bool = False) -> List[str]:
        dir_path = self._full(self._secure(directory))
        if not dir_path.exists():
            return []
        pattern = "**/*" if recursive else "*"
        dirs: List[str] = []
        for item in dir_path.glob(pattern):
            if item.is_dir():
                dirs.append(str(item.relative_to(self.root)))
        return sorted(dirs)

    async def make_directory(self, path: str) -> bool:
        try:
            dp = self._full(self._secure(path))
            dp.mkdir(parents=True, exist_ok=True)
            return True
        except Exception:
            return False

    async def delete_directory(self, directory: str) -> bool:
        try:
            dp = self._full(self._secure(directory))
            if dp.exists() and dp.is_dir():
                shutil.rmtree(dp)
            return True
        except Exception:
            return False

    async def download(
        self,
        path: str,
        *,
        filename: Optional[str] = None,
        inline: bool = False,
        mimetype: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        max_age: Optional[int] = None,
    ):
        safe_name = sanitize_filename(filename or path.split("/")[-1])
        content_type = mimetype or get_mime_type(safe_name) or "application/octet-stream"
        abs_path: Path = self.absolute_path(path)
        resp = await send_file(
            abs_path,
            mimetype=content_type,
            as_attachment=not inline,
            download_name=safe_name,
            conditional=True,
            max_age=max_age if max_age is not None else (3600 if inline else 0),
        )
        if extra_headers:
            for k, v in extra_headers.items():
                resp.headers[k] = v
        return resp


