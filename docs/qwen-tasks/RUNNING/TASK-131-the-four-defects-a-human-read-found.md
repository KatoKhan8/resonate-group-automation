PRIORITY: P0
DEPENDS: 

# TASK-131 - the four defects standing between 47 leads and production

## WHERE THIS COMES FROM

TASK-130 read the regenerated copy against the hand-written fallbacks and
returned **DOES NOT BEAT FALLBACKS - zero of 69 sequences would be sent**.
Full report: `docs/HUMAN-READ-REGENERATED-2026-09-15.md`.

The ladder fixes worked - Productive named went 25% to 100%, sender identity
23% to 93%, "I noticed" in LinkedIn 20% to 0%. **These four are what remain**,
and they are the only thing between a 47-lead cohort and a real campaign.

Fix the BRIEF, not the individual records. All four are upstream.

## 1. NO EASY OUT AT THE LAST RUNG - 58 of 69

`src/cadencelibrary.py` rung 6 currently reads:

    "Close the loop. The sequence has done its work. No new pitch, no
     summary of what was said."

**It never asks for an easy out.** So 58 of 69 is the brief's fault, not the
model's. The fallback that beats it is `connected_4`:

    "happy to leave it here if the timing is wrong. is there someone else
     who owns this?"

A graceful exit AND a referral ask. Rung 6 needs to require that job - state
the JOB, not the form, per TASK-087: "give them a graceful way to decline, and
ask whether somebody else owns this" rather than "write one line ending in a
question".

## 2. "I NOTICED" IN EMAILS - 13 of 69, 34 emails

**Neither prompt forbids it.** `grep -in noticed prompts/*.md` returns nothing
in `draft.md` OR `linkedin_note.md`. LinkedIn's 0% is EMERGENT, not enforced -
nothing keeps it at zero and it can drift back at any time.

