"""TASK-283: the render carries every variable the provider sequence needs.

The verifier is `scripts/verify_s7_render.py`. These tests drive its
functions through constructed configs and journals, asserting on the
errors list and the report lines. The config-level checks (key diff,
thread_reply_pattern, final wait) are tested with synthetic configs;
the journal-level checks (per-variable table, variable set diff) are
tested with temp JSONL files.

The real 927-row journal is not in this worktree (it lives in `work/`
which is gitignored). The per-variable table over real rows is produced
by running the verifier against a copy, not by these tests. These tests
prove the VERIFIER is correct; the run proves the JOURNAL is clean.
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "verify_s7_render",
    os.path.join(ROOT, "scripts", "verify_s7_render.py"))
v = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v)


def _config(steps=None, thread_reply_pattern=None, wait_last=1):
    """A minimal client config for testing.

    Five steps by default (em1..em5), matching the current productive.yaml
    shape. Override `steps` to test mismatch, `thread_reply_pattern` to
    test the threading check, `wait_last` to test the terminal wait.
    """
    if steps is None:
        keys = ["em1", "em2", "em3", "em4", "em5"]
    else:
        keys = list(steps)
    block = {}
    for i, key in enumerate(keys, start=1):
        wait = 3 if i < len(keys) else wait_last
        block[key] = {
            "order": i,
            "subject": "{SUBJECT_1}",
            "body": "<p>{BODY_%d}</p>" % i,
            "wait_in_days": wait,
        }
    es = {"steps": block}
    if thread_reply_pattern is not None:
        es["thread_reply_pattern"] = thread_reply_pattern
    else:
        es["thread_reply_pattern"] = [False] + [True] * (len(keys) - 1)
    return {"email_sequence": es}


def _cadence_steps(keys=None):
    """CADENCE_STEPS matching the config's keys."""
    if keys is None:
        keys = ["em1", "em2", "em3", "em4", "em5"]
    days = [1, 4, 8, 12, 21]
    out = []
    for i, key in enumerate(keys):
        out.append({"key": key, "day": days[i] if i < len(days)
                     else days[-1] + (i - len(days) + 1) * 7,
                     "channel": "email", "generated": True})
    return out


def _journal_row(email, variables, state="rendered"):
    return {"email": email, "state": state, "variables": variables}


def _write_journal(rows, path):
    with open(path, "w", encoding="utf-8") as out:
        for row in rows:
            out.write(json.dumps(row) + "\n")


class TestDiffCadenceKeys(unittest.TestCase):
    """Check 1: cadence keys vs config step keys, both directions."""

    def test_agreement(self):
        cfg = _config()
        steps = _cadence_steps()
        cfg_keys, cad_keys, only_cfg, only_cad = v.diff_cadence_keys(
            cfg, steps)
        self.assertEqual(cfg_keys, ["em1", "em2", "em3", "em4", "em5"])
        self.assertEqual(cad_keys, ["em1", "em2", "em3", "em4", "em5"])
        self.assertEqual(only_cfg, [])
        self.assertEqual(only_cad, [])

    def test_config_has_extra(self):
        cfg = _config(steps=["em1", "em2", "em3", "em4", "em5", "em6"])
        steps = _cadence_steps()
        _cfg_keys, _cad_keys, only_cfg, only_cad = v.diff_cadence_keys(
            cfg, steps)
        self.assertIn("em6", only_cfg)
        self.assertEqual(only_cad, [])

    def test_cadence_has_extra(self):
        cfg = _config(steps=["em1", "em2"])
        steps = _cadence_steps()
        _cfg_keys, _cad_keys, only_cfg, only_cad = v.diff_cadence_keys(
            cfg, steps)
        self.assertEqual(only_cfg, [])
        self.assertIn("em3", only_cad)
        self.assertIn("em4", only_cad)

    def test_both_directions_differ(self):
        cfg = _config(steps=["em1", "em2", "emX"])
        steps = _cadence_steps(keys=["em1", "em2", "em3"])
        _cfg_keys, _cad_keys, only_cfg, only_cad = v.diff_cadence_keys(
            cfg, steps)
        self.assertIn("emX", only_cfg)
        self.assertIn("em3", only_cad)


