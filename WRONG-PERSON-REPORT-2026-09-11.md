# Wrong-person report — 2026-09-11

One question, asked of the whole system: **can an identifier belonging to
person A end up on person B, such that a real human is contacted as somebody
else?** Three places said yes. All three are fixed, each reproduced before it
was touched, and the answer was then validated end to end against live
provider truth.

---

## HEAD / TREE / VALIDATION

```
HEAD            5a383b9
commits         6 this session on top of bc957b4
tree            clean

full suite      7,100 tests   OK   (definitive, settled tree)
offline harness 7,100 tests   OK   "nothing reached off this machine"
mutations       22            each caught by the intended test
                              (9 referral + 7 enrich + 5 linkedin + 1 funnel)

execution guard 14 of 15 gates PASS against live provider truth
                only killswitch stops, by construction
```

The two harnesses were run with a gap between them, which is what CLAUDE.md
prescribes, and they agree on the same 7,100.

A note on the suite verdict, because it nearly was not one. The first full run
on this tree was piped through `tail -20`, and the trailing stdout of the demo
estates pushed `Ran N tests / OK` out of the window - while the pipeline's exit
code reported `tail`'s success, not unittest's. There was no verdict, only
something that resembled one. Re-run with the output captured whole.

---

## 1. The three paths

| where | how a real person gets contacted as somebody else | mutations |
|---|---|---|
| `referral.promotable` | a reply names two people; the first address is welded to the first profile | 9 |
| `enrich.merge_contacts` | two people share a name; one's address lands on the other's profile | 7 |
| `linkedin.canonical` | two legacy `/pub/` members collapse onto one identity | 5 |

They are the same defect wearing three coats: **a name treated as an
identity**, or **two independent lists read as though their order meant
something**.

`referral.py` already stated the rule, in its own module docstring: "An
address or a canonical profile URL is identity. A name is not - two people
share one and one person has three." The module that said it obeyed it at one
step and broke it at the next; `enrich.py` disagreed with it outright; and
`linkedin.py`, which opens by refusing fuzzy matching, was doing a fuzzy
match on the segment that distinguishes two members.

### 1.1 A referral that names two people

`evidence()` returns emails, profiles and names as three independent lists and
says so - "No interpretation." `promotable()` then took `emails[0]` and
`profiles[0]`.

Reproduced end to end:

    reply     "speak to Dana Reed, dana.reed@acme.test ... you could also
               try Tomas Brabec: linkedin.com/in/tomas-brabec"
    promoted  status=ready   email=dana.reed@acme.test
                             linkedin=.../in/tomas-brabec

The LinkedIn step sends a connection request to `contact["linkedin"]` greeting
`contact["name"]`, so the second person would have received an invitation
addressed to the first, about a conversation he had never had. A reply
signature is enough to reach it: two identifiers in a body is the ordinary
shape of a referral.

The approval screen compounded it. It rendered `email or linkedin`, so when an
address existed the profile was never shown - the operator could not see the
half that was wrong at the moment of deciding.

Now refused rather than resolved, reusing the `AMBIGUOUS` status `resolve()`
already uses for the same statement one step earlier. The name is taken only
when the reply mentions exactly one.

### 1.2 A shared name merging two people

`merge_contacts` built one index keyed by every handle a contact is known by -
address, profile and **name** alike - so all three were interchangeable when
looking somebody up.

Reproduced in the shape the pipeline actually reaches. Both call sites run only
when `usable_contacts(rec)` is empty, so the contact being merged into is
somebody known by name and profile, and it is the **address** that gets welded
on:

    on the record   Jan Novak, /in/jan-novak, no address
    provider says   Jan Novak, j.novak2@acme.test, /in/jan-novak-studio

    after merge     /in/jan-novak  +  j.novak2@acme.test
                    added: []   excluded: []

`usable_contacts` then returns that row, so verification buys a check on the
second person's address and a valid answer marks it **sendable**: the email
goes to one human and the connection request to another. The second person is
neither added nor excluded and no reason is recorded - a real decision maker
deleted without a trace.

This one needed no reply from anybody. And a contact added from a referral
arrives as exactly the shape it preys on - name and profile, no address - so
the two paths chain.

### 1.3 A legacy profile URL collapsing two members

`canonical()` kept only the first path segment, which is right for
`/in/x/detail/contact-info` and wrong for `/pub/jan-novak/1a/2b3/4c5`: the
trailing triplet is what tells two members with that vanity apart. Both of
them - and anybody at `/in/jan-novak`, who may be a third person - became one
identity. This module's answers decide suppression, collision and whose
campaign gets paused.

Latent: the estate holds no `/pub/` URL at all. Fixed because identity is the
wrong place to keep a known-false equivalence, not because it had fired.

