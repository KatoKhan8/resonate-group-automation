# Merge request — the five-step cadence — 2026-09-25

Lane B (Bison/cadence), background agent, own locked worktree.

    branch    worktree-agent-a68c1abeb4d3a99f5
    based on  24acafff
    files     src/cadence.py
              config/clients/productive.yaml
              scripts/batch1_build.py
              scripts/stage_s7_copy.py
              tests/test_a_five_step_campaign_sends_five_different_emails.py
              tests/test_angle_subjects_are_readable.py
              docs/STEPS-4-5-DRAFTS-2026-09-24.md      (correction header)
              tests/test_the_cadence_lands_in_every_file.py           NEW
              scripts/verify_s7_cadence_render.py                     NEW

**THIS SHIPPED IN TWO PASSES AND THE SECOND IS WHAT STANDS.** Four steps
(em1, em2, em4, em5) landed 2026-09-24 with rung 3 unwritten and its position
deliberately left EMPTY. The operator approved rung 3 on 2026-09-25 and it
took that position as `em3`, making five. The other keys never moved across
either change, which is the whole reason they were not renumbered while the
gap existed. Where this document says something was measured at four steps,
that measurement is kept, because the difference between the two is itself a
finding — see §2.2.

`src/bisonfactory.py` carries ONE new function, `_require_declared_cadence`,
in its own region near line 350 - see §2.4. It is deliberately far from the
copylint call at line 86 that lane D adds, so B and D merge cleanly.
`src/configdiff.py` was read closely and NOT modified - see §2.1 and §6.1.

**NO PROVIDER WRITE HAPPENED.** No EmailBison, no HeyReach, no Apify, no
credential read. Nothing was merged and nothing was pushed.

---

## THE ONE CORRECTION THAT HAS TO TRAVEL FURTHER THAN THIS BRANCH

**There is no `SUBJECT_2`, and no step in this cadence opens a second thread.
Any document that says otherwise describes a shape `bisonfactory` refuses.**

    thread_reply_pattern   [false, true, true, true, true]
    every step's subject   {SUBJECT_1}

em1 opens the thread and owns the only subject. em2, em3, em4 and em5 are
thread replies into it and the provider prepends `Re:` itself. Measured, not
read — the refusal text and the second latent defect behind it are in §2.1,
and I re-ran both shapes at FIVE steps rather than inheriting the result:

    [F,T,T,F,T] + SUBJECT_2 on em4   REFUSED: "step 4 is not a thread reply
                                     but carries a distinct subject"
    [F,T,T,T,T] + SUBJECT_1 only     BUILT 5 steps, no variable written and
                                     cleared in the same PATCH

**At least three documents currently say the opposite**, which is why this is
restated here rather than left in §2.1:

1. `docs/STEPS-4-5-DRAFTS-2026-09-24.md` §2 - `[false, true, true, false,
   true]`, em4 on `SUBJECT_2`. **Corrected on this branch** with a header
   pointing here.
2. **Lane D's** `docs/MERGE-REQUEST-2026-09-24-COPY-AND-COPYLINT.md` §1, on
   branch `worktree-agent-a63bd2d9102384dba`, verbatim: *"the thread-reply
   pattern becomes `[false, true, true, false, true]` - em1 opens, em2 and em3
   reply into it, em4 opens a new thread with `SUBJECT_2`, em5 replies into
   that."* **Not corrected - it is lane D's file and I did not edit it.**
   Rung 3 itself is unaffected: it is a thread reply on `SUBJECT_1` either
   way. Only the accompanying claim about em4 is wrong.
3. **TASK-283 on master**, which the coordinator reports encoded the same
   mapping from the handoff and says has already been corrected there. **I
   did not read it** - it postdates this branch's base `24acafff` - so that
   is reported, not verified by me.

**Whoever merges lane B and lane D must reconcile 2 before the merge**, or
master ends up carrying an approved copy document specifying a cadence the
factory will not build.

Rung 3 itself was never the problem: it is a thread reply on `SUBJECT_1`
either way. Only the accompanying claim about em4 was wrong.

**THREE INDEPENDENT CONFIRMATIONS of `[false, true, true, true, true]`**, which
settles a value two committed documents still get wrong:

1. `cadencelibrary.THREAD_REPLY_PATTERNS["email_five"]` is already
   `(False, True, True, True, True)` - the client's own declared ladder, found
   while checking something else.
2. A config read by lane F.
3. A `_sequence_steps` run by the coordinator, and a second one by me: the
   `[F,T,T,F,T]` + `SUBJECT_2` shape is REFUSED at five steps exactly as it
   was at four.

---

## 0. THE HEADLINE, AND WHAT EACH NUMBER IS THE ANSWER TO

      927   rows in `work/stage/s7-copy.jsonl`
      814   RENDERED by S7. The other 113 are HELD and always were
      814   build a complete four-step provider payload — every variable
            non-empty, none the literal 'None', none unrendered
    - 2     refused by `lint.check`, which is the approval gate
    - 16    held by `cadence.company_name`, which refuses per RECORD
    -----
      796   survive every gate this script can ask

**ASK FOR 796, NOT 814, AND NEVER 927.** Each of those numbers answers a
different question.

**AND 796 IS STILL NOT "HOW MANY CAN BE PUSHED"** — I would be repeating the
exact mistake to say it is. 796 is what survives every gate reachable from a
worktree with no `work/`. The verification pair, suppression, collision and
fatigue gates were never asked, and the handoff records 167 leads held on the
verification pair alone last time. **Only `batch1_build --plan` answers the
push question, and its number will be lower.** §5 item 2.

**927 was never the rendered count.** It is the journal's line count:
814 rendered plus 113 held. `docs/STEPS-4-5-DRAFTS-2026-09-24.md` says
"927 rendered rows" in its own header and then lists persona counts of 621 and
193 four lines later, which sum to 814. The handoff inherited the 927. This is
the same defect §8 of the handoff names: a headline from a stage that had not
asked the next stage's question.

