#!/usr/bin/env python3
"""Generate 3 synthetic invoice PDFs + ground-truth JSON. Never use real client docs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from faker import Faker
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "samples" / "invoices"

fake = Faker()
Faker.seed(42)


def _money(value: float) -> str:
    return f"{value:.2f}"


def build_invoice(seed_offset: int, messy: bool = False) -> dict:
    Faker.seed(42 + seed_offset)
    vendor = fake.company()
    invoice_number = f"INV-{fake.random_int(1000, 9999)}"
    invoice_date = fake.date_between(start_date="-60d", end_date="-5d")
    due_date = fake.date_between(start_date=invoice_date, end_date="+30d")

    line_items = []
    subtotal = 0.0
    for _ in range(fake.random_int(2, 4)):
        qty = fake.random_int(1, 8)
        unit = round(fake.pyfloat(left_digits=3, right_digits=2, positive=True, min_value=12, max_value=240), 2)
        amount = round(qty * unit, 2)
        subtotal += amount
        line_items.append(
            {
                "description": fake.bs().title(),
                "quantity": str(qty),
                "unit_price": _money(unit),
                "amount": _money(amount),
            }
        )

    subtotal = round(subtotal, 2)
    tax = round(subtotal * 0.08, 2)
    total = round(subtotal + tax, 2)

    return {
        "vendor": vendor,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date.isoformat(),
        "due_date": due_date.isoformat(),
        "subtotal": _money(subtotal),
        "tax": _money(tax),
        "total": _money(total),
        "line_items": line_items,
        "bill_to": {
            "name": "Northstar Accounting",
            "address": fake.address().replace("\n", ", "),
        },
        "messy": messy,
    }


def draw_clean_invoice(path: Path, data: dict) -> None:
    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    y = height - inch

    c.setFont("Helvetica-Bold", 18)
    c.drawString(inch, y, data["vendor"])
    y -= 0.35 * inch
    c.setFont("Helvetica", 11)
    c.drawString(inch, y, "INVOICE")
    y -= 0.4 * inch

    c.setFont("Helvetica", 10)
    c.drawString(inch, y, f"Invoice Number: {data['invoice_number']}")
    y -= 0.22 * inch
    c.drawString(inch, y, f"Invoice Date: {data['invoice_date']}")
    y -= 0.22 * inch
    c.drawString(inch, y, f"Due Date: {data['due_date']}")
    y -= 0.4 * inch

    c.setFont("Helvetica-Bold", 10)
    c.drawString(inch, y, "Bill To:")
    y -= 0.22 * inch
    c.setFont("Helvetica", 10)
    c.drawString(inch, y, data["bill_to"]["name"])
    y -= 0.22 * inch
    c.drawString(inch, y, data["bill_to"]["address"][:80])
    y -= 0.45 * inch

    # Table header
    c.setFillColor(colors.HexColor("#1f2937"))
    c.rect(inch, y - 0.05 * inch, width - 2 * inch, 0.28 * inch, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(inch + 0.1 * inch, y, "Description")
    c.drawString(4.2 * inch, y, "Qty")
    c.drawString(5.0 * inch, y, "Unit Price")
    c.drawString(6.3 * inch, y, "Amount")
    y -= 0.35 * inch
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 9)

    for item in data["line_items"]:
        c.drawString(inch + 0.1 * inch, y, item["description"][:42])
        c.drawString(4.2 * inch, y, item["quantity"])
        c.drawRightString(5.8 * inch, y, f"${item['unit_price']}")
        c.drawRightString(7.0 * inch, y, f"${item['amount']}")
        y -= 0.25 * inch

    y -= 0.2 * inch
    c.setFont("Helvetica", 10)
    c.drawRightString(7.0 * inch, y, f"Subtotal: ${data['subtotal']}")
    y -= 0.22 * inch
    c.drawRightString(7.0 * inch, y, f"Tax: ${data['tax']}")
    y -= 0.22 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(7.0 * inch, y, f"Total: ${data['total']}")

    c.showPage()
    c.save()


def draw_messy_invoice(path: Path, data: dict) -> None:
    """Sparse / uneven layout to exercise extraction robustness (still text-layer PDF)."""
    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter

    c.setFont("Courier", 9)
    c.drawString(0.7 * inch, height - 0.8 * inch, data["vendor"].upper())
    c.setFont("Courier-Bold", 14)
    c.drawString(4.8 * inch, height - 1.1 * inch, "BILL")
    c.setFont("Courier", 9)
    c.drawString(0.7 * inch, height - 1.4 * inch, f"#{data['invoice_number']}")
    c.drawString(0.7 * inch, height - 1.65 * inch, f"dated {data['invoice_date']}")
    c.drawString(4.5 * inch, height - 1.65 * inch, f"pay by {data['due_date']}")

    c.drawString(0.7 * inch, height - 2.2 * inch, f"Customer: {data['bill_to']['name']}")

    y = height - 2.8 * inch
    for item in data["line_items"]:
        c.drawString(0.8 * inch, y, f"- {item['description']}")
        c.drawString(
            0.9 * inch,
            y - 0.18 * inch,
            f"  {item['quantity']} x ${item['unit_price']} = ${item['amount']}",
        )
        y -= 0.45 * inch

    c.setFont("Courier-Bold", 10)
    c.drawString(0.7 * inch, y - 0.3 * inch, f"SUB {data['subtotal']}  TAX {data['tax']}  TOTAL DUE ${data['total']}")
    c.setFont("Courier", 8)
    c.drawString(0.7 * inch, 0.8 * inch, "Thank you — remittance to AP@example.test")
    # Decorative noise lines (still selectable text elsewhere)
    c.setStrokeColor(colors.grey)
    c.line(0.5 * inch, height - 2.0 * inch, width - 0.5 * inch, height - 2.05 * inch)

    c.showPage()
    c.save()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    specs = [
        ("invoice_001", 1, False),
        ("invoice_002", 2, False),
        ("invoice_003", 3, True),
    ]

    for name, offset, messy in specs:
        data = build_invoice(offset, messy=messy)
        pdf_path = OUT_DIR / f"{name}.pdf"
        truth_path = OUT_DIR / f"{name}.json"
        if messy:
            draw_messy_invoice(pdf_path, data)
        else:
            draw_clean_invoice(pdf_path, data)

        truth = {
            "vendor": data["vendor"],
            "invoice_number": data["invoice_number"],
            "invoice_date": data["invoice_date"],
            "due_date": data["due_date"],
            "subtotal": data["subtotal"],
            "tax": data["tax"],
            "total": data["total"],
            "line_items": data["line_items"],
        }
        truth_path.write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {pdf_path.relative_to(ROOT)} and {truth_path.relative_to(ROOT)}")

    print("Done. Generated 3 synthetic invoices (no real client documents).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
