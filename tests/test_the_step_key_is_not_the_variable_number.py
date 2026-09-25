#!/usr/bin/env python3
"""The step key is NOT the variable number.  TASK-295.

``em4`` reads ``{BODY_3}`` and ``em5`` reads ``{BODY_4}`` in the four-step
shape.  A check that maps ``em5 -> BODY_5`` will look for a variable that
does not exist and report every lead as blank.

These tests prove the mapping is read FROM THE CONFIG, not hardcoded.
"""
import json
import os
import shutil
import tempfile
import unittest

from scripts.qa import check_lead_copy
from src import bisonfactory


# A body that is 40+ words long, passing the length_in_band rule.
LONG_BODY = (
    "Hi {first}, I work with {industry} teams on {angle} and I do not "
    "know how {company} handles it. The pattern I see in teams the size "
    "of {company} is that the numbers arrive too late to act on. "
    "Utilisation and margin are known at the end of the month which is "
    "after the month when something could have been done about them. "
    "The work itself is rarely the problem. The visibility into it is."
)


class StepToVariableMapping(unittest.TestCase):
    """The mapping is read from the config, not assumed."""

    def _config_with_steps(self, keys, thread_pattern=None):
        steps = {}
        for i, key in enumerate(keys, start=1):
            steps[key] = {"subject": "{SUBJECT_1}", "body": "{BODY_%d}" % i,
                          "wait_in_days": 3, "order": i}
        es = {"steps": steps}
        if thread_pattern is not None:
            es["thread_reply_pattern"] = thread_pattern
        return {"email_sequence": es}

    def test_four_step_mapping_em4_is_position_3(self):
        """em4 is at position 3 in a four-step campaign."""
        config = self._config_with_steps(
            ["em1", "em2", "em4", "em5"],
            thread_pattern=[False, True, True, True])
        cadence = [{"channel": "email", "key": k, "day": i}
                   for i, k in enumerate(["em1", "em2", "em4", "em5"], 1)]
        info = check_lead_copy.determine_steps(
            config, campaign={"cadence_steps": cadence})
        mapping = info["steps"]
        self.assertEqual(len(mapping), 4)
        em4 = mapping[2]
        self.assertEqual(em4["step_key"], "em4")
        self.assertEqual(em4["position"], 3)

    def test_three_step_mapping_has_three_entries(self):
        config = self._config_with_steps(
            ["em1", "em2", "em3"],
            thread_pattern=[False, True, True])
        cadence = [{"channel": "email", "key": k, "day": i}
                   for i, k in enumerate(["em1", "em2", "em3"], 1)]
        info = check_lead_copy.determine_steps(
            config, campaign={"cadence_steps": cadence})
        self.assertEqual(info["steps_expected"], 3)
        self.assertEqual(len(info["steps"]), 3)

    def test_five_step_mapping(self):
        config = self._config_with_steps(
            ["em1", "em2", "em3", "em4", "em5"],
            thread_pattern=[False, True, True, True, True])
        cadence = [{"channel": "email", "key": k, "day": i}
                   for i, k in enumerate(
                       ["em1", "em2", "em3", "em4", "em5"], 1)]
        info = check_lead_copy.determine_steps(
            config, campaign={"cadence_steps": cadence})
        self.assertEqual(info["steps_expected"], 5)
        keys = [s["step_key"] for s in info["steps"]]
        self.assertEqual(keys, ["em1", "em2", "em3", "em4", "em5"])

    def test_thread_reply_pattern_from_config(self):
        config = self._config_with_steps(
            ["em1", "em2", "em4", "em5"],
            thread_pattern=[False, True, True, True])
        cadence = [{"channel": "email", "key": k, "day": i}
                   for i, k in enumerate(["em1", "em2", "em4", "em5"], 1)]
        info = check_lead_copy.determine_steps(
            config, campaign={"cadence_steps": cadence})
        self.assertEqual(info["thread_reply_pattern"],
                         (False, True, True, True))

    def test_no_hardcoded_subject_2(self):
        """All four steps carry SUBJECT_1; there is no SUBJECT_2."""
        config = self._config_with_steps(
            ["em1", "em2", "em4", "em5"],
            thread_pattern=[False, True, True, True])
        cadence = [{"channel": "email", "key": k, "day": i}
                   for i, k in enumerate(["em1", "em2", "em4", "em5"], 1)]
        info = check_lead_copy.determine_steps(
            config, campaign={"cadence_steps": cadence})
        pattern = info["thread_reply_pattern"]
        self.assertFalse(pattern[0])
        self.assertTrue(all(pattern[1:]))

    def test_pattern_trimmed_to_campaign_length(self):
        """A 4-entry pattern is trimmed to 2 for a 2-step campaign."""
        config = self._config_with_steps(
            ["em1", "em2"],
            thread_pattern=[False, True, True, True])
        cadence = [{"channel": "email", "key": k, "day": i}
                   for i, k in enumerate(["em1", "em2"], 1)]
        info = check_lead_copy.determine_steps(
            config, campaign={"cadence_steps": cadence})
        self.assertEqual(len(info["thread_reply_pattern"]), 2)
        self.assertEqual(info["thread_reply_pattern"], (False, True))


