# Slack Notifications

Two levels, and they must never be mixed.

Read this before changing `src/notify.py`, `src/providers/slack.py`, or
anything on the web app's `/admin/slack` and `/notifications` screens.

**Nothing in this build posts to Slack.** `SLACK_LIVE` is unset, `slack.post`
raises `SlackPostingNotEnabled`, and every notification this system has
produced is stored with status `planned` or `unconfigured`. Turning it on is a
separate, explicitly authorised exercise.

---

## 1. The two levels

### The global operations channel

One room, for the people who run the machine. Configured with the
`SLACK_OPS_CHANNEL` environment variable, so it is a deployment setting rather
than anybody's client config.

It carries: campaign approval requests, QA failures, provider health and
credit warnings, failed jobs, unmatched replies, sender capacity warnings,
workspace configuration problems, MX anomalies, and the fact that a report was
generated.

Twenty-one of the twenty-seven event types route here.

### The per-workspace channel

One room per client, and it is the client's room. Configured with the
`slack.workspace_channel` workspace policy - set on that workspace's settings
page, stored in `workspaces.jsonl`, and never inferred from the workspace's
name, slug, or anything else.

It carries three things: positive replies, campaign milestones, and the note
that a report is ready. That is the complete list, and it is a table rather
than a rule, so adding a fourth is a visible edit.

### Neither

`neutral_reply`, `negative_reply` and `unsubscribe` route to `NOWHERE`, on
purpose and by name in the routing table. A client whose Slack channel fills
with every "not interested" stops reading the channel, and then stops seeing
the positive replies too. Those three live in the Web App, where somebody
looks at them when they are looking for them.

---

## 2. The properties this is built to

### There is no fallback

`notify.workspace_channel(slug)` reads one workspace's own policy and returns
None if it has none. There is no code path that could return another
workspace's channel: not a disabled one, an absent one. A workspace with no
mapping produces a notification with status `unconfigured` that posts nowhere,
and `/admin/slack` names every such workspace at the top of the page.

A positive reply in the wrong client's room is the worst thing this system
could do with Slack. An alert that nobody received is a configuration problem
somebody fixes in a minute; an alert in the wrong room cannot be taken back.

The same reasoning governs `notify.workspace_for_client`. A record carries a
client, not a workspace, and the two are the same string in every current
deployment - which is exactly why it is worth not relying on. That function
returns a slug only when **exactly one** workspace claims the client. Two
matches returns None, and the alert goes nowhere.

### One router, not two

Before the workspace mapping existed, a positive reply's channel came from
`slack.positive_replies_channel` in the client YAML. Both mechanisms resolving
a channel would be two routers with two answers, and the one that wins would
be whichever caller was written last.

So the workspace mapping wins outright. `slack.channel_for` takes a `channel`
argument that is used verbatim when given - **including when it is None**,
which is what the `slack.UNSET` sentinel exists to distinguish. `channel=None`
has to be able to mean "this workspace has no room, so nothing is posted",
which is a different statement from "nobody told me, look it up".

`tests/test_notify_wiring.py::OneRouterNotTwo` pins both halves.

### A client channel is client-safe by construction

`notify._scrub` filters the fields that reach a workspace payload against
`WORKSPACE_SAFE_FIELDS`, an allowlist, and refuses any field whose **name**
matches `FORBIDDEN` (token, secret, password, api_key, bearer, authorization,
signing_secret, webhook_url).

It checks names, never values. An earlier version grepped the serialised
payload, which would have refused to deliver a prospect's reply saying "we
would need to sort out authorization first". A prospect's own words are not a
credential scan, and `AProspectsOwnWordsAreNotAKeywordScan` in
`tests/test_notify.py` is what keeps that true.

What never reaches a client's room: provider names, API keys, raw payloads,
internal QA notes, credit exposure, another client's anything, and the name of
the global operations channel.

### The previous outreach is the outreach that happened

The "Previous outreach" block in a positive-reply alert is built from
`touch.confirmed_touches`, the same gate that decides whether a *message* may
claim a touch occurred. `push_marked`, `email_delivered` and
`linkedin_connected` count; `push_prepared` explicitly does not.

So a planned step cannot appear in it, which means a team is never told their
multichannel sequence converted when only one channel ever ran. Never
fabricate outreach history: there is no code path in `notify.positive_reply`
that formats a step the engine has not confirmed.

### Slack cannot break outbound state

`notify.notify()` cannot raise. It catches everything, records the failure as
a notification row with status `failed`, and returns.

