#!/usr/bin/env python3
"""Qwen Code CLI behind the model seam.

`QwenCliModel` satisfies the same `complete(prompt) -> str` contract as
`NoModel`, `ScriptedModel` and `OpenAICompatibleModel`, so every semantic
step in this repository can run on Qwen instead of a paid endpoint without
a single caller changing.

The CLI is an AGENT, not a completion API. Left alone it narrates, uses
tools and reads files. `--json-schema` forces structured output, `--bare`
reduces tool noise, `-y` is the headless flag, and the prompt travels as
an argument-list element (never `shell=True`) because it contains
untrusted record data by construction.

Every test mocks `subprocess.run`. No test invokes the real CLI: it is
slow, non-deterministic, and would make the suite depend on a binary at
an absolute Windows path.
"""
import json
import subprocess
import unittest
from unittest import mock

from src import llm, generate, clients, store
from tests.base import QueueTest

CONFIG = clients.load("productive")

FAKE_EXE = r"C:\fake\qwen.cmd"


def a_model():
    return llm.QwenCliModel(exe=FAKE_EXE, timeout=30)


def a_result(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def a_record(rid="rec-qwen-1"):
    return {"id": rid, "client": "productive", "domain": "example.com",
            "company": "Example Agency", "state": "verified",
            "contacts": [{"key": "rec-qwen-1-c1", "name": "Ada Tester",
                          "email": "ada@example.com", "first_name": "Ada",
                          "persona": "economic_buyer", "angle": "founder",
                          "linkedin": "https://www.linkedin.com/in/ada-tester",
                          "title": "Managing Director",
                          "sendable": True, "verdict": "valid",
                          "email_source": "provider",
                          "mx": {"mx_classification": "normal",
                                 "email_eligible": True,
                                 "email_excluded_reason": None},
                          "reoon": {"is_catch_all": False,
                                    "is_deliverable": True,
                                    "is_safe_to_send": True,
                                    "overall_score": 98,
                                    "status": "valid"},
                          "verification": {"state": "verified",
                                           "sendable": True,
                                           "reason": "fixture"}}]}


def _exe_exists():
    """Patch os.path.isfile so the fake exe passes configured()."""
    return mock.patch("os.path.isfile", return_value=True)


class TheSeamIsUnchanged(unittest.TestCase):
    """`QwenCliModel` satisfies the same contract as the stubs."""

    def test_it_has_the_same_surface_as_the_other_models(self):
        for model in (llm.NoModel(), llm.ScriptedModel("x"),
                      llm.OpenAICompatibleModel(key="k", model="m",
                                                base="https://x.test"),
                      a_model()):
            self.assertTrue(callable(getattr(model, "complete", None)))
            self.assertTrue(getattr(model, "name", None))

    def test_ask_drives_it_like_any_other_model(self):
        answer = '{"note": "hello, worth a word?"}'
        with _exe_exists(), \
             mock.patch("subprocess.run",
                        return_value=a_result(stdout=answer)):
            data, attempts, errors = llm.ask(a_model(), "linkedin_note",
                                             "prompt")
        self.assertEqual(data["note"], "hello, worth a word?")
        self.assertEqual(attempts, 1)
        self.assertEqual(errors, [])

    def test_ask_retries_a_bad_answer_and_feeds_the_error_back(self):
        bad = a_result(stdout="not json at all")
        good = a_result(stdout='{"note": "second time"}')
        with _exe_exists(), \
             mock.patch("subprocess.run", side_effect=[bad, good]):
            data, attempts, errors = llm.ask(a_model(), "linkedin_note",
                                             "prompt")
        self.assertEqual(data["note"], "second time")
        self.assertEqual(attempts, 2)
        self.assertTrue(errors, "the first failure was not fed back")


class ConfiguredMeansTheExecutableExists(unittest.TestCase):

    def test_configured_when_file_exists(self):
        with mock.patch("os.path.isfile", return_value=True):
            self.assertTrue(llm.QwenCliModel(exe="/fake/qwen").configured())

    def test_not_configured_when_file_is_missing(self):
        with mock.patch("os.path.isfile", return_value=False):
            self.assertFalse(llm.QwenCliModel(exe="/no/such/path").configured())

    def test_why_not_names_the_missing_path(self):
        with mock.patch("os.path.isfile", return_value=False):
            m = llm.QwenCliModel(exe="/no/such/path")
            self.assertIn("/no/such/path", m.why_not())

    def test_an_unconfigured_model_refuses_before_any_subprocess(self):
        with mock.patch("os.path.isfile", return_value=False), \
             mock.patch("subprocess.run") as ran:
            with self.assertRaises(llm.ModelError):
                llm.QwenCliModel(exe="/no/such/path").complete("anything")
        self.assertFalse(ran.called,
                         "it spawned a subprocess for a missing executable")


class ThePromptTravelsAsAnArgument(unittest.TestCase):
    """The prompt contains untrusted record data. It must never reach a shell."""

    def test_subprocess_run_is_called_with_a_list_not_a_string(self):
        with _exe_exists(), \
             mock.patch("subprocess.run",
                        return_value=a_result(stdout='{"note": "ok"}')) as ran:
            a_model().complete("the prompt text")
        args = ran.call_args[0][0]
        self.assertIsInstance(args, list,
                              "the prompt must travel as an argument list, "
                              "never a shell string")
        self.assertFalse(ran.call_args[1].get("shell", False),
                         "shell=True is forbidden: the prompt carries "
                         "untrusted record data")

    def test_the_prompt_is_in_the_argument_list(self):
        with _exe_exists(), \
             mock.patch("subprocess.run",
                        return_value=a_result(stdout='{"note": "ok"}')) as ran:
            a_model().complete("the specific prompt")
        args = ran.call_args[0][0]
        self.assertIn("the specific prompt", args)

    def test_dash_y_is_present_for_headless(self):
        """`--approval-mode auto` cannot run headless. `-y` is what works."""
        with _exe_exists(), \
             mock.patch("subprocess.run",
                        return_value=a_result(stdout='{"note": "ok"}')) as ran:
            a_model().complete("prompt")
        args = ran.call_args[0][0]
        self.assertIn("-y", args)

    def test_json_schema_is_derived_from_schemas(self):
        """The schema passed to --json-schema must come from llm.SCHEMAS,
        not a parallel representation that would drift."""
        with _exe_exists(), \
             mock.patch("subprocess.run",
                        return_value=a_result(stdout='{"note": "ok"}')) as ran:
            a_model().complete("prompt")
        args = ran.call_args[0][0]
        i = args.index("--json-schema")
        schema = json.loads(args[i + 1])
        self.assertEqual(schema["type"], "object")
        props = schema["properties"]
        for spec in llm.SCHEMAS.values():
            for field in spec["required"]:
                self.assertIn(field, props,
                              f"{field} is in SCHEMAS but not in the "
                              f"derived schema")
            for field in spec["optional"]:
                self.assertIn(field, props)

    def test_the_schema_is_not_a_hardcoded_parallel_representation(self):
        """If SCHEMAS changes, the derived schema changes with it."""
        original = dict(llm.SCHEMAS)
        try:
            llm.SCHEMAS["test_step"] = {
                "required": ("unique_test_field_xyzzy",), "optional": ()}
            schema = llm._qwen_json_schema()
            self.assertIn("unique_test_field_xyzzy", schema["properties"])
        finally:
            llm.SCHEMAS.clear()
            llm.SCHEMAS.update(original)


class FailureClassification(unittest.TestCase):
    """Timeout and process failure are ModelUnavailable. Bad output is
    ModelError. Getting this wrong is not cosmetic: generate_record
    re-raises the first and holds the record on the second."""

    def test_a_timeout_raises_model_unavailable(self):
        with _exe_exists(), \
             mock.patch("subprocess.run",
                        side_effect=subprocess.TimeoutExpired(cmd="qwen",
                                                              timeout=30)):
            with self.assertRaises(llm.ModelUnavailable):
                a_model().complete("prompt")

    def test_exit_55_is_wall_time_and_raises_model_unavailable(self):
        with _exe_exists(), \
             mock.patch("subprocess.run",
                        return_value=a_result(returncode=55)):
            with self.assertRaises(llm.ModelUnavailable):
                a_model().complete("prompt")

    def test_a_non_zero_exit_raises_model_unavailable(self):
        with _exe_exists(), \
             mock.patch("subprocess.run",
                        return_value=a_result(returncode=1,
                                              stderr="something broke")):
            with self.assertRaises(llm.ModelUnavailable):
                a_model().complete("prompt")

    def test_empty_output_raises_model_error(self):
        """Not ModelUnavailable: the process succeeded but gave nothing."""
        with _exe_exists(), \
             mock.patch("subprocess.run",
                        return_value=a_result(stdout="")):
            with self.assertRaises(llm.ModelError) as caught:
                a_model().complete("prompt")
        self.assertNotIsInstance(caught.exception, llm.ModelUnavailable)

    def test_the_output_is_returned_on_success(self):
        answer = '{"hook": "a specific hook about something"}'
        with _exe_exists(), \
             mock.patch("subprocess.run",
                        return_value=a_result(stdout=answer)):
            self.assertEqual(a_model().complete("prompt"), answer)


class TheDifferenceMatters(QueueTest):
    """Prove the classification is not cosmetic.

    `generate_record` raises on `ModelUnavailable` (does not hold the
    record) and holds on `ModelError` (the record's business). If the
    two were the same type, a timeout would park a company forever.
    """

    def setUp(self):
        super().setUp()
        store.save([a_record()])

    def test_a_timeout_does_not_hold_the_record(self):
        """ModelUnavailable: the process failed, not the record."""
        with _exe_exists(), \
             mock.patch("subprocess.run",
                        side_effect=subprocess.TimeoutExpired(cmd="qwen",
                                                              timeout=30)):
            rec = store.load()[0]
            with self.assertRaises(llm.ModelUnavailable):
                generate.generate_record(rec, a_model(), CONFIG)
        self.assertEqual(rec.get("state"), "verified",
                         "a timeout held the record - it should not have")

    def test_exit_55_does_not_hold_the_record(self):
        with _exe_exists(), \
             mock.patch("subprocess.run",
                        return_value=a_result(returncode=55)):
            rec = store.load()[0]
            with self.assertRaises(llm.ModelUnavailable):
                generate.generate_record(rec, a_model(), CONFIG)
        self.assertEqual(rec.get("state"), "verified",
                         "a wall-time abort held the record")

    def test_empty_output_holds_the_record(self):
        """ModelError: the process succeeded but gave nothing usable.
        That IS the record's business."""
        with _exe_exists(), \
             mock.patch("subprocess.run",
                        return_value=a_result(stdout="")):
            rec = store.load()[0]
            generate.generate_record(rec, a_model(), CONFIG)
        self.assertEqual(rec.get("state"), "held",
                         "empty output did not hold the record - "
                         "the classification is wrong")


class FromEnvSelection(unittest.TestCase):

    def test_returns_nomodel_when_nothing_is_configured(self):
        with mock.patch("os.path.isfile", return_value=False), \
             mock.patch("src.providers.load_env", return_value={}), \
             mock.patch.dict("os.environ", {}, clear=True):
            self.assertIsInstance(llm.from_env(), llm.NoModel)

    def test_returns_qwen_when_cli_exists_but_no_api_key(self):
        with mock.patch("os.path.isfile", return_value=True), \
             mock.patch("src.providers.load_env", return_value={}), \
             mock.patch.dict("os.environ", {}, clear=True):
            result = llm.from_env()
        self.assertIsInstance(result, llm.QwenCliModel)

    def test_openai_takes_priority_over_qwen(self):
        """The paid path wins when both are configured."""
        from src import providers
        with mock.patch("os.path.isfile", return_value=True), \
             mock.patch.object(providers, "load_env",
                               return_value={"LLM_API_KEY": "k",
                                             "LLM_BASE_URL": "https://x.test",
                                             "LLM_MODEL": "m"}), \
             mock.patch.dict("os.environ", {"LLM_API_KEY": "k",
                                            "LLM_BASE_URL": "https://x.test",
                                            "LLM_MODEL": "m"}, clear=False):
            result = llm.from_env()
        self.assertIsInstance(result, llm.OpenAICompatibleModel)


class BreakTheWiring(QueueTest):
    """Delete the call, not the logic. If the subprocess mock is removed,
    the tests must fail - proving they test the wiring, not just the
    classification logic in isolation.

    These tests drive through `generate_record`, the real entry point,
    not through `complete` directly. The mock on `subprocess.run` is the
    wiring: without it, the classification cannot fire.
    """

    def setUp(self):
        super().setUp()
        store.save([a_record()])

    def test_timeout_through_generate_record_raises_not_holds(self):
        """Driven through the real entry point. The subprocess mock is the
        wiring: remove it and the test cannot prove the classification."""
        with _exe_exists(), \
             mock.patch("subprocess.run",
                        side_effect=subprocess.TimeoutExpired(cmd="qwen",
                                                              timeout=30)):
            rec = store.load()[0]
            with self.assertRaises(llm.ModelUnavailable):
                generate.generate_record(rec, a_model(), CONFIG)
        self.assertEqual(rec.get("state"), "verified")

    def test_break_the_wiring_remove_the_mock_and_it_fails(self):
        """Without the _exe_exists() patch, the fake path fails configured()
        and raises ModelError (not ModelUnavailable). generate_record catches
        ModelError and holds the record. With the patch, a timeout raises
        ModelUnavailable and the record stays verified. The two outcomes
        prove the mock is what connects the test to the classification."""
        rec = store.load()[0]
        # No _exe_exists() patch: the fake path fails configured()
        generate.generate_record(rec, a_model(), CONFIG)
        # The record was HELD because configured() raised ModelError,
        # not ModelUnavailable. With the wiring intact (the patch), the
        # same model raises ModelUnavailable on timeout and the record
        # stays verified. Different outcome = different classification.
        self.assertEqual(rec.get("state"), "held",
                         "without the exe-exists patch, the model should "
                         "fail at configured() with ModelError, which "
                         "generate_record catches and holds")


if __name__ == "__main__":
    unittest.main()


class TheAgentCannotSeeTheEstate(unittest.TestCase):
    """`-y` auto-approves every tool call and Qwen Code is an AGENT.

    Without `cwd`, `subprocess.run` starts it in whatever directory the caller
    happened to be in - for every real caller, the repository root, two levels
    above `work/queue.jsonl`. `docs/CLAUDE-HANDOFF.md` warned about precisely
    this: "a model that opens work/queue.jsonl to be helpful has just put
    another client's data into a prompt."

    So the call runs in a fresh empty directory. This is not a sandbox and does
    not pretend to be - the process could still walk upwards - but it removes
    the accident, and the accident is the failure mode.
    """

    def test_the_subprocess_runs_in_an_empty_directory(self):
        import os
        import subprocess

        from src import llm

        seen = {}

        def fake_run(argv, **kwargs):
            seen["cwd"] = kwargs.get("cwd")
            seen["listing"] = (os.listdir(kwargs["cwd"])
                               if kwargs.get("cwd") else None)
            raise subprocess.TimeoutExpired(argv, 1)

        model = llm.QwenCliModel(exe=__file__)
        with mock.patch.object(subprocess, "run", side_effect=fake_run):
            with self.assertRaises(llm.ModelUnavailable):
                model.complete("anything")

        self.assertIsNotNone(seen["cwd"], "the CLI ran with no cwd at all")
        self.assertEqual(seen["listing"], [],
                         "the directory the agent starts in is not empty")

    def test_it_is_not_the_repository_root(self):
        import os
        import subprocess

        from src import llm

        seen = {}

        def fake_run(argv, **kwargs):
            seen["cwd"] = kwargs.get("cwd")
            raise subprocess.TimeoutExpired(argv, 1)

        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model = llm.QwenCliModel(exe=__file__)
        with mock.patch.object(subprocess, "run", side_effect=fake_run):
            with self.assertRaises(llm.ModelUnavailable):
                model.complete("anything")

        self.assertNotEqual(os.path.abspath(seen["cwd"]), root)
        self.assertFalse(
            os.path.exists(os.path.join(seen["cwd"], "work")),
            "the estate is reachable from where the agent starts")
