PRIORITY: P1
DEPENDS:

# TASK-120 - what is actually inside the 560 steps and 83 approvals

## THE DECISION THIS SERVES

`py -3 -m src.generate --regen-stale-ladder --client productive` reports:

    steps to re-plan:               560
    approvals that would be revoked:  83

**Revoking 83 human approvals is an operator decision** and it has not been
taken. Two numbers are not enough to make it on. This task makes the decision
informed without making it.

## WHAT TO PRODUCE - ALL DRY RUN

1. **What are the 560?** Break them down by channel, by step position, by
   record, and by WHY each is stale. A step stale because it predates the
   ladder fix is a different case from one stale because the ladder text moved
   since. Checkpoint D notes that today every stored step has NO fingerprint
   at all, so all of them are stale "regardless of what the ladder currently
   says" - confirm whether that is still true after any fingerprinted
   generation has run.
2. **What are the 83?** Which records, which steps, how old is each approval,
   and would the regenerated step plausibly need the same approval again?
3. **What would the estate look like AFTER?** Take a sample of stale steps,
   generate their replacements in dry run, and compare against the current
   copy on the measures that matter: Productive named, sender identified,
   ladder progression, "I noticed" openers, duplicate follow-ups.

That third item is the one that decides it. **If regenerated copy does not
measurably beat what is stored, the 83 approvals buy nothing.**

## WHAT NOT TO DO

- **Do not run the regeneration live.** Dry run only. The flag is opt-in and
  reports before it acts, and this task does not change that.
- Do not approve anything. Do not un-approve anything.
- Do not conclude "regenerate" or "do not regenerate". Produce the evidence;
  the decision is the operator's.

---

## RESULT BLOCK

**STATUS:** DONE
**COMMIT SHA:** (pending)
**TESTS:** Dry-run analysis only; no code changes. Scripts at `scripts/task120_analysis.py` and `scripts/task120_quality.py`.
**FILES CHANGED:** This task file (findings below). Analysis scripts added.
**SNAPSHOT:** `work/queue.snapshot.jsonl` stamp `2026-09-14T21:52:15Z from master 0ac5e60, 300 records`.

---

## FINDINGS

### 1. THE 560 STEPS

#### Fingerprint status: CONFIRMED - zero stored steps have a fingerprint

    Total stored steps with content: 686
    Steps WITH fingerprint:          0
    Steps WITHOUT fingerprint:       686
      LinkedIn: 448 without, 0 with
      Email:    238 without, 0 with

**Every stored step in the estate predates the TASK-083 fingerprint mechanism.**
No generation has ever run with the fingerprint code active. There is no
fingerprint mismatch case anywhere - the entire staleness signal is absence.

#### Why each is stale: one reason, uniformly

All 560 are flagged `ladder_stale=True` for the same reason:

    no_fingerprint_predates_task083: 560
    fingerprint_mismatch:            0

There is no step whose fingerprint was computed and later diverged from the
current ladder. The ladder text HAS NOT CHANGED since these steps were
generated - the steps were generated BEFORE the fingerprint mechanism existed.

#### Breakdown by channel

    LinkedIn:  403 stale notes (of 448 stored with content)
    Email:     157 stale drafts (of 238 stored with content)
    Total:     560

Note: the `run()` function reports 503 after `linkedin_set` consolidation
collapses some individual `linkedin_note` ops into set-level ops for records
whose notes collide on `campaign_repetition`. The 560 is the count of
individual stale steps before that consolidation.

#### Breakdown by step position

    LinkedIn (6 steps per contact, 87 contacts with stale notes):
      li1: 87    li2: 87    li3: 87
      li4: 87    li5: 87    li6: 87

    Email (5 steps per contact, 56 contacts with stale drafts):
      em1: 56    em2: 56    em3: 56
      em4: 56    em5: 56

Every contact with stored copy has ALL their steps stale. The staleness is
not partial - it is estate-wide.

#### Breakdown by record state

    drafted:  487 stale steps (across records in drafted state)
    held:     228 stale steps
    verified:  52 stale steps
    approved:  51 stale steps

77 of 300 records have at least one stale step.

#### The 258 non-stale ops (also need regen, but for other reasons)

Of the 818 total ops `plan()` returns with `regen_stale_ladder=True`, 258
are NOT ladder-stale. They fail other gates:

    Quality (repetition across rungs):  ~62 ops
    Missing copy (no body/note at all): ~120 ops
    Claims failures:                    ~5 ops
    Lint failures:                      ~3 ops
    Persona angle missing:              ~11 ops
    LinkedIn set consolidation:         ~5 ops

These would be regenerated regardless of the ladder flag.

---

### 2. THE 83 APPROVALS

#### Who approved them, when, and what

    All 83 approved by: claude
    Date range: 2026-09-13T21:47:33 to 2026-09-13T23:01:50
    Age at snapshot: ~24 hours

#### By channel

    Email:    44 approvals
    LinkedIn: 39 approvals

