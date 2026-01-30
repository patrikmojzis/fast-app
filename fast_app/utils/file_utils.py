import mimetypes
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Optional, Union, Tuple

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

try:
    import magic
except Exception:  # pragma: no cover - optional dependency
    magic = None  # type: ignore[assignment]


def secure_path(filename: str) -> str:
    """
    Make a filename safe for storage by removing or replacing potentially dangerous characters.
    Similar to Laravel's str()->slug() but for filenames.
    """
    return secure_filename(filename)


def generate_unique_filename(original_filename: str, preserve_extension: bool = True) -> str:
    """
    Generate a unique filename, optionally preserving the original extension.
    Similar to Laravel's Storage::putFile() behavior.
    """
    if preserve_extension and '.' in original_filename:
        name, extension = os.path.splitext(secure_path(original_filename))
        return f"{uuid.uuid4().hex}{extension}"
    else:
        return uuid.uuid4().hex


def get_file_extension_from_filename(filename: str) -> str:
    """Get the file extension from a filename."""
    return Path(filename).suffix.lower()


def get_mime_type(filename: str) -> Optional[str]:
    """
    Get the MIME type of a file based on its extension.
    """
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type


def normalize_path(path: str) -> str:
    """
    Normalize a file path by removing redundant separators and up-level references.
    """
    return os.path.normpath(path).replace('\\', '/')


def join_paths(*paths: str) -> str:
    """
    Join multiple path components into a single path.
    """
    return '/'.join(paths).replace('//', '/').strip('/')


def is_image(filename: str) -> bool:
    """
    Check if a file is an image based on its MIME type.
    """
    mime_type = get_mime_type(filename)
    return mime_type is not None and mime_type.startswith('image/')


def is_video(filename: str) -> bool:
    """
    Check if a file is a video based on its MIME type.
    """
    mime_type = get_mime_type(filename)
    return mime_type is not None and mime_type.startswith('video/')


def is_audio(filename: str) -> bool:
    """
    Check if a file is an audio file based on its MIME type.
    """
    mime_type = get_mime_type(filename)
    return mime_type is not None and mime_type.startswith('audio/')


def is_document(filename: str) -> bool:
    """
    Check if a file is a document based on its MIME type.
    """
    mime_type = get_mime_type(filename)
    if not mime_type:
        return False
    
    document_types = [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'text/plain',
        'text/csv',
        'application/rtf'
    ]
    
    return mime_type in document_types


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format (bytes, KB, MB, GB, TB).
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def validate_file_size(size_bytes: int, max_size_mb: float) -> bool:
    """
    Validate if file size is within the allowed limit.
    
    Args:
        size_bytes: File size in bytes
        max_size_mb: Maximum allowed size in megabytes
    
    Returns:
        True if file size is valid, False otherwise
    """
    max_size_bytes = max_size_mb * 1024 * 1024
    return size_bytes <= max_size_bytes


