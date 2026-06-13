"""
utils/storage.py
----------------
File storage abstraction.
Currently saves to local filesystem under /tmp/sangatna/
Switch to S3 later by replacing these functions — nothing else changes.
"""

import os
import uuid
from pathlib import Path

# Local storage directory
UPLOAD_DIR = Path("/tmp/sangatna/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def save_upload(file_bytes: bytes, original_filename: str) -> str:
    """
    Save file bytes to local disk.
    Returns the file key (relative path) — same concept as an S3 key.
    """
    ext = Path(original_filename).suffix.lower()
    file_key = f"{uuid.uuid4()}{ext}"
    file_path = UPLOAD_DIR / file_key
    file_path.write_bytes(file_bytes)
    return file_key


def read_file(file_key: str) -> bytes:
    """Read file bytes by key."""
    file_path = UPLOAD_DIR / file_key
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_key}")
    return file_path.read_bytes()


def delete_object(file_key: str) -> None:
    """Delete a file by key."""
    file_path = UPLOAD_DIR / file_key
    if file_path.exists():
        file_path.unlink()


async def generate_presigned_url(file_key: str, expires_in: int = 3600) -> str:
    """
    In local dev, return a direct file path URL.
    In production this will return a real S3 presigned URL.
    """
    return f"http://localhost:8000/api/v1/documents/file/{file_key}"