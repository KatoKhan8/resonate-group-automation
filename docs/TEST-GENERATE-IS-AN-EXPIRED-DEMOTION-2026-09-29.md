PRIORITY: OPERATOR DECISION — BLOCKS BATCHING

# THE `test_generate` "DEFECT" IS AN EXPIRED OPERATOR DEMOTION

    measured at   master 3a742c5f, 2026-09-29

    test_generate today                              Ran 56, 2 failed, 1 error
    test_generate with demotion evaluated 2026-09-28 Ran 56, 0 failed, 0 errors

**There is no code defect.** The three failures are one rule reverting to
refusing on schedule, exactly as designed.

---

## WHAT IT ACTUALLY IS

`src/copylint.py`:

    DEMOTIONS = (
        ("step1_without_pack_fact", "2026-09-28",
         "PROOF MODE - leads in campaigns, proof first",
         "Zvonimir, 2026-09-25"),
    )

`warning_rules()` keeps a demotion while `today <= until`. Today is
**2026-09-29**. The demotion lapsed at the end of **2026-09-28**, so
`step1_without_pack_fact` went back to REFUSING — which the module's own
comment says is the intended behaviour:

> *"A demotion that outlives its deadline silently reverts - no human has to
> remember to edit a frozenset."*

## HOW IT PRODUCES ALL THREE FAILURES

One root cause, three symptoms. Traced through the real writer loop:

    writer call 1  the deliberately BAD draft   -> refused (4 reasons)
    writer call 2  the canonical GOOD draft     -> refused: step1_without_pack_fact
    writer call 3  the canonical GOOD draft     -> refused: step1_without_pack_fact
    contact held "copy_refused", sequences emptied, nothing stored

- `KeyError: 'rowan-blake'` — nothing was stored, so the cadence key is absent.
- `retry_prompts == 2` where the contract expects 1 — the good draft was
  refused twice instead of passing on the first retry.

The suite's canonical GOOD fixture opens step 1 with a line its pack does not
support. While the rule was demoted that was a warning; now it refuses.

## WHY THIS MATTERS MORE THAN THE SUITE — THE BATCH IMPACT

The rule is refusing **in production right now**, not only in tests. Its own
comment records the scale it was demoted for:

> *"It was refusing EVERY push this system can make ... of 927 rendered rows,
> 636 matched a record and ZERO carried a pack fact."*

Measured today on the live queue: of **400 productive records sampled, 125
carry research facts** — about **31%**. With the demotion expired, roughly
**two thirds of any batch would be refused at copylint**, after spending the
model calls to generate the copy.

Rachele is unaffected: her pack carries two real facts and `em1` opens with a
supported line, which is why her copylint is clean.

## THE DECISION — OPERATOR ONLY

This is a dated grant that only the operator can renew. Three options:

**A. Renew the demotion with a new deadline.** One line in `DEMOTIONS`.
Batching proceeds at today's pack coverage. The rule keeps firing and keeps
being counted and reported — it just does not stop the push. This is what the
2026-09-25 grant did, and the mechanism is designed to be renewed
deliberately rather than forgotten.

**B. Let it refuse and raise pack coverage first.** Honest, and expensive:
about 69% of the estate needs research facts before it can ship. That is a
sourcing/enrichment programme, not a code change.

**C. Let it refuse and accept a smaller batch.** Generate only from the ~31%
that already carry facts. Slowest per company, no new gate risk, no policy
change. The first 5-company batch only needs 5 qualifying companies.

**Recommendation: C for the first batch, then A or B as a considered policy.**
C needs no policy change and no new grant, and the first batch is small enough
that the 31% pool is ample. It also keeps the rule refusing, which is the
safer default while the copy gates are still settling.

**What must NOT happen:** editing the suite to expect the new behaviour, or
widening the rule. `CLAUDE.md`: *"Never widen a lint rule to make a draft
pass."* The rule is telling the truth about pack coverage.

## SEQUENCING CONSEQUENCE

The plan step *"fix known test_generate 2 FAIL + 1 ERROR -> full green"* is
not an engineering task and should not be dispatched as one. Under option A
the suite goes green the moment the demotion is renewed; under B or C the
suite needs its fixture pack aligned with its canonical good draft, which is
a small, honest test-fixture change and NOT a production-code fix.

**Until this is decided, the 5-company batch should not start**, because most
of it would be refused after paying for generation.
