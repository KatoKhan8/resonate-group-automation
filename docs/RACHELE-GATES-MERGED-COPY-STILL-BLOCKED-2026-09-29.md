PRIORITY: READ WITH THE RACHELE MILESTONE

# RACHELE — GATES MERGED, COPY STILL BLOCKED ON THREE MEASURED ITEMS

    master            bf9eab0b   (local == origin/master)
    merged branch     qwen-worker-8-r29 @ 89cd006f   (TASK-918/919/920)
    approval hash     (not computed - artifact not accepted)

    QUALITY GATE      PASS  - both classes now gated and merged
    RACHELE           BLOCKED
    SLACK             NOT POSTED

Nothing sent by this work. Provider writes 0, enrolments 0, prospect-facing
sends 0, campaign activation 0, `sending.live` false. `work/campaigns.jsonl`
unchanged.

---

## 1. THE GATES WORK, AND THEY MOVED THE COPY

Both previously ungated classes are now refused, and — unlike the last
attempt — regeneration is **no longer inert**, because a gate refusal feeds
the reason back into the writer prompt. The stored artifact changed on the
third canonical regeneration and now passes:

    claims (TASK-917 + 918/919/920)   clean on all 10 steps
    copylint                          refused=False, no failures
    campaign_repetition               NONE on both channels
    lint                              clean on all 10 steps
    structure                         em1..em5 + li1..li5, li6 cancelled

The two specific defects that blocked the previous artifact are **gone**:
`em3`'s service-list P.S. was replaced, and `em4`'s
*"improved resource decisions for others"* no longer appears.

Verification of the merged gates: **37 positive assertions** across four
matrices — three of them held out from the implementer — all refuse through
`generate._step_refusals` on both channels and all release when evidence is
licensed. No negative control overblocks. Both authorities are
mutation-proved load-bearing.

## 2. WHY RACHELE IS STILL BLOCKED — THREE MEASURED ITEMS

### 2a. `em4` — the same claim with the beneficiary deleted

    "Can I share a brief example of how real-time margin insights have
     improved resource allocation?"

    claims.check             -> []
    customer_outcome_claim   -> does not fire

This is the original TASK-914 defect with `for others` simply removed. It
asserts a **realized** improvement and offers an example of it, while
`offers.missing()` still reports no customer case studies and no verified
benchmarks. The new rule needs a third-party reference or a customer subject;
this sentence has **neither** — the beneficiary is elided entirely.

### 2b. `li4` — the proximity window is walkable

    "companies using real-time margin visibility make better resource
     decisions that improve profitability."

    customer_outcome_claim("companies improve profitability")   -> REFUSES
    customer_outcome_claim(the sentence above)                  -> no fire

Same subject, same verb, same metric. The only difference is distance: the
modifier phrase pushes `improve profitability` past the 40-character window
from `companies`. **The window is a bypass, and ordinary copy walks through
it without trying.**

### 2c. `em5` — a concatenated subject, again

    Subject: "margin visibility, budget burn, resource decisions"

Three comma-separated fragments, not a written subject line. This is the same
class the 2026-09-29 handoff named in section H.2
(`"real-time / project margin / visibility"`), with commas instead of
slashes. Nothing gates subject quality, so nothing refused it.

## 3. THE PATTERN WORTH NAMING

Three rounds of gate work have each been followed by the writer landing in
whatever the gate does not cover — `for others` removed leaves a subjectless
assertion; a customer subject plus metric is spaced apart until the window
lapses. Decoding is `temperature=0`, so this is not sampling noise: the gate
refusal changes the prompt, and the model moves to the nearest phrasing the
gate permits.

**Gate-by-example converges slowly against a writer that adapts.** The next
task should close structural bypasses rather than add vocabulary:

1. **Subjectless realized-outcome assertions** — "have improved X",
   "has reduced Y" offered as an example or benchmark, with no named
   beneficiary, while no customer-outcome evidence is licensed.
2. **The proximity window** — replace the fixed 40-character distance with
   clause-scoped matching, so a modifier cannot separate subject from
   outcome. Guard against the false positives the window was protecting
   against (`_CUSTOMER_OUTCOME_RE`'s comment records why it exists).
3. **Subject-line quality** — a subject that is an enumeration of fragments
   is not a subject. Nothing checks this today.

Item 3 is small and independent. Items 1 and 2 are one task and need the same
adversarial treatment as TASK-918/919/920, including held-out matrices.

## 4. WHAT WAS NOT DONE

No sentence was hand-edited. No gate weakened. No approval revoked beyond the
authorised Rachele machine approvals. No Slack post — the artifact is not
approval-ready. No estate sweep, no batching, no canary, no enrolment, no
send. The pre-existing `test_generate` defect (2 fail, 1 error) is unchanged
and remains the blocker before autonomous batching.

## 5. ONE OPEN, NON-BLOCKING DEFECT CARRIED FORWARD

`plan()` still reports a permanent `angle_wording_leakage` op for `li3` that
no run clears: the planner's LinkedIn branch runs `_note_quality` while
`_step_refusals`'s LinkedIn branch runs only lint and claims, so the two
authorities disagree and the planner can never reach zero ops for this
contact. Recorded in
`docs/RACHELE-BLOCKED-ON-UNGATED-COPY-QUALITY-2026-09-29.md` section 5.