**814 is the answer to "did the copy render", and two later gates disagree.**

### 0.1 Two leads fail lint, and both are PRE-EXISTING

    lead A   em_dash      its `Company` value contains an EN DASH
    lead B   placeholder  its `Company` value is wrapped in SQUARE BRACKETS

(The two addresses are real prospects and are deliberately not written here.
`scripts/verify_s7_cadence_render.py` names them on stdout when run against
the live journal, which is where an operator should read them. An earlier
draft of this document DID carry them and the hygiene guard caught it -
see section 8.4.)

Proved rather than assumed: the same two leads fail the same two codes on
em1/em2/em3 in the **3-step** journal, measured with the same gate. They are
supplier data, they break every step equally, and they are correctly failing
closed. Not this change's regression, and not worth widening a lint rule for.

### 0.2 Sixteen leads carry a company name `cadence.company_name` refuses

Thirteen records, sixteen leads. Every one of them is a company whose own
name carries a TLD - the shape `<word>.io`, `<word>.co`, `<word>.AI` and so
on - which is exactly what `company_name` refuses so that no prospect is
addressed by their own hostname. The names themselves are the client's
prospect list and are not reproduced here; the verifier prints them.

**Two gates disagree about the same fact and S7 is the one that is wrong.**
S7 writes the supplier's `Company` column straight into four bodies and never
calls `company_name`. `cadence.build` does call it, raises
`CompanyNameUnusable`, and `scripts/batch1_build.py` catches that **per
RECORD** and drops the whole account from the batch. So these leads render
beautifully and then vanish at S8, and the number that reaches a provider is
smaller than the number S7 printed.

Also PRE-EXISTING - `body_1` already renders the same hostname-shaped name
into the sentence "teams the size of ..." - and
also correctly failing closed. But several of these are genuine brand names
several of these companies really are named that way, which
`company_name`'s own docstring admits it cannot tell apart from a hostname. **This is an operator decision
about data**, and it is worth making before the push because it is 16 leads.

**Cross-tabulated, not subtracted in prose**: 0 leads are in both the lint set
and the company-name set, which the verifier computes as a set intersection
and prints. `814 - 2 - 16` happens to be right and was not assumed to be.

### The held 113, unchanged in both directions

By EMAIL and in both directions against the pre-change journal:

    rendered before and held now      0
    held before and rendered now      0
    existing copy (subject_1, body_1..body_3) that moved   0

Adding em4 and em5 held nothing new and moved not one live word. The 113 are
S7's own fail-closed gates and every one predates tonight:

    109   no company name, and three sentences name it
      2   no industry, and the opener states it
      1   no angle is written for 'economic_buyer' with this title
      1   no usable first name

---

## 1. WHAT CHANGED

### `config/clients/productive.yaml`

`email_sequence.steps` now declares **em1, em2, em4, em5**; `em3`/`breakup` is
retired from this client's sequence. `breakup` is NOT deleted from
`src/cadence.py` — it stays correct for a cadence that really is three steps.

`thread_reply_pattern` is **`[false, true, true, true]`** — four entries, one
per declared step.

Waits are **3, 4, 5, 1**. The final one is 1 and never 0.

### `scripts/batch1_build.py`

`STEP_KEYS` and `CADENCE_STEPS` gain the same keys, at days **1, 4, 8, 13**.
The declared waits above are exactly those gaps, which is what
`_sequence_steps` recomputes and refuses on.

The per-contact cadence block now writes em4 and em5 from S7's `body_4` /
`body_5` and records the resolved per-persona template name on each slot.

### `scripts/stage_s7_copy.py`

Renders em4 and em5 per lead **from `src/cadence.TEMPLATES`**, not from a
second copy of the words. `BODY_1..BODY_3` stay hardcoded because those are
campaign 489's live copy read back off the provider and a change to
`cadence.TEMPLATES` must not silently edit what a prospect is already
receiving. em4 and em5 have no live provenance — they were approved INTO
`cadence.TEMPLATES` on 2026-09-24, which makes that module the one place they
exist.

`angle_for` now returns the angle KEY as well as the phrase, because
`cadence.angle_word` looks the short label up by key and two personas share
the `finance` phrase verbatim, so deriving the key back from the phrase is not
even injective.

`BODY_3` is renamed `BODY_3_RETIRED_BREAKUP` and is **no longer rendered**.
It is kept rather than deleted because it is what the eleven live three-step
campaigns are sending as their third email; `bison.set_sequence` appends with
no replace, so they cannot be corrected in place and will go on sending it,
and deleting the constant would leave nothing in the repository saying what
those leads receive.

### `src/cadence.py` — rung 3 and two new template variables

`rung3_economic_buyer` and `rung3_champion`, **lane D's approved text
verbatim** — not rewritten, not tightened, not re-linted into different
words. Rendered they measure 103 and 86 words, matching lane D's own figures
exactly.

`product_words(contact, config)` resolves `{our_company}` from
`product.name` and `{capability}` from `product.capabilities[<key>]`, the key
chosen per persona from `product.capability_by_persona`. **One implementation,
two callers** — `template_vars` and S7 — because two functions computing one
fact is how a writer and its comparator drift.

Nothing client-specific is hardcoded into `TEMPLATES`. `TEMPLATES` is shared
by every client, so the literal "Productive" in there would make another
client's rung 3 name a product that is not theirs. Lane D refused to write it
inline and a test now asserts that over the **whole register**, not just
rung 3, because the next template to name a product is the one nobody reviews.

**A key that cannot be resolved is OMITTED, never faked.** `render` calls
`str.format(**values)` and raises `CadenceError` on a missing key, so the step
is HELD. An empty `{capability}` would ship a paragraph reading "." to a real
person while every readback agreed the campaign was correct — the blank-render
incident exactly. A configured-but-blank value is treated as absent for the
same reason.

### Where the capability map lives is load-bearing

