import json
import logging
from typing import Any

from openai import OpenAI

from config import get_settings
from extract.validate import validate_invoice
from schemas import ExtractionResult, InvoiceExtraction, LineItem

logger = logging.getLogger(__name__)

INVOICE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "vendor": {"type": "string"},
        "invoice_number": {"type": "string"},
        "invoice_date": {"type": "string", "description": "Prefer YYYY-MM-DD"},
        "due_date": {"type": "string", "description": "Prefer YYYY-MM-DD"},
        "subtotal": {"type": "string", "description": "Numeric string, no currency symbol preferred"},
        "tax": {"type": "string"},
        "total": {"type": "string"},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "description": {"type": "string"},
                    "quantity": {"type": "string"},
                    "unit_price": {"type": "string"},
                    "amount": {"type": "string"},
                },
                "required": ["description", "quantity", "unit_price", "amount"],
            },
        },
        "field_confidence": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "vendor": {"type": "number"},
                "invoice_number": {"type": "number"},
                "invoice_date": {"type": "number"},
                "due_date": {"type": "number"},
                "subtotal": {"type": "number"},
                "tax": {"type": "number"},
                "total": {"type": "number"},
                "line_items": {"type": "number"},
            },
            "required": [
                "vendor",
                "invoice_number",
                "invoice_date",
                "due_date",
                "subtotal",
                "tax",
                "total",
                "line_items",
            ],
        },
    },
    "required": [
        "vendor",
        "invoice_number",
        "invoice_date",
        "due_date",
        "subtotal",
        "tax",
        "total",
        "line_items",
        "field_confidence",
    ],
}


def extract_invoice_fields(document_text: str) -> ExtractionResult:
    settings = get_settings()
    settings.require_openai()

    client = OpenAI(api_key=settings.openai_api_key)
    system = (
        "You extract invoice fields from document text. "
        "Return only values present or clearly implied by the text. "
        "Use YYYY-MM-DD for dates when possible. "
        "Money fields should be plain numeric strings. "
        "field_confidence values must be between 0 and 1."
    )
    user = f"Extract invoice data from this document text:\n\n{document_text[:12000]}"

    response = client.chat.completions.create(
        model=settings.openai_model,
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "invoice_extraction",
                "strict": True,
                "schema": INVOICE_JSON_SCHEMA,
            },
        },
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )

    content = response.choices[0].message.content or "{}"
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        logger.error("OpenAI returned invalid JSON: %s", content)
        raise RuntimeError("OpenAI returned invalid JSON") from exc

    confidence_map = {
        key: float(value)
        for key, value in (payload.get("field_confidence") or {}).items()
    }
    invoice = InvoiceExtraction(
        vendor=str(payload.get("vendor") or ""),
        invoice_number=str(payload.get("invoice_number") or ""),
        invoice_date=str(payload.get("invoice_date") or ""),
        due_date=str(payload.get("due_date") or ""),
        subtotal=str(payload.get("subtotal") or ""),
        tax=str(payload.get("tax") or ""),
        total=str(payload.get("total") or ""),
        line_items=[
            LineItem(
                description=str(item.get("description") or ""),
                quantity=str(item.get("quantity") or ""),
                unit_price=str(item.get("unit_price") or ""),
                amount=str(item.get("amount") or ""),
            )
            for item in (payload.get("line_items") or [])
            if isinstance(item, dict)
        ],
    )

    errors, confidences = validate_invoice(
        invoice,
        llm_confidences=confidence_map,
        threshold=settings.confidence_threshold,
    )
    return ExtractionResult(
        invoice=invoice,
        field_confidences=confidences,
        validation_errors=errors,
    )
