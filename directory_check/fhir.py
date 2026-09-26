"""Client for FHIR R4 provider directories (Da Vinci PDex Plan-Net).

CMS requires Medicare Advantage, Medicaid, CHIP and ACA exchange plans to
publish a public, unauthenticated Provider Directory API built on the
Plan-Net implementation guide:
https://hl7.org/fhir/us/davinci-pdex-plan-net/

The data model we care about:
    Practitioner      -- the person, identified by NPI
    PractitionerRole  -- "this practitioner, at this Location, for this
                         Organization, in this insurance network", with
                         phone numbers, specialty, and accepting-new-patients
    Location          -- address / phone of the office
    Organization      -- the practice group, and also the insurance
                         network itself (Organization.type = "ntwk")
    InsurancePlan     -- the plan product, pointing at its networks

Servers that don't implement Plan-Net (e.g. the public HAPI test server)
still work; the Plan-Net-specific fields just come back empty.
"""

from dataclasses import dataclass, field

from . import normalize
from .httpjson import APIError, get_json

NPI_SYSTEM = "http://hl7.org/fhir/sid/us-npi"
PLAN_NET = "http://hl7.org/fhir/us/davinci-pdex-plan-net/StructureDefinition"
NETWORK_EXT = f"{PLAN_NET}/network-reference"
NEW_PATIENTS_EXT = f"{PLAN_NET}/newpatients"

# Codes from the Plan-Net AcceptingPatientsVS value set.
ACCEPTING_CODES = {
    "newpt": "accepting",
    "nopt": "not_accepting",
    "existptonly": "existing_only",
    "existptfam": "existing_and_family_only",
}

DEFAULT_FHIR_BASE = "https://hapi.fhir.org/baseR4"


@dataclass
class DirectoryLocation:
    reference: str
    name: str | None
    address_line: str
    city: str
    state: str
    postal_code: str
    phones: set[str] = field(default_factory=set)
    active: bool = True

    @property
    def key(self):
        return normalize.address_key(self.address_line, self.city, self.state, self.postal_code)


@dataclass
class DirectoryRole:
    """One PractitionerRole: how the insurer says a patient can reach this provider."""
    reference: str
    active: bool
    organization: str | None
    specialties: list[str]
    phones: set[str]
    locations: list[DirectoryLocation]
    networks: list[str]  # display names (or references) of insurance networks
    accepting_new_patients: str | None  # a value from ACCEPTING_CODES, or None if unstated
    last_updated: str | None


@dataclass
class DirectoryListing:
    """Everything a FHIR directory says about one NPI."""
    npi: str
    practitioner_ref: str | None
    name: str | None
    active: bool | None
    roles: list[DirectoryRole] = field(default_factory=list)

    @property
    def found(self):
        return self.practitioner_ref is not None

    @property
    def phones(self):
        out = set()
        for r in self.roles:
            out |= r.phones
            for loc in r.locations:
                out |= loc.phones
        return out

    @property
    def locations(self):
        return [loc for r in self.roles for loc in r.locations]

    @property
    def networks(self):
        return sorted({n for r in self.roles for n in r.networks})


# ---------------------------------------------------------------- parsing helpers

def _telecom_phones(resource):
    return {
        p for t in resource.get("telecom", [])
        if t.get("system") == "phone" and (p := normalize.phone(t.get("value")))
    }


def _human_name(resource):
    for n in resource.get("name", []):
        if n.get("text"):
            return n["text"]
        parts = n.get("given", []) + ([n["family"]] if n.get("family") else [])
        if parts:
            return " ".join(parts)
    return None


def _extensions(resource, url):
    return [e for e in resource.get("extension", []) if e.get("url") == url]


def _accepting_new_patients(resource):
    for ext in _extensions(resource, NEW_PATIENTS_EXT):
        for sub in ext.get("extension", []):
            if sub.get("url") == "acceptingPatients":
                for coding in sub.get("valueCodeableConcept", {}).get("coding", []):
                    if coding.get("code") in ACCEPTING_CODES:
                        return ACCEPTING_CODES[coding["code"]]
    return None


def _codeable_text(cc):
    if cc.get("text"):
        return cc["text"]
    for c in cc.get("coding", []):
        if c.get("display") or c.get("code"):
            return c.get("display") or c.get("code")
    return None


def parse_location(ref, resource):
    addr = resource.get("address", {})
    return DirectoryLocation(
        reference=ref,
        name=resource.get("name"),
        address_line=" ".join(addr.get("line", [])),
        city=addr.get("city", ""),
        state=addr.get("state", ""),
        postal_code=addr.get("postalCode", ""),
        phones=_telecom_phones(resource),
        active=resource.get("status", "active") == "active",
    )