`product.capability_by_persona` is **client-wide and deliberately not nested
inside a persona.** `web/api.save_persona` rebuilds a persona as exactly
`titles`, `cap_per_domain` and `angles`, so anything else kept there is
dropped the first time somebody edits that persona in the product.
`angle_labels` sits client-wide for precisely this reason and says so in its
own docstring. The failure would be **silent**: rung 3 starts being held and
the cadence quietly gets one step shorter with no error anywhere. Asserted.

---

## 2. TWO THINGS THE BRIEF ASKED FOR THAT THE CODE REFUSES

Both were measured by running the code, not by reading it.

### 2.1 em4 CANNOT open a new thread with a second subject

The brief and `docs/STEPS-4-5-DRAFTS-2026-09-24.md` both specify em4 as a NEW
thread carrying `SUBJECT_2`, pattern `[false, true, false, true]`. Fed to
`bisonfactory._sequence_steps`, that shape raises:

> `FactoryRefused`: step 3 is not a thread reply but carries a distinct
> subject (`'{SUBJECT_2}'` vs opener `'{SUBJECT_1}'`). Only the opener owns a
> subject; follow-ups must be thread replies referencing the opener's subject.

That invariant was added 2026-09-16 under TASK-219 and is
**operator-verified in the EmailBison UI**:
`docs/ONLY-THE-OPENER-OWNS-A-SUBJECT-2026-09-16.md` records "follow-ups must
stay in the original thread, and only the opener owns a subject… no
`subject_2`, no `subject_3` exists to be generated, approved, or accidentally
sent." I did not weaken it. **The pattern shipped is
`[false, true, true, true]` and all four steps carry `{SUBJECT_1}`.**

There is a **second, independent** reason the same shape is unsafe, which the
refusal above hides by firing first. `_variables_for` numbers variables by
POSITION and empties follow-up subjects only for THREADED steps, while
`_stale_clearances` clears `subject_{2..N}` whenever the sequence has ANY
threading. So a non-threaded follow-up at position 3 has its subject written
AND cleared to `""` in the same `update_lead` payload — `_ensure_leads` builds
`all_wanted = wanted_vars + clearances` and passes both — and which one the
provider applies is a property of its payload ordering. Measured:

    F,T,F,T with SUBJECT_2   variables:  subject_3 = 'S2'
                             clearances: subject_3 = ''

Enabling the two-thread design therefore means changing **`_sequence_steps`,
`_variables_for` and `_stale_clearances` together**, plus
`src/configdiff.py`'s `_expected_lead_variables`, which mirrors
`_variables_for`. That is a real piece of work on a guard the operator set,
not a config edit. **This is the decision to overturn if the two-thread
cadence is wanted** — see §5.

### 2.2 THE VARIABLE MAPPING — AND WHY IT MUST BE DERIVED EVERY TIME

`bisonfactory._variables_for` numbers copy variables **by POSITION in the
built sequence**, never by step key. Derived from the code at both lengths,
not assumed either time.

**FIVE STEPS — what ships:**

| step key | position | provider reads | journal field | thread_reply | wait |
|---|---|---|---|---|---|
| `em1` | 1 | `{SUBJECT_1}` `{BODY_1}` | `subject_1`, `body_1` | false | 3 |
| `em2` | 2 | `{BODY_2}` | `body_2` | true | 4 |
| `em3` | 3 | `{BODY_3}` | `body_3`, `template_3` | true | 4 |
| `em4` | 4 | `{BODY_4}` | `body_4`, `template_4` | true | 9 |
| `em5` | 5 | `{BODY_5}` | `body_5`, `template_5` | true | **1** |

There is no `subject_2`..`subject_5`: `_variables_for` writes a threaded
follow-up's subject as `""` and `_stale_clearances` clears `subject_2..6` and
`body_6`. Verified that **no variable is written and cleared to `""` in the
same PATCH** — the collision that would otherwise be decided by payload order.

**THE TRAP, AND IT IS THE REASON THIS SECTION EXISTS.** At five steps the key
digit and the position coincide. **At four steps they did not:**

| step key | position | provider reads |
|---|---|---|
| `em1` | 1 | `{BODY_1}` |
| `em2` | 2 | `{BODY_2}` |
| `em4` | 3 | `{BODY_3}` ← **not** `BODY_4` |
| `em5` | 4 | `{BODY_4}` ← **not** `BODY_5` |

So today's agreement is **a coincidence of this cadence's shape, not a rule**.
Remove any step and the bodies renumber by position while the keys stay put.
Writing `{BODY_4}` against `em4` because the key says 4 would have sent em5's
words as the third email, and every readback would have agreed the campaign
was correct. `test_the_variable_numbers_are_positions_not_step_keys` asserts
the rule (position) for every step rather than the coincidence.

`scripts/verify_s7_cadence_render.py` now **derives** both name sets rather
than listing them — its predecessor hardcoded the four-step list and, left
alone, would have checked five steps of copy against four steps of names and
printed PASS.

---

### 2.3 `em3` NOW MEANS TWO DIFFERENT MESSAGES, AND THAT IS SAFE

Worth stating because it looks alarming. `em3` was `breakup` until
2026-09-25 and is rung 3 after it, and both meanings exist in one store.

It is safe, and I checked the mechanism rather than reasoning about it:

- `scripts/batch1_build.py` appends **only records absent from the store** —
  `fresh = {k: v for k, v in records.items() if k not in existing}`. It never
  rewrites an existing record's cadence. So the records behind campaigns
  485–500 keep breakup's words under `em3`.
- The WORDS travel on the record, and `_certified_copy` re-verifies the
  approval fingerprint against the words in the slot. A record can only send
  copy its own approval covers, so the two can never be swapped silently —
  a mismatch is a refusal, not a wrong email.

**The one consequence to carry forward:** the 63 stopped leads on 496/497/498
hold records with no `em4`/`em5` words at all. Putting them on a five-step
campaign is a re-render plus a rebuild, not a re-push.

---

### 2.4 THE DAY ALIGNMENT DISSOLVED A GUARD, AND THE REPLACEMENT IS REAL

**The old protection was an accident and it evaporated on a correct change.**

