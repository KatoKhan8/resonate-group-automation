"""One test message to the ops channel, and the `ts` read back off the reply.

WHY A SMOKE TEST AT ALL. `SLACK_LIVE` and `SLACK_BOT_TOKEN` being set proves
nothing about whether this workspace's bot can post to THIS channel: the token
can be valid, the flag on, and the post still fail with `not_in_channel`,
`channel_not_found` or `missing_scope`. Those are the three that actually
happen, they are configuration rather than code, and each needs a different
person to fix it. So this sends one real message and reports which one it hit.

It reads the `ts` back off the postMessage response rather than calling
`conversations.history`, because `ts` IS the receipt - Slack returns it only
when the message was accepted - and reading history would need a scope the
bot does not otherwise require.

REFUSES RATHER THAN GUESSES. Every variable is checked before the transport
is touched, and a missing one names itself and the file it belongs in. There
is no default channel: posting a test message into whatever channel happened
to be configured is how a client workspace gets a message meant for ops.

    py -3 scripts/slack_smoke.py            # refuses unless fully configured
    py -3 scripts/slack_smoke.py --dry-run  # prove the payload, send nothing

This posts to the GLOBAL OPS channel only. It never posts to a workspace
channel - those carry client-visible traffic and are not a test surface.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import notify                                          # noqa: E402
from src.providers import load_env, slack                       # noqa: E402


REQUIRED = (
    (slack.KEY_VAR, "the bot token, xoxb-...; config/.env or an OS variable"),
    (slack.LIVE_VAR, "the arming flag; set it to 1"),
    (notify.OPS_CHANNEL_VAR, "the global ops channel id, C..."),
)


def missing():
    """[(name, why)] for every variable that is unset or empty."""
    return [(name, why) for name, why in REQUIRED
            if not (os.environ.get(name) or "").strip()]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="build and print the payload, send nothing")
    parser.add_argument("--text", default=None,
                        help="override the message body")
    args = parser.parse_args(argv)

    load_env()

    gaps = missing()
    if gaps:
        print("REFUSED: Slack is not fully configured. Nothing was sent.\n")
        for name, why in gaps:
            print(f"  {name:<22} UNSET   {why}")
        print("\nSet them in config/.env (or as OS variables, which win over "
              "the file),\nthen run this again. See "
              "docs/SLACK-ACTIVATION-2026-09-21.md for the exact lines.")
        return 2

    channel = notify.ops_channel()
    text = args.text or (
        "Resonate OS smoke test - if you can read this, the ops channel is "
        "wired. No action required.")
    payload = {"kind": "operational", "channel": channel, "text": text,
               "blocks": [], "actions": (),
               "metadata": {"source": "scripts/slack_smoke.py"}}

    if args.dry_run:
        print("DRY RUN - nothing sent.")
        print(f"  channel  {channel}")
        print(f"  text     {text}")
        print(f"  live()   {slack.live()}")
        return 0

    # `live()` is checked again inside `post`; this is only so the failure
    # reads as a configuration problem rather than a transport one.
    if not slack.live():
        print(f"REFUSED: {slack.LIVE_VAR} is set but not to a truthy value, "
              f"or {slack.KEY_VAR} is empty. Nothing was sent.")
        return 2

    try:
        result = slack.post(payload)
    except Exception as e:                                      # noqa: BLE001
        # Never print the exception's payload - `post` is careful not to echo
        # the token, and the message body would land in a log.
        name = type(e).__name__
        print(f"FAILED: {name}: {str(e)[:200]}")
        print("\nThe three that actually happen:")
        print("  channel_not_found  the id is wrong, or the bot is not in "
              "this workspace")
        print("  not_in_channel     invite the bot: /invite @<bot> in the "
              "channel")
        print("  missing_scope      the token needs chat:write")
        return 1

    ts = (result or {}).get("ts")
    if not ts:
        print("FAILED: Slack accepted the call but returned no `ts`, so there "
              "is no receipt that a message exists. Treating as a failure.")
        return 1

    print("SENT")
    print(f"  channel  {result.get('channel')}")
    print(f"  ts       {ts}")
    print("\n`ts` is the receipt: Slack returns it only for a message it "
          "accepted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
