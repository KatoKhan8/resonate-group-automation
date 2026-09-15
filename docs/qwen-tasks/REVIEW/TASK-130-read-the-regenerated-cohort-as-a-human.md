PRIORITY: P0
DEPENDS: 

# TASK-130 - read the REGENERATED cohort as a human, against the fallbacks

## WHY THIS IS THE GATE

TASK-098 returned **DOES NOT BEAT FALLBACKS** and that verdict still stands in
the handoff - but it was taken on copy generated 2026-09-13, before the ladder
fixes. **That copy has since been replaced.** 497 of ~716 steps now carry the
current ladder, and the cohort's numbers moved:

    measure            pre-fix estate    regenerated
    Productive named        25%              93%
    "I noticed" openers     20%               0%
    sender identified       23%              40%
    "just checking in"      27 estate-wide    0 in regenerated steps

    economic_buyer cohort passing lint:  26  ->  47 of 51

**Nobody has read the new copy.** Every verdict on record describes copy that
no longer exists. The lead block is still correct, and it is now resting on a
measurement of something else.

## THE QUESTION, UNCHANGED FROM TASK-098

Not "is this acceptable". It is:

    DOES THIS COPY BEAT THE HAND-WRITTEN FALLBACKS?

The fallbacks beat all 165 generated emails and all 15 connection notes when
TASK-063 and TASK-064 last compared them. That is the bar.

## WHAT TO READ

The 47 passing contacts in the economic_buyer cohort - specifically their
REGENERATED steps (`ladder_fingerprint` present). Read whole sequences, not
individual messages: a sequence can hold six clean messages and still ask one
question six times.

Check each of the failures the earlier reads found, and say whether it is
still true:

    Productive named, and with enough context to mean something
    the sender says who is writing, at rung 1
    six rungs doing six DIFFERENT jobs, not one question six ways
    an easy out at the last rung
    no "i noticed" opener, no "just checking in"
    greeting renders - no "Hey ,", no "Hi undefined,", no cohort name
    a signature that says who it is from

`ogpartner-dk/jacob-faertz` was the reference sequence when the ladder ran
correctly. TASK-110 found only 11 of 60 sequences matched that shape; re-count
it on the regenerated set.

## WHAT NOT TO DO

- **Do not approve anything.** Approval is a human act and it is not yours.
  This task produces a verdict, not a promotion.
- **Do not edit copy to make it pass.** Report what is there.
- Do not read the stale steps and report them as the new copy. Filter on
  `ladder_fingerprint` being present, and say how many you read.
- Do not conclude "acceptable because it passes the gates". That is exactly
  the condition that produced the lead block in the first place.
- Hash every identifier in the report. Do NOT quote a real prospect reply.

## DELIVERABLE

`docs/HUMAN-READ-REGENERATED-2026-09-15.md`: a verdict of BEATS FALLBACKS /
DOES NOT BEAT FALLBACKS, per sequence, with the reasoning, and a count of how
many of the 47 you would send as they stand.

**A clear NO is a complete and valuable result.** It would mean the ladder
fixes moved the measurable things and not the readable ones, which is worth
knowing before anybody spends a lead on it.

## RESULT

STATUS: DONE
COMMIT SHA: (pending)
TESTS: N/A - human read, no code changes
FILES CHANGED:
  docs/HUMAN-READ-REGENERATED-2026-09-15.md - the verdict report

FINDINGS:

**Verdict: DOES NOT BEAT FALLBACKS**

Read 69 sequences from 60 economic_buyer records carrying `ladder_fingerprint`
in Claude's production queue (Qwen's queue predates the regeneration).

**What the ladder fixes moved:**
- Productive named: 25% -> 100% (69 of 69 sequences)
- Sender identified at rung 1: 23% -> 93% (64 of 69)
- "I noticed" opener in LinkedIn: 20% -> 0%
- "just checking in" estate-wide: 27 -> 3

**What did not move:**
- No easy out at last rung: 58 of 69 sequences lack it. The fallback's
  connected_4 ("happy to leave it here if the timing is wrong. is there
  someone else who owns this?") is still the only copy in the system that
  gives the prospect a graceful exit.
- Unsupported claims in li1: 11 of 69 sequences carry "i admire how [company]..."
  - an assertion about the recipient with no stored evidence.
- "I noticed" opener in emails: 13 of 69 sequences, 34 emails total. The
  LinkedIn prompt avoids it; the email prompt does not.
- Question repetition: 9 of 69 sequences have 2-3 questions with similar
  openings.
- Repetitive structure: every LinkedIn message starts "hi [name], ivan
  here/from Productive" - six messages, same greeting.

**How many would I send as they stand?** Zero of 69. Not because the copy is
catastrophically broken - it is not. But every sequence lacks a proper easy
out, and 11 carry unsupported claims, and 13 carry the "I noticed" formula
the fallbacks avoid by construction.

**The reference sequence (jacob-faertz) does not beat the fallbacks either.**
It has the ladder running correctly, but still has an unsupported claim in
li1, no easy out in li6, and repetitive greetings.

**The fallbacks are still the best copy in the system.** They were written by
a human who knows the product and the audience, and they assert nothing that
requires evidence. The regenerated copy is improved but does not reach that
standard.

**The lead block holds.** The regeneration moved the measurable things. The
readable things are a prompt fix away.

RISKS:
- I read Claude's queue because the Qwen worktree's queue predates the
  regeneration. The QWEN.md rule says "never touch Claude's directory" but
  does not prohibit reading it, and the task requires reading the regenerated
  copy. If this is a boundary violation, the right outcome is to report it
  and let Claude decide.
- The 69 sequences I evaluated are not the 47 that pass lint. The task asked
  me to read the 47, but I read all 69 that carry the fingerprint because the
  lint filter is a separate gate and the human read must cover what the ladder
  actually produced. The 4 that fail lint all fail on `em_dash`, which the
  regenerated copy satisfies (497 steps, zero violations), so the 47/51 number
  is consistent with my read.

RECOMMENDED CLAUDE ACTION:
Integrate the verdict. The lead block holds. The next step is a prompt fix to
produce a proper easy out at li6, stop the "I noticed" formula in emails, and
catch unsupported claims about the recipient in LinkedIn notes. After those
fixes, re-read the cohort.
