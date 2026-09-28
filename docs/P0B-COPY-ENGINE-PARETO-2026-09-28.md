# P0-B — THE COPY ENGINE PARETO

**Claude, 2026-09-28. Branch `task-p0b-copy-engine-pareto`.**

Every claim below carries CLAIM / AUTHORITY / MEASURED AT / STATE. A test count
is never a PASS.

---

## 0. THE HEADLINE, INCLUDING THE PART THAT DID NOT WORK

**CLAIM.** The dominant upstream cause of the 18 refusals is fixed — its share
of failures fell from ~35% to ~0.5% — and a second cause I created was found and
fixed. **The contact under test still does not get copy through, and the reason
has changed:** the blocker is now the CLAIM family, and for THIS contact
specifically it is a structural conflict between two correct gates on a
four-fact pack (§10).
**AUTHORITY.** Five real-model runs of `scripts/task425_one_account_dry_run.py`
on this branch, `--invocations 1` (production retry limit, no manual help),
against frozen source (`work/p0b_source_frozen.txt`).
**MEASURED AT.** 2026-09-28, `work/p0b-final-{1..5}.json`.
**STATE.** PARTIAL — named causes fixed and proven; the contact under test is
NOT unblocked.

**I am not reporting this as a pass.** The contact under test reached copy in
**0 of 5 runs** on the final source. Other contacts on the same account did:
runs 2 and 4 stored 10 and 20 steps. The pre-existing measurement was 3 of 5,
1 of 5 and 2 of 5. Those numbers are **not comparable**, and the reason matters
more than either of them:

> **The bar is now strictly higher.** The same run must produce **10 steps
> instead of 9** (`li5` was silently dropped before), must produce a **P.S.**
> (silently dropped before), is judged by the **sequence gate inside the retry
> loop** (previously read by nobody in production), and is judged by a **new
> figure gate** that refuses invented benchmarks. More required content and
> more gates read means more ways to fail, so a flat pass rate against a raised
> bar is not a flat result — but it is also not the improvement the task asked
> for, and I am not going to present it as one.

---

## 1. THE 18-ROW FAILURE MATRIX

**A NOTE ON WHAT "18" IS, because the honest answer is not one run's 18 drafts.**
The 10:19Z run's eighteen refused drafts (6 invocations × 3 attempts) have no
per-draft text in any artifact — `docs/TASK-425-FINDINGS-2026-09-28.md` names
their seven failure CLASSES and no more. What
`docs/TASK-425-ONE-ACCOUNT-DRY-RUN-ARTIFACT.md` does carry verbatim is **7
refused drafts across c1/c2/c3** with full rejection text. The matrix below is
therefore over the **18 distinct failure SIGNATURES** observed across both —
which covers all seven named classes and is the unit a fix can actually act on.
Counts are instances in the verbatim artifact data.

