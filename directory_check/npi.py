"""Client for the CMS NPPES NPI Registry API (v2.1).

Docs: https://npiregistry.cms.hhs.gov/api-page
No API key required. Deactivated NPIs are not returned by the API, so a
lookup that comes back empty for a checksum-valid NPI usually means the
provider was deactivated (retired, deceased, or enumeration revoked).
"""

from dataclasses import dataclass, field

from . import normalize
from .httpjson import get_json

NPI_API_URL = "https://npiregistry.cms.hhs.gov/api/"
MAX_LIMIT = 200  # hard cap enforced by the API


def is_valid_npi(npi):
    """Check the NPI check digit (Luhn over '80840' + first 9 digits)."""
    npi = str(npi or "")
    if len(npi) != 10 or not npi.isdigit():
        return False
    digits = [int(d) for d in "80840" + npi[:9]]
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 0:  # double every other digit, starting from the rightmost
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - total % 10) % 10 == int(npi[9])


@dataclass
class NPIAddress:
    purpose: str  # LOCATION or MAILING
    line1: str
    line2: str
    city: str
    state: str
    postal_code: str
    phone: str | None
    fax: str | None

    @property
    def key(self):
        return normalize.address_key(self.line1, self.city, self.state, self.postal_code)


@dataclass
class NPIRecord:
    npi: str
    enumeration_type: str  # NPI-1 individual, NPI-2 organization
    status: str  # "A" = active
    name: str
    first_name: str | None
    last_name: str | None
    organization_name: str | None
    credential: str | None
    last_updated: str | None
    primary_taxonomy: str | None
    taxonomies: list[dict] = field(default_factory=list)
    addresses: list[NPIAddress] = field(default_factory=list)
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def is_active(self):
        return self.status == "A"

    @property
    def is_individual(self):
        return self.enumeration_type == "NPI-1"

    @property
    def location_addresses(self):
        return [a for a in self.addresses if a.purpose == "LOCATION"]

    @property
    def phones(self):
        return {a.phone for a in self.addresses if a.phone}


def _parse_address(a):
    return NPIAddress(
        purpose=a.get("address_purpose", ""),
        line1=a.get("address_1", ""),
        line2=a.get("address_2", ""),
        city=a.get("city", ""),
        state=a.get("state", ""),
        postal_code=a.get("postal_code", ""),
        phone=normalize.phone(a.get("telephone_number")),
        fax=normalize.phone(a.get("fax_number")),
    )


def parse_record(result):
    basic = result.get("basic", {})
    org = basic.get("organization_name")
    first, last = basic.get("first_name"), basic.get("last_name")
    display = org or " ".join(p for p in (first, basic.get("middle_name"), last) if p)
    taxonomies = result.get("taxonomies", [])
    primary = next((t for t in taxonomies if t.get("primary")), taxonomies[0] if taxonomies else None)
    # Primary addresses plus any secondary practice locations.
    addresses = [_parse_address(a) for a in result.get("addresses", [])]
    addresses += [_parse_address(a) for a in result.get("practiceLocations", [])]
    return NPIRecord(
        npi=result.get("number", ""),
        enumeration_type=result.get("enumeration_type", ""),
        status=basic.get("status", ""),
        name=display,
        first_name=first,
        last_name=last,
        organization_name=org,
        credential=basic.get("credential"),
        last_updated=basic.get("last_updated"),
        primary_taxonomy=primary.get("desc") if primary else None,
        taxonomies=taxonomies,
        addresses=addresses,
        raw=result,
    )


class NPIClient:
    def __init__(self, base_url=NPI_API_URL, timeout=15):
        self.base_url = base_url
        self.timeout = timeout

    def _query(self, **params):
        params = {k: v for k, v in params.items() if v not in (None, "")}
        params["version"] = "2.1"
        data = get_json(self.base_url, params, timeout=self.timeout)
        if data.get("Errors"):
            raise ValueError("; ".join(e.get("description", str(e)) for e in data["Errors"]))
        return [parse_record(r) for r in data.get("results", [])]

    def lookup(self, npi):
        """Return the NPIRecord for `npi`, or None if not found / deactivated."""
        npi = str(npi).strip()
        if not is_valid_npi(npi):
            raise ValueError(f"{npi!r} is not a valid NPI (bad length or check digit)")
        results = self._query(number=npi)
        return results[0] if results else None

    def search(self, first_name=None, last_name=None, organization_name=None,
               city=None, state=None, postal_code=None, taxonomy_description=None,
               enumeration_type=None, limit=10, skip=0):
        """Search the registry. Trailing '*' wildcards are allowed on names (min 2 chars).

        `enumeration_type` is "NPI-1" (individuals) or "NPI-2" (organizations).
        The API requires at least one criterion besides state.
        """
        return self._query(
            first_name=first_name, last_name=last_name, organization_name=organization_name,
            city=city, state=state, postal_code=postal_code,
            taxonomy_description=taxonomy_description, enumeration_type=enumeration_type,
            limit=min(limit, MAX_LIMIT), skip=skip,
        )
