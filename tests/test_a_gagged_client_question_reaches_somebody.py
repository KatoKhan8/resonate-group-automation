"""The gag stopped the agent answering, and stopped us hearing the question.

`CLIENT_CHANNEL_GAG` is correct and stays: it was set because the agent told
a client there were three positive replies when our own classifier says
zero, answered "awaiting your approval" for a decision that was the
operator's, and took seven minutes to do it.

What was NOT correct is what the gagged path did next. It wrote one row to
`work/slack-agent.jsonl`, emitted one line to stdout, and returned. No Slack
post, no ticket, no internal notification. A client asking us something
produced nothing any person would ever see.

The replay audit measured the size of that: 11 of 32 real questions - 34% of
traffic - were client questions, and every one got silence. The gag was
meant to stop the agent saying something wrong to a client. It was also
stopping the operator finding out the client had asked.

The alert is INTERNAL. Nothing it does reaches the client channel, so it is
safe while the gag stands and still useful after it lifts.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import notify                                         # noqa: E402
from src import slackconversation                              # noqa: E402


class TheEventExistsAndIsRoutedForAPerson(unittest.TestCase):

    def test_it_is_action_required_not_critical(self):
        """A person must answer it. It is not an outage."""
        self.assertEqual(notify.ROUTES[notify.CLIENT_QUESTION_UNANSWERED],
                         (notify.GLOBAL, notify.ACTION_REQUIRED))

    def test_it_goes_to_the_internal_operations_channel(self):
        destination, _severity = notify.ROUTES[
            notify.CLIENT_QUESTION_UNANSWERED]
        self.assertEqual(destination, notify.GLOBAL)


class TheGaggedPathRaisesIt(unittest.TestCase):
    """Asserted on the SOURCE, because importing the loop pulls in providers
    and opens a Slack socket. The defect was never in the alert - there was
    no alert - so what has to be pinned is that the gag branch contains one.
    """

    def _source(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scripts", "slack_agent_loop.py")
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    def test_the_gag_branch_notifies_before_it_returns(self):
        import ast
        tree = ast.parse(self._source())
        gag_tests = [n for n in ast.walk(tree)
                     if isinstance(n, ast.If)
                     and "gagged" in ast.dump(n.test)]
        self.assertTrue(gag_tests, "the gag branch should still exist")
        raised = any("CLIENT_QUESTION_UNANSWERED" in ast.dump(branch)
                     for branch in gag_tests)
        self.assertTrue(
            raised,
            "a gagged client question must raise an internal alert; without "
            "one the operator never learns the client asked")

    def test_the_gag_branch_still_posts_nothing_to_the_client(self):
        """The alert must not become a way to answer the client by accident."""
        import ast
        tree = ast.parse(self._source())
        gag = [n for n in ast.walk(tree)
               if isinstance(n, ast.If) and "gagged" in ast.dump(n.test)][0]
        dumped = ast.dump(gag)
        for forbidden in ("post_message", "chat_postMessage", "say("):
            self.assertNotIn(forbidden, dumped)

    def test_the_gag_itself_is_still_set(self):
        """This suite must go red the day the gag is lifted, so it is reread."""
        self.assertTrue(
            slackconversation.CLIENT_CHANNEL_GAG,
            "the gag is lifted - re-read this file and the three faults "
            "named in CLIENT_CHANNEL_GAG before deleting anything")


if __name__ == "__main__":
    unittest.main()