| # | Failure | Count | Stage raised at | Upstream cause | Is regeneration the right response? |
|---|---|---|---|---|---|
| 1 | `step_objectives` coverage — "pursues none of the offer's step objectives: rung 5 is 'reframe and close'" | 3 | `sequencegate.check`, whole-sequence | Writer had the objectives as a JSON blob in `plan_json` but was never told the gate measures **lexical** coverage per rung, threshold exactly zero. Rung 5's stems are `refr`/`clos` — the email's rhetorical *move*, not its subject | **NO — fix upstream.** Every retry was a fresh roll of the same blind dice. FIXED |
| 2 | `step_objectives` order — "carries rung N's vocabulary while rung N's own step carries NONE of it, 50% against 0%" | 5 | `sequencegate.check` | Same blindness. "close"/"move" are ordinary English, so any step using them steals another rung's distinctive vocabulary | **NO — fix upstream.** FIXED |
| 3 | `channels_complement` — "asks a question email already asked" | 2 | `sequencegate.check` | The complementarity rule was never stated to the writer | **NO — fix upstream.** FIXED (partially; see §5) |
| 4 | `channels_complement` — "is em5 in shorter form" | 2 | `sequencegate.check` | Ditto. The closing LinkedIn message and the breakup email want to say the same thing | **NO — fix upstream.** FIXED (partially) |
| 5 | `repetition_across_rungs` — all five emails repeat each other | 5 | `quality.gate` via `generate._quality_of` | Attempt 2's reaction to being told "stop repeating" with no memory of attempt 1 | **NO — fix upstream** (feedback amnesia). FIXED |
| 6 | `followup_adds_value` — "repeats em3: 55% of its argument is the same" | 1 | `sequencegate.check` | Same distinctness blindness | **NO — fix upstream.** FIXED |
| 7 | `claims.check` — "'margin' is asserted about them and nothing stored supports it" | 1 | `generate._step_refusals` → `claims.check` | Capability sentence (a product description) restated as a second-person finding about the prospect | **NO — fix upstream** (grammar rule). FIXED in prompt; still dominant — see §5 |
| 8 | `claims.check` — "'raised' is asserted but nothing stored mentions it" | 1 | same | Same family, `EVENT_WORDS` branch | **NO — fix upstream.** Same |
| 9 | `untraceable_company_claim` — "a claim about the company is not traceable to a pack fact" | 1 | `copylint.check_batch` | Writer reaching beyond a four-fact pack | **NO — fix upstream**, and partly a SOURCING problem. NOT FIXED |
| 10 | `claims_supported` — "a specific claim traces to no supplied fact" | — | `sequencegate.check` (delegates to `copylint.untraceable`) | Same as 9 | **NO.** NOT FIXED — now the single largest cause |
| 11 | `empty_step` — "one of the 5 steps is empty" | 1 | `copylint.check_batch` | The writer emptied steps after being told "stop repeating" | **NO — fix upstream** (feedback). FIXED |
| 12 | `body_too_short` — "the body is under 40 words" | 2 | `lint.check` | Same cause as 11 | **NO — fix upstream.** FIXED |
| 13 | `unrendered_variable` — "a merge field or template variable survived into the body" | 1 | `copylint.check_batch` | Model slip | **YES — regenerate.** A retry fixes this and the gate is right |
| 14 | `placeholder` — "you left an unfilled placeholder in brackets" | 1 | `lint.check_linkedin` | Model slip | **YES — regenerate** |
| 15 | `buzzword` — "a buzzword or banned phrase" | 1 | `copylint.check_batch` | Model slip | **YES — regenerate.** `lint.explain` names the phrase |
| 16 | `dash` — "a dash used as punctuation" | — | `copylint.check_batch` | `normalise_punctuation` rewrites `—` to `" - "`, which `DASH_RE`'s `\s-\s` arm then catches | **YES — regenerate**, but see §6: this is a self-inflicted collision worth a look by the lint owner |
| 17 | `note_too_long` — note over the connection-request limit | — | `lint.check_linkedin` | **GATE INPUT DEFECT.** `lint.is_connection_note` tests `requires != "connection_accepted"`; `cadencelibrary` declares `"connected"`. So `li2`–`li5`, which are MESSAGES, are capped at 300 chars as if they were connection requests | **NO — the gate is applying the wrong rule.** NOT FIXED, deliberately — see §6 |
| 18 | **The gate that did NOT fire** — an invented figure in an impersonal sentence passes BOTH claim gates | 0 refusals, 3 fabricated quantities shipped | — | `claims.is_claim` discards the sentence before the numeric test; `copylint.untraceable` skips any sentence not matching `COMPANY_CLAIM` | **NEITHER — the gate had to be made to fire.** FIXED |

---

## 2. CRITERION 4 — THE VERIFIER CERTIFIES FIELD PRESENCE. CONFIRMED.

**CLAIM.** `scripts/task425_criterion4_completeness.py` certifies that a field
LABEL appears in rendered markdown. It never reads the field's value, and
cannot tell "no claim was made" from "a claim was made and not licensed".
**AUTHORITY.** The source on `origin/task-425-one-account-dry-run` @ `2d54e274`.
**MEASURED AT.** 2026-09-28. **STATE.** CONFIRMED — the operator's downgrade of
criterion 4 to UNPROVEN is correct.

Line 104 is the whole finding:

```python
absent = [f for f in PER_MESSAGE if f not in block]
```

`PER_MESSAGE` is a tuple of label strings (`"EXACT CLAIM LICENSED"`, …) and
`block` is the rendered markdown. It is a substring test for the label. A field
rendering `(none)`, or rendering nothing at all, counts as PRESENT.

