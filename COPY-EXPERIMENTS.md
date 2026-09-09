# Copy experiments

Five ways to say the same true thing, and a way to find out which works.

It is **not** five drafts for an operator to pick from. Picking by taste is
what the product did before, and taste is not evidence.

---

## 1. The data model

A variant is one **complete message**, not a subject or a body:

| Field | Means |
| --- | --- |
| `variant_id` | stable within its step |
| `style` | the hypothesis — see §2 |
| `subject` / `body` | email copy |
| `note` | LinkedIn copy |
| `status` | `active` / `paused` / `retired` |
| `version` | bumped when the copy changes materially |
| `allocation` | share of traffic, normalised at read time |

Variants live on the campaign's step spec (see §10), so there is no
second store and nothing new to keep in step.

Complete variants rather than a factorial of parts: five subjects × five
bodies is 625 cells, none of which anybody has the traffic to settle.

## 2. Style is the finding, not the letter

A variant is "short and direct", not "B". The letter generalises to
nothing; the approach generalises across steps, campaigns, and eventually
a workspace's whole history.

**Email:** short and direct · casual · professional · consultative ·
problem-led

**LinkedIn:** casual · short and direct · professional · consultative ·
peer-to-peer

`STYLES_FOR` is one table holding both the key and the sentence describing
it, so a style cannot be renamed in one place and not the other.

## 3. Which steps have experiments

`MESSAGE_NODES`: `email`, `connection_request`, `linkedin_message`,
`linkedin_followup`. A wait, a branch, a reply check, a handoff and a stop
carry no copy, and `variants.validate` blocks variants on them.

**Every message step runs its own experiment.** The winner on day 1 says
nothing about day 6 — different message, different state.

Five is the supported minimum, not a cap. Fewer warns; more is fine.

## 4. Assignment

`assign()` is a pure function of `(campaign, step, contact, allocation
version)`, hashed. So:

- the same planned touch resolves the same way on every read — a page
  refresh cannot move somebody from A to D
- each step assigns independently, so one contact is not placed in the
  same relative cell of every experiment, which would silently correlate
  every step's results
- traffic lands within a few percent of the configured shares

**One contact, one variant, per step.** Contact-level is the default unit.
Account-level cohorting is a deliberate non-goal for now and is noted in
`PRODUCT-GAPS.md`.

## 5. History is never rewritten

A **recorded** assignment outranks the function. `resolve()` prefers what
was actually sent, so shifting the allocation tomorrow moves future
traffic and cannot change who was in which cell yesterday — otherwise
every rate computed from it would be wrong.

The variant travels on the touch event (`variant_id`, `variant_style`), so
attribution reads what was sent rather than what would be assigned now.

## 6. The evaluator, and what it refuses

States: `exploring` · `insufficient_data` · `leading` · `winner` ·
`no_clear_winner` · `paused` · `completed`.

Checked in this order, and the order is the argument:

1. **Before the 10% checkpoint** → `exploring`, by policy not by data.
2. **Below 30 exposures per variant, or 8 outcomes total** →
   `insufficient_data`, whatever the rates look like.
3. **Leader's lower bound clears every other upper bound, and lift ≥ 30%**
   → `winner`.
4. Leader ahead but overlapping → `leading`.
5. Nothing separating them → `no_clear_winner`.

**Four replies against three returns `no_clear_winner`.** That is the case
the brief names and there is a test for it.

Wilson intervals rather than plain proportions, because a plain proportion
says a variant with one reply from one send has a 100% rate. Wilson pulls
that toward nothing, which is what the evidence supports, and it is a
closed form somebody can check.

Every threshold is workspace-configurable under `experiments`.

## 7. What we optimise for

`positive_replies` (default) · `replies` · `meetings`.

Opens and clicks are deliberately absent from `OBJECTIVES`. They are not
authoritative here, and a system that optimised for them would be
optimising for a proxy nobody asked for.

## 8. Traffic after a winner

A winner keeps **75%** by default, not everything. The rest stays with the
challengers, because a variant that stops being served stops being
measured, and an experiment that stops measuring cannot notice that its
winner has stopped working.

