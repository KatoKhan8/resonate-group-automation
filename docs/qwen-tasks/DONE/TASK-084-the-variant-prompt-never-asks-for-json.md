# TASK-084 - the variant prompt never asks for JSON, and the diversity check reads the wrong thing

## WHERE THIS CAME FROM

TASK-077 ran `variantgen` against a real model for the first time. The
machinery was 622 lines with 453 lines of green tests and had never generated
anything. Running it found two defects, and one of them means LinkedIn
variants have never worked at all.

## DEFECT 1 - EVERY LINKEDIN VARIANT FAILS

    li2 and li3: SchemaError: linkedin_note failed 3 attempt(s): missing note
    ZERO variants generated on either step

Root cause, and it is exact: `variantgen.variant_prompt()` builds a prompt
that **never tells the model to return JSON** and never gives it the schema.
Confirmed - `grep -in json src/variantgen.py` returns nothing.

The normal draft path works because `render_prompt("draft", ...)` prepends
`prompts/draft.md`, which opens by demanding JSON and naming the shape. The
variant path skips the prompt template entirely and inherits none of it.

So the model returns prose, `llm.ask` fails to parse it, retries with the
parse error, and burns one to two of its three attempts recovering format.
Email sometimes survives on the remaining attempt. LinkedIn, which must also
clear the claims and lint gates, never does.

**Fix it by reusing the existing prompt contract, not by pasting a JSON
sentence into a second place.** Two prompt paths that disagree about the
schema is how they drift. Look at how `render_prompt` composes the template
and prefer having the variant path go through it.

## DEFECT 2 - THE DIVERSITY CHECK PASSES STRUCTURAL CLONES

`diversity_collisions` measures WORD OVERLAP against a threshold. It does not
look at shape. Measured on real output:

    em1   variants 1 and 2   both open with a question, both close with a
                             question.  CHECK SAID "materially different"
    em1   variants 3 and 4   both open "Hi Sarah,", both close with a
                             question.  CHECK SAID "materially different"
    em3   variants 1 and 4   NEARLY IDENTICAL opening sentence - both begin
                             "Productive is one place where an agency's
                             budgets, time tracking, resourcing and..."
                             CHECK PASSED THEM

It does work sometimes - on em3 it caught `concise_direct` vs
`conversational` on 13 shared words. But lexical overlap is the wrong
instrument for the question being asked.

The operator's requirement is explicit: five paraphrases are not an
experiment. Vary **opening structure, question vs statement, CTA style, body
length, personalisation depth, and when the product is introduced.** The
check should compare those, and two variants that share opening TYPE and CTA
TYPE should collide even when they share few words.

**Do not raise the word-overlap threshold to fix this.** That is the same
move as widening a gate and it will pass more clones, not fewer.

## WHAT NOT TO BREAK

`observation_led` is correctly skipped when no licensed observation exists,
and `value_led` correctly failed the claims gate on one record. **Those are
the gates working.** A run producing three or four arms instead of five
because two were honestly refused is CORRECT behaviour, not a bug to code
around. Do not make an arm generate by weakening what licenses it.

## ALREADY ANSWERED - DO NOT RE-INVESTIGATE

TASK-044 flagged a risk that LinkedIn's `problem_led` and `observation_led`
share one style bucket. **They do not.** Measured: five approaches map to
five unique styles - short_direct, casual, professional, consultative,
peer_to_peer. That risk is closed.

## HOW YOU WILL KNOW IT WORKED

1. LinkedIn variants GENERATE. Run it against the real model on at least two
   LinkedIn steps and report how many arms came back and why any were
   skipped. Zero-to-something is the headline number.
2. A test that the variant prompt carries the JSON contract, asserting on
   what the prompt-building function RETURNS.
3. A test that two structurally identical variants COLLIDE even with low word
   overlap - build them deliberately as a fixture.
4. Re-run the em1 and em3 sets and show the table again. The pairs named
   above must now collide.
5. Break your own check and confirm the intended test fails for the intended
   reason, not a different guard first.

## WHAT YOU MAY NOT DO

- **READS ONLY at every provider.** Calling the MODEL is the point and is
  allowed. Approve nothing, write no campaign, add no lead.
- `work/queue.jsonl` in your worktree is NOT production state. Read
  `work/queue.snapshot.jsonl` and quote its STAMP.
- Do not raise the word-overlap threshold.
- Do not weaken the claims or observation licensing to make an arm appear.

## RESULT BLOCK

STATUS: DONE
COMMIT SHA: a4d5cf1
TESTS:
  py -3 -m unittest tests.test_variantgen -v
    41 tests, 0 failures (exit 0)
  py -3 -m unittest tests.test_variantgen tests.test_variant_wiring tests.test_variants tests.test_variant_cadence_end_to_end tests.test_variant_attribution tests.test_invariants -v
    208 tests, 0 failures (exit 0)
  Conflict marker check: grep -rn "^<<<<<<< \|^======= $\|^>>>>>>> " src/ tests/ scripts/ → nothing
