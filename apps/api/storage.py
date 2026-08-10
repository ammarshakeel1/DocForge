"""Supabase Storage helpers.

The `invoices` bucket must be private. Clients never receive the service-role key;
they access files only via API signed URLs or streamed PDF responses.
"""

from uuid import uuid4

from fastapi import HTTPException, UploadFile

from config import get_settings
from db import get_supabase


def upload_pdf(file: UploadFile, contents: bytes) -> str:
    settings = get_settings()
    supabase = get_supabase()
    filename = file.filename or "invoice.pdf"
    path = f"{uuid4()}/{filename}"

    result = supabase.storage.from_(settings.supabase_storage_bucket).upload(
        path=path,
        file=contents,
        file_options={"content-type": "application/pdf", "upsert": "false"},
    )
    if getattr(result, "error", None):
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {result.error}")

    return path


def download_pdf(file_path: str) -> bytes:
    settings = get_settings()
    supabase = get_supabase()
    try:
        return supabase.storage.from_(settings.supabase_storage_bucket).download(file_path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=f"Could not download file: {exc}") from exc


def create_signed_url(file_path: str, expires_in: int = 3600) -> str:
    settings = get_settings()
    supabase = get_supabase()
    result = supabase.storage.from_(settings.supabase_storage_bucket).create_signed_url(
        file_path, expires_in
    )
    if isinstance(result, dict):
        url = result.get("signedURL") or result.get("signedUrl") or result.get("signed_url")
        if url:
            return url
    signed = getattr(result, "signed_url", None) or getattr(result, "signedURL", None)
    if signed:
        return signed
    raise HTTPException(status_code=500, detail="Could not create signed URL for PDF")
