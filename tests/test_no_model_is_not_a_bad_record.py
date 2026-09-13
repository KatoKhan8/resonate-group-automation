#!/usr/bin/env python3
"""Nobody configured a model. That is not this company's fault.

`generate.generate_record` holds a record when the model fails on it, which
is right: a draft that could not be written is a record that must not go
forward. It was also holding records when NO MODEL EXISTED AT ALL, because
`NoModel.complete` raised the same `ModelError` a real failure raises.

Measured 2026-09-13. `python -m src.generate --live --id 16kagency-com` moved
that record from `verified` to `held`, wrote no event saying so, saved the
estate, and printed "GENERATED: 1 record(s), model=none". Three separate
things were wrong and each hid the next:

  - `main` never called `llm.from_env()`, so `--live` could not reach the
    model that was sitting in `config/.env` the whole time;
  - `NoModel` raised an exception that cannot be told apart from a real
    model failure, so the caller could not know not to blame the record;
  - and holding wrote a configuration mistake into canonical state, once per
    record, under a banner reporting success.

At estate scale that is three hundred records held for a missing environment
variable, and nothing in the queue saying why.
"""
import unittest
from unittest import mock

from src import clients, generate, llm, providers, store
from tests.base import QueueTest

# The real client config, because the sequence these drafts are
# planned against is the one Productive actually runs. `client` is a
# CONFIG everywhere inside this module, not a slug - `plan` hands it
# to `cadence.steps_for` as `config`.
CONFIG = clients.load("productive")


def a_record(rid="rec-1", state="verified"):
    return {"id": rid, "client": "productive", "domain": "example.com",
            "company": "Example Agency", "state": state,
            "contacts": [{"key": "rec-1-c1", "name": "Ada Tester",
                          "email": "ada@example.com", "first_name": "Ada",
                          "persona": "economic_buyer", "angle": "founder",
                          # `lint.sendable` is the authority and reads the
                          # verification evidence, not a copied boolean -
                          # `src/verification.py` is the only module allowed
                          # to conclude an address may be written to. A
                          # fixture carrying the flag alone plans no work at
                          # all, so nothing would reach the model and this
                          # file would pass by asking nothing.
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


class NoModelIsItsOwnKindOfFailure(unittest.TestCase):

    def test_it_is_still_a_model_error(self):
        """Every existing `except llm.ModelError` must keep catching it."""
        self.assertTrue(issubclass(llm.NoModelConfigured, llm.ModelError))

    def test_nomodel_raises_the_configuration_one(self):
        with self.assertRaises(llm.NoModelConfigured):
            llm.NoModel().complete("anything")

    def test_a_real_model_failure_is_not_the_configuration_one(self):
        """A bad endpoint is a failure OF a model, not the absence of one."""
        with mock.patch.object(providers, "request",
                               return_value=(500, {"error": "nope"})):
            with self.assertRaises(llm.ModelError) as caught:
                llm.OpenAICompatibleModel(
                    key="k", model="m", base="https://endpoint.test/v1"
                ).complete("anything")
        self.assertNotIsInstance(caught.exception, llm.NoModelConfigured)


class AMissingModelHoldsNobody(QueueTest):

    def setUp(self):
        super().setUp()
        store.save([a_record()])

    def test_generate_record_raises_instead_of_holding(self):
        rec = store.load()[0]
        with self.assertRaises(llm.NoModelConfigured):
            generate.generate_record(rec, llm.NoModel(), CONFIG)
        self.assertEqual(rec.get("state"), "verified",
                         "a configuration fault was written onto the record")

    def test_a_real_model_failure_still_holds_the_record(self):
        """The guard that was there for a reason is still there.

        If this passes while the one above passes, the two cases are being
        told apart. If it fails, the fix went too far and a record whose
        draft genuinely could not be written would go forward undrafted.
        """
        class Failing:
            name = "failing"

            def complete(self, prompt):
                raise llm.ModelError("the endpoint returned 500")

        rec = store.load()[0]
        generate.generate_record(rec, Failing(), CONFIG)
        self.assertEqual(rec.get("state"), "held")

    def test_the_estate_is_not_saved_when_no_model_is_configured(self):
        """`run` saves every targeted record after generating. A run that
        asked nothing must leave the file exactly as it found it."""
        before = store.load()
        with self.assertRaises(llm.NoModelConfigured):
            generate.run(live=True, client=CONFIG)
        self.assertEqual(store.load(), before)


class TheCommandReachesForTheConfiguredModel(QueueTest):

    def setUp(self):
        super().setUp()
        store.save([a_record()])

    def test_live_asks_from_env_for_a_model(self):
        """`--live` used to call `run()` with nothing and print GENERATED."""
        asked = []

        def from_env():
            asked.append(True)
            return llm.NoModel()

        with mock.patch.object(llm, "from_env", from_env):
            code = generate.main(["--live", "--id", "rec-1", "--client", "productive"])
        self.assertTrue(asked, "--live never asked for the configured model")
        self.assertEqual(code, 1, "it reported success with no model")

    def test_a_dry_run_does_not_ask_for_one(self):
        """A credential in the environment must not turn a dry run paid."""
        asked = []
        with mock.patch.object(llm, "from_env",
                               lambda: asked.append(True) or llm.NoModel()):
            self.assertEqual(generate.main(["--id", "rec-1", "--client", "productive"]), 0)
        self.assertFalse(asked, "a dry run reached for a real model")

    def test_nothing_is_written_when_the_command_refuses(self):
        before = store.load()
        with mock.patch.object(llm, "from_env", lambda: llm.NoModel()):
            generate.main(["--live", "--id", "rec-1", "--client", "productive"])
        self.assertEqual(store.load(), before)


if __name__ == "__main__":
    unittest.main()