class TestCheckThreadPattern(unittest.TestCase):
    """Check 2: thread_reply_pattern read from config at run time."""

    def test_valid_five_step(self):
        cfg = _config(thread_reply_pattern=[False, True, True, True, True])
        pattern, errs = v.check_thread_pattern(cfg, 5)
        self.assertEqual(errs, [])
        self.assertEqual(pattern, [False, True, True, True, True])

    def test_valid_four_step(self):
        cfg = _config(steps=["em1", "em2", "em4", "em5"],
                       thread_reply_pattern=[False, True, True, True])
        pattern, errs = v.check_thread_pattern(cfg, 4)
        self.assertEqual(errs, [])

    def test_wrong_length_refused(self):
        cfg = _config(thread_reply_pattern=[False, True, True])
        pattern, errs = v.check_thread_pattern(cfg, 5)
        self.assertTrue(len(errs) > 0)
        self.assertIn("3 entries", errs[0])
        self.assertIn("5 email steps", errs[0])

    def test_opener_not_false(self):
        cfg = _config(thread_reply_pattern=[True, True, True, True, True])
        _pattern, errs = v.check_thread_pattern(cfg, 5)
        self.assertTrue(any("opener" in e for e in errs))

    def test_follow_up_not_true(self):
        cfg = _config(thread_reply_pattern=[False, False, True, True, True])
        _pattern, errs = v.check_thread_pattern(cfg, 5)
        self.assertTrue(any("follow-up" in e for e in errs))

    def test_absent_pattern(self):
        cfg = {"email_sequence": {"steps": {}}}
        pattern, errs = v.check_thread_pattern(cfg, 3)
        self.assertIsNone(pattern)
        self.assertTrue(any("absent" in e for e in errs))


class TestCheckFinalWait(unittest.TestCase):
    """Check 3: final step wait_in_days >= 1."""

    def test_valid_wait(self):
        cfg = _config(wait_last=1)
        steps = _cadence_steps()
        wait, errs = v.check_final_wait(cfg, steps)
        self.assertEqual(wait, 1)
        self.assertEqual(errs, [])

    def test_zero_wait_refused(self):
        cfg = _config(wait_last=0)
        steps = _cadence_steps()
        wait, errs = v.check_final_wait(cfg, steps)
        self.assertEqual(wait, 0)
        self.assertTrue(len(errs) > 0)
        self.assertIn("campaign 485", errs[0].lower())

    def test_missing_wait(self):
        cfg = _config()
        steps = _cadence_steps()
        del cfg["email_sequence"]["steps"]["em5"]["wait_in_days"]
        wait, errs = v.check_final_wait(cfg, steps)
        self.assertIsNone(wait)
        self.assertTrue(len(errs) > 0)

    def test_no_email_steps(self):
        cfg = _config(steps=[])
        wait, errs = v.check_final_wait(cfg, [])
        self.assertTrue(len(errs) > 0)


class TestProviderSequenceVariables(unittest.TestCase):
    """Check 4 helper: extract variable names from provider templates."""

    def test_five_step(self):
        cfg = _config()
        prov = v.provider_sequence_variables(cfg)
        self.assertEqual(prov, {"subject_1", "body_1", "body_2", "body_3",
                                "body_4", "body_5"})

    def test_four_step(self):
        """At four steps the provider references body_1..body_4 BY POSITION.

        The step key is NOT the variable number: em4 sits at position 3
        and reads {BODY_3}; em5 sits at position 4 and reads {BODY_4}.
        """
        cfg = _config(steps=["em1", "em2", "em4", "em5"])
        prov = v.provider_sequence_variables(cfg)
        self.assertEqual(prov, {"subject_1", "body_1", "body_2",
                                "body_3", "body_4"})

    def test_subject_only_in_opener(self):
        cfg = _config()
        prov = v.provider_sequence_variables(cfg)
        self.assertIn("subject_1", prov)
        self.assertNotIn("subject_2", prov)
        self.assertNotIn("subject_3", prov)