# ---------------------------------------------------------------- client

class FHIRDirectoryClient:
    def __init__(self, base_url=DEFAULT_FHIR_BASE, headers=None, timeout=20):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self._cache = {}  # "Type/id" -> resource

    def _get(self, path, params=None):
        return get_json(f"{self.base_url}/{path}", params, headers=self.headers, timeout=self.timeout)

    def search(self, resource_type, params, max_pages=5):
        """Run a search and follow `next` links. Returns (matches, included_by_ref)."""
        matches, included = [], {}
        bundle = self._get(resource_type, params)
        for _ in range(max_pages):
            for entry in bundle.get("entry", []):
                res = entry.get("resource", {})
                ref = f"{res.get('resourceType')}/{res.get('id')}"
                self._cache[ref] = res
                if entry.get("search", {}).get("mode", "match") == "include":
                    included[ref] = res
                else:
                    matches.append(res)
            next_url = next((l["url"] for l in bundle.get("link", []) if l.get("relation") == "next"), None)
            if not next_url:
                break
            bundle = get_json(next_url, headers=self.headers, timeout=self.timeout)
        return matches, included

    def read(self, reference):
        """Resolve a relative reference like 'Location/123', using the cache first."""
        if reference not in self._cache:
            self._cache[reference] = self._get(reference)
        return self._cache[reference]

    def _resolve(self, ref_obj, included):
        """Resolve a Reference element to a resource (or None if it can't be fetched)."""
        ref = (ref_obj or {}).get("reference")
        if not ref or ref.startswith("#"):
            return None, ref_obj.get("display") if ref_obj else None
        if "://" in ref:  # absolute URL -> keep only Type/id if it's on this server
            if not ref.startswith(self.base_url):
                return None, ref_obj.get("display")
            ref = ref[len(self.base_url) + 1:]
        if ref in included:
            return included[ref], ref
        try:
            return self.read(ref), ref
        except APIError:
            return None, ref

    def find_practitioners(self, npi):
        matches, _ = self.search("Practitioner", {"identifier": f"{NPI_SYSTEM}|{npi}"})
        return matches

    def find_organizations(self, npi):
        matches, _ = self.search("Organization", {"identifier": f"{NPI_SYSTEM}|{npi}"})
        return matches

    def get_roles(self, practitioner_ref):
        params = [
            ("practitioner", practitioner_ref),
            ("_include", "PractitionerRole:location"),
            ("_include", "PractitionerRole:organization"),
            ("_count", "50"),
        ]
        try:
            roles, included = self.search("PractitionerRole", params)
        except APIError as e:
            if e.status != 400:
                raise
            # Some servers reject _include; fall back and resolve references one by one.
            roles, included = self.search("PractitionerRole", {"practitioner": practitioner_ref})
        return [self._parse_role(r, included) for r in roles]

    def _parse_role(self, role, included):
        locations = []
        for loc_ref in role.get("location", []):
            res, ref = self._resolve(loc_ref, included)
            if res:
                locations.append(parse_location(ref, res))

        org_res, org_ref = self._resolve(role.get("organization"), included)
        org_name = org_res.get("name") if org_res else org_ref

        networks = []
        for ext in _extensions(role, NETWORK_EXT):
            ref_obj = ext.get("valueReference", {})
            res, ref = self._resolve(ref_obj, included)
            networks.append((res or {}).get("name") or ref_obj.get("display") or ref)

        return DirectoryRole(
            reference=f"PractitionerRole/{role.get('id')}",
            active=role.get("active", True),
            organization=org_name,
            specialties=[t for s in role.get("specialty", []) if (t := _codeable_text(s))],
            phones=_telecom_phones(role),
            locations=locations,
            networks=[n for n in networks if n],
            accepting_new_patients=_accepting_new_patients(role),
            last_updated=role.get("meta", {}).get("lastUpdated"),
        )

    def get_listing(self, npi):
        """Everything this directory publishes for an individual NPI."""
        practitioners = self.find_practitioners(npi)
        if not practitioners:
            return DirectoryListing(npi=npi, practitioner_ref=None, name=None, active=None)
        # A directory can (wrongly) contain duplicate Practitioners for one NPI;
        # merge the roles of all of them.
        first = practitioners[0]
        listing = DirectoryListing(
            npi=npi,
            practitioner_ref=f"Practitioner/{first['id']}",
            name=_human_name(first),
            active=first.get("active", True),
        )
        for p in practitioners:
            listing.roles.extend(self.get_roles(f"Practitioner/{p['id']}"))
        return listing
