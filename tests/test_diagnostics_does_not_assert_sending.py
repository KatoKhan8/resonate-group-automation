"""The sending panel reports what is true, rather than asserting a literal.

`/diagnostics` rendered five hardcoded strings under a heading of "Sending",
one of which the system can actually check and was getting wrong:

    row("Slack posting", tag("preview only", "pass"), raw=True)

`SLACK_LIVE` plus a token arms `slack.post()`. So with posting switched on,
the operator's own diagnostics screen said "preview only" in the pass colour
while `/admin` - a super-admin screen most operators never open - said it was
on. A sending-safety surface contradicting the thing beside it is the exact
defect `api.feature_flags` carries a comment about having already fixed once;
this is the same bug left standing on the lower-privilege screen.

Both now read one computation. `feature_flags` is the source and
`api.diagnostics` reports its answer rather than a second one - a second
computation that agrees today is how the two came apart in the first place.

The semantics stay flag-presence, which `test_health_is_not_silence` locks in
as a pair: SLACK_LIVE set means on, and the sentence beside it may not say
"unset". Requiring a token as well would make SLACK_LIVE=1 read as off, which
is the wrong direction for a sending-safety surface to be wrong in.

"Paid enrichment" also stopped claiming "not run", which is a statement about
history that the spend ledger contradicts. It says what is actually asserted:
no web job spends.
"""
import os
import unittest

from src.providers import slack
from src.web import api, pages
from tests.webbase import WebTest

OPERATOR = "ops@productive.test"


class TheSendingPanelIsDerived(WebTest):

    def setUp(self):
        self.session = self.signin(OPERATOR)
        self._prev = {k: os.environ.get(k)
                      for k in (slack.LIVE_VAR, slack.KEY_VAR)}

    def tearDown(self):
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def arm_slack(self):
        os.environ[slack.LIVE_VAR] = "1"

    def panel(self):
        status, body, _ = self.session.get("/diagnostics")
        self.assertEqual(status, 200)
        head = body.index("<h3>Sending</h3>")
        return body[head:body.index("</div>", head)]

    def slack_row(self):
        """Only Slack's cell. EmailBison and HeyReach say "preview only"
        truthfully - there is no send path - so a panel-wide search would
        pass on their answer instead of on the one under test."""
        panel = self.panel()
        at = panel.index("<th>Slack posting</th>")
        return panel[at:panel.index("</tr>", at)]

    # ----------------------------------------------------------- the defect

    def test_with_posting_armed_the_panel_does_not_say_preview_only(self):
        self.arm_slack()
        self.assertNotIn("preview only", self.slack_row())

    def test_with_posting_armed_the_panel_says_so(self):
        self.arm_slack()
        self.assertIn("LIVE", self.slack_row())

    def test_the_two_screens_agree(self):
        """The contradiction, asserted directly."""
        self.arm_slack()
        flag = next(f for f in api.feature_flags()
                    if f["flag"] == "slack_posting")
        self.assertTrue(flag["state"])
        self.assertIn("LIVE", self.slack_row())

    def test_they_agree_when_it_is_off_too(self):
        os.environ.pop(slack.LIVE_VAR, None)
        os.environ.pop(slack.KEY_VAR, None)
        flag = next(f for f in api.feature_flags()
                    if f["flag"] == "slack_posting")
        self.assertFalse(flag["state"])
        self.assertIn("preview only", self.slack_row())

    # -------------------------------------------------- what it reports

    def test_paid_enrichment_does_not_claim_never_to_have_run(self):
        self.assertNotIn("not run", self.panel())

    def test_live_sending_is_still_reported_as_disabled(self):
        """True by construction, and it must stay on the screen."""
        self.assertIn("DISABLED", self.panel())


if __name__ == "__main__":
    unittest.main()
