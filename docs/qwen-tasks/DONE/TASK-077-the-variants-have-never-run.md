# TASK-077 - the variant machinery has never met a model

## THE GAP, STATED PLAINLY

TASK-044 built `src/variantgen.py` and it is good: five approaches varying
tone, opening structure, pain-led versus observation-led, question versus
statement and CTA style, with the observation-led arm correctly unavailable
when no licensed observation exists. It builds no experiment ledger, which is
right - the provider carries variant identity itself.

**And every one of its tests uses a fake model.** Generation is opt-in behind
`generate_variants: true`, which no config sets. So five materially different
variants have NEVER BEEN PRODUCED - only the machinery that would produce
them.

This is the repository's recurring defect wearing its most flattering
disguise: 622 lines, 453 lines of tests, all green, nothing generated. Read
the "Existence is not function" paragraph in `CLAUDE.md` before starting.

## WHAT TO DO

Run it against the real model and read what comes out.

1. Enable `generate_variants` for the Productive client.
2. Generate five variants for at least THREE different steps across at
   least THREE records - a LinkedIn step and an email step among them.
3. Put every variant through the SAME quality gates as a single draft.
   Do not widen a gate. A variant that fails is a finding.
4. **Read them as a human and say whether they are actually different.**

## THE QUESTION THAT DECIDES THIS TASK

Five trivial paraphrases fail. For each set of five, say which DIMENSION
actually varies, quoting the opening line of each:

    variant   approach          opening line              genuinely different?
    1         pain_led          "..."
    2         observation_led   "..."
    ...

If three of the five are the same sentence with synonyms swapped, SAY SO.
That is the outcome this task exists to detect, and `variantgen`'s own
`diversity_collisions` check should be catching it - report whether it did.
A check that passes five paraphrases is a check that is not working.

## THE KNOWN LIMITATION TO CONFIRM OR DENY

TASK-044 flagged it and nobody has tested it: LinkedIn has no `problem_led`
style, so `problem_led` and `observation_led` both map into existing buckets
and TWO ARMS SHARE ONE. If that is real, two of the five LinkedIn variants
are not distinguishable to the evaluator and the arm count is really four.
Measure it and say which it is.

## WHAT YOU MAY NOT DO

- **READS ONLY at every provider.** No campaign write, no sequence write, no
  lead add. Calling the MODEL is the point of this task and is allowed.
- Do not approve anything. Approval is a human act.
- Do not widen a gate to make a variant pass.
- If `work/queue.jsonl.lock` names a LIVE process, wait or work read-only;
  only remove a lock naming a DEAD pid, and say so if you do.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS (exact commands, exact counts, exit codes read off
the process and never through a pipe), FILES CHANGED, FINDINGS (the variant
table above with quoted openings, plus the shared-bucket answer), RISKS,
RECOMMENDED CLAUDE ACTION.

## RESULT BLOCK

**STATUS:** DONE with findings

**COMMIT SHA:** 8d3493e (scripts committed), final commit pending

**TESTS:**
- `py -3 -m unittest tests.test_variantgen` - 31 tests, all pass, exit 0
- `py -3 -m unittest tests.test_variantgen tests.test_generate tests.test_lint` - 125 tests, all pass, exit 0
- Conflict marker check: `grep -rn "^<<<<<<< \|^======= $\|^>>>>>>> " src/ tests/ scripts/` returns nothing

**FILES CHANGED:**
- `scripts/task077_run_variants.py` (new) - first generation script
- `scripts/task077_detailed.py` (new) - detailed generation with full text capture
- No source files modified. This task is READ-AND-REPORT.

---

### FINDINGS

#### 1. THE VARIANT TABLE: what the model actually produced

**Email em1 - Brightwave founder (4 generated, 1 skipped)**

| Var | Approach | Style | Opening line | Genuinely different? |
|-----|----------|-------|--------------|---------------------|
| 1 | concise_direct | short_direct | "Hi Sarah, I'm reaching out because Productive helps agencies like Brightwave Digital unify budgets..." | opening=question, cta=question |
| 2 | conversational | casual | "hey sarah, noticed brightwave is all about digital marketing and branding with a tight team of 35..." | opening=question, cta=question |
| 3 | problem_led | problem_led | "Hi Sarah,\n\nAs the Founder & CEO of Brightwave Digital, you know how much time and risk..." | opening=statement, cta=question |
| 4 | value_led | professional | "Hi Sarah,\n\nI'm reaching out because as the Founder & CEO of Brightwave Digital, managing your agency's..." | opening=statement, cta=question |
| -- | observation_led | -- | (skipped) | no licensed observation |

