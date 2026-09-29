PRIORITY: BLOCKS THE CANARY AND THE RAMP — OPERATOR DECISION NEEDED

# CANARY PHASE A — BLOCKED BEFORE THE FIRST PROVIDER WRITE

    measured at   master 3ddb879d, 2026-09-29
    approved      hash fba63864ca640b9e, Rachele Crumpler / 2020 Companies

    PROVIDER WRITES        0
    PROSPECT-FACING SENDS  0
    CAMPAIGN ACTIVATIONS   0
    sending.live           off, never turned on
    execution grant        never opened
    canary campaign        canonical row only, status HELD,
                           bison_campaign_id = None (never created)

---

## THE BLOCKER

The approved artifact carries a P.S. on `em1` and **none on `em3`**.
`bisonfactory.STEPS_REQUIRING_PS` is `{"em1", "em3"}` and TASK-560 states the
rule it enforces: *"the P.S. is required on these steps. A step in this set
whose `ps` field is absent or empty BLOCKS - it must never vanish silently."*

Measured on the record: `em3` has **no `ps` key at all**. Absent, not
deliberately empty. The staging guard cannot tell that apart from a P.S. that
was written and then lost, which is **incident 9** - the exact case the guard
was built for. **It is refusing correctly and has not been touched.**

The dry run is otherwise clean: four of five steps certify, `copylint` runs,
and the Bison sequence projects `em1..em5` with the right merge variables.

## HOW THE ARTIFACT CAME TO HAVE NO em3 P.S.

Operator copy direction, earlier on 2026-09-29: *"P.S. should normally contain
a genuinely interesting verified prospect fact... If there is no worthwhile
verified P.S. fact, omit the P.S."* Rachele's research pack carries exactly
two admissible facts; the agency description is spent on `em1`'s opening line
and Christ's Haven on `em1`'s P.S. There is no third fact, so the writer
correctly omitted `em3`'s rather than recycling the pitch or listing services
- both of which `copylint` refuses.

So the copy direction and the staging contract now disagree, and the artifact
the operator personally approved sits on the wrong side of the older rule.

## WHY THIS WAS NOT SELF-REPAIRED

Every route past it is one the standing authorization explicitly forbids:

    a) give em3 a P.S.              changes the approved copy and its hash
    b) relax STEPS_REQUIRING_PS     weakens an incident-9 guard
    c) make the P.S. expectation    changes approval-fingerprint semantics
       per-step and declared        estate-wide, invalidating every existing
                                    approval on every campaign

(c) is the principled fix and the one I would choose with authority, because
it is the only one that distinguishes *declared and lost* from *deliberately
none* - which is the distinction the guard actually wants. It is also the one
with the widest blast radius, so it is not a 48-hour-window improvisation.

**The guard that correctly detected the problem is not the thing to fix.**

## TWO DEFECTS FIXED ON THE WAY, NEITHER TOUCHING THE COPY

1. **The approval was not accountable.** `approve.approve_step` was stamped
   `by="Zvonimir (operator)"`, and `approval.is_accountable_approver` rejects
   it: that function wants an address or one of `OPERATOR_ARMS`
   (`operator`, `operator-control-arm`). `_certified_copy` therefore returned
   `None` for all five email steps and staging reported every one missing -
   a refusal whose message pointed at the copy while the cause was the
   signature on it. Re-stamped as an address with provenance. **Fingerprints
   unchanged**, so the words and hash `fba63864ca640b9e` are untouched.

2. **A reduced cadence spec crashes step expansion.** The canary campaign row
   first carried `{day, key, channel}` dicts; `cadence.expand_step` reads
   `spec["template"]` for any step not marked `generated: true` and raised
   `KeyError('template')`. The row now carries the canonical
   `PRODUCTIVE_LI_HEAVY_V1` email specs verbatim. Worth knowing for the ramp:
   a campaign row must carry the sequence's own specs, not a summary of them.

## ALSO CLEARED

`.git` carried an abandoned cherry-pick from **2026-09-27 00:46** (TASK-384),
which blocks every commit in this checkout. Cleared with
`git cherry-pick --quit`, which leaves HEAD and the working tree alone.
`--abort` would have reset HEAD to `fc473844` and destroyed two days of
commits.

## WHAT HAPPENS NEXT

The canary and therefore the whole ramp are stopped until (a), (b) or (c) is
chosen. Nothing else in the 48-hour authorization can proceed past this point,
because the ramp's first step is a proven live path and there is not one yet.

Posted to `#resonate-os` at ts 1790702331.963519.