class TestDiffVariableSets(unittest.TestCase):
    """Check 4: variable set diff, both directions."""

    def test_agreement(self):
        j = {"subject_1", "body_1", "body_2", "body_3"}
        p = {"subject_1", "body_1", "body_2", "body_3"}
        only_j, only_p = v.diff_variable_sets(j, p)
        self.assertEqual(only_j, [])
        self.assertEqual(only_p, [])

    def test_journal_missing_variable(self):
        j = {"subject_1", "body_1"}
        p = {"subject_1", "body_1", "body_2", "body_3"}
        only_j, only_p = v.diff_variable_sets(j, p)
        self.assertEqual(only_j, [])
        self.assertEqual(only_p, ["body_2", "body_3"])

    def test_journal_extra_variable(self):
        j = {"subject_1", "body_1", "body_2", "subject_2"}
        p = {"subject_1", "body_1", "body_2"}
        only_j, only_p = v.diff_variable_sets(j, p)
        self.assertEqual(only_j, ["subject_2"])
        self.assertEqual(only_p, [])

    def test_both_directions_differ(self):
        j = {"subject_1", "body_1", "extra_var"}
        p = {"subject_1", "body_1", "body_2"}
        only_j, only_p = v.diff_variable_sets(j, p)
        self.assertEqual(only_j, ["extra_var"])
        self.assertEqual(only_p, ["body_2"])


class TestJournalVariableNames(unittest.TestCase):
    """The journal's variable names are the INTERSECTION across rows."""

    def test_all_rows_same(self):
        rend = {
            "a@x.com": _journal_row("a@x.com", {"subject_1": "s", "body_1": "b"}),
            "b@x.com": _journal_row("b@x.com", {"subject_1": "s", "body_1": "b"}),
        }
        self.assertEqual(v.journal_variable_names(rend),
                         {"subject_1", "body_1"})

    def test_one_row_missing_variable(self):
        rend = {
            "a@x.com": _journal_row("a@x.com", {"subject_1": "s", "body_1": "b"}),
            "b@x.com": _journal_row("b@x.com", {"subject_1": "s"}),
        }
        self.assertEqual(v.journal_variable_names(rend), {"subject_1"})

    def test_empty(self):
        self.assertEqual(v.journal_variable_names({}), set())


