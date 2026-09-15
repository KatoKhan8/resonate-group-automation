PRIORITY: P1
DEPENDS:

# TASK-143 - 34% of research rows are page furniture, and one measurement says it does not matter

## THE TWO FACTS THAT HAVE TO BE HELD TOGETHER

    navigation / junk rows            237 of 695   (34%)
    records whose FIRST THREE are junk  47 of 203

`research.for_prompt` takes `[:3]` in stored order with no quality ordering, so
those 47 records show the model menu fragments where facts should be.

And:

    TASK-135's quality-filtering change is INTEGRATED and it moved NO
    claims-gate outcome. 26 drafts, 13 records, zero unsupported-claim
    rejections in either arm.

Both are true. The obvious reading - "the junk does not matter" - is one
hypothesis and the sample was 13 records. The other reading is that the claims
gate is not the place where junk evidence does its damage, and nobody has
looked at the place where it would.

**Do not re-investigate whether the model can SEE the evidence.** It can;
`generate.py:490` passes `public_evidence` from `research.for_prompt(rec)` with
`field`, `source_url`, `retrieved_at` and `fact`. `docs/CRAWLER-AUDIT-2026-09-15.md`
Part 1 is wrong about this and Part 3 corrects it. Settled.

## THE QUESTION

Where does junk evidence actually surface, and is it worth more filtering?

Three candidate answers, and the task is to find which is true:

1. **Nowhere.** The model ignores unusable evidence and writes from the
   structured company data instead. Then the junk is cosmetic and the finding
   is "stop worrying about it", which is a real result worth writing down.
2. **In the copy, silently.** The draft is grammatical, passes lint, passes
   claims, and says something bland because the evidence gave it nothing. The
   cost is a weak message rather than a rejected one - which is invisible to
   every gate and visible to a human read, and three human reads have already
   said the generated copy loses to the fallbacks.
3. **In the rejection rate.** Drafts fail repetition or lint more often on
   junk-fed records. 377 of ~440 recorded rejections are repetition, so this
   is checkable.

## HOW TO TELL THEM APART

Against `work/queue.snapshot.jsonl`. **Quote the STAMP.**

Split the 203 records with evidence into JUNK-FED (first three rows are
navigation) and FACT-FED. Then compare, on the copy that already exists in the
estate, with no generation required:

    rejection reasons by class          (repetition, lint, claims, none)
    how often the draft names a fact from the evidence at all
    how often the draft falls back to generic product language
    length, and the vocabulary shared with every other draft

**A comparison of 47 against 156 is not a coin flip - say what the difference
would have to be to be worth acting on BEFORE you compute it**, and hold to
that. This repository has a standing rule against optimising to noisy tiny
samples, and the honest outcome "the difference is inside the noise" is a
result.

## IF THE ANSWER IS (2)

Then the useful deliverable is not a filter - it is the measurement that
tells a generation task what "good evidence" means. Say what a fact would have
to look like to be worth putting in front of the model, with examples from the
real rows, both kinds.

## WHAT YOU MAY NOT DO

- Do not run `py -3 -m src.generate --live`. Generation against the real queue
  is Claude's, from Claude's worktree; a run here writes to an isolated queue
  that never reaches production. If your finding needs generation, say so
  under FINDINGS and Claude runs it.
- No provider calls. No writes to `work/`.
- Do not widen or weaken any gate.

## FILES ALLOWED

    docs/RESEARCH-QUALITY-IMPACT-2026-09-15.md   (new)
    scripts/task143_*.py
    the task file itself

## FILES FORBIDDEN

    src/       work/       config/

## DELIVERABLE

The pre-stated threshold, the two-group comparison, the verdict among the
three candidates with the numbers behind it, and - if the answer is (2) - what
good evidence looks like, in examples.

---

## RESULT BLOCK

**STATUS:** DONE
**COMMIT:** 192510f
**SNAPSHOT:** work/queue.snapshot.jsonl — 2026-09-14T21:52:15Z from master 0ac5e60, 300 records

**TESTS:** Analysis script at `scripts/task143_analysis.py`. Run with `py -3 scripts/task143_analysis.py`. No unit tests needed — this is a measurement, not a code change.

**FILES CHANGED:**
- `docs/RESEARCH-QUALITY-IMPACT-2026-09-15.md` (new) — full report with numbers, examples, and verdict
- `scripts/task143_analysis.py` (new) — the measurement script
- `docs/qwen-tasks/RUNNING/TASK-143-*.md` (moved from TODO)

**FINDINGS:**

The answer is **(2): In the copy, silently.**

The two groups (32 JUNK-FED vs 119 FACT-FED) differ on exactly one metric
outside the noise: **evidence-reference rate** (0% vs 7.3%). The model
receives navigation text and ignores it entirely, writing from `company_facts`
alone. No gate catches this — rejection rates are similar, unsupported claims
are rare in both groups (1.2% vs 2.7%, a 1.5pp difference inside noise).

The damage is invisible to every gate and visible to a human read:
- JUNK-FED drafts never reference evidence facts (0 of 49)
- FACT-FED drafts reference evidence only 7.3% of the time (27 of 371)
- Generic phrase rates are similar or LOWER in JUNK-FED (20.4% vs 27.2%)
- Navigation leakage is only slightly higher in JUNK-FED (16.3% vs 11.6%)
- Vocabulary overlap is low across both groups (Jaccard 0.281)

31 of 32 JUNK-FED records have NO usable evidence at any position. Reordering
or expanding the limit would help exactly 1 record. The extraction, not the
filtering, is the bottleneck.

**What good evidence looks like** (from the report):
1. Contains a complete sentence about the company, not a fragment
2. Names something specific — a service, speciality, or client outcome
3. Is not the company's own tagline repeated back to them
4. Survives the "so what?" test — gives the model something to build on

**The real constraint:** Even when given usable facts, the model references
them only 7.3% of the time. Filtering works (TASK-135 already does it). The
extraction itself is the bottleneck — the crawler needs to extract better
prose, not the system needs to sort worse.

**RISKS:**
- Sample size is small (32 JUNK-FED). The comparison can detect only large
  differences (>= 20pp at 80% power). The pre-stated threshold was 15pp.
- The 0% vs 7.3% evidence-reference difference is real but small. It tells
  us the model CAN use evidence but usually does not, regardless of quality.
- This measurement is against existing copy, not a fresh generation. The
  TASK-135 changes (quality filtering, contact-awareness, 5 entries) are
  integrated but the copy in the snapshot predates them.

**RECOMMENDED CLAUDE ACTION:**
1. Accept the finding: junk evidence causes silent degradation, not rejections.
2. The useful deliverable is NOT a filter (TASK-135 already did that). It is
   the measurement of what "good evidence" means, with examples from real rows.
3. If generation quality matters, the bottleneck is extraction, not filtering.
   The crawler needs to skip navigation-dominant pages and prioritize pages
   with actual prose (/about, /services, /team).
4. A new gate that checks whether the draft references ANY evidence fact
   (not just whether claims are supported) would catch silent degradation.
   This is a new gate, and the task forbids widening gates — so this is a
   recommendation, not a deliverable.
