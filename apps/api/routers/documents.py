import csv
import io
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse

from config import get_settings
from db import get_supabase
from extract.llm import extract_invoice_fields
from extract.text import extract_text_from_pdf
from extract.validate import validate_required_field_values
from schemas import (
    DocumentOut,
    ExtractedFieldOut,
    ReviewRequest,
    ReviewResponse,
)
from status_flow import (
    APPROVE_FROM,
    EXPORT_FROM,
    EXTRACT_FROM,
    REVIEW_FROM,
    assert_status_in,
    can_transition,
)
from storage import create_signed_url, download_pdf, upload_pdf

router = APIRouter(prefix="/documents", tags=["documents"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_document(row: dict[str, Any]) -> DocumentOut:
    return DocumentOut(
        id=row["id"],
        file_path=row["file_path"],
        original_filename=row["original_filename"],
        status=row["status"],
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _row_to_field(row: dict[str, Any]) -> ExtractedFieldOut:
    return ExtractedFieldOut(
        id=row["id"],
        document_id=row["document_id"],
        field_name=row["field_name"],
        field_value=row.get("field_value"),
        confidence=float(row["confidence"]) if row.get("confidence") is not None else None,
        needs_review=bool(row.get("needs_review")),
        reviewed_value=row.get("reviewed_value"),
        created_at=row.get("created_at"),
    )


def _get_document_or_404(document_id: UUID) -> dict[str, Any]:
    supabase = get_supabase()
    result = (
        supabase.table("documents")
        .select("*")
        .eq("id", str(document_id))
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Document not found")
    return result.data[0]


def _set_status(document_id: UUID, current: str, target: str) -> None:
    if not can_transition(current, target):
        raise HTTPException(
            status_code=409,
            detail=f"Invalid status transition: {current} → {target}",
        )
    supabase = get_supabase()
    supabase.table("documents").update(
        {"status": target, "updated_at": _now_iso()}
    ).eq("id", str(document_id)).execute()


def _get_fields(document_id: UUID) -> list[ExtractedFieldOut]:
    supabase = get_supabase()
    result = (
        supabase.table("extracted_fields")
        .select("*")
        .eq("document_id", str(document_id))
        .order("created_at")
        .execute()
    )
    return [_row_to_field(row) for row in (result.data or [])]


def _final_field_values(
    fields: list[ExtractedFieldOut],
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    overrides = overrides or {}
    values: dict[str, str] = {}
    for field in fields:
        if field.field_name in overrides:
            values[field.field_name] = overrides[field.field_name]
        elif field.reviewed_value not in (None, ""):
            values[field.field_name] = field.reviewed_value
        else:
            values[field.field_name] = field.field_value or ""
    for key, value in overrides.items():
        values.setdefault(key, value)
    return values


def _invoice_to_field_rows(
    document_id: str,
    invoice_dict: dict[str, Any],
    confidences: list[Any],
) -> list[dict[str, Any]]:
    conf_map = {c.field_name: c for c in confidences}
    rows: list[dict[str, Any]] = []
    for field_name, value in invoice_dict.items():
        if field_name == "line_items":
            serialized = json.dumps(value)
        else:
            serialized = str(value) if value is not None else ""
        conf = conf_map.get(field_name)
        rows.append(
            {
                "document_id": document_id,
                "field_name": field_name,
                "field_value": serialized,
                "confidence": conf.confidence if conf else 0.5,
                "needs_review": conf.needs_review if conf else True,
                "reviewed_value": None,
            }
        )
    return rows


@router.post("", response_model=DocumentOut)
async def upload_document(file: UploadFile = File(...)) -> DocumentOut:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported in v0.1")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")

    file_path = upload_pdf(file, contents)
    supabase = get_supabase()
    insert = (
        supabase.table("documents")
        .insert(
            {
                "file_path": file_path,
                "original_filename": file.filename,
                "status": "uploaded",
                "updated_at": _now_iso(),
            }
        )
        .execute()
    )
    if not insert.data:
        raise HTTPException(status_code=500, detail="Failed to create document row")
    return _row_to_document(insert.data[0])


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: UUID) -> DocumentOut:
    return _row_to_document(_get_document_or_404(document_id))


@router.post("/{document_id}/extract")
def extract_document(document_id: UUID) -> dict[str, Any]:
    settings = get_settings()
    doc = _get_document_or_404(document_id)
    previous_status = doc["status"]

    try:
        assert_status_in(previous_status, EXTRACT_FROM, "extract")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    supabase = get_supabase()
    _set_status(document_id, previous_status, "processing")

    try:
        pdf_bytes = download_pdf(doc["file_path"])
        text_result = extract_text_from_pdf(pdf_bytes)

        if not text_result.text.strip():
            error = text_result.error or "Could not extract text from PDF."
            _set_status(document_id, "processing", "needs_review")
            supabase.table("review_events").insert(
                {
                    "document_id": str(document_id),
                    "action": "extract_failed",
                    "payload": {
                        "method": text_result.method,
                        "error": error,
                    },
                }
            ).execute()
            updated = _get_document_or_404(document_id)
            return {
                "document": _row_to_document(updated),
                "fields": _get_fields(document_id),
                "validation_errors": [error],
                "extraction_method": text_result.method,
                "error": error,
            }

        result = extract_invoice_fields(text_result.text)
        invoice_dict = result.invoice.model_dump()
        rows = _invoice_to_field_rows(str(document_id), invoice_dict, result.field_confidences)

        upserted = (
            supabase.table("extracted_fields")
            .upsert(rows, on_conflict="document_id,field_name")
            .execute()
        )

        needs_review = any(c.needs_review for c in result.field_confidences) or bool(
            result.validation_errors
        )
        target_status = "needs_review" if needs_review else "approved"
        _set_status(document_id, "processing", target_status)

        supabase.table("review_events").insert(
            {
                "document_id": str(document_id),
                "action": "extract",
                "payload": {
                    "method": text_result.method,
                    "validation_errors": result.validation_errors,
                    "threshold": settings.confidence_threshold,
                },
            }
        ).execute()

        updated = _get_document_or_404(document_id)
        return {
            "document": _row_to_document(updated),
            "fields": [_row_to_field(row) for row in (upserted.data or [])]
            or _get_fields(document_id),
            "validation_errors": result.validation_errors,
            "extraction_method": text_result.method,
            "error": None,
        }
    except HTTPException:
        # Roll hard failures back toward a non-processing state.
        rollback = previous_status if previous_status in EXTRACT_FROM else "uploaded"
        if can_transition("processing", rollback):
            _set_status(document_id, "processing", rollback)
        raise
    except Exception as exc:  # noqa: BLE001
        rollback = previous_status if previous_status in EXTRACT_FROM else "uploaded"
        if can_transition("processing", rollback):
            _set_status(document_id, "processing", rollback)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {exc}") from exc


@router.get("/{document_id}/fields", response_model=list[ExtractedFieldOut])
def get_fields(document_id: UUID) -> list[ExtractedFieldOut]:
    _get_document_or_404(document_id)
    return _get_fields(document_id)


@router.post("/{document_id}/review", response_model=ReviewResponse)
def review_document(document_id: UUID, body: ReviewRequest) -> ReviewResponse:
    doc = _get_document_or_404(document_id)
    current = doc["status"]
    supabase = get_supabase()

    try:
        if body.approve:
            assert_status_in(current, APPROVE_FROM, "approve")
        else:
            assert_status_in(current, REVIEW_FROM, "review")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    for update in body.fields:
        (
            supabase.table("extracted_fields")
            .update(
                {
                    "reviewed_value": update.reviewed_value,
                    "needs_review": False,
                }
            )
            .eq("document_id", str(document_id))
            .eq("field_name", update.field_name)
            .execute()
        )

    fields = _get_fields(document_id)
    overrides = {item.field_name: item.reviewed_value for item in body.fields}
    final_values = _final_field_values(fields, overrides)

    if body.approve:
        errors = validate_required_field_values(final_values)
        if errors:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Cannot approve until required fields are valid.",
                    "validation_errors": errors,
                },
            )
        if current != "approved":
            _set_status(document_id, current, "approved")
        else:
            supabase.table("documents").update({"updated_at": _now_iso()}).eq(
                "id", str(document_id)
            ).execute()
    else:
        if current != "needs_review":
            _set_status(document_id, current, "needs_review")
        else:
            supabase.table("documents").update({"updated_at": _now_iso()}).eq(
                "id", str(document_id)
            ).execute()

    supabase.table("review_events").insert(
        {
            "document_id": str(document_id),
            "action": "approve" if body.approve else "edit",
            "payload": body.model_dump(),
        }
    ).execute()

    updated = _row_to_document(_get_document_or_404(document_id))
    fields = _get_fields(document_id)
    return ReviewResponse(
        document=updated,
        fields=fields,
        message="approved" if body.approve else "review saved",
    )


def _require_exportable(document_id: UUID) -> list[ExtractedFieldOut]:
    doc = _get_document_or_404(document_id)
    try:
        assert_status_in(doc["status"], EXPORT_FROM, "export")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    fields = _get_fields(document_id)
    if not fields:
        raise HTTPException(status_code=400, detail="No extracted fields to export")

    errors = validate_required_field_values(_final_field_values(fields))
    if errors:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Cannot export until required fields are valid. Approve the document first.",
                "validation_errors": errors,
            },
        )
    return fields


