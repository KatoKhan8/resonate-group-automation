PRIORITY: P1
SIZE: XL
DEPENDS: TASK-425
STATUS: BLOCKED

# TASK-462 — COMPANY FACT PROVENANCE (decision "A"). REQUIRED POST-SLICE.

> **BLOCKED ON PURPOSE. DO NOT UNBLOCK WITHOUT THE OPERATOR.** Unblock only when
> `TASK-425` has completed and the operator has reviewed the one-account
> artifact.
>
> **`DEPENDS:` DID NOT HOLD THIS BACK AND `STATUS: BLOCKED` IS WHAT DOES.**
> This file was written with `DEPENDS: TASK-425` in the belief that a dependency
> on unfinished work made it unclaimable. It did not: `claim_task.py`'s readiness
> check reads `meta["dependencies"]`, which is not this header line, and a Qwen
> worker claimed this task within the hour — i.e. it started building the
> architecture the operator had just said explicitly not to build tonight. The
> claim was released and this header added, because the readiness check *does*
> honour `STATUS: BLOCKED`.
>
> The general lesson, and the second instance of it in one night: **in this
> repository, a header line that expresses an intention is not a control.** The
> first instance was a critical-path brief marked "CLAUDE ONLY" in `TODO/`, which
> the pool would have handed to the next free Qwen worker because no such filter
> exists. Express a restriction in the mechanism that enforces it, or move the
> file out of the pool's reach.

**Operator decision, Zvonimir, 2026-09-28. REQUIRED work, and explicitly NOT to
be built tonight or before `TASK-425`.** It is recorded now, at full fidelity,
because it is the real fix for a hole that is currently plugged by a blunt
temporary policy, and a temporary policy nobody has written the replacement for
is how a stopgap becomes the architecture.

**Do not start this task while the one-account slice is unfinished.** It depends
on `TASK-425` for exactly that reason. The operator's words: "Do NOT build A
tonight; record it as required post-slice work."

## WHY IT EXISTS — what "B" costs

`ISSUE-048`. There are two independent claim-validation paths, and
`company_facts` carries **no provenance at all**: a value from the client's CSV
and the same value from verified public evidence are indistinguishable. So a
prospect-facing figure could be licensed by an unverified spreadsheet.

Decision **B** (approved the same evening, the immediate conservative fix) closes
that by refusing the six `CLIENT_SUPPLIED` keys as claim support outright. **B is
deliberately blunt and errs toward refusing**: a claim that a provider-sourced
value would legitimately support is ALSO refused when it happens to live under
one of those six keys. That cost is accepted as temporary. **This task is what
makes the cost unnecessary.**

## THE MODEL

**Every company fact that may eventually license prospect-facing copy carries
provenance AT FACT LEVEL, NOT FIELD LEVEL.** At minimum, per fact:

    value
    source type
    source identifier          URL, or file + row
    observed/retrieved timestamp   where applicable
    verification / admission status
    licensed for prospect-facing copy   yes/no

**THE RULE, and it is the whole task in one line:**

> **Same value + different provenance = different claim authority.**

The operator's own example, which is also the acceptance test:

    employee_count 4000, from the CLIENT_SUPPLIED CSV
        -> usable for strategy
        -> NOT sufficient for a prospect-facing claim

    employee_count 4000, from verified admitted public or stored evidence
        -> MAY support a claim, if the normal evidence gates pass

Note what that second line does NOT say: provenance makes a claim *eligible*, it
does not make it *licensed*. The existing gates still run. Provenance replaces a
blanket refusal with a question the system can actually answer; it is not a
bypass, and it must not become one.

**The same model then applies to:** funding, hiring, revenue, tech stack, job
openings, growth, acquisitions, leadership changes. Design for those from the
start rather than retrofitting six keys — but do not *implement* them
speculatively either; the point is that the shape generalises.

## WHAT MAKES THIS HARD, recorded so it is not rediscovered

1. **Existing records.** Facts already stored carry no provenance and cannot have
   one invented. `UNKNOWN` is the honest value and must be distinguishable from
   absence. Missing evidence is never positive evidence, and an `UNKNOWN`
   provenance must fail closed for claims — otherwise migration silently licenses
   everything that predates the migration.
2. **Two validators, one model.** The pack path (`packfacts.pack_for` ->
   `copylint.untraceable`, `sequencegate.check`) and `src/claims.py` must read the
   SAME provenance. A second representation of the same truth is how the two
   drift, and this repository has that defect on record more than once.
   `src/claims.py` has six live callers: `eligibility` (x2), `executionguard`,
   `bisonfactory`, `heyreachfactory`, `generate`.
3. **B must be REMOVED, not left beside A.** When this lands, the six-key
   refusal is deleted in the same change, or the system carries two answers to
   one question and the blunt one wins silently.
4. **Prefer canonical state.** `company_facts` on the record is the canonical
   home that qualification and strategy already read. Do not build a parallel
   fact store; extend the one that exists.

## ACCEPTANCE (to be sharpened when the task starts, not before)

1. The same value from two provenances yields two different claim authorities,
   proved through BOTH validation paths and through a real production entrypoint.
2. Qualification, segmentation, prioritisation, strategy and offer selection keep
   full access to client-supplied facts — proved, not assumed.
3. A fact with `UNKNOWN` provenance cannot license a prospect-facing claim.
4. **B's six-key blanket refusal is removed in the same change**, and a test
   proves the CSV-only claim is still refused afterwards — by provenance now,
   rather than by key name.
5. Mutation: make provenance ignored, and prove the intended test fails.
6. No `hasattr`, no source-text assertions. Never weaken a validator.

## BOUNDARIES

Provider writes 0. Never call a real provider. The freeze applies. This task
changes what copy may ASSERT, so it is prospect-facing by definition: any
question about what a given provenance licenses goes to the operator, in the
decision format, rather than being resolved by whoever is implementing.
