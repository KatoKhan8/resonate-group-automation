# The 83 approvals: who made them, what they protect, and what is still unknown

Evidence for the operator's conditional authorisation of 2026-09-15. Every
number read from `work/queue.jsonl` and from the real
`--regen-stale-ladder` dry run this morning. Nothing inferred from a plan.

---

## 1. THE HEADLINE, AND IT CHANGES THE QUESTION

**167 of the 169 approvals in the estate were made by `claude`, not by a
human.**

    approved by                                              count
    claude                                                     167
    zvonimir@resonategroup.co                                    1
    zvonimir@resonategroup.co (operator authorisation ...)       1

    approved on   2026-09-09    1
                  2026-09-13  168

Every handoff in this repository, including checkpoint D and TASK-083's own
impact report, describes these as "83 human approvals". **They are not.** The
count is real and the revocation cost is real, but the word "human" was
carried forward unchecked, and it is the word the whole decision rested on.

## 2. ZERO HUMAN APPROVALS WOULD BE REVOKED

Cross-referencing the 560 steps the planner marks `LADDER STALE` against every
approval in the estate:

    approvals inside the stale set          83   (tool) / 89 (independent
                                                 cross-reference; the tool's
                                                 count is authoritative, the
                                                 delta is name-collision in my
                                                 display-name mapping)
    of those, made by claude                ALL
    of those, made on 2026-09-13            ALL
    by channel                              44 email, 45 linkedin
    HUMAN approvals in the set              ZERO

**Both genuine operator approvals sit outside the stale set and would survive
untouched.** The operator's protective condition - "if an approval protects
genuinely good copy that still passes the current production standard,
preserve it" - is satisfied without any special handling, because the only
two approvals a person ever gave are not at risk.

## 3. WHY EVERY STEP IS STALE, AND IT IS NOT WHAT THE PHRASE SUGGESTS

The planner's own reason, on all 560:

    "<contact>'s <step> note has no ladder fingerprint (predates TASK-083)"

    steps with a ladder_fingerprint    0 of 686
    steps without one                686 of 686

Not one stored step in the estate carries a fingerprint. So "ladder stale"
currently means **"predates the mechanism that tracks staleness"**, not "the
current ladder invalidates it". Checkpoint D predicted exactly this and it is
confirmed: 560/83 is *everything that exists*, and the two readings only
diverge once something has been regenerated with a fingerprint.

This satisfies the operator's condition directly. All 560 steps, and all 83
approvals attached to them, **predate the current generation and gating
system** - the fingerprinting mechanism, the rung-progression fix, the
sender-identity requirement and the fourth claims clause all landed on
2026-09-14 and 2026-09-15. The approvals were made on 2026-09-13.

## 4. WHAT THEY PROTECT - AND WHY THE COPY FAILS THE CURRENT STANDARD

TASK-098 read the live sequence against the hand-written fallbacks and
returned **DOES NOT BEAT FALLBACKS** on every pushable contact and every
dimension:

    Productive named         1 of 18 pushable steps
    sender identified        0 of 18 pushable steps
    "I noticed" openers     49 of 234, the identical count TASK-063 recorded

Across all 686 stored steps: Productive appears in 32%, a sender-identifying
construction in 23%, and 7% open with "I noticed".

The current standard requires the product introduced with context, the sender
named at rung 1, six rungs doing six different jobs, and no unsupported claim
about the sender. This copy does not meet it.

## 5. THE ONE CONDITION I COULD NOT TEST

The operator's fifth condition was **"whether regenerated copy measurably
improves it."** I could not answer it, and the reason matters:

**There is no post-fix cohort in the estate to compare against.** Zero of 686
steps carry a fingerprint, so every stored step is pre-fix. The natural
experiment - compare copy generated after the fixes against copy generated
before - has no treatment group. Any comparison between "pushable" and
"estate" copy, including the one in TASK-098, is comparing pre-fix copy with
other pre-fix copy.

Answering it requires actually generating a sample against the live model and
comparing. That is a state-mutating, credit-spending action on the production
ledger, and:

- **This session's sandbox denies it.** `py -3 -m src.generate
  --regen-stale-ladder --live --limit 3` was refused.
- **It may not be delegated to a Qwen worker.** `work/*.jsonl` is a production
  ledger and is on the list of things a worker may never own, alongside
  approval semantics. Handing a worker a live regeneration to get around a
  permission boundary would be the wrong kind of clever.

So the sample regeneration is Claude's to run and Claude currently cannot run
it. That is the blocker, and it is a permission question rather than an
evidence question.

## 6. WHERE THAT LEAVES THE DECISION

Four of the operator's five conditions are established and all four point the
same way:

    approval age                    all 2026-09-13
    what the copy is                fails the current standard on every
                                    measure TASK-098 checked
    predates current system         YES - no fingerprint on any step; the
                                    fixes landed 09-14/15
    protects human judgement        NO - 167 of 169 approvals are agent-made,
                                    and ZERO human approvals are in the
                                    revoked set
    regenerated copy improves it    UNTESTED - no treatment group exists and
                                    the sample run is blocked

The residual risk of proceeding is low and specific: if regeneration produced
copy no better than what is stored, the cost would be 560 re-planned steps and
83 agent approvals, and **no human judgement would be lost at all**. The
protective concern behind the operator's condition - that a person's
considered approval might be thrown away - does not arise here.

The residual risk of NOT proceeding is that the improved ladder never reaches
any copy, which is the state the system has been stuck in since 2026-09-14:
`plan` refuses to re-plan a step that still passes its gates, so the fixes
land in the generator and never in the estate.

**Recommendation: run the sample regeneration first, measure, then decide on
the full run.** That needs one permission.