---

## 2. What the tests found in the fixes

Both of these are the failure mode this repository names in its own
contributing rules, and both were in my own work.

**A field read that did not exist.** `promotable` read `entry["names"]`, but
the persisted `REFERRAL_MENTIONED` event stores them as `named` - one
comma-joined string for the six places that display it. Only the live
`evidence()` dict has the list. So on the one path that actually adds a
contact, the name check saw an empty list and every referred contact would
have arrived nameless. `names_in()` now reads both real shapes in one place,
and a test pins the property that makes the split exact rather than assuming
it.

**Computed and consumed by nobody.** The refusal carried a `candidates` dict
that nothing read. A refused row has no email and no profile by construction,
and that page does not render the reply body - so the operator read "this
reply names more than one person" beside a blank cell, with nowhere to go. The
row now lists what the reply said.

Three mutations survived the first `enrich` sweep, and each was a test I had
reasoned about and never written:

  - **Precedence is load-bearing, not tidiness.** My first precedence test did
    not discriminate, because in that fixture the name-matched contact
    disagreed anyway and the conflict check rescued it. The case that needs
    order is a contact known *only* by name: nothing about her contradicts
    anything, so `disagree` has nothing to compare, and consulting the name
    first fills an incoming profile onto her when it belongs to somebody
    already on the record.
  - **The normalisation I had proved necessary was unasserted.** The estate
    audit told me every profile is stored as a bare vanity slug and every
    provider returns a full URL. Compared raw, one person becomes two, and
    minting the second discards the verification bought for the first. I
    reasoned it out in a docstring and tested none of it.
  - **A placeholder is not a handle.** `normalise_email` answers None without
    an `@`; lowercasing raw instead makes every contact carrying "N/A" match
    every other one.

---

## 3. Was the live estate already damaged

No. Audited, read-only, across all 300 records:

```
records with two contacts sharing a name        0
contacts whose address resembles neither
  their own name nor their own profile          0
```

One contact was flagged by the first pass and it was my predicate's fault, not
the data's: that contact stores its profile as a bare slug, so my URL regex
returned `""`, and `"" in name` is trivially true. The bug is real and
reproducible; it has not fired here. That bounds the exposure and does not
excuse it.

---

## 4. What was validated against provider truth rather than asserted

### Campaign 594061, reconciled

```
status          PAUSED                            as expected
name            PRODUCTIVE - CANARY - 2026-09-09  as expected
seat            campaignAccountIds [116968]       as expected
org unit        118832                            as expected
leads staged    totalUsers 1                      as expected, cap 1
finished 0   failed 0   excluded 0   stopped 0    nothing has run
in progress     1                                 the lead, unactioned
conversations   0 for this campaign               nothing was opened
copy            renders from what we send         re-read from /sequence
```

No difference on any line. The counters also say something the prose did not:
`startedAt` is 65 seconds after `creationTime`, so the campaign was started
once and paused again, and it actioned nothing in that window.

"Nothing was sent" is an inference from four agreeing signals, not one
authoritative field - this vendor exposes no invitation state at all. The
conversation count is the strongest of the four and was falsified before being
trusted: the same filter returns 14 to 26 conversations for FINISHED campaigns
on this same seat and 0 for DRAFT ones, so 0 here is an answer rather than an
unrecognised filter key.

### The collision gate, run live

The duplicate-send question for the LinkedIn lane. Run against the canary
account's two contacts:

```
contact A   verdict CLEAR   10 of our conversations examined
contact B   verdict CLEAR   37 of our conversations examined
both        3 other tenants' conversations ignored, 32 seats searched
```

That is real coverage rather than a vacuous CLEAR: conversations were actually
read and compared, and the tenancy scoping demonstrably did work. A prior
conversation with the same profile on any of the client's 32 seats returns
TOUCHED or IN_SEQUENCE, and the execution guard requires CLEAR.

The account-level version of the question remains unanswerable and is recorded
in the code as a function rather than a comment, which is the right place for
it: `searchString` does not match `companyName`, so "has anybody at this
company talked to one of our seats" needs all ~25,600 conversations walked.

### The execution guard, against live provider truth

```
PASS  tenancy  approval  campaign_approval  readback  eligibility
PASS  suppression  copy  claims  fatigue  collision  sender
PASS  pilot_cap  stoppability  ledger
STOP  killswitch - global: live sending is refused in code
      (3 of 6 layers refuse: global, workspace, campaign)
REFUSED at gate killswitch (14 gate(s) passed first)
```

`readback` passing means a live configdiff against HeyReach agreed with the
approved material. Every gate that can be satisfied is satisfied, on a tree
carrying all three identity fixes. The one refusal is deliberate and is not a
flag.