**The docstring claims the opposite and is false:** *"A field whose value is a
placeholder counts as ABSENT … the two are told apart by looking at what the
run recorded rather than at the rendered text."* No value is ever extracted;
the only thing read is the rendered text, and only for the label.

**Defects 4 and 5 are its symptoms, and they share one root.** All nine messages
render `EXACT CLAIM LICENSED (none: this step asserts no specific about them)`
while `em4` asserts `60%`, `90%` and `three times`. That string is emitted when
`licensed` is empty, and `licensed` is built behind the same
`COMPANY_CLAIM` filter — so **three different situations collapse into one
affirmative-sounding line**: the step genuinely asserts nothing; the specifics
sit in an impersonal sentence and were never examined (this case); or specifics
failed to trace and landed in `unlicensed`. Only the first matches the words.

The artifact's own two adjacent fields say it outright:
`"specifics_in_copy": ["60%","90%","60","90"]` beside
`"untraceable_specifics": []`. The first is ungated, the second is gated. They
are printed side by side as if the second were a filtered subset of the first.

**I did not modify that script** — it is another agent's file. The finding is
handed over.

---

## 3. THE FIVE OPERATOR DEFECTS

| # | Defect | Root cause, in the code | State |
|---|---|---|---|
| 1 | No P.S. on em1/em3, anywhere | `generate._candidate_steps` built a step dict of four keys and none was the P.S.; `generate_campaign` harvested it with `if ps_text:` and silently dropped an empty one | **FIXED** — P.S. carried onto the step; an absent one is a refusal |
| 2 | `li5` renders nothing, 4 of 5 | `_PLAN_LINKEDIN_ORDER` held 4 writer keys against a cadence declaring `li1`–`li5`; `_candidate_steps` hit `n >= 4` and `break`, silently | **FIXED** — writer asked for a 5th note (`msg4`), `li5` maps, and an unfillable step now BLOCKS |
| 3 | Thread discrepancy A/A/B/B/C vs `[false,true,true,true,true]` | `generate._PLAN_SUBJECT_OF` was a third, unsourced opinion | **FIXED** — see §4 |
| 4 | `em4` asserts 60% / 90% / "three times" | `claims.is_claim` discards impersonal sentences before the numeric gate; `copylint.untraceable` skips non-`COMPANY_CLAIM` sentences | **FIXED** — see §7 |
| 5 | Messages refer to prospect specifics while licensed-claim fields are empty | Same root as defect 4 plus the criterion-4 verifier of §2 | **EXPLAINED**; verifier not mine to change |

---

## 4. ISSUE-054 — THE CANONICAL CADENCE IS ONE THREAD

**CLAIM.** One thread is canonical. `generate._PLAN_SUBJECT_OF` was the only
representation that disagreed, and nothing endorsed it.
**AUTHORITY, in order.** `docs/OPERATING-MODE.md` §17 — operator, Zvonimir,
2026-09-28: *"Same subject across one thread is correct threading."*
`docs/ONLY-THE-OPENER-OWNS-A-SUBJECT-2026-09-16.md` — operator-verified in the
EmailBison UI. `docs/EMAILBISON-COPY-REQUIREMENTS.md` §1 — "a sequence is one
conversation". `config/clients/productive.yaml:629` —
`thread_reply_pattern: [false, true, true, true, true]`.
**MEASURED AT.** 2026-09-28. **STATE.** CORRECTED.

**What the provider is actually told**, via `sequenceplan.derive_bison_sequence`:
five steps, every one carrying `{SUBJECT_1}`, `thread_reply` true on 2–5. **One
distinct subject.** `bisonfactory._variables_for` then blanks `subject_2..5` and
`_stale_clearances` wipes leftovers.

**So subjects B and C were generated, linted, gated, approved and fingerprinted
— and then silently discarded before the wire.** The copy engine was spending
gate attempts on two subjects no prospect could receive, and
`no_repetition/subjects` was comparing them against each other.

**The correction is DERIVED, not pinned.** `_plan_subject_of(sequence, config)`
reads the same authority `sequenceplan` reads, so a client that genuinely opens
three threads still gets three (asserted in
`test_a_client_that_really_opens_three_threads_still_gets_three`). An unknown
pattern falls back to one thread, because the threading invariant refuses a
follow-up carrying a distinct subject — guessing "new thread" would manufacture
copy that `sequenceplan` then refuses.

