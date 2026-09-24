# Option A, the free-crawl route, and the sequencing that follows

Operator decisions, Zvonimir, 2026-09-25 ~00:35. Recorded here because both
change what tomorrow does, and because the handoff that set them up got one
thing backwards.

---

## 1. THE TWO DECISIONS

**Option A** on the eleven campaigns lane B found: new campaigns get the
four-step cadence; **485-500 stay three-step**; the 63 stopped leads on
496/497/498 go onto a **new** four-step campaign rather than back onto theirs.
No stored `cadence_steps` row is rewritten and no campaign is left
half-sequenced.

**The free-crawl route for the 128.** Lane D measured that of the 394 records
carrying free-crawl research, **366 (93%) would pass copylint rule 1 today**.
That clears the dominant push blocker with **no Apify spend and no branch
merge**, which also decouples tomorrow's push from the researchpack merge
decision.

---

## 2. THE HANDOFF HAD THE DANGER BACKWARDS, AND IT CHANGES THE ORDER

`PRODUCTION-HANDOFF-2026-09-24-LATE.md` §2 says:

> **The cadence is HALF-APPLIED AND MUST BE FINISHED BEFORE ANY PUSH.** ...
> until all four of these land together, a push fails in a place that does not
> name the cause.

**Measured on master at 5cd5173d, against the real campaign row for 491:**

    configured steps          ['em1', 'em2', 'em3']
    row cadence email keys    ['em1', 'em2', 'em3']
    _sequence_steps(...)      builds 3 steps, no refusal
                              em1 wait 3 / em2 wait 4 / em3 wait 1
                              thread_reply False / True / True

**The current state pushes fine.** The four step-4/step-5 templates sitting in
`src/cadence.py` are unused and break nothing — `_sequence_steps` compares the
CONFIG's keys against the CAMPAIGN ROW's keys, and those agree today.

Fed lane B's four-key config, the same row raises:

    FactoryRefused: `email_sequence.steps` declares ['em1','em4','em5','em2']
    and the cadence's email steps are ['em1','em2','em3']. These must be the
    same keys in the same order.

So **withholding the config is the safe state and landing it is what creates
the refusal.** "Must be finished before any push" is false; the truth is
"must not be landed until the campaigns it breaks are no longer needed."

This matters because the handoff's framing would have had a session land the
config first thing, at which point eleven campaigns — including the 63 stopped
leads' 496/497/498 and campaign 500 — refuse every stage, for no benefit until
the new campaigns exist.

---

## 3. THE ORDER FOR TOMORROW, WHICH FOLLOWS FROM §2

**Do NOT land lane B's config until the step before the push.** Concretely:

1. Confirm free-crawl coverage **on the 128 specifically**. Lane D's 93% is
   across all 394 researched records and is NOT the same question. Lane C has
   been asked for the 128 by name, plus how many of them match no queue record
   at all (lane D found 31% of rendered rows match none). This project's
   recurring failure is a headline number from a stage that had not asked the
   next stage's question — 1,508 exportable that was 114, 19,612 "IN" of which
   two-thirds were under the floor.
2. Crawl the gap, if there is one. That is the critical path, not Apify.
3. Create the new four-step campaigns: Bojan and Jakov, plus one for the 63
   stopped leads, plus a replacement for 500's batch-1b role.
   **Note 501 is taken** — a session consumed it for the stop-test campaign, so
   the pair lands on 502/503.
4. **Then** land lane B's config, when the old campaigns are no longer being
   staged to.
5. Then push the 128 under the gate, with the copylint wiring merged so the
   push refuses anything without a pack fact.

Campaign 500 keeps its three-step provider sequence (steps 4775/4776/4777) and
0 leads. Under option A it is not rebuilt, so it cannot serve batch 1b; it
stays parked rather than deleted, as the previous session left it.

---

## 4. WHAT THIS DOES NOT DECIDE

- The **researchpack merge** — deferred to after lane C reports, by the
  operator. The branch is pushed (`researchpack-four-sources-2026-09-24` @
  `dc33469d`); `origin/master` is untouched at `24acafff`.
- **Rung 3** — drafted per persona by lane D, awaiting approval. It needs
  `{our_company}` and `{capability}`, which do not exist in `src/cadence.py`,
  and a `productive.yaml` change. Lane D declared the dependency rather than
  editing lane B's files, and refused to hardcode "Productive" into shared
  `TEMPLATES` because it would leak into every other client.
- **Whether to merge lane D's copylint at all.** It is correct and proved on
  the real send path, and as things stand it refuses every push this system
  can make. Step 1 above is what makes merging it safe rather than blocking.