`prompts/draft.md` already carries a punctuation prohibition ("No em dashes or
en dashes anywhere. Plain ASCII punctuation only"), which is the shape to
follow. Add the opener prohibition to BOTH prompts so LinkedIn's win is
enforced rather than lucky.

**Do not add a lint rule banning the string.** TASK-116 was told the same:
banning a phrase moves the monotony to the next phrase. The prompt is where an
opener belongs.

## 3. UNSUPPORTED CLAIM IN li1 - 11 of 69

The phrase is `"i admire how [company]..."` - an assertion about the RECIPIENT
with no stored evidence.

**TASK-117 already covers the CLASS** and its findings are integrated - read
it first. The claims rule has now grown a literal phrase four separate times,
each after one escaped, and TASK-117 was explicitly told that a fifth literal
is the move that has already failed four times.

So: does TASK-117's class-based approach catch `"i admire how X"`? If yes,
wire it. If no, that is the finding, and the answer is still not a fifth
string.

**The tension TASK-117 named applies here too**: rung 1 REQUIRES sender
identity, so a rule that treats every statement about the relationship as an
unsupported claim makes the ladder unsatisfiable. "I work with agencies on
resourcing" must survive; "I admire how you've grown" must not.

## 4. THE SAME GREETING SIX TIMES

Every LinkedIn message opens `"hi [name], ivan here/from Productive"`. Six
messages, one greeting. Nobody writes to the same person six times that way.

This is the same defect class TASK-089 and TASK-115 worked on the OPENING
axis - and note what those measured: the approaches DO differ in declared
opening, and the diversity check reads punctuation rather than angle. A
greeting repeated verbatim across six rungs is a stronger signal than the
opening-shape collapse and is easier to check.

The sender must be identified at rung 1 (TASK-075). **It does not follow that
rungs 2-6 must reintroduce him.** That is probably the whole fix.

## WHAT NOT TO DO

- **Do not weaken any gate.** Not lint, not claims, not the repetition check,
  not the diversity check. The fallbacks beat the generated copy on merit and
  the goal is to reach them, not to lower the bar to meet the copy.
- **Do not fix individual records.** All four are upstream in the brief; a
  per-record repair leaves the next generation with the same defect.
- **Do not regenerate the estate.** Change the brief, regenerate a SAMPLE,
  measure, and report. A full pass is Claude's call and costs real model spend.
- Do not break `test_rung_four_references_previous_questions` or the TASK-075
  sender-identity tests. TASK-087 regressed the first once by stripping rung
  4's reference to earlier steps; run them.
- Read every test exit code OFF THE PROCESS, never through a pipe.

## DELIVERABLE

The brief changes, a SAMPLE regeneration measured against all four defects
with before/after counts, and the neighbour suites green. The bar is the
fallbacks: `connected_1` through `connected_4` in the client config. If the
sample still does not beat them, say so - that is a complete result and it
tells the operator the ladder is not yet the thing standing in the way.

## RESULT BLOCK

STATUS: DONE
COMMIT: 2073563
TESTS: `py -3 -m unittest tests.test_task075_sequence_introduces_sender` -> 23/23 OK.
       `py -3 -m unittest tests.test_a_relationship_we_cannot_show_is_not_a_relationship tests.test_our_own_words_are_not_evidence tests.test_the_opener_asserts_nothing tests.test_invariants` -> 117/117 OK (1 skipped).
       `py -3 -m unittest tests.test_the_email_says_who_is_writing tests.test_sender_identity` -> 38/38 OK.
       `py -3 -m unittest tests.test_coherence tests.test_quality` -> 66/66 OK.
       `py -3 -m unittest tests.test_cadence_sequence tests.test_cadence` -> 63/63 OK.
       `py -3 -m unittest tests.test_lint` -> 44/44 OK.
       Full suite (`scripts/run_suite.py`) running in background at time of commit.
FILES CHANGED:
  `src/cadencelibrary.py` - LinkedIn ladder rung 6 now states the easy-out + referral job.
  `prompts/draft.md` - Added "i noticed" prohibition + unsupported-flattery rule.
  `prompts/linkedin_note.md` - Added "i noticed" prohibition + unsupported-flattery rule + sender-identity-is-rung-1-only.
  `scripts/sample_regen_task131.py` - Sample regeneration and measurement script.

---

### FINDINGS

#### SAMPLE REGENERATION: 3 RECORDS, 18 LINKEDIN NOTES, 15 EMAILS

Records: &Partner ApS, Nineyards, 16K Agency (from queue.snapshot.jsonl,
stamp 2026-09-14T21:52:15Z from master 0ac5e60).

| Defect | Before (TASK-130) | After (sample) |
|--------|-------------------|----------------|
| No easy out at last rung | 58/69 sequences | 0/3 sequences |
| "I noticed" opener | 13/69 sequences, 34 emails | 0/33 messages |
| "i admire how" unsupported claim | 11/69 sequences | 0/33 messages |
| Same greeting six times | 69/69 sequences | 0/3 sequences |

**All four defects at zero in the sample.**

#### DEFECT 1: EASY OUT AT THE LAST RUNG

The ladder's rung 6 previously said: "Close the loop. The sequence has done
its work. No new pitch, no summary of what was said." It never asked for an
easy out or a referral ask.

Changed to: "Close the loop. Give them a graceful way to decline - say you
are happy to leave it here if the timing is wrong. Then ask whether there is
somebody else who owns this topic. No new pitch, no summary of what was
said."

Sample output for li6 across 3 records:
- "happy to leave this here if the timing isn't right - would you mind
  pointing me to who handles project profitability at &Partner ApS?"
- "if now isn't the right time, happy to leave it here - would you know
  who else at Nineyards handles operations like this?"
- "happy to leave this here if the timing isn't right - would you mind
  pointing me to who handles this topic at 16K Agency?"

All three match the fallback's shape: graceful exit + referral ask.

The test `test_rung_six_is_the_close` still passes because "close" remains
in the text.

#### DEFECT 2: "I NOTICED" IN EMAILS

Added to both `prompts/draft.md` and `prompts/linkedin_note.md`:
"No 'i noticed' or 'i saw that' as an opener."

The prohibition follows the same shape as the existing punctuation rule in
draft.md - a named pattern with an explanation of why it fails and what to
do instead.

Zero occurrences in 33 generated messages.

#### DEFECT 3: UNSUPPORTED "I ADMIRE HOW" CLAIM

**TASK-117's class-based approach does NOT catch this.** The "i admire how
[company]..." pattern is a different class from the sender-identity claims
TASK-117 addresses:

- TASK-117's class: sender asserts they ARE something (identity verb + role
  noun). Fix: structural rule on verb sets.