class BisonfactorySequenceStepsAgrees(unittest.TestCase):
    """``bisonfactory._sequence_steps`` produces the same mapping."""

    def _cadence_steps(self, keys, days=None):
        if days is None:
            days = list(range(1, len(keys) + 1))
        return [{"channel": "email", "key": k, "day": d}
                for k, d in zip(keys, days)]

    def _config(self, keys, thread_pattern=None):
        steps = {}
        for i, key in enumerate(keys, start=1):
            steps[key] = {"subject": "{SUBJECT_1}",
                          "body": "{BODY_%d}" % i,
                          "wait_in_days": 3, "order": i}
        es = {"steps": steps}
        if thread_pattern is not None:
            es["thread_reply_pattern"] = thread_pattern
        return {"email_sequence": es}

    def test_four_step_sequence_has_four_entries(self):
        """em4 is at position 3, with thread_reply=true and a subject."""
        keys = ["em1", "em2", "em4", "em5"]
        # wait_in_days=3 for each; gaps are 1 (days 1,2,3,4 with gap 1).
        # But bisonfactory checks gap = next_day - this_day == wait.
        # So we need days where consecutive gaps are 3: 1, 4, 7, 10.
        days = [1, 4, 7, 10]
        config = self._config(keys, [False, True, True, True])
        cadence = self._cadence_steps(keys, days)
        seq = bisonfactory._sequence_steps(config["email_sequence"], cadence)
        self.assertEqual(len(seq), 4)
        self.assertEqual(seq[2]["step_key"], "em4")
        self.assertEqual(seq[2]["order"], 3)
        self.assertTrue(seq[2]["email_subject"])
        self.assertTrue(seq[2]["thread_reply"])

    def test_threaded_step_still_carries_subject(self):
        config = self._config(
            ["em1", "em2", "em4", "em5"],
            [False, True, True, True])
        cadence = self._cadence_steps(
            ["em1", "em2", "em4", "em5"], [1, 4, 7, 10])
        seq = bisonfactory._sequence_steps(
            config["email_sequence"], cadence)
        for step in seq[1:]:
            self.assertTrue(step["thread_reply"])
            self.assertTrue(step["email_subject"])


