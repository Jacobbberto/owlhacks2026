"""
Loads call results from a filled-in CSV (see data/call_log_template.csv)
into the call_logs table, then rescores all providers.

Usage:
    python3 load_call_logs.py ../data/call_log_template.csv
"""

import csv
import sqlite3
import sys

from scoring import rescore_all

DB_PATH = "unghosted.db"

VALID_OUTCOMES = {
    "booked", "accepting", "not_accepting", "wrong_number", "no_answer", "voicemail_vague"
}


def load(csv_path):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    loaded, skipped = 0, 0

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            provider_id = (row.get("provider_id") or "").strip()
            provider_name = (row.get("provider_name") or "").strip()
            phone = (row.get("phone") or "").strip()
            outcome = (row.get("outcome") or "").strip()

            if not outcome:
                continue

            # Resolve provider_id by name (and phone, to disambiguate
            # providers with the same name at different locations) when
            # it's not given directly.
            if not provider_id:
                if not provider_name:
                    continue
                if phone:
                    matches = cur.execute(
                        "SELECT id FROM providers WHERE name = ? AND phone = ?",
                        (provider_name, phone),
                    ).fetchall()
                else:
                    matches = cur.execute(
                        "SELECT id FROM providers WHERE name = ?", (provider_name,)
                    ).fetchall()

                if not matches:
                    print(f"  skipping row: no provider found matching name='{provider_name}' phone='{phone}'")
                    skipped += 1
                    continue
                if len(matches) > 1:
                    print(f"  skipping row: multiple providers match name='{provider_name}' "
                          f"— add the phone number to disambiguate")
                    skipped += 1
                    continue
                provider_id = matches[0][0]

            if outcome not in VALID_OUTCOMES:
                print(f"  skipping row for provider {provider_id}: unrecognized outcome '{outcome}'")
                skipped += 1
                continue

            # actual_wait_days: whole number of days until the earliest
            # appointment they offered. Blank is fine (no offer / didn't ask).
            raw_wait = (row.get("actual_wait_days") or "").strip()
            actual_wait = None
            if raw_wait:
                if not raw_wait.isdigit():
                    print(f"  skipping row for provider {provider_id}: actual_wait_days must be a whole "
                          f"number of days, got '{raw_wait}' (convert '2 weeks' -> 14)")
                    skipped += 1
                    continue
                actual_wait = int(raw_wait)

            cur.execute(
                "INSERT INTO call_logs (provider_id, caller_name, outcome, actual_wait_days, notes) "
                "VALUES (?, ?, ?, ?, ?)",
                (int(provider_id), row.get("caller_name", ""), outcome, actual_wait, row.get("notes", "")),
            )
            loaded += 1

    conn.commit()
    conn.close()
    print(f"Loaded {loaded} call log rows ({skipped} skipped)")
    rescore_all()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 load_call_logs.py <path-to-csv>")
        sys.exit(1)
    load(sys.argv[1])
