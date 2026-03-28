# app/core/scan_parser.py
from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from typing import Any


_DTC_RE = re.compile(r"\b([B|C|P|U][0-9]{4})\b", re.IGNORECASE)


@dataclass(frozen=True)
class ScanParseResult:
    dtcs: list[str]
    raw_summary: dict[str, Any]


def _unique_preserve(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in seq:
        x2 = x.upper().strip()
        if x2 and x2 not in seen:
            seen.add(x2)
            out.append(x2)
    return out


def parse_scan_bytes(filename: str, content: bytes) -> ScanParseResult:
    name = (filename or "").lower().strip()
    text = None
    try:
        text = content.decode("utf-8", errors="ignore")
    except Exception:
        text = ""

    if name.endswith(".json"):
        return _parse_json(text)
    if name.endswith(".csv"):
        return _parse_csv(text)
    if name.endswith(".log") or name.endswith(".txt"):
        return _parse_text(text)

    # fallback: try JSON, then CSV, then text
    for fn in (_parse_json, _parse_csv, _parse_text):
        try:
            return fn(text)
        except Exception:
            continue
    return ScanParseResult(dtcs=[], raw_summary={"note": "unrecognized scan format"})


def _parse_text(text: str) -> ScanParseResult:
    dtcs = _unique_preserve(_DTC_RE.findall(text or ""))
    return ScanParseResult(dtcs=dtcs, raw_summary={"format": "text", "len": len(text or ""), "sample": (text or "")[:800]})


def _parse_csv(text: str) -> ScanParseResult:
    f = io.StringIO(text or "")
    reader = csv.DictReader(f)
    dtcs: list[str] = []
    rows: list[dict[str, Any]] = []
    for i, row in enumerate(reader):
        if i > 5000:
            break
        rows.append(row)
        blob = " ".join([str(v) for v in row.values() if v is not None])
        dtcs.extend(_DTC_RE.findall(blob))
    dtcs = _unique_preserve([d.upper() for d in dtcs])
    return ScanParseResult(dtcs=dtcs, raw_summary={"format": "csv", "rows": len(rows), "sample": rows[:20]})


def _parse_json(text: str) -> ScanParseResult:
    data = json.loads(text or "{}")
    dtcs: list[str] = []
    # Look for typical keys: dtcs, codes, troubleCodes, etc. Otherwise scan stringified JSON.
    if isinstance(data, dict):
        for key in ("dtcs", "codes", "troubleCodes", "trouble_codes", "DTCs"):
            if key in data and isinstance(data[key], list):
                dtcs.extend([str(x) for x in data[key]])
    dtcs.extend(_DTC_RE.findall(json.dumps(data)))
    dtcs = _unique_preserve([d.upper() for d in dtcs])
    return ScanParseResult(dtcs=dtcs, raw_summary={"format": "json", "keys": sorted(list(data.keys()))[:50] if isinstance(data, dict) else None})
