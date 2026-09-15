PRIORITY: P1
DEPENDS:

# TASK-139 - the relationship states we can actually prove, and what each one forbids

## THE PROBLEM IS NOT THAT HISTORY IS MISSING

It is that history exists and only ONE bit of it reaches a production decision.
`build_control_cohort.py` holds out contacts carrying a `bison_lead_id` - 29 of
277 - and that is the entire relationship model in the live path. Everything
else the estate knows about a person is inert.

That single bit conflates cases that must be treated differently:

    previously emailed, no reply
    previously emailed, replied NEGATIVE
    previously emailed, replied POSITIVE
    previously emailed, reply UNKNOWN
    already a LinkedIn connection
    previous LinkedIn outreach, no reply
    suppressed / DNC
    nobody has ever contacted them

A previous POSITIVE reply is not a reason to hold somebody out of outreach -
it is a reason to treat them as a warm relationship rather than send them a
connection request. Holding all of them out equally is as wrong as sending to
all of them equally.

## WHAT THIS TASK IS - MEASUREMENT FIRST, AND IT MAY BE ALL OF IT

Read the snapshot, not the queue:

    work/queue.snapshot.jsonl     read-only copy of production
    work/queue.snapshot.STAMP     when, and from which commit

**Quote the stamp in your result block.** A measurement against a snapshot is
a measurement at a moment and the moment is part of the answer. Never write to
either file.

Answer, with counts:

1. For each state above, how many contacts in the estate are in it, and WHAT
   FIELD PROVES IT. A state you cannot evidence is not a state - report it as
   unknown and say what would be needed.
2. Which of those states are already computed somewhere in `src/`, by name.
   `engagement`, `touch`, `events`, `replies`, `linkedinstate` and
   `eligibility` all hold something adjacent. Name the function and say what
   reads its answer.
3. **THE ONE THAT MATTERS: which of them changes a decision today?** For each
   state, trace whether any production path - channel choice, cohort
   membership, connection request vs message, copy, cadence - reads it. A
   state computed correctly that nothing consumes is the recurring defect in
   this repository and finding one is a result, not a failure.
4. LinkedIn connection state specifically. The 599020 sequence root is
   `CHECK_IS_CONNECTION`, so the PROVIDER branches at runtime and a connection
   request never reaches an existing connection. Given that, state precisely
   what a local connection-state model would add that the provider's own
   branch does not. It may be little. Say so if so.

## WHAT YOU MAY NOT DO

- No provider calls. You hold real keys and the rule is READS ONLY at every
  provider; this task needs none at all.
- Do not write to `work/`.
- Do not change `eligibility.must_not_contact`. Suppression and DNC semantics
  are not this task's to move.

## IF THE MEASUREMENT LEAVES TIME

Propose - in the task file, as a design, with the consumer named - the
smallest change that would make ONE additional state change ONE real decision.
Smallest, with a named consumer. Not a state machine.

## FILES ALLOWED

    docs/RELATIONSHIP-STATE-2026-09-15.md   (new, your findings)
    scripts/task139_*.py                    (measurement scripts)
    the task file itself

## FILES FORBIDDEN

    src/  (anything - this task REPORTS; Claude changes the live path)
    work/ (anything)

## DELIVERABLE

The counts with their evidence fields, the consumed/not-consumed verdict per
state traced to a named caller, the snapshot stamp, and the one proposed
change with its consumer.

## RESULT BLOCK

**STATUS:** DONE

**SNAPSHOT STAMP:** `2026-09-14T21:52:15Z from master 0ac5e60 300 records`

**COMMIT SHA:** eafd777

**TESTS:** No code changes in src/. Measurement script: `scripts/task139_measure.py`. Findings document: `docs/RELATIONSHIP-STATE-2026-09-15.md`.

**FILES CHANGED:**
- `docs/RELATIONSHIP-STATE-2026-09-15.md` (new) — full findings
- `scripts/task139_measure.py` (new) — measurement script
- `docs/qwen-tasks/RUNNING/TASK-139-*.md` (moved from TODO, result block added)

**FINDINGS:**

1. **Counts with evidence fields:**

   | State | Count | Evidence field |
   |-------|-------|----------------|
   | `bison_lead_id` present | 29/92 | `contact["bison_lead_id"]` |
   | Previously emailed, no reply | 0/92 | `events[]` type `push_marked`/`email_delivered` |
   | Replied NEGATIVE | 0/92 | `events[]` type `reply_received` + classification |
   | Replied POSITIVE | 0/92 | Same |
   | Reply UNKNOWN | 0/92 | Same |
   | Already LinkedIn connected | 0/92 | `events[]` type `linkedin_connected`/`connection_accepted` |
   | Previous LinkedIn outreach, no reply | 0/92 | `events[]` type `push_marked` for LinkedIn |
   | Suppressed / DNC | 0/92 | `contact["suppressed"]`, domain list, `agencydnc` |
   | True cold (no history) | 91/92 | Absence of all touch events |

2. **Consumed vs not-consumed:**

   - **Suppression/DNC** → `eligibility.must_not_contact()` → `eligibility.decide()` → CONSUMED, blocks everything
   - **LinkedIn connection state** → `linkedinstate.connection()` → `linkedinstate.plan_step()` → CONSUMED, selects branch
   - **Reply blocking** → `eligibility._replied()` → CONSUMED, stops sequence
   - **Confirmed touch** → `account.has_confirmed_touch()` → `outreachclaims.resolve()` → CONSUMED for claim gating, NOT for channel/copy choice
   - **`bison_lead_id`** → `build_control_cohort.eligible_contacts()` → NOT consumed by live send path, only by a script
   - **Reply classification** → `replies.classify()` → `accountpolicy.apply_reply()` → WIRED but has never fired (zero replies)

3. **LinkedIn connection state specifically:**

   The provider's `CHECK_IS_CONNECTION` root node branches at runtime and handles the already-connected case correctly. The local model (`linkedinstate.connection()`) adds planning-time knowledge (pre-staging validation, copy selection, screen display) but NOT runtime safety the provider lacks. The provider is the load-bearing gate; the local model is the map.

4. **Proposed smallest change:**

   `heyreachfactory._plan()` reads `contact["bison_lead_id"]` and selects the `already` branch (message chain, no connection request) instead of the `cold` branch. Consumer: `heyreachfactory._plan()`. This makes prior-outreach contacts receive warm copy rather than cold copy, instead of holding them out entirely.

**RISKS:**
- The estate is in a pre-send state with almost no relationship data. These findings describe the architecture's readiness, not its track record.
- The `log` array carries 740 `linkedin_note` entries that are NOT structured events. If these are meant to be confirmed touches, the event model has a gap.

**RECOMMENDED CLAUDE ACTION:**
- Review `docs/RELATIONSHIP-STATE-2026-09-15.md` for accuracy
- Decide whether `bison_lead_id` should route contacts to the warm branch in `heyreachfactory._plan()` (the proposed change)
- Decide whether `linkedin_note` log entries should be promoted to structured events
