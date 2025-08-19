import os
import io
import re
from typing import List, Dict, Any
from datetime import datetime
from PyPDF2 import PdfReader

MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

def ensure_dir(path: str):
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def read_txt_bytes(b: bytes) -> str:
    if not b:
        return ""
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("latin-1", errors="ignore")

def read_pdf_bytes(b: bytes) -> str:
    if not b:
        return ""
    text = []
    reader = PdfReader(io.BytesIO(b))
    for page in reader.pages:
        try:
            text.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(text).strip()

def split_paragraphs(text: str) -> List[str]:
    # Split on blank lines; also respect large single blocks by splitting on double newline
    blocks = re.split(r"\n\s*\n+", text.strip())
    # Trim and drop empties
    return [b.strip() for b in blocks if b.strip()]

# ---------------- Date Normalization ----------------
def _safe_int(x, default=None):
    try:
        return int(x)
    except Exception:
        return default

def _fmt_date(y: int, m: int = 1, d: int = 1) -> str:
    # clamp month/day minimally
    m = max(1, min(12, m or 1))
    d = max(1, min(28, d or 1))  # keep simple to avoid month length edge-cases
    return f"{y:04d}-{m:02d}-{d:02d}"

def _month_to_num(token: str):
    t = token.strip().lower()
    return MONTHS.get(t)

def _try_iso(raw: str):
    # YYYY-MM-DD or YYYY/M/D
    m = re.match(r"^\s*(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s*$", raw)
    if m:
        y, mo, d = _safe_int(m.group(1)), _safe_int(m.group(2)), _safe_int(m.group(3))
        if y:
            return _fmt_date(y, mo, d)
    return None

def _try_year_month(raw: str):
    # YYYY-MM
    m = re.match(r"^\s*(\d{4})[-/](\d{1,2})\s*$", raw)
    if m:
        y, mo = _safe_int(m.group(1)), _safe_int(m.group(2))
        if y:
            return _fmt_date(y, mo, 1)
    # Month YYYY
    m2 = re.match(r"^\s*([A-Za-z]+)\s+(\d{4})\s*$", raw)
    if m2:
        mo = _month_to_num(m2.group(1))
        y = _safe_int(m2.group(2))
        if y and mo:
            return _fmt_date(y, mo, 1)
    # YYYY Month
    m3 = re.match(r"^\s*(\d{4})\s+([A-Za-z]+)\s*$", raw)
    if m3:
        y = _safe_int(m3.group(1))
        mo = _month_to_num(m3.group(2))
        if y and mo:
            return _fmt_date(y, mo, 1)
    return None

def _try_month_day_year(raw: str):
    # Month D, YYYY  or  Mon D, YYYY
    m = re.match(r"^\s*([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})\s*$", raw)
    if m:
        mo = _month_to_num(m.group(1))
        d = _safe_int(m.group(2))
        y = _safe_int(m.group(3))
        if y and mo and d:
            return _fmt_date(y, mo, d)
    # D Month YYYY
    m2 = re.match(r"^\s*(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})\s*$", raw)
    if m2:
        d = _safe_int(m2.group(1))
        mo = _month_to_num(m2.group(2))
        y = _safe_int(m2.group(3))
        if y and mo and d:
            return _fmt_date(y, mo, d)
    return None

def _try_year_only(raw: str):
    m = re.match(r"^\s*(\d{4})\s*$", raw)
    if m:
        y = _safe_int(m.group(1))
        if y:
            return _fmt_date(y, 1, 1)
    return None

def normalize_date_string(raw: str) -> str:
    """
    Normalize to YYYY-MM-DD with rules:
      - Full date -> YYYY-MM-DD
      - Year-month -> YYYY-MM-01
      - Year only -> YYYY-01-01
      - If nothing parsable but year present anywhere -> YYYY-01-01
      - Else return empty string
    """
    if not raw:
        return ""
    s = raw.strip()

    # Exact parses
    for parser in (_try_iso, _try_month_day_year, _try_year_month, _try_year_only):
        val = parser(s)
        if val:
            return val

    # Fallback: sniff a year anywhere
    yr = re.search(r"(19|20)\d{2}", s)
    if yr:
        return _fmt_date(int(yr.group(0)), 1, 1)

    return ""

# ---------------- Deduplication ----------------
def dedupe_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate by company_name (casefold). Merge founders (unique, preserve order).
    Keep the earliest non-empty founding_date if multiple.
    """
    by_name = {}
    for r in records:
        name = (r.get("company_name") or "").strip()
        if not name:
            continue
        key = name.casefold()

        founders = [f for f in (r.get("founders") or []) if f]
        date = (r.get("founding_date") or "").strip()

        if key not in by_name:
            by_name[key] = {
                "company_name": name,
                "founding_date": date,
                "founders": founders[:],
            }
        else:
            # Merge founders (preserve order, unique)
            seen = set(x.casefold() for x in by_name[key]["founders"])
            for f in founders:
                if f.casefold() not in seen:
                    by_name[key]["founders"].append(f)
                    seen.add(f.casefold())
            # Earliest date preference (string compare works for ISO)
            existing_date = by_name[key]["founding_date"]
            if existing_date and date:
                by_name[key]["founding_date"] = min(existing_date, date)
            elif date and not existing_date:
                by_name[key]["founding_date"] = date

    # Sort by company name for stability
    out = list(by_name.values())
    out.sort(key=lambda x: x["company_name"].casefold())
    return out
