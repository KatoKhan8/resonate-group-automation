# Account intelligence: signals, freshness, and explainable priority

Three questions, kept apart because collapsing them is how a system starts
asserting more than it knows:

1. **What is happening** at this account — signals.
2. **How much it matters now** — priority, decomposed.
3. **Whether anything may be sent** — eligibility, which outranks both.

---

## 1. Signals observe canonical state; they never replace it

The most trustworthy things known about an account are already in the event
log: who replied, who referred whom, who booked a meeting, who asked to be
removed. A signal layer storing a second copy would be a second place that
can disagree with the first.

So **first-party signals are derived, not stored.** `signals.derive()`
reads the log through `account` and `accountpolicy`. It writes nothing, and
there is no path by which a signal changes what a reply meant.

`ENGAGEMENT_SIGNAL` maps the canonical reply outcomes onto engagement
signals — one direction only. The outcome is the fact; the signal is a
reading of it. No second vocabulary for things that already have names.

## 2. Evidence is not optional

`signals.signal()` raises without it. The rule is what the evidence has to
be, not that a field is filled:

| Bad | Good |
| --- | --- |
| "scaling rapidly" | "7 open project-management roles listed on the careers page" |

The first cannot be quoted back to a prospect; the second can. And a signal
is **still not a licence to say it**. A hiring signal is a reason to
prioritise an account, not permission to write "I saw you're hiring" —
that sentence needs `src/observations.py` to grant it, and a signal can
never be what grants it. See §7.

## 3. Taxonomy

Three scopes, because "who does this tell us about" has three answers:

- **Account** — funding, headcount growth, hiring surge, new executive, new
  market, new office, tech adoption/removal, job posting, website change,
  company news, expansion
- **Person** — job change, promotion, new role, relevant content,
  responsibility change
- **Engagement** — derived from the canonical reply outcomes

## 4. Freshness and decay

Per-type half-life, not one universal curve: a funding round is still
interesting a quarter later and a website change is not.

| | Half-life |
| --- | --- |
| Website change | 30 days |
| Job posting, company news | 45 |
| Hiring surge | 60 |
| New executive, headcount, tech | 120 |
| Funding, new market/office | 180 |
| **Removal requests, wrong person, left company** | **never decay** |

That last row is deliberate: a removal request is as true in a year as on
the day, and letting it fade is the one kind of forgetting this system must
never do.

Below 15% weight a signal is **stale**: still recorded, still shown, no
longer contributing. Kept rather than deleted — "we knew this and it aged
out" is a different statement from "we never knew it".

An **undated** signal is treated as one half-life old. No date is not the
same as fresh.

`weight_at()` returns the weight, the decay multiplier, the age and a
freshness word. A score that cannot show its own decay is one nobody can
argue with.

**Strength saturates** (`total / (total + 2)`), so ten stale job postings
cannot add up to a referral.

## 5. Priority, decomposed

"AI says 92" is an assertion, not a score. Five components, each returning
its own evidence:

| Component | Default weight | Asks |
| --- | --- | --- |
| ICP fit | 0.35 | does this match what the client sells to |
| Signal strength | 0.20 | is anything happening |
| Timing | 0.10 | is it still current |
| Persona coverage | 0.15 | do we have the right people, reachable |
| Engagement | 0.20 | have we got somewhere already |

Weights and tier thresholds are per workspace. The defaults lean on fit and
engagement because those are measured most reliably — weighting signal
strength heavily today would be weighting a number that is mostly zero,
since no external source is connected.

**Signal strength counts what is happening at them, not what we did
to them.** Engagement is derived from the same event log, and the
`engagement` component already scores it. Feeding those events to both
counted one reply twice, and it made an account we had merely written to
last week report "1 fresh signal" in its why-now - which reads as interest
from them rather than activity from us. Scoring uses external signals
only; every screen still shows both, labelled.

**ICP fit is read, never recomputed.** It comes from
`qualification.verdict`, where `qualify.company` writes it. A second
opinion about ICP would be a second ICP, and the client configured one.

**Persona coverage counts verified reachability**, not contacts found.
Three unverified addresses are not coverage.