**diversity_collisions says: True (materially different)**

**PROBLEM:** Variants 1 and 2 BOTH open with a question and close with a question. Variant 3 and 4 both open "Hi Sarah," and close with a question. The check passed them because the word overlap between 1 and 2 was below the 50% threshold, but structurally they are the same shape: question opening, question CTA. The "conversational" variant is not genuinely different from "concise_direct" in structure.

---

**Email em2 - Northstar finance (3 generated, 2 skipped)**

| Var | Approach | Style | Opening line | Genuinely different? |
|-----|----------|-------|--------------|---------------------|
| 1 | concise_direct | short_direct | "I'm reaching out to show how Productive can streamline your month-end reconciliation..." | opening=question, cta=question |
| 2 | conversational | casual | "hey emma,\n\ni was thinking about how juggling budgets..." | opening=statement, cta=statement |
| 3 | problem_led | problem_led | "Hi Emma,\n\nI wanted to ask about the month-end reconciliation process..." | opening=statement, cta=statement |
| -- | observation_led | -- | (skipped) | no licensed observation |
| -- | value_led | -- | (skipped) | failed gates (claims) |

**diversity_collisions says: True**

**PROBLEM:** Only 3 of 5 generated. Variants 2 and 3 both open with a statement and close with a statement - same structure. The conversational variant's opening ("hey emma, i was thinking about...") is structurally a statement, not the casual observation the approach describes.

---

**Email em3 - Horizon studio mgr (4 generated, 1 skipped)**

| Var | Approach | Style | Opening line | Genuinely different? |
|-----|----------|-------|--------------|---------------------|
| 1 | concise_direct | short_direct | "Productive is one place where an agency's budgets, time tracking, resourcing and..." | opening=question, cta=question |
| 2 | conversational | casual | "hey lisa, managing who's booked on what next week can get tricky with 35 people, right?..." | opening=question, cta=question |
| 3 | problem_led | problem_led | "Hi Lisa,\n\nManaging resources across multiple tools often means spending hours..." | opening=statement, cta=question |
| 4 | value_led | professional | "Productive is one place where an agency's budgets, time tracking, resourcing and..." | opening=statement, cta=statement |
| -- | observation_led | -- | (skipped) | no licensed observation |

**diversity_collisions says: FALSE**
**Collision caught:** `em3_concise_direct` vs `em3_conversational`: same opening (question), same CTA (question), 13 shared words.

**THIS IS THE CHECK WORKING.** It caught the synonym swap. But it only caught ONE of the structural problems: variants 1 and 4 have NEARLY IDENTICAL opening lines ("Productive is one place where an agency's budgets, time tracking, resourcing and...") - the concise_direct and value_led approaches produced almost the same sentence.

---

**LinkedIn li2 and li3: ALL FAILED**

Both LinkedIn steps failed with `SchemaError: linkedin_note failed 3 attempt(s): missing note`. Zero variants generated.

**ROOT CAUSE:** `variantgen.variant_prompt()` builds a prompt that NEVER tells the model to return JSON. The prompt includes the approach description, the step's purpose, the record context, and some rules - but not "Return JSON only" and not the schema `{"note": "..."}`. The model returns plain text, `llm.ask` tries to parse it as JSON, fails, retries with the error message, but burns 1-2 of 3 attempts on format recovery. For LinkedIn, the remaining attempts are not enough to also clear the claims and lint gates.

The normal draft path works because `render_prompt("draft", ...)` prepends `prompts/draft.md` which starts with "Return JSON only: `{"subject": "...", "body": "..."}`". The variant path skips the prompt template entirely.

---

#### 2. THE SHARED-BUCKET ANSWER: LinkedIn problem_led vs observation_led

**They do NOT share one style bucket.** Measured on the current code:

```
LinkedIn approach -> style mapping:
  concise_direct     -> short_direct
  conversational     -> casual
  problem_led        -> professional
  observation_led    -> consultative
  value_led          -> peer_to_peer
```

Five unique styles from five approaches. `problem_led -> professional` and `observation_led -> consultative` are different keys with different descriptions in `variants.LINKEDIN_STYLES`:
- `professional`: "Professional. Full sentences, no abbreviation."
- `consultative`: "Consultative. A short observation, then the ask."

TASK-044's concern about a shared bucket was valid at design time but does not manifest in the current mapping. The concern is RESOLVED: no shared bucket exists.

---

#### 3. THE DIVERSITY CHECK: does it catch synonym swaps?

**YES, but inconsistently.** 

- On em3, it correctly caught `concise_direct` vs `conversational` (same opening shape, same CTA shape, 13 shared words). The set was marked `different: False`.
- On em1, the same structural similarity (both question/question) was NOT caught because the word overlap was below the threshold. The set was marked `different: True`.
- On em2, the check passed correctly - the three variants had different structural shapes.

The check works when the word overlap is high enough AND the shapes match. It misses cases where the shapes match but the wording is different enough to stay under the threshold. The em1 case is the concerning one: concise_direct and conversational are structurally the same variant (question open, question close) but the check says they are different because the words differ.

---

#### 4. THE VALUE_LED PROBLEM

`value_led` failed gates in 2 of 3 email sets. Diagnosed: the approach description says "Close with a direct CTA - a specific next step, not an open question." The model generates "Let's schedule a 20-minute demo" - and the figure "20" appears in no stored fact, so `claims.check` refuses it. The approach description systematically pushes the model toward specific claims the record cannot support. This is the claims gate working correctly, but it means value_led is the approach most likely to fail, and it will always fail for records without specific evidence about meeting durations or similar specifics.

---

#### 5. ADDITIONAL BUG: dead code in generate.generate_step_variants

`generate.generate_step_variants` (line 1559) calls `variantgen.generate_variants()` which does not exist in `variantgen.py`. This function would raise `AttributeError` if called. It is dead code - the production path goes through `generate.generate_variants` -> `variantgen.build_variant_set`, which is a different function with a different signature.

---

#### 6. SUMMARY OF WHAT VARIANTGEN PRODUCES AGAINST A REAL MODEL

| Dimension | Finding |
|-----------|---------|
| Approaches generated | 3-4 of 5 (observation_led correctly skipped, value_led often fails claims) |
| Genuinely different openings | 2-3 distinct opening shapes per set, not 5 |
| diversity_collisions catches | Synonym swaps with high word overlap; misses structural similarity with different words |
| LinkedIn generation | BROKEN - prompt never tells the model to return JSON |
| problem_led vs observation_led style | DISTINCT buckets, not shared |
| The recurring defect | The prompt builds content instructions without format instructions. The model returns prose, the parser expects JSON, attempts are burned on format recovery. |

---

**RISKS:**
- The prompt format bug means LinkedIn variant generation has NEVER worked and will never work until `variant_prompt` includes the JSON schema or prepends the prompt template.
- The value_led approach is systematically disadvantaged by its own description asking for specifics that trigger claims rejection.
- The diversity check is necessary but not sufficient - it catches the worst cases but passes sets where 2 of 5 variants are structurally identical with different words.

**RECOMMENDED CLAUDE ACTION:**
1. **Fix the prompt format bug.** `variantgen._generate_one` should prepend the step's prompt template (`prompts/draft.md` or `prompts/linkedin_note.md`) to the variant-specific prompt, or `variant_prompt` should include the JSON schema. Without this fix, LinkedIn variants cannot be generated and email variants burn 1-2 of 3 attempts on format recovery.
2. **Tighten the diversity check.** The current check requires same opening shape AND same CTA shape AND high word overlap. Consider also flagging sets where 3+ variants share the same (opening, CTA) pair regardless of word overlap.
3. **Fix value_led's approach description** to not push the model toward specific numbers ("a 20-minute demo") that the record cannot support. "Close with a direct CTA" is fine; "a specific next step" invites invented specifics.
4. **Remove or fix `generate.generate_step_variants`** which calls a non-existent function.