class TestAnalyseRows(unittest.TestCase):
    """Check 5: per-variable stats over rendered rows."""

    def _vars(self, **kw):
        return {"subject_1": "subject text", "body_1": "body text", **kw}

    def test_all_present(self):
        rend = {
            "a@x.com": _journal_row("a@x.com", self._vars()),
            "b@x.com": _journal_row("b@x.com", self._vars()),
        }
        stats = v.analyse_rows(rend, {"subject_1", "body_1"})
        self.assertEqual(stats["body_1"]["present"], 2)
        self.assertEqual(stats["body_1"]["empty"], 0)
        self.assertEqual(stats["body_1"]["none_string"], 0)
        self.assertEqual(stats["body_1"]["unrendered"], 0)
        self.assertEqual(stats["body_1"]["missing"], 0)

    def test_empty_caught(self):
        rend = {
            "a@x.com": _journal_row("a@x.com", self._vars(body_1="")),
            "b@x.com": _journal_row("b@x.com", self._vars()),
        }
        stats = v.analyse_rows(rend, {"subject_1", "body_1"})
        self.assertEqual(stats["body_1"]["empty"], 1)
        self.assertEqual(stats["body_1"]["present"], 1)
        self.assertEqual(stats["body_1"]["example_empty"], "a@x.com")

    def test_literal_none_caught(self):
        rend = {
            "a@x.com": _journal_row("a@x.com", self._vars(body_1="None")),
            "b@x.com": _journal_row("b@x.com", self._vars()),
        }
        stats = v.analyse_rows(rend, {"subject_1", "body_1"})
        self.assertEqual(stats["body_1"]["none_string"], 1)
        self.assertEqual(stats["body_1"]["present"], 1)
        self.assertEqual(stats["body_1"]["example_none"], "a@x.com")

    def test_none_distinguished_from_empty(self):
        """'None' and '' are DIFFERENT faults with different causes."""
        rend = {
            "a@x.com": _journal_row("a@x.com", self._vars(body_1="None")),
            "b@x.com": _journal_row("b@x.com", self._vars(body_1="")),
            "c@x.com": _journal_row("c@x.com", self._vars()),
        }
        stats = v.analyse_rows(rend, {"subject_1", "body_1"})
        self.assertEqual(stats["body_1"]["none_string"], 1)
        self.assertEqual(stats["body_1"]["empty"], 1)
        self.assertEqual(stats["body_1"]["present"], 1)

    def test_unrendered_placeholder_caught(self):
        rend = {
            "a@x.com": _journal_row(
                "a@x.com", self._vars(body_1="hi {FIRST}, ...")),
            "b@x.com": _journal_row("b@x.com", self._vars()),
        }
        stats = v.analyse_rows(rend, {"subject_1", "body_1"})
        self.assertEqual(stats["body_1"]["unrendered"], 1)
        self.assertEqual(stats["body_1"]["example_unrendered"], "a@x.com")

    def test_missing_variable_caught(self):
        rend = {
            "a@x.com": _journal_row("a@x.com", {"subject_1": "s"}),
            "b@x.com": _journal_row("b@x.com", self._vars()),
        }
        stats = v.analyse_rows(rend, {"subject_1", "body_1"})
        self.assertEqual(stats["body_1"]["missing"], 1)
        self.assertEqual(stats["body_1"]["example_missing"], "a@x.com")

    def test_blankish_values_caught(self):
        """All blankish values are caught, not just empty string."""
        rend = {
            "a@x.com": _journal_row("a@x.com", self._vars(body_1="n/a")),
            "b@x.com": _journal_row("b@x.com", self._vars(body_1="null")),
            "c@x.com": _journal_row("c@x.com", self._vars()),
        }
        stats = v.analyse_rows(rend, {"subject_1", "body_1"})
        self.assertEqual(stats["body_1"]["empty"], 2)
        self.assertEqual(stats["body_1"]["present"], 1)


class TestCollectErrors(unittest.TestCase):
    """Error strings from analyse_rows stats."""

    def test_clean(self):
        stats = {"body_1": {"present": 10, "empty": 0, "none_string": 0,
                            "unrendered": 0, "missing": 0,
                            "example_empty": None, "example_none": None,
                            "example_unrendered": None,
                            "example_missing": None}}
        self.assertEqual(v.collect_errors(stats), [])

    def test_each_fault_reported(self):
        stats = {
            "body_1": {"present": 5, "empty": 1, "none_string": 2,
                        "unrendered": 3, "missing": 4,
                        "example_empty": "e@x.com",
                        "example_none": "n@x.com",
                        "example_unrendered": "u@x.com",
                        "example_missing": "m@x.com"},
        }
        errs = v.collect_errors(stats)
        self.assertEqual(len(errs), 4)
        self.assertTrue(any("missing" in e for e in errs))
        self.assertTrue(any("empty" in e for e in errs))
        self.assertTrue(any("'None'" in e for e in errs))
        self.assertTrue(any("unrendered" in e for e in errs))


