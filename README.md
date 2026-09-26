# owlhacks2026
#https://www.mlh.com/events/owlhacks-e2/prizes

By analyzing phone call logs, transscrpits, or automated outbound call resonses, this tool flags out-of-service numbers, retired providers, insurance mismatches, and closed caseloads-helping regulatory bodies and advocacy groups hold insurance companies accountable.

## NPI + FHIR provider checks (`directory_check/`)

Pure Python 3.10+, no dependencies.

- `npi.py`: NPPES NPI Registry client (lookup, search, NPI check-digit validation). No API key needed.
- `fhir.py`: FHIR R4 provider-directory client (Da Vinci PDex Plan-Net, the format CMS requires payers to publish). Resolves Practitioner → PractitionerRole → Location / Organization / insurance network, plus the accepting-new-patients flag.
- `verify.py`: Cross-checks NPPES, the insurer's directory, and a call outcome, and returns flags such as `NPI_DEACTIVATED`, `PHONE_OUT_OF_SERVICE`, `NOT_ACCEPTING_NEW_PATIENTS`, `NETWORK_NOT_LISTED`, and `DIRECTORY_CONTRADICTED`.

```bash
python3 -m directory_check npi 1003000126
python3 -m directory_check search --last-name "smi*" --state PA --limit 5
python3 -m directory_check fhir <NPI> --fhir-base https://<payer-directory>/fhir
python3 -m directory_check verify <NPI> --fhir-base https://<payer-directory>/fhir \
    --network "Gold HMO" --call-outcome out_of_service --called-phone 215-555-0100
python3 -m unittest discover tests
```

```python
from directory_check import FHIRDirectoryClient, check_npi

report = check_npi("1003000126", fhir_client=FHIRDirectoryClient("https://<payer>/fhir"),
                   call_outcome="not_accepting_new")
report.is_ghost, [f.code for f in report.flags]
```
