-- Unghosted database schema
-- SQLite. Run: sqlite3 unghosted.db < schema.sql

DROP TABLE IF EXISTS providers;
DROP TABLE IF EXISTS call_logs;
DROP TABLE IF EXISTS user_reports;

-- One row per provider/practice listing pulled from CBH's directory.
CREATE TABLE providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    provider_type TEXT,              -- 'Independent Practitioner' | 'Group Practitioner' | 'Facility'
    specialty TEXT,                  -- e.g. 'Licensed Clinical Social Workers (LCSW)', 'Psychiatry'
    phone TEXT NOT NULL,
    address TEXT,
    zip_code TEXT,
    languages TEXT,                  -- comma-separated
    population_served TEXT,          -- 'Adults' | 'Children/Adolescents' | 'Adults, Children/Adolescents'
    accepting_new_patients_claimed INTEGER DEFAULT 1,  -- what CBH's directory/availability sheet says
    reported_wait_days INTEGER,      -- CLAIMED: from CBH's self-reported availability sheet, if present
    verified_wait_days INTEGER,      -- REAL: days until the next appointment actually offered on a call
                                     --   or reported by a user who booked. NULL = not yet checked.
    telehealth_available INTEGER DEFAULT 0,

    -- NPI registry cross-check (filled by scripts/npi_lookup.py)
    npi_number TEXT,
    npi_address_match INTEGER,       -- 1 = matches, 0 = mismatch, NULL = not checked
    npi_status TEXT,                 -- 'active' | 'inactive' | NULL

    -- duplicate detection
    duplicate_listing_count INTEGER DEFAULT 0,  -- how many other CBH listings share this phone/name

    -- derived score, recomputed by backend/scoring.py
    score INTEGER DEFAULT 50,
    score_reason TEXT,               -- short human-readable explanation shown in the UI

    data_source TEXT DEFAULT 'placeholder',  -- 'placeholder' | 'cbh_directory' | 'cbh_availability_sheet'
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- One row per call your team makes this weekend.
CREATE TABLE call_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL REFERENCES providers(id),
    caller_name TEXT,                -- who on the team made the call
    called_at TEXT DEFAULT (datetime('now')),
    outcome TEXT NOT NULL,           -- see data/call_log_template.csv for allowed values
    actual_wait_days INTEGER,        -- days from the call to the earliest appointment offered (NULL if none offered)
    notes TEXT
);

-- One row per in-app user report (the crowdsourced correction loop).
CREATE TABLE user_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL REFERENCES providers(id),
    outcome TEXT NOT NULL,           -- 'booked' | 'not_accepting' | 'wrong_number' | 'no_answer'
    wait_days INTEGER,               -- optional: for 'booked', how many days until the appointment
    reported_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_providers_zip ON providers(zip_code);
CREATE INDEX idx_call_logs_provider ON call_logs(provider_id);
CREATE INDEX idx_user_reports_provider ON user_reports(provider_id);
