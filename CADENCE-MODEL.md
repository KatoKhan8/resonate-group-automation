# Cadence Model

Cadences that branch, wait, and involve more than one human.

Read this before changing `src/cadencegraph.py`. `ACCOUNT-OUTREACH.md` covers
the account graph these cadences run against.

---

## 1. Why a list stopped working

`src/cadence.py` models a sequence as an ordered list of steps with a day
number. That is exactly right for "email day 1, LinkedIn day 3, email day 5"
and cannot express what Resonate actually runs:

```
connection request
  ├── accepted?   yes → message          no → wait 7 days, email instead
  ├── replied?    yes → stop             no → follow up
  └── nothing after a month?             → re-engage from a different profile
```

A list has no "if". The old model bolted one on — a `requires:
connection_accepted` field — which handles a single condition and stops.

So a cadence is now a small **directed graph**: typed nodes, and edges that may
carry a condition.

---

## 2. Deliberately not a workflow engine

No scripting. No user-defined predicates. No loops. The node types and
conditions are closed sets, and adding to either is a visible edit to
`src/cadencegraph.py`.

A general engine would be more powerful and much worse. It would let somebody
build a cadence whose behaviour nobody can predict by reading it, and every
safety rule in this repository depends on outreach behaviour being predictable
by reading it.

---

## 3. Reference material — what was and was not available

The mission brief refers to HeyReach exports of successful sequences as a
structural reference.

**Those files are not in this repository.** They were not supplied in the
context available to this build, so nothing here was derived from them.

The node vocabulary below comes from two sources that *were* available:

1. the brief's own list of required primitives
2. what `src/providers/heyreach.py` and its recorded cassette demonstrably
   support

Two node types the brief names — **post reaction** and **withdraw connection
request** — are present in the vocabulary but marked `validated: False`,
because no recorded contract here proves the provider does them. A cadence
using one is **blocked at validation**, not quietly planned. See
`LIVE-VALIDATION-PLAN.md`.

If the exports are supplied later, the right change is to widen the vocabulary
against them and mark the newly-proven nodes validated — not to assume.

---

## 4. Node types

| Type | Channel | Contacts? | Validated | What it does |
| --- | --- | --- | --- | --- |
| `wait` | — | no | yes | hold for N days |
| `email` | email | **yes** | yes | send from an assigned inbox |
| `connection_request` | LinkedIn | **yes** | yes | request, with or without a note |
| `linkedin_message` | LinkedIn | **yes** | yes | DM; needs an accepted connection |
| `linkedin_followup` | LinkedIn | **yes** | yes | later message in the same thread |
| `connection_check` | LinkedIn | no | yes | read acceptance state |
| `reply_check` | — | no | yes | read whether they replied |
| `branch` | — | no | yes | split on a condition |
| `handoff` | — | no | yes | move channels, carrying a permitted reference |
| `dm_handoff` | — | no | yes | move to another contact at the account |
| `reengage` | — | no | yes | restart after a long wait |
| `stop` | — | no | yes | end this contact's sequence |
| `post_reaction` | LinkedIn | no | **NO** | react to a post — **unvalidated** |
| `withdraw_request` | LinkedIn | no | **NO** | cancel a pending request — **unvalidated** |

### The "contacts" column is load-bearing

A `wait` or a `branch` is a node in the graph but **not a touch**. Counting one
as a touch would throttle a campaign wrongly *and* let a message claim an
approach that never happened. `steps_of()` returns only contacting nodes, and
that is what fatigue counts and what claims may reference.

---

## 5. Conditions

Everything a branch may test. Each maps onto a fact the engine already records;
none needs a new kind of evidence.

| Condition | True when |
| --- | --- |
| `connection_accepted` | the request was accepted |
| `connection_pending` | it was not |
| `replied` | this contact replied |
| `no_reply` | they have not |
| `positive_reply` | the reply was positive |
| `email_confirmed_sent` | an earlier email is **confirmed** sent |
| `referral_received` | somebody here referred us to this contact |
| `other_dm_replied` | another decision maker at this account replied |
| `always` | always |

`email_confirmed_sent` is the condition behind a cross-channel handoff, and it
tests **confirmed**, not planned. That is the same rule the claim resolver
enforces, expressed as a branch.

---

## 6. Roles, not contact keys

A node targets `contact_role` — `primary`, `secondary`, `tertiary`,
`referral` — never a specific contact key.

A cadence is a plan for an *account shape*. A graph naming `contact_key=k3` is
a graph that works for exactly one company.

---

## 7. Validation

`validate()` returns structural findings. Blocking:

- unknown node type or condition
- a node type whose provider capability is unvalidated
- an edge pointing at a node that does not exist
- a branch with no condition
- a wait with no duration
- a contacting node with no sender
- a cycle — a cadence that would never end
- a sender not on the campaign's outreach team

Warning:

- a branch with one edge (that is a step)
- a LinkedIn message with no connection request before it
- an unreachable node
- a graph written under an older schema version

Validation is **structure only** — whether the graph is runnable and
internally consistent. Whether it is *wise* is fatigue and claim resolution,
checked by their own modules against a real account.

---

## 8. Versioning

`SCHEMA_VERSION = 2`. Every stored graph carries its version.

A cadence written under version 1 is **read under version 1's rules**, not
reinterpreted. Silently re-reading an old plan under new semantics is how a
campaign somebody approved becomes a campaign nobody approved.

`from_legacy()` reads the old linear `cadence.STEPS` as a graph and stamps it
version 1. A `requires: connection_accepted` becomes an explicit branch, which
is what it always meant.

---

## 9. Templates

Reusable **shapes**, not client copy. Each builds a graph from the senders it
is given, so the same template works for any workspace — a template carrying
one client's messaging is a template nobody else can use.

| Template | Shape |
| --- | --- |
| `standard` | email opens, LinkedIn supports, email closes. 2 branches |
| `linkedin_heavy` | LinkedIn-led, second profile takes over if the first stalls, 21-day re-engagement |
| `account_multi_dm` | two decision makers, two email humans, two LinkedIn humans, referral branch |
| `reengagement` | long and quiet, for accounts that went cold |

`account_multi_dm` is the one the brief is actually about: the primary is
opened by one pair, the secondary by a different pair, and the second person's
sequence is aware of the first's.

---

## 10. What a cadence cannot do

- name a sender outside the outreach team
- use a provider capability nothing has validated
- loop
- reference a touch that has not been confirmed
- reach a prospect more often than the fatigue policy allows
- be reinterpreted under a schema version it was not written for