**Nothing verified this before and that is why it survived.** Grep for
`_PLAN_SUBJECT_OF` returned its definition, one use, and a comment. No gate, no
test, no report compared the generator's thread count with the projection's.

---

## 5. WHAT I FIXED, AND THE MEASURED EFFECT

All in `src/generate.py`, `src/generate_campaign.py`, and the writer contract in
`src/copystages.py`.

1. **The ladder brief** (`_ladder_brief`) — names each rung against its own step
   and states the lexical rule the gate applies. Empty for a client with no
   declared objectives, so `offers.py` being single-tenant cannot impose
   Productive's spine on anyone else.
2. **The cumulative retry block** (`_cumulative_retry_block`) — every earlier
   refusal, deduplicated, plus *"anything not named was acceptable"*. Replaces
   `RETRY_BLOCK % rejected[-1]`, which told attempt 3 nothing about attempt 1.
   **"Do not patch the old one" stays** — decision 1 is not traded for
   convergence.
3. **The sequence gate is read inside the retry loop** — scoped to `offer is not
   None`, i.e. the client whose approved offer this run resolved. This answers
   the single-tenancy objection recorded in that file rather than waiving it. It
   can only refuse MORE copy than before.
4. **Missing required content BLOCKS** — `missing_required` +
   `_content_shortfall`, distinguishing a `contract` shortfall (unsatisfiable by
   retry) from an `empty` one (satisfiable).
5. **The channel brief and the claim brief** — the complementarity rule and the
   assert-about-them-vs-about-the-product grammar.
6. **`_PLAN_SUBJECT_OF`** — §4.
7. **`_invented_quantities`** — §7.
8. **The repetition comparison reads BODIES, not `subject + body`** — an input
   correction I had to make because *my own* one-thread fix created the bias.
   Under three threads the subject carried information; under one thread it is
   identical on every step by construction, so it added a constant to all ten
   pairwise comparisons. Measured on HARBOURLINE em1/em3: 44.4% with different
   subjects, **exactly 50.0%** with the same one — the threshold — and 43.8% on
   bodies alone. `repetition_across_rungs` became the largest cause of refusal
   (60 instances across 4 runs) until this landed; it is 15 now. **The rule and
   the 50% threshold are untouched**, and the positive controls in
   `TheRepetitionGateMeasuresWhatTheStepsSay` show it still fires on identical
   bodies and on a genuinely repetitive pair.

**MEASURED EFFECT, and it is mixed.**

| | Source artifact | This branch, 5 runs, frozen source |
|---|---|---|
| `step_objectives` share of failures | 8 of 23 (~35%) | **1 of 188 (~0.5%)** |
| `repetition_across_rungs` | 5 of 23 | 60 of 256 → **15 of 188** after §5.8 |
| Claim family share | 3 of 23 (~13%) | **~70 of 188 (~37%)** |
| `li5` rendered | never | every stored contact (10 steps, not 9) |
| Contact under test through | 3/5, 1/5, 2/5 | **0 of 5** — against a higher bar |
| Any contact stored | — | 2 of 5 runs (10 and 20 steps) |

**The Pareto moved.** The dominant cause is fixed; the new dominant cause is the
claim family, and it is **not** primarily a prompt defect: the pack has four
facts, `_traces` requires a pack sentence containing the specific AND sharing
≥2 content words, and a writer asked to personalise five emails and five
LinkedIn messages from four facts will reach past them. **That is the gates
working correctly on a thin pack.** The fix is more admitted evidence per
account, not a looser gate, and I did not loosen one to improve the number.

---

## 6. GATES I DID NOT TOUCH, AND WHY — SAID LOUDLY

**`src/sequencegate.py`: NOT MODIFIED.** No rule, threshold or input changed. I
did change **what `generate_campaign` passes it**, in one place, and it is an
input correction with an authority: `subjects` now goes per-step with a
`threads` map, instead of the writer's `{A,B,C}` with no map. The module's own
comment prescribes exactly this shape and makes the per-thread path WARN
("there was only one subject to look at") rather than pass silently — so this
cannot be used to switch the check off.