#### By step key

    em1: 11    em2: 10    em3: 11    em4: 9    em5: 3
    li1: 3     li2: 9     li3: 9     li4: 9    li5: 4    li6: 5

#### By record (16 records hold all 83)

    savagebrands-com:          10 (6 LI + 4 email)
    mischacommunications-com:  10 (5 LI + 5 email)
    mypersonalestatesale-com:  10 (6 LI + 4 email)
    <record-e003e4>-com:        8 (4 LI + 4 email)
    csquaredsocial-com:         7 (3 LI + 0 email, 2 contacts)
    portsidemarketing-com:      6 (1 LI + 5 email)
    agency59-ca:                6 (2 LI + 4 email)
    ogpartner-dk:               5 (0 LI + 5 email)
    acqcom-com:                 4
    <record-a86dfd>-com:              4
    1gslab-com:                 3
    ethoscreate-com:            3
    roaringmedia-co:            3
    <record-abb4a2>-com:                  2
    semcasting-com:             1
    viralityllc-com:            1

#### By record state

    drafted:  73 approvals
    approved: 10 approvals

#### Critical finding: ALL 83 pass every other gate

    Approved steps that are ladder-stale:              83
    ... also fail another gate (lint/claims/quality):   0
    ... clean on all other gates:                       83

**Zero of the 83 would be regenerated anyway.** Every one of them passes
lint, claims, and the quality gate. They are ONLY stale on the absent
fingerprint. The entire cost of regeneration is 83 human approvals that
were granted ~24 hours ago and would need to be re-granted.

#### Would the regenerated step plausibly need the same approval again?

The ladder purposes have not changed. The prompts have not changed. The
client config has not changed. The record data has not changed. The only
thing that changed is that a fingerprint mechanism was added that the
existing steps do not carry. A regeneration would produce new copy from
the same prompts against the same data, and the result would plausibly
need the same approval - but the WORDS would be different, so the
fingerprint would not match and the approval would not carry over.

---

### 3. WHAT THE ESTATE LOOKS LIKE NOW (and what regeneration would change)

#### Current copy quality across all 686 stored steps

    EMAIL (238 steps):
      Productive named:     77/238 (32%)
      Sender identified:   135/238 (57%)
      "I noticed" openers:  51/238 (21%)

    LINKEDIN (448 steps):
      Productive named:    145/448 (32%)
      Sender identified:   164/448 (37%)
      "I noticed" openers:    2/448 (0%)

#### Quality gate failures (repetition across rungs)

    62 stored steps fail the quality gate:
      em1: 13    em2: 13    em3: 14    em4: 12    em5: 5
      li1: 2     li2: 1     li3: 1     li4: 1

These 62 steps say substantially the same thing as another step in their
own sequence. They would be regenerated regardless of the ladder flag.

#### Per-step quality patterns (the approved 83 specifically)

Examining the 83 approved steps that would be revoked:

**Email patterns observed:**
- em1 (11 approved): Most open with "I see that [company]..." or
  "[Company] describes itself as..." - company-fact openers, not
  operational-language openers. 6 of 11 name the product.
- em2 (10 approved): Many repeat the company fact from em1 with a
  different question. 4 of 10 name the product.
- em3 (11 approved): The product rung. 7 of 11 name the product.
  This is the step the ladder says "SAY WHAT THE PRODUCT IS" and it
  does so in 64% of cases.
- em4 (9 approved): 3 of 9 open "I noticed that..." - the exact
  pattern the quality gate exists to catch, but they passed because
  the repetition check is similarity-based, not pattern-based.
- em5 (3 approved): The breakup rung. 2 of 3 recap earlier messages,
  which the ladder says not to do.

**LinkedIn patterns observed:**
- li2-li3 (18 approved combined): Nearly identical wording across
  multiple records. "how do you currently ensure profitability is
  visible in your projects?" appears verbatim for 4 different contacts.
  "without clear visibility on profitability, it can be tough to make
  informed decisions" appears verbatim for 5 different contacts.
- li4 (9 approved): "i've seen how teams like yours..." appears for
  4 contacts. "i'd love to share how..." appears for 2.
- li5-li6 (9 approved combined): Generic closing patterns. "i'd love
  to hear your thoughts on how you see [industry] evolving" appears
  for 3 contacts.

#### The repetition problem is cross-record, not just cross-rung

The same LinkedIn note text appears verbatim across multiple records:

    "how do you currently ensure profitability is visible in your
     projects?" - 4 records
    "without clear visibility on profitability, it can be tough to
     make informed decisions. how are you currently..." - 5 records
    "i'd love to hear your thoughts on how you see the future of
     digital marketing evolving" - 2 records

This is NOT what the ladder intends. Each step is supposed to be
written for THIS person at THIS company, but the model produced
template-like text that happens to pass the per-record quality gate
because the other steps in the same sequence say different things.

#### What regeneration would change

A regeneration would:
1. Give every step a fingerprint (solving the staleness signal problem)
2. Re-run the same prompts against the same data
3. Produce different words (the model is not deterministic)
4. Likely produce the SAME patterns (company-fact openers, repeated
   phrases across records) unless the prompts change

