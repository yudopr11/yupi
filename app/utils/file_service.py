import logging
import boto3
from botocore.config import Config
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional
import uuid

from app.core.config import settings

logger = logging.getLogger(__name__)
from app.models.file import FileUpload
from app.utils.uuid import uuid7

ALLOWED_IMAGE_TYPES = {
    "image/jpeg", "image/png", "image/jpg", "image/webp", "image/gif",
    "application/pdf",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def get_s3_client():
    """Create an S3 client connected to RustFS."""
    endpoint = settings.RUSTFS_ENDPOINT
    if endpoint and not endpoint.startswith(("http://", "https://")):
        endpoint = f"http://{endpoint}"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.RUSTFS_ACCESS_KEY,
        aws_secret_access_key=settings.RUSTFS_SECRET_KEY,
        region_name=settings.RUSTFS_REGION,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket(s3_client, bucket: str):
    """Create bucket if it doesn't exist."""
    try:
        s3_client.head_bucket(Bucket=bucket)
    except s3_client.exceptions.ClientError:
        s3_client.create_bucket(Bucket=bucket)


def validate_file(file: UploadFile) -> None:
    """Validate file type and size."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{file.content_type}' not allowed. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}"
        )

    # Verify magic bytes match expected file signatures
    try:
        header = file.file.read(12)
        file.file.seek(0)
        valid_magic = (
            header[:3] == b'\xff\xd8\xff' or          # JPEG
            header[:4] == b'\x89PNG' or                # PNG
            (header[:4] == b'RIFF' and header[8:12] == b'WEBP') or  # WebP
            header[:4] == b'GIF8' or                   # GIF
            header[:5] == b'%PDF-'                     # PDF
        )
        if not valid_magic:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File content does not match a valid image or PDF format"
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unable to verify file content"
        )


def upload_file(
    db: Session,
    file: UploadFile,
    user_id: uuid.UUID,
    prefix: str = "receipts",
) -> FileUpload:
    """Upload a file to RustFS and create a DB record."""
    validate_file(file)

    ext = ""
    if file.filename and "." in file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower()

    file_id = uuid7()
    storage_key = f"uploads/{user_id}/{prefix}/{file_id}{ext}"
    bucket = settings.RUSTFS_BUCKET

    # Check file size before reading into memory
    file.file.seek(0, 2)  # seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # seek back to start
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)}MB"
        )

    # Read file content
    content = file.file.read()

    # Upload to RustFS
    s3 = get_s3_client()
    ensure_bucket(s3, bucket)
    s3.put_object(
        Bucket=bucket,
        Key=storage_key,
        Body=content,
        ContentType=file.content_type or "application/octet-stream",
    )

    # Create DB record
    file_upload = FileUpload(
        id=file_id,
        user_id=user_id,
        filename=storage_key.rsplit("/", 1)[-1],
        original_filename=file.filename or "unknown",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        storage_key=storage_key,
        bucket=bucket,
        is_orphan=False,
    )
    db.add(file_upload)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflict")
    except Exception:
        db.rollback()
        raise
    db.refresh(file_upload)
    return file_upload


def _stream_body(body):
    try:
        for chunk in body.iter_chunks(chunk_size=8192):
            yield chunk
    finally:
        body.close()


def download_file(file_upload: FileUpload):
    """Download a file from RustFS. Returns a generator that auto-closes the body."""
    s3 = get_s3_client()
    response = s3.get_object(Bucket=file_upload.bucket, Key=file_upload.storage_key)
    return _stream_body(response["Body"])


def delete_file_from_storage(storage_key: str, bucket: str) -> None:
    """Delete a file from RustFS."""
    s3 = get_s3_client()
    try:
        s3.delete_object(Bucket=bucket, Key=storage_key)
    except Exception:
        logger.warning(f"Failed to delete file from S3: {storage_key}", exc_info=True)


def mark_orphan(db: Session, file_upload_id: uuid.UUID) -> Optional[FileUpload]:
    """Mark a file as orphaned. Caller must commit."""
    file_upload = db.query(FileUpload).filter(FileUpload.id == file_upload_id).first()
    if file_upload:
        file_upload.is_orphan = True
        file_upload.deleted_at = datetime.now(timezone.utc)
    return file_upload


def cleanup_orphans(db: Session) -> list[dict]:
    """Delete all orphaned files from storage and DB. Returns list of deleted files."""
    orphans = db.query(FileUpload).filter(FileUpload.is_orphan == True).all()
    deleted = []
    for f in orphans:
        deleted.append({
            "id": str(f.id),
            "storage_key": f.storage_key,
            "bucket": f.bucket,
            "original_filename": f.original_filename,
        })
        db.delete(f)

    # Commit DB deletions first so orphan markers are removed even if S3 fails
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflict")
    except Exception:
        db.rollback()
        raise

    # Then attempt S3 cleanup — log failures but don't rollback the DB
    for entry in deleted:
        try:
            delete_file_from_storage(entry["storage_key"], entry["bucket"])
        except Exception:
            logger.warning(f"Failed to delete orphaned file from S3: {entry['storage_key']}", exc_info=True)

    return deleted
