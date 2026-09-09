# Live Validation Plan

Everything this system cannot prove without touching something real, ordered
from cheapest and most reversible to most expensive and least reversible.

**None of it has been performed.** This document is the plan, not a record.
Nothing below has been executed: zero paid provider calls, zero Slack posts,
zero provider mutations, zero emails, zero LinkedIn actions.

Each step is a separate authorisation. Passing step 3 does not authorise step
4. Work down the list; stop at the first failure and fix it before continuing,
because every later step assumes the earlier ones held.

---

## How to read an entry

| Field | Meaning |
| --- | --- |
| **What** | The exact thing being proven |
| **Why offline cannot** | What a recorded contract or a fixture genuinely cannot tell us |
| **Risk** | What goes wrong if it fails, and who notices |
| **Needs** | Credentials, configuration, and any human standing by |
| **Procedure** | The command or click path, and the assertion |
| **Cost** | Credits, money, or provider-side objects created |
| **Rollback** | How to undo it, or why it cannot be undone |

---

## Stage 0 — no external contact

These need no credentials and no network. Run them first; they are how you
know the build under test is the build you think it is.

### 0.1 Full offline suite

- **What** — every test, with the socket layer blocked.
- **Why offline cannot** — nothing; this *is* the offline proof.
- **Risk** — none.
- **Needs** — nothing.
- **Procedure** — `py -m tests.offline`. Expect OK and the line
  "nothing reached off this machine".
- **Cost** — none.
- **Rollback** — n/a.

### 0.2 Mutation audit

- **What** — that the safety guards are load-bearing.
- **Why offline cannot** — nothing.
- **Risk** — a guard nobody tests is a guard that can be deleted.
- **Needs** — nothing.
- **Procedure** — `py tools/mutation_audit.py`. Every mutation must be
  reported caught.
- **Cost** — a few minutes per mutation.
- **Rollback** — the tool restores each file in a `finally`. Verify
  `git status` is clean afterwards before committing anything.

---

## Stage 1 — read-only, free

The first contact with the outside world. Every call here is a read that costs
nothing and creates nothing.

### 1.1 Provider reachability

- **What** — that each configured provider answers at all, on the cheapest
  free call it offers.
- **Why offline cannot** — a recorded contract proves the parser handles a
  response we already have. It cannot prove the endpoint still exists, that
  the key is valid, or that the account is in good standing.
- **Risk** — low. A failure means a misconfiguration, discovered before it
  costs anything.
- **Needs** — the provider keys in `config/.env`. No `SLACK_LIVE`.
- **Procedure** — `py -m src.check`. Expect `ok` per configured provider,
  `SKIP` for Reoon and Deliverable (whose only endpoints cost money).
- **Cost** — zero. This is why it is first.
- **Rollback** — nothing was changed.

### 1.2 ContactOut people-count

- **What** — that a company search returns a count in the shape the qualifier
  expects.
- **Why offline cannot** — the cassette was recorded once; the API's paging
  and filter semantics may have moved.
- **Risk** — low.
- **Needs** — `CONTACTOUT_TOKEN`.
- **Procedure** — a single people-count for one known company. Assert the
  count is an integer and the response carries no person records.
- **Cost** — zero. People-count is free; this is the only person-adjacent
  call that is.
- **Rollback** — nothing was changed.

---

## Stage 2 — one credit, deliberately

The first spend. One credit, one address, one person watching.

### 2.1 Deliverable wire contract — **the top blocker**

- **What** — the *shape* of a Deliverable verification response.
- **Why offline cannot** — this is the one provider whose response is
  undocumented. The endpoints and auth are documented and are already the
  adapter's defaults; the body that comes back has never been read. Everything
  downstream of it - the normaliser, the valid/invalid/catch-all mapping, the
  disagreement rule - is written against a shape nobody has confirmed.
- **Risk** — **the highest-consequence unknown in the system.** If the
  normaliser misreads the response, an invalid address could be classified
  valid, and a contact that should have been held becomes sendable. That is
  the one failure this architecture is built to make impossible, and it is
  currently guarded by a refusal rather than by knowledge.
- **Needs** — `DELIVERABLE_KEY`, and one address whose true status is known
  independently (use an address you control: one real, one known-invalid).