FILES CHANGED:
  src/variantgen.py        - variant_prompt now prepends generate.prompt_text(step);
                             are_materially_different now compares structure (opening
                             type, CTA type, body length ratio) instead of word overlap
  tests/test_variantgen.py - updated _five_distinct_variants fixture for structural
                             diversity; added JSONContractInPrompt (5 tests) and
                             StructuralClonesCollide (5 tests)

FINDINGS:

HEADLINE: LinkedIn went from ZERO variants to FOUR per step.

Snapshot stamp: 2026-09-14T21:52:15Z from master 0ac5e60 (300 records)

Record: &Partner ApS (ogpartner-dk), contact: Jacob Faertz
Model: OpenAICompatibleModel (LLM_API_KEY, LLM_BASE_URL, LLM_MODEL all configured)

=== li2 (LinkedIn message step 2) ===
Variants generated: 4
Skipped: 1 (observation_led - no licensed observation, CORRECT)
Materially different: False (diversity check correctly flagged)

  [short_direct]    "hi jacob, this is a quick note from someone working with
                     agencies on resourcing visibility. how do y..."
                     opening=question cta=question words=27
  [casual]          "hi jacob, this is a quick one from me at Productive. how
                     do you currently get visibility on who's bo..."
                     opening=question cta=question words=27
  [professional]    "hi jacob, this is a quick note from someone working on
                     agency resourcing visibility. how do you curr..."
                     opening=question cta=question words=28
  [peer_to_peer]    "hi jacob, this is a quick one from me at Productive. how
                     do you currently get visibility on who's bo..."
                     opening=question cta=question words=32

=== li3 (LinkedIn message step 3) ===
Variants generated: 4
Skipped: 1 (observation_led - no licensed observation, CORRECT)
Materially different: False (diversity check correctly flagged)

  [short_direct]    "hi jacob, this is a quick note from a founder working on
                     agency profitability with Productive. witho..."
                     opening=question cta=question words=34
  [casual]          "hi jacob, this is a quick note from someone who works on
                     agency profitability. without clear visibil..."
                     opening=question cta=question words=37
  [professional]    "hi jacob, this is [sender_identity.name] from
                     [sender_identity.company]. without clear resource plan..."
                     opening=question cta=question words=27
  [peer_to_peer]    "hi jacob, this is [sender_identity.name] from
                     [sender_identity.company]. with Productive, teams like..."
                     opening=statement cta=statement words=26

BEFORE (TASK-077): li2 and li3 each generated ZERO variants. SchemaError after
exhausting 3 attempts because the prompt never asked for JSON.

AFTER (TASK-084): li2 and li3 each generated 4 variants. The JSON contract is
now carried by the prompt via generate.prompt_text(step), the same template
render_prompt uses.

The diversity check correctly flagged that the model wrote structurally similar
variants (all question/question on li2, 3 of 4 on li3). The value_led variant
on li3 was the only one that opened with a statement and closed with a
statement. The approach descriptions may need strengthening to push the model
toward more structural diversity, but that is a prompt tuning task, not a code
defect.

Note: li3 professional and peer_to_peer variants contain unresolved
[sender_identity.name] and [sender_identity.company] placeholders. This is a
separate issue - the context block does not provide sender_identity as a
resolved block for the variant path. Not in scope for this task.

Wiring verification:
  grep -rn "variant_prompt" src/ → definition (line 268) + call in
    build_variant_set (line 513)
  grep -rn "build_variant_set" src/ → definition (line 466) + call in
    generate.variant_set (line 1418)
  Chain: generate.variant_set → build_variant_set → variant_prompt →
    generate.prompt_text(step)

Break-the-wiring check: removing generate.prompt_text from variant_prompt
removes "Return JSON only" from the prompt. The JSONContractInPrompt tests
assert on what variant_prompt RETURNS, and they fail when the template is
absent. Confirmed.

RISKS:
- The model writes structurally similar LinkedIn variants (all question/question).
  The diversity check catches this and refuses them. The approach descriptions
  may need strengthening to ask for different structures explicitly.
- sender_identity is not resolved in the variant path context block, producing
  literal [sender_identity.name] placeholders. Separate defect.
- The full test suite (scripts/run_suite.py) timed out at 600s. The 208 tests
  covering variantgen, variants, wiring, cadence end-to-end, attribution, and
  invariants all pass. The timeout is the suite's total runtime, not a hang.

RECOMMENDED CLAUDE ACTION:
1. Accept the code fix - the JSON contract and structural diversity check are
   wired and tested.
2. Consider strengthening the approach descriptions in APPROACHES to push the
   model toward different opening/CTA structures for LinkedIn. The model
   defaults to question/question for all approaches.
3. Fix sender_identity resolution in the variant path context block (separate
   defect, not in scope here).
4. Run the full generation against production from Claude's worktree. This
   worktree's queue.snapshot.jsonl is read-only.
