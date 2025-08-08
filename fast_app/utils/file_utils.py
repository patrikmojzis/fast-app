import os
import mimetypes
import shutil
import uuid
from pathlib import Path
from typing import Optional, Union, Tuple, Set
from werkzeug.utils import secure_filename


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


def get_file_extension(filename: str) -> str:
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
    file_ext = get_file_extension(filename)
    
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
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
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


class FileValidator:
    """
    File validation utility class for comprehensive file checks.
    """
    
    def __init__(self, 
                 max_size_mb: float = 10.0,
                 allowed_extensions: Optional[list] = None,
                 allowed_mime_types: Optional[list] = None):
        """
        Initialize file validator.
        
        Args:
            max_size_mb: Maximum file size in megabytes
            allowed_extensions: List of allowed file extensions
            allowed_mime_types: List of allowed MIME types
        """
        self.max_size_mb = max_size_mb
        self.allowed_extensions = allowed_extensions or []
        self.allowed_mime_types = allowed_mime_types or []
    
    def validate(self, filename: str, size_bytes: int) -> Tuple[bool, Optional[str]]:
        """
        Validate a file against all configured rules.
        
        Args:
            filename: Name of the file
            size_bytes: Size of the file in bytes
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check file size
        if not validate_file_size(size_bytes, self.max_size_mb):
            return False, f"File size exceeds maximum allowed size of {self.max_size_mb}MB"
        
        # Check file extension
        if self.allowed_extensions and not validate_file_type(filename, self.allowed_extensions):
            return False, f"File type not allowed. Allowed extensions: {', '.join(self.allowed_extensions)}"
        
        # Check MIME type
        if self.allowed_mime_types:
            mime_type = get_mime_type(filename)
            if mime_type not in self.allowed_mime_types:
                return False, f"File MIME type not allowed. Allowed types: {', '.join(self.allowed_mime_types)}"
        
        return True, None
    
    def is_valid(self, filename: str, size_bytes: int) -> bool:
        """
        Check if file is valid (convenience method).
        """
        valid, _ = self.validate(filename, size_bytes)
        return valid


# Common file validators
ImageValidator = FileValidator(
    max_size_mb=5.0,
    allowed_extensions=['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'],
    allowed_mime_types=['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml']
)

DocumentValidator = FileValidator(
    max_size_mb=20.0,
    allowed_extensions=['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.csv', '.rtf'],
    allowed_mime_types=[
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
)

VideoValidator = FileValidator(
    max_size_mb=100.0,
    allowed_extensions=['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv'],
    allowed_mime_types=['video/mp4', 'video/avi', 'video/quicktime', 'video/x-ms-wmv', 'video/webm', 'video/x-matroska']
)

AudioValidator = FileValidator(
    max_size_mb=50.0,
    allowed_extensions=['.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'],
    allowed_mime_types=['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/flac', 'audio/aac', 'audio/mp4']
)


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
