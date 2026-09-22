"""They ask what the message SAYS, and the agent could only give its shape.

`docs/SLACK-AGENT-QUESTION-CATALOGUE.md`, on cadence and copy — 110
questions, the second-largest intent:

    `cadence_detail` gives the shape. **Nobody has ever asked for the
    shape.** They ask what the message *says*. Showing approved copy to a
    client in their own channel is a scope decision, not a missing
    function.

OPERATOR, 2026-09-22, making that decision: *a client may see the currently
approved steps of its own cadences in its own channel, email and LinkedIn,
as sent. Not variants under test, not history, not other clients. Internal
channels see everything including variants. Test: client A cannot see
client B's copy; the response never includes a step that is not in the
approved set.*

Both of the operator's named tests are here, and each is asserted more than
one way, because "the response never includes an unapproved step" is the
kind of property that passes by accident when the fixture happens to have
nothing unapproved in it.
"""
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import approval                                        # noqa: E402
from src import slackagenttools as tools                        # noqa: E402
from src import slackscope                                      # noqa: E402


def approved(step):
    """A step carrying a real approval for its own exact words."""
    slot = dict(step)
    slot["approval"] = {"by": "zb", "at": "2026-09-20T10:00:00Z",
                        "fingerprint": approval.fingerprint(slot)}
    return slot


def stale(step):
    """Approved, then edited. The fingerprint no longer matches."""
    slot = approved(step)
    slot["body"] = str(slot.get("body") or "") + " — and one more thing"
    return slot


def record(client, contact="c1", steps=None):
    return {"id": "r-%s-%s" % (client, contact), "client": client,
            "domain": "%s.test" % client,
            "cadence": {contact: dict(steps or {})}}


ALPHA_DAY1 = {"channel": "email", "subject": "Profitability on Monday",
              "body": "Hi Ivana, one line about margins."}
ALPHA_LI2 = {"channel": "linkedin", "note": "Thanks for connecting, Ivana."}
BETA_DAY1 = {"channel": "email", "subject": "BETA SECRET SUBJECT",
             "body": "Beta's own words, which alpha may never read."}


def client(workspace="alpha"):
    return slackscope.Scope(slackscope.CLIENT, workspace=workspace,
                            source="test")


def internal():
    return slackscope.Scope(slackscope.INTERNAL, source="test")


class Copy(unittest.TestCase):

    RECORDS = ()

    def setUp(self):
        self._default = tools._default_workspace
        tools._default_workspace = lambda: "alpha"
        rows = list(self.RECORDS) or self.estate()
        self._records = mock.patch.object(
            tools, "_records",
            lambda slug: [r for r in rows if r.get("client") == slug])
        self._records.start()

    def tearDown(self):
        self._records.stop()
        tools._default_workspace = self._default

    def estate(self):
        return [
            record("alpha", "c1", {"day1": approved(ALPHA_DAY1),
                                   "li2": approved(ALPHA_LI2)}),
            record("beta", "c9", {"day1": approved(BETA_DAY1)}),
        ]


# ================================ 1. IT SAYS WHAT THE MESSAGE SAYS

class TheWordsRatherThanTheShape(Copy):

    def test_a_client_sees_the_approved_email_copy(self):
        out = tools.campaign_copy(client("alpha"))
        body = json.dumps(out)
        self.assertIn("Profitability on Monday", body)
        self.assertIn("one line about margins", body)

    def test_linkedin_copy_comes_too(self):
        out = tools.campaign_copy(client("alpha"))
        steps = {(r["channel"], r["step"]): r for r in out["steps"]}
        self.assertIn(("linkedin", "li2"), steps)
        self.assertIn("Thanks for connecting",
                      json.dumps(steps[("linkedin", "li2")]))

    def test_it_can_be_narrowed_to_one_step_or_one_channel(self):
        one = tools.campaign_copy(client("alpha"), "day1")
        self.assertEqual([r["step"] for r in one["steps"]], ["day1"])
        email = tools.campaign_copy(client("alpha"), "linkedin")
        self.assertEqual([r["channel"] for r in email["steps"]],
                         ["linkedin"])

    def test_it_is_on_the_tool_list_for_both_scopes(self):
        self.assertIn("campaign_copy", tools.for_scope(client()))
        self.assertIn("campaign_copy", tools.for_scope(internal()))


# ================================ 2. NEVER A STEP OUTSIDE THE APPROVED SET

class TheApprovedSetIsTheWholeAnswer(Copy):

    def test_an_unapproved_step_is_absent(self):
        """The operator's second named test."""
        rows = [record("alpha", "c1", {
            "day1": approved(ALPHA_DAY1),
            "day4": {"channel": "email", "subject": "NEVER APPROVED",
                     "body": "A draft nobody signed."}})]
        with mock.patch.object(tools, "_records", lambda slug: rows):
            out = tools.campaign_copy(client("alpha"))
        self.assertNotIn("NEVER APPROVED", json.dumps(out))
        self.assertEqual([r["step"] for r in out["steps"]], ["day1"])

    def test_an_edited_step_drops_out_by_itself(self):
        """"Not history" needs no code that knows what history is: the
        approval is bound to the words, so changing one removes it."""
        rows = [record("alpha", "c1", {"day1": stale(ALPHA_DAY1)})]
        with mock.patch.object(tools, "_records", lambda slug: rows):
            out = tools.campaign_copy(client("alpha"))
        self.assertEqual(out["steps"], [])
        self.assertNotIn("one more thing", json.dumps(out))

    def test_a_revoked_approval_takes_the_step_with_it(self):
        slot = approved(ALPHA_DAY1)
        slot.pop("approval")
        rows = [record("alpha", "c1", {"day1": slot})]
        with mock.patch.object(tools, "_records", lambda slug: rows):
            out = tools.campaign_copy(client("alpha"))
        self.assertEqual(out["steps"], [])

    def test_an_internal_channel_gets_no_unapproved_step_either(self):
        """The approved set is the filter in every scope. Internal sees
        more ABOUT each message, not more messages."""
        rows = [record("alpha", "c1", {
            "day1": {"channel": "email", "subject": "NEVER APPROVED",
                     "body": "x"}})]
        with mock.patch.object(tools, "_records", lambda slug: rows):
            out = tools.campaign_copy(internal())
        self.assertNotIn("NEVER APPROVED", json.dumps(out))

    def test_an_empty_approved_set_says_which_kind_of_empty_it_is(self):
        rows = [record("alpha", "c1", {"day1": stale(ALPHA_DAY1)})]
        with mock.patch.object(tools, "_records", lambda slug: rows):
            out = tools.campaign_copy(client("alpha"))
        self.assertIn("empty approved set", out["note"])
        self.assertIn("not an empty cadence", out["note"])


