"""Evidence-pack export: structured JSON and a human-readable PDF.

Both outputs include the source quotes and the explicit disclaimer that SetuPay
does not determine liability.
"""
from __future__ import annotations

import io
import json
from datetime import datetime
from typing import Any

from config import MODEL
from schema import DocumentFacts, Finding

DISCLAIMER = (
    "SetuPay organises and cross-checks documents for human review. It is not "
    "legal advice, does not determine legal liability, and does not file "
    "complaints. A discrepancy is a review signal, not proof of wrongdoing, and "
    "a past due date does not by itself establish that an invoice is unpaid."
)


def build_payload(documents: list[DocumentFacts], findings: list[Finding]) -> dict[str, Any]:
    """Assemble the JSON export."""
    return {
        "tool": "SetuPay",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": MODEL,
        "disclaimer": DISCLAIMER,
        "documents": [doc.to_dict() for doc in documents],
        "findings": [finding.to_dict() for finding in findings],
    }


def payload_to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _escape(text: Any) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_pdf(documents: list[DocumentFacts], findings: list[Finding]) -> bytes:
    """Render the evidence pack as PDF bytes."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "SetuPayTitle", parent=styles["Title"], fontSize=20, spaceAfter=6
    )
    body = styles["BodyText"]
    small = ParagraphStyle("SetuPaySmall", parent=body, fontSize=8, textColor=colors.grey)

    status_colors = {
        "Verified check": colors.HexColor("#1B7F3B"),
        "Review required": colors.HexColor("#B45309"),
        "Missing": colors.HexColor("#B91C1C"),
        "Uncertain": colors.HexColor("#6B7280"),
    }

    buffer = io.BytesIO()
    template = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="SetuPay Evidence Pack",
    )
    story: list[Any] = []

    story.append(Paragraph("SetuPay — Evidence Pack", title_style))
    story.append(
        Paragraph(
            f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} · "
            f"local model: {_escape(MODEL)}",
            small,
        )
    )
    story.append(Spacer(1, 6))
    story.append(Paragraph(_escape(DISCLAIMER), small))
    story.append(Spacer(1, 12))

    # --- Findings summary -------------------------------------------------- #
    story.append(Paragraph("Findings for review", styles["Heading2"]))
    if findings:
        rows = [["Status", "Check", "Summary"]]
        for finding in findings:
            rows.append(
                [
                    Paragraph(
                        f"<font color='{status_colors.get(finding.status, colors.black).hexval()}'>"
                        f"<b>{_escape(finding.status)}</b></font>",
                        body,
                    ),
                    _escape(finding.check),
                    Paragraph(_escape(finding.summary), body),
                ]
            )
        table = Table(rows, colWidths=[28 * mm, 34 * mm, None], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(table)
    else:
        story.append(Paragraph("No findings were produced.", body))
    story.append(Spacer(1, 14))

    # --- Per-document facts ------------------------------------------------ #
    story.append(Paragraph("Extracted document facts", styles["Heading2"]))
    for doc in documents:
        story.append(Paragraph(_escape(doc.filename), styles["Heading3"]))
        if doc.error:
            story.append(Paragraph(f"<i>Could not read this file: {_escape(doc.error)}</i>", body))
            story.append(Spacer(1, 8))
            continue
        fields = [
            ("Type", doc.document_type),
            ("Document no.", doc.document_number),
            ("Buyer", doc.buyer),
            ("Supplier", doc.supplier),
            ("Currency", doc.currency),
            ("Amount", doc.amount),
            ("Issue date", doc.issue_date),
            ("Due date", doc.due_date),
            ("Delivery date", doc.delivery_date),
            ("Quantity", doc.quantity),
        ]
        fact_rows = [
            [_escape(label), _escape(value if value not in (None, "") else "—")]
            for label, value in fields
        ]
        fact_table = Table(fact_rows, colWidths=[40 * mm, None])
        fact_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E5E7EB")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(fact_table)
        if doc.source_quotes:
            story.append(Spacer(1, 4))
            story.append(Paragraph("<b>Source quotes</b>", small))
            for quote in doc.source_quotes:
                story.append(
                    Paragraph(
                        f"• <b>{_escape(quote.get('field', ''))}</b>: "
                        f"“{_escape(quote.get('quote', ''))}”",
                        small,
                    )
                )
        if doc.uncertainties:
            story.append(Spacer(1, 4))
            story.append(Paragraph("<b>Uncertainty notes</b>", small))
            for note in doc.uncertainties:
                story.append(Paragraph(f"• {_escape(note)}", small))
        story.append(Spacer(1, 12))

    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "Every value above must be verified against the original document. "
            "Machine extraction can be incomplete or wrong.",
            small,
        )
    )

    template.build(story)
    return buffer.getvalue()
