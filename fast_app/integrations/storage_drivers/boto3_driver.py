from datetime import datetime
from typing import Any, Dict, IO, List, Optional, Union

from quart import Response

from fast_app.contracts.storage_driver import StorageDriver
from fast_app.utils.file_utils import get_mime_type, sanitize_filename


class Boto3Driver(StorageDriver):
    """S3-compatible driver using boto3 (AWS S3, MinIO, DigitalOcean Spaces, etc.)."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.bucket = config.get("bucket")
        self.region = config.get("region_name", "us-east-1")
        try:
            import boto3
            from botocore.exceptions import ClientError

            self._client = boto3.client(
                "s3",
                aws_access_key_id=config.get("access_key_id"),
                aws_secret_access_key=config.get("secret_access_key"),
                region_name=self.region,
                endpoint_url=config.get("endpoint_url"),
            )
            self._ClientError = ClientError
        except ImportError:
            raise ImportError("boto3 is required for Boto3Driver. Install with: pip install boto3")

    def _key(self, path: str) -> str:
        return path.lstrip("/")

    async def exists(self, path: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=self._key(path))
            return True
        except self._ClientError:
            return False

    async def get(self, path: str) -> bytes:
        try:
            resp = self._client.get_object(Bucket=self.bucket, Key=self._key(path))
            return resp["Body"].read()
        except self._ClientError as e:
            raise FileNotFoundError(f"File not found: {path}") from e

    # Streaming helper (yields chunks) for proxy downloads
    def stream(self, path: str, chunk_size: int = 8 * 1024):
        resp = self._client.get_object(Bucket=self.bucket, Key=self._key(path))
        body = resp["Body"]
        while True:
            data = body.read(chunk_size)
            if not data:
                break
            yield data

    async def put(self, path: str, content: Union[str, bytes, IO], extra_args: Optional[Dict[str, Any]] = None) -> str:
        key = self._key(path)
        extra_args: Dict[str, Any] = extra_args or {}
        content_type = get_mime_type(path)
        if content_type:
            extra_args["ContentType"] = content_type

        if isinstance(content, str):
            content = content.encode("utf-8")
        if isinstance(content, bytes):
            from io import BytesIO
            content = BytesIO(content)

        self._client.upload_fileobj(content, self.bucket, key, ExtraArgs=extra_args)
        return key


    async def delete(self, path: Union[str, List[str]]) -> bool:
        keys = [path] if isinstance(path, str) else path
        try:
            objects = [{"Key": self._key(k)} for k in keys]
            if len(objects) == 1:
                self._client.delete_object(Bucket=self.bucket, Key=objects[0]["Key"])
            else:
                self._client.delete_objects(Bucket=self.bucket, Delete={"Objects": objects})
            return True
        except Exception:
            return False

    async def copy(self, source: str, destination: str) -> bool:
        try:
            copy_source = {"Bucket": self.bucket, "Key": self._key(source)}
            self._client.copy_object(CopySource=copy_source, Bucket=self.bucket, Key=self._key(destination))
            return True
        except Exception:
            return False

    async def move(self, source: str, destination: str) -> bool:
        if await self.copy(source, destination):
            return await self.delete(source)
        return False

    async def size(self, path: str) -> int:
        try:
            resp = self._client.head_object(Bucket=self.bucket, Key=self._key(path))
            return resp["ContentLength"]
        except self._ClientError as e:
            raise FileNotFoundError(f"File not found: {path}") from e

    async def last_modified(self, path: str) -> datetime:
        try:
            resp = self._client.head_object(Bucket=self.bucket, Key=self._key(path))
            return resp["LastModified"].replace(tzinfo=None)
        except self._ClientError as e:
            raise FileNotFoundError(f"File not found: {path}") from e

    async def files(self, directory: str = "", recursive: bool = False) -> List[str]:
        prefix = self._key(directory)
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        try:
            resp = self._client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix,
                Delimiter="" if recursive else "/",
            )
            files: List[str] = []
            for obj in resp.get("Contents", []):
                key = obj["Key"]
                if not key.endswith("/"):
                    files.append(key)
            return sorted(files)
        except Exception:
            return []

    async def directories(self, directory: str = "", recursive: bool = False) -> List[str]:
        prefix = self._key(directory)
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        try:
            dirs: set[str] = set()
            if recursive:
                resp = self._client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
                for obj in resp.get("Contents", []):
                    parts = obj["Key"].split("/")
                    for i in range(1, len(parts)):
                        dp = "/".join(parts[:i])
                        if dp and dp != prefix.rstrip("/"):
                            dirs.add(dp)
            else:
                resp = self._client.list_objects_v2(Bucket=self.bucket, Prefix=prefix, Delimiter="/")
                for cp in resp.get("CommonPrefixes", []):
                    dirs.add(cp["Prefix"].rstrip("/"))
            return sorted(dirs)
        except Exception:
            return []

    async def make_directory(self, path: str) -> bool:
        try:
            key = self._key(path)
            if not key.endswith("/"):
                key += "/"
            self._client.put_object(Bucket=self.bucket, Key=key, Body=b"")
            return True
        except Exception:
            return False

    async def delete_directory(self, directory: str) -> bool:
        try:
            prefix = self._key(directory)
            if not prefix.endswith("/"):
                prefix += "/"
            resp = self._client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
            if "Contents" in resp:
                objs = [{"Key": o["Key"]} for o in resp["Contents"]]
                for i in range(0, len(objs), 1000):
                    self._client.delete_objects(Bucket=self.bucket, Delete={"Objects": objs[i : i + 1000]})
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
        disposition = "inline" if inline else "attachment"

        def generate():
            for chunk in self.stream(path):
                yield chunk

        headers = {
            "Content-Disposition": f'{disposition}; filename="{safe_name}"',
            "X-Content-Type-Options": "nosniff"
        }
        if extra_headers:
            headers.update(extra_headers)
        if max_age is not None:
            headers["Cache-Control"] = f"public, max-age={max_age}"
        return Response(generate(), headers=headers, mimetype=content_type, direct_passthrough=True)


