# Slack activation — exactly where each value goes

**STATUS 2026-09-21T11:3xZ: LIVE.** The operator set all three variables and
`scripts/slack_smoke.py` posted to `#resonate-notifications` (C0C34GCAR27),
Slack returning `ts 1789990679.422989`. The ops channel below is the NEW one;
the earlier `#resonate-notifs` / C0AQB4KB9TM is superseded everywhere.
`scripts/slack_replay_today.py` remains UNRUN by instruction.

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
    SLACK_OPS_CHANNEL=C0C34GCAR27

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

**ANSWERED 2026-09-21, and the refusal to guess was correct.** ISSUE-005 in
`docs/state/PROBLEM-REGISTER.md` already recorded both ids, and **BOTH ARE
PRODUCTIVE**: `#productive-resonate-outbound` (C0ADUMGQX8S) and
`#replies-productive` (C0BFUF4JRK9). Neither belongs to `contactout`. Pairing
them one-to-one against the two workspaces that carry a
`slack.workspace_channel` would therefore have put Productive's outbound
channel into ContactOut's policy — the exact cross-client leak this module is
built to prevent.

So the remaining decision is an operator's, not a lookup: `productive` has two
channels for two purposes, and which is `slack.workspace_channel` (replies)
versus `slack.approvals_channel` is a choice. `#replies-productive` is the
obvious reading for the reply channel, but it is not written until you say so.
`contactout` still has no id at all and keeps its name.

Set them with:

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

---

# Addendum — the two follow-up questions, 2026-09-21T10:3xZ

## A. The adapter does NOT resolve names. Use ids.

`slack.post` builds `{"channel": channel, "text": ...}` and passes it straight
to `chat.postMessage`. There is no `conversations.list` call anywhere in
`src/providers/slack.py`, so whatever string it is given is what Slack
receives. Slack still accepts a `#name` for a PUBLIC channel, but it is
deprecated, it does not work for a private channel, and it breaks silently the
day somebody renames the channel. **An id never moves, so both policies should
carry ids.**

**I still have not mapped them, because the mapping is derivable and a guess
is unsafe.** `scripts/slack_map_channels.py` resolves it properly: it calls
`conversations.info` on `C0ADUMGQX8S` and `C0BFUF4JRK9`, reads each channel's
real name, and pairs it against the name already in each workspace's policy
(`#client-productive-replies`, `#client-contactout-replies`). If the two names
do not pair one-to-one it refuses and writes nothing.

    py -3 scripts/slack_map_channels.py            # show the mapping
    py -3 scripts/slack_map_channels.py --apply    # write both policies

It needs only `SLACK_BOT_TOKEN` and no posting scope — it reads. So the
mapping resolves itself the moment the token from §2 exists, and nobody has to
remember which id was which.

## B. The 15 are NOT from 327/328/352. They are HeyReach, and they are the
## client's — but the routing question is real anyway.

Every one of the 15 carries `provider: heyreach`, `status: unmatched`, `why:
"no record for this event"`. None carries a campaign id, a workspace or a
lead; the only identifier is a `provider_event_id` of the form
`heyreach:2-<base64 conversation id>:<timestamp>`. So they are not EmailBison
and 327/328/352 are not involved.

**They cannot be ours, and that is provable rather than likely.** Our only
live HeyReach campaign is 605732, and it has `sent = 0` on every read today —
zero messages, zero connection requests. A reply event cannot originate from a
campaign that has never sent anything. We own 4 of 86 HeyReach campaigns, the
API key is workspace-wide, and the reply watcher reports
`events_inspected: 21, ambiguous_identities: 21, new_replies_ingested: 0`. We
are being shown the client's inbox traffic and correctly failing to attribute
it.

Rate: 15 between 05:15Z and 09:37Z, about 3.4/hour, so roughly 80/day if it
holds. That is an ops channel nobody will read by Wednesday.

**PROPOSED, NOT APPLIED. Nothing is sent until you decide.** Neither option
touches the NOWHERE routes for `negative_reply` / `unsubscribe` /
`neutral_reply`.

**Option 1 — fix the attribution, which is the real defect.** An event whose
conversation belongs to a LinkedIn seat we do not operate is not ours to
review, and raising `action_required` for it is a false positive rather than a
volume problem. The check is cheap: 605732's seat is known, and an event from
any other seat is the client's. This makes the 15 disappear because they
should never have been raised, and a genuine unmatched event on OUR seat still
pages immediately. Costs one bounded engineering task.

**Option 2 — batch them, if you want the visibility kept.** `src/digest.py`
already exists and already records a digest as a notification, so the change
is to route `unmatched_reply_needs_review` into it rather than to post one
message each: one summary, a count and the seats involved, on whatever
interval you want. Cheaper to build, but it keeps paging about somebody else's
inbox, just more quietly.

**My recommendation is Option 1, with Option 2 on top only if you want a
daily count of client traffic.** Option 2 alone treats a correctness bug as a
noise problem, and the 80/day is a symptom of the attribution gap rather than
the thing to manage.

Until you decide: `scripts/slack_replay_today.py` still reports 15 and still
sends nothing without `--live`.
