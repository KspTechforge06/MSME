# Sample documents for SetuPay

Fictional documents you can upload into the app. Every file is invented; none
contains real client or personal data.

Upload **all files from one scenario folder together** (the checks compare
documents across files, so a single file alone will not exercise much).

Formats covered: PDF, DOCX, TXT, CSV, XLSX.

Regenerate at any time with:

```bash
python make_samples.py
```

## `guide_case/` — the example from the project guide

Mixed formats (PDF invoice, DOCX purchase order, TXT, XLSX ledger).

| File | Contents |
|---|---|
| `01_invoice.pdf` | Invoice INV-2026-0042, total INR 48,000, due 2026-08-31 |
| `02_purchase_order.docx` | PO-2026-0117, total INR 45,000 |
| `03_delivery_receipt.txt` | Delivery DR-2026-0088, 2026-08-05, 500 units |
| `04_email_correspondence.txt` | Buyer queries the INR 3,000 difference; mentions part payment |
| `05_payment_ledger.xlsx` | Part payment 20,000, an unrelated courier charge, one blank amount |

Expected findings: amount difference of **INR 3,000** flagged for review, due
date extracted, partial payment flagged, one ledger row reported missing.

## `clean_match/` — everything consistent

Plain text plus a CSV ledger.

All amounts, dates and quantities agree, and the ledger shows full payment.

Expected findings: **all checks Verified** (no review, missing, or uncertain).

## `incomplete_noisy/` — poor-quality input

An illegible invoice, a DOCX purchase order, and a ledger with blank amounts.

Expected findings: the missing due date and document number are reported as
**Missing**, the unsearchable ledger as **Uncertain**, and the model's
uncertainty notes are surfaced rather than guessed over.

## A note on local extraction

Numbers and dates come from a small local model (`qwen2.5:3b`), so results can
vary between runs. The deterministic checks in `validate.py` always apply the
same rules to whatever facts were extracted. Always verify values against the
original documents.