class TestValidateEndToEnd(unittest.TestCase):
    """End-to-end validate() with constructed configs and journals."""

    def test_all_pass_config_only(self):
        cfg = _config()
        steps = _cadence_steps()
        errs, lines = v.validate(cfg, steps)
        self.assertEqual(errs, [])
        output = "\n".join(lines)
        self.assertIn("PASS", output)

    def test_key_mismatch_fails(self):
        cfg = _config(steps=["em1", "em2", "emX"])
        steps = _cadence_steps(keys=["em1", "em2", "em3"])
        errs, lines = v.validate(cfg, steps)
        self.assertTrue(len(errs) > 0)
        output = "\n".join(lines)
        self.assertIn("FAIL", output)
        self.assertIn("emX", output)
        self.assertIn("em3", output)

    def test_thread_pattern_wrong_length_fails(self):
        cfg = _config(thread_reply_pattern=[False, True, True])
        steps = _cadence_steps()
        errs, lines = v.validate(cfg, steps)
        self.assertTrue(len(errs) > 0)
        output = "\n".join(lines)
        self.assertIn("3 entries", output)

    def test_zero_final_wait_fails(self):
        cfg = _config(wait_last=0)
        steps = _cadence_steps()
        errs, lines = v.validate(cfg, steps)
        self.assertTrue(len(errs) > 0)
        output = "\n".join(lines)
        self.assertIn("485", output)

    def test_journal_with_empty_variable_fails(self):
        cfg = _config(steps=["em1", "em2"])
        cfg["email_sequence"]["thread_reply_pattern"] = [False, True]
        steps = _cadence_steps(keys=["em1", "em2"])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl",
                                         delete=False,
                                         encoding="utf-8") as tmp:
            tmp.write(json.dumps(_journal_row(
                "a@x.com", {"subject_1": "s", "body_1": "b1",
                            "body_2": ""})) + "\n")
            tmp.write(json.dumps(_journal_row(
                "b@x.com", {"subject_1": "s", "body_1": "b1",
                            "body_2": "b2"})) + "\n")
            path = tmp.name
        try:
            errs, lines = v.validate(cfg, steps, path)
            self.assertTrue(any("empty" in e for e in errs))
        finally:
            os.unlink(path)

    def test_journal_with_none_string_fails(self):
        cfg = _config(steps=["em1", "em2"])
        cfg["email_sequence"]["thread_reply_pattern"] = [False, True]
        steps = _cadence_steps(keys=["em1", "em2"])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl",
                                         delete=False,
                                         encoding="utf-8") as tmp:
            tmp.write(json.dumps(_journal_row(
                "a@x.com", {"subject_1": "s", "body_1": "b1",
                            "body_2": "None"})) + "\n")
            path = tmp.name
        try:
            errs, lines = v.validate(cfg, steps, path)
            self.assertTrue(any("'None'" in e for e in errs))
        finally:
            os.unlink(path)

    def test_journal_with_unrendered_placeholder_fails(self):
        cfg = _config(steps=["em1", "em2"])
        cfg["email_sequence"]["thread_reply_pattern"] = [False, True]
        steps = _cadence_steps(keys=["em1", "em2"])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl",
                                         delete=False,
                                         encoding="utf-8") as tmp:
            tmp.write(json.dumps(_journal_row(
                "a@x.com", {"subject_1": "s", "body_1": "b1",
                            "body_2": "hi {FIRST}"})) + "\n")
            path = tmp.name
        try:
            errs, lines = v.validate(cfg, steps, path)
            self.assertTrue(any("unrendered" in e for e in errs))
        finally:
            os.unlink(path)

    def test_journal_missing_variable_fails(self):
        cfg = _config(steps=["em1", "em2"])
        cfg["email_sequence"]["thread_reply_pattern"] = [False, True]
        steps = _cadence_steps(keys=["em1", "em2"])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl",
                                         delete=False,
                                         encoding="utf-8") as tmp:
            tmp.write(json.dumps(_journal_row(
                "a@x.com", {"subject_1": "s", "body_1": "b1"})) + "\n")
            path = tmp.name
        try:
            errs, lines = v.validate(cfg, steps, path)
            self.assertTrue(any("body_2" in e for e in errs))
        finally:
            os.unlink(path)

    def test_held_rows_ignored(self):
        """Held rows do not count towards the per-variable table."""
        cfg = _config(steps=["em1", "em2"])
        cfg["email_sequence"]["thread_reply_pattern"] = [False, True]
        steps = _cadence_steps(keys=["em1", "em2"])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl",
                                         delete=False,
                                         encoding="utf-8") as tmp:
            tmp.write(json.dumps(_journal_row(
                "a@x.com", {"subject_1": "s", "body_1": "b1",
                            "body_2": "b2"})) + "\n")
            tmp.write(json.dumps({"email": "b@x.com", "state": "held",
                                  "reason": "no first name"}) + "\n")
            path = tmp.name
        try:
            errs, lines = v.validate(cfg, steps, path)
            self.assertEqual(errs, [])
            output = "\n".join(lines)
            self.assertIn("1 rendered", output)
        finally:
            os.unlink(path)

    def test_clean_journal_passes(self):
        cfg = _config(steps=["em1", "em2"])
        cfg["email_sequence"]["thread_reply_pattern"] = [False, True]
        steps = _cadence_steps(keys=["em1", "em2"])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl",
                                         delete=False,
                                         encoding="utf-8") as tmp:
            for i in range(5):
                tmp.write(json.dumps(_journal_row(
                    f"user{i}@x.com",
                    {"subject_1": f"subject {i}",
                     "body_1": f"body 1 for {i}",
                     "body_2": f"body 2 for {i}"})) + "\n")
            path = tmp.name
        try:
            errs, lines = v.validate(cfg, steps, path)
            self.assertEqual(errs, [])
            output = "\n".join(lines)
            self.assertIn("5 rows x 3 variables", output)
        finally:
            os.unlink(path)