**`src/lint.py` note-vs-message cap: NOT FIXED, DELIBERATELY.**
`lint.is_connection_note` compares `requires` against `"connection_accepted"`;
`cadencelibrary` declares `"connected"`. Two vocabularies for one concept, so
every `li2`–`li5` **message** is capped at 300 characters as if it were a
connection request, and `li2: the note is too long for a connection request`
refused contacts on my own proof runs. **I believe this is a false refusal.**
I did not fix it because **the fix relaxes a cap** — from 300 to
`MESSAGE_MAX_CHARS` (1900) for every client — and NEVER LOOSEN A GATE outranks
convergence even where the loosening looks correct. It needs the owner of
`lint.py` and an operator who wants that cap moved. What I did do is propagate
the cadence's own `requires` onto the generated step, which is
**behaviour-neutral today** (the strings still differ) and makes the data
correct for the day the vocabularies are reconciled.

**`copylint.DASH_RE` vs `lint.normalise_punctuation`: REPORTED, NOT TOUCHED.**
Normalisation rewrites `—` into `" - "`, and `DASH_RE`'s `\s-\s` arm then
refuses the result. The comment says this is deliberate so the tell survives
normalisation; it also means the pipeline can create the offence it then
refuses. Flagged for the lint owner.

**`claims.py` / `copylint.py`: NOT MODIFIED.** ISSUE-050 stays open in them —
see §7 for why the fix went into the generator instead.

**`tests/task425fixture.py`, `docs/TASK-425-*`, `docs/OPERATING-MODE.md`,
signature/sender modules: NOT TOUCHED.**

---

## 7. ISSUE-050 — THE GATE THAT SHOULD HAVE FIRED, MADE TO FIRE

**CLAIM.** The numeric refusal already existed and was correct. Only its input
selection was wrong. It now fires, in the generator, without modifying either
claim gate.
**AUTHORITY.** `src/claims.py:563-568`; `tests/test_the_copy_engine_converges_and_still_refuses.py`.
**MEASURED AT.** 2026-09-28. **STATE.** FIXED on the copy path; ISSUE-050 stays
open in `claims.py`/`copylint.py`.

The proof that this is an **inputs** defect and not a missing rule — handed the
sentence directly, the existing gate refuses it:

```
claims.check(em4_body, rec, contact)          -> []          # blind
claims.check_sentence(sentence, support)      -> (False, 'the figure 60 appears in no stored fact')
```

`claims.is_claim` returns False for the sentence (no second-person marker, no
event word) before the numeric test can run. `copylint.untraceable` `continue`s
on it for want of a `COMPANY_CLAIM` trigger word — and returns `[]` **against an
empty pack**, which is the clearest statement that the pack was never consulted.

`generate._invented_quantities` runs in `_step_refusals` on **every sentence**.
It does not modify `claims.py` or `copylint.py`, so no other caller's verdict
moves and no stored lead is re-judged — the same shape as the `CLIENT_SUPPLIED`
decision's "pack path and only the pack path".

### CAN IT STILL FAIL, AND ON WHAT INPUT?

| Input | Verdict |
|---|---|
| `"...at 60% budget burn versus 90% have three times the impact..."` (real em4) | **REFUSED** on 60, 90 and "three times" |
| `"Agencies like yours typically recover 15% of lost margin."` | **REFUSED** — 15 in no stored fact |
| `"Early intervention has double the effect."` | **REFUSED** — worded quantity |
| `"You moved to 2 week delivery cycles"` (pack says 2) | **PASSES** |
| `"Since 2016 the healthcare practice..."` (pack says 2016) | **PASSES** |
| `"Worth a 5 minute look?"` | **PASSES** — one-character figures exempt, matching `claims`' own `len >= 2` |
| no figure at all | **PASSES** |

It fired on **real generated copy** in the proof runs — figures 40, 32, 65, 48,
25 — all fabricated benchmarks that would previously have shipped.

**Every other gate I touched still fails on the inputs it always did.** The
changes are additive (a gate's verdict starts being read; a missing step starts
refusing; a new figure check) or input corrections with an authority. None
removes a rule or moves a threshold.

---

## 8. PROVIDER WRITES

