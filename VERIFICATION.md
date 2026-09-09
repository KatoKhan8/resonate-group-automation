# No address is written to on one opinion

Two independent providers must confirm an email address before anything is
sent to it. One verifier is a single point of failure with a commercial
interest in saying yes, and ContactOut has been observed returning
`accept_all` for an address it separately marked verified in its own data
(BUILD-SPEC §9, trap 2). The second opinion costs one credit. The thing it
protects is sender reputation, which cannot be bought back.

    python -m src.verification --contact <record> <key>

## The flow

    selected contact
      → email found
      → MX lookup                free, one per domain, cached a week
      → blocked gateway?         YES → EMAIL CLOSED, no verifier credit spent
                                       LinkedIn untouched
      → ContactOut               the primary
      → invalid?                 YES → BLOCKED, nothing else is bought
      → Deliverable              the second confirmation, always
      → still short, or a
        catch-all, or a
        disagreement?            YES → Reoon, the escalation
      → confirmations ≥ 2?       NO  → HELD
      → final email eligibility

MX screening runs **before** the first paid call. A DNS lookup is free and
shared across every contact at a domain; a verification is two paid calls per
address. A domain behind a gateway this client blocks has its email channel
closed whatever a verifier would have said, so buying that answer buys
nothing.

The screening is deliberately narrow: only a **positively identified** blocked
gateway cancels verification. A DNS failure or a domain with no MX also closes
the channel, but neither is evidence about the address, and a resolver that was
down for a minute must not quietly cancel the verification of an address that
is perfectly good.

## The agreement matrix

| ContactOut | Deliverable | Reoon | Confirmations | Result |
|---|---|---|---|---|
| valid | valid | not needed | 2 | **PASS** |
| valid | invalid | not needed | 1 | **HELD** — reported as a disagreement |
| valid | unknown | valid | 2 | **PASS** |
| valid | unknown | invalid | 1 | **HELD** |
| valid | unknown | unknown | 1 | **HELD** |
| valid | accept_all | safe_to_send | 2 | **PASS** |
| valid | accept_all | not safe | 1 | **HELD** |
| valid | accept_all | unknown | 1 | **HELD** |
| valid | error / timeout | — | 1 | **HELD** — an error is evidence of nothing |
| valid | *not run* | *not run* | 1 | **HELD** — one confirmation of two |
| invalid | anything | not run | 0 | **BLOCKED** |
| unknown | valid | policy | 1 | **HELD** — the primary is never rescued silently |
| accept_all | — | safe_to_send | 1 | **HELD** — see below |

**A disagreement never picks the optimistic answer.** Two providers reaching
different conclusions is a hold, in both orderings, whichever one answered
first. "They disagree" and "it is dead" are different facts about an address
and the reason string says which.

### What changed for catch-alls

A catch-all cleared by Reoon alone used to be sendable. It is now held: the
primary said `accept_all`, which is the absence of a confirmation rather than
one, so Reoon's clearance is a single provider vouching for a domain that
accepts everything. That is the last address that should be the exception.

This reduces sendable volume on catch-all-heavy lists. It is a deliberate
trade and it is configurable — see below — but the default is the conservative
one.

## Confirmations are counted by provider

`verification.confirmations()` returns a **set of provider names**. Asking
ContactOut twice is one confirmation: two answers from one source share
whatever made the first one wrong, which is the entire reason a second opinion
is worth buying.

Only `valid` counts. A catch-all is not a confirmation, it is the absence of
one; `unknown` is the absence of an answer; an error or timeout is evidence of
nothing.

## And counted only for the address they were obtained for

The rule is not "this contact has two confirmations". It is that two
independent vendors approved **the exact normalised mailbox about to be
written to**. Those are different claims the moment an address changes, and
evidence stored on a contact outlives the address it describes.

`verification.evidence_for()` binds them, and `all_evidence()` is the only
way in. Before that binding existed, a contact whose two confirmations were
obtained for `old@acme.test` reported `verified` and `sendable` once its
address became `new@acme.test` - an address no vendor had ever seen. The
ordinary ways an address changes are all it took: a corrected typo, a
re-enrichment finding a better mailbox, an operator replacing one that
bounced.

Saying the rule twice did not catch it. Both `eligibility.decide` and the
payload gate in `push.verify_before_payload` read `verification.resolve`,
so the second guard asked the same question and got the same wrong answer.
A duplicated guard protects against a *forgotten* check, not a wrong one.

Two consequences worth stating:

- Evidence recording no address cannot be shown to be about this one, so it
  does not count. Fail closed: the cost is a re-verification, against the
  alternative of writing to an unverified mailbox.
- Stored evidence that is all bound out does **not** fall through to the
  legacy `verdict`/`reoon` fields. Those are read against the contact's
  *current* address, so the fallback would restore exactly the drift the
  binding removes, on the records old enough to carry both.

Comparison folds case and surrounding whitespace and nothing else. No mail
system treats either as significant; deciding that `a.b@` and `ab@` are the
same mailbox would be the fuzzy matching this system refuses everywhere it
matters.

## Where the rule is enforced

In one place, applied to every branch. `verification._verdict()` wraps every
return from `decide()` and downgrades a sendable decision that is short of
confirmations. Applying it there rather than at each branch is what makes it
an invariant instead of a convention: a new branch inherits it without its
author having to remember, and the branch somebody forgets is always the one
that says `sendable: True`.

The downgrade is one-way. It can turn a sendable decision into a held one and
never the reverse, so no future policy knob plumbed through it can accidentally
open the gate.

