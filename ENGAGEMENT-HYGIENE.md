# Engagement state, list hygiene, and what the providers are told

Three things that are easy to conflate and must not be:

1. **What we know** — canonical engagement state, in the event log.
2. **What to do about a new row** — a hygiene verdict, computed on demand.
3. **What EmailBison and HeyReach are told** — a copy, downstream of both.

Resonate is authoritative. The arrow points one way and nothing reverses it.

---

## 1. There is one taxonomy, and it already existed

`src/hygiene.py` invents no engagement states. It reads:

| Source | Answers |
| --- | --- |
| `accountpolicy.classify_outcome` | what a reply was classified as |
| `accountpolicy.contact_state` | what that did to the person |
| `accountpolicy.account_state` | what it did to their company |
| `account.touches` / `account.replies` | what actually happened |
| `dedupe.keys_for` | who this is, if we can prove it |

The twelve canonical outcomes are the reply taxonomy from
`ACCOUNT-OUTREACH.md` §10. What hygiene adds is a **verdict**: what to do
about a candidate row given those facts. A verdict is a decision, not a
state, which is why it is computed and never stored.

---

## 2. Hygiene verdicts

Ordered most-final first. A row matching several histories gets the most
conservative.

| Verdict | What it means | Action |
| --- | --- | --- |
| `suppressed_account` | the company asked not to be contacted | suppress |
| `suppressed_contact` | this person asked | suppress |
| `agency_suppressed` | agency-wide list (see §6) | suppress |
| `wrong_person` | not the right person here | suppress |
| `invalid_contact` | they have left the company | exclude |
| `meeting_booked` | a meeting is recorded | exclude from cold |
| `active_conversation` | a conversation is in progress here | hold |
| `previously_engaged` | replied to us before | hold |
| `future_follow_up` | asked us to come back later | route |
| `referral` | came to us through a referral | route |
| `previously_contacted` | contacted, never replied | review |
| `fresh` | no prior history | eligible |

**Previously engaged is not permanently excluded.** That distinction is the
whole point. Collapsing these into `exclude` throws away the best rows in
the list; collapsing them into `eligible` is how a client discovers we do
not read our own history.

**Nothing is deleted.** Every row keeps its place in the preview with the
evidence that produced the verdict — the contact, the event, the date, the
policy. An operator who cannot see *why* a row was held cannot tell a wrong
hold from a right one.

---

## 3. Identity is proved, never guessed

Matching uses `dedupe.keys_for` and nothing else:

- normalised email (`john@acme.test`)
- canonical LinkedIn URL (`linkedin.canonical`)
- provider lead id, namespaced by provider
- our own `record_id` + `contact_key`

A name and a company are **never** identity, here or in provider tagging.
Two people called Jan Novak at two Novak Consultings are two people.

A row with no strong identifier is matched at the **account** level only, on
its domain, and the result says `matched_on: account` so a reader knows
which question was answered.

### The account reaches a person we have never seen

This is the case the whole module was asked for:

> Acme has an `account_do_not_contact`. A newly imported `sarah@acme.test`
> must not become cold-eligible merely because Sarah has never appeared.

She does not. And the converse:

> John replied positively at Acme. A newly imported Michael at Acme is
> **classified, not deleted** — `active_conversation`, held, with
> "John Smith replied positively on 2026-08-05 at Acme Ltd" as the reason.

When a row *is* matched on identity, that person's own history outranks the
account's reading of the same event: John's "come back in Q4" stays
`future_follow_up` rather than being flattened into "somebody here replied".

---

## 4. Where hygiene runs, and why that is not enough

    CSV
      -> normalise, in-file dedupe, domain suppression   (upload.parse)
      -> hygiene against workspace history + agency index
      -> preview: classified, nothing committed
      -> commit -> ICP -> enrichment -> campaign
      -> eligibility.decide                              (pre-send)

**Import-time cleaning is not authoritative and must never be treated as
such.** Monday's verdict is Monday's. `tests/test_hygiene_lifecycle.py`
pins the case: fresh at import, replies on Tuesday, and Wednesday's
approved campaign is blocked by `eligibility.decide` — which asks the
canonical state again, for that exact step, immediately before anything
could go out.

Cross-campaign suppression falls out of the same design: canonical state
sits above provider campaigns, so a reply recorded anywhere reaches every
campaign the policy says it should.

---

### One row per company, not per person

A record is a company, so the parser dedupes by domain: two rows sharing a
domain are one row. The `email` and `linkedin` columns are read for
*identity* — that is how a row matches somebody we have written to before —
but they do not make the file a contact list. `PRODUCT-GAPS.md` §3bb has
the consequence and what a contact lane would take.

---

## 5. Cross-list deduplication

