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

STATUS, COMMIT SHA, TESTS (exact commands, exact counts, exit codes read off
the process and never through a pipe), FILES CHANGED, FINDINGS (the variant
table with quoted openings, before and after), RISKS, RECOMMENDED CLAUDE
ACTION.
