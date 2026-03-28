# GM Full-Size SUV AI Shop System

A simple, professional FastAPI app for **2021+ Suburban / Tahoe / Yukon / Yukon XL / Escalade / Escalade ESV**
focused on **5.3L L84** and **6.2L L87** platforms.

## What it does
- VIN intake and platform decode
- scan import (`.txt`, `.log`, `.csv`, `.json`)
- DTC extraction and symptom intake
- triage engine with ranked probable causes
- programming recommendation + preflight checklist
- approval-gated service action workflow
- repair case history with learning from prior outcomes
- screenshot upload placeholders for future expansion

## What it does not do
- autonomous key/immobilizer bypass
- unattended module flashing
- unattended security functions

## Run
```bash
cd gm_suv_shop_grade
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:
```text
http://127.0.0.1:8000
```

## Suggested next upgrades
- scanner-specific templates for your exact tool exports
- OCR/vision flow for scan screenshots
- real TSB ingestion from your own authorized sources
- role-based users / audit permissions
- J2534 or OEM launcher integration with human approval gate
