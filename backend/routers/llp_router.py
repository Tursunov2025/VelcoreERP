import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from auth.deps import get_current_user
from database import get_db
from models import Document, DocumentFolder, DocumentReadStatus, ExportShipmentDocument, User
from routers.uploads_router import UPLOAD_DIR, _resolve_content_type, _safe_ext
from services.audit import log_action
from services.notifications import notify_event
from services.permissions import user_has_permission
from services.telegram import format_llp_important_alert

router = APIRouter(prefix="/llp", tags=["llp"])

LLP_DIR = UPLOAD_DIR / "llp"
LLP_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_LLP_EXT = {".pdf", ".docx", ".xlsx", ".xls", ".jpg", ".jpeg", ".png"}
MAX_LLP_SIZE = 15 * 1024 * 1024


class FolderCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None


class FolderUpdate(BaseModel):
    name: str


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    folder_id: Optional[int] = None
    is_important: Optional[bool] = None


def _require(db: Session, user: User, perm: str) -> None:
    if not user_has_permission(db, user, perm):
        raise HTTPException(status_code=403, detail=f"Permission required: {perm}")


def _serialize_folder(folder: DocumentFolder, doc_count: int = 0) -> dict:
    return {
        "id": folder.id,
        "name": folder.name,
        "parent_id": folder.parent_id,
        "created_by": folder.created_by,
        "created_at": folder.created_at,
        "document_count": doc_count,
    }


def _is_read(doc: Document, username: str) -> bool:
    return any(r.username == username for r in (doc.read_statuses or []))


def _serialize_document(doc: Document, username: str) -> dict:
    return {
        "id": doc.id,
        "folder_id": doc.folder_id,
        "folder_name": doc.folder.name if doc.folder else None,
        "title": doc.title,
        "description": doc.description or "",
        "url": doc.url,
        "filename": doc.filename,
        "original_filename": doc.original_filename,
        "content_type": doc.content_type,
        "file_size": doc.file_size,
        "is_important": bool(doc.is_important),
        "uploaded_by": doc.uploaded_by,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
        "is_read": _is_read(doc, username),
        "read_count": len(doc.read_statuses or []),
    }


def _save_llp_file(content: bytes, original_name: str | None) -> dict:
    ext = _safe_ext(original_name)
    if ext not in ALLOWED_LLP_EXT:
        raise HTTPException(status_code=400, detail="Invalid file type for LLP")
    LLP_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{ext}"
    filepath = LLP_DIR / stored_name
    filepath.write_bytes(content)
    if not filepath.is_file():
        raise HTTPException(status_code=500, detail="Failed to save file on disk")
    return {
        "url": f"/uploads/llp/{stored_name}",
        "filename": stored_name,
        "original_filename": original_name or stored_name,
        "content_type": _resolve_content_type(None, original_name),
    }


@router.get("/folders")
def list_folders(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "llp_view")
    folders = db.query(DocumentFolder).order_by(DocumentFolder.name).all()
    counts = {}
    for row in db.query(Document.folder_id, Document.id).all():
        if row.folder_id:
            counts[row.folder_id] = counts.get(row.folder_id, 0) + 1
    return {
        "folders": [
            _serialize_folder(f, counts.get(f.id, 0)) for f in folders
        ]
    }


