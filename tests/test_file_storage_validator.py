import io

from werkzeug.datastructures import FileStorage

from fast_app.utils.file_utils import FileStorageValidator


class CountingBytesIO(io.BytesIO):
    def __init__(self, initial_bytes: bytes) -> None:
        super().__init__(initial_bytes)
        self.bytes_read = 0

    def read(self, size: int = -1) -> bytes:
        data = super().read(size)
        self.bytes_read += len(data)
        return data


def test_file_storage_validator_does_not_read_entire_oversized_file() -> None:
    stream = CountingBytesIO(b"a" * (2 * 1024 * 1024))
    upload = FileStorage(stream=stream, filename="large.txt", content_type="text/plain")

    validator = FileStorageValidator(max_size_mb=1, reject_mime_mismatch=False)
    is_valid, error, meta = validator.validate(upload)

    assert is_valid is False
    assert error == "File size exceeds 1 MB."
    assert meta["size_bytes"] == 2 * 1024 * 1024
    assert stream.bytes_read <= validator._mime_probe_bytes
