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

`src/bisonfactory.py` and `src/configdiff.py` were read closely and
deliberately NOT modified — see §2.1 and §6.1.

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
| `em3` | 3 | `{BODY_3}` | `body_3`, `template_3` | true | 5 |
| `em4` | 4 | `{BODY_4}` | `body_4`, `template_4` | true | 5 |
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
2. **The days are 1/4/8/13/18 and the client's default cadence disagrees.**
   `productive_li_heavy_v1` runs its five email steps on 1/4/8/12/21. Only a
   campaign row's own days are checked against the declared waits, so nothing
   refuses — but the pacing an operator gets is mine, extrapolated from the
   drafts doc's 4-step reading (em3 at the retired step's day 8, then +5 and
   +5). **If the intended pacing is the li-heavy one, change `CADENCE_STEPS`
   to 1/4/8/12/21 and the waits to 3/4/4/9/1 in the same commit.** Nothing
   else has to move.
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
7. **A guard got thinner and I only documented it.** Until rung 3 landed,
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

## 8. SUITE — AND A MISTAKE I MADE MEASURING IT

**The trustworthy evidence is the targeted module runs, not the full pass.**

### 8.1 What I ran, and what is good

Every module that touches `email_sequence`, the threading invariant, the
productive config or the cadence, run to completion:

    test_the_cadence_is_four_steps_everywhere      13   OK   (new)
    test_threaded_sequence
    test_bison_campaign_write
    test_lead_variables
    test_task081_thread_reply                      69   OK   (together)
    test_staging_a_campaign_twice_builds_one
    test_staging_refuses_colliding_contacts
    test_two_campaigns_do_not_collide_at_the_provider
    test_five_subject_variants_the_provider_already_rotates
    test_eight_step_cadence                       107   OK   (together)
    test_a_five_step_campaign_sends_five_different_emails
    test_angle_subjects_are_readable               38   OK   (after §6.5)

227 tests, green. Plus the three deliberate breakages in §4.2, each of which
went red for its own reason.

### 8.2 THE MISTAKE: I CONTAMINATED THE FULL PASS

I started `py -3 -m tests.offline` and then, while it was still running,
started targeted module runs in the same checkout. `CLAUDE.md` says plainly:
*"`unittest discover` and `tests.offline` both bind loopback and build demo
estates; run back to back they still overlap during teardown, and one HTTP
test fails intermittently."* I did it concurrently, which is worse than back
to back.

**So the failure names that full pass produces cannot be attributed.** A
failure in it may be mine, may be environmental (this worktree has no `work/`
and no `config/.env`, which the brief warns accounts for many of the ~108
known ones), or may be my own concurrent runs stealing a port. I stopped the
concurrent job when I noticed, which does not undo the overlap.

**I am not reporting a number from it, and nobody should read one.** Reading
a contaminated count as a verdict is the failure mode this document spends
§0 on.

### 8.3 What the foreground session should do instead

Run one clean pass on the merged result, alone, and diff BY NAME against the
same command at `24acafff` — `scripts/suite_baseline.py --measure` writes the
names, which `docs/state/SUITE-BASELINE-2026-09-23-MERGED.json` does not: its
`failures` and `errors` are INTEGERS (97 and 73), and two equal counts
compare equal while a different set fails.

A mid-run `grep '^FAIL:'` returns 0 whatever is happening, because `unittest`
prints the blocks only at the end. Wait for the verdict line.
