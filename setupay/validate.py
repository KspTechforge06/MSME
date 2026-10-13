"""Deterministic validation.

Ordinary Python rules (no model involved) compare selected fields across
documents and emit ``Finding`` objects for human review. A finding is a review
signal, never proof of wrongdoing, and never a statement of what is legally
payable.
"""
from __future__ import annotations

from typing import Any, Optional

from config import STATUS_MISSING, STATUS_REVIEW, STATUS_UNCERTAIN, STATUS_VERIFIED
from parsing import parse_date, parse_number
from schema import DocumentFacts, Finding

REQUIRED_FIELDS: dict[str, list[str]] = {
    "invoice": ["document_number", "amount", "currency", "issue_date", "due_date"],
    "purchase_order": ["document_number", "amount", "currency", "issue_date"],
    "delivery_receipt": ["document_number", "delivery_date", "quantity"],
}


def _of_type(documents: list[DocumentFacts], doc_type: str) -> list[DocumentFacts]:
    return [doc for doc in documents if doc.document_type == doc_type]


def _has_value(doc: DocumentFacts, field: str) -> bool:
    value = doc.get(field)
    return value not in (None, "", [])


def _richness(doc: DocumentFacts) -> int:
    fields = (
        "document_number",
        "buyer",
        "supplier",
        "currency",
        "amount",
        "issue_date",
        "due_date",
        "delivery_date",
        "quantity",
    )
    return sum(1 for field in fields if _has_value(doc, field))


def _dedupe_by_number(documents: list[DocumentFacts]) -> list[DocumentFacts]:
    """Collapse documents of the same type sharing a document number.

    Emails or cover notes that restate an invoice number are treated as the same
    record (the richest version is kept) so they do not break pairwise
    comparison. Documents without a number are left untouched.
    """
    best: dict[tuple[str, str], DocumentFacts] = {}
    order: list[tuple[str, str]] = []
    unnumbered: list[DocumentFacts] = []
    for doc in documents:
        number = (doc.document_number or "").strip().lower()
        if not number:
            unnumbered.append(doc)
            continue
        key = (doc.document_type, number)
        if key not in best:
            best[key] = doc
            order.append(key)
        elif _richness(doc) > _richness(best[key]):
            best[key] = doc
    return [best[key] for key in order] + unnumbered


def _pick_column(keys: list[str], *needles: str) -> Optional[str]:
    for key in keys:
        lowered = key.lower()
        if any(needle in lowered for needle in needles):
            return key
    return None


# --------------------------------------------------------------------------- #
# Individual checks
# --------------------------------------------------------------------------- #

def check_amount_comparison(documents: list[DocumentFacts]) -> list[Finding]:
    """Compare invoice totals with purchase-order totals."""
    invoices = [d for d in _of_type(documents, "invoice") if parse_number(d.amount) is not None]
    orders = [d for d in _of_type(documents, "purchase_order") if parse_number(d.amount) is not None]
    if not invoices or not orders:
        return []

    if len(invoices) > 1 or len(orders) > 1:
        return [
            Finding(
                check="amount_comparison",
                status=STATUS_UNCERTAIN,
                summary="Multiple invoices or purchase orders found; automatic pairing was skipped.",
                detail="Compare the relevant documents manually, or add explicit document references.",
                documents=[d.filename for d in invoices + orders],
            )
        ]

    invoice, order = invoices[0], orders[0]
    inv_amount = parse_number(invoice.amount)
    po_amount = parse_number(order.amount)

    if invoice.currency and order.currency and invoice.currency.upper() != order.currency.upper():
        return [
            Finding(
                check="amount_comparison",
                status=STATUS_UNCERTAIN,
                summary="Invoice and purchase order use different currencies; amounts were not compared.",
                detail=f"Invoice: {inv_amount:,.2f} {invoice.currency}; "
                f"purchase order: {po_amount:,.2f} {order.currency}.",
                documents=[invoice.filename, order.filename],
            )
        ]

    difference = round(inv_amount - po_amount, 2)
    currency = (invoice.currency or order.currency or "").upper()
    if difference == 0:
        return [
            Finding(
                check="amount_comparison",
                status=STATUS_VERIFIED,
                summary="Invoice and purchase-order amounts match.",
                detail=f"Both documents show {inv_amount:,.2f} {currency}".strip() + ".",
                documents=[invoice.filename, order.filename],
                source_quotes=invoice.source_quotes + order.source_quotes,
            )
        ]

    return [
        Finding(
            check="amount_comparison",
            status=STATUS_REVIEW,
            summary=f"Invoice and purchase-order amounts differ by {difference:,.2f} {currency}".strip()
            + ".",
            detail=(
                f"Invoice {invoice.filename} shows {inv_amount:,.2f}; "
                f"purchase order {order.filename} shows {po_amount:,.2f}. "
                "This is a review signal only and does not indicate which amount is correct."
            ),
            documents=[invoice.filename, order.filename],
            source_quotes=invoice.source_quotes + order.source_quotes,
        )
    ]


