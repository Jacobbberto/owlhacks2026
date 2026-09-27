"""
Loads real CBH providers from a filled-in CSV (see
data/README_providers.md and data/providers_template.csv) into the
providers table, then computes duplicate_listing_count and runs an
initial scoring pass.

This REPLACES seed_data.py's placeholder rows for the real demo. Run the
schema rebuild first if you haven't already:

    python3 -c "import sqlite3; c=sqlite3.connect('unghosted.db'); c.executescript(open('schema.sql').read()); c.commit()"
    python3 load_providers.py ../data/providers_template.csv

Safe to re-run: each run clears the providers table (and everything that
references it -- call_logs, user_reports) before reloading, so you can fix
a bad row and rerun without hand-editing the database.
"""

import csv
import sqlite3
import sys

from scoring import rescore_all

DB_PATH = "unghosted.db"

REQUIRED_COLUMNS = {"name", "phone"}
BOOLEAN_COLUMNS = {"accepting_new_patients_claimed", "telehealth_available"}
INT_COLUMNS = {"reported_wait_days"}

VALID_PROVIDER_TYPES = {"Independent Practitioner", "Group Practitioner", "Facility", ""}


def parse_bool(value, field, row_num, errors):
    value = (value or "").strip()
    if value in ("1", "yes", "true", "Yes", "TRUE", "True"):
        return 1
    if value in ("0", "no", "false", "No", "FALSE", "False", ""):
        return 0
    errors.append(f"row {row_num}: {field} must be 1/0 or yes/no, got '{value}' -- defaulting to 0")
    return 0


def parse_int_or_none(value, field, row_num, errors):
    value = (value or "").strip()
    if not value:
        return None
    if not value.isdigit():
        errors.append(f"row {row_num}: {field} must be a whole number of days, got '{value}' -- leaving blank")
        return None
    return int(value)


def load(csv_path):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Wipe existing providers (and dependent rows) so reruns start clean.
    cur.execute("DELETE FROM user_reports")
    cur.execute("DELETE FROM call_logs")
    cur.execute("DELETE FROM providers")
    conn.commit()

    loaded, skipped = 0, 0
    warnings = []

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        missing_cols = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing_cols:
            print(f"CSV is missing required column(s): {sorted(missing_cols)}")
            sys.exit(1)

        for i, row in enumerate(reader, start=2):  # row 1 is the header
            name = (row.get("name") or "").strip()
            phone = (row.get("phone") or "").strip()
            if not name or not phone:
                print(f"  skipping row {i}: name and phone are both required (got name='{name}', phone='{phone}')")
                skipped += 1
                continue

            provider_type = (row.get("provider_type") or "").strip()
            if provider_type and provider_type not in VALID_PROVIDER_TYPES:
                warnings.append(
                    f"row {i}: provider_type '{provider_type}' isn't one of "
                    f"{sorted(t for t in VALID_PROVIDER_TYPES if t)} -- keeping it anyway, but check for a typo"
                )

            accepting = parse_bool(row.get("accepting_new_patients_claimed"), "accepting_new_patients_claimed", i, warnings)
            telehealth = parse_bool(row.get("telehealth_available"), "telehealth_available", i, warnings)
            reported_wait = parse_int_or_none(row.get("reported_wait_days"), "reported_wait_days", i, warnings)

            cur.execute(
                """
                INSERT INTO providers (
                    name, provider_type, specialty, phone, address, zip_code,
                    languages, population_served, accepting_new_patients_claimed,
                    reported_wait_days, telehealth_available, data_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'cbh_directory')
                """,
                (
                    name,
                    provider_type,
                    (row.get("specialty") or "").strip(),
                    phone,
                    (row.get("address") or "").strip(),
                    (row.get("zip_code") or "").strip(),
                    (row.get("languages") or "").strip(),
                    (row.get("population_served") or "").strip(),
                    accepting,
                    reported_wait,
                    telehealth,
                ),
            )
            loaded += 1

    conn.commit()

    # Duplicate-listing signal: same address counted more than once.
    cur.execute(
        """
        UPDATE providers
        SET duplicate_listing_count = (
            SELECT COUNT(*) - 1 FROM providers p2
             WHERE p2.address = providers.address AND providers.address != ''
        )
        """
    )
    conn.commit()
    conn.close()

    print(f"\nLoaded {loaded} providers ({skipped} skipped)")
    if warnings:
        print(f"\n{len(warnings)} warning(s) -- these rows were still loaded, but double-check them:")
        for w in warnings:
            print(f"  {w}")

    if loaded < 15:
        print(
            f"\nHeads up: only {loaded} providers loaded. You'll want 20-40 for a "
            "convincing demo with real variety. Keep adding rows and rerun this script."
        )

    rescore_all()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 load_providers.py <path-to-csv>")
        sys.exit(1)
    load(sys.argv[1])