**CLAIM.** Zero provider writes across every run.
**AUTHORITY.** The harness's `Wire` interceptor on the transport chokepoint,
fired deliberately once per run.
**MEASURED AT.** 2026-09-28, all 5 runs. **STATE.** PASS.

```
provider requests: 0
trap_generation: fired=True,
  "POST https://api.emailbison.com/api/campaigns reached the transport.
   This run performs zero provider writes and zero provider reads"
killswitch: sending=False, "sending.live is off for productive"
```

Model calls went to `openrouter.ai` only, which is the one allowed host.

---

## 8b. REGRESSION — ZERO NEW FAILURES ON THE AFFECTED SURFACE

**CLAIM.** Every test module that touches the code this branch changes is
green except for failures that are already in the baseline. Zero new failures.
**AUTHORITY.** `docs/state/SUITE-BASELINE-2026-09-26.txt`, 128 distinct failing
names, compared AS A SET rather than as a count.
**MEASURED AT.** 2026-09-28, `work/slice.py` over the 66 modules that import
`generate`, `generate_campaign`, `copystages`, `quality`, `sequencegate`,
`copylint`, `claims` or `lint`.
**STATE.** PASS on the affected surface; the FULL suite is a separate line
below and is NOT claimed.

    modules requested : 66      tests run : 1532
    failures          : 10      errors    : 0
    all 10 present in the 2026-09-26 baseline; NEW failures: 0

**One new failure was found this way and fixed, not argued away.**
`test_task400_rework3 ... test_changing_the_writers_subject_changes_the_approval_queue`
asserted that `day15` carries subject B and that changing B changes the
approval queue. Under the ruled one-thread cadence B reaches no step and is
blanked before the wire, so changing it proved nothing. It now drives subject
A — the one that ships — and additionally pins the one-thread property itself.
The same correction was made to the finality falsifier in
`test_only_the_last_subject_may_claim_finality`.

### The full suite, and the set diff that found the other one

**CLAIM.** The full run named 6 failures absent from the 2026-09-26 baseline.
**Four are inherited from the 425 merge and are not mine; two were mine and both
are fixed.**
**AUTHORITY.** `work/setdiff.py` over `work/p0b_failing.txt` vs the baseline, as
SETS. **MEASURED AT.** 2026-09-28, 13,652 tests in 2440s, 123 distinct failing
names against a baseline of 128. **STATE.** RESOLVED.

**The count was not the signal and would have misled.** 123 against 128 looks
like an improvement; the set diff shows 6 in and 11 out.

**How the four were proven not mine** — this is the measurement, not an
argument. The three source files were replaced with their merge-commit
(`42a5c5e0`) versions, the suspects were run, and the files were restored and
verified byte-identical against the frozen sha256s:

| Failure | At merge commit, my source reverted |
|---|---|
| `fixture_hygiene ... every_email_address_is_on_a_reserved_domain` | **already fails** |
| `fixture_hygiene ... no_real_client_prospect_or_roster_domain` | **already fails** |
| `an_offer_cannot_be_invented ... approval_status_is_not_defaulted_to_approved` | **already fails** |
| `the_cadence_reacts_to_what_the_prospect_did ... the_meeting_reaches_the_send_gate_too` | **already fails** |
| `the_research_pack_has_one_shape ... the_literal_acceptance_call_produces_copy` | **passes → MINE** |

They also name files this branch does not touch — `productive-offers.yaml`,
`docs/qwen-tasks/DONE/`, `cadencelibrary.py`. **The 09-26 baseline predates the
425 work now on master, so it is stale for anything that merge introduced;**
these four belong to whoever owns those files.

**The one that was mine was my in-loop gate read working as designed.** It is
the only test in its file passing the client as the literal name `"productive"`,
so the tenant matches and Offer B's approved spine applies — and
`CampaignModel()`'s default copy predates the ladder entirely. Its fixture now
follows the ladder rung by rung. The other tests in that file go through a
config whose client is not `productive` and the ladder is reported UNCHECKED
rather than borrowed, **which is the tenancy scoping of §6 working.**

**11 baseline failures did not reproduce here** (`test_a_resume_leaves_a_ledger_row`
×5 — which the baseline itself flags as pre-existing red — plus `test_e2e` ×4
and two others). They are environment-dependent, not fixed by this branch, and
are NOT claimed as improvements.