def validate_file_type(filename: str, allowed_extensions: Union[list, tuple]) -> bool:
    """
    Validate if file type is allowed based on extension.
    
    Args:
        filename: Name of the file
        allowed_extensions: List/tuple of allowed extensions (with or without dots)
    
    Returns:
        True if file type is allowed, False otherwise
    """
    file_ext = get_file_extension_from_filename(filename)
    
    # Normalize extensions (ensure they start with a dot)
    normalized_extensions = []
    for ext in allowed_extensions:
        if not ext.startswith('.'):
            ext = '.' + ext
        normalized_extensions.append(ext.lower())
    
    return file_ext in normalized_extensions


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize filename by removing invalid characters and limiting length.
    
    Args:
        filename: Original filename
        max_length: Maximum allowed filename length
    
    Returns:
        Sanitized filename
    """
    # Remove invalid characters
    filename = secure_filename(filename)
    
    # Remove control characters
    filename = ''.join(char for char in filename if ord(char) >= 32)
    
    # Limit length while preserving extension
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        max_name_length = max_length - len(ext)
        filename = name[:max_name_length] + ext
    
    return filename.strip()


def extract_path_info(path: str) -> dict:
    """
    Extract information about a file path.
    
    Returns:
        dict: Contains 'directory', 'filename', 'name', 'extension', 'basename'
    """
    path_obj = Path(path)
    
    return {
        'directory': str(path_obj.parent),
        'filename': path_obj.name,
        'name': path_obj.stem,
        'extension': path_obj.suffix,
        'basename': path_obj.stem
    }


def build_file_path(directory: str, filename: str, create_dirs: bool = False) -> str:
    """
    Build a complete file path and optionally create directories.
    
    Args:
        directory: Directory path
        filename: Filename
        create_dirs: Whether to create directories if they don't exist
    
    Returns:
        Complete file path
    """
    full_path = Path(directory) / filename
    
    if create_dirs:
        full_path.parent.mkdir(parents=True, exist_ok=True)
    
    return str(full_path)


def resolve_cli_path(path: Optional[str], default_subpath: Union[str, Path]) -> Path:
    """
    Resolve a CLI --path override relative to the project root (cwd).

    - If path is provided, it must be relative and stay within the project root.
    - If not provided, default_subpath is used under the project root.
    """
    base = Path.cwd().resolve()

    if path:
        candidate = Path(path)
        if candidate.is_absolute():
            raise ValueError("--path must be relative to the project root")
        resolved = (base / candidate).resolve()
        try:
            resolved.relative_to(base)
        except ValueError as exc:
            raise ValueError("--path must stay within the project root") from exc
        return resolved

    return base / default_subpath


class FileStorageValidator:
    """
    Comprehensive file validator for uploads.
    - Verifies real MIME from content via libmagic.
    - Checks extension allow-list.
    - Checks max size (bytes derived from actual content).
    - (Optional) rejects when client/filename MIME disagrees with real MIME.
    """

    def __init__(
        self,
        max_size_mb: float = 10.0,
        allowed_extensions: Optional[list[str]] = None,
        allowed_mime_types: Optional[list[str]] = None,
        reject_mime_mismatch: bool = True,  # fail if client/filename MIME != real MIME
    ):
        self.max_size_mb = max_size_mb
        self.allowed_extensions = {e.lower().lstrip(".") for e in (allowed_extensions or [])}
        self.allowed_mime_types = set(allowed_mime_types or [])
        self.reject_mime_mismatch = reject_mime_mismatch
        self.max_size_bytes = int(self.max_size_mb * 1024 * 1024)

    def validate(self, file: FileStorage) -> Tuple[bool, Optional[str], dict[str, Any]]:
        """
        Validate a werkzeug FileStorage (Quart/Flask upload).

        Returns: (is_valid, error_message, meta)
          meta = {
            "filename", "size_bytes",
            "ext",
            "real_mime",        # preferred MIME (magic -> guess)
            "magic_mime",       # from libmagic (optional)
            "magic_available",  # whether magic import succeeded
            "client_mime",      # from browser header
            "guessed_mime"      # from filename (mimetypes)
          }
        """
        filename = getattr(file, "filename", "") or ""
        client_mime = getattr(file, "mimetype", None)

        # Read bytes ONCE to measure size + detect MIME; then rewind.
        content: bytes = file.read()
        size_bytes = len(content)
        try:
            file.seek(0)  # rewind so caller can read/save again
        except Exception:
            # Some storages expose file.stream
            try:
                file.stream.seek(0)
            except Exception:
                pass  # worst case, caller must handle

        guessed_mime, _ = mimetypes.guess_type(filename)
        magic_mime: Optional[str] = None

        if magic and content:
            try:
                magic_mime = magic.from_buffer(content, mime=True)
            except Exception:
                magic_mime = None

        real_mime = magic_mime or guessed_mime
        ext = get_file_extension_from_filename(filename)

        meta = {
            "filename": filename,
            "size_bytes": size_bytes,
            "ext": ext,
            "real_mime": real_mime,
            "magic_mime": magic_mime,
            "magic_available": magic is not None,
            "client_mime": client_mime,
            "guessed_mime": guessed_mime,
        }

        # ---- Size check (actual bytes) ----
        if size_bytes == 0:
            return False, "Empty file.", meta
        if size_bytes > self.max_size_bytes:
            return False, f"File size exceeds {self.max_size_mb} MB.", meta

        # ---- Extension allow-list (optional) ----
        if self.allowed_extensions and ext not in self.allowed_extensions:
            return False, f"File type not allowed. Allowed: {', '.join(sorted(self.allowed_extensions))}", meta

        # ---- Real MIME allow-list (optional, strongest check) ----
        if self.allowed_mime_types:
            candidate_mime = magic_mime or guessed_mime
            if candidate_mime and candidate_mime not in self.allowed_mime_types:
                return False, f"MIME not allowed ({candidate_mime}). Allowed: {', '.join(sorted(self.allowed_mime_types))}", meta

        # ---- Mismatch checks (optional hard-fail) ----
        if self.reject_mime_mismatch and magic_mime:
            if client_mime and (client_mime != magic_mime):
                return False, f"MIME mismatch: client={client_mime}, real={magic_mime}", meta
            if guessed_mime and (guessed_mime != magic_mime):
                return False, f"Filename does not match content: name={guessed_mime}, real={magic_mime}", meta

        return True, None, meta

    def is_valid(self, file: FileStorage) -> bool:
        ok, _, _ = self.validate(file)
        return ok

# Common file validators
# ImageValidator = FileStorageValidator(
#     max_size_mb=5.0,
#     allowed_extensions=['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'],
#     allowed_mime_types=['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml']
# )

# DocumentValidator = FileStorageValidator(
#     max_size_mb=20.0,
#     allowed_extensions=['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.csv', '.rtf'],
#     allowed_mime_types=[
#         'application/pdf',
#         'application/msword',
#         'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
#         'application/vnd.ms-excel',
#         'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
#         'application/vnd.ms-powerpoint',
#         'application/vnd.openxmlformats-officedocument.presentationml.presentation',
#         'text/plain',
#         'text/csv',
#         'application/rtf'
#     ]
# )

# VideoValidator = FileStorageValidator(
#     max_size_mb=100.0,
#     allowed_extensions=['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv'],
#     allowed_mime_types=['video/mp4', 'video/avi', 'video/quicktime', 'video/x-ms-wmv', 'video/webm', 'video/x-matroska']
# )

# AudioValidator = FileStorageValidator(
#     max_size_mb=50.0,
#     allowed_extensions=['.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'],
#     allowed_mime_types=['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/flac', 'audio/aac', 'audio/mp4']
# )


# CLI-specific utilities
def copy_with_substitution(src: Path, dst: Path, substitutions: dict[str, str]) -> None:
    """Copy file with template variable substitution."""
    text_extensions = {'.py', '.js', '.yml', '.yaml', '.example', '.md', '.txt', '.json'}
    
    if src.suffix in text_extensions:
        content = src.read_text(encoding='utf-8')
        for old, new in substitutions.items():
            content = content.replace(old, new)
        dst.write_text(content, encoding='utf-8')
    else:
        shutil.copy2(src, dst)


def copy_tree(src: Path, dst: Path, substitutions: dict[str, str] | None = None) -> None:
    """Recursively copy directory tree with optional substitutions."""
    if not src.exists():
        return
    
    substitutions = substitutions or {}
    
    for item in src.rglob('*'):
        if item.is_file():
            rel_path = item.relative_to(src)
            dest_file = dst / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            copy_with_substitution(item, dest_file, substitutions)