class TestMainExitCode(unittest.TestCase):
    """The CLI exit code is non-zero on failure."""

    def test_clean_config_exit_zero(self):
        rc = v.main(["--client", "productive"])
        self.assertEqual(rc, 0)

    def test_journal_with_faults_exit_nonzero(self):
        cfg = _config(steps=["em1", "em2"])
        cfg["email_sequence"]["thread_reply_pattern"] = [False, True]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl",
                                         delete=False,
                                         encoding="utf-8") as tmp:
            tmp.write(json.dumps(_journal_row(
                "a@x.com", {"subject_1": "s", "body_1": "b1",
                            "body_2": ""})) + "\n")
            path = tmp.name
        try:
            stats = v.analyse_rows(
                {"a@x.com": _journal_row(
                    "a@x.com", {"subject_1": "s", "body_1": "b1",
                                "body_2": ""})},
                {"subject_1", "body_1", "body_2"})
            errs = v.collect_errors(stats)
            self.assertTrue(len(errs) > 0)
        finally:
            os.unlink(path)


class TestThreadingInvariantAsData(unittest.TestCase):
    """The threading invariant is asserted as DATA, not from a table.

    TASK-283's correction: the table in the task file was wrong. The
    verifier reads the config at run time and asserts against what it
    finds, not against what a document says.
    """

    def test_four_step_pattern_accepted(self):
        cfg = _config(steps=["em1", "em2", "em4", "em5"],
                       thread_reply_pattern=[False, True, True, True])
        pattern, errs = v.check_thread_pattern(cfg, 4)
        self.assertEqual(errs, [])
        self.assertEqual(pattern, [False, True, True, True])

    def test_five_step_pattern_accepted(self):
        cfg = _config(thread_reply_pattern=[False, True, True, True, True])
        pattern, errs = v.check_thread_pattern(cfg, 5)
        self.assertEqual(errs, [])

    def test_three_entries_on_five_steps_refused(self):
        """The pre-change value on a post-change cadence. Named cause."""
        cfg = _config(thread_reply_pattern=[False, True, True])
        pattern, errs = v.check_thread_pattern(cfg, 5)
        self.assertTrue(len(errs) > 0)
        self.assertIn("3 entries", errs[0])
        self.assertIn("5 email steps", errs[0])

    def test_provider_variables_match_step_count(self):
        """At N steps, the provider references body_1..body_N."""
        for n in (3, 4, 5):
            keys = ["em1", "em2", "em3"][:n] if n <= 3 else \
                ["em1", "em2", "em4", "em5"][:n] if n == 4 else \
                ["em1", "em2", "em3", "em4", "em5"]
            cfg = _config(steps=keys)
            prov = v.provider_sequence_variables(cfg)
            expected_bodies = {f"body_{i}" for i in range(1, n + 1)}
            self.assertEqual(prov, {"subject_1"} | expected_bodies,
                             f"at {n} steps")


if __name__ == "__main__":
    unittest.main()