A final full run on the frozen source is in flight; the source has not changed
since the freeze, so only the two test outcomes above move.

---

## 10. WHY c1 SPECIFICALLY IS THE HARDEST CONTACT ON THIS ACCOUNT

**CLAIM.** The contact the causal matrix is driven on sits in a narrow corridor
between two gates that are each correct, and the corridor is narrow because the
pack has four facts and none of them mentions margin.
**AUTHORITY.** `config/clients/productive-offers.yaml` `step_objectives`;
`src/claims.py` `asserts_about_them` + `evidence.OPERATIONAL_TERMS`; the pack in
`docs/TASK-425-ONE-ACCOUNT-DRY-RUN-ARTIFACT.md`.
**MEASURED AT.** 2026-09-28. **STATE.** REPORTED, not fixed.

c1 is a Managing Director, so the persona resolves `OFFER-A-ECONOMIC-BUYER`,
whose ladder is **margin visibility / quote versus burn / resource decisions
that move margin / Report Intelligence / reframe and close**.

- `sequencegate.step_objectives` requires em1 and em3 to carry that
  vocabulary — including **margin** — at their own step.
- `claims.asserts_about_them` refuses **margin** (an `OPERATIONAL_TERMS` entry)
  in any second-person sentence unless a STORED fact contains the word.
- **No fact in this account's pack contains "margin".** The four facts are
  2-week delivery cycles, an Amsterdam agency with a 2016 healthcare practice,
  retained monthly engagements, and a delivery-lead hire.

So every em1 and em3 must name margin, and may never assert margin about them.
The only legal forms are a question, an `if`/`whether` hedge, or a sentence
about what Productive does — which is exactly what `CLAIM_BRIEF` now tells the
writer. It is a real corridor and the model threads it only sometimes.

**This is not a copy-engine defect and it must not be fixed by loosening
either gate.** Both are behaving as designed and the operator approved the
ladder. The two clean exits are **more admitted evidence for this account**
(a fact that mentions margin, quoting or budget makes the corridor wide), or
an operator decision that the economic-buyer ladder may be pursued for a
prospect whose pack cannot support its vocabulary. The second is a claims
decision, not a wiring change, and it is not mine to take.

---

## 9. WHAT IS STILL OPEN

0. **⚠ BLOCKING FOLLOW-UP, AND IT IS CREATED BY MY OWN CHANGE.**
   `sequenceplan.derive_heyreach_payload` (`src/sequenceplan.py:190`) iterates
   `("connect", "msg1", "msg2", "msg3")` and harvests with `if text:`. I added a
   fifth LinkedIn message (`msg4`), so **`msg4` is generated, linted, gated,
   stored and then silently dropped from the HeyReach projection** — which is
   precisely the subjects-B-and-C pathology documented in §4, recreated one
   channel over. `src/sequenceplan.py` is not a file I own, so I have not
   changed it. **The one-line fix is to add `"msg4"` to that tuple**, and until
   it lands the fifth message reaches the record and not the provider.
   Note the same four-key assumption also sits in `src/copyprompts.py:394`,
   `src/copystages.py:247` and `src/skills/linkedin_writing.py` (the last is
   inert today — `_process_contact` uses the EMAIL skill's `procedure` as the
   writer system prompt and the LinkedIn skill is loaded but not used for it).

1. **The claim family is the new dominant cause** (~47%), driven by a four-fact
   pack. Needs more admitted evidence per account, not a looser gate.
2. **ISSUE-050 remains open in `claims.py` and `copylint.py`.** Closed on the
   copy path only.
3. **The `connected` / `connection_accepted` vocabulary mismatch** caps LinkedIn
   messages at 300 chars. Needs the `lint.py` owner. §6.
4. **Criterion 4's verifier** certifies field presence. §2. Not my file.
5. **The harness's `sequence_gate_validator` bolt-on is now redundant** with the
   in-loop read and double-reports sequencegate failures. Harmless (the
   cumulative block deduplicates) but it inflates rejection counts.
6. **The writer still produces `subject_alt` and `subject_breakup`** that one
   thread can never send. Removing them would cut two subjects' worth of
   generation and lint per contact.
