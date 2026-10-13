# SetuPay — MSME Payment Evidence Agent

SetuPay is a local-first, AI-assisted tool that helps MSMEs organise documents
related to delayed payments. It extracts key facts from business documents,
cross-checks selected fields, highlights missing or conflicting information, and
produces a human-reviewable evidence pack.

It is an **evidence-organisation prototype**. It is not legal advice, does not
determine legal liability, and does not automatically file complaints.

## How it works

```text
Upload documents -> readers (PDF/DOCX/TXT/CSV/XLSX) -> local Ollama model
     -> structured facts + source quotes + uncertainty notes
     -> deterministic Python checks -> findings for review
     -> evidence-pack PDF + extracted-data JSON
```

The language model only *interprets* text and proposes facts. All comparisons
(amount differences, missing fields, payment evidence) are done by plain Python
rules in `validate.py`, so findings are reproducible and testable.

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com/download) running locally
- The `qwen2.5:3b` model

## Setup

```bash
# 1. Model
ollama pull qwen2.5:3b
ollama list

# 2. Python environment
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

# 3. Run
streamlit run app.py
```

Open the URL Streamlit prints (usually http://localhost:8501). If the `streamlit`
command is unavailable, run `python -m streamlit run app.py`.

## Demo

1. Keep Ollama running with `qwen2.5:3b` available.
2. Launch the app and leave **"include the bundled fictional demo documents"**
   checked (or upload files from `demo_data/`).
3. Click **Analyse documents**.
4. Inspect the extracted fields, source quotes, and uncertainty notes.
5. Confirm the invoice total (INR 48,000) and purchase-order total (INR 45,000)
   are extracted, and that the INR 3,000 difference is flagged for review.
6. Download and inspect the evidence-pack PDF and the JSON export.

## Project layout

| File | Purpose |
|---|---|
| `app.py` | Streamlit interface |
| `config.py` | Model/host settings and finding statuses |
| `schema.py` | `DocumentFacts` and `Finding` data model |
| `readers.py` | PDF / DOCX / TXT / CSV / XLSX text and table extraction |
| `parsing.py` | Shared number and date normalisation |
| `llm.py` | Ollama client + structured fact extraction |
| `validate.py` | Deterministic amount / date / missing-field checks |
| `report.py` | Evidence-pack PDF and JSON export |
| `smoke_test.py` | Headless end-to-end run over `demo_data/` (or a folder argument) |
| `make_samples.py` | Generates the `samples/` scenarios |
| `demo_data/` | Fictional sample documents |
| `samples/` | Extra uploadable scenarios in every supported format |

## Configuration

Environment variables (all optional):

| Variable | Default | Meaning |
|---|---|---|
| `SETUPAY_MODEL` | `qwen2.5:3b` | Ollama model name |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API base URL |
| `SETUPAY_DEMO_DIR` | `demo_data` | Demo document directory |

## Notes on provenance and licensing

The field vocabulary used here (invoice, purchase order, delivery receipt,
payment ledger, due date) is inspired by common accounting/ERP concepts,
including open-source ERP projects. **No source code from those projects is
copied or vendored** — every line in this repository is original so SetuPay can
be licensed freely.

## Limitations

- OCR for scanned PDFs is not included.
- Local model extraction can be incomplete or wrong; every value must be verified.
- A mismatch is a review signal, not proof of fraud or wrongdoing.
- A past due date does not establish that payment has not been made.
- The prototype does not determine legal eligibility or liability, does not file
  complaints, and does not replace the official MSME Samadhaan portal.

## Privacy

- Inference runs locally through Ollama; no hosted AI API is used.
- Do not expose the Ollama service on a public network.
- Use only fictional documents for public demonstrations.
- Do not commit real client documents, credentials, `.venv`, or model files.
