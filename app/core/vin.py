# app/core/vin.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VinInfo:
    vin: str
    year: int | None
    make: str | None
    model_family: str | None
    platform: str | None
    notes: list[str]


_YEAR_MAP = {
    # 2021+ mapping commonly used in VIN 10th char. (I,O,Q,U,Z excluded in VIN year codes)
    "M": 2021,
    "N": 2022,
    "P": 2023,
    "R": 2024,
    "S": 2025,
    "T": 2026,
    "V": 2027,
    "W": 2028,
    "X": 2029,
    "Y": 2030,
}

# These are heuristics; exact decoding may require OEM access.
_WMI_MAKE = {
    "1G": "Chevrolet",
    "1C": "Chevrolet",
    "1Y": "Cadillac",
    "1G6": "Cadillac",
    "1GK": "GMC",
}


def decode_vin(vin: str) -> VinInfo:
    vin = (vin or "").strip().upper()
    notes: list[str] = []
    if len(vin) != 17:
        return VinInfo(vin=vin, year=None, make=None, model_family=None, platform=None, notes=["VIN must be 17 chars"])

    year_code = vin[9]
    year = _YEAR_MAP.get(year_code)
    if year is None:
        notes.append(f"Unknown year code '{year_code}'")

    make = None
    for k, v in _WMI_MAKE.items():
        if vin.startswith(k):
            make = v
            break
    if make is None:
        notes.append("Make not recognized from WMI")

    # Full model identification is not reliably possible without a richer decoder.
    # We keep it “shop-grade”: identify K2XX/T1XX-ish full-size SUV family heuristically.
    platform = "GM T1 (Full-Size SUV/Truck)"
    model_family = "Full-Size SUV (Tahoe/Suburban/Yukon/Escalade family)"
    notes.append("Heuristic VIN decode; for full RPO/build data use OEM/authorized decoder")

    return VinInfo(vin=vin, year=year, make=make, model_family=model_family, platform=platform, notes=notes)
