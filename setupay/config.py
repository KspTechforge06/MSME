"""Runtime configuration for SetuPay.

All values can be overridden with environment variables so the app stays
local-first and can be pointed at a different Ollama host or model without
code changes.
"""
from __future__ import annotations

import os

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
MODEL = os.environ.get("SETUPAY_MODEL", "qwen2.5:3b")
DEMO_DATA_DIR = os.environ.get("SETUPAY_DEMO_DIR", "demo_data")

# Max characters of a document sent to the model. Keeps prompt size bounded.
MAX_TEXT_CHARS = 12000

# Finding status labels, aligned with the review dashboard the guide describes.
STATUS_VERIFIED = "Verified check"
STATUS_REVIEW = "Review required"
STATUS_MISSING = "Missing"
STATUS_UNCERTAIN = "Uncertain"
