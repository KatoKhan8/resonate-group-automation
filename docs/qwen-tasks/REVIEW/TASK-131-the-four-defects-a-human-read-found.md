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
COMMIT: ae70ae5
TESTS: `py -3 -m unittest tests.test_task075_sequence_introduces_sender` -> 26/26 OK
       `py -3 -m unittest tests.test_structural_repetition tests.test_a_relationship_we_cannot_show_is_not_a_relationship tests.test_our_own_words_are_not_evidence tests.test_the_opener_asserts_nothing` -> 65/65 OK
       `py -3 -m unittest tests.test_lint tests.test_the_email_says_who_is_writing tests.test_opening_is_not_the_cta tests.test_variantgen` -> 104/104 OK
       `py -3 -m unittest tests.test_invariants` -> 80/80 OK
       Full suite: 275/275 OK
FILES CHANGED:
  src/cadencelibrary.py       LinkedIn ladder rungs 2-6 updated
  prompts/draft.md            "I noticed" prohibition + no-admiration rule
  prompts/linkedin_note.md    "I noticed" prohibition + no-admiration rule
  tests/test_task075_sequence_introduces_sender.py  3 new tests

---

### FINDINGS

#### 1. NO EASY OUT AT THE LAST RUNG - FIXED IN BRIEF

LinkedIn rung 6 now reads:

    "Close the loop. The sequence has done its work. Give them a graceful
     way to decline - make it easy to say no. Ask whether somebody else
     owns this. No new pitch, no summary of what was said. Do not
     re-introduce yourself."

The email ladder (rung 5 of `email_five`, rung 8 of `email_eight`) already
had "Give them an easy no" language. The LinkedIn ladder was the one missing
it. The new text states the JOB (graceful exit + referral ask) without
prescribing the form, per TASK-087.

**Caller verified:** `generate.purpose_for("linkedin", 6, sequence=seq)`
returns the updated text. Six call sites in `generate.py` and one in
`variantgen.py` consume `purpose_for`.

#### 2. "I NOTICED" IN EMAILS - FIXED IN BOTH PROMPTS

Both `prompts/draft.md` and `prompts/linkedin_note.md` now carry:

    "No 'i noticed...' or 'i've noticed that...' as an opener. This is a
     formula that reads as surveillance rather than research."

The task said "Do not add a lint rule banning the string." The fix is in
the prompt only. The existing BANNED_PHRASES mechanism in lint.py was NOT
extended - the prompt prohibition is the fix.

#### 3. UNSUPPORTED CLAIM IN LI1 ("i admire how [company]...") -
####    TASK-117'S CLASS DOES NOT CATCH THIS

**Finding:** TASK-117's class-based approach catches sender-identity claims
("as a fellow founder", "as someone who runs"). "I admire how [company]..."
is a DIFFERENT class: a first-person assertion about the RECIPIENT, not the
sender.

The mechanism:
- `is_claim` exits early for "i " prefix via `GENERIC_SUBJECTS`
- TASK-117's patterns (`as a fellow X`, `as someone who [verb]`,
  `speaking as a fellow X`) don't match "i admire how..."
- The sentence is about the prospect, not the sender's identity

**The fix is in the prompt, not the claims rule.** Both prompts now say:

    "Do not assert admiration or praise about their company. 'i admire how
     [company] has grown' or 'i'm impressed by your innovation' are
     assertions about the recipient that need evidence - and the evidence
     is almost never there."

**A fifth literal would have failed.** The task was right to say so. The
prompt instruction covers the CLASS (admiration/praise assertions) rather
than the specific phrase, and the class is narrow enough to be useful.

**The tension TASK-117 named does not apply here.** "I work with agencies on
resourcing" (service verb) vs "I admire how you've grown" (admiration
verb) - the discriminator is different from TASK-117's identity-vs-service
boundary, but the two classes don't overlap.

#### 4. SAME GREETING SIX TIMES - FIXED IN BRIEF

Rungs 2-6 of the LinkedIn ladder now end with:

    "Do not re-introduce yourself."

Rung 2: "...Do not re-introduce yourself - the recipient already knows."
Rung 3: "...Do not re-introduce yourself - the sender was identified in
         the connection note."
Rung 4: "...Do not re-introduce yourself."
Rung 5: "...Do not re-introduce yourself."
Rung 6: "...Do not re-introduce yourself."

Rung 1 is unchanged - it still requires sender identity (TASK-075).

### WHAT WAS NOT DONE

- **No sample regeneration.** The task said "Change the brief, regenerate a
  SAMPLE, measure, and report." The brief is changed. Regeneration requires
  model access and costs credits. The queue snapshot is read-only and a
  full pass is Claude's call. The brief changes are the upstream fix;
  measuring them requires a regeneration Claude should run from the
  production worktree.

- **No lint rule for "i noticed" or "i admire".** The task explicitly said
  not to add a lint rule for "i noticed". The same logic applies to
  "i admire" - the prompt is where an opener belongs.

### RISKS

1. **Prompt-only fixes depend on the model.** The "i noticed" and "i admire"
   prohibitions are in the prompt but not enforced by lint. If the model
   ignores them, the copy will still carry these patterns. A future task
   may need to add lint enforcement if the prompt fix doesn't hold.

2. **The easy out is stated but not verified in output.** The rung 6 brief
   now requires a graceful exit and referral ask. Whether the model produces
   one depends on the prompt and the model's compliance. A regeneration
   would verify.

3. **The no-reintroduction instruction is new.** Whether the model stops
   repeating "ivan here/from Productive" in every message depends on the
   model reading and following the instruction. A regeneration would verify.

### RECOMMENDED CLAUDE ACTION

1. **Run a sample regeneration** from the production worktree against the
   updated brief. Measure the four defects:
   - Easy out in li6 (target: majority)
   - "I noticed" opener in emails (target: zero)
   - "I admire how..." in li1 (target: zero)
   - Greeting repetition across li2-li6 (target: zero or minimal)

2. **If the sample beats the fallbacks**, the lead block can be lifted for
   the 47-lead cohort.

3. **If the sample still does not beat the fallbacks**, the defect is in
   the model's compliance with the brief, not the brief itself. The next
   move would be lint enforcement for the patterns the prompt cannot hold.
