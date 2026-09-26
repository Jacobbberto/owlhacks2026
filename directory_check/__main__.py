"""Command line interface.

    python -m directory_check npi 1003000126
    python -m directory_check search --last-name smith --state PA --limit 5
    python -m directory_check fhir 1447382219 --fhir-base https://hapi.fhir.org/baseR4
    python -m directory_check verify 1003000126 --call-outcome out_of_service --called-phone 443-602-6207
    python -m directory_check verify 1447382219 --fhir-base https://hapi.fhir.org/baseR4 --network "Acme HMO"
"""

import argparse
import json
import sys
from dataclasses import asdict

from .fhir import DEFAULT_FHIR_BASE, FHIRDirectoryClient
from .httpjson import APIError
from .npi import NPIClient
from .verify import CallOutcome, check_npi


def _dump(obj):
    def default(o):
        if isinstance(o, set):
            return sorted(o)
        return str(o)
    print(json.dumps(obj, indent=2, default=default))


def _record_summary(r):
    return {
        "npi": r.npi, "name": r.name, "type": r.enumeration_type, "status": r.status,
        "credential": r.credential, "primary_taxonomy": r.primary_taxonomy,
        "last_updated": r.last_updated,
        "locations": [f"{a.line1}, {a.city}, {a.state} {a.postal_code} ({a.phone})"
                      for a in r.location_addresses],
    }


def _fhir_client(args):
    headers = {"Authorization": f"Bearer {args.token}"} if args.token else None
    return FHIRDirectoryClient(args.fhir_base, headers=headers)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="directory_check")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("npi", help="Look up one NPI in NPPES")
    p.add_argument("npi")

    p = sub.add_parser("search", help="Search NPPES")
    for name in ("first-name", "last-name", "organization-name", "city", "state",
                 "postal-code", "taxonomy-description"):
        p.add_argument(f"--{name}")
    p.add_argument("--type", choices=["NPI-1", "NPI-2"], dest="enumeration_type")
    p.add_argument("--limit", type=int, default=10)

    def add_fhir_args(p, required):
        p.add_argument("--fhir-base", default=DEFAULT_FHIR_BASE if required else None,
                       help=f"FHIR directory base URL (default for `fhir`: {DEFAULT_FHIR_BASE})")
        p.add_argument("--token", help="Bearer token, if the directory requires one")

    p = sub.add_parser("fhir", help="Fetch a provider's listing from a FHIR directory")
    p.add_argument("npi")
    add_fhir_args(p, required=True)

    p = sub.add_parser("verify", help="Cross-check NPPES, FHIR directory and call outcome")
    p.add_argument("npi")
    add_fhir_args(p, required=False)
    p.add_argument("--network", dest="plan_network", help="Network/plan name the provider should be in")
    p.add_argument("--call-outcome", choices=[c.value for c in CallOutcome])
    p.add_argument("--called-phone")

    args = parser.parse_args(argv)
    try:
        if args.command == "npi":
            record = NPIClient().lookup(args.npi)
            _dump(_record_summary(record) if record else {"npi": args.npi, "found": False})
        elif args.command == "search":
            criteria = {k: v for k, v in vars(args).items() if k not in ("command", "limit")}
            _dump([_record_summary(r) for r in NPIClient().search(**criteria, limit=args.limit)])
        elif args.command == "fhir":
            _dump(asdict(_fhir_client(args).get_listing(args.npi)))
        elif args.command == "verify":
            report = check_npi(
                args.npi,
                fhir_client=_fhir_client(args) if args.fhir_base else None,
                plan_network=args.plan_network,
                call_outcome=args.call_outcome,
                called_phone=args.called_phone,
            )
            _dump(report.to_dict())
            return 1 if report.is_ghost else 0
    except (APIError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
