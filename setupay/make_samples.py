"""Generate fictional sample documents for SetuPay demos.

Creates three self-contained scenarios in ``samples/`` using every supported
format (PDF, DOCX, TXT, CSV, XLSX). All data is fictional.

Usage:  python make_samples.py
"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).parent / "samples"


# --------------------------------------------------------------------------- #
# Writers
# --------------------------------------------------------------------------- #

def write_txt(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_pdf(path: Path, title: str, lines: list[str]) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        str(path), pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm,
        title=title,
    )
    story = [Paragraph(f"<b>{title}</b>", styles["Title"]), Spacer(1, 8)]
    for line in lines:
        if line == "":
            story.append(Spacer(1, 6))
        else:
            story.append(Paragraph(line.replace("&", "&amp;").replace("<", "&lt;"), styles["BodyText"]))
    doc.build(story)


def write_docx(path: Path, title: str, lines: list[str]) -> None:
    from docx import Document

    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_heading(title, level=1)
    for line in lines:
        if line == "":
            continue
        document.add_paragraph(line)
    document.save(str(path))


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def write_xlsx(path: Path, header: list[str], rows: list[list]) -> None:
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=header).to_excel(path, index=False)


# --------------------------------------------------------------------------- #
# Scenario 1: the exact case from the project guide (48,000 vs 45,000)
# --------------------------------------------------------------------------- #

def scenario_guide_case() -> None:
    folder = ROOT / "guide_case"

    write_pdf(
        folder / "01_invoice.pdf",
        "INVOICE",
        [
            "Invoice Number : INV-2026-0042",
            "Invoice Date   : 2026-08-01",
            "Payment Terms  : Net 30",
            "Due Date       : 2026-08-31",
            "",
            "Supplier : Sunrise Components Pvt Ltd",
            "Buyer    : Meridian Traders LLP",
            "",
            "Line items",
            "Industrial fasteners, batch 12      500 units",
            "Against purchase order: PO-2026-0117",
            "",
            "Invoice Total : INR 48,000",
        ],
    )
    write_docx(
        folder / "02_purchase_order.docx",
        "PURCHASE ORDER",
        [
            "Purchase Order Number : PO-2026-0117",
            "Order Date            : 2026-07-25",
            "Buyer                 : Meridian Traders LLP",
            "Supplier              : Sunrise Components Pvt Ltd",
            "Currency              : INR",
            "",
            "Item                   Quantity",
            "Industrial fasteners   500 units",
            "",
            "Purchase Order Total : INR 45,000",
        ],
    )
    write_txt(
        folder / "03_delivery_receipt.txt",
        """\
DELIVERY RECEIPT
Delivery Receipt Number : DR-2026-0088
Delivery Date           : 2026-08-05
Received By             : Meridian Traders LLP (Warehouse 2)
Delivered By            : Sunrise Components Pvt Ltd
Against Purchase Order  : PO-2026-0117

Item                    Ordered      Received
Industrial fasteners    500 units    500 units

Condition on receipt : Good, sealed packaging intact.
""",
    )
    write_txt(
        folder / "04_email_correspondence.txt",
        """\
From: accounts@meridiantraders.example
To: billing@sunrisecomponents.example
Date: 2026-09-04
Subject: Re: Invoice INV-2026-0042

Hello,

Thank you for the fasteners delivered on 2026-08-05.

We note that invoice INV-2026-0042 shows a total of INR 48,000, while our
purchase order PO-2026-0117 was raised for INR 45,000. Please clarify the
difference of INR 3,000.

A part payment was released earlier this month. The remaining balance is
pending internal approval on our side.

