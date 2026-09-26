"""Cross-check an insurer's FHIR directory listing against NPPES and call results.

Each problem becomes a Flag. Flag codes map to the categories in the README:
    out-of-service numbers  -> PHONE_OUT_OF_SERVICE, WRONG_NUMBER, PHONE_NOT_IN_NPPES
    retired providers       -> NPI_DEACTIVATED, NPI_INACTIVE, PROVIDER_LEFT_PRACTICE
    insurance mismatches    -> INSURANCE_NOT_ACCEPTED, NO_NETWORK_LISTED
    closed caseloads        -> NOT_ACCEPTING_NEW_PATIENTS
"""

from dataclasses import asdict, dataclass, field
from enum import Enum

from . import normalize
from .fhir import DirectoryListing
from .npi import NPIRecord, is_valid_npi


class Severity(str, Enum):
    HIGH = "high"      # patient cannot get care through this listing
    MEDIUM = "medium"  # listing is likely wrong / misleading
    LOW = "low"        # data-quality issue worth a second look


class CallOutcome(str, Enum):
    """Result of calling the listed number (from a call log, transcript, or bot)."""
    REACHED_ACCEPTING = "reached_accepting"
    NOT_ACCEPTING_NEW = "not_accepting_new"
    INSURANCE_NOT_ACCEPTED = "insurance_not_accepted"
    PROVIDER_LEFT = "provider_left"
    OUT_OF_SERVICE = "out_of_service"
    WRONG_NUMBER = "wrong_number"
    NO_ANSWER = "no_answer"


@dataclass
class Flag:
    code: str
    severity: Severity
    message: str
    evidence: dict = field(default_factory=dict)


@dataclass
class VerificationReport:
    npi: str
    provider_name: str | None
    flags: list[Flag] = field(default_factory=list)

    @property
    def is_ghost(self):
        """True if the listing is unusable for a patient trying to get care."""
        return any(f.severity == Severity.HIGH for f in self.flags)

    def add(self, code, severity, message, **evidence):
        self.flags.append(Flag(code, severity, message, evidence))

    def to_dict(self):
        d = asdict(self)
        d["is_ghost"] = self.is_ghost
        return d


def _check_nppes(report, npi_record, listing):
    if npi_record is None:
        report.add("NPI_DEACTIVATED", Severity.HIGH,
                   "NPI is valid but not in the NPPES registry; it has likely been "
                   "deactivated (retired, deceased, or revoked).")
        return
    if not npi_record.is_active:
        report.add("NPI_INACTIVE", Severity.HIGH, f"NPPES status is {npi_record.status!r}, not active.")

    if listing is None or not listing.found:
        return

    # Name: compare last names for individuals (first names vary: nicknames, initials).
    if npi_record.is_individual and listing.name and npi_record.last_name:
        if normalize.name(npi_record.last_name) not in normalize.name(listing.name):
            report.add("NAME_MISMATCH", Severity.MEDIUM,
                       "Directory name does not match NPPES.",
                       directory=listing.name, nppes=npi_record.name)

    # Phones: directory numbers that NPPES has never heard of.
    unknown = listing.phones - npi_record.phones
    if listing.phones and unknown == listing.phones:
        report.add("PHONE_NOT_IN_NPPES", Severity.LOW,
                   "None of the directory's phone numbers appear in NPPES.",
                   directory=sorted(listing.phones), nppes=sorted(npi_record.phones))

    # Addresses: directory locations NPPES doesn't list (street + zip match).
    nppes_keys = {(a.key[0], a.key[3]) for a in npi_record.location_addresses}
    for loc in listing.locations:
        if loc.address_line and (loc.key[0], loc.key[3]) not in nppes_keys:
            report.add("ADDRESS_NOT_IN_NPPES", Severity.LOW,
                       "Directory location is not one of the provider's NPPES practice locations.",
                       location=loc.reference,
                       address=f"{loc.address_line}, {loc.city}, {loc.state} {loc.postal_code}")