`winner_takes_all` exists on the node for workspaces that want it. It is
not the default.

## 9. Attribution

Three questions, kept apart:

| | |
| --- | --- |
| **exposed to** | this contact was sent this variant on this step |
| **last touch** | this variant was the last confirmed touch before the outcome |
| **journey** | every variant this contact saw, in order |

Rates use last-touch, because it is the only one with a denominator that
means anything. **This is a reporting convention, not a claim about
cause**, and the screen says so. The journey travels beside it so nobody
reads "variant E won" as "variant E did it alone".

**A planned touch is not an exposure.** Same rule as everywhere else in
the product, with its own test and its own mutation.

## 10. Safety is not a variant-level decision

`campaignqa` lints **every active variant separately**. A campaign does not
become approvable because variant A is clean while variant D fails — a
fifth of the audience receives the fifth one.

Findings name the step, the variant and the style, so the fix is
locatable. Recipient- and record-level codes are filtered out, because
they are not facts about the copy.

Claim safety is unchanged and still resolves per contact at preparation
time. **Style may change tone, length, structure, opening and call to
action. It may not change what is true.** A variant that wants to claim
more needs evidence, not a different style.

Variants are designed to slot into the existing gates rather than beside
them: `apply_to_step` puts the assigned copy into the step, and
`approval.fingerprint` already hashes exactly that — so editing a variant
would invalidate its approval by the rule that has always applied.

**That paragraph now describes a running connection.**
`cadence.expand_step` resolves the assigned variant for the contact and
calls `apply_to_step`, so the present tense used everywhere else in this
file is finally earned. It was a design for two missions before it was a
behaviour.

What *is* connected, as of the pilot-hardening pass: a step that carries a
variant has it recorded onto the confirmed-touch event, so
`variants.journey_of` and `results_from` can count it. Before that,
`account.touches` read `variant_id` off events that nothing ever wrote it
to - every journey was empty, every tally was `{}`, and every experiment
reported `INSUFFICIENT_DATA` no matter what had been sent. That looked
exactly like a working evaluator waiting for volume. See
`tests/test_variant_attribution.py`.

### Where the variants live

On the campaign's step spec, under `variants`, beside `template` and
`variant_if_accepted` - which is where a sequence already keeps the
question of which words a step uses. Assignment is sticky on what the
stored step recorded, so approving a draft fixes the variant as well as
the words, and a later traffic shift cannot rewrite who was in which cell
yesterday.

Two refusals, both deliberate:

- **A generated step may not carry variants.** Its copy was written for
  that contact by phase 5; a variant would replace it wholesale, which is
  not a variant of anything. `validate_steps` raises.
- **A sequence read with no campaign assigns nothing.** An assignment that
  cannot say which experiment it belongs to cannot be reported, and an
  unreportable assignment is worse than none.

`src/cadencegraph.py` also holds variants, on its nodes. That model is not
the one that executes: its keys are its own (`d1`, `d3`), it contains
branch, wait and stop nodes with no linear equivalent, and it is still
never stored on a campaign. Resolving a running step's node out of a graph
needs a mapping that does not exist, and building one was not worth doing
to avoid putting variants where the executor already looks.

What is still missing is the *authoring*: nobody writes the five variants
but an operator, by hand, onto the campaign's steps. See PRODUCT-GAPS
§3d.

## 11. The screen

`/campaigns/experiments`, under Campaign. One panel per message step, led
by the **state** rather than by a leader, because the honest answer is
usually "not yet".

Every rate carries its pair (`14.8% 31/210`). A step whose traffic has
shifted says so and says why the challengers keep a share.

## 12. Demo

`src/web/demovariants.py` demonstrates all five states at once: a winner
with traffic already shifted, one leading, one with no clear winner, one
with insufficient data, and one still exploring.

**The totals are planted, and the module says so.** Putting four thousand
touch events into the demo estate to make one screen render would cost
more than the demonstration is worth. Every verdict, threshold, interval
and traffic share on the screen is computed from those totals by the
production code — only the totals are fictional, and the page says DEMO.