Until 2026-09-25, a campaign carrying no `cadence_steps` was caught - when it
was caught at all - by `_sequence_steps`, because the client's declared step
KEYS happened to differ from whatever `cadence.steps_for` fell back to. Rung 3
gave the control an `em3`, the operator then aligned the days to the client's
own ladder so email and LinkedIn run one clock, and the two agreed. The
refusal stopped firing. Measured, not predicted: the test went red with
`FactoryRefused not raised`, on an assertion added the night before for
exactly this case.

**What that exposed, measured by the coordinator before the decision:**
16 of 28 campaign rows carry no `cadence_steps`, and three are real EMAIL
campaigns - one of them LIVE and ACTIVE with its sequence already written.
`bison.set_sequence` APPENDS with no replace and no per-step delete, so
staging it would have left it holding its existing sequence PLUS five more
and sending duplicates to a live cohort. One staging call away.

**So `_plan` now refuses a campaign that declares no `cadence_steps`**, before
any cadence is resolved, on both the dry-run and live paths. The refusal names
the campaign and says it declared no cadence of its own - it is not "the
config and the library agree", which is the accidental protection being
deliberately given up.

**Campaign-level and client-agnostic, and that is the load-bearing part.** A
client-scoped check does not reach this case: `steps_for` falls back through
`_named_sequence` and `_library_sequence`, which ARE client declarations, so
"the client declared something" is satisfied while the campaign declared
nothing. The dangerous campaign passes a client-scoped check.

**Nothing was written to any row to make it pass.** Filling `cadence_steps`
in for the sixteen would hand them a cadence nobody chose, which is the same
defect one level down. They are refused until somebody decides what they run.

#### The fixtures, and the check that made the edit legitimate

EIGHT test files staged campaigns without a cadence and relied on the same
fallback. Each now declares exactly what the fallback would have produced, so
behaviour is unchanged by construction. **The eighth was found by the guard
firing in the wrong place:** `test_threaded_sequence`'s negative tests went
red on the NEW guard rather than the threading invariant - a different guard
masking the one under test, which is the failure CLAUDE.md names explicitly.

Each fixture was then attacked on its OWN subject to prove it can still fail:

| broken | result |
|---|---|
| stale clearances disabled | 5 red in `test_lead_variables` |
| collision verdict ignored | 4 red in the collision fixture |
| workspace killswitch ignored | 2 red in the killswitch fixture |
| one body for all five steps | 1 red, `test_every_step_gets_its_own_words` |
| idempotent reuse via `bound` disabled | **NOTHING RED** |

**That last row is the useful one.** Idempotency is protected by a SECOND
mechanism - recovery-by-name - so disabling the binding proved nothing. Only
disabling both made the fixtures fail. Had I stopped at the first attack I
would have concluded the fixture edit had broken the test's ability to fail,
and reported the opposite of the truth.

#### A dead guard is worse than none

With every fixture declaring a cadence, **nothing in the suite could observe
the guard firing** - a check that passes because the condition it guards
against no longer appears anywhere. That is the shape this estate has
produced three times in a week: a copy lint proved by tests that called it
directly, a LinkedIn stop gated on a field no contact carries, and my own
verifier that would have checked five steps of copy against four steps of
names and printed PASS.

So `test_a_campaign_that_declares_no_cadence_reaches_no_provider` and its
dry-run twin stage a campaign with no `cadence_steps` and assert **by
effect** - `FakeBison.created_campaigns` and `created_leads` unchanged - not
by message text. Removing the guard turns both red, plus the `_plan` test.

`test_the_control_refuses_the_five_step_library_cadence` was **replaced, not
deleted**: its scenario still refuses, on the new guard, through `_plan`. Its
old mechanism is recorded as a fact in
`test_the_library_and_the_control_now_agree`, so nobody reinstates a guard
that cannot fire.

---

## 3. THE BLOCKER: ELEVEN EXISTING CAMPAIGNS — RESOLVED AS OPTION A

**This is the most important thing in this document and it is not in the
brief.** `email_sequence` is CLIENT-wide. `cadence_steps` is stored PER
CAMPAIGN ROW. Eleven rows in `work/campaigns.jsonl` carry the old shape:

    485 487 489 491 492 493 494 495 496 497 498 500
    cadence_steps email keys ['em1','em2','em3'] at days [1,4,8]

(485 and 500 among them; 491–498 are the live batch-1 campaigns.)

Fed the five-key config, `_sequence_steps` raises:

> `email_sequence.steps` declares `['em1','em2','em3','em4','em5']` and the
> cadence's email steps are `['em1','em2','em3']`. These must be the same keys
> in the same order.

So **any further `bisonfactory.stage` against 485–500 refuses the moment this
config lands**, including the 63 stopped leads waiting on 496/497/498 and
campaign 500.

`campaign_row` writes `cadence_steps` only at creation and nothing rewrites an
existing row, so this is not fixed by editing the config. And it cannot be
fixed by lengthening those campaigns at the provider either:
`bison.set_sequence` **appends** — no replace, no per-step delete, which is
the finding `docs/ONLY-THE-OPENER-OWNS-A-SUBJECT-2026-09-16.md` records for
campaign 485, and which is the whole reason the operator required all five
steps in ONE write.

### THE OPERATOR CHOSE OPTION A

**New campaigns get the five steps; 485–500 keep three and are not
rewritten.** Nothing in this branch depends on rewriting a stored
`cadence_steps` row, and nothing in it touches `work/campaigns.jsonl`.

Two consequences that follow from that choice and are not optional:

1. **This config must not land on master until the new campaigns exist.**
   The current three-step state builds and pushes fine today; it is LANDING
   the longer config that raises `FactoryRefused` on the eleven. That is the
   correct order, and it is the reverse of what the handoff implied.
2. **The 63 stopped leads on 496/497/498 cannot simply be re-pushed onto the
   long cadence.** Their records hold no `em4`/`em5` words at all (§2.3), so
   they need a re-render and a new campaign, not a retry.

