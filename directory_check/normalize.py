"""Normalization helpers so NPPES and FHIR data can be compared field-by-field."""

import re

_STREET_ABBREVIATIONS = {
    "STREET": "ST", "AVENUE": "AVE", "ROAD": "RD", "DRIVE": "DR", "BOULEVARD": "BLVD",
    "LANE": "LN", "COURT": "CT", "CIRCLE": "CIR", "PLACE": "PL", "PARKWAY": "PKWY",
    "HIGHWAY": "HWY", "SUITE": "STE", "BUILDING": "BLDG", "FLOOR": "FL",
    "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W",
    "NORTHEAST": "NE", "NORTHWEST": "NW", "SOUTHEAST": "SE", "SOUTHWEST": "SW",
}


def phone(value):
    """Return the 10-digit US phone number, or None if it isn't one."""
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) == 10 else None


def zip5(value):
    digits = re.sub(r"\D", "", value or "")
    return digits[:5] if len(digits) >= 5 else None


def street(value):
    words = re.sub(r"[^\w\s]", " ", (value or "").upper()).split()
    return " ".join(_STREET_ABBREVIATIONS.get(w, w) for w in words)


def address_key(line, city, state, postal_code):
    """A comparable key for an address: (street, city, state, zip5)."""
    return (street(line), (city or "").strip().upper(), (state or "").strip().upper(), zip5(postal_code))


def name(value):
    return re.sub(r"[^A-Z]", "", (value or "").upper())
