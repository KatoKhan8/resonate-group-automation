# Cadence length and sequence strategy: what was built, and what it refuses

The mission was to make Resonate able to test whether different outreach
*structures* perform differently — four steps against seven, email-only
against multichannel, one approach against another — as a second
experiment dimension, separate from message copy.

That is now possible end to end: an operator can put an experiment on a
campaign, preparing it assigns each account to an arm, the arm decides
what is actually built and sent, and eight modules measure what happened
without any of them being able to talk itself into a verdict.

The most useful thing in this document is not the list of what was built.
It is [what the system refuses to say](#what-it-refuses-to-say), because
almost every way a cadence experiment produces a confident wrong answer is
a place where the honest answer is "not yet".

---

## The chain, and where it was broken

    experiment -> assignment -> step selection -> copy variant ->
    approval -> payload -> confirmed send -> event -> reply ->
    attribution -> report

Every link is now consumed, and there is a test for each. Three were
broken when the mission started, all the same shape: **the system computed
the right thing and nothing downstream read it.**

| Link | What was wrong | Fixed in |
| --- | --- | --- |
| experiment → campaign | `cadencearms.experiment()` had no caller. Eight modules read `campaign["cadence_experiment"]`; nothing wrote it. | `e7e40c7` |
| campaign → assignment | `cadencearms.assign` had no caller either. No contact was ever put in an arm. | `e7e40c7` |
| campaign → step selection | `cadence.build` takes the campaign; one call site of thirty-five passed it. The arm reached one preview screen. | `a3e6db5`, `5dcadfd` |
| step → copy variant | `variants.apply_to_step` had no caller. No step carried a `variant_id`, so no confirmed touch could, so every copy experiment reported INSUFFICIENT_DATA for ever. | `1e30d69` |

The last one is worth stating plainly: an evaluator reporting
INSUFFICIENT_DATA because nothing ever wrote the field it reads is
indistinguishable, on screen, from an evaluator honestly waiting for
volume.

---

## What was built

### The sequence is a property of the campaign

`cadence.STEPS` was a module constant — seven steps, fixed days, for every
campaign in every workspace. Cadence length was not a variable in this
system, which an experiment comparing four steps against seven needs it to
be. `cadence.steps_for` resolves it. A campaign without one behaves
identically; a test builds the whole timeline both ways and compares.

### Arms

`src/cadencearms.py`. An experiment is a set of arms and a split.
Assignment is hashed rather than drawn, so the same account resolves the
same way on every read in every process; the experiment id and the
allocation version are both in the hashed material, so one account is not
placed in the same relative position in every experiment it joins, and a
recorded assignment can say which regime produced it.

The **account** is the unit by default. Two people at one company are not
two observations: a reply from one pauses the other, and fatigue counts
them together.

Shares renormalise across the arms a contact is actually eligible for,
without which somebody ineligible for the early arms lands on the last one
purely because the buckets above it are unreachable.

### Exposure

`src/cadenceexposure.py`. The invariant the layer exists for:

> A contact assigned to a seven-step arm who replies after three confirmed
> steps must never be reported as having received seven.

Assignment is not exposure, and a planned step is not a touch. Only
confirmed touches on *this arm's own step keys* count — a confirmed touch
on a key the arm does not contain came from a different sequence, and
crediting it borrows another campaign's history.

Terminations are split into `outcome` and `safety`, because a reply and a
removal request end a sequence for very different reasons and dropping
either observation biases everything.

### Maturity

`src/cadencematurity.py`. A four-step arm finishes on day twelve and a
seven-step arm on day thirty-five. Compared on day fifteen the short arm
has had every chance it will ever get while the long one has had two
thirds of one — and the short arm wins, on a difference that is entirely
an artefact of when somebody looked.

Maturity is per arm and the experiment is as mature as its slowest. Time
is counted from each contact's **own assignment**, because an experiment
started six weeks ago may hold a contact assigned yesterday. A sequence
that ended is finished whatever the calendar says: somebody who replied at
step three is not waiting for step seven.

### Reply attribution

`src/cadencereplies.py`. A reply is attributed to the last confirmed touch
*before its own timestamp* — not the last confirmed touch overall. A step
can be confirmed after somebody has answered, and the direction of that
error is what makes it worth a guard: a late confirmation always attaches
to a later step, so the bias runs towards making long arms look better,
which is the exact question being settled.

A reply with no confirmed touch before it is reported as unattributed,
never credited to step one.

### Incremental step value

`src/cadencevalue.py`. "Seven steps got 34 replies, four got 29" cannot
tell apart a world where steps five to seven earned five replies from one
where they earned none. The marginal number is what decides whether to run
three more steps.

Each step's rate is over the people who **reached that step**. Dividing by
the whole arm makes every sequence look like it decays, because the
denominator stands still while the population shrinks. Every row after the
first states what it is conditional on: the people who reach step five are
exactly the people who did not reply to steps one to four, and that
conditioning is the decision rather than a bias to remove.

### Safety and fatigue

`src/cadencesafety.py`. What the cadence cost the people who received it:
removal requests, stops, account suppressions and negative replies, shared
across one denominator so somebody who replies negatively and then
unsubscribes is one person harmed rather than two. Bounces, holds and
drops are counted separately as context — a bounce is a fact about an
address, and folding it in would let list quality masquerade as fatigue.

### The report

`src/cadencereport.py` assembles the five and computes nothing of its own.
The statistical question is answered by `variants.evaluate`, the same
evaluator the copy experiments use, through an adapter built at read time
— one set of Wilson intervals, one set of thresholds, one place to correct
a mistake in either. Thresholds may be raised for cadence under
`cadence_experiments`, because an arm needs more people than a wording
does.

---

## What it refuses to say

Each of these is a test, and each was mutated to prove the test bites.

**It will not compare arms that have not had time to be compared.** A
verdict is never actionable while any arm is immature, whatever the
intervals say. There is a test that watches the evaluator find a
statistically clean winner on day fifteen and then asserts the report
refuses to act on it.

**It will not call a winner on overlapping intervals.** Four replies
against three is `no_clear_winner`, which is the truthful answer and the
one a rosette would hide.

**It will not read an empty column as evidence.** Zero replies after step
six means the step earns nothing, or that nine people reached it. Below a
minimum reach a step is `too_few` and never `no_evidence`, and one
`too_few` after a candidate settling point means there is no settling
point yet — only a question nobody has the data to answer.

**It will not net a cost against a return.** There is no score combining a
reply with an unsubscribe, and a test asserts no field is ever added that
looks like one. That number would be the most useful-looking output in
this codebase and the one most likely to burn a sending domain, because
whoever read it would stop looking at the two columns underneath.

**It will not let a leader that costs more be a winner.** The safety
comparison is a veto, not a footnote.

**It will not guess an arm.** A record in two live campaigns resolves to
no campaign rather than to one of them; an assignment naming an arm that
no longer exists resolves to nothing rather than to whichever arm is
first; a sequence read with no campaign assigns no copy variant, because
an assignment that cannot name its experiment cannot be reported.

**It names every refusal.** A report that says "no clear winner" without
saying whether that is for want of time, for want of people, or because
the arms genuinely perform alike gets read as the last of the three — and
the first two are recoverable while the third is not.

---

## What was found on the way

Seven defects, all in code that already existed and all of the same
family. Six were fixed; the seventh is documented.

1. **The campaign never reached the send path.** The approval fingerprint
   of a four-step campaign and a three-step campaign were identical, digit
   for digit — so the cadence was not a launch-sensitive fact, and an
   operator previewing four steps would have had seven fingerprinted and
   sent.

2. **The last gate before a payload skipped every campaign-level guard.**
   `eligibility._campaign` returns None when there is no campaign, and
   nothing on the payload path passed one — so the freeze, the rejection,
   the already-launched check, the approval, the staleness and the
   provider mapping were all inert at the one point the code calls "the
   last moment anything is cheap to stop".

3. **A four-step campaign's records could never reach `approved`.**
   `approvable_steps` enumerated the constant's seven, two of which nobody
   would ever draft, so the record never left `drafted` and the campaign's
   own launch gate never opened. One arm of a four-against-seven
   experiment could not have run at all, and the reason would have looked
   like a drafting problem.

4. **The copy experiment had no wire into drafting**, so every variant
   reported INSUFFICIENT_DATA for ever.

5. **The cadence experiment had no way to exist**, and no way to be
   joined.

6. **A live approval read as stale at the payload gate**, because the
   campaign-wide approval check was being handed a one-record world.

7. **`cadencegraph` is still never stored on a campaign.**
   `campaign["cadence_graph"]` is read by `campaignqa` and written by
   nothing. Documented in `PRODUCT-GAPS.md` rather than fixed: its node
   keys are its own, it contains branch, wait and stop nodes with no
   linear equivalent, and resolving a running step's node out of it needs
   a mapping that does not exist.

The test suite also gave up five gaps of its own under mutation, four in
the arms work and one that matters more than the rest: **the invariant
`cadenceexposure` is named for — a planned touch is not an exposure — was
stated in the docstring, in a comment and twice in the code, and asserted
nowhere.** Every fixture in that file created confirmed events only, so
removing both confirmation checks changed nothing.

---

## Verification

| | |
| --- | --- |
| Full suite | **4738 tests, OK** |
| Offline harness | **4738 tests, OK - nothing reached off this machine** |
| Mutation audit | **384/384 caught** |
| Mutations added this mission | 99 (57 new, 34 owed from earlier, 8 authoring) |
| Live sending | disabled, unchanged; nothing here needs a provider |

`tests/test_mutation_anchors.py` is new and asks in a second what the
audit answers in fifty minutes: does every mutation still match its file
exactly once. It found an entry that had been dead since a refactor
reflowed the line it was anchored on, and a second that matched twice and
was mutating the right line by ordering alone.

---

## What is not built

- **Nobody writes the five copy variants but an operator, by hand.** There
  is no authoring screen and no generator. `PRODUCT-GAPS.md` §3d.
- **There is no screen for cadence experiments.** Every module has a CLI
  (`python -m src.cadencereport --campaign <id>`) and none has a page.
- **`benchmark`, `simulator` and `demo_outreach` still measure the default
  cadence.** They are measurement and demo surfaces with no campaign in
  their call paths, and giving them a parameter nobody passes would be a
  wire that looks connected. `PRODUCT-GAPS.md` §11.
- **No experiment has ever run.** Everything above is proven against
  fixtures. The arms, the assignment, the exposure accounting and the
  report are all local and need no provider — but a real verdict needs a
  real campaign and time, and `LIVE-READINESS.md` is the document that
  says what may be promised.