def check_invoice_due_date(documents: list[DocumentFacts]) -> list[Finding]:
    """Confirm whether an invoice due date was extracted (extraction check only)."""
    findings: list[Finding] = []
    for invoice in _of_type(documents, "invoice"):
        if parse_date(invoice.due_date):
            findings.append(
                Finding(
                    check="invoice_due_date",
                    status=STATUS_VERIFIED,
                    summary=f"Invoice due date extracted: {invoice.due_date}.",
                    documents=[invoice.filename],
                    source_quotes=[q for q in invoice.source_quotes if "due" in q.get("field", "").lower()],
                )
            )
        else:
            findings.append(
                Finding(
                    check="invoice_due_date",
                    status=STATUS_MISSING,
                    summary="Invoice due date could not be extracted.",
                    detail="Confirm the due date against the source document.",
                    documents=[invoice.filename],
                )
            )
    return findings


def check_missing_fields(documents: list[DocumentFacts]) -> list[Finding]:
    """Flag expected fields that are absent for each document type."""
    findings: list[Finding] = []
    for doc in documents:
        required = REQUIRED_FIELDS.get(doc.document_type)
        if not required:
            continue
        missing = [field for field in required if not _has_value(doc, field)]
        if missing:
            findings.append(
                Finding(
                    check="missing_fields",
                    status=STATUS_MISSING,
                    summary=f"{doc.document_type.replace('_', ' ').title()} {doc.filename}: "
                    f"missing {', '.join(missing)}.",
                    detail="Absent information is reported as missing, never guessed.",
                    documents=[doc.filename],
                )
            )
        else:
            findings.append(
                Finding(
                    check="missing_fields",
                    status=STATUS_VERIFIED,
                    summary=f"{doc.document_type.replace('_', ' ').title()} {doc.filename}: "
                    "all expected fields present.",
                    documents=[doc.filename],
                )
            )
    return findings


