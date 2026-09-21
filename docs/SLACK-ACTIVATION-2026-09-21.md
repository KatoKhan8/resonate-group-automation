# Slack activation — exactly where each value goes

Nothing here contains a secret. The operator sets the values; everything else
is prepared and tested.

## 1. The file

    C:\Users\Zvonimir\Desktop\resonate-group-automation\config\.env

`src/providers/__init__.py` reads it with `os.environ.setdefault`, so **a real
OS environment variable always wins over this file**. Either works; if a value
is set in both and they disagree, the OS one is what the process sees. If you
prefer the OS store, set the same three names with `setx` and the file can
stay untouched.

## 2. The three lines to paste — ops channel already filled in

Append to `config/.env`, replacing only the token:

    SLACK_BOT_TOKEN=xoxb-REPLACE-WITH-THE-BOT-TOKEN
    SLACK_LIVE=1
    SLACK_OPS_CHANNEL=C0AQB4KB9TM

`SLACK_LIVE` is a second switch on purpose: a token alone never enables
posting, so a token that leaks into an environment cannot start sending
messages on its own. Accepted truthy values are `1`, `true`, `yes`, `on`.

A fourth is declared and is worth setting at the same time, though nothing in
the outbound path needs it:

    SLACK_SIGNING_SECRET=REPLACE-WITH-THE-SIGNING-SECRET

It verifies INBOUND Slack interactions (the approve/reject buttons). Without
it every inbound interaction is refused rather than trusted, which is the
correct default — but it means the buttons do nothing until it is set.

## 3. The two per-workspace channels are NOT environment variables

This is the one place the instruction and the codebase disagree, and the
codebase is right, so the values go somewhere else rather than into `.env`.

`src/config.py` on `SLACK_OPS_CHANNEL`:

> the one global operations channel. Per-workspace channels are workspace
> policies, never environment variables

The reason is in `notify.workspace_channel`: it reads one workspace's own
policy and nothing else, so **there is no code path that can return a
different client's channel** — not a disabled fallback, an absent one. An
environment variable is process-global and would reintroduce exactly the
cross-client leak that design prevents. A `SLACK_WORKSPACE_CHANNEL` in `.env`
would be read by nothing.

They are policy key `slack.workspace_channel` on each workspace. Current
values are channel NAMES, and both need replacing with the ids:

    workspace `productive`   slack.workspace_channel = '#client-productive-replies'
    workspace `contactout`   slack.workspace_channel = '#client-contactout-replies'

**WHICH ID BELONGS TO WHICH WORKSPACE IS NOT RECORDED ANYWHERE AND I AM NOT
GUESSING IT.** `C0ADUMGQX8S` and `C0BFUF4JRK9` were given without a mapping,
and a wrong guess posts one client's reply traffic into the other client's
channel — the precise failure this module is built to make impossible. Tell me
which is which, or set them yourself:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import workspaces as ws;ws.set_policy('productive', {'slack.workspace_channel': 'C0XXXXXXXXX'}, actor='operator')"
    py -3 -c "import sys;sys.path.insert(0,'.');from src import workspaces as ws;ws.set_policy('contactout', {'slack.workspace_channel': 'C0XXXXXXXXX'}, actor='operator')"

## 4. Verify, in this order

    py -3 scripts/slack_smoke.py --dry-run   # payload and channel, sends nothing
    py -3 scripts/slack_smoke.py             # ONE message, prints the `ts`

The smoke test refuses with a named list while any variable is unset, and it
posts to the ops channel only. It reads `ts` off the postMessage response —
that is the receipt, returned only for a message Slack accepted. The three
failures that actually happen are `channel_not_found`, `not_in_channel` (the
bot has to be invited: `/invite @<bot>` in the channel) and `missing_scope`
(the token needs `chat:write`); each is named explicitly in the output.

## 5. Then replay today's queue, and only today's

    py -3 scripts/slack_replay_today.py          # dry run, the default
    py -3 scripts/slack_replay_today.py --live   # posts

Measured 2026-09-21T10:1xZ, with the ops channel set:

    notification store   236 rows
    on or after today    15   -> WOULD DELIVER 15
    older, untouched     221

All 15 are `unmatched_reply_needs_review`, severity `action_required`, routed
`global`. The 221 older rows are left exactly as they are — arming Slack and
replaying the whole store would post 221 messages in one burst, and a muted
ops channel is worse than no ops channel.

The rows currently read `channel: None` because they were built while the
variable was unset, and `notify.deliver` returns early on `unconfigured`
without reaching the transport. So the replay re-asks `notify.destination_for`
for the routing decision now that the variable exists and writes it back
before delivering. If a type still routes nowhere, the row stays undelivered
and says why.

## 6. Noted once, as instructed, and not touched

`negative_reply`, `unsubscribe` and `neutral_reply` all route `('nowhere',
'info')` in `notify.ROUTES`. Verified today, unchanged, and left alone —
whether those should reach Slack is a separate operator decision.
