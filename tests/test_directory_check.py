"""Offline tests: HTTP is mocked with NPPES- and Plan-Net-shaped payloads.

Run with:  python3 -m unittest discover tests
"""

import unittest
from unittest import mock

from directory_check import FHIRDirectoryClient, NPIClient, check_npi, is_valid_npi
from directory_check.fhir import NETWORK_EXT, NEW_PATIENTS_EXT, NPI_SYSTEM

NPI = "1003000126"
BASE = "https://directory.example-payer.com/fhir"

NPPES_RESPONSE = {
    "result_count": 1,
    "results": [{
        "number": NPI,
        "enumeration_type": "NPI-1",
        "basic": {"first_name": "ARDALAN", "last_name": "ENKESHAFI", "credential": "M.D.",
                  "status": "A", "last_updated": "2025-05-28"},
        "taxonomies": [{"code": "208M00000X", "desc": "Hospitalist", "primary": True}],
        "addresses": [{"address_purpose": "LOCATION", "address_1": "6410 Rockledge Drive Suite 304",
                       "city": "BETHESDA", "state": "MD", "postal_code": "208171841",
                       "telephone_number": "443-602-6207"}],
        "practiceLocations": [],
    }],
}


def _new_patients(code):
    return {"url": NEW_PATIENTS_EXT, "extension": [{
        "url": "acceptingPatients",
        "valueCodeableConcept": {"coding": [{"code": code}]},
    }]}


PRACTITIONER_BUNDLE = {"resourceType": "Bundle", "entry": [{
    "resource": {"resourceType": "Practitioner", "id": "p1", "active": True,
                 "identifier": [{"system": NPI_SYSTEM, "value": NPI}],
                 "name": [{"family": "Enkeshafi", "given": ["Ardalan"]}]},
    "search": {"mode": "match"},
}]}

ROLE_BUNDLE = {"resourceType": "Bundle", "entry": [
    {"resource": {
        "resourceType": "PractitionerRole", "id": "r1", "active": True,
        "practitioner": {"reference": "Practitioner/p1"},
        "organization": {"reference": "Organization/o1"},
        "location": [{"reference": "Location/l1"}],
        "telecom": [{"system": "phone", "value": "(215) 555-0100"}],
        "specialty": [{"coding": [{"display": "Internal Medicine"}]}],
        "extension": [
            {"url": NETWORK_EXT, "valueReference": {"reference": "Organization/net1"}},
            _new_patients("newpt"),
        ],
    }, "search": {"mode": "match"}},
    {"resource": {"resourceType": "Location", "id": "l1", "status": "active",
                  "address": {"line": ["100 Main St"], "city": "Philadelphia", "state": "PA",
                              "postalCode": "19104"}},
     "search": {"mode": "include"}},
    {"resource": {"resourceType": "Organization", "id": "o1", "name": "Main Street Medicine"},
     "search": {"mode": "include"}},
]}

NETWORK_ORG = {"resourceType": "Organization", "id": "net1", "name": "Acme Gold HMO Network"}


def fake_get_json(url, params=None, headers=None, timeout=None):
    if "npiregistry" in url:
        return NPPES_RESPONSE if dict(params)["number"] == NPI else {"result_count": 0, "results": []}
    if url == f"{BASE}/Practitioner":
        return PRACTITIONER_BUNDLE
    if url == f"{BASE}/PractitionerRole":
        return ROLE_BUNDLE
    if url == f"{BASE}/Organization/net1":
        return NETWORK_ORG
    raise AssertionError(f"unexpected request {url}")


@mock.patch("directory_check.npi.get_json", fake_get_json)
@mock.patch("directory_check.fhir.get_json", fake_get_json)
class DirectoryCheckTests(unittest.TestCase):
    def test_npi_checksum(self):
        self.assertTrue(is_valid_npi("1234567893"))  # CMS's documented example
        self.assertTrue(is_valid_npi(NPI))
        self.assertFalse(is_valid_npi("1234567890"))
        self.assertFalse(is_valid_npi("12345"))

    def test_npi_lookup(self):
        rec = NPIClient().lookup(NPI)
        self.assertEqual(rec.name, "ARDALAN ENKESHAFI")
        self.assertEqual(rec.primary_taxonomy, "Hospitalist")
        self.assertEqual(rec.phones, {"4436026207"})

    def test_deactivated_npi(self):
        report = check_npi("1234567893")
        self.assertEqual([f.code for f in report.flags], ["NPI_DEACTIVATED"])
        self.assertTrue(report.is_ghost)

    def test_fhir_listing(self):
        listing = FHIRDirectoryClient(BASE).get_listing(NPI)
        self.assertEqual(listing.name, "Ardalan Enkeshafi")
        role = listing.roles[0]
        self.assertEqual(role.organization, "Main Street Medicine")
        self.assertEqual(role.networks, ["Acme Gold HMO Network"])
        self.assertEqual(role.accepting_new_patients, "accepting")
        self.assertEqual(listing.phones, {"2155550100"})
        self.assertEqual(listing.locations[0].city, "Philadelphia")

    def test_full_verification(self):
        report = check_npi(NPI, fhir_client=FHIRDirectoryClient(BASE),
                           plan_network="Silver PPO", call_outcome="not_accepting_new",
                           called_phone="215-555-0100")
        codes = {f.code for f in report.flags}
        self.assertEqual(codes, {
            "PHONE_NOT_IN_NPPES", "ADDRESS_NOT_IN_NPPES", "NETWORK_NOT_LISTED",
            "NOT_ACCEPTING_NEW_PATIENTS", "DIRECTORY_CONTRADICTED",
        })
        self.assertTrue(report.is_ghost)

    def test_clean_listing_has_no_high_flags(self):
        report = check_npi(NPI, fhir_client=FHIRDirectoryClient(BASE),
                           plan_network="acme gold", call_outcome="reached_accepting")
        self.assertFalse(report.is_ghost)
        self.assertNotIn("NETWORK_NOT_LISTED", {f.code for f in report.flags})


if __name__ == "__main__":
    unittest.main()
