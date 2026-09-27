"""No operator-facing route may resolve to a retired channel.

WHY THIS TEST EXISTS. On 2026-09-27 a status report was posted to
`#resonate-notifications` (C0C34GCAR27) instead of `#resonate-os`
(C0C3C6MDN9L). Nothing was broken: `SLACK_OPS_CHANNEL` still pointed at the
retired room, `notify.ops_channel()` returned it, and the caller had no way to
tell that the id it received was the wrong room. The operator retired the
channel and asked for the change to live in the routing rather than in a
variable's value, so that a stale `.env` on another machine cannot resurrect it.

The assertions are about the RESOLVED ID, not about the text of the source. A
test that greps for a channel constant would pass while a resolver still handed
the retired id back.
"""
import os
import unittest

from src import notify

RETIRED = "C0C34GCAR27"        # #resonate-notifications, retired 2026-09-27
RESONATE_OS = "C0C3C6MDN9L"    # #resonate-os


class RetiredChannelIsNeverAdestination(unittest.TestCase):

    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in
                       ("SLACK_OPS_CHANNEL", "SLACK_STATUS_CHANNEL")}

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_ops_channel_never_returns_the_retired_id(self):
        """Even with the retired id explicitly configured as the ops channel."""
        os.environ["SLACK_OPS_CHANNEL"] = RETIRED
        os.environ["SLACK_STATUS_CHANNEL"] = RESONATE_OS
        self.assertNotEqual(notify.ops_channel(), RETIRED)

    def test_ops_channel_resolves_to_resonate_os(self):
        os.environ["SLACK_OPS_CHANNEL"] = RETIRED
        os.environ["SLACK_STATUS_CHANNEL"] = RESONATE_OS
        self.assertEqual(notify.ops_channel(), RESONATE_OS)

    def test_status_channel_never_returns_the_retired_id(self):
        os.environ["SLACK_STATUS_CHANNEL"] = RETIRED
        self.assertIsNone(notify.status_channel())

    def test_ops_channel_is_none_rather_than_the_retired_room(self):
        """With no status channel, the answer is None - not the old variable.

        Posting nothing is the safe failure. Falling back to SLACK_OPS_CHANNEL
        would put operator-facing detail back in the retired room.
        """
        os.environ["SLACK_OPS_CHANNEL"] = RETIRED
        os.environ.pop("SLACK_STATUS_CHANNEL", None)
        self.assertIsNone(notify.ops_channel())

    def test_the_real_configured_environment_does_not_resolve_to_retired(self):
        """The live config, as loaded, must not route anywhere retired."""
        from src.providers import load_env
        load_env()
        for name, value in (("ops_channel", notify.ops_channel()),
                            ("status_channel", notify.status_channel())):
            self.assertNotIn(
                value, notify.RETIRED_CHANNELS,
                "%s resolved to a retired channel: %r" % (name, value))


if __name__ == "__main__":
    unittest.main()