def check_payment_evidence(documents: list[DocumentFacts]) -> list[Finding]:
    """Look for ledger rows referencing each invoice.

    A past due date alone never establishes non-payment, so the absence of a
    matching row is reported as *uncertain*, not as an unpaid invoice.
    """
    findings: list[Finding] = []
    invoices = _of_type(documents, "invoice")
    ledgers = _of_type(documents, "payment_ledger")
    rows = [row for ledger in ledgers for row in ledger.table_rows]

    for invoice in invoices:
        number = (invoice.document_number or "").strip()
        if not number:
            findings.append(
                Finding(
                    check="payment_evidence",
                    status=STATUS_UNCERTAIN,
                    summary="Invoice number was not extracted; the payment ledger could not be searched.",
                    documents=[invoice.filename],
                )
            )
            continue

        matches = [
            row
            for row in rows
            if number.lower() in " ".join(str(v) for v in row.values() if v is not None).lower()
        ]
        if not matches:
            findings.append(
                Finding(
                    check="payment_evidence",
                    status=STATUS_UNCERTAIN,
                    summary=f"No ledger entry referencing {number} was found.",
                    detail=(
                        "A due date in the past does not, by itself, establish that the "
                        "invoice remains unpaid. Confirm payment status from a primary source."
                    ),
                    documents=[invoice.filename] + [ledger.filename for ledger in ledgers],
                )
            )
            continue

        invoiced = parse_number(invoice.amount)
        recorded = 0.0
        missing_amount = False
        for row in matches:
            keys = list(row.keys())
            amount_col = _pick_column(keys, "amount", "value")
            row_amount = parse_number(row.get(amount_col)) if amount_col else None
            if row_amount is None:
                missing_amount = True
            else:
                recorded += row_amount

        if missing_amount:
            findings.append(
                Finding(
                    check="payment_evidence",
                    status=STATUS_UNCERTAIN,
                    summary=f"Ledger entries reference {number}, but at least one amount is missing.",
                    detail="The recorded total cannot be relied upon until every amount is present.",
                    documents=[invoice.filename] + [ledger.filename for ledger in ledgers],
                )
            )
        elif invoiced is not None and recorded + 1e-9 < invoiced:
            findings.append(
                Finding(
                    check="payment_evidence",
                    status=STATUS_REVIEW,
                    summary=f"Recorded payments against {number} "
                    f"({recorded:,.2f}) are less than the invoice amount ({invoiced:,.2f}).",
                    detail="Possible partial payment. Confirm against bank or accounting records.",
                    documents=[invoice.filename] + [ledger.filename for ledger in ledgers],
                )
            )
        else:
            findings.append(
                Finding(
                    check="payment_evidence",
                    status=STATUS_VERIFIED,
                    summary=f"Ledger entries referencing {number} total {recorded:,.2f}.",
                    documents=[invoice.filename] + [ledger.filename for ledger in ledgers],
                )
            )
    return findings


def check_ledger_quality(documents: list[DocumentFacts]) -> list[Finding]:
    """Flag ledger rows with unusable values (missing amount or date)."""
    findings: list[Finding] = []
    for ledger in _of_type(documents, "payment_ledger"):
        if not ledger.table_rows:
            continue
        keys = list(ledger.table_rows[0].keys())
        amount_col = _pick_column(keys, "amount", "value")
        date_col = _pick_column(keys, "date")
        for index, row in enumerate(ledger.table_rows, start=1):
            problems = []
            if amount_col and parse_number(row.get(amount_col)) is None:
                problems.append("amount")
            if date_col and parse_date(row.get(date_col)) is None:
                problems.append("date")
            if problems:
                findings.append(
                    Finding(
                        check="ledger_quality",
                        status=STATUS_MISSING,
                        summary=f"{ledger.filename} row {index}: missing {', '.join(problems)}.",
                        detail="This ledger row cannot be used in checks until completed.",
                        documents=[ledger.filename],
                    )
                )
    return findings


def check_uncertainties(documents: list[DocumentFacts]) -> list[Finding]:
    """Surface model-reported uncertainty without turning it into a fact."""
    notes: list[str] = []
    sources: list[str] = []
    for doc in documents:
        for note in doc.uncertainties:
            notes.append(f"{doc.filename}: {note}")
            sources.append(doc.filename)
    if not notes:
        return []
    return [
        Finding(
            check="extraction_uncertainty",
            status=STATUS_UNCERTAIN,
            summary=f"{len(notes)} extraction uncertainty note(s) reported by the model.",
            detail="\n".join(notes),
            documents=sorted(set(sources)),
        )
    ]


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def run_checks(documents: list[DocumentFacts]) -> list[Finding]:
    """Run every deterministic check and return the findings."""
    documents = _dedupe_by_number(documents)
    findings: list[Finding] = []
    findings.extend(check_amount_comparison(documents))
    findings.extend(check_invoice_due_date(documents))
    findings.extend(check_payment_evidence(documents))
    findings.extend(check_ledger_quality(documents))
    findings.extend(check_missing_fields(documents))
    findings.extend(check_uncertainties(documents))
    return findings


def summarise(findings: list[Finding]) -> dict[str, int]:
    """Count findings by status for the dashboard."""
    counts: dict[str, int] = {
        STATUS_VERIFIED: 0,
        STATUS_REVIEW: 0,
        STATUS_MISSING: 0,
        STATUS_UNCERTAIN: 0,
    }
    for finding in findings:
        counts[finding.status] = counts.get(finding.status, 0) + 1
    return counts
