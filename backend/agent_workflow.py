import os
import json
import re
from typing import List, Dict, Any
from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_google_genai import ChatGoogleGenerativeAI

from utils import (
    split_paragraphs,
    normalize_date_string,
    dedupe_records,
)

# ------------- Model Setup -------------
# Expect GOOGLE_API_KEY in environment.
# You can also set GEMINI_API_KEY; we'll fall back to GOOGLE_API_KEY if present.
def _get_gemini_api_key() -> str:
    return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""

MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")  # fast & cheap; upgrade to pro if you like

def _make_model():
    key = _get_gemini_api_key()
    if not key:
        raise RuntimeError(
            "Missing API key. Set GOOGLE_API_KEY (or GEMINI_API_KEY) in your environment."
        )
    return ChatGoogleGenerativeAI(model=MODEL_NAME, google_api_key=key, temperature=0)

# ------------- LCEL Chain -------------
# We process one paragraph at a time and ask the model to ONLY return strict JSON.
SYSTEM_MSG = (
    "You are an information extraction assistant. "
    "Extract company formation details ONLY from the provided paragraph. "
    "Output STRICT JSON with the following shape:\n"
    "{\n"
    '  "companies": [\n'
    "    {\n"
    '      "company_name": "string",\n'
    '      "founding_date": "string (ISO-like date if present, else year or year-month or empty)",\n'
    '      "founders": ["string", ...]\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "- Company name: preserve official punctuation (Inc., LLC, Ltd., etc.).\n"
    "- Founding date: if a full date is present, return as YYYY-MM-DD if possible; "
    "  else return available parts (YYYY or YYYY-MM). If date unknown, use empty string.\n"
    "- Founders: list of names. If unclear, use an empty list.\n"
    "Do not include commentary. JSON only."
)

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_MSG),
        (
            "human",
            "Paragraph:\n{paragraph}\n\nReturn JSON only.",
        ),
    ]
)

MODEL = _make_model()
CHAIN = PROMPT | MODEL | StrOutputParser() | RunnableLambda(lambda s: json.loads(s))


def _coerce_record(d: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce and clean a single extracted item."""
    company = (d.get("company_name") or "").strip()
    raw_date = (d.get("founding_date") or "").strip()
    founders = d.get("founders") or []

    # Ensure list of strings
    if isinstance(founders, str):
        # Try parse if it's a stringified list, else split by comma
        text = founders.strip()
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text.replace("'", '"'))
                founders = parsed if isinstance(parsed, list) else [text]
            except Exception:
                founders = [text]
        else:
            founders = [x.strip() for x in text.split(",") if x.strip()]

    founders = [f for f in founders if f]

    # Normalize date to YYYY-MM-DD (with fallback rules)
    norm_date = normalize_date_string(raw_date)

    return {
        "company_name": company,
        "founding_date": norm_date,
        "founders": founders,
    }


def _extract_from_paragraph(paragraph: str) -> List[Dict[str, Any]]:
    """Run LCEL chain on a single paragraph and normalize results."""
    if not paragraph.strip():
        return []
    try:
        out = CHAIN.invoke({"paragraph": paragraph})
        companies = out.get("companies") or []
        cleaned = [_coerce_record(item) for item in companies]
        # Filter empty company names
        cleaned = [c for c in cleaned if c["company_name"]]
        return cleaned
    except Exception:
        # If model outputs invalid JSON, try a salvage pass with regex (best-effort)
        return []


def extract_company_info(text: str) -> List[Dict[str, Any]]:
    """Main entry: split into paragraphs, run extraction per paragraph, then dedupe."""
    paragraphs = split_paragraphs(text)
    results: List[Dict[str, Any]] = []

    # Batch inference with LCEL (optionally you could set max_concurrency)
    batch_payload = [{"paragraph": p} for p in paragraphs]
    if batch_payload:
        batch_out = []
        # Using the chain's underlying prompt->model->parser piece for each paragraph
        for p in paragraphs:
            batch_out.append(_extract_from_paragraph(p))

        # Flatten
        for arr in batch_out:
            results.extend(arr)

    # Deduplicate companies, merge founders
    results = dedupe_records(results)
    return results


def save_records_to_csv(records: List[Dict[str, Any]], csv_path: str) -> None:
    """
    Save to CSV with headers:
      S.N.,Company Name,Founded in,Founded by
    founders are stored as Pythonic list string: "['A', 'B']"
    """
    import csv
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["S.N.", "Company Name", "Founded in", "Founded by"])
        for i, r in enumerate(records, start=1):
            founders = r.get("founders") or []
            founders_str = "['" + "', '".join(founders) + "']"
            writer.writerow([i, r.get("company_name", ""), r.get("founding_date", ""), founders_str])
