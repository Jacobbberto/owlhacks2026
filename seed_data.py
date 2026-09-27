"""
Seeds the Unghosted database with starter data.

IMPORTANT: These 20 rows are PLACEHOLDERS, not real CBH listings. This
sandbox has no internet access to pull CBH's live directory or its
self-reported availability spreadsheet, so the rows below mimic CBH's real
structure (provider types, specialties, North Philly zip codes near Temple)
but the names/phones/addresses are invented.

Before you demo:
  1. Pull real listings from CBH's directory: https://cbhphilly.org/members/provider-directory/
     (search by zip 19122/19133/19140, "Accepting New Patients" checked,
     Mental Health service type)
  2. Also grab the self-reported availability sheet linked on that page
     ("Outpatient Provider-Reported Routine, Urgent, and Emergent Appointment
     Availability") for reported_wait_days
  3. Replace the ROWS list below with real name/phone/address/specialty data
  4. Have the team call them (see data/call_log_template.csv) and load
     results with backend/load_call_logs.py
  5. Run scripts/npi_lookup.py (on a machine with real internet) to fill in
     npi_address_match / duplicate_listing_count

Run: python3 seed_data.py
"""

import sqlite3
import random

DB_PATH = "unghosted.db"

# (name, provider_type, specialty, phone, address, zip_code, languages,
#  population_served, accepting_new_patients_claimed, reported_wait_days,
#  telehealth_available)
ROWS = [
    ("Broad Street Behavioral Health", "Facility", "Mental Health Outpatient Clinics (MHOP)",
     "215-555-0101", "1500 N Broad St, Philadelphia, PA", "19122", "English,Spanish",
     "Adults, Children/Adolescents", 1, 5, 1),
    ("Dr. Jane Okafor, LCSW", "Independent Practitioner", "Licensed Clinical Social Workers (LCSW)",
     "215-555-0102", "1200 W Susquehanna Ave, Philadelphia, PA", "19122", "English",
     "Adults", 1, 3, 1),
    ("Temple Community Counseling", "Group Practitioner", "General Psychology",
     "215-555-0103", "1801 N Broad St, Philadelphia, PA", "19122", "English",
     "Adults, Children/Adolescents", 1, 14, 0),
    ("Marcus Reilly, LPC", "Independent Practitioner", "Licensed Professional Counselors (LPC)",
     "215-555-0104", "2100 N 11th St, Philadelphia, PA", "19133", "English",
     "Adults", 1, 7, 1),
    ("North Philly Wellness Center", "Facility", "Mental Health Outpatient Clinics (MHOP)",
     "215-555-0105", "2601 N 5th St, Philadelphia, PA", "19133", "English,Spanish,Arabic",
     "Adults, Children/Adolescents", 1, 10, 1),
    ("Dr. Priya Nair, Psychiatry", "Independent Practitioner", "Psychiatry",
     "215-555-0106", "1100 W Lehigh Ave, Philadelphia, PA", "19133", "English",
     "Adults", 1, 21, 1),
    ("Kensington Family Therapy", "Group Practitioner", "Licensed Marriage and Family Therapy (LMFT)",
     "215-555-0107", "2800 Kensington Ave, Philadelphia, PA", "19134", "English,Spanish",
     "Adults, Children/Adolescents", 1, 9, 0),
    ("Angela Whitfield, LSW", "Independent Practitioner", "Licensed Social Workers (LSW)",
     "215-555-0108", "1900 N 6th St, Philadelphia, PA", "19122", "English",
     "Adults", 0, None, 1),  # claims NOT accepting -- should score low
    ("Fairhill Behavioral Associates", "Facility", "Mental Health Outpatient Clinics (MHOP)",
     "215-555-0109", "2900 N 5th St, Philadelphia, PA", "19133", "English,Spanish",
     "Adults, Children/Adolescents", 1, 6, 1),
    ("Dr. Samuel Osei, LCSW", "Independent Practitioner", "Licensed Clinical Social Workers (LCSW)",
     "215-555-0110", "1500 N Broad St, Philadelphia, PA", "19122", "English",
     "Adults", 1, 4, 1),  # same address as row 1 -> duplicate signal
    ("Diamond Street Mental Health", "Facility", "Mental Health Outpatient Clinics (MHOP)",
     "215-555-0111", "2200 N Broad St, Philadelphia, PA", "19132", "English",
     "Adults, Children/Adolescents", 1, 12, 0),
    ("Renee Castillo, LMFT", "Independent Practitioner", "Licensed Marriage and Family Therapy (LMFT)",
     "215-555-0112", "1600 W Girard Ave, Philadelphia, PA", "19130", "English,Spanish",
     "Adults", 1, 8, 1),
    ("Hunting Park Counseling Services", "Group Practitioner", "General Psychology",
     "215-555-0113", "4200 N 6th St, Philadelphia, PA", "19140", "English,Spanish",
     "Adults, Children/Adolescents", 1, 15, 0),
    ("Dr. Robert Liu, Psychiatry", "Independent Practitioner", "Psychiatry",
     "215-555-0114", "3401 N Broad St, Philadelphia, PA", "19140", "English,Mandarin",
     "Adults", 1, 18, 1),
    ("Nicetown Behavioral Health", "Facility", "Mental Health Outpatient Clinics (MHOP)",
     "215-555-0115", "4501 Germantown Ave, Philadelphia, PA", "19144", "English",
     "Adults, Children/Adolescents", 1, 11, 1),
    ("Tanya Brooks, LPC", "Independent Practitioner", "Licensed Professional Counselors (LPC)",
     "215-555-0116", "1500 N Broad St, Philadelphia, PA", "19122", "English",
     "Adults", 1, 2, 1),  # 3rd listing at same address -> stronger duplicate signal
    ("Strawberry Mansion Family Services", "Group Practitioner", "Licensed Social Workers (LSW)",
     "215-555-0117", "2900 W Diamond St, Philadelphia, PA", "19121", "English",
     "Adults, Children/Adolescents", 0, None, 0),  # claims NOT accepting
    ("Dr. Fatima Al-Sayed, LCSW", "Independent Practitioner", "Licensed Clinical Social Workers (LCSW)",
     "215-555-0118", "2500 W Lehigh Ave, Philadelphia, PA", "19132", "English,Arabic",
     "Adults", 1, 5, 1),
    ("Ridge Avenue Counseling", "Facility", "Mental Health Outpatient Clinics (MHOP)",
     "215-555-0119", "3200 Ridge Ave, Philadelphia, PA", "19121", "English,Spanish",
     "Adults, Children/Adolescents", 1, 13, 0),
    ("James Whitaker, Art Therapy", "Independent Practitioner", "Art Therapy",
     "215-555-0120", "1700 N American St, Philadelphia, PA", "19122", "English",
     "Adults, Children/Adolescents", 1, 6, 1),
]


def seed():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for row in ROWS:
        cur.execute(
            """
            INSERT INTO providers (
                name, provider_type, specialty, phone, address, zip_code,
                languages, population_served, accepting_new_patients_claimed,
                reported_wait_days, telehealth_available, data_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'placeholder')
            """,
            row,
        )
    conn.commit()

    # Flag duplicate addresses now, so the scoring model has something to work
    # with even before real NPI lookups run.
    cur.execute(
        """
        UPDATE providers
        SET duplicate_listing_count = (
            SELECT COUNT(*) - 1 FROM providers p2 WHERE p2.address = providers.address
        )
        """
    )
    conn.commit()
    print(f"Seeded {len(ROWS)} placeholder providers into {DB_PATH}")
    conn.close()


if __name__ == "__main__":
    seed()
