# 🧪 Gray Vial PDF Processor

A Streamlit app that processes lab report PDFs while preserving full layout integrity.

## What it does
- Keeps layout, text, tables, chromatogram, and footer unchanged
- Modifies ONLY the vial image on page 1
- Applies tone-preserving grayscale (no black cap issue)
- Returns a clean downloadable PDF

## How to use
1. Upload your lab report PDF
2. Adjust shadow/contrast if needed
3. Download the processed file

## Run locally
```bash
pip install -r requirements.txt
streamlit run pdf_gray_vial_app.py