Regards,
Accounts, Meridian Traders LLP
""",
    )
    write_xlsx(
        folder / "05_payment_ledger.xlsx",
        ["date", "reference", "party", "type", "amount", "currency", "note"],
        [
            ["2026-08-10", "PAY-9901", "Sunrise Components Pvt Ltd", "outgoing", 20000, "INR", "part payment for INV-2026-0042"],
            ["2026-08-18", "PAY-9944", "Orbit Logistics", "outgoing", 1500, "INR", "courier charges"],
            ["2026-08-25", "PAY-9987", "Sunrise Components Pvt Ltd", "outgoing", None, "INR", "amount not captured in this export"],
        ],
    )


# --------------------------------------------------------------------------- #
# Scenario 2: everything consistent -> should be mostly "Verified"
# --------------------------------------------------------------------------- #

def scenario_clean_match() -> None:
    folder = ROOT / "clean_match"

    write_txt(
        folder / "invoice.txt",
        """\
INVOICE
Invoice Number : INV-2026-0101
Invoice Date   : 2026-09-01
Payment Terms  : Net 30
Due Date       : 2026-10-01

Supplier : Sunrise Components Pvt Ltd
Buyer    : Meridian Traders LLP
Currency : INR

Item: Industrial fasteners, batch 15   500 units

Invoice Total : INR 45,000
""",
    )
    write_txt(
        folder / "purchase_order.txt",
        """\
PURCHASE ORDER
Purchase Order Number : PO-2026-0201
Order Date            : 2026-08-28
Buyer                 : Meridian Traders LLP
Supplier              : Sunrise Components Pvt Ltd
Currency              : INR

Item: Industrial fasteners   500 units

Purchase Order Total : INR 45,000
""",
    )
    write_txt(
        folder / "delivery_receipt.txt",
        """\
DELIVERY RECEIPT
Delivery Receipt Number : DR-2026-0201
Delivery Date           : 2026-09-03
Received By             : Meridian Traders LLP
Delivered By            : Sunrise Components Pvt Ltd
Against Purchase Order  : PO-2026-0201

Item                    Ordered      Received
Industrial fasteners    500 units    500 units
""",
    )
    write_csv(
        folder / "payment_ledger.csv",
        ["date", "reference", "party", "type", "amount", "currency", "note"],
        [
            ["2026-09-20", "PAY-7001", "Sunrise Components Pvt Ltd", "outgoing", 45000, "INR", "full payment for INV-2026-0101"],
        ],
    )


# --------------------------------------------------------------------------- #
# Scenario 3: incomplete / noisy -> should surface Missing + Uncertain
# --------------------------------------------------------------------------- #

def scenario_incomplete_noisy() -> None:
    folder = ROOT / "incomplete_noisy"

    write_txt(
        folder / "invoice_noisy.txt",
        """\
T A X   I N V O I C E   (text layer is patchy)
Inv No : ??? (illegible stamp)
Dated  : 1 Aug 26
Amount : approximately forty eight thousand rupees (handwritten)
Payment: as agreed, no due date written on this copy
Buyer  : Meridian Traders (spelling unclear)
""",
    )
    write_docx(
        folder / "purchase_order.docx",
        "PURCHASE ORDER",
        [
            "Purchase Order Number : PO-2026-0305",
            "Order Date            : 2026-07-30",
            "Buyer                 : Meridian Traders LLP",
            "Supplier              : Sunrise Components Pvt Ltd",
            "Currency              : INR",
            "",
            "Item                   Quantity",
            "Industrial fasteners   500 units",
            "",
            "Purchase Order Total : INR 45,000",
        ],
    )
    write_csv(
        folder / "payment_ledger_missing.csv",
        ["date", "reference", "party", "type", "amount", "currency", "note"],
        [
            ["2026-09-05", "PAY-5501", "Sunrise Components Pvt Ltd", "outgoing", "", "INR", "possibly against INV-2026-0305"],
            ["2026-09-11", "PAY-5502", "Sunrise Components Pvt Ltd", "outgoing", None, "INR", "amount blank in export"],
        ],
    )


SCENARIOS = {
    "guide_case": scenario_guide_case,
    "clean_match": scenario_clean_match,
    "incomplete_noisy": scenario_incomplete_noisy,
}


def main() -> None:
    for name, build in SCENARIOS.items():
        build()
        print(f"built samples/{name}/")
    print("\nUpload the files from any one scenario folder into the app together.")


if __name__ == "__main__":
    main()
