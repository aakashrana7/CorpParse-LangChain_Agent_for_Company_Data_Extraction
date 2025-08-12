# CorpParse — LCEL-Powered Company Info Extractor

## Project Summary
**CorpParse** is a lightweight pipeline that uses LangChain’s LCEL (Runnable) patterns and an agent-driven workflow to locate and extract structured company details from free-form text. The tool processes text **paragraph-by-paragraph**, identifies company names, founding dates, and founders, and outputs a normalized CSV (`company_info.csv`) for downstream use.

This project is aimed at researchers, analysts, and data engineers who need an automated, repeatable way to convert narrative business descriptions into tabular data.

## Key Features
- Paragraph-level processing (each paragraph treated as one input unit)
- Agentic extraction pipeline using LangChain LCEL Runnables
- Tool wrappers for deterministic parsing (dates, names) and post-processing
- Output: standardized CSV with one row per discovered company
- Easy to extend (add more fields, integrate vector DBs, or connect to a database)