---

## 4b. Is the staged canary still the right one, derived today

The selection was made on 2026-09-09. Rather than trust it, it was re-derived
from current state by running `eligibility.decide` over every fully verified
contact in the estate, for the LinkedIn day-3 step:

```
contact 1 (the staged canary)   eligible   reasons []
contact 2                       held       held:draft_not_approved
contact 3                       held       held:draft_not_approved
contact 4                       held       held:draft_not_approved
contact 5                       held       held:draft_not_approved
```

The ranking is not a judgement call today: the field of eligible candidates
has exactly one member, and it is the contact already staged on campaign
594061. The other four are held for one reason, and it is the same reason as
§5g - no model, so no cadence, so no draft, so nothing approved. Their
verification is complete and their gates are otherwise clear.

The selection is deliberately NOT persisted as a set of CANARY_* fields.
Everything it would record already has one canonical home: the campaign holds
the record and the approval fingerprint, the provider holds the lead, and the
verdict above is derived on demand from the state that decides it. A stored
copy would be a second representation of a fact that is already canonical,
and this project's rule is to prefer the canonical one - a remembered choice
is exactly the thing that goes stale while the state it was drawn from moves.

Identifiers are omitted here on purpose. This file is tracked, and
`test_fixture_hygiene` refuses a real prospect's name or domain in tracked
source - the domain in question is on its forbidden list.

---

## 5. Where the funnel stands

```
input_domains               300
company_facts               265   of 300    88.3%
researched                   72   of 300    24.0%
confidence_medium_or_high     10   of 264     3.8%
qualified                      9   of 264     3.4%
people_found                  25   of   9   x2.778
emails_2_of_2_verified         5   of  25    20.0%
campaign_ready                 1   of  25     4.0%
approved                       1   of   1   100.0%
provider_staged                0   of   1
```

Attrition across the 300: 102 the system working correctly, 88 bounded by the
research budget, 42 waiting on a human, 35 with no provider coverage, 33 still
needing an explanation.

`people_found` reads `x2.778` rather than `278%` because people and records
are different units, which is the whole point of that column.

**An earlier note in this project said 32 people and 6 verified. It was
wrong.** The queue has not been written since 08:57 today, so nothing
regressed; the figures above are measured from the file.

`provider_staged 0 of 1` is correct and its label was not. It counts
action-ledger rows - what this system did - while describing itself as "the
provider holds the lead", which is provider truth. Today those disagree out
loud: HeyReach holds one real staged lead, put there by a person in the vendor
UI, and the ledger has no row because this system did not do it. The label is
corrected. It under-reports, which is the safe direction for a count of
prospect-facing actions, and it will read 0 until a supported staging write
exists.

---

## 6. What a person has to do, and why I did not do it

**Press unpause on campaign 594061.** Unchanged, and now reconciled. One
correction landed in HUMAN-ACTIONS §5e: it told the operator `heyreach.pause`
has no route, so nothing could stop a running campaign. A route exists now.
The conclusion is unchanged - a route is not a capability, the one live
attempt returned a non-2xx and was classified UNVERIFIED, and
`providerwrites.SUPPORTED` is still empty so the `stoppability` cap still
holds - but "no code exists" and "code exists and has never worked" are
different things to accept a risk against.

**Provide a model credential (new, §5g).** Four of the five fully verified,
sendable contacts have no cadence and none can be given one.
`generate.run()` defaults to `llm.NoModel`, which refuses by design; the only
other implementation returns canned answers for tests. `LLM_API_KEY` is
declared in `config.py` and read by no code path that builds a model.

The adapter is about twenty lines and is deliberately not written. With no
credential it cannot be run once against the real contract, and an adapter
nobody can exercise is a module that looks like a capability and is not one -
the same mistake `providerwrites.SUPPORTED` exists to refuse. Credential
first, then adapter, then one real generation read back and linted.

---

## 7. What this did not do

No prospect-facing action. No provider write of any kind; every provider call
this session was a read. No ICP, verification, suppression, fatigue,
collision, claims, approval, tenancy, readback, idempotency, budget or
killswitch rule was loosened - the only rule changes tightened two identity
checks and refused a case that used to be allowed, which lowers yield rather
than raising it. No test was weakened to make it pass; one stale enumeration
was corrected upward after it correctly caught a fifth promotion outcome.

An incident worth recording: a two-minute tool timeout killed a mutation
harness mid-run and left a mutated `src/web/api.py` on disk. It was caught by
grepping for each original line rather than trusting the harness's own
`restored: True`, and this repository has committed mutated source once
before. The verification step is the only reason it did not happen twice.
