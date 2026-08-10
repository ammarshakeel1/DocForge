from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


DocumentStatus = Literal[
    "uploaded",
    "processing",
    "needs_review",
    "approved",
    "exported",
]


class LineItem(BaseModel):
    description: str = ""
    quantity: str = ""
    unit_price: str = ""
    amount: str = ""


class InvoiceExtraction(BaseModel):
    vendor: str = ""
    invoice_number: str = ""
    invoice_date: str = ""
    due_date: str = ""
    subtotal: str = ""
    tax: str = ""
    total: str = ""
    line_items: list[LineItem] = Field(default_factory=list)


class FieldConfidence(BaseModel):
    field_name: str
    confidence: float
    needs_review: bool = False
    reason: str | None = None


class ExtractionResult(BaseModel):
    invoice: InvoiceExtraction
    field_confidences: list[FieldConfidence]
    validation_errors: list[str] = Field(default_factory=list)


class DocumentOut(BaseModel):
    id: UUID
    file_path: str
    original_filename: str
    status: DocumentStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ExtractedFieldOut(BaseModel):
    id: UUID
    document_id: UUID
    field_name: str
    field_value: str | None = None
    confidence: float | None = None
    needs_review: bool = False
    reviewed_value: str | None = None
    created_at: datetime | None = None


class ReviewFieldUpdate(BaseModel):
    field_name: str
    reviewed_value: str


class ReviewRequest(BaseModel):
    fields: list[ReviewFieldUpdate] = Field(default_factory=list)
    approve: bool = False


class ReviewResponse(BaseModel):
    document: DocumentOut
    fields: list[ExtractedFieldOut]
    message: str


class HealthOut(BaseModel):
    status: str
    detail: dict[str, Any] = Field(default_factory=dict)
