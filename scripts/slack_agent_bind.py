#!/usr/bin/env python3
"""Bind a Slack channel to a scope. The operator's tool, not the agent's.

    py -3 scripts/slack_agent_bind.py --show
    py -3 scripts/slack_agent_bind.py --internal C0C3C6MDN9L C0C34GCAR27
    py -3 scripts/slack_agent_bind.py --operator U07KWV94J0H
    py -3 scripts/slack_agent_bind.py --client productive --channel C0... \\
        --dry-run
    py -3 scripts/slack_agent_bind.py --client productive --channel C0...

OPERATOR, 2026-09-21: "Binding lives in workspace policy, set by the
operator." This is the only thing that sets one. The agent reads bindings
and cannot write them - `slackscope` imports no writer, and
`tests/test_slack_agent_cannot_act.py` asserts it.

## WHY BINDING A CLIENT CHANNEL IS A SEPARATE COMMAND WITH A DRY RUN

Binding `#some-client-channel` to a workspace tells the agent it may answer
about that client, by name, to whoever is in that room. Getting it wrong is
not a configuration error, it is a disclosure - and it is the one mistake
this whole module exists to prevent.

So `--client` prints exactly what it would write, names the channel through
Slack's own `conversations.info` where a token allows it, and refuses to
proceed unless `--channel` is an id rather than a name. `slack.post` resolves
no names either: it passes the string straight to `chat.postMessage`, so a
`#name` that looks right and is not would post into somebody else's room.

## THE TWO KINDS OF BINDING ARE STORED IN DIFFERENT PLACES

    internal channels   SLACK_INTERNAL_CHANNELS, an environment variable
    client channels     `slack.agent_channel` in that WORKSPACE's policy

An internal channel belongs to no workspace, so filing it under one would
make it look like that client's. A client channel belongs to exactly one,
and the workspace row is where every other per-tenant decision already
lives.

This command does not edit `config/.env`. It prints the line to add, because
that file holds credentials and a script that rewrites it is a script that
can lose one.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import slackscope, workspaces as ws                     # noqa: E402
from src.providers import load_env                               # noqa: E402

#: A Slack channel id. Ids start with C (public), G (private) or D (DM), and
#: are upper-case alphanumeric. A `#name` is refused on purpose.
CHANNEL_SHAPE = ("C", "G", "D")
USER_SHAPE = ("U", "W")


def _emit(line=""):
    print(line, flush=True)


def looks_like_channel_id(value):
    value = (value or "").strip()
    return (len(value) >= 9 and value[0] in CHANNEL_SHAPE
            and value.isalnum() and value.isupper())


def looks_like_user_id(value):
    value = (value or "").strip()
    return (len(value) >= 9 and value[0] in USER_SHAPE
            and value.isalnum() and value.isupper())


def show():
    """Every binding this build would resolve, and where each comes from."""
    load_env()
    rows = ws.load()
    _emit("INTERNAL CHANNELS  (env %s, plus the ops and status channels)"
          % slackscope.INTERNAL_CHANNELS_VAR)
    internal = sorted(slackscope.internal_channels())
    for channel in internal:
        origin = []
        if channel in slackscope._csv_env(slackscope.INTERNAL_CHANNELS_VAR):
            origin.append(slackscope.INTERNAL_CHANNELS_VAR)
        if channel == (os.environ.get(slackscope.OPS_CHANNEL_VAR) or "").strip():
            origin.append(slackscope.OPS_CHANNEL_VAR)
        if channel == (os.environ.get(
                slackscope.STATUS_CHANNEL_VAR) or "").strip():
            origin.append(slackscope.STATUS_CHANNEL_VAR)
        _emit("  %s  <- %s" % (channel, ", ".join(origin) or "?"))
    if not internal:
        _emit("  (none)")

    _emit()
    _emit("CLIENT CHANNELS    (%s in each workspace's policy)"
          % slackscope.AGENT_CHANNEL_KEY)
    bound = slackscope.client_channels(rows)
    for channel, slug in sorted(bound.items()):
        _emit("  %s  -> %s" % (channel, slug))
    if not bound:
        _emit("  (none - every client channel resolves UNBOUND, which is "
              "the safe default)")

    _emit()
    _emit("OPERATOR AND PEOPLE")
    operator = (os.environ.get(slackscope.OPERATOR_USER_VAR) or "").strip()
    _emit("  operator            %s" % (operator or "(unset - NOBODY can "
                                        "approve a change request)"))
    _emit("  internal users      %s"
          % ", ".join(sorted(slackscope.internal_users(rows))) or "(none)")
    for entry in ws.workspaces(rows):
        policy = (entry.get("settings") or {}).get("policy") or {}
        people = slackscope._policy_list(
            policy, slackscope.WORKSPACE_USERS_KEY)
        if people:
            _emit("  %-18s  %s" % (entry.get("slug"), ", ".join(people)))

    _emit()
    _emit("UNBOUND is the default. A channel in none of the above gets the "
          "product description and no client data at all.")
    return 0


def set_internal(channels):
    """Print the env line. This command does not edit `config/.env`."""
    bad = [c for c in channels if not looks_like_channel_id(c)]
    if bad:
        _emit("REFUSED: %s is not a channel id. Use the id (C...), never a "
              "#name - `slack.post` resolves no names and would post the "
              "string verbatim." % ", ".join(bad))
        return 1
    existing = set(slackscope._csv_env(slackscope.INTERNAL_CHANNELS_VAR))
    merged = sorted(existing | set(channels))
    _emit("Add this line to config/.env:")
    _emit()
    _emit("    %s=%s" % (slackscope.INTERNAL_CHANNELS_VAR, ",".join(merged)))
    _emit()
    _emit("Not written by this script: config/.env holds credentials, and a "
          "script that rewrites it is a script that can lose one.")
    return 0


def set_operator(user):
    if not looks_like_user_id(user):
        _emit("REFUSED: %r is not a Slack user id (U... or W...)." % user)
        return 1
    _emit("Add this line to config/.env:")
    _emit()
    _emit("    %s=%s" % (slackscope.OPERATOR_USER_VAR, user))
    _emit()
    _emit("This id is the ONLY one whose `approve <id>` approves a change "
          "request, and it also holds internal scope in a DM.")
    return 0


def bind_client(slug, channel, dry_run=True, actor="operator"):
    """Bind ONE channel to ONE workspace. Refuses everything ambiguous."""
    load_env()
    rows = ws.load()
    entry = ws.workspace(slug, rows)
    if entry is None:
        _emit("REFUSED: no workspace %r. Known: %s"
              % (slug, ", ".join(w.get("slug") for w in ws.workspaces(rows))))
        return 1
    if not looks_like_channel_id(channel):
        _emit("REFUSED: %r is not a channel id. Use the id (C...), never a "
              "#name." % channel)
        return 1

    if channel in slackscope.internal_channels():
        _emit("REFUSED: %s is an internal channel. A channel cannot be both "
              "the Resonate team's and a client's - that is the "
              "cross-client disclosure this module exists to prevent."
              % channel)
        return 1

    already = slackscope.client_channels(rows)
    if channel in already and already[channel] != slug:
        _emit("REFUSED: %s is already bound to %r. Unbind it first - a "
              "channel bound to two workspaces resolves to NEITHER, and "
              "silently taking it over would be worse."
              % (channel, already[channel]))
        return 1

    name = _channel_name(channel)
    _emit("WOULD BIND" if dry_run else "BINDING")
    _emit("  workspace   %s (%s)" % (slug, entry.get("name") or slug))
    _emit("  channel     %s%s" % (channel,
                                  " (#%s)" % name if name else
                                  "  [Slack could not name this channel]"))
    _emit("  policy key  %s" % slackscope.AGENT_CHANNEL_KEY)
    _emit()
    _emit("  After this the agent will answer in that channel AS %s: their "
          "campaigns, their accounts, their own leads by name, their sends "
          "and their replies. It will not name another client, anyone at "
          "Resonate, any provider, any cost or any incident." % slug)
    if dry_run:
        _emit()
        _emit("Nothing was written. Re-run without --dry-run to apply.")
        return 0

    ws.set_policy(slug, {slackscope.AGENT_CHANNEL_KEY: channel}, actor=actor)
    check = slackscope.resolve(channel=channel)
    _emit()
    _emit("WRITTEN. Readback: %r" % (check,))
    if not (check.is_client and check.workspace == slug):
        _emit("REFUSED AFTER WRITING: the readback does not agree. Nothing "
              "should be trusted about this binding until it does.")
        return 1
    return 0


def set_people(slug, workspace_users=(), internal_users=(), dry_run=True,
               actor="operator"):
    """Who in a channel is the CLIENT and who is Resonate.

    Both lists are written together and read back, because the split is the
    thing that decides what each person is told. A Slack id in neither list
    is scoped to nothing: an unknown DM is `unbound`, which is the safe
    failure, and in the bound channel the CHANNEL decides rather than the
    person - so a missing id costs a narrower DM and never a wider one.

    A bot is in neither list on purpose. `handle` already drops anything
    carrying `bot_id`, so a bot cannot ask a question; listing one would
    only make a reader think it could.
    """
    load_env()
    rows = ws.load()
    if ws.workspace(slug, rows) is None:
        _emit("REFUSED: no workspace %r" % slug)
        return 1
    bad = [u for u in tuple(workspace_users) + tuple(internal_users)
           if not looks_like_user_id(u)]
    if bad:
        _emit("REFUSED: not Slack user ids: %s" % ", ".join(bad))
        return 1
    both = sorted(set(workspace_users) & set(internal_users))
    if both:
        _emit("REFUSED: %s appear in BOTH lists. A person is a client's or "
              "Resonate's, and somebody in both would be scoped by whichever "
              "check ran first." % ", ".join(both))
        return 1

    updates = {}
    if workspace_users:
        updates[slackscope.WORKSPACE_USERS_KEY] = ",".join(workspace_users)
    if internal_users:
        updates[slackscope.INTERNAL_USERS_KEY] = ",".join(internal_users)
    _emit("WOULD WRITE" if dry_run else "WRITING")
    for key, value in updates.items():
        _emit("  %-26s %d id(s)" % (key, len(value.split(","))))
        for user in value.split(","):
            _emit("      %s" % user)
    if dry_run:
        _emit("\nNothing was written.")
        return 0
    ws.set_policy(slug, updates, actor=actor)
    policy = ws.policy(slug)
    _emit("\nWRITTEN. Readback from workspace policy:")
    for key in (slackscope.WORKSPACE_USERS_KEY,
                slackscope.INTERNAL_USERS_KEY):
        _emit("  %-26s %s" % (key, policy.get(key)))
    return 0


def unbind_client(slug, actor="operator"):
    load_env()
    if ws.workspace(slug) is None:
        _emit("REFUSED: no workspace %r" % slug)
        return 1
    ws.set_policy(slug, {slackscope.AGENT_CHANNEL_KEY: ""}, actor=actor)
    _emit("UNBOUND %s. Its channel now resolves UNBOUND." % slug)
    return 0


def _channel_name(channel):
    """Ask Slack what this channel is called. None if it cannot say.

    A read, through the same transport every other Slack call uses. It is
    best-effort on purpose: the binding is by id and does not depend on the
    name resolving, but printing the name is what lets a person spot that
    they have pasted the wrong id before they approve it.
    """
    try:
        from src.providers import request, key, ok, slack as slack_provider
        status, data = request(
            "GET", "https://slack.com/api/conversations.info?channel=%s"
            % channel,
            {"Authorization": "Bearer %s" % key(slack_provider.KEY_VAR)},
            None)
        if ok(status) and isinstance(data, dict) and data.get("ok"):
            return (data.get("channel") or {}).get("name")
    except Exception:                                           # noqa: BLE001
        return None
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--show", action="store_true",
                        help="print every binding and where it comes from")
    parser.add_argument("--internal", nargs="+", metavar="CHANNEL_ID",
                        help="channels the Resonate team owns")
    parser.add_argument("--operator", metavar="USER_ID",
                        help="the one Slack user who may approve a request")
    parser.add_argument("--client", metavar="SLUG",
                        help="bind a channel to this client workspace")
    parser.add_argument("--channel", metavar="CHANNEL_ID",
                        help="the channel id to bind (with --client)")
    parser.add_argument("--workspace-users", nargs="+", metavar="USER_ID",
                        help="Slack ids that are this CLIENT's own people")
    parser.add_argument("--internal-users", nargs="+", metavar="USER_ID",
                        help="Slack ids on the Resonate team")
    parser.add_argument("--unbind", metavar="SLUG",
                        help="remove a client workspace's agent channel")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be written, write nothing")
    args = parser.parse_args(argv)

    if args.internal:
        return set_internal(args.internal)
    if args.operator:
        return set_operator(args.operator)
    if args.unbind:
        return unbind_client(args.unbind)
    if args.client:
        if args.workspace_users or args.internal_users:
            code = set_people(args.client,
                              args.workspace_users or (),
                              args.internal_users or (),
                              dry_run=args.dry_run)
            if code or not args.channel:
                return code
            _emit("")
        if not args.channel:
            _emit("REFUSED: --client needs --channel, "
                  "--workspace-users or --internal-users")
            return 1
        return bind_client(args.client, args.channel, dry_run=args.dry_run)
    return show()


if __name__ == "__main__":
    raise SystemExit(main())
