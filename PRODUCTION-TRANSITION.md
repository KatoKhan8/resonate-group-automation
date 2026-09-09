# Production transition

What has actually been proved against real counterparts, what that
revealed, and the one finding that changes the shape of a first pilot.

Written 2026-09-02. `RELEASE-CANDIDATE.md` holds the verdicts;
`PRODUCTION-AUTH.md` holds the authentication mechanism. This document is
the record of the first time this build spoke to anything real.

---

## 1. Live provider reads — executed

Every call below was classified before it was made. Only READ_ONLY calls
that consume no credits were executed. **No write was made to any
provider, and no credit was spent.**

The tools are the repository's own: `python -m src.check` pings each
provider with the cheapest call it offers and refuses to spend to turn one
green, and `python -m src.validate` prices a run before making it.

| provider | call | result |
| --- | --- | --- |
| ContactOut | `GET /stats`, and `people-count` for a domain | **200.** Quota visible, 0 used this period. The `people-count` trim **matches** the live response - four keys the adapter deliberately ignores, and nothing it expected was missing |
| AI Ark | `tools/list` | **200**, 11 tools |
| EmailBison | `GET /campaigns` | **200**, 15 campaigns. The `{data, links, meta}` envelope and Laravel-style pagination keys are confirmed live |
| HeyReach | `GET /auth/CheckApiKey`, `POST /campaign/GetAll` | **200.** 76 campaigns, paging confirmed at `limit=100` |
| Apify | `GET /users/me` | **200** |
| Reoon | none | **SKIP, correctly.** Its only endpoint verifies an address and costs a credit |
| Deliverable | none | **SKIP.** No account or quota endpoint is documented, so the key cannot be exercised without spending a verification credit. **Its response shape is still unread, and it remains the top provider blocker** |
| Slack | none | No token configured. Nothing to read, and nothing was posted |

**One transient observed and worth recording:** `POST /campaign/GetAll`
timed out once at 25s and answered in 1.4s on the retry. The contract is
fine; the timeout is real and a poller will meet it.

**One adapter defect found by reading the real thing:**
`heyreach.campaigns()` returns `(items, total)`, which is correct and
documented in its own docstring - but it is easy to read as a
`(status, data)` pair, and the first attempt to consume it here did
exactly that. Nothing in the shipped code makes that mistake.

---

## 2. What the reads revealed, and why it changes the pilot

This is the finding that matters more than any of the contracts.

**Productive already has a large live LinkedIn outreach operation
running.** Not planned. Running, today, through HeyReach:

| | |
| --- | --- |
| Campaigns | 76 total; **42 in progress**, 31 paused, 3 draft |
| Named `PRODUCTIVE*` | **51** |
| Distinct LinkedIn sender accounts | **39** |
| Organisation units | 1 |
| Prospects currently in progress | **~160,000** |

Email is the opposite. EmailBison holds 15 campaigns - 6 draft, 7 paused,
2 completed - and **nothing sending**.

### What follows from that

**The first pilot is not a greenfield.** Every plan in this repository -
`PILOT-PLAN.md`, `RELEASE-CANDIDATE.md` §9 - was written for a workspace
with no existing outbound. That assumption is now known to be false, and
the pilot design has to change before it is run rather than after.

**Engagement hygiene stops being a nicety and becomes the gating
control.** `ENGAGEMENT-HYGIENE.md` describes checking a new list against
canonical engagement state before anybody spends a credit on it. Canonical
state in this build knows nothing about those 160,000 people. A Resonate
campaign built today could contact somebody who is mid-sequence in a live
HeyReach campaign, from a different sender, saying something unrelated -
and the prospect would experience one company approaching them twice.

That is the single most likely way a first pilot does visible damage, and
it is now a **P1**, recorded in `PRODUCT-GAPS.md` §15.

**Capacity is real and knowable, and it is not what anyone assumed.**
LinkedIn is the constrained-but-abundant channel here - 39 sender accounts
- while email capacity is idle. Any capacity engine built against a
guess of "one or two senders" would have been built against the wrong
shape. The authoritative source is the provider: `campaignAccountIds` on
each campaign is the sender inventory, and it is discovered rather than
configured.

---

## 3. What was deliberately not done

| | why |
| --- | --- |
| Any provider write | Not authorised. Nothing was created, updated, paused or tagged |
| Reoon verification | Costs a credit. `--live-reoon` exists and was not passed |
| Deliverable verification | Costs a credit, and is the one contract still unread |
| ContactOut enrichment | `decision-makers`, `people-search` and `company-information-from-domain` cost 16 credits together. Only the free `people-count` was run |
| Apify actor runs | A run costs money. Only `GET /users/me` was called |
| Any Slack message | Not authorised, and no token is configured |
| Endpoint discovery by guessing | An undocumented path is UNKNOWN, and UNKNOWN is not executed. This is why the inbox and LinkedIn-account inventories below are marked unsupported rather than probed |

---

## 4. Workspace infrastructure intelligence: what the contract supports