The same person in `August UK.csv`, `Founder List.csv` and
`Productive ICP.csv` is one canonical contact. Each file keeps its
provenance (`batch`, `row`); identity is not tripled. `dedupe` already
scopes duplicates as batch / campaign / client / cross-client, and
cross-client is **off by default** — two Resonate clients may legitimately
sell to the same company.

---

## 6. Agency-wide do-not-contact, and its privacy model

`src/agencydnc.py`. Somebody tells *Resonate* never to contact them; that
must hold in whichever workspace next imports them.

**What is stored:** a SHA-256 of a strong identifier, and a reason category.

    sha256("email:sarah@acme.test") -> {"reason": "requested", "at": ...}

No name, no company, no workspace, no campaign, no record id, no plaintext.
The file cannot be read to enumerate anybody: answering "is this person on
the list" requires already holding the identifier, which the workspace
asking does, because they are holding the row.

**What a workspace is told:** `suppressed by agency safety policy
(asked us directly)`. Never who asked, never when, never by whom.

**What it is not:** a mirror of reply state. A reply in one workspace does
not put anybody here — that is the client's business and stays inside their
tenancy. Only a request made to the agency does, written deliberately,
never derived.

**What it does not buy:** this is not encryption. Somebody holding both the
file and a candidate list can test each candidate, exactly as the importing
workspace does. What it prevents is the file being a directory of other
clients' prospects, and a lookup returning anything beyond yes.

---

## 7. Provider tags

`src/tagsync.py`. Stable, namespaced, lower case:

    resonate_replied      resonate_positive       resonate_follow_up
    resonate_not_interested                       resonate_referral
    resonate_wrong_person resonate_left_company   resonate_dnc
    resonate_account_dnc  resonate_existing_client
    resonate_meeting      resonate_review

The prefix is not decoration: a provider account is shared with the
client's own sequences and a bare `positive` would collide.

### Accumulate, except one

Tags accumulate — `resonate_positive` and `resonate_dnc` are both true of
somebody who replied warmly in March and asked to be removed in June, and
both stay. What does not accumulate is **stage**, the single tag naming
where the contact is now, so a filter for "current stage" has one answer.
History lives in the event log, which is immutable; the provider holds a
summary and is allowed to be one.

### The outbox

    authoritative reply
      -> canonical state        (accountpolicy.apply_reply)
      -> desired tag state      (tagsync.enqueue)
      -> a provider call, later, by something else
      -> result recorded, retried if it failed

Reply ingestion never waits on a provider. A row says *what should be
true*, keyed by `(workspace, record_id, contact_key, provider)`.
Re-ingesting the same reply recomputes the same desired state and writes
nothing new — there is no second operation to deduplicate. Attempts, last
error and last success live beside the desired state.

`_queue_tags` runs **after** every canonical transition and cannot raise
into its caller. A tag failure delays a label in somebody else's UI; the
transition above it cannot be lost. Same ordering, same reason, as the
Slack notification.

### Identity, again

A tag row is written only for a contact this provider can be told about
authoritatively: its own lead id, or the canonical email (EmailBison) or
canonical profile URL (HeyReach). Anything else is `blocked` — not a
failure and never retried, because there is nothing to retry. Tagging the
wrong lead writes our conclusion about one person onto another.

### LIVE CONTRACT VALIDATION REQUIRED

**No tag endpoint on either provider has been exercised.** `tagsync.send()`
raises `TagSyncRefused` and there is no code path that mutates a provider.

| Provider | State |
| --- | --- |
| EmailBison | custom variables round-trip for `subject` and `body` only. A tag endpoint is named in `emailbison_request` so it is reviewable; nothing has confirmed it exists. |
| HeyReach | confirmed live 2026-08-26: `customFields` comes back empty on every conversation and `/lead/GetLead` exposes none, so tags cannot ride the lead payload. Needs HeyReach's own tag or list API, whose shape nobody here has seen. |

What *is* ready offline: the canonical desired-state model, the adapter
interface, the outbox with retry and status, the preview, and the tests.
See `LIVE-VALIDATION-PLAN.md` for how a first real call would be made.

### Reconciliation

Not implemented, deliberately. The shape is available — `tagsync.load()` is
the desired state and a read-only provider fetch would be the actual state —
but comparing them is only useful once a tag can be written, and no
reconciliation may ever change canonical truth.

---

## 8. What an operator sees

- **Import preview** — counts by verdict, then every non-eligible row with
  its reason. Filterable by action.
- **Contact dossier** — engagement state, cold-outreach eligibility and
  *why not*, last reply, active conversation, and per-provider tag sync.
- **Reply policy** — what each outcome does, unchanged from
  `ACCOUNT-OUTREACH.md` §10.

Provider sync status is operator-facing only. A client-facing role sees
engagement, never which provider holds which tag.
