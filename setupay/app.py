"""SetuPay — MSME Payment Evidence Agent (Streamlit UI).

Run with:  streamlit run app.py
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

import config
from llm import OllamaUnavailable, check_available, extract_facts, list_models
from readers import (
    SUPPORTED_EXTENSIONS,
    UnsupportedFileType,
    extract_tables,
    extract_text,
)
from report import build_payload, build_pdf, payload_to_json
from schema import DocumentFacts
from validate import run_checks, summarise

DEMO_DIR = Path(config.DEMO_DATA_DIR)

STATUS_ICON = {
    config.STATUS_VERIFIED: "✅",
    config.STATUS_REVIEW: "⚠️",
    config.STATUS_MISSING: "❌",
    config.STATUS_UNCERTAIN: "❓",
}


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #

def collect_inputs(uploaded_files, use_demo: bool) -> list[tuple[str, bytes]]:
    items: list[tuple[str, bytes]] = []
    if use_demo and DEMO_DIR.is_dir():
        for path in sorted(DEMO_DIR.iterdir()):
            if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                items.append((path.name, path.read_bytes()))
    for uploaded in uploaded_files or []:
        items.append((uploaded.name, uploaded.getvalue()))
    return items


def analyse(items: list[tuple[str, bytes]]) -> tuple[list[DocumentFacts], list]:
    documents: list[DocumentFacts] = []
    for name, data in items:
        try:
            text = extract_text(name, data)
        except UnsupportedFileType as exc:
            documents.append(DocumentFacts(filename=name, error=str(exc)))
            continue
        except Exception as exc:  # noqa: BLE001 - surface any reader failure
            documents.append(DocumentFacts(filename=name, error=f"Could not read file: {exc}"))
            continue

        try:
            doc = extract_facts(name, text)
        except OllamaUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - model output could not be parsed
            doc = DocumentFacts(
                filename=name,
                text_excerpt=text[:2000],
                error=f"Extraction failed: {exc}",
            )

        try:
            doc.table_rows = extract_tables(name, data)
        except Exception:  # noqa: BLE001 - tables are best-effort
            doc.table_rows = []
        documents.append(doc)

    findings = run_checks(documents)
    return documents, findings


# --------------------------------------------------------------------------- #
# UI helpers
# --------------------------------------------------------------------------- #

def render_finding(finding) -> None:
    icon = STATUS_ICON.get(finding.status, "•")
    st.markdown(f"**{icon} {finding.status}** — `{finding.check}`")
    st.markdown(finding.summary)
    if finding.detail:
        st.caption(finding.detail)
    if finding.documents:
        st.caption("Documents: " + ", ".join(finding.documents))
    if finding.source_quotes:
        with st.expander("Source quotes"):
            for quote in finding.source_quotes:
                st.markdown(f"- **{quote.get('field', '')}**: “{quote.get('quote', '')}”")
    st.divider()


def render_document(doc: DocumentFacts) -> None:
    with st.expander(f"{doc.filename}  ·  {doc.document_type}", expanded=False):
        if doc.error:
            st.error(doc.error)
            return
        cols = st.columns(3)
        fields = [
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
        for index, (label, value) in enumerate(fields):
            cols[index % 3].metric(label, "—" if value in (None, "") else str(value))

        if doc.source_quotes:
            st.markdown("**Source quotes**")
            for quote in doc.source_quotes:
                st.markdown(f"- **{quote.get('field', '')}**: “{quote.get('quote', '')}”")
        if doc.uncertainties:
            st.markdown("**Uncertainty notes**")
            for note in doc.uncertainties:
                st.markdown(f"- {note}")
        if doc.table_rows:
            st.markdown("**Parsed table rows**")
            st.dataframe(doc.table_rows, use_container_width=True)
        with st.expander("Raw extracted text"):
            st.text(doc.text_excerpt or "(empty)")


# --------------------------------------------------------------------------- #
# Page
# --------------------------------------------------------------------------- #

st.set_page_config(
    page_title="SetuPay — MSME Payment Evidence Agent",
    page_icon="🧾",
    layout="wide",
)

st.title("🧾 SetuPay — MSME Payment Evidence Agent")
st.caption(
    "Local-first document organiser. Extracts facts, cross-checks selected fields, "
    "and produces a human-reviewable evidence pack."
)
st.info(
    "SetuPay is an evidence-organisation prototype. It is not legal advice, does not "
    "determine liability, and does not file complaints. A discrepancy is a review "
    "signal only; a past due date does not by itself mean an invoice is unpaid."
)

with st.sidebar:
    st.header("Setup")
    st.write(f"**Model:** `{config.MODEL}`")
    st.write(f"**Ollama host:** `{config.OLLAMA_HOST}`")
    if check_available():
        st.success("Ollama reachable")
        installed = list_models()
        if installed:
            st.caption("Installed models: " + ", ".join(installed))
        if config.MODEL not in installed:
            st.warning(
                f"Model `{config.MODEL}` is not installed. Run "
                f"`ollama pull {config.MODEL}`."
            )
    else:
        st.error("Ollama not reachable. Start it, then reload.")
    st.divider()
    st.caption(
        "Field vocabulary is inspired by standard accounting/ERP concepts "
        "(invoice, purchase order, delivery, payment ledger). All code here is "
        "original to SetuPay."
    )

uploaded = st.file_uploader(
    "Upload business documents",
    type=[ext.lstrip(".") for ext in sorted(SUPPORTED_EXTENSIONS)],
    accept_multiple_files=True,
)
use_demo = st.checkbox("Also include the bundled fictional demo documents", value=True)

if st.button("Analyse documents", type="primary"):
    items = collect_inputs(uploaded, use_demo)
    if not items:
        st.warning("Upload at least one document (or enable the demo documents).")
    elif not check_available():
        st.error(
            "Ollama is not reachable. Start Ollama and confirm the model is pulled "
            f"(`ollama pull {config.MODEL}`)."
        )
    else:
        with st.spinner("Extracting facts locally and running checks..."):
            try:
                documents, findings = analyse(items)
            except OllamaUnavailable as exc:
                st.error(f"Model extraction failed: {exc}")
            else:
                st.session_state["documents"] = documents
                st.session_state["findings"] = findings
                st.session_state["payload"] = build_payload(documents, findings)
                st.success(f"Analysed {len(documents)} document(s).")

documents = st.session_state.get("documents")
findings = st.session_state.get("findings")
payload = st.session_state.get("payload")

if documents is not None:
    counts = summarise(findings)
    metrics = st.columns(4)
    metrics[0].metric("Verified checks", counts[config.STATUS_VERIFIED])
    metrics[1].metric("Review required", counts[config.STATUS_REVIEW])
    metrics[2].metric("Missing", counts[config.STATUS_MISSING])
    metrics[3].metric("Uncertain", counts[config.STATUS_UNCERTAIN])

    tab_findings, tab_documents, tab_export = st.tabs(
        ["Findings for review", "Extracted documents", "Exports"]
    )

    with tab_findings:
        if findings:
            for finding in findings:
                render_finding(finding)
        else:
            st.write("No findings were produced.")

    with tab_documents:
        for doc in documents:
            render_document(doc)

    with tab_export:
        st.download_button(
            "Download evidence-pack PDF",
            data=build_pdf(documents, findings),
            file_name="setupay_evidence_pack.pdf",
            mime="application/pdf",
        )
        st.download_button(
            "Download extracted-data JSON",
            data=payload_to_json(payload),
            file_name="setupay_extracted_data.json",
            mime="application/json",
        )
        st.caption(
            "Verify every value against the original documents before relying on it."
        )
        with st.expander("Preview JSON"):
            st.json(payload)