Four scripts still hardcode `("em1","em2","em3")` and each is correctly scoped
to a campaign that really is three steps — §5 item 6. Under option A they stay
right for 485–500 and will under-report readiness for the new ones.

---

## 4. EVIDENCE

### 4.1 The re-render

Run in this worktree against a COPY of production's inputs
(`work/stage/ready.json`, the supplier CSV), output to a new file nothing else
reads. Production's `work/` was read and never written.

    py -3 scripts/stage_s7_copy.py --ready work/stage/ready.json         --out work/stage/s7-copy-5step.jsonl

    S7  from 927 READY
      rendered   814
      held       113
      economic_buyer 621   champion 193

Then `scripts/verify_s7_cadence_render.py`, which asks the next four stages'
questions:

    STAGE 1  every referenced variable, on every rendered row
      the build reads ['subject_1', 'body_1', 'body_2', 'body_3',
                       'template_3', 'body_4', 'template_4', 'body_5',
                       'template_5']
      PASS  814 rows x 9 variables = 7326 values, none blank, none 'None',
            none unrendered
    STAGE 2  the held set, BY EMAIL, both directions
      rendered before, held now      0
      held before, rendered now      0
      LIVE copy moved                0     (subject_1, body_1, body_2)
      body_3 replaced              814     (breakup -> rung 3, intended)
    STAGE 3  lint.check, the real approval gate, every step
      3256 steps checked across 709 records
      2 leads refused (both pre-existing, section 0.1)
    STAGE 3b cadence.company_name, which refuses per RECORD
      13 records carry only a domain-shaped company name, holding 16 leads
    STAGE 4  the custom_variables payload bisonfactory would build
      sequence  em1@1 tr=False {SUBJECT_1} wait=3 | em2@2 tr=True wait=4
              | em3@3 tr=True wait=5 | em4@4 tr=True wait=5
              | em5@5 tr=True wait=1
      814 leads built
      PASS  every lead carries body_1..body_5 and subject_1 non-empty, and
            no follow-up subject leaks

**STAGE 2 WAS SPLIT, because lumping made it a rubber stamp.** `body_3`
changed meaning, so every row differs there by design; a check counting that
as a fault is red on every run and nobody reads it. The two questions are now
separate, and the one that matters is `LIVE copy moved = 0`: `subject_1`,
`body_1` and `body_2` are campaign 489's approved copy and are what the
eleven running campaigns are sending. **Not one byte moved.**

**BOTH blank hazards were checked.** No variable is the empty string and none
is the literal `'None'`. The `'None'` case is genuinely absent — confirming
the handoff — but the check catches either, because checking only the one
that bit last time is how the other gets through.

Rung 3 renders at **103 words (economic_buyer) and 86 (champion)**, matching
lane D's own measurements exactly, and `{capability}` resolves to the
client's unedited sentence in both cases.

### 4.2 The tests, and that they go red

`tests/test_the_cadence_lands_in_every_file.py`, 18 tests, green. Every
assertion is made against a sequence BUILT by `_sequence_steps`, or a value
read off one, or a real render. Nothing greps a source file, so nothing fails
when somebody writes a comment.

**I broke the fix five times, each reverted before the next, and confirmed
each failure was the intended one for the intended reason with no other guard
firing first.**

| breakage | result |
|---|---|
| `capability_by_persona` renamed | 3 red — resolve, render, and the not-nested-in-a-persona guard |
| `"Productive"` hardcoded into rung 3 | 1 red, naming the template and the field |
| persona pointed at a capability key that does not exist | 2 red — `CadenceError` on render, and the key-exists assertion |
| `thread_reply_pattern` back to four entries | 4 red, incl. **`'Sem5' != ''`** — em5's subject leaking to the provider. That is the hazard; the length is only the symptom |
| terminal `wait_in_days` 1 → 0 | 2 red, `0 != 1` (the campaign-485 defect) |

**TWO OF THE FIVE NEEDED A SECOND ATTEMPT, and that is worth recording.** My
first `sed` for two of them matched nothing — wrong indentation — and the
suite stayed green. A breakage that does not apply proves exactly as much as
no breakage at all, and a green run after one reads like a passed test. Both
were checked against the file before rerunning.

**AND ATTACKING THEM FOUND A DEFECT IN MY OWN TEST.**
`test_both_variables_resolve_for_every_persona` asserted
`words.get("capability") == capabilities.get(key)` and nothing else, so a
persona pointed at a non-existent capability compared `None` with `None` and
**passed** — on a configuration that would hold every rung-3 step. It now
asserts the key exists and both values are non-empty before comparing them.

### 4.3 Full suite

See §6. One pass only, diffed by name.

---

## 5. WHAT I COULD NOT VERIFY, AND WHY

1. **Nothing reached EmailBison.** No provider write was permitted and none
   was made. A sequence built in memory is not a sequence at the provider, a
   2xx would not be evidence either, and only a readback is. Steps 6 and 7 of
   `STEPS-4-5-DRAFTS-2026-09-24.md` §6 remain undone.
2. **The approval gate's non-copy conditions were not exercised.** The
   verifier stamps fingerprints the way `approve.approve_step` does once
   `why_not` has passed, then runs the real copy chain. It does NOT run the
   verification-pair, sendability, suppression, collision or fatigue checks —
   those need `work/` state a worktree does not have. **796 is what survives
   the gates about the WORDS and the COMPANY NAME.**
   `scripts/batch1_build.py` still decides who is approvable, and the handoff
   records that 167 leads were held on the verification pair alone last time.
   **Expect the enrolled number to be materially below 796.**
3. **`scripts/render_preview.py` was not run** over representative leads
   (§6 step 6 of the drafts doc). The four-stage verifier covers the same
   ground through `bisonfactory`, which is the path that actually stages, but
   the preview is a second reader and a second reader is worth having.
4. **The 3-step → 5-step transition on existing campaigns is untested**
   because it cannot be made to work (§3). I proved the refusal; I did not
   prove any migration, and option A means none is wanted.