That matters because of where it is called from. In `replies.apply` the
announcement is **last** - after the company was paused by `events.apply` and
after the classification was recorded. A notification layer that runs first is
a notification layer that can lose a pause. `jobs._announce_failure` returns
nothing at all, so no caller can start depending on it.

`tests/test_notify_wiring.py` asserts the second half of every call site: the
job still ended failed, the pause is still in place, the approval request
still succeeded - with no channel configured.

### Idempotency

`notification_id` is a sha256 over the event type, the workspace and the
sorted identifiers. `plan()` returns the existing row unchanged rather than
appending a second one.

The check happens **inside** `notify.transaction()`, and only there. An
earlier version also checked before building the payload. Each check alone
kept the behaviour identical, which sounds like defence in depth and is the
opposite: neither could be removed by a mutation and caught by a test, so
neither was verified. The one that survives is the one that holds when two
writers race between reading the file and appending to it, which is what
`tests/test_notify_concurrency.py` exercises.

The two parameters of `notification_id` are positional-only and the
identifiers are nested under their own key, because an identifier legibly
named `workspace` or `type` is a reasonable thing for a caller to pass -
and before that it either raised a TypeError or, worse, overwrote the
workspace in the material and made two different workspaces' notifications
collide on one id.

For an approval request the fingerprint is one of those identifiers, so
re-requesting approval for an unchanged campaign is one notification, and
re-requesting it for a *changed* campaign is correctly a new one - because it
is a new ask.

---

## 3. Where the code is

| File | What it owns |
| --- | --- |
| `src/notify.py` | The router: the routing table, the scrub, the id, the store, the builders, `render`. |
| `src/providers/slack.py` | The transport and the legacy per-client payloads. `post` refuses. |
| `src/replies.py` | `_announce` - a positive reply reaches its workspace's room. |
| `src/inbound.py` | An unmatched reply reaches the operations channel. |
| `src/jobs.py` | `_announce_failure` - an aborted job reaches the operations channel. |
| `src/orchestrator.py` | The approval request, and the one-router rule for positive replies. |
| `src/web/api.py` | `slack_overview`, `workspace_slack`, `notification_history`, `announce_report`. |
| `src/web/pages.py` | `slack_admin`, `slack_notifications`, `slack_demo`, `slack_status_panel`. |
| `src/web/demoslack.py` | Eight fictional scenarios across three workspaces. |

State lives in `work/notifications.jsonl`, reached only through
`src/notify.py`, and moved together with the other state files by
`store.use_directory`.

---

## 4. The screens

**`/admin/slack`** - super admin only, guarded by `_require_super_admin`
rather than by a workspace permission, because no workspace permission can
express "may read every workspace at once". It shows the operations channel,
every workspace's mapping, the workspaces with no mapping, channel collisions
(reported, never resolved - two workspaces in one room may be deliberate, and
it is also what a copied setting looks like), and the full routing table.

**`/notifications`** - scoped to the session's workspace and gated on
`operations.view`. `?scope=all` widens it only for a super admin: a parameter
that widens a scope on its own is not a parameter, it is the vulnerability.

**The workspace dashboard's Slack panel** - a client-facing role is told which
room its own replies land in, and nothing about the operations channel. Where
credit exposure is discussed is not part of what a client bought.

**The demo scenario board** - eight fictional alerts and the channel each
would go to, rendered only in the unscoped super-admin view. The board names
every workspace's room by design, which makes it a cross-tenant read, and a
demo is not a reason to widen a scope.

---

## 5. Approving from Slack

An approval action posted from Slack goes through `orchestrator.decide`, the
same function the web app calls. Nothing about arriving from Slack makes it
trusted:

- the fingerprint travels with the request, and a stale one is refused
- the Slack user is mapped to a role, and the role must carry the permission
- QA, eligibility, verification, MX and suppression are all still checked
- the decision is idempotent on the interaction id

Approving is a decision about a campaign, not about a message.

---

## 6. Turning it on

Not in this build. When it is authorised:

1. Set `SLACK_OPS_CHANNEL` and a bot token.
2. Map every workspace's `slack.workspace_channel`, and check `/admin/slack`
   reports no unconfigured workspaces and no collisions you did not intend.
3. Set `SLACK_LIVE`.
4. Retry the planned notifications, or let the next real event produce one.

Step 2 before step 3, always. A live build with an unmapped workspace posts
nothing for that client, which is safe but silent, and silence is what this
architecture is worst at making visible on its own.