def _check_directory(report, listing, plan_network):
    if listing is None:
        return
    if not listing.found:
        report.add("NOT_IN_DIRECTORY", Severity.LOW, "NPI not found in the FHIR directory.")
        return
    report.provider_name = report.provider_name or listing.name
    if listing.active is False:
        report.add("LISTING_INACTIVE", Severity.MEDIUM, "Practitioner is marked inactive in the directory.")

    active_roles = [r for r in listing.roles if r.active]
    if not active_roles:
        report.add("NO_ACTIVE_ROLES", Severity.MEDIUM,
                   "Directory has no active PractitionerRole (no place to actually see this provider).")
    for role in active_roles:
        if not role.phones and not any(loc.phones for loc in role.locations):
            report.add("NO_PHONE", Severity.MEDIUM, "Role lists no phone number.", role=role.reference)
        if not role.networks:
            report.add("NO_NETWORK_LISTED", Severity.LOW, "Role lists no insurance network.", role=role.reference)
        if role.accepting_new_patients in ("not_accepting", "existing_only", "existing_and_family_only"):
            report.add("NOT_ACCEPTING_NEW_PATIENTS", Severity.MEDIUM,
                       f"Directory itself says: {role.accepting_new_patients}.", role=role.reference)

    if plan_network:
        wanted = plan_network.strip().lower()
        if not any(wanted in n.lower() for n in listing.networks):
            report.add("NETWORK_NOT_LISTED", Severity.MEDIUM,
                       f"Provider is not listed in network {plan_network!r}.",
                       networks=listing.networks)


_CALL_FLAGS = {
    CallOutcome.OUT_OF_SERVICE: ("PHONE_OUT_OF_SERVICE", Severity.HIGH, "Listed number is out of service."),
    CallOutcome.WRONG_NUMBER: ("WRONG_NUMBER", Severity.HIGH, "Listed number does not reach this provider."),
    CallOutcome.PROVIDER_LEFT: ("PROVIDER_LEFT_PRACTICE", Severity.HIGH, "Office says the provider no longer practices there."),
    CallOutcome.NOT_ACCEPTING_NEW: ("NOT_ACCEPTING_NEW_PATIENTS", Severity.HIGH, "Office says the provider is not accepting new patients."),
    CallOutcome.INSURANCE_NOT_ACCEPTED: ("INSURANCE_NOT_ACCEPTED", Severity.HIGH, "Office says it does not accept this insurance."),
    CallOutcome.NO_ANSWER: ("NO_ANSWER", Severity.LOW, "No answer at listed number."),
}


def _check_call(report, call_outcome, called_phone, listing):
    if call_outcome is None:
        return
    outcome = CallOutcome(call_outcome)
    evidence = {"phone": called_phone} if called_phone else {}
    if outcome in _CALL_FLAGS:
        code, sev, msg = _CALL_FLAGS[outcome]
        report.add(code, sev, msg, **evidence)
    # A call contradicting the directory is the strongest evidence of an inaccurate listing.
    if outcome == CallOutcome.NOT_ACCEPTING_NEW and listing and listing.found:
        if any(r.accepting_new_patients == "accepting" for r in listing.roles):
            report.add("DIRECTORY_CONTRADICTED", Severity.HIGH,
                       "Directory says accepting new patients but the office says no.", **evidence)


def verify_provider(npi, npi_record=None, listing: DirectoryListing | None = None,
                    plan_network=None, call_outcome=None, called_phone=None,
                    npi_record_fetched=True):
    """Build a VerificationReport from already-fetched data.

    `npi_record` is the NPPES result (None means not found, if
    `npi_record_fetched` is True). `listing` is the FHIR directory listing, or
    None to skip directory checks. `call_outcome` is a CallOutcome (or its
    string value) from calling `called_phone`.
    """
    npi = str(npi).strip()
    report = VerificationReport(npi=npi, provider_name=npi_record.name if npi_record else None)
    if not is_valid_npi(npi):
        report.add("INVALID_NPI", Severity.HIGH, "NPI fails the check-digit test; it cannot be a real NPI.")
        return report
    if npi_record_fetched:
        _check_nppes(report, npi_record, listing)
    _check_directory(report, listing, plan_network)
    _check_call(report, call_outcome, normalize.phone(called_phone) or called_phone, listing)
    return report


def check_npi(npi, npi_client=None, fhir_client=None, **kwargs):
    """Convenience wrapper: fetch from NPPES (and FHIR, if a client is given), then verify."""
    from .npi import NPIClient

    npi = str(npi).strip()
    if not is_valid_npi(npi):
        return verify_provider(npi, **kwargs)
    npi_record = (npi_client or NPIClient()).lookup(npi)
    listing = fhir_client.get_listing(npi) if fhir_client else None
    return verify_provider(npi, npi_record, listing, **kwargs)


__all__ = ["CallOutcome", "Flag", "NPIRecord", "Severity", "VerificationReport", "check_npi", "verify_provider"]