## 6. Priority is not permission

The most important rule here.

A score says *worth attention*. It says nothing about whether anything may
be sent. `hygiene` and `eligibility` decide that and outrank this
completely.

`assess()` returns the eligibility verdict **beside** the score and never
folds it in, so no screen can show one without the other. In the demo,
Skyline Studio scores 67 and is **not eligible** — held while a
conversation is live. The dashboard shows both on the same row.

A suppressed account can score 90. It is still suppressed.

## 7. Knowing something and being allowed to say it

`src/observations.py` is the licence. It answers, before a word is
written: what has this system actually observed about this company or this
person that a message may state, and on what evidence.

Three modules, three questions, and they are not interchangeable:

| module | question |
| --- | --- |
| `outreachclaims` | may a message say something about *us* - "my colleague Anna emailed you" |
| `observations` | may a message say something about *them* - "you opened a Vienna office" |
| `claims` | does this finished draft contain a sentence nothing supports |

`claims` is a refusal at the end. `observations` is a licence at the
start, and a generator with no licence to consult guesses generously.

**A signal never licenses a sentence.** This is the rule the module exists
for. A signal carries a type, a date, a confidence and a short evidence
note - and no source URL, because it is a reading rather than a citation.
"I saw you're hiring three implementation managers" is a checkable factual
claim, and only a piece of evidence with a link can back one. `resolve()`
refuses every signal *explicitly* rather than by omission, and `withheld()`
lists them, because a system that silently declines to mention something
looks exactly like a system that never knew it.

Four things are known and stay unspoken, each with its own reason on the
row:

| | why it is refused |
| --- | --- |
| a signal | no source a message could point at |
| a fact with no URL | not defensible when they ask where we saw it |
| a fact that aged out | still true, no longer current enough to write from |
| a weak fact | known, not worth a sentence |

**Recent is itself a claim.** "You just opened a Vienna office" asserts a
date. A fact outside the freshness window may still be stated - the office
is still there - but not as news, so `may_call_it_now` is carried
separately from `allowed`. An undated fact never earns it: a wrong "last
month" is a small lie the recipient can check against their own calendar.

**The subject must match.** A company fact cannot license a sentence about
a person, one contact's evidence cannot license a sentence about another,
and quoting somebody needs something they actually wrote. That swap is the
one a generator makes without noticing.

**Permission is not obligation.** Every type has a campaign switch.
Person-level types are off by default, and widening that is a deliberate
setting rather than a consequence of having found something.

---

## 8. Storage

Only what cannot be derived: manual signals today, a provider's one day.
`signals.jsonl`, append-only, beside the queue, registered in
`store.STATE_OVERRIDES` and `config/.env.example` so it moves with every
other state file.

`record()` refuses a first-party signal outright — storing one would put a
second copy of an event-log fact where it can drift.

`load(workspace)` filters by workspace. That filter is the tenancy
boundary, not an optimisation.

## 9. Entering one by hand

`signals.record` is its own permission, held by operator and above. A
reviewer reads an account's signals and cannot add one: reading the estate
and changing what it is worked in are different powers.

Four refusals, each for its own reason:

- **the permission**, asked before anything is read
- **the record**, resolved through the scoped repo, so an id from another
  workspace is a 404 and not a write
- **the type**, which may not be an engagement signal
- **the evidence**, which has to be long enough to quote

That third one is the rule this path is shaped around. Reply state comes
from the event log; somebody typing "they replied" would create a second
copy of it, and between two copies the handwritten one is the one that
goes stale. So the form does not offer engagement types, says why they are
absent, and `record()` refuses them at the door regardless of what the form
sent - the same rule `record()` already applied to first-party sources,
reached by the other route.

The date defaults to today rather than to nothing. Undated signals are
treated as one half-life old, which is right for a signal whose date was
never known and wrong for one a person is entering as they watch it.

Every entry is stored as manual, attributed to whoever entered it, and
written to the audit log with its evidence - the evidence is a quotable
observation, not a secret.

## 10. The campaign brief

`contextpack` answers the question the campaign screens do not:

    why these companies, why now, and what may we say to them?