- **Procedure** —
  ```
  py -m src.validate --provider deliverable --live-validation --max-credits 1
  ```
  Read the raw body. Check the normaliser against it by hand. Only then set
  `DELIVERABLE_RESULT_SHAPE=confirmed`.
- **Cost** — one verification credit. Possibly two if you check a known-bad
  address as well, which is worth it: a normaliser that maps everything to
  "valid" passes a one-address test.
- **Rollback** — unset `DELIVERABLE_RESULT_SHAPE`. `verify()` returns to
  refusing. Nothing was mutated provider-side.

### 2.2 Reoon escalation

- **What** — that the escalation verifier answers in the recorded shape.
- **Why offline cannot** — same reasoning, weaker: Reoon's contract is
  documented and the cassette matches it, so this confirms rather than
  discovers.
- **Risk** — moderate. Reoon is only reached on disagreement, so a break here
  holds contacts rather than releasing them - which fails safe.
- **Needs** — `REOON_KEY`.
- **Procedure** — `py -m src.check --live-reoon`.
- **Cost** — one Reoon credit.
- **Rollback** — nothing was changed.

---

## Stage 3 — Slack, read then write

Slack is the first thing that writes somewhere people can see.

### 3.1 Slack auth and channel resolution

- **What** — that the bot token is valid and can see the configured channels.
- **Why offline cannot** — channel ids are configuration; nothing offline can
  confirm the bot is a member of the room.
- **Risk** — low. A read.
- **Needs** — `SLACK_BOT_TOKEN`, `SLACK_OPS_CHANNEL`, and each workspace's
  `slack.workspace_channel` policy set. **Not** `SLACK_LIVE`.
- **Procedure** — `auth.test`, then `conversations.info` for the operations
  channel and each mapped workspace channel. Check `/admin/slack` reports no
  unconfigured workspaces and no collision you did not intend.
- **Cost** — none.
- **Rollback** — nothing was changed.

### 3.2 First real Slack post — **to a throwaway channel**

- **What** — that a rendered notification posts and looks right.
- **Why offline cannot** — the payload is exercised offline; how Slack
  *renders* it is not.
- **Risk** — moderate, and asymmetric. A message in the wrong room cannot be
  taken back. Post to a channel created for this test, not to a client's.
- **Needs** — `SLACK_LIVE=1`, and `SLACK_OPS_CHANNEL` **temporarily** pointed
  at a throwaway channel.
- **Procedure** — take one existing planned notification and
  `notify.deliver(<id>)`. Read the message. Then unset `SLACK_LIVE`.
- **Cost** — none.
- **Rollback** — delete the message. Set the operations channel back.

### 3.3 Workspace channel isolation, live

- **What** — that a positive reply in one workspace reaches that workspace's
  room and no other.
- **Why offline cannot** — the router is proven offline. What is not proven is
  that the channel *ids in configuration* are the rooms somebody thinks they
  are.
- **Risk** — **the highest client-facing risk in this document.** A positive
  reply in the wrong client's channel is a disclosure that cannot be undone.
- **Needs** — two throwaway channels standing in for two workspaces.
- **Procedure** — map both workspaces to throwaway channels. Ingest a
  fictional positive reply into each. Confirm each message landed in exactly
  one room. **Only then** map the real client channels, and re-read
  `/admin/slack` to confirm the mapping.
- **Cost** — none.
- **Rollback** — delete the messages; re-map.

### 3.4 Slack interaction callback

- **What** — that an approval pressed in Slack is verified and applied.
- **Why offline cannot** — signature verification is tested against
  constructed payloads. Slack's actual signing, timestamps and retry
  behaviour are not.
- **Risk** — high. A callback endpoint that accepts an unsigned payload is an
  approval anybody can forge.
- **Needs** — `SLACK_SIGNING_SECRET`, and a publicly reachable callback URL,
  which means this cannot happen before deployment.
- **Procedure** — press Approve on a test campaign. Assert: the signature
  verified; a replayed request with an old timestamp is refused; a payload
  with a stale fingerprint is refused; the Slack user maps to a role that
  carries `campaign.approve`; a second press is idempotent.
- **Cost** — none.
- **Rollback** — the approval is reversible in the Web App. The endpoint can
  be disabled by unsetting the signing secret, which makes it refuse
  everything.

---

## Stage 4 — outbound providers, one object at a time

Everything here creates something on a provider's side.

