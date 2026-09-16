"""Every two-letter code in any record's office data must be in ISO_TO_NAME.

This is the check that would have caught TASK-201: 17 ISO codes were absent
from the lookup, silently making 21 records unresolvable.  The test scans
every record in the snapshot and fails on the first code the table cannot
map.  It also verifies the table covers the full ISO 3166-1 alpha-2 set.
"""
import json
import os
import unittest

from src import icpstructural


SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "work",
                        "queue.snapshot.jsonl")

# Full ISO 3166-1 alpha-2 set: 249 officially assigned codes.
# Source: ISO 3166 Maintenance Agency, ISO Online Browsing Platform.
FULL_ISO_3166_1_ALPHA2 = {
    "AD", "AE", "AF", "AG", "AI", "AL", "AM", "AO", "AQ", "AR",
    "AS", "AT", "AU", "AW", "AX", "AZ",
    "BA", "BB", "BD", "BE", "BF", "BG", "BH", "BI", "BJ", "BL",
    "BM", "BN", "BO", "BQ", "BR", "BS", "BT", "BV", "BW", "BY", "BZ",
    "CA", "CC", "CD", "CF", "CG", "CH", "CI", "CK", "CL", "CM",
    "CN", "CO", "CR", "CU", "CV", "CW", "CX", "CY", "CZ",
    "DE", "DJ", "DK", "DM", "DO", "DZ",
    "EC", "EE", "EG", "EH", "ER", "ES", "ET",
    "FI", "FJ", "FK", "FM", "FO", "FR",
    "GA", "GB", "GD", "GE", "GF", "GG", "GH", "GI", "GL", "GM",
    "GN", "GP", "GQ", "GR", "GS", "GT", "GU", "GW", "GY",
    "HK", "HM", "HN", "HR", "HT", "HU",
    "ID", "IE", "IL", "IM", "IN", "IO", "IQ", "IR", "IS", "IT",
    "JE", "JM", "JO", "JP",
    "KE", "KG", "KH", "KI", "KM", "KN", "KP", "KR", "KW", "KY", "KZ",
    "LA", "LB", "LC", "LI", "LK", "LR", "LS", "LT", "LU", "LV", "LY",
    "MA", "MC", "MD", "ME", "MF", "MG", "MH", "MK", "ML", "MM",
    "MN", "MO", "MP", "MQ", "MR", "MS", "MT", "MU", "MV", "MW",
    "MX", "MY", "MZ",
    "NA", "NC", "NE", "NF", "NG", "NI", "NL", "NO", "NP", "NR",
    "NU", "NZ",
    "OM",
    "PA", "PE", "PF", "PG", "PH", "PK", "PL", "PM", "PN", "PR",
    "PS", "PT", "PW", "PY",
    "QA",
    "RE", "RO", "RS", "RU", "RW",
    "SA", "SB", "SC", "SD", "SE", "SG", "SH", "SI", "SJ", "SK",
    "SL", "SM", "SN", "SO", "SR", "SS", "ST", "SV", "SX", "SY", "SZ",
    "TC", "TD", "TF", "TG", "TH", "TJ", "TK", "TL", "TM", "TN",
    "TO", "TR", "TT", "TV", "TW", "TZ",
    "UA", "UG", "UM", "US", "UY", "UZ",
    "VA", "VC", "VE", "VG", "VI", "VN", "VU",
    "WF", "WS",
    "YE", "YT",
    "ZA", "ZM", "ZW",
}


class TestISOCoverage(unittest.TestCase):
    """The lookup must cover every code the data uses, and the full standard."""

    def test_table_covers_full_iso_3166_1_alpha2(self):
        """Every officially assigned ISO 3166-1 alpha-2 code is in the table."""
        missing = FULL_ISO_3166_1_ALPHA2 - set(icpstructural.ISO_TO_NAME.keys())
        self.assertEqual(
            missing, set(),
            f"ISO_TO_NAME is missing {len(missing)} ISO 3166-1 alpha-2 codes: "
            f"{sorted(missing)}")

    def test_table_has_reserved_uk_alias(self):
        """UK is an exceptionally reserved code for GB and must be present."""
        self.assertIn("UK", icpstructural.ISO_TO_NAME)
        self.assertEqual(icpstructural.ISO_TO_NAME["UK"], "United Kingdom")
        self.assertEqual(icpstructural.ISO_TO_NAME["GB"], "United Kingdom")

    def test_no_office_code_is_unknown(self):
        """Every two-letter trailing token in office data resolves to a country.

        This is the test that would have caught the 17 missing codes.
        """
        if not os.path.exists(SNAPSHOT):
            self.skipTest("queue snapshot not available")

        unknown_codes = set()
        with open(SNAPSHOT, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                offices = (rec.get("company_facts") or {}).get("offices") or []
                for office_line in offices:
                    token = (str(office_line).strip().rstrip(".")
                             .split(",")[-1].strip().upper())
                    if token and len(token) == 2:
                        if token not in icpstructural.ISO_TO_NAME:
                            unknown_codes.add(token)

        self.assertEqual(
            unknown_codes, set(),
            f"{len(unknown_codes)} ISO code(s) in office data are not in "
            f"ISO_TO_NAME: {sorted(unknown_codes)}")

    def test_table_has_no_empty_values(self):
        """Every entry maps to a non-empty country name."""
        empty = [code for code, name in icpstructural.ISO_TO_NAME.items()
                 if not name or not name.strip()]
        self.assertEqual(empty, [])


if __name__ == "__main__":
    unittest.main()
