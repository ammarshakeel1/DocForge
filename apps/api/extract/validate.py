import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Mapping

from schemas import FieldConfidence, InvoiceExtraction, LineItem

DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y")
REQUIRED_FIELDS = (
    "vendor",
    "invoice_number",
    "invoice_date",
    "due_date",
    "subtotal",
    "tax",
    "total",
)
MONEY_FIELDS = ("subtotal", "tax", "total")
CONFIDENCE_THRESHOLD = 0.8


def parse_money(value: str | None) -> Decimal | None:
    if value is None:
        return None
    cleaned = (
        str(value)
        .strip()
        .replace("$", "")
        .replace(",", "")
        .replace("USD", "")
        .strip()
    )
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_date(value: str | None) -> datetime | None:
    if not value or not str(value).strip():
        return None
    raw = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def validate_invoice(
    invoice: InvoiceExtraction,
    llm_confidences: dict[str, float] | None = None,
    threshold: float = CONFIDENCE_THRESHOLD,
) -> tuple[list[str], list[FieldConfidence]]:
    errors: list[str] = []
    llm_confidences = llm_confidences or {}
    confidences: list[FieldConfidence] = []

    values = invoice.model_dump()
    for field in REQUIRED_FIELDS:
        value = values.get(field, "")
        base = float(llm_confidences.get(field, 0.9 if value else 0.2))
        reason = None
        if not value or not str(value).strip():
            errors.append(f"Missing required field: {field}")
            base = min(base, 0.3)
            reason = "missing"
        elif field in ("invoice_date", "due_date") and parse_date(str(value)) is None:
            errors.append(f"Unparseable date for {field}: {value}")
            base = min(base, 0.4)
            reason = "invalid_date"
        elif field in MONEY_FIELDS and parse_money(str(value)) is None:
            errors.append(f"Unparseable amount for {field}: {value}")
            base = min(base, 0.4)
            reason = "invalid_amount"

        confidences.append(
            FieldConfidence(
                field_name=field,
                confidence=base,
                needs_review=base < threshold,
                reason=reason,
            )
        )

    subtotal = parse_money(invoice.subtotal)
    tax = parse_money(invoice.tax)
    total = parse_money(invoice.total)
    if subtotal is not None and tax is not None and total is not None:
        expected = subtotal + tax
        if abs(expected - total) > Decimal("0.05"):
            errors.append(
                f"Totals mismatch: subtotal ({subtotal}) + tax ({tax}) != total ({total})"
            )
            for item in confidences:
                if item.field_name in MONEY_FIELDS:
                    item.confidence = min(item.confidence, 0.5)
                    item.needs_review = True
                    item.reason = "totals_mismatch"
        else:
            for item in confidences:
                if item.field_name in MONEY_FIELDS and item.reason is None:
                    item.confidence = max(item.confidence, 0.92)
                    item.needs_review = item.confidence < threshold

    # Line items as a JSON-ish string field for storage
    line_conf = float(llm_confidences.get("line_items", 0.85 if invoice.line_items else 0.4))
    if not invoice.line_items:
        errors.append("No line items extracted")
        line_conf = min(line_conf, 0.4)
    confidences.append(
        FieldConfidence(
            field_name="line_items",
            confidence=line_conf,
            needs_review=line_conf < threshold,
            reason=None if invoice.line_items else "missing",
        )
    )

    return errors, confidences


def validate_required_field_values(values: Mapping[str, str]) -> list[str]:
    """Validate final (reviewed or extracted) values before approve/export."""
    invoice = InvoiceExtraction(
        vendor=values.get("vendor", ""),
        invoice_number=values.get("invoice_number", ""),
        invoice_date=values.get("invoice_date", ""),
        due_date=values.get("due_date", ""),
        subtotal=values.get("subtotal", ""),
        tax=values.get("tax", ""),
        total=values.get("total", ""),
        line_items=_parse_line_items_json(values.get("line_items", "")),
    )
    errors, _confidences = validate_invoice(invoice)
    return errors


def _parse_line_items_json(raw: str) -> list[LineItem]:
    if not raw or not str(raw).strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    items: list[LineItem] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        items.append(
            LineItem(
                description=str(item.get("description") or ""),
                quantity=str(item.get("quantity") or ""),
                unit_price=str(item.get("unit_price") or ""),
                amount=str(item.get("amount") or ""),
            )
        )
    return items
