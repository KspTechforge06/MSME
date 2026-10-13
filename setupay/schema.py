"""Data model for SetuPay.

Field names deliberately mirror the vocabulary used by ordinary accounting /
ERP systems (invoice, purchase order, delivery receipt, payment ledger, due
date, total). The model itself is original: it is a small, flat record used by
the extraction and validation steps, not a database schema.

Nothing here assigns liability or decides which document is "correct".
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

# Document types the extractor may assign.
DOC_TYPES = [
    "invoice",
    "purchase_order",
    "delivery_receipt",
    "email",
    "payment_ledger",
    "unknown",
]

# Fact fields the model is asked to fill. Values are numbers or strings or null.
FACT_FIELDS = [
    "document_number",
    "buyer",
    "supplier",
    "currency",
    "amount",
    "issue_date",
    "due_date",
    "delivery_date",
    "quantity",
    "payment_amount",
    "payment_date",
]

DATE_FIELDS = {"issue_date", "due_date", "delivery_date", "payment_date"}
NUMBER_FIELDS = {"amount", "quantity", "payment_amount"}


@dataclass
class DocumentFacts:
    """Facts extracted from one uploaded document."""

    filename: str
    document_type: str = "unknown"
    document_number: Optional[str] = None
    buyer: Optional[str] = None
    supplier: Optional[str] = None
    currency: Optional[str] = None
    amount: Optional[float] = None
    issue_date: Optional[str] = None
    due_date: Optional[str] = None
    delivery_date: Optional[str] = None
    quantity: Optional[float] = None
    payment_amount: Optional[float] = None
    payment_date: Optional[str] = None

    # Evidence and transparency.
    source_quotes: list[dict[str, Any]] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)

    # Raw material kept for the evidence pack and deterministic checks.
    text_excerpt: str = ""
    table_rows: list[dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    def get(self, name: str) -> Any:
        return getattr(self, name, None)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Finding:
    """A single human-reviewable result produced by a deterministic check."""

    check: str
    status: str
    summary: str
    detail: str = ""
    documents: list[str] = field(default_factory=list)
    source_quotes: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