5. **`scripts/batch1_build.py` was not executed.** It writes canonical state
   through `store.transaction()` and this worktree has no `work/`. The record
   shape it would write was reproduced in the verifier and driven through
   `lint.check` and `bisonfactory`, which is the chain that matters, but the
   script itself has not run against the new constants.
6. **Other scripts still hardcode `("em1","em2","em3")` and I left them
   alone, because each is scoped to a campaign that really is three steps.**
   Checked one by one: `activate_control_campaign.py`,
   `apply_control_approval.py` and `build_us_cohort_row_and_approvals.py`
   target 484/485/489; `next_ready_cohort.py` says so in its own comment —
   "Email takes them from campaign 487's own `cadence_steps`, which are
   em1..em3" — and names `productive-email-control-v3` as the shape campaign.
   All four stay correct for those campaigns and all four will UNDER-REPORT
   readiness the first time a five-step campaign exists. That is a follow-on,
   not a regression, and it is a second reason §3 matters.
   `scripts/render_preview.py` still previews the `{SUBJECT_3}` shape; it was
   not run tonight (see 3 above).
7. **Rung 3's copy was not re-linted into different words, by instruction,
   and one thing in it is worth an operator's eye.** Both bodies render the
   capability as its own paragraph - `{capability}.` - and the client's
   sentences do not start with a capital, so the paragraph reads "margin per
   project while it is running, not after it closes." beginning lowercase.
   That is lane D's approved construction and the client's unedited words, so
   I did not touch it. It lints clean. If it reads as a typo rather than as a
   quoted capability, the fix is new copy and needs approval.
8. **The library-refusal guard got thinner and I did not thicken it.** §6
   item 7 below.
9. **A latent mismatch I found and did NOT fix, because it is out of scope.**
   `batch1_build` stores `contact["angle"]` as the angle PHRASE, and
   `cadence.angle_words` does `angles.get(contact["angle"])` expecting the
   KEY — so that lookup misses and falls back to the first configured angle.
   It is harmless today: every batch-1 step is `generated: true` with
   pre-rendered words, so `template_vars` is never consulted for them. It
   would stop being harmless the moment a batch-1 step stopped being
   pre-rendered. S7 now also emits `angle_key`, which is what a fix would
   store. Belongs in `PRODUCT-GAPS.md`, not in this diff.

---

## 6. DECISIONS AN OPERATOR SHOULD OVERTURN IF I GOT THEM WRONG

1. **The biggest one: em4 is a thread reply, not a new thread.** Two
   approved copy documents say otherwise and the code refuses the shape they
   describe (§2.1). The coordinator independently reproduced both results.
   I chose the shape the code accepts over weakening an operator-verified
   guard. If the two-thread cadence is what is wanted, that is a change to
   `bisonfactory._sequence_steps`, `_variables_for`, `_stale_clearances` and
   `configdiff._expected_lead_variables`, with the threading invariant
   rewritten to permit exactly one subject change and no more. It is not a
   config edit and it should not be done at 1 a.m. before a push.
   **The copy still works threaded** — `angle_shift_*` makes a new argument
   and reads fine as a reply — but it was written for a fresh subject and an
   operator may disagree that it survives the move.
2. **RESOLVED: the days are the client's own ladder, 1/4/8/12/21.** Kept in
   this list because the process is the point. I shipped 1/4/8/13/18 first,
   extrapolated from the four-step reading, and flagged it as MY
   extrapolation rather than letting it pass as chosen. Nothing would have
   caught it: a campaign row's days are checked only against its OWN declared
   waits, so both spacings are internally consistent and no gate fires, and
   `set_sequence` appends so it is unfixable once the campaigns exist. The
   operator chose the client's ladder, so email and LinkedIn run one clock
   for the same prospect - which matters because the account rule pairs
   personas across both channels. Waits DERIVED from those days and proved
   against `_sequence_steps`: **3/4/4/9/1**, and bumping each of the first
   four makes it refuse while bumping the terminal one does not.
   The alignment then dissolved a guard, which is §2.4.
3. **`CADENCE_STEPS`' em3/em4/em5 name no template and are marked
   `generated`.** Their copy is per persona, so no single campaign-wide
   template name is true, and a made-up family name like `"angle_shift"` would be a
   `TEMPLATES[name]` KeyError the first time anything built a timeline against
   the row. Marking them generated also makes `expand_step` return the STORED
   words on the campaign-scoped path instead of re-rendering a template over
   them — which I verified by running both branches. em1/em2 were left alone.
4. **`breakup` is no longer rendered at all**, and its text is kept in
   `stage_s7_copy.py` as `BODY_3_RETIRED_BREAKUP`. `body_3` now means rung 3,
   so leaving breakup under that name would have been the exact drift this
   file warns about. The constant is kept, not deleted, because it is what
   the eleven live three-step campaigns are sending and `set_sequence`
   appends with no replace — they cannot be corrected and will go on sending
   it, and nothing else in the repository records what those leads receive.
   Delete it if that is not worth keeping.
5. **I SPLIT A TEST RATHER THAN DELETING HALF OF IT, AND SOMEBODY SHOULD
   CHECK THAT.** `tests/test_angle_subjects_are_readable.test_the_budget_is_real`
   was **already red on master** — `git diff 24acafff..HEAD` over
   `src/cadence.py`, `src/lint.py` and that test file is empty, so it is not
   mine. It asserted, per template, that every `{angle_word}` subject sits
   exactly on the 60-character line. True while `comparable_proof` (prefix
   27, 27 + 32 = 59) was the only such template; the four step-4/step-5
   templates merged on 2026-09-24 have prefixes of 22 and 24, so they fit
   with 3 to 5 characters of SLACK and all four went red for being safer than
   the constant requires. Rung 3 reuses `comparable_proof`'s subject exactly,
   so it is tight and adds nothing to this.

   I did not widen it. I split it: `test_the_budget_is_real` keeps the safety
   half per template (32 fits everywhere) and a new `test_the_budget_is_tight`
   asserts the constant is the largest safe value over the SET (at least one
   template goes over at 33). Both directions were attacked and both go red —
   32→33 fails the first, 32→31 fails the second.

   **The judgement to check is whether "every angle_word subject should sit on
   the line" was a deliberate copy rule rather than an artefact of there being
   one template.** If it was deliberate, the fix is to lengthen the four new
   subjects, not to split the test — and that is new copy, which needs
   approval.