`/campaigns/<id>` says whether a campaign is *in order* - lint, QA,
mapping. The outreach preview says what would *arrive*. Neither says
whether it should go out at all, and the four answers that settle it live
in four different modules. A person assembling them by hand misses one.

The pack asserts nothing of its own. Every number is counted from records
the caller could already read, and every sentence belongs to a module that
already stands behind it: `segments` for why these companies are a group,
`priority` for which are worth attention, `signals` for what is happening,
`strategy` for which angle the evidence supports, `outreachclaims` for what
a message may assert. There is no fifth opinion.

Three rules it exists to hold:

**Supported and hypothetical never merge.** `strategy` already splits a
pain into "this company's evidence fired it" and "typical for the vertical,
but nothing here supports it". The pack keeps them apart to the screen, and
names any pain *no* company in the campaign supports - that is the one most
likely to reach copy on the strength of sounding right.

**Priority is not permission, at campaign scale.** The tier counts and the
count of accounts that cannot be written to are one block. Thirty
high-priority accounts of which eleven are suppressed is a different
campaign.

**A signal is not a claim.** The evidence is quotable and right there,
which is why the pack says plainly that quoting it is not what it is for.
Every claim type `outreachclaims` knows is about a prior touch or a
relationship; none covers an observation about the company. Mentioning a
funding round in a message would need a claim type of its own.

The brief also separates *what is happening at them* from *where we
already stand with them*, for the reason above: listing our own touches
under the first heading makes contacting somebody into evidence that they
were worth contacting.

Its checklist is conditional throughout, so an orderly campaign produces
an empty one. A checklist that always says the same six things is one
nobody reads.

## 11. Playbooks

Two template systems already existed and neither was this one.
`cadencegraph.TEMPLATES` holds cadence *shapes*; `cadence.TEMPLATES` holds
message *copy*. Between them sat the decision nobody had written down:
given a 50-person German agency that is hiring, which shape, which angle,
which proof, which ask?

A playbook is that bundle - six of them, deliberately few, because a
library of thirty is one nobody has read.

**It recommends; it does not assign.** Nothing selects a cadence, writes
copy or touches a campaign. `recommend()` returns ranked candidates, each
carrying the conditions that held, the ones that did not, and the ones
never established - because a recommendation whose weak points are hidden
is one nobody can disagree with, which makes it an instruction.

**Unknown is not a miss.** An account whose employee band was never
established has not failed the size condition; it has not been asked.
Collapsing those turns "we know nothing about this company" into "this
company is a poor fit".

**"Nothing here fits" is an answer.** Below the confidence floor nothing is
recommended and the segment default is offered separately, never mixed
into the ranking - "the segment approach, because we know nothing else"
and "the new-leadership approach, because their COO started in August" are
different kinds of recommendation.

**A playbook licenses nothing.** Choosing the hiring playbook selects an
angle - operational scalability. It does not permit a message to say "I
saw you're hiring". That stays with `outreachclaims`, which has no claim
type covering an observation.

An invariant asserts every playbook names a cadence template and pains
that actually exist, so a plan that cannot be run is caught here rather
than by whoever tries to run it.

## 12. What an operator sees

- **`/signals`** — every account by priority, with why-now, fresh-signal
  count, and whether outreach is allowed. Tier filters. Live signals by
  type.
- **Account screen** — a "Why this account" panel: score, tier, eligibility,
  the why-now sentence, every signal with its evidence and freshness and
  source, and an expandable breakdown of how the score was reached.

Manual signals read "Entered by a person"; derived ones read "Observed by
Resonate". A person can always tell which is which.

## 13. What is not here

**No external signal sources.** No job feed, no funding feed, no
technology detection, no news monitoring, no scraping. Nothing in
`signals.py` calls anything. `SOURCES` names `provider` so a future
integration has a shape to fill.

Every account-level and person-level signal in the demo is **manual and
fictional**. See `PRODUCT-GAPS.md`.

Also absent: score history (today's answer only — "why was Acme 92 on
1 October" is not answerable yet), scheduled recalculation, and any
learning from outcomes.
