"""Output and operations are two destinations, and output never falls back.

`ops_channel()` falls back to the status channel on purpose. `output_channel()`
must NOT, and the asymmetry is the whole content of this module: generated copy
published into the operations room buries the alerts that room exists for, and
a muted operations room is the failure `notify.RETIRED_CHANNELS` was written
after - one status report reached `#resonate-notifications` on 2026-09-27 and
the channel was retired by the operator.
"""
import os
import unittest
from unittest import mock

from src import config, notify


class TheVariableIsDeclared(unittest.TestCase):
    def test_it_is_in_the_registry(self):
        """A credential or destination read from the environment but absent
        from `config.VARIABLES` cannot be reported by
        `credential_health.py`, which reads the registry and so cannot
        invent a name."""
        self.assertIn("SLACK_OUTPUT_CHANNEL", config.BY_NAME)

    def test_it_is_grouped_with_the_other_slack_settings(self):
        _classification, group, why = config.BY_NAME["SLACK_OUTPUT_CHANNEL"]
        self.assertEqual(group, "slack")
        self.assertTrue(why.strip(), "a registry row with no reason is a name")


class TheOutputChannelResolves(unittest.TestCase):
    def test_it_returns_what_is_configured(self):
        with mock.patch.dict(os.environ,
                             {"SLACK_OUTPUT_CHANNEL": "C0OUTPUT1234"}):
            self.assertEqual(notify.output_channel(), "C0OUTPUT1234")

    def test_whitespace_only_is_not_a_channel(self):
        with mock.patch.dict(os.environ, {"SLACK_OUTPUT_CHANNEL": "   "}):
            self.assertIsNone(notify.output_channel())

    def test_unset_is_none_rather_than_empty_string(self):
        env = {k: v for k, v in os.environ.items()
               if k != "SLACK_OUTPUT_CHANNEL"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertIsNone(notify.output_channel())

    def test_a_retired_channel_is_refused_here_too(self):
        """The retirement is enforced in routing, not by editing the value,
        so a stale `.env` on another machine cannot resurrect it."""
        retired = notify.RETIRED_CHANNELS[0]
        with mock.patch.dict(os.environ,
                             {"SLACK_OUTPUT_CHANNEL": retired}):
            self.assertIsNone(notify.output_channel())


class ItNeverFallsBack(unittest.TestCase):
    """The reason this module exists."""

    def test_an_unset_output_channel_does_not_become_the_ops_channel(self):
        env = {k: v for k, v in os.environ.items()
               if k != "SLACK_OUTPUT_CHANNEL"}
        env["SLACK_OPS_CHANNEL"] = "C0OPSROOM999"
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertIsNone(
                notify.output_channel(),
                "output fell back to the operations channel - generated "
                "copy would be published into the room that exists for "
                "alerts, which is how an operations channel gets muted")

    def test_an_unset_output_channel_does_not_become_the_status_channel(self):
        env = {k: v for k, v in os.environ.items()
               if k != "SLACK_OUTPUT_CHANNEL"}
        env["SLACK_STATUS_CHANNEL"] = "C0STATUS7777"
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertIsNone(notify.output_channel())

    def test_ops_still_does_fall_back_and_that_is_not_changed(self):
        """THE CONTROL on the asymmetry.

        Without it, 'output never falls back' is satisfied by a change that
        broke every fallback in the module, and the operations channel would
        go silent when its own variable is unset.
        """
        env = {k: v for k, v in os.environ.items()
               if k not in ("SLACK_OPS_CHANNEL",)}
        env["SLACK_STATUS_CHANNEL"] = "C0STATUS7777"
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(notify.ops_channel(), "C0STATUS7777",
                             "ops stopped falling back to status, which is "
                             "a different guarantee and must survive")

    def test_output_and_ops_are_not_the_same_function(self):
        with mock.patch.dict(os.environ,
                             {"SLACK_OUTPUT_CHANNEL": "C0OUTPUT1234",
                              "SLACK_OPS_CHANNEL": "C0OPSROOM999"}):
            self.assertNotEqual(notify.output_channel(),
                                notify.ops_channel())


if __name__ == "__main__":
    unittest.main()
