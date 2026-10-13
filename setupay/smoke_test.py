"""Headless smoke test: run the whole pipeline over demo_data and print results.

Usage:  python smoke_test.py
Useful for CI or for checking the setup without launching Streamlit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import config
from llm import check_available, extract_facts
from readers import SUPPORTED_EXTENSIONS, extract_tables, extract_text
from report import build_payload, build_pdf
from validate import run_checks, summarise


def main() -> None:
    if not check_available():
        raise SystemExit(
            f"Ollama is not reachable at {config.OLLAMA_HOST}. Start it first."
        )

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(config.DEMO_DATA_DIR)
    demo_dir = target
    documents = []
    for path in sorted(demo_dir.iterdir()):
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        data = path.read_bytes()
        text = extract_text(path.name, data)
        doc = extract_facts(path.name, text)
        doc.table_rows = extract_tables(path.name, data)
        documents.append(doc)
        print(
            f"[{path.name}] type={doc.document_type} number={doc.document_number} "
            f"amount={doc.amount} due_date={doc.due_date}"
        )

    findings = run_checks(documents)
    print("\nFindings:")
    for finding in findings:
        print(f"  {finding.status:>16} | {finding.check} | {finding.summary}")

    print("\nSummary:", summarise(findings))

    exports = Path("exports")
    exports.mkdir(exist_ok=True)
    stem = demo_dir.name or "demo"
    payload = build_payload(documents, findings)
    (exports / f"{stem}_extracted_data.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    (exports / f"{stem}_evidence_pack.pdf").write_bytes(build_pdf(documents, findings))
    print(f"Wrote exports/{stem}_extracted_data.json and exports/{stem}_evidence_pack.pdf")


if __name__ == "__main__":
    main()
