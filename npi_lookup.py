"""
Cross-checks each provider in the database against the free NPI Registry API
and flags address mismatches. This does NOT run in a sandboxed environment
without internet access — run it on your own laptop.

The NPI Registry is a public, no-key-required API from CMS:
    https://npiregistry.cms.hhs.gov/api-page

Usage (from your laptop, inside backend/):
    python3 ../scripts/npi_lookup.py

What it does for each provider:
  1. Searches the NPI registry by last name (parsed from provider name) + PA
  2. If a match is found, compares the registry's practice address city/zip
     to the address on file
  3. Sets npi_number, npi_status, npi_address_match on the provider row

This is intentionally simple string matching for a 30-hour hackathon --
it will produce false negatives on nicknames, middle initials, etc. Note
that in the pitch: "an early, conservative signal, not a ground truth."
"""

import re
import sqlite3
import sys
import time

import requests  # pip install --break-system-packages requests

NPI_API = "https://npiregistry.cms.hhs.gov/api/"
DB_PATH = "unghosted.db"


def parse_last_name(provider_name: str) -> str:
    """
    Best-effort extraction of a last name from strings like:
      "Dr. Jane Okafor, LCSW" -> "Okafor"
      "Broad Street Behavioral Health" -> None (facility, not a person)
    """
    name = re.sub(r"^(Dr\.?|Mr\.?|Ms\.?|Mrs\.?)\s+", "", provider_name).strip()
    name = name.split(",")[0].strip()  # drop credentials after comma
    parts = name.split()
    if len(parts) < 2:
        return None
    return parts[-1]


def lookup_npi(last_name: str, state: str = "PA"):
    try:
        resp = requests.get(
            NPI_API,
            params={"version": "2.1", "last_name": last_name, "state": state, "limit": 5},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except requests.RequestException as e:
        print(f"  NPI lookup failed for {last_name}: {e}")
        return []


def zip_prefix_matches(address: str, npi_addresses: list) -> bool:
    """Loose match: does any NPI-listed practice address share the same 5-digit zip?"""
    m = re.search(r"\b(\d{5})\b", address or "")
    if not m:
        return False
    target_zip = m.group(1)
    for addr in npi_addresses:
        if addr.get("address_purpose") == "LOCATION" and addr.get("postal_code", "").startswith(target_zip[:5]):
            return True
    return False


def run():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM providers WHERE provider_type != 'Facility'")
    providers = cur.fetchall()

    checked = 0
    for p in providers:
        last_name = parse_last_name(p["name"])
        if not last_name:
            continue

        results = lookup_npi(last_name)
        time.sleep(0.3)  # be polite to the free API

        if not results:
            conn.execute(
                "UPDATE providers SET npi_address_match = NULL WHERE id = ?", (p["id"],)
            )
            continue

        result = results[0]
        npi_number = result.get("number")
        status = "active" if result.get("basic", {}).get("status") == "A" else "inactive"
        match = zip_prefix_matches(p["address"], result.get("addresses", []))

        conn.execute(
            "UPDATE providers SET npi_number = ?, npi_status = ?, npi_address_match = ? WHERE id = ?",
            (npi_number, status, 1 if match else 0, p["id"]),
        )
        checked += 1
        print(f"  {p['name']}: NPI {npi_number}, status={status}, address_match={match}")

    conn.commit()
    conn.close()
    print(f"\nChecked {checked} providers against the NPI registry.")
    print("Run `python3 scoring.py` next to fold these signals into scores.")


if __name__ == "__main__":
    run()