6. **The two lint-refused leads and the sixteen company-name holds were left
   held.** Correct fail-closed behaviour and both pre-existing. The
   alternative is correcting `Company` values in the supplier file — two for
   lint, thirteen records for the hostname rule — which is an operator's call
   about data, not mine. Sixteen leads is enough to be worth the call.
7. **RESOLVED, and it became the largest change in this branch.** The guard
   did not merely get thinner - the day alignment removed it entirely, and
   the operator had it replaced rather than rewritten into agreement. §2.4.
   The original note follows so the reasoning survives: Until rung 3 landed,
   `test_the_control_refuses_the_five_step_library_cadence` rested on the
   control having four keys against the library's five. Both sides are now
   `em1..em5` and only the DAYS differ, so the refusal is on the em3 gap
   (declared 5, library 8→12 is 4). Measured, not assumed. **If anybody
   aligns the days, a campaign carrying no `cadence_steps` of its own would
   build five provider steps against the library instead of refusing** — not
   the disaster campaign 484 was, since all five steps now carry approved
   copy, but it would be a campaign running a schedule nobody declared for
   it. The test now asserts the days still differ and says what it would
   mean if they stopped. A real fix is to require `cadence_steps` on any
   campaign this client stages, which is a `bisonfactory` change.

---

## 7. THE ORDER FOR WHOEVER PUSHES

§3 is already decided: **option A**. The remaining order is:

1. Decide §6 item 2 — days 1/4/8/13/18 as shipped, or the li-heavy
   1/4/8/12/21. One-line change either way, and it must be made BEFORE the
   campaigns are created, because `cadence_steps` is written at creation and
   nothing rewrites it.
2. Decide §6 item 1 — threaded em4 as shipped, or the two-thread rewrite.
   Shipping as-is needs no decision; the rewrite is four functions.
3. **Merge this branch BEFORE landing the config on master is safe**, in the
   sense §3 sets out: the config must not be on master while the eleven
   three-step campaigns are the only ones that exist. Merge B, then C, then
   D, each after its own tests — the operator's order.
4. Re-run S7 in production:
   `py -3 scripts/stage_s7_copy.py --ready work/stage/ready.json`
   (it backs the previous journal up itself, stamped).
5. Verify it:
   `py -3 scripts/verify_s7_cadence_render.py --old <that .bak>`
   Expect **927 rows / 814 rendered / 796 survivors**, `LIVE copy moved 0`
   and `body_3 replaced 814`. A different number means the ready set moved,
   and the difference has to be named BY EMAIL before anything is pushed —
   the script prints both directions.
6. `py -3 scripts/batch1_build.py --plan`, and read the refused counts — that
   is where the verification-pair holds show up and where the real enrolled
   number appears. **This script has not been executed against the new
   constants** (§5 item 5), so read its output rather than trusting it.
7. Only then create 502/503 and stage — **all five steps in ONE
   `set_sequence` call**, because it appends and a third write was measured
   on 2026-09-13 to renumber a campaign 1, 3, 2, 4. Readback before
   activation.

**STILL AHEAD AND NOT IN THIS BRANCH:** the operator's order to re-render
step 1 and steps 3, 4 and 5 **from the packs**, because lane C measured the
free crawl at 62.5% rule-1 pass on the 128 and 54 of 117 passes resting on a
single word. S7 rendered this copy before any pack existed, so the openers
share vocabulary with the research rather than referencing it. That is S7's
next job and it is not done here.

---

## 8. SUITE — ONE PASS EACH SIDE, DIFFED BY NAME

### 8.1 The diff, both directions

Two full passes, each run ALONE with nothing else touching the checkout: one
at this branch, one at the base commit `24acafff` on a detached HEAD. Their
preambles are byte-identical, so they are comparable.

    base   12,517 tests   99 failures + 10 errors = 109
    head   12,536 tests   99 failures + 10 errors = 109

**The counts are equal and the SETS ARE NOT**, which is the entire reason to
diff by name:

    ONLY AT HEAD      test_fixture_hygiene.TestNoRealDataAnywhereInGit
                      .test_every_email_address_is_on_a_reserved_domain
    ONLY AT BASELINE  test_angle_subjects_are_readable
                      .test_the_budget_is_real

The other 108 are identical by name in both directions. The 19-test
difference in totals is this branch's new tests, not a change in what runs.

### 8.2 THE ONE NEW FAILURE WAS MINE, AND IT WAS A DATA LEAK

`test_every_email_address_is_on_a_reserved_domain` went red because **I wrote
two real prospect email addresses into this document**, plus thirteen real
prospect company names, while explaining the two lint-refused leads and the
sixteen hostname holds.

`work/` is gitignored precisely because it is real companies and real
contacts and is not ours to publish. I copied a piece of it into `docs/` and
committed it. **The guard is the only reason it is not on master.**

Redacted to the SHAPE, which is all the technical point ever needed: one
`Company` value contains an en dash, another is wrapped in square brackets,
thirteen carry a TLD. `scripts/verify_s7_cadence_render.py` prints the actual
names on stdout against the live journal, which is where an operator should
read them. Re-ran the guard after redacting rather than reading the diff and
assuming: 17 tests, OK.

This estate already wrote the rule down - *redact before the first command,
and self-test the filter against every value* - after an IPv4 leaked because
it was checked afterwards. I checked afterwards.

### 8.3 The baseline-only failure is the one I repaired

`test_the_budget_is_real` was already red on master before this branch
started - `git diff 24acafff..HEAD` over `src/cadence.py`, `src/lint.py` and
that test is empty. It asserted per template that every `{angle_word}`
subject sits exactly on the 60-character line, which was true only while
`comparable_proof` was the only such template. See §6 item 5.

