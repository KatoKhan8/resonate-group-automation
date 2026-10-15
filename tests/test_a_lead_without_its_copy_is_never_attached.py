"""A lead whose copy did not take is never attached - the incident control.

`bisonfactory._refuse_unvariabled_leads` is the structural half of the
2026-09-23 blank-email incident fix (operator decision, recorded in the
function): set the variables, READ THE LEAD BACK, and only then attach. The
measured failure is not hypothetical - a PATCH accepted-but-not-taken put 76
empty emails in front of real prospects on 2026-09-22/23, and nothing in the
staging readback showed it, because campaign, schedule, sender and membership
all looked right.

The property is about what is ON THE WIRE, not what we intended: a lead the
provider does not hold the wanted copy for is refused with `FactoryRefused`,
naming the lead and the variable that did not take - not passed silently and
not attached on the strength of our own copy of what we sent.

The provider read is faked, not made: `bison.lead` is patched to return a
lead holding everything the run wanted EXCEPT its subject. That is precisely
the accepted-but-did-not-take case, built without a network.
"""
import unittest
from unittest import mock

from src import bisonfactory
from src.providers import bison


LEAD = {
    "record_id": "acme",
    "contact_key": "acme-champ",
    "subject": "A real subject that says something",
    "copy": [{"body": "A real body that says something."}],
    # no persona: no offer, no cta - the copy under test is just the words
}


class ALeadWithoutItsCopyIsNeverAttached(unittest.TestCase):

    def test_a_lead_missing_its_subject_is_refused_by_name(self):
        wanted = {v["name"]: v["value"]
                  for v in bisonfactory._variables_for(
                      LEAD, {"client": "demo"}, sequence=[], sender=None)}
        self.assertIn("subject", wanted, "fixture: the run must want a subject")
        held = {name: value for name, value in wanted.items()
                if name != "subject"}
        provider_lead = {
            "id": "lead-1",
            "custom_variables": [{"name": name, "value": value}
                                 for name, value in held.items()],
        }
        report = {}
        with mock.patch.object(bison, "lead", return_value=provider_lead):
            with self.assertRaises(bisonfactory.FactoryRefused) as raised:
                bisonfactory._refuse_unvariabled_leads(
                    ["lead-1"], {"lead-1": LEAD}, {"client": "demo"},
                    {"provider_sequence": [], "sender": None}, report)
        message = str(raised.exception)
        self.assertIn("lead-1", message)
        self.assertIn("subject did not take", message)
        self.assertIn("Nothing was attached", message)
        self.assertEqual(
            report.get("provider", {}).get("leads_variable_verified"), 0,
            "a refused lead must not be counted as verified")


if __name__ == "__main__":
    unittest.main()
