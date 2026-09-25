#!/usr/bin/env python3
"""A threaded step still carries a subject.  TASK-295.

``bisonfactory._sequence_steps`` states it in its own docstring:
"A follow-up step STILL CARRIES ``email_subject`` — the flag is the
mechanism, not subject omission."

So "step 2 has no subject" is NOT how a threaded step is detected.  A
check that treats an empty subject on step 2 as correct threading will
pass a step that sends with no subject line — which is the defect this
whole check exists for (ISSUE-025, 76 blank emails).

These tests prove:

1. ``_sequence_steps`` puts a non-empty ``email_subject`` on every step,
   including threaded ones.
2. The QA check does NOT treat an empty subject on a threaded step as
   correct — it fires ``subject_present``.
3. The ``thread_reply`` flag is the mechanism, not subject omission.
"""
import json
import os
import shutil
import tempfile
import unittest

from scripts.qa import check_lead_copy
from src import bisonfactory


# A body that is 40+ words long.
LONG_BODY = (
    "Hi Alice, I work with SaaS teams on project margin visibility and "
    "I do not know how Acme handles it. The pattern I see in teams the "
    "size of Acme is that the numbers arrive too late to act on. "
    "Utilisation and margin are known at the end of the month which is "
    "after the month when something could have been done about them."
)


class ThreadedStepCarriesSubject(unittest.TestCase):
    """``_sequence_steps`` puts ``email_subject`` on every step."""

    def _config(self, keys, thread_pattern):
        steps = {}
        for i, key in enumerate(keys, start=1):
            steps[key] = {"subject": "{SUBJECT_1}",
                          "body": "{BODY_%d}" % i,
                          "wait_in_days": 3, "order": i}
        return {"steps": steps, "thread_reply_pattern": thread_pattern}

    def _cadence(self, keys, days=None):
        if days is None:
            # Space days so gaps match wait_in_days=3.
            days = [1 + 3 * i for i in range(len(keys))]
        return [{"channel": "email", "key": k, "day": d}
                for k, d in zip(keys, days)]

    def test_four_step_every_step_carries_subject(self):
        config = self._config(
            ["em1", "em2", "em4", "em5"],
            [False, True, True, True])
        cadence = self._cadence(["em1", "em2", "em4", "em5"])
        seq = bisonfactory._sequence_steps(config, cadence)
        for step in seq:
            self.assertTrue(
                step["email_subject"],
                "step %d (%s) has no email_subject" % (
                    step["order"], step["step_key"]))

    def test_three_step_every_step_carries_subject(self):
        config = self._config(
            ["em1", "em2", "em3"],
            [False, True, True])
        cadence = self._cadence(["em1", "em2", "em3"])
        seq = bisonfactory._sequence_steps(config, cadence)
        for step in seq:
            self.assertTrue(step["email_subject"])

    def test_threaded_steps_are_flagged(self):
        config = self._config(
            ["em1", "em2", "em4", "em5"],
            [False, True, True, True])
        cadence = self._cadence(["em1", "em2", "em4", "em5"])
        seq = bisonfactory._sequence_steps(config, cadence)
        self.assertFalse(seq[0]["thread_reply"])
        for step in seq[1:]:
            self.assertTrue(step["thread_reply"])


class QACheckDoesNotExcuseEmptySubjectOnThreadedStep(unittest.TestCase):
    """The QA check fires ``subject_present`` on an empty subject_1.

    The s7 output carries only ``subject_1``.  All steps reference it.
    An empty ``subject_1`` means every step sends with no subject line.
    """

    def _make_workspace(self, rows):
        tmp = tempfile.mkdtemp()
        stage = os.path.join(tmp, "stage")
        os.makedirs(stage)
        with open(os.path.join(stage, "s7-copy.jsonl"), "w",
                  encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        return tmp

    def _campaign(self, keys):
        return [{"cadence_steps": [
            {"channel": "email", "key": k, "day": i}
            for i, k in enumerate(keys, 1)]}]

    def test_empty_subject_fires_subject_present(self):
        row = {
            "email": "alice@test.com",
            "state": "rendered",
            "variables": {
                "FIRST": "Alice",
                "subject_1": "",
                "body_1": LONG_BODY,
                "body_2": LONG_BODY.replace("Hi Alice,", "Alice,"),
                "persona": "champion",
                "angle": "margin visibility",
            },
        }
        ws = self._make_workspace([row])
        try:
            result = check_lead_copy.run(
                workspaces=ws, client="productive",
                campaign_rows=self._campaign(["em1", "em2"]))
            self.assertEqual(result["verdict"], "FAIL")
            self.assertIn("alice@test.com",
                          result["offenders"]["subject_present"])
        finally:
            shutil.rmtree(ws)

    def test_nonempty_subject_passes_subject_rule(self):
        row = {
            "email": "alice@test.com",
            "state": "rendered",
            "variables": {
                "FIRST": "Alice",
                "subject_1": "margin visibility",
                "body_1": LONG_BODY,
                "body_2": LONG_BODY.replace("Hi Alice,", "Alice,"),
                "persona": "champion",
                "angle": "margin visibility",
            },
        }
        ws = self._make_workspace([row])
        try:
            result = check_lead_copy.run(
                workspaces=ws, client="productive",
                campaign_rows=self._campaign(["em1", "em2"]))
            self.assertNotIn("alice@test.com",
                             result["offenders"]["subject_present"])
        finally:
            shutil.rmtree(ws)


if __name__ == "__main__":
    unittest.main()
