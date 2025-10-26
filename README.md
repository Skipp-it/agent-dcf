# Agent DCF API

Run a DCF with audited inputs (SEC), risk-free from FRED, market fields from Yahoo Finance, and a Google Finance fallback via Google Sheets.

## Quick start
```bash
python -m pip install --upgrade pip
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8080