## Nothing trusts the stored state

`verification.is_sendable()` **recomputes from the evidence every time**. It
used to return `stored in SENDABLE_STATES` whenever a verification block
existed, which made `verification.state` a second source of truth: anything
that could write that string — a hand edit, a resumed run under an older
policy, a future UI, a bug — could clear an address no provider had ever
confirmed.

The evidence list is the durable fact. The state is a cached opinion about it,
and this is the function that must not be reading a cache. Re-deciding is
cheap: `decide` is pure, does no I/O, and reads a handful of dicts already in
memory.

Three gates ask independently, and all three recompute:

- `channels.email_verdict` → is this channel open at all
- `eligibility.decide` → may this step go out
- `push.verify_before_payload` → may this become a request body

## What is stored

```jsonc
"verification": {
  "state": "verified",
  "sendable": true,
  "reason": "contactout says valid",
  "confirmation_count": 2,
  "required_confirmations": 2,
  "confirmed_by": ["contactout", "deliverable"],
  "disagreement": false,
  "results": {
    "contactout":  {"verdict": "valid",   "checked_at": "…", "reason": "…"},
    "deliverable": {"verdict": "valid",   "checked_at": "…", "reason": "…"},
    "reoon":       {"verdict": "valid",   "checked_at": "…",
                    "is_safe_to_send": true, "is_catch_all": false,
                    "score": 92}
  },
  "evidence": [ … the normalised results, in the order they arrived … ]
}
```

`results` is a projection of `evidence` for reading. `evidence` is what
decides.

## Configuration

```yaml
verification:
  required_confirmations: 2     # the default. 1 restores single-verifier.
  primary: contactout
  secondary: deliverable
  catch_all: reoon              # the escalation
  accept_all_clears_on: [reoon]
  disagreement: hold
  max_verification_cost_per_contact: 3
```

Setting `required_confirmations: 1` is a deliberate, configured, tested choice.
It is not the default and it is not what happens by accident. Raising it to 3
works too, and the escalation supplies the third.

## The Deliverable gap, stated plainly

**Deliverable's response contract has never been read.** Its transport is
documented — base URL, submit and poll endpoints, the `x-api-key` header — but
the provider documents no response: no field names, no status values, no error
shape. `deliverable.verify()` therefore **refuses** until one real answer has
been seen and checked:

    python -m src.validate --provider deliverable --live-validation --max-credits 1
    # then set DELIVERABLE_RESULT_SHAPE=confirmed

Until then a Deliverable call returns `error`, which is evidence of nothing and
never a confirmation. The resolver stays conservative rather than assuming a
mapping: an unrecognised answer degrades to `unknown`, never to `valid`.

**The practical consequence today:** the second confirmation comes from Reoon,
not Deliverable, on every address. That is three verifier calls per address
rather than two. Once one real Deliverable response has been validated,
Deliverable closes the pair and Reoon drops back to catch-alls and
disagreements only.

This is the single most valuable thing to fix before a live pilot, and it costs
one credit to fix.

## Cost

At 5,000 domains, from `python -m src.costsim`:

| | expected |
|---|---|
| contacts selected | 7,000 |
| blocked by MX before any verifier ran | 840 |
| verifications | 6,160 |
| Deliverable calls | 5,236 |
| Reoon escalations | 5,236 |
| ContactOut credits | 33,000 |
| Deliverable credits | 5,236 |
| Reoon credits | 5,236 |

MX screening avoids roughly 840 primary, 714 secondary and 714 escalation calls
— a saving that doubled when the second confirmation became mandatory, because
a blocked domain now skips two paid calls rather than one and a maybe.

**Credits are provider units, not money.** No per-credit price is configured
anywhere in this build, and inventing one would make the column worse than
absent. `report.by_confirmation()` reports operations and credits, and says so.

## Channel behaviour

Verification failure closes **email only**. Every one of these keeps the
contact, the record and the LinkedIn steps:

| Outcome | Email | LinkedIn |
|---|---|---|
| two providers agree | eligible | eligible |
| second verifier says invalid | **blocked** | eligible |
| one confirmation of two | **held** | eligible |
| behind a blocked gateway | **blocked** | eligible |

A record whose state is `held` refuses its *email* steps and allows its
LinkedIn ones. That was a bug until this change: `approve.REFUSED_STATES`
included `held`, so an email-level judgement silently took the surviving
channel away — the failure `channels.py` exists to prevent, undone one module
later.

## What a reviewer sees

`out/demo-outreach.html` shows, per contact: the confirmation count against
the requirement, a per-verifier table including the providers that were never
asked, the final verdict, and a plain sentence when the count is short or the
verifiers disagree. Seven scenarios cover double-confirmed, second-verifier-
invalid, escalated-to-Reoon, one-confirmation-only, MX-blocked-before-spending,
email-only and reply-pauses-both.

`qa.report()` counts double-verified, single-verified, disagreements, verifier
failures, Reoon escalations, verification-blocked, and verification calls
avoided because MX screened first. A campaign is not launch-ready while an
email step exists for a contact short of its confirmations —
`campaigns.check_double_verification`, the seventeenth check on the list.

## What still needs a real provider

- **One Deliverable response**, read and checked. Everything above is
  conservative because that has not happened.
- **Reoon at volume.** It is now on the path for most addresses rather than
  catch-alls only, and its rate limits have never been hit.
- **Whether two providers actually disagree often.** The matrix says what
  happens; nobody knows yet how often the disagreement row fires on real data.

Live sending remains disabled. `push.run(live=True)` raises
`LiveSendNotEnabled`.