# ================================ 3. CLIENT A CANNOT SEE CLIENT B'S COPY

class OneClientsWordsAreOnlyEverTheirs(Copy):

    def test_betas_own_channel_does_see_it(self):
        """The control for every assertion below. Without it they would
        all pass against an empty fixture."""
        out = tools.campaign_copy(client("beta"))
        self.assertIn("BETA SECRET SUBJECT", json.dumps(out))

    def test_alphas_channel_never_carries_betas_copy(self):
        """The operator's first named test."""
        out = tools.campaign_copy(client("alpha"))
        self.assertNotIn("BETA SECRET SUBJECT", json.dumps(out))
        self.assertNotIn("alpha may never read", json.dumps(out))
        # And alpha's own copy IS there, so the absence above is a filter
        # working rather than a lookup finding nothing.
        self.assertIn("Profitability on Monday", json.dumps(out))

    def test_no_argument_reaches_the_other_client(self):
        for phrasing in ("beta", "beta day1", "all", "../beta", None):
            out = tools.campaign_copy(client("alpha"), phrasing)
            self.assertNotIn("BETA SECRET", json.dumps(out), repr(phrasing))

    def test_the_workspace_comes_from_the_scope_not_the_argument(self):
        out = tools.campaign_copy(client("alpha"), "beta")
        self.assertEqual(out["workspace"], "alpha")

    def test_an_internal_channel_reads_one_workspace_at_a_time(self):
        self.assertNotIn("BETA SECRET",
                         json.dumps(tools.campaign_copy(internal())))


# ================================ 4. VARIANTS UNDER TEST

class WhatIsUnderTestIsNotShownAndIsNotHidden(Copy):

    def estate(self):
        under_test = approved(dict(ALPHA_DAY1,
                                   subject="VARIANT SUBJECT",
                                   variant_id="v-2", variant_style="bold"))
        return [record("alpha", "c1", {"day1": approved(ALPHA_DAY1)}),
                record("alpha", "c2", {"day1": under_test})]

    def test_a_client_is_not_shown_a_variant(self):
        out = tools.campaign_copy(client("alpha"))
        self.assertNotIn("VARIANT SUBJECT", json.dumps(out))

    def test_and_is_not_left_thinking_it_has_seen_everything(self):
        """An answer showing one of two and saying nothing reads as the
        whole set."""
        out = tools.campaign_copy(client("alpha"))
        self.assertEqual(out["withheld_under_test"], 1)
        self.assertIn("not shown here", out["withheld_note"])

    def test_no_variant_vocabulary_reaches_the_client_answer(self):
        body = json.dumps(tools.campaign_copy(client("alpha")))
        for word in ("variant_id", "variant_style", "v-2", "bold"):
            self.assertNotIn(word, body, word)

    def test_an_internal_channel_sees_the_variant_and_who_signed_it(self):
        out = tools.campaign_copy(internal())
        body = json.dumps(out)
        self.assertIn("VARIANT SUBJECT", body)
        self.assertIn("v-2", body)
        self.assertIn("zb", body)
        self.assertNotIn("withheld_under_test", out)

    def test_a_client_is_never_told_who_approved_it(self):
        """Who signed off inside Resonate is Resonate's record."""
        body = json.dumps(tools.campaign_copy(client("alpha")))
        self.assertNotIn("approved_by", body)
        self.assertNotIn("zb", body)


# ================================ 5. PERSONALISED COPY IS MANY TEXTS

class OneStepCanCarrySeveralMessages(Copy):

    def estate(self):
        rows = []
        for index in range(8):
            rows.append(record("alpha", "c%d" % index, {
                "day1": approved(dict(ALPHA_DAY1,
                                      body="Hi person %d." % index))}))
        rows.append(record("alpha", "shared", {
            "day1": approved(dict(ALPHA_DAY1, body="Hi person 0."))}))
        return rows

    def test_identical_texts_are_one_row_with_a_count(self):
        out = tools.campaign_copy(client("alpha"))
        step = out["steps"][0]
        top = step["messages"][0]
        self.assertEqual(top["approved_for_recipients"], 2)

    def test_the_cap_says_what_it_hid(self):
        out = tools.campaign_copy(client("alpha"))
        step = out["steps"][0]
        self.assertEqual(len(step["messages"]), tools.COPY_PER_STEP_CAP)
        self.assertEqual(step["distinct_messages"], 8)
        self.assertEqual(step["not_shown"],
                         8 - tools.COPY_PER_STEP_CAP)
        self.assertIn("personalised", step["note"])

    def test_the_note_warns_that_one_step_carries_several_texts(self):
        out = tools.campaign_copy(client("alpha"))
        self.assertIn("several texts", out["note"])


if __name__ == "__main__":
    unittest.main()
