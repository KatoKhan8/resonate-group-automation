"""Resolve channel ids to names, and map them onto workspace policies.

THE MAPPING IS DERIVABLE, SO IT MUST NOT BE GUESSED. Two channel ids were
handed over without saying which belongs to which workspace, and the two
workspaces already carry channel NAMES in policy:

    productive   slack.workspace_channel = '#client-productive-replies'
    contactout   slack.workspace_channel = '#client-contactout-replies'

`conversations.info` returns each id's name, so the pairing is a lookup rather
than a coin flip. Guessing it wrong posts one client's reply traffic into
another client's channel, which is the exact failure `notify.workspace_channel`
is built to make impossible - so this refuses to write anything it had to
assume.

WHY IDS AT ALL. `slack.post` passes `payload["channel"]` straight to
`chat.postMessage` and resolves nothing. Slack still accepts a `#name` there
for public channels, but it is deprecated, it does not work for private
channels, and it silently breaks the moment somebody renames the channel. An
id never moves.

    py -3 scripts/slack_map_channels.py                # show the mapping only
    py -3 scripts/slack_map_channels.py --apply        # write the policies

Needs SLACK_BOT_TOKEN. Needs no posting scope and sends no message; it reads.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import workspaces as ws                               # noqa: E402
from src.providers import load_env, slack                      # noqa: E402


# The ids handed over on 2026-09-21, without a mapping.
CANDIDATES = ("C0ADUMGQX8S", "C0BFUF4JRK9")

# Every workspace that carries a per-client reply channel today.
SLUGS = ("productive", "contactout")

POLICY_KEY = "slack.workspace_channel"


def _info(channel_id):
    """{'id','name'} for one channel, or an error string."""
    status, data = slack.request(
        "GET", f"{slack.BASE}/conversations.info?channel={channel_id}",
        {"Authorization": f"Bearer {slack.key(slack.KEY_VAR)}"}, None)
    if not slack.ok(status):
        return {"id": channel_id, "error": f"HTTP {status}"}
    if not isinstance(data, dict) or not data.get("ok"):
        return {"id": channel_id,
                "error": (data or {}).get("error", "unknown")}
    channel = data.get("channel") or {}
    return {"id": channel_id, "name": channel.get("name"),
            "is_private": channel.get("is_private")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="write the resolved ids into workspace policy")
    args = parser.parse_args(argv)

    load_env()
    if not (os.environ.get(slack.KEY_VAR) or "").strip():
        print(f"REFUSED: {slack.KEY_VAR} is unset, so no id can be resolved "
              f"and nothing may be guessed. Nothing was written.")
        return 2

    current = {slug: (ws.policy(slug).get(POLICY_KEY) or "") for slug in SLUGS}
    print("workspace policy today:")
    for slug, value in current.items():
        print(f"  {slug:<12} {POLICY_KEY} = {value!r}")

    resolved = [_info(cid) for cid in CANDIDATES]
    print("\nresolved from Slack:")
    for row in resolved:
        if row.get("error"):
            print(f"  {row['id']}  ERROR {row['error']}")
        else:
            print(f"  {row['id']}  #{row.get('name')}"
                  f"{'  (private)' if row.get('is_private') else ''}")

    if any(r.get("error") for r in resolved):
        print("\nREFUSED: at least one id did not resolve. Nothing was "
              "written. `channel_not_found` usually means the bot is not a "
              "member of that channel.")
        return 1

    # Pair by name. A workspace's current policy value is its channel NAME,
    # so the match is exact once the leading '#' is stripped from both sides.
    pairing, unmatched = {}, []
    for row in resolved:
        name = (row.get("name") or "").lstrip("#")
        hit = [s for s, v in current.items() if v.lstrip("#") == name]
        if len(hit) == 1:
            pairing[hit[0]] = row["id"]
        else:
            unmatched.append(row)

    print("\nmapping:")
    for slug in SLUGS:
        if slug in pairing:
            print(f"  {slug:<12} {current[slug]!r}  ->  {pairing[slug]}")
        else:
            print(f"  {slug:<12} {current[slug]!r}  ->  UNRESOLVED")

    if unmatched or len(pairing) != len(SLUGS):
        print("\nREFUSED: the names did not pair one-to-one with the "
              "workspace policies, so the mapping would be an assumption. "
              "Nothing was written. Set them explicitly with "
              "`ws.set_policy(<slug>, {'slack.workspace_channel': '<id>'})`.")
        return 1

    if not args.apply:
        print("\nDRY RUN - nothing written. Re-run with --apply.")
        return 0

    for slug, channel_id in pairing.items():
        ws.set_policy(slug, {POLICY_KEY: channel_id}, actor="operator")
        print(f"  set {slug} -> {channel_id}")
    print("\nwritten. Ids do not move when a channel is renamed; names do.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