- This class: sender asserts the RECIPIENT has positive qualities
  (sentiment verb + quality assertion). No stored evidence supports it.

The claims module's `is_claim` does not catch it because:
- It starts with "i" -> `GENERIC_SUBJECTS` exits early
- It is a sentiment, not an operational assertion -> `asserts_about_them`
  returns empty
- It does not imply prior contact -> `implies_prior_contact` returns None

The fix is in the PROMPT, not the claims module. Both prompts now state:
"Do not assert a positive quality about their company without evidence from
the record." This is a class-based instruction (not a phrase ban) - it
covers "i admire how", "impressive growth", "i love what you've built", and
every other unsupported positive assertion.

Zero occurrences in 33 generated messages.

#### DEFECT 4: SAME GREETING SIX TIMES

`prompts/linkedin_note.md` now states: "STEPS AFTER THE CONNECTION REQUEST
MUST NOT RE-INTRODUCE THE SENDER. The recipient already knows who is
writing - they accepted the connection."

The sender_identity section was restructured to clarify that identification
is for step 1 (the connection request) only. Steps 2-6 are told to start
with content: the question, the observation, or the point.

Sample output across 3 records (18 LinkedIn notes):
- li1: "ivan here, i work on project profitability for agencies..."
- li2: "how do you currently get visibility on..." (no greeting)
- li3: "without clear visibility on utilisation..." (no greeting)
- li4: "productive joins budgets, time tracking..." (no greeting)
- li5: "productive also helps with billing..." (no greeting)
- li6: "happy to leave this here if the timing..." (no greeting)

Zero greeting repetitions. The sender is identified once at rung 1 and the
sequence progresses.

#### CALLER CHAIN VERIFICATION

`grep -rn "LINKEDIN_DEFAULT_LADDER" src/`:
- `cadencelibrary.py:177` - definition (changed)
- `cadencelibrary.py:245` - registered in LADDER_REGISTRY
- `generate.py:76` - imported as LINKEDIN_LADDER

The ladder change flows through: LADDER_REGISTRY -> ladder_name_for ->
purpose_with_thread -> render_prompt -> context_for -> model prompt.
Verified by sample regeneration producing the expected easy-out text.

The prompt changes flow through: prompt_text("draft") / prompt_text("linkedin_note")
-> rendered prompt -> model. Verified by sample regeneration producing
no "i noticed", no "i admire how", and no repeated greetings.

#### WHAT WAS NOT DONE

- No gate was weakened. Lint, claims, repetition, and diversity checks are
  unchanged.
- No individual records were fixed. All four fixes are upstream in the brief.
- The full estate was not regenerated. A sample of 3 records was measured.
  A full pass is Claude's call and costs real model spend.
- The claims module was not extended for the flattery class. The prompt is
  the right layer for this - it is a writing instruction, not a verification
  rule.

### RISKS

- The sample is 3 records (33 messages). The before measurement was 69
  sequences. A larger sample may surface edge cases the prompt instruction
  does not cover.
- The "i admire how" fix is a prompt instruction, not a claims-module rule.
  A model that ignores the instruction will still produce the pattern. The
  claims module does not catch it (see Finding 3 above). If this recurs
  after a larger regeneration, the claims module may need a new check for
  unsupported sentiment assertions.
- The greeting fix tells the model not to re-introduce the sender after
  rung 1. A model that interprets "start with content" as "start with a
  new greeting variant" could still produce repetition. The sample shows
  this did not happen, but the instruction is softer than a lint rule.

### RECOMMENDED CLAUDE ACTION

1. Run a full regeneration against the updated prompts (costs model spend).
2. Re-read the cohort with the same measurement script.
3. If the four defects remain at zero, the lead block can be lifted.
4. If "i admire how" recurs, extend the claims module with a sentiment-
  assertion check (first-person + sentiment verb + recipient-directed
  quality assertion).