### 8.4 What I did wrong the first time

The earlier pass in this branch was contaminated: I started `tests.offline`
and then ran targeted modules in the same checkout while it was still going,
which `CLAUDE.md` warns against for back-to-back runs, let alone concurrent
ones. No number was reported from it. Both passes above were run alone.

A mid-run `grep '^FAIL:'` returns 0 whatever is happening, because `unittest`
prints the blocks only at the end. Recorded because I checked, saw 0, and had
to remember that it means nothing.

### 8.5 THE GUARD HAS NO FULL-SUITE PASS BEHIND IT. SAID PLAINLY.

A third pass was started after the `cadence_steps` guard and the eight
fixture updates landed. **It did not finish and it was stopped.** There is no
by-name diff for it and none is claimed.

**The guard's evidence is 105 targeted tests across every module that stages
a campaign**, plus the attack table in section 2.4 - not a full run. The two
by-name passes in section 8.1 were taken BEFORE the guard existed, so they
say nothing about it.

Whoever merges this should run one clean pass alone on the merged result and
diff it by name against `24acafff` with `scripts/suite_baseline.py --measure`.
The committed baseline JSON cannot be used for that: its `failures` and
`errors` are INTEGERS, 97 and 73, and section 8.1 is the demonstration of why
a count cannot answer the question.

---

## 8.6 THINGS THAT EXISTED ONLY IN COMMIT MESSAGES

Written out because the squash discards them.

- **A `git checkout --` discarded an uncommitted docstring fix** during
  breakage testing on 2026-09-24, and it went unnoticed until the file was
  read again the next day. The rule "commit before you verify" exists for
  exactly this; I verified first on that one file.
- **Two deliberate breakages did not apply**, because the `sed` matched
  nothing - wrong indentation - and the suite stayed green. A green run after
  a breakage that never landed reads exactly like a passed test. Both were
  checked against the file before rerunning. Any attack whose diff is not
  confirmed proves nothing.
- **A test of mine compared `None` with `None` and passed.**
  `test_both_variables_resolve_for_every_persona` asserted
  `words.get("capability") == capabilities.get(key)`; point a persona at a
  capability key that does not exist and both sides are `None`. It passed on
  a configuration that would have held every rung-3 step. Found by attacking
  it, fixed to assert the key exists and both values are non-empty first.
- **My own import-graph selector was wrong in the safe-looking direction.** It
  skipped `from . import cadence` (relative import, `module` is `None`) and
  reported that 1 src module reaches `cadence`. Corrected: 159. It would have
  declared 41 failing modules out of scope without looking, which is why the
  full baseline pass was run instead of trusting the filter.
- **`_variables_for` and `configdiff._expected_lead_variables` are two
  implementations of one fact** and were compared at five steps rather than
  assumed to agree. They agree. A drift there stages correctly and is then
  REFUSED at activation for carrying exactly what it was told to carry.

---

## 9. FOUR FINDINGS WORTH MORE THAN THE CADENCE CHANGE

Put here because this document survives and the commit history does not: this
branch is SQUASH-merged, because commit `c3266ca6` carries two real prospect
email addresses in its diff and a normal merge would leave them in master's
permanent history where `git log -p` would show them for ever. Only the
redacted final state lands. So anything that lived only in a commit message
is written out below.

### 9.1 Counts equal, sets not

    base   109 failures      head   109 failures      DIFFERENT 109s

Demonstrated on this branch's own diff, section 8.1. One name appeared, one
disappeared, and a reader comparing totals would have seen `109 == 109` and
concluded nothing had changed. The one that appeared was a real prospect data
leak I had committed. **A count says something changed. Only a set of names
says WHAT**, and the estate's committed baseline JSON still stores counts.

### 9.2 The terminal `wait_in_days` is checked against nothing

Measured by bumping each declared wait by one and watching
`_sequence_steps`:

    em1 3->4   REFUSED       em2 4->5   REFUSED
    em3 4->5   REFUSED       em4 9->10  REFUSED
    em5 1->2   NOT REFUSED

The last step has no successor, so there is no gap to reproduce and nothing
validates it. **That is exactly how `wait_in_days: 0` reached campaign 485**,
which `set_sequence` then rejected, leaving the campaign holding zero steps.
The number is inert in the cadence and load-bearing at the provider. It is
asserted by a test because no gate will ever catch it.

### 9.3 One attack is not verification

Disabling idempotent reuse through `bound` in `_find_or_create` made **no test
go red**. The obvious reading - that updating the fixtures had destroyed the
tests' ability to fail - was wrong. Idempotency has a SECOND mechanism,
recovery-by-name, and only disabling both made the idempotency fixtures fail.

Had I stopped at the first attack I would have reported the opposite of the
truth about my own change. When a deliberate breakage produces no failure,
the first hypothesis to test is that something else is holding the property
up - not that the test is broken.

### 9.4 A new guard can mask the guard under test

`test_threaded_sequence`'s negative threading tests went red on the NEW
`cadence_steps` guard instead of on the threading invariant they exist to
prove. The refusal was correct, the tests were red, and the thing they
actually assert was never reached.

**Anyone adding a guard near an existing one needs to look for this.** A test
that fails for the wrong reason is invisible in a count and reads as "my
change broke something" rather than "my change hid something". The fix was to
give that fixture a declared cadence so the threading refusal is reached
again - found only because the assertion messages were read, not the totals.

### 9.5 And the one about me

The data leak in section 8.2 was mine. The rule this estate already wrote down
is *redact before the first command, and self-test the filter against every
value*, recorded after an IPv4 leaked because it was checked afterwards.
**I checked afterwards.** The guard caught it, not me. What I did right was
redact to the SHAPE rather than delete the evidence - the technical points
about the en dash, the square brackets and the thirteen TLD-shaped names all
survive - and re-run the guard instead of assuming the redaction worked.