@router.post("/folders")
def create_folder(
    data: FolderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "llp_upload")
    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Folder name required")
    if data.parent_id:
        parent = db.query(DocumentFolder).filter(DocumentFolder.id == data.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent folder not found")
    folder = DocumentFolder(
        name=name,
        parent_id=data.parent_id,
        created_by=user.username,
    )
    db.add(folder)
    log_action(db, user.username, "create", "document_folder", details=name)
    db.commit()
    db.refresh(folder)
    return _serialize_folder(folder)


@router.put("/folders/{folder_id}")
def update_folder(
    folder_id: int,
    data: FolderUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "llp_edit")
    folder = db.query(DocumentFolder).filter(DocumentFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Folder name required")
    folder.name = name
    log_action(db, user.username, "update", "document_folder", folder_id, name)
    db.commit()
    return _serialize_folder(folder)


@router.delete("/folders/{folder_id}")
def delete_folder(
    folder_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "llp_delete")
    folder = db.query(DocumentFolder).filter(DocumentFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    doc_count = db.query(Document).filter(Document.folder_id == folder_id).count()
    if doc_count:
        raise HTTPException(status_code=400, detail="Folder is not empty")
    db.delete(folder)
    log_action(db, user.username, "delete", "document_folder", folder_id)
    db.commit()
    return {"message": "Folder deleted"}


@router.get("/documents")
def list_documents(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    folder_id: Optional[int] = Query(None),
    q: str = Query(""),
    important_only: bool = Query(False),
    unread_only: bool = Query(False),
):
    _require(db, user, "llp_view")
    query = (
        db.query(Document)
        .options(selectinload(Document.folder), selectinload(Document.read_statuses))
        .order_by(Document.is_important.desc(), Document.created_at.desc())
    )
    if folder_id is not None:
        query = query.filter(Document.folder_id == folder_id)
    if important_only:
        query = query.filter(Document.is_important.is_(True))
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            Document.title.ilike(term)
            | Document.description.ilike(term)
            | Document.original_filename.ilike(term)
        )
    docs = query.all()
    result = [_serialize_document(d, user.username) for d in docs]
    if unread_only:
        result = [d for d in result if not d["is_read"]]
    return {"documents": result}


@router.post("/documents")
async def upload_document(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    file: UploadFile = File(...),
    title: str = Form(""),
    description: str = Form(""),
    folder_id: Optional[int] = Form(default=None),
    is_important: bool = Form(False),
):
    _require(db, user, "llp_upload")
    ext = _safe_ext(file.filename)
    if ext not in ALLOWED_LLP_EXT:
        raise HTTPException(
            status_code=400,
            detail="Allowed: PDF, DOCX, XLSX, XLS, JPG, PNG",
        )
    if folder_id is not None:
        folder = db.query(DocumentFolder).filter(DocumentFolder.id == folder_id).first()
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")

    content = await file.read()
    if len(content) > MAX_LLP_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 15MB)")

    saved = _save_llp_file(content, file.filename)
    doc_title = (title or "").strip() or saved["original_filename"]

    doc = Document(
        folder_id=folder_id,
        title=doc_title,
        description=description or "",
        url=saved["url"],
        filename=saved["filename"],
        original_filename=saved["original_filename"],
        content_type=saved["content_type"],
        file_size=len(content),
        is_important=bool(is_important),
        uploaded_by=user.username,
    )
    db.add(doc)
    db.flush()
    log_action(db, user.username, "upload", "document", doc.id, doc.title)
    db.commit()
    doc = (
        db.query(Document)
        .options(selectinload(Document.folder), selectinload(Document.read_statuses))
        .filter(Document.id == doc.id)
        .first()
    )

    if doc.is_important:
        await notify_event(db, "llp_important", format_llp_important_alert(doc, user.username))

    return _serialize_document(doc, user.username)


@router.put("/documents/{document_id}")
def update_document(
    document_id: int,
    data: DocumentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "llp_edit")
    doc = (
        db.query(Document)
        .options(selectinload(Document.folder), selectinload(Document.read_statuses))
        .filter(Document.id == document_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if data.title is not None:
        doc.title = data.title.strip() or doc.title
    if data.description is not None:
        doc.description = data.description
    if data.folder_id is not None:
        if data.folder_id:
            folder = db.query(DocumentFolder).filter(DocumentFolder.id == data.folder_id).first()
            if not folder:
                raise HTTPException(status_code=404, detail="Folder not found")
        doc.folder_id = data.folder_id
    if data.is_important is not None:
        doc.is_important = bool(data.is_important)
    doc.updated_at = datetime.utcnow()

    log_action(db, user.username, "update", "document", document_id, doc.title)
    db.commit()
    db.refresh(doc)
    return _serialize_document(doc, user.username)


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "llp_delete")
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    filepath = LLP_DIR / (doc.filename or "")
    db.query(ExportShipmentDocument).filter(
        ExportShipmentDocument.llp_document_id == document_id
    ).update({ExportShipmentDocument.llp_document_id: None}, synchronize_session=False)
    db.delete(doc)
    log_action(db, user.username, "delete", "document", document_id)
    db.commit()
    if filepath.exists():
        try:
            filepath.unlink()
        except OSError:
            pass
    return {"message": "Document deleted"}


@router.post("/documents/{document_id}/read")
def mark_document_read(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "llp_read_confirm")
    doc = (
        db.query(Document)
        .options(selectinload(Document.read_statuses))
        .filter(Document.id == document_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    existing = (
        db.query(DocumentReadStatus)
        .filter(
            DocumentReadStatus.document_id == document_id,
            DocumentReadStatus.username == user.username,
        )
        .first()
    )
    if existing:
        existing.read_at = datetime.utcnow()
    else:
        db.add(
            DocumentReadStatus(
                document_id=document_id,
                username=user.username,
            )
        )
    db.commit()
    doc = (
        db.query(Document)
        .options(selectinload(Document.folder), selectinload(Document.read_statuses))
        .filter(Document.id == document_id)
        .first()
    )
    return _serialize_document(doc, user.username)


@router.get("/documents/{document_id}/download")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require(db, user, "llp_download")
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    filepath = LLP_DIR / (doc.filename or "")
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found on server")
    from fastapi.responses import FileResponse

    return FileResponse(
        path=str(filepath),
        filename=doc.original_filename or doc.filename,
        media_type=doc.content_type or "application/octet-stream",
    )
