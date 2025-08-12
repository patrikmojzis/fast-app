from pathlib import Path
from typing import Optional

from app.http_files.middlewares.auth_middleware import protected_route
from app.models.user import User
from quart import request, g, jsonify

from fast_app.core.storage import Storage
from fast_app.exceptions.http_exceptions import HttpException, UnauthorisedException, NotFoundException, \
    UnprocessableEntityException
from fast_app.utils.file_utils import get_mime_type, format_file_size, sanitize_filename


async def download(file_path: str):
    """
    Download a file using the pluggable Downloads standard.
    """
    secure_path = file_path.replace('..', '').strip('/')

    # Default disk
    disk_name = 'local'

    # Check existence early
    if not await Storage.disk(disk_name).exists(secure_path):
        raise NotFoundException(error_type="file_not_found")

    # Use unified Storage.download for a memory-optimized response
    return await Storage.download(secure_path, disk=disk_name, inline=False)


async def download_public(file_path: str):
    """
    Download a file from public storage (no authentication required).
    """
    try:
        # Security: Sanitize the file path
        secure_path = file_path.replace('..', '').strip('/')
        
        # Use public disk
        public_disk = Storage.disk('public')
        
        # Check if file exists
        if not await public_disk.exists(secure_path):
            raise NotFoundException(error_type="file_not_found")
        
        return await Storage.download(secure_path, disk='public', inline=False)
        
    except NotFoundException:
        raise


async def stream(file_path: str):
    """
    Stream a file for viewing (e.g., images, videos, PDFs).
    Sets appropriate headers for inline viewing.
    """
    try:
        # Security: Sanitize the file path
        secure_path = file_path.replace('..', '').strip('/')
        
        if not await Storage.exists(secure_path):
            raise NotFoundException(error_type="file_not_found")
        return await Storage.download(secure_path, disk='local', inline=True)
        
    except NotFoundException:
        raise


async def info(file_path: str):
    """
    Get file information without downloading.
    """
    try:
        # Security: Sanitize the file path
        secure_path = file_path.replace('..', '').strip('/')
        
        if not await Storage.exists(secure_path):
            raise NotFoundException(error_type="file_not_found")

        file_size = await Storage.size(secure_path)
        last_modified = await Storage.last_modified(secure_path)
        mime_type = get_mime_type(secure_path)
        filename = Path(secure_path).name

        return jsonify({
            'path': secure_path,
            'filename': filename,
            'size': file_size,
            'size_formatted': format_file_size(file_size),
            'mime_type': mime_type,
            'last_modified': last_modified.isoformat(),
            'exists': True
        })
        
    except NotFoundException:
        raise


async def upload():
    """
    Upload a file to storage.
    """
    try:
        from fast_app.utils.file_utils import generate_unique_filename, FileValidator
        
        # Get uploaded files
        files = await request.files
        if not files or 'file' not in files:
            raise UnprocessableEntityException(error_type="no_file_uploaded")
        
        uploaded_file = files['file']
        if not uploaded_file.filename:
            raise UnprocessableEntityException(error_type="no_file_selected")
        
        # Get upload parameters
        form = await request.form
        disk_name = form.get('disk', 'local')
        directory = form.get('directory', 'uploads')
        visibility = form.get('visibility', 'private')
        preserve_filename = form.get('preserve_filename', 'false').lower() == 'true'
        
        # Read file content
        file_content = uploaded_file.read()
        file_size = len(file_content)
        
        # Basic validation
        max_size_mb = 10.0  # 10MB default
        validator = FileValidator(max_size_mb=max_size_mb)
        is_valid, error = validator.validate(uploaded_file.filename, file_size)
        
        if not is_valid:
            raise UnprocessableEntityException(error_type="file_validation_failed", message=f"File validation failed: {error}")
        
        # Generate filename
        if preserve_filename:
            filename = sanitize_filename(uploaded_file.filename)
        else:
            filename = generate_unique_filename(uploaded_file.filename)
        
        # Build file path
        file_path = f"{directory.strip('/')}/{filename}"
        
        # Store file
        disk = Storage.disk(disk_name)
        stored_path = await disk.put(file_path, file_content, visibility)

        return jsonify({
            'success': True,
            'path': stored_path,
            'filename': filename,
            'original_filename': uploaded_file.filename,
            'size': file_size,
            'size_formatted': format_file_size(file_size),
            'mime_type': get_mime_type(filename),
            'disk': disk_name
        })
        
    except HttpException:
        raise


async def delete_file(file_path: str):
    """
    Delete a file from storage.
    """
    try:
        # Security: Sanitize the file path
        secure_path = file_path.replace('..', '').strip('/')
        
        # Check if file exists
        if not await Storage.exists(secure_path):
            raise NotFoundException(error_type="file_not_found")
        
        # Delete file
        success = await Storage.delete(secure_path)
        
        if not success:
            raise Exception(f"Failed to delete file {file_path}")
        
        return jsonify({
            'success': True,
            'message': f"File deleted: {file_path}"
        })
        
    except NotFoundException:
        raise


# Convenience function for user file access control
def _check_file_access(file_path: str, user: Optional[User] = None) -> bool:
    """
    Check if user has access to the file.
    Implement your own logic here based on your requirements.
    """
    # Example: Users can only access files in their own directory
    if user and file_path.startswith(f"users/{user.id}/"):
        return True
    
    # Example: Public files are accessible to everyone
    if file_path.startswith("public/"):
        return True
    
    # Example: Admin users can access everything
    if user and hasattr(user, 'is_admin') and user.is_admin:
        return True
    
    return False


async def download_user_file(file_path: str):
    """
    Download a file with user-specific access control.
    """
    user = getattr(g, 'user', None)
    
    if not _check_file_access(file_path, user):
        raise UnauthorisedException(error_type="access_denied_to_file")
    
    return await download(file_path)