The mission for this phase was to model each workspace's real outbound
infrastructure. What the **confirmed** provider contracts expose:

| wanted | EmailBison | HeyReach |
| --- | --- | --- |
| Campaign inventory | **yes**, `GET /campaigns` | **yes**, `POST /campaign/GetAll` |
| Sender accounts | not in the confirmed contract | **derivable**: `campaignAccountIds` per campaign, 39 distinct |
| Inbox inventory | **no confirmed route** | n/a |
| Per-sender status / health | **no confirmed route** | not exposed |
| Configured sending limits | **no confirmed route** | not exposed |
| Connection status | n/a | **explicitly unavailable** - `heyreach.CONNECTION_STATUS_AVAILABLE = False`, and the module says why |
| Progress per campaign | not read | **yes**, `progressStats` |

So a capacity engine can be built on authoritative campaign and
sender-account data, and **cannot** currently be built on authoritative
inbox counts or configured limits. Those are `UNKNOWN`, and `UNKNOWN` is a
real answer here - inferring an inbox count from campaign membership would
be exactly the invention this repository refuses everywhere else.

**Not built in this pass.** The capacity engine, its consumption by
strategy, and the operator screen are a real build, and the right thing
was to discover the true shape first rather than build against a guessed
one. The shape is now known and recorded above. `RESUME-NEXT.md` carries
it as the next mission.

---

## 4b. The mutation audit found dead code in tonight's own work

The full 410-mutation run came back **409/410**, and the survivor was
last night's:

    MISSED  startup: production mode is allowed to run on demo authentication

It survived because tonight's change made it unkillable. A separate branch
in `check_configuration` refused `APP_MODE=production` outright, and that
was correct when written. Then `AUTH_PROVIDER` and its four settings
became REQUIRED in production, so `config.verify()` - two lines earlier -
started refusing that same state first, and with a better message. A
configured provider returns before it. There was no path left that reached
the branch.

**A branch a mutation cannot kill is a branch nothing depends on.** It was
removed rather than exempted, which is the whole reason to run the audit
on a tree you have just changed rather than on the tree you changed it
from. The invariant still has a home: `AUTH_PROVIDER` is REQUIRED in
`config.VARIABLES`, and `test_a_real_auth_provider_is_required` fails if
anybody reclassifies it.

Afterwards: **409 mutations, and the 22 that touch this change - 4 startup,
18 auth - re-run and all caught.**

---

## 4c. The real environment exists, and it refuses to start

Created 2026-09-02. **Separate from the demonstration** - a different
Railway project, a different service, a different database of record.
The demo was not converted and is untouched.

| | |
| --- | --- |
| Project | `resonate` · `a60c5e64-c7a8-4813-924e-bad305bf3792` |
| Service | `resonate` · `d5ddbd51-78ba-4db8-979e-54496ddd20d7` |
| Volume | `resonate-volume`, **5 GB, mounted at `/data`**, Ready |
| Host | `resonate-production-a2d5.up.railway.app` |
| Variables set | `APP_MODE=production`, `QUEUE=/data/work/queue.jsonl`, `AUTH_PROVIDER=oidc`, `AUTH_ISSUER`, `AUTH_REDIRECT_URL`, `AUTH_ALLOWED_DOMAINS` |
| Variables absent | `AUTH_CLIENT_ID`, `AUTH_CLIENT_SECRET` - the owner's |

**The first deploy failed on purpose, and that is the result worth
having.** The build succeeded, Python 3.14.6 resolved, no packages
installed, the image pushed, and the log then reads:

    Mounting volume on: /var/lib/containers/railwayapp/bind-mounts/...
    RuntimeError: refusing to start in production mode without:
    AUTH_CLIENT_ID, AUTH_CLIENT_SECRET.

`/healthz` and `/login` both answer **502**. Nothing is served, so nothing
unauthenticated is exposed - which is what fail-closed is supposed to look
like from outside, and this is the first time it has been seen anywhere
other than a test.

Three things were verified here that could not be verified locally: the
volume genuinely mounts, the production build path works, and the refusal
fires in real infrastructure naming exactly what is missing.

**One CLI observation.** `railway volume list` printed `Mount path: /tmp`
and `Attached to: N/A` for a volume the same command had just created at
`/data`. `railway volume list --json` reports `"mountPath": "/data"` and
the correct service, and the deploy log confirms the mount. The
human-readable output is wrong; the JSON is not. Worth knowing before
somebody trusts the table.

---

## 5. What is now true that was not

- **ContactOut, AI Ark, EmailBison, HeyReach and Apify have authenticated
  and answered.** `LIVE-READINESS.md` moves each from "never called from
  this build" to a live-validated read contract, with the specific call
  named.
- **The `people-count` trim is validated against a real response**, not a
  documented one.
- **EmailBison's pagination envelope is confirmed**, which the reply
  poller depends on.
- **Deliverable is unchanged and still blocking.** Nothing here made it
  better, and the entry that says so is the same entry it has always been.