### 4.1 EmailBison read

- **What** — that campaigns and accounts list in the expected shape.
- **Why offline cannot** — cassette age.
- **Risk** — low. A read.
- **Needs** — `BISON_KEY`, `BISON_BASE`.
- **Cost** — none.
- **Rollback** — nothing was changed.

### 4.2 EmailBison controlled mutation

- **What** — that a lead pushes with our identifiers attached, and comes back
  carrying them.
- **Why offline cannot** — the round trip is the point. Custom fields are
  where identifiers get silently dropped, and a dropped identifier means a
  reply nobody can attribute.
- **Risk** — high. This writes to a sending platform. Use a campaign created
  for this test, containing one contact you control.
- **Needs** — `BISON_KEY`, a throwaway campaign, an address you own.
- **Procedure** — push one contact. Read it back. Assert `record_id` and
  `contact_key` survived. **Do not enable sending on the campaign.**
- **Cost** — one lead on one throwaway campaign.
- **Rollback** — delete the lead and the campaign.

### 4.3 HeyReach custom field round-trip

- **What** — the same property, for LinkedIn.
- **Why offline cannot** — same reasoning. HeyReach's custom-field handling is
  the specific unknown.
- **Risk** — high, and higher than EmailBison: LinkedIn actions are harder to
  reverse and are rate-limited by a third party who does not answer support
  tickets.
- **Needs** — `HEYREACH_KEY`, a throwaway list, a profile you control.
- **Procedure** — add one lead to a list with custom fields set. Read back.
  Assert the identifiers survived. **Do not start the sequence.**
- **Cost** — one lead on one throwaway list.
- **Rollback** — delete the lead and the list.

### 4.4 Reply ingestion, live

- **What** — that a real provider webhook or poll produces a neutral event
  this system matches to the right contact.
- **Why offline cannot** — the adapters are tested against recorded payloads.
  Whether the *real* payload carries the identifiers we pushed in 4.2 is the
  open question, and it is the one that decides whether replies can be
  attributed at all.
- **Risk** — high. An unmatched reply means somebody answered and nobody was
  told, and the company kept being sequenced.
- **Needs** — everything from 4.2, plus a reply sent by hand from the address
  you control.
- **Procedure** — reply to the pushed lead. Ingest. Assert: the event matched;
  the company paused; the classification recorded; the notification routed to
  the right workspace channel.
- **Cost** — none beyond 4.2.
- **Rollback** — the pause is reversible in the Web App.

---

## Stage 5 — infrastructure

Not provider work, but equally unprovable offline. All of it depends on
DEPLOYMENT-PLAN.md having been executed.

### 5.1 Production authentication

- **What** — that a real identity provider authenticates, and that demo
  sign-in is refused.
- **Why offline cannot** — this build has no production authentication. It is
  a deployment blocker, not a validation.
- **Risk** — total. Demo sign-in in production is unauthenticated access to
  every workspace.
- **Procedure** — with `APP_MODE=production`, assert the seeded-user sign-in
  form is absent and posting to it is refused.

### 5.2 Production database

- **What** — that state survives a restart and two processes can write.
- **Why offline cannot** — this build stores JSONL and takes a file lock. It
  is single-process by construction; see `DATABASE-MIGRATION.md`.
- **Risk** — high. Two web processes on a file store will corrupt it.
- **Procedure** — the migration's own acceptance tests.

### 5.3 Worker and scheduler

- **What** — that jobs run outside the request process and that cadence
  timing advances.
- **Why offline cannot** — neither exists yet. `/admin/health` reports both as
  live-validation-required, which is accurate.

### 5.4 Domain and TLS

- **What** — `app.resonategroup.co` resolves, serves a valid certificate, and
  the marketing site at `resonategroup.co` is untouched.
- **Risk** — moderate; a DNS mistake takes the marketing site down.
- **Procedure** — see DEPLOYMENT-PLAN.md §DNS. Add the app record only; do not
  touch the apex.

---

## What must never be validated by trying it

Some things are only provable by causing the harm they prevent. They stay
proven by construction and by the mutation audit, and no live test is
authorised for any of them:

- that an unverified address is never emailed
- that a planned touch is never described as sent
- that an MX-blocked contact never becomes email-eligible
- that one workspace never sees another's data
- that a stale approval never launches changed content

A "test" of any of these is the incident.