@router.get("/{document_id}/export.csv")
def export_csv(document_id: UUID) -> StreamingResponse:
    fields = _require_exportable(document_id)
    doc = _get_document_or_404(document_id)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["field_name", "value", "confidence", "needs_review", "source"])
    for field in fields:
        value = (
            field.reviewed_value
            if field.reviewed_value is not None and field.reviewed_value != ""
            else field.field_value or ""
        )
        source = "reviewed" if field.reviewed_value not in (None, "") else "extracted"
        writer.writerow(
            [
                field.field_name,
                value,
                field.confidence if field.confidence is not None else "",
                field.needs_review,
                source,
            ]
        )

    supabase = get_supabase()
    _set_status(document_id, doc["status"], "exported")
    supabase.table("review_events").insert(
        {
            "document_id": str(document_id),
            "action": "export_csv",
            "payload": {"field_count": len(fields)},
        }
    ).execute()

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="document-{document_id}.csv"'
        },
    )


@router.get("/{document_id}/export.json")
def export_json(document_id: UUID) -> Response:
    fields = _require_exportable(document_id)
    doc = _get_document_or_404(document_id)

    payload: dict[str, Any] = {}
    for field in fields:
        value = (
            field.reviewed_value
            if field.reviewed_value is not None and field.reviewed_value != ""
            else field.field_value or ""
        )
        if field.field_name == "line_items":
            try:
                payload[field.field_name] = json.loads(value) if value else []
            except json.JSONDecodeError:
                payload[field.field_name] = value
        else:
            payload[field.field_name] = value

    supabase = get_supabase()
    _set_status(document_id, doc["status"], "exported")
    supabase.table("review_events").insert(
        {
            "document_id": str(document_id),
            "action": "export_json",
            "payload": {"field_count": len(fields)},
        }
    ).execute()

    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="document-{document_id}.json"'
        },
    )


@router.get("/{document_id}/file")
def get_file_url(document_id: UUID) -> dict[str, str]:
    """Return a short-lived signed URL for the private Storage object."""
    doc = _get_document_or_404(document_id)
    url = create_signed_url(doc["file_path"])
    return {"url": url, "expires_in": "3600"}


@router.get("/{document_id}/file.pdf")
def get_file_pdf(document_id: UUID) -> Response:
    """Stream PDF bytes through the API (preferred for private buckets)."""
    doc = _get_document_or_404(document_id)
    pdf_bytes = download_pdf(doc["file_path"])
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{doc["original_filename"]}"'
        },
    )
