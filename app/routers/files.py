from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import re
import uuid

from app.utils.database import get_db
from app.utils.auth import get_non_guest_user, get_non_guest_superuser
from app.models.auth import User
from app.models.file import FileUpload
from app.utils.file_service import download_file, mark_orphan, cleanup_orphans

router = APIRouter(
    prefix="/files",
    tags=["Files"]
)


@router.get("/{file_id}")
def get_file(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_non_guest_user),
):
    """Download a file. Only the owner can access."""
    file_upload = db.query(FileUpload).filter(FileUpload.id == file_id).first()
    if not file_upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    if file_upload.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if file_upload.is_orphan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File has been deleted")

    body = download_file(file_upload)
    return StreamingResponse(
        body,
        media_type=file_upload.content_type,
        headers={"Content-Disposition": f'inline; filename="{re.sub(r"[^\w.\-]", "_", file_upload.original_filename)}"'},
    )


@router.delete("/{file_id}")
def delete_file(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_non_guest_user),
):
    """Mark a file as orphaned (soft delete)."""
    file_upload = db.query(FileUpload).filter(FileUpload.id == file_id).first()
    if not file_upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    if file_upload.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    mark_orphan(db, file_id)
    db.commit()
    return {"message": "File marked for deletion", "file_id": str(file_id)}


@router.post("/cleanup-orphans")
def cleanup(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_non_guest_superuser),
):
    """Delete all orphaned files from storage and DB. Superuser only."""
    deleted = cleanup_orphans(db)
    return {"message": f"Cleaned up {len(deleted)} orphaned files", "deleted": deleted}