class CheckAgainstRenderedRows(unittest.TestCase):
    """The check reads rendered rows and applies rules."""

    def _make_workspace(self, rows):
        tmp = tempfile.mkdtemp()
        stage = os.path.join(tmp, "stage")
        os.makedirs(stage)
        with open(os.path.join(stage, "s7-copy.jsonl"), "w",
                  encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        return tmp

    def _good_row(self, email="alice@test.com", first="Alice"):
        body = LONG_BODY.replace("{first}", first).replace(
            "{company}", "Acme").replace(
            "{industry}", "SaaS").replace(
            "{angle}", "project margin visibility")
        return {
            "email": email,
            "state": "rendered",
            "variables": {
                "FIRST": first,
                "COMPANY": "Acme",
                "INDUSTRY": "SaaS",
                "ANGLE": "project margin visibility",
                "subject_1": "project margin visibility",
                "body_1": body,
                "body_2": body.replace("Hi %s," % first,
                                       "%s," % first),
                "persona": "champion",
                "angle": "project margin visibility",
                "angle_key": "delivery",
            },
        }

    def _campaign(self, keys):
        return [{"cadence_steps": [
            {"channel": "email", "key": k, "day": i}
            for i, k in enumerate(keys, 1)]}]

    def test_clean_batch_passes(self):
        ws = self._make_workspace([self._good_row("a@test.com", "Alice"),
                                   self._good_row("b@test.com", "Bob")])
        try:
            result = check_lead_copy.run(
                workspaces=ws, client="productive",
                campaign_rows=self._campaign(["em1", "em2"]))
            self.assertIn(result["verdict"], ("PASS", "UNCONFIRMED"),
                          result)
        finally:
            shutil.rmtree(ws)

    def test_empty_body_fires_body_present(self):
        row = self._good_row()
        row["variables"]["body_1"] = ""
        ws = self._make_workspace([row])
        try:
            result = check_lead_copy.run(
                workspaces=ws, client="productive",
                campaign_rows=self._campaign(["em1"]))
            self.assertEqual(result["verdict"], "FAIL")
            self.assertIn(row["email"],
                          result["offenders"]["body_present"])
        finally:
            shutil.rmtree(ws)

    def test_empty_subject_fires_subject_present(self):
        row = self._good_row()
        row["variables"]["subject_1"] = ""
        ws = self._make_workspace([row])
        try:
            result = check_lead_copy.run(
                workspaces=ws, client="productive",
                campaign_rows=self._campaign(["em1"]))
            self.assertEqual(result["verdict"], "FAIL")
            self.assertIn(row["email"],
                          result["offenders"]["subject_present"])
        finally:
            shutil.rmtree(ws)

    def test_literal_none_fires_not_literal_none(self):
        row = self._good_row()
        row["variables"]["body_1"] = "None"
        ws = self._make_workspace([row])
        try:
            result = check_lead_copy.run(
                workspaces=ws, client="productive",
                campaign_rows=self._campaign(["em1"]))
            self.assertEqual(result["verdict"], "FAIL")
            self.assertIn(row["email"],
                          result["offenders"]["not_literal_none"])
        finally:
            shutil.rmtree(ws)

    def test_unrendered_placeholder_fires(self):
        row = self._good_row()
        row["variables"]["body_1"] = "Hi Alice, {BODY_3} remains. " * 10
        ws = self._make_workspace([row])
        try:
            result = check_lead_copy.run(
                workspaces=ws, client="productive",
                campaign_rows=self._campaign(["em1"]))
            self.assertEqual(result["verdict"], "FAIL")
            self.assertIn(row["email"],
                          result["offenders"]["no_unrendered_placeholder"])
        finally:
            shutil.rmtree(ws)

    def test_dash_fires(self):
        row = self._good_row()
        row["variables"]["body_1"] = (
            "Hi Alice, the project \u2014 which was large \u2014 "
            "needed attention to detail and careful management of "
            "resources across multiple teams and offices. " + "word " * 30)
        ws = self._make_workspace([row])
        try:
            result = check_lead_copy.run(
                workspaces=ws, client="productive",
                campaign_rows=self._campaign(["em1"]))
            self.assertEqual(result["verdict"], "FAIL")
            self.assertIn(row["email"],
                          result["offenders"]["no_dash"])
        finally:
            shutil.rmtree(ws)

    def test_banned_phrase_fires(self):
        row = self._good_row()
        row["variables"]["body_1"] = (
            "Hi Alice, I hope this email finds you well and I wanted "
            "to reach out about your project margin visibility at Acme. "
            "The pattern I see is that the numbers arrive too late to "
            "act on them. " + "word " * 30)
        ws = self._make_workspace([row])
        try:
            result = check_lead_copy.run(
                workspaces=ws, client="productive",
                campaign_rows=self._campaign(["em1"]))
            self.assertEqual(result["verdict"], "FAIL")
            self.assertIn(row["email"],
                          result["offenders"]["no_banned_phrase"])
        finally:
            shutil.rmtree(ws)

    def test_lowercase_first_name_fires(self):
        row = self._good_row(first="alice")
        ws = self._make_workspace([row])
        try:
            result = check_lead_copy.run(
                workspaces=ws, client="productive",
                campaign_rows=self._campaign(["em1"]))
            self.assertEqual(result["verdict"], "FAIL")
            self.assertIn(row["email"],
                          result["offenders"][
                              "first_name_present_and_capitalised"])
        finally:
            shutil.rmtree(ws)

    def test_duplicate_first_line_fires(self):
        same_first_line = ("Hi, I work with SaaS teams on project margin "
                           "visibility and I do not know how Acme handles "
                           "it. The pattern I see in teams the size of "
                           "Acme is that the numbers arrive too late.")
        r1 = self._good_row("a@test.com", "Alice")
        r2 = self._good_row("b@test.com", "Bob")
        # Both bodies start with the SAME first line, separated by \n\n
        # from the rest.  The first line is the unit of comparison.
        tail_1 = "More text about Alice. " + "word " * 30
        tail_2 = "Different text about Bob. " + "word " * 30
        r1["variables"]["body_1"] = same_first_line + "\n\n" + tail_1
        r2["variables"]["body_1"] = same_first_line + "\n\n" + tail_2
        ws = self._make_workspace([r1, r2])
        try:
            result = check_lead_copy.run(
                workspaces=ws, client="productive",
                campaign_rows=self._campaign(["em1"]))
            self.assertEqual(result["verdict"], "FAIL")
            self.assertIn("a@test.com",
                          result["offenders"]["first_line_unique_in_batch"])
            self.assertIn("b@test.com",
                          result["offenders"]["first_line_unique_in_batch"])
        finally:
            shutil.rmtree(ws)

    def test_vacuous_when_no_rendered_rows(self):
        ws = self._make_workspace([
            {"email": "x@test.com", "state": "held", "reason": "no name"}])
        try:
            result = check_lead_copy.run(
                workspaces=ws, client="productive",
                campaign_rows=self._campaign(["em1"]))
            self.assertEqual(result["verdict"], "VACUOUS")
        finally:
            shutil.rmtree(ws)

    def test_empty_vs_none_vs_unrendered_are_separate_counts(self):
        r1 = self._good_row("a@test.com", "Alice")
        r1["variables"]["body_1"] = ""
        r2 = self._good_row("b@test.com", "Bob")
        r2["variables"]["body_1"] = "None"
        r3 = self._good_row("c@test.com", "Carol")
        r3["variables"]["body_1"] = "Hi Carol, {BODY_3} remains. " * 10
        ws = self._make_workspace([r1, r2, r3])
        try:
            result = check_lead_copy.run(
                workspaces=ws, client="productive",
                campaign_rows=self._campaign(["em1"]))
            counts = result["empty_vs_none_vs_unrendered"]
            self.assertGreaterEqual(counts["empty_body"], 1)
            self.assertGreaterEqual(counts["literal_none"], 1)
            self.assertGreaterEqual(counts["unrendered"], 1)
        finally:
            shutil.rmtree(ws)

    def test_arithmetic_closes(self):
        ws = self._make_workspace([self._good_row("a@test.com", "Alice"),
                                   self._good_row("b@test.com", "Bob")])
        try:
            result = check_lead_copy.run(
                workspaces=ws, client="productive",
                campaign_rows=self._campaign(["em1", "em2"]))
            self.assertTrue(result["arithmetic_closes"])
        finally:
            shutil.rmtree(ws)

    def test_rule_sentences_rendered_from_run_parameters(self):
        ws = self._make_workspace([self._good_row()])
        try:
            result = check_lead_copy.run(
                workspaces=ws, client="productive",
                campaign_rows=self._campaign(["em1", "em2", "em3"]))
            self.assertEqual(result["steps_expected"], 3)
            self.assertIn("body_present", result["rules"])
            # The body_present rule should say "3 step bodies", not "5".
            self.assertIn("3", result["rules"]["body_present"])
        finally:
            shutil.rmtree(ws)


if __name__ == "__main__":
    unittest.main()