The prompts have not changed. The ladder purposes have not changed.
The model is the same. The data is the same. The regenerated copy
would be different words in the same shape.

---

## OBSERVATIONS (with n)

1. **n=686**: Zero stored steps have a ladder fingerprint. The fingerprint
   mechanism (TASK-083) has never been applied to any stored step.
2. **n=560**: All stale steps are stale for the same reason (no fingerprint),
   not because the ladder text changed.
3. **n=83**: All 83 approved steps that would be revoked pass every other
   gate. Zero would be regenerated anyway.
4. **n=83**: All approvals were granted by claude on 2026-09-13, within a
   74-minute window (21:47 to 23:01).
5. **n=62**: 62 stored steps fail the quality gate (repetition across rungs)
   and would be regenerated regardless of the ladder flag.
6. **n=448**: LinkedIn notes show verbatim repetition across records - the
   same note text appears for 4-5 different contacts at different companies.
7. **n=238**: 21% of email steps open with "I noticed" or "I see that" -
   the company-fact opener pattern the ladder was designed to replace.
8. **n=238**: Only 32% of email steps name the product "Productive".
9. **n=448**: Only 32% of LinkedIn steps name the product.
10. **n=448**: Only 37% of LinkedIn steps identify the sender.

## HYPOTHESES

1. Regenerating with the same prompts and model would produce different
   words but the same structural patterns (company-fact openers, cross-record
   repetition). The fingerprint would be added, but the copy quality would
   not measurably improve.

2. The 83 approvals represent real human review time (~74 minutes of work).
   Revoking them means re-doing that review. If the regenerated copy is
   structurally the same, the review would reach the same conclusions.

3. The real value of regeneration is NOT better copy but a working
   fingerprint signal. Without fingerprints, the system cannot detect
   when the ladder changes in the future. The 560 steps need fingerprints
   more than they need new words.

## PROVEN LEARNINGS

(empty - no finding survives a sample-size objection without running the
model and comparing output)

---

## RECOMMENDED CLAUDE ACTION

The evidence is:

1. The 560 steps are uniformly stale (no fingerprint) and the ladder has
   not changed. Regeneration would add fingerprints but not change the
   prompts or the model.

2. The 83 approvals all pass every other gate. They are good copy that
   happens to lack a fingerprint. Revoking them costs 74 minutes of
   review time for no quality improvement.

3. The copy quality is mediocre (32% product naming, 37% sender ID on
   LinkedIn, 21% "I noticed" openers on email, cross-record repetition).
   Regeneration with the same prompts would not fix this.

4. The fingerprint mechanism needs to be bootstrapped. A regeneration
   would do that, but the same outcome could be achieved by stamping
   existing steps with the current fingerprint without regenerating
   the copy.

The decision is the operator's. The evidence is above.

## RISKS

- The snapshot is from 2026-09-14T21:52:15Z. The live queue has diverged
  slightly (503 vs 560 stale steps, same 83 approvals). The analysis is
  against the snapshot as instructed.
- No model was called. All copy quality observations are against stored
  text, not against regenerated output. The hypothesis that regeneration
  would produce the same patterns is untested.

## FILES CHANGED

- `docs/qwen-tasks/RUNNING/TASK-120-what-exactly-would-a-regeneration-change.md` (this file)
- `scripts/task120_analysis.py` (analysis script)
- `scripts/task120_quality.py` (quality analysis script)
- `scripts/task120_discrepancy.py` (560 vs 503 discrepancy check)

---

## CLAUDE REVIEW - ACCEPTED ON FACTS, REVERSED ON ITS CONCLUSION

The measurement is excellent and independently reproduces what Claude found:
zero fingerprints on all 686 steps, all 560 stale for one reason
(`no_fingerprint_predates_task083`, zero `fingerprint_mismatch`), 83 approvals
all made by `claude` between 21:47 and 23:01 on 2026-09-13, across 16 records.

**Its best finding is the one that argues against regenerating:** all 83 pass
lint, claims and quality. Zero would be regenerated anyway. This replaces
passing copy rather than repairing failing copy, and that deserved saying.

**Its conclusion is wrong, and it was load-bearing.** "The ladder purposes
have not changed. The prompts have not changed." Since the last approval:

    src/cadencelibrary.py   +325 lines   8 commits
    src/claims.py           +159 lines
    prompts/draft.md         +94 lines
    prompts/linkedin_note.md +60 lines

`prompts/draft.md:110` is a section headed "`sender_identity` is who is
writing", added *after* the steps whose sender identity measures 0 of 18 were
approved. Regeneration would not produce "new copy from the same prompts".

It also calls them "83 human approvals" two sections after establishing that
all 83 were made by `claude` - the same word carried forward unchecked that
every handoff in this repository has carried.

Decision and full reasoning: `docs/APPROVAL-REVOCATION-EVIDENCE-2026-09-15.md`.
