# TheraVerify

**An auditing engine that flags "ghost network" listings in mental health provider directories.**

Built for [OwlHacks 2026](https://www.mlh.com/events/owlhacks-e2/prizes).

> If you or someone you know is in crisis, call or text **988** (Suicide & Crisis Lifeline).

## The problem: ghost networks

Insurance provider directories are supposed to tell patients which mental health providers they can see. In practice, many listings are "ghosts": the number is disconnected, the provider left the network or retired, or they aren't taking new patients.

A 2023 U.S. Senate Finance Committee secret shopper study of 12 Medicare Advantage plans in 6 states found that more than 80% of listed mental health providers contacted were unreachable, not in-network, or not accepting new patients. Callers got an appointment only 18% of the time.

That failure cascades:

1. **Financial harm:** Patients who can't find an in-network provider pay out of pocket for out-of-network care.
2. **Clinical harm:** People seeking help, sometimes in crisis, give up after a string of dead ends.
3. **Compliance risk:** Insurers must keep directories accurate (the federal No Surprises Act requires regular verification) and meet network adequacy standards.

## The solution

TheraVerify pulls listings from an insurer's directory, cross-references each one against the federal NPI Registry, and adds the results of calling the listed number (from call logs, transcripts, or automated outbound calls). It flags out-of-service numbers, retired providers, insurance mismatches, and closed caseloads, so regulators and advocacy groups can hold insurers accountable. It shifts the burden of verification from patients to an automated system.

Mismatches are evidence, not proof: NPI Registry data is self-reported and can be stale too. That's why every flag comes with its evidence and a severity, rather than a bare yes/no.

## Current status

| Component | Status |
|---|---|
| NPI Registry client (lookup, search, check-digit validation) | ✅ Built, tested against the live API |
| FHIR provider directory client (Da Vinci PDex Plan-Net) | ✅ Built; tested offline and against the public HAPI test server, not yet against a real insurer |
| Verification rules and call-outcome flags | ✅ Built, unit tested |
| Command-line interface | ✅ Built |
| CSV import, SQLite cache, 0 to 100 reliability score | 🔜 Planned |
| Dashboard (Streamlit) | 🔜 Planned |

## Quickstart

Requires Python 3.10+. No dependencies to install.

```bash
python3 -m unittest discover tests        # offline tests, no network needed

python3 -m directory_check npi 1003000126                                    # look up one NPI
python3 -m directory_check search --last-name "smi*" --state PA --limit 5     # search the registry
python3 -m directory_check verify 1003000126 \
    --call-outcome out_of_service --called-phone 443-602-6207                # simulate a failed call
```

Using an insurer's FHIR directory (check `[base]/metadata` first to see what it supports):

```bash
python3 -m directory_check fhir <NPI> --fhir-base https://<insurer-fhir-base>
python3 -m directory_check verify <NPI> --fhir-base https://<insurer-fhir-base> \
    --network "Plan network name" --call-outcome not_accepting_new --called-phone 215-555-0100
```

Call outcomes: `reached_accepting`, `not_accepting_new`, `insurance_not_accepted`, `provider_left`, `out_of_service`, `wrong_number`, `no_answer`.

`verify` prints a JSON report and exits with `0` if the listing looks usable, `1` if it's a likely ghost (any high-severity flag), and `2` on an error.

From Python:

```python
from directory_check import FHIRDirectoryClient, check_npi

report = check_npi("1003000126",
                   fhir_client=FHIRDirectoryClient("https://<insurer-fhir-base>"),
                   call_outcome="not_accepting_new")
report.is_ghost, [f.code for f in report.flags]
```

## How verification works

Each check produces a flag with a severity. **High** means a patient can't get care through this listing; **medium** means the listing is likely wrong; **low** is a data-quality issue worth a second look.

| Problem | Flags | Source |
|---|---|---|
| Out-of-service numbers | `PHONE_OUT_OF_SERVICE`, `WRONG_NUMBER` (high), `NO_PHONE` (medium), `PHONE_NOT_IN_NPPES`, `NO_ANSWER` (low) | Call outcome, directory, NPI Registry |
| Retired or departed providers | `INVALID_NPI`, `NPI_DEACTIVATED`, `NPI_INACTIVE`, `PROVIDER_LEFT_PRACTICE` (high) | NPI Registry, call outcome |
| Insurance mismatches | `INSURANCE_NOT_ACCEPTED` (high), `NETWORK_NOT_LISTED` (medium), `NO_NETWORK_LISTED` (low) | Call outcome, directory |
| Closed caseloads | `NOT_ACCEPTING_NEW_PATIENTS` (medium from the directory, high from a call), `DIRECTORY_CONTRADICTED` (high) | Directory, call outcome |
| Stale or inconsistent data | `NAME_MISMATCH`, `LISTING_INACTIVE`, `NO_ACTIVE_ROLES` (medium), `ADDRESS_NOT_IN_NPPES`, `NOT_IN_DIRECTORY` (low) | Directory vs. NPI Registry |

`DIRECTORY_CONTRADICTED` is the strongest evidence: the directory says the provider is accepting new patients, but the office says they aren't.

The NPI Registry API doesn't return deactivated NPIs, so a number that passes the check-digit test but has no record is flagged as likely deactivated (retired, deceased, or revoked).

## Architecture

```
 FHIR directory API ──► fhir.py ─────┐
                                     │
 NPI Registry API ────► npi.py ──────┼─► verify.py ─► report (flags + severity) ─► CLI / future dashboard
                                     │
 Call outcome ───────────────────────┘
```

| File | Purpose |
|---|---|
| `directory_check/npi.py` | NPPES NPI Registry API v2.1 client and NPI check-digit validation |
| `directory_check/fhir.py` | FHIR R4 client: Practitioner → PractitionerRole → Location, Organization, insurance network, accepting-new-patients |
| `directory_check/verify.py` | Rules that turn the data above into flags |
| `directory_check/normalize.py` | Phone, zip, street address, and name normalization for comparisons |
| `directory_check/httpjson.py` | Standard-library HTTP client with retries |
| `directory_check/__main__.py` | Command-line interface |
| `tests/` | Offline unit tests with mocked registry and directory data |

The engine has no UI dependencies, so any front end (Streamlit, `customtkinter`, a web app) can call the same functions.

## Planned: reliability score

The flags above will feed a **Provider Reliability Score** from 0 to 100, with every deduction itemized. Each listing starts at 100; these weights are starting estimates to tune against secret-shopper call results:

| Evidence | Points |
|---|---|
| NPI fails the check digit, or has no active NPI Registry record | −65 |
| No NPI on the listing | −30 |
| Listed specialty doesn't match registered taxonomy | −25 |
| Phone or zip differs from the registry | −15 each |
| Same zip but different street address; name mismatch (individuals only) | −10 each |
| Phone shared by 5+ providers; provider at 4+ locations; not updated in a year | −10 each |
| Directory says not accepting new patients | −5 |
| Patient call reports (decay by half every 90 days, capped) | −50 to +25 |

**Bands:** 85 and up is *likely reachable*, 50 to 84 *needs verification*, below 50 *likely ghost*.

## Data sources

- **NPI Registry (NPPES):** Federal registry of provider NPIs, including specialty taxonomy and practice locations. Free, public, no key. It confirms NPI records, not state licensure or network status.
- **FHIR provider directory APIs:** Medicare Advantage, Medicaid, CHIP, and ACA marketplace plans must publish directories through a public API under the CMS Interoperability and Patient Access rule, using the Da Vinci PDex Plan-Net format. Look for a "developer" or "interoperability" page on the insurer's website. The public HAPI server (`https://hapi.fhir.org/baseR4`) works for smoke tests, but its sample data has no networks or new-patient info.
- **Community Behavioral Health (CBH):** Manages Medicaid behavioral health in Philadelphia. Its online directory mostly lists organizations and clinics, which have their own (NPI-2) numbers.

## Limitations

- NPI Registry data is self-reported and may itself be outdated.
- Network status and "accepting new patients" can only be confirmed by calling, which is why call outcomes carry the most weight.
- Organization names in directories often differ from registered legal names, so name matching only applies to individual providers.
- Directory implementations vary; some servers don't support `_include`, so the client falls back to fetching references one at a time.

## Roadmap

### Hackathon MVP

**Phase 0: Setup and scoping**
- [x] Repo and project structure
- [x] Test the NPI Registry API with a real NPI
- [ ] Lock scope: one plan, a set of Philly zip codes, behavioral health specialties
- [ ] Find a live insurer FHIR provider directory endpoint and check its `/metadata`
- [ ] CI pipeline (GitHub Actions running the tests)

**Phase 1: Ingestion**
- [x] FHIR directory client (Practitioner, PractitionerRole, Location, Organization, network, with paging)
- [ ] CSV import for hand-collected listings (columns: npi, name, specialty, address, city, state, zip, phone, accepting_new, last_updated)
- [ ] Collect 20 to 50 real listings from the CBH directory into a CSV
- [ ] Run the FHIR client against a live insurer endpoint (fall back to CSV if it isn't working by the halfway point)
- [ ] Batch mode: verify a whole directory or CSV, not one NPI at a time

**Phase 2: NPI verification**
- [x] NPI Registry client with check-digit validation
- [x] Field-by-field comparison with normalization (phone, address, zip, name)
- [ ] SQLite cache for registry lookups and an offline demo mode
- [ ] Specialty check: map plain-English specialties to NUCC taxonomy codes and verify against the official list
- [ ] Directory-wide pattern checks (shared phone numbers, many locations, stale listings)

**Phase 3: Scoring**
- [x] Explainable flags with severity and evidence
- [ ] 0 to 100 reliability score with call report decay
- [ ] Tune weights against secret-shopper call results

**Phase 4: Dashboard**
- [ ] Listings table and side-by-side detail view (directory vs. registry)
- [ ] Call logging form
- [ ] Coverage by zip code, then a map view of gaps

**Phase 5: Secret shopper study**
- [ ] Call about 20 real listings and log outcomes
- [ ] Compare call results with flags and scores; turn it into a pitch slide

**Phase 6: Deploy and demo**
- [ ] Synthetic demo data (fictional names, 555-01XX phone numbers, clearly fake NPIs)
- [ ] Deploy the dashboard to a live URL
- [ ] Record a backup demo video
- [ ] Final pitch deck

### After the hackathon

- [ ] LLM parsing of call transcripts and PDF provider directories
- [ ] Anomaly detection model alongside the rule-based score
- [ ] Automated outbound phone line checks
- [ ] CSV and Excel export for regulators running batch compliance checks
- [ ] State license verification (Pennsylvania Department of State)
- [ ] Use NPI Registry search to find behavioral health providers in a zip who are missing from a plan's directory

## Team

| Role | Owns |
|---|---|
| Data | FHIR client, data collection, normalization |
| Engine | NPI verification, flags and scoring, tests |
| Frontend | Dashboard, deployment |
| Pitch | Secret shopper calls, business case, deck |
