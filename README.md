# Unghosted

Find mental health providers who will actually see you. Built for OwlHacks 2026.

CBH's directory (Philadelphia's Medicaid behavioral health plan) lists providers,
but the listings are self-reported and go stale. This app scores each listing on
how likely it is to be real and open — using real call outcomes, NPI registry
checks, and duplicate-listing detection — and gets more accurate every time a
user reports what actually happened when they called.

## Quickstart

```bash
cd backend
pip install --break-system-packages fastapi uvicorn pydantic requests scikit-learn

# first time only: build the DB and load placeholder data
python3 -c "import sqlite3; c=sqlite3.connect('unghosted.db'); c.executescript(open('schema.sql').read()); c.commit()"
python3 seed_data.py

# start the API
uvicorn main:app --reload --port 8000
```

Then open `frontend/index.html` directly in a browser (double-click it, or
`python3 -m http.server 5500` from the `frontend/` folder and visit
`localhost:5500`). It talks to the API at `localhost:8000`.

## Before you demo: replace placeholder data with real CBH data

The 20 seed providers from `seed_data.py` are **placeholders** — realistic
North Philly addresses and CBH specialty categories, but invented
names/phones. No coding needed to replace them — it's a CSV anyone on the
team can fill in from a browser.

1. **Fill in `data/providers_template.csv`** with real listings from CBH's
   directory. Full instructions, including exactly which field on CBH's site
   maps to which CSV column, are in **`data/README_providers.md`**. Aim for
   20-40 rows across a few North Philly zip codes (19122, 19133, 19140,
   19132, 19121).
2. **Load it:**
   ```bash
   cd backend
   python3 -c "import sqlite3; c=sqlite3.connect('unghosted.db'); c.executescript(open('schema.sql').read()); c.commit()"
   python3 load_providers.py ../data/providers_template.csv
   ```
   The loader validates as it goes — it'll tell you exactly which row and
   column has a problem (a typo'd yes/no, a non-numeric wait time, a missing
   phone) instead of silently loading bad data or crashing.
3. **Make the calls.** Use `data/call_log_template.csv` — one row per call.
   See `data/README_call_log.md` for the outcome vocabulary and, critically,
   how to log `actual_wait_days` (the real wait, not what CBH claims).
4. **Load results and rescore:**
   ```bash
   python3 load_call_logs.py ../data/call_log_template.csv
   ```
5. **(Optional, needs real internet — won't run in a sandboxed dev environment)**
   Cross-check against the NPI registry:
   ```bash
   python3 ../scripts/npi_lookup.py
   python3 scoring.py
   ```

`seed_data.py` still works if you want to reset back to placeholder data
for local testing — just re-run it after rebuilding the schema.

## What makes this novel: claimed vs. real

CBH publishes a wait time for each provider, but providers report it
themselves and nobody checks it. Unghosted stores two numbers per provider:

- `reported_wait_days` — **"CBH says"**, from CBH's self-reported sheet
- `verified_wait_days` — **"We found"**, the most recent real wait from
  either a team call (`actual_wait_days` in the call log) or a user who
  booked and told us how far out it was

Every result card shows both side by side and flags big gaps. The stat
card at the top compares the averages across only the providers where we
have both numbers, so it's a fair comparison. "Soonest available" sorts by
the real wait when we have one, so a provider that under-reports its wait
can't jump the line.

**This only works if your team asks every provider they reach:**
"What's the earliest available appointment for a new patient?" and writes
down the number of days. See `data/README_call_log.md`.

## How the scoring works

`backend/scoring.py` is rule-based by default (transparent, easy to explain
to judges) and automatically switches to a logistic regression once you have
30+ labeled call outcomes (`MIN_LABELED_FOR_ML` in that file). Signals:

- Directory says "not accepting new patients" → big penalty
- Most recent call outcome (booked / accepting / not_accepting / wrong_number / no_answer)
- User-submitted outcome reports (the in-app crowdsourcing loop)
- NPI registry address match/mismatch
- How many other listings share the same address (duplicate/ghost signal)

Every score ships with a short human-readable reason — that's what's shown
in the UI and what you should read out in the demo.

## Project layout

```
backend/
  schema.sql          SQLite schema
  seed_data.py         placeholder provider data, for local testing only
  load_providers.py     loads data/providers_template.csv -> real demo data
  scoring.py            the scoring model
  load_call_logs.py     loads data/*.csv call results into the DB and rescores
  main.py               FastAPI app
frontend/
  index.html            the whole app: crisis check → search → ranked results →
                         call script → outcome report (single file, no build step)
data/
  providers_template.csv  fill this out with real CBH listings (no coding needed)
  README_providers.md     field-by-field guide, CBH site -> CSV column
  call_log_template.csv   fill this out during your calling session
  README_call_log.md      outcome vocabulary + instructions
  sample_call_results.csv example data proving the scoring loop works
scripts/
  npi_lookup.py          NPI registry cross-check (run on a laptop w/ internet)
```

## Demo script (~2 min)

1. Show the crisis-check screen — say why it's there.
2. Search zip 19122. Point at the top result's score and its plain-English reason.
3. Tap "Report outcome" on a mid-ranked provider → pick "wrong number" → watch
   the score drop live. That's the crowdsourcing loop.
4. Say the numbers from your real calls: "We called CBH's own list of
   [N] providers claiming to accept new patients. [X] were unreachable,
   [Y] said no. Here's who's actually real."

## Known gaps / what's next

- AI caller (Twilio-based, calls providers automatically) is a stretch goal,
  not built yet — see `main.py` for where a `/providers/{id}/auto-call` endpoint
  would hook in.
- NPI matching is last-name + zip only; good enough to demo, not production accurate.
- No auth — fine for a hackathon demo, not fine for real patient data.
