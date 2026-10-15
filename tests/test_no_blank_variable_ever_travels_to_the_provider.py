"""No blank variable ever travels to the provider.

`bisonfactory._variables_for` composes everything a lead carries at the
provider, and `bison._variables` drops empties: a variable whose value is
blank is not written at all rather than written as "". That drop is the
upstream half of the 2026-09-23 blank-email incident class - the measured
failure put empty subjects and `<p></p>` bodies in front of 76 real
prospects, and every downstream gate (`_refuse_unvariabled_leads`,
`_refuse_blank_render`) reads what this function produced. A blank that
travels is a blank those gates must each catch individually; a blank that
never ships cannot be missed.

The property: nothing in the returned variable list is blank. The fixture is
the incident's own input - a lead whose subject is empty and whose body is
real - so the test pins the exact case that reached prospects, asserted as
the general property rather than as a lookup of one name.
"""
import unittest

from src import bisonfactory


LEAD = {
    "record_id": "acme",
    "contact_key": "acme-champ",
    "subject": "",                       # the incident input, verbatim
    "copy": [{"body": "A real body that says something."}],
}


class NoBlankVariableEverTravelsToTheProvider(unittest.TestCase):

    def test_no_variable_in_the_list_is_blank(self):
        out = bisonfactory._variables_for(
            LEAD, {"client": "demo"}, sequence=[], sender=None)
        blanks = [v["name"] for v in out
                  if not str(v.get("value") or "").strip()]
        self.assertEqual(
            blanks, [],
            f"blank variables travelled to the provider: {blanks}")
        # and the incident's own subject is one of the things that did not
        # travel, not merely a name that happened to be absent
        names = [v["name"] for v in out]
        self.assertNotIn("subject", names)


if __name__ == "__main__":
    unittest.main()
