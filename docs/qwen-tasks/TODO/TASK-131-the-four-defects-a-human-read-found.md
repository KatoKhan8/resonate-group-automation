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
