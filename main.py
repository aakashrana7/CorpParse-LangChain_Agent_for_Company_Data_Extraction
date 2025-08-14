# main.py
import os
import csv
from datetime import datetime
from typing import List, Dict

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableMap, RunnableLambda
from langchain_core.tools import tool

# ----------------------
# CONFIG
# ----------------------
os.environ["GOOGLE_API_KEY"] = "YOUR_GEMINI_API_KEY"  # Replace with your Gemini API key

# ----------------------
# TOOL: Write CSV
# ----------------------
@tool
def write_to_csv(data: List[Dict], file_path: str = "output/company_info.csv"):
    """Write extracted company info to CSV."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["company_name", "founding_date", "founders"])
        writer.writeheader()
        for row in data:
            writer.writerow(row)
    return f"Data written to {file_path}"

# ----------------------
# PROMPT for extraction
# ----------------------
template = """
You are an AI that extracts company information from a paragraph.
Extract:
- Company name
- Founding date in format YYYY-MM-DD (if missing month/day, set month=01/day=01; if missing day, set day=01)
- Founders (comma separated)

Paragraph:
{paragraph}

Return JSON in the format:
{{
    "company_name": "...",
    "founding_date": "...",
    "founders": ["...", "..."]
}}
"""
prompt = PromptTemplate(input_variables=["paragraph"], template=template)

# ----------------------
# LLM
# ----------------------
llm = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0)

# ----------------------
# Runnable pipeline
# ----------------------
def clean_date(date_str: str) -> str:
    """Normalize incomplete dates to YYYY-MM-DD."""
    try:
        parts = date_str.strip().split("-")
        if len(parts) == 1:  # only year
            return f"{parts[0]}-01-01"
        elif len(parts) == 2:  # year and month
            return f"{parts[0]}-{parts[1]}-01"
        elif len(parts) == 3:
            return date_str
    except:
        return date_str
    return date_str

def clean_output(parsed: Dict) -> Dict:
    """Ensure founders is comma-separated string, and date is correct."""
    return {
        "company_name": parsed.get("company_name", "").strip(),
        "founding_date": clean_date(parsed.get("founding_date", "")),
        "founders": ", ".join(parsed.get("founders", []))
    }

extract_chain = (
    {"paragraph": RunnableLambda(lambda x: x)}
    | prompt
    | llm
    | RunnableLambda(lambda x: eval(x.content))  # Convert model output string to dict
    | RunnableLambda(clean_output)
)

# ----------------------
# Main workflow
# ----------------------
if __name__ == "__main__":
    # Read essay
    with open("essay.txt", "r", encoding="utf-8") as f:
        paragraphs = [p.strip() for p in f.read().split("\n") if p.strip()]

    extracted_data = []
    for para in paragraphs:
        result = extract_chain.invoke(para)
        extracted_data.append(result)

    # Write CSV via tool
    write_to_csv(extracted_data)
    print("✅ Extraction complete. CSV saved in output/company_info.csv")
