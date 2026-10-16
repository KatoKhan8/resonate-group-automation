# CANARY-01 — CRITERIA 3, 5 AND 9 RE-AUDITED AGAINST TONIGHT'S COMMITS

TASK 0210 (pilotcaps), 2026-10-16. **A verdict moves here only on evidence
produced in this run.** No lane's report of its own work was accepted; every
number below was re-measured, and two of the brief's own premises did not
survive.

    T1   wt-pilotcaps-2026-10-14              008aa86dd   CRLF (CR=15)
         branch task-pilotcaps-pool-readback-2026-10-16
    T2   resonate-trees/wt-pc0210-e84108f5d   e84108f5d   LF   (CR=0)
         DETACHED at a named SHA, created for this audit, owned by no track
    origin/master                             b1f290c84   UNCHANGED, verified

**T1 is CRLF and T2 is LF.** No name-set is diffed across that boundary in this
document: each criterion's instrument is measured for its own absolute verdict
in the tree that holds it, and the one cross-tree comparison made (§5's bypass
sites) is a comparison of *source-derived site keys*, which line endings cannot
move.

**No provider call. No network. No `--live`. No cap or gate change. The real
`STOP-SENDING` file was never created** — asserted `False` before and after the
plant harness ran.

    e84108f5d contains 50cdfe48e, 97fec582d and 0c687f813   verified
    T1 contains 50cdfe48e and 97fec582d, NOT 0c687f813 or e84108f5d

---

## 0. THE TABLE

| # | criterion | authority | inside repo? | command | output | verdict |
|---|---|---|---|---|---|---|
| 3 | li1 renders a real connection note for every contact, RED if empty | `config/linkedin/productive-standard.json` CONNECTION_REQUEST payload — **and** `DECISION-linkedin-connection-note-2026-10-15.md`, which outranks it | **split**: the config is in the repo; the decision that governs it is **outside**, in `resonate-ops`, readable by the operator and any lane given the absolute path | `py -3 -B -m unittest tests.test_the_empty_connection_note_is_an_operator_decision` + direct read of the node payload, both trees | pin **OK**; payload `{'messages': [''], 'fallbackMessage': ''}`; `{connection_note}` placeholder **absent from the file**; 1 config, 1 node, identical at T1 and T2 | **NOT MET** |
| 5 | the count of write paths that bypass the gate is zero, against a real denominator | `scripts/write_path_denominator.py` (the analyzer) + `scripts/known_write_bypasses.json` (the baseline) | **inside**, both | the analyzer run against each tree's ROOT; `py -3 -B -m unittest tests.test_no_new_write_bypasses_the_door` (T1 only — the module does not exist at T2) | **58 call sites, 26 BYPASS, 32 gated — at BOTH SHAs**; 21 distinct bypass site keys at both; pin **FAILED (2 names)** at T1 | **NOT MET** |
| 9 | a kill switch the operator can operate alone, named and tested | `src/haltfile.py` + seven test modules | **inside** at T2; **absent entirely** at T1 | the seven modules at T2; then five planted violations | **Ran 36 — OK**, failing names none; **all 5 plants CAUGHT** | **MET at `e84108f5d`** / **NOT MET at T1** |

---

## 1. CRITERION 3 — NOT MET, AND IT NEEDS A DECISION

**One sentence.** `li1` must render a real connection note for every contact,
and the check must go RED when the note is empty.

**Authority, and it is split.** The bytes are
`config/linkedin/productive-standard.json`, inside the repo. What those bytes
*mean* is `resonate-ops/DECISION-linkedin-connection-note-2026-10-15.md` —
**outside** the repo. The operator can read it; a lane can only if a brief
hands it the absolute path. That split is the whole reason this criterion is
stuck: the repository cannot tell, from its own contents, whether an empty note
is blocker B3 or a decision, and for one day it was both.

**Measured, at both SHAs:**

    py -3 -B -m unittest tests.test_the_empty_connection_note_is_an_operator_decision
      T2 e84108f5d   OK
      T1 008aa86dd   OK
    py -3 -B -m unittest tests.test_a_connection_request_may_carry_no_note
      T2 e84108f5d   OK              (the complement: the validator may not refuse it)

    the CONNECTION_REQUEST node, read directly:
      config/linkedin/productive-standard.json
      graph.unconditionalNode.unconditionalNode
        nodeType  'CONNECTION_REQUEST'
        payload   {'messages': [''], 'fallbackMessage': '',
                   'toBeWithdrawnAfterDays': 21}
      identical bytes at T1 and T2.

**The pin passing is not the criterion passing, and that is the trap here.**
`test_the_empty_connection_note_is_an_operator_decision` goes RED **if anyone
fills the note** — it is a drift guard on a decision, pointing the opposite way
from criterion 3. Both of its directions are green, and criterion 3 is still
NOT MET. Reading "OK" as progress on 3 would be reading a guard against the
fix as evidence of the fix.

### The sub-question that WAS open and is now settled

The pin's own docstring names an uncovered direction: `src/heyreachfactory.py`
maps `li1 -> {"role": "connection_note", "kind": "MESSAGE"}`, so a note could
in principle ship as a **per-lead merge variable** rather than from this JSON —
and `CONTEXT-RESET-2026-09-15-E` says exactly that about HeyReach sequences.
The docstring says which of the two authorities actually ships "is being
measured under `queue/glm/0068`, which had not been dispatched when this was
written".

**`glm/0068` never ran.** It is in
`resonate-ops/queue/glm/DONE/20261016-0045-HANDCLOSED-0068-two-sources-of-linkedin-copy.md`
— **HANDCLOSED** at 00:45 by a human, not executed by a lane. So nothing
measured it, and per the standing rules a brief in DONE is gone.

**Measured here instead, and it is one line of evidence:**

    the string "{connection_note}" appears in
    config/linkedin/productive-standard.json   ZERO times
    across every file in config/linkedin/      1 file, 1 node, 0 placeholders

**There is nothing in the provider graph for a per-lead note to substitute
into.** So there are not two authorities shipping; there is one, and it ships
empty. The `heyreachfactory` role mapping is real code with no slot in the
graph it feeds. **That is the answer `glm/0068` was written to get, and it did
not need a dispatch — it needed one grep that nobody ran.**

**VERDICT: NOT MET.**

**Next action: a DECISION, the operator's.** Criterion 3 as written contradicts
his own standing decision of 2026-10-15 22:35 that connection requests go out
without a note. Nobody can code past that. He either reverses the decision (and
then the note has to be written, approved and the pin removed) or he **rewrites
criterion 3** to say what he actually wants — which, on tonight's evidence, is
"the connection request carries no note, deliberately, and the graph has no
placeholder that could silently fill it". **Recommendation: rewrite the
criterion.** The second form is already true and already pinned in both
directions; the first would reopen copy approval the week of a first send.

> **WITHDRAWN 2026-10-16 by TASK 0220 (pilotcaps). The recommendation above is
> superseded; the paragraph is kept because it is the record of what 0210
> concluded, not because its advice still stands.**
>
> 0210 measured one graph - `config/linkedin/productive-standard.json` - and
> read its empty note as a decision. That file declares its own provenance:
> `source_campaign_id 565765`, `PRODUCTIVE - SOFTWARE DEVELOPMENT - JELENA -
> AUGUST 24`. **That is the client's campaign**, named explicitly as *not ours,
> REPORT ONLY* by the standing rule of 2026-10-15 23:45. Our own campaign
> 599020 **does** carry `{connection_note}` on its CONNECTION_REQUEST node
> (`glm/0068`, graph hash `32f8dde79bfa0f27`).
>
> So "the graph has no placeholder" is true of the client's graph and false of
> ours, and adopting it would **write a defect down as a decision** - the one
> outcome criterion 3 exists to prevent. The note is not empty because the
> mechanism is missing; it is empty because the only consumer reads a hardcoded
> path (`scripts/batch_linkedin_push.py:76`) to a read of someone else's
> noteless campaign, while the client config key that names a source
> (`productive.yaml:1001`, `linkedin_standard_source: 565765`) has **zero
> readers** in `src/`, `scripts/` and `tests/`.
>
> The replacement wording, the case against it, and what would have to be true
> for it to be MET (measured: nought of four, one partial) are in
> `resonate-ops/PROPOSAL-criterion-3-2026-10-16.md`. **Criterion 3 itself is
> unchanged** - in this repository and in `CANARY-01.md`, which lives outside
> git and whose bytes were verified untouched. It is the operator's sentence.

---

## 2. CRITERION 5 — NOT MET, AND THE BRIEF'S PREMISE DID NOT SURVIVE

**One sentence.** The number of mutating provider call sites that do not pass
the write door is zero, measured against a denominator that is derived rather
than kept by hand.

**Authority: inside the repo**, both halves — `scripts/write_path_denominator.py`
derives the denominator from the source, and `scripts/known_write_bypasses.json`
is the pinned baseline.

**The brief says glm-c 0210 landed a "58-site inventory, 0 violations". It did.
It is not this criterion.**

    glm-c's test asks:  is every mutating provider call
                        DOOR-WIRED **OR** A BRAKE
    criterion 5 asks:   does every mutating provider call pass THE DOOR

That is a **disjunction against a conjunction**. A site that bypasses
`providerwrites.perform` entirely satisfies glm-c's inventory as long as it
consults the STOP-SENDING brake directly. Same denominator, 58, two different
questions — and reading one as the other is exactly the "two authorities for
one number" failure this repository keeps recording.

**Measured, the analyzer run against each tree's ROOT from one process, so the
analyzer itself is held constant:**

    tree                 writers  call sites  verdicts
    T1 008aa86dd (CRLF)        2          58  {'BYPASS': 26, 'gated': 32}
    T2 e84108f5d  (LF)         2          58  {'BYPASS': 26, 'gated': 32}

    distinct BYPASS site keys:  T1 = 21,  T2 = 21

**26 of 58 at both SHAs. The count did not move.** The only difference between
the two trees' bypass *sets* is one site renamed:

    FIXED in T2   - scripts/batch_activate.py::main::bison.resume_campaign
    NEW   in T2   + scripts/batch_activate.py::gated_resume::bison.resume_campaign

glm-c's 0200 lifted the resume out of `main` into a new `gated_resume`, which
calls `providerwrites.CONDITIONAL[EMAIL_RESUME]`, then `killswitch.require`,
then `haltfile.require_released()`, **and then the verb directly**. So the site
is now genuinely guarded by three gates — and still counts as a door bypass,
because it does not go through `perform`. **That is not the analyzer being
wrong. It is criterion 5 measuring door-wiring and glm-c having built guarding,
which are not the same property.**

**And one claim worth checking before it is repeated.** glm-c 0200's subject
says the resume paths "now consult suppression". `src/suppression.py` **does
not exist at `e84108f5d`** — it is the suppression lane's module and that
branch does not contain it. The claim is nonetheless **true on its own terms**:
what `gated_resume` consults is `providerwrites.CONDITIONAL[EMAIL_RESUME]`,
TASK-331's pre-send suppression revalidation, a different and older authority.
No correction is owed; the ambiguity in the word is worth naming so nobody
reads it as criteria 1/2 having moved.

**The pin, at T1 only** — `tests/test_no_new_write_bypasses_the_door.py` is a
pilotcaps artifact and **does not exist at `e84108f5d`**:

    py -3 -B -m unittest tests.test_no_new_write_bypasses_the_door
      T1   FAILED (failures=2)
           test_no_bypassing_call_site_is_new
           test_the_baseline_has_not_fallen_behind_the_code
           over scripts/batch_linkedin_push.py::stage_rows_to_list::heyreach.add_leads_to_list
      T2   ModuleNotFoundError — the module is not in that tree

Those two names reproduce the "2 new failing names" that 0170 recorded for the
integration tree. **Neither is new tonight and neither is pilotcaps 0200's**:
that task touched neither file. **The baseline must not be regenerated to make
them green.**

**VERDICT: NOT MET. 26 of 58 at both SHAs.**

**Next action: CONSTRUCTION, and the fixes already exist unapplied.** Route the
bypassing sites through `perform` under verbs that are already in `SUPPORTED`.
The nearest one, and the one CANARY-01 actually needs, is
`bison.attach_senders` → `bison.assign_sender`: pilotcaps 0200 measured that
the write door does **not** refuse a sender attach at all, and that the only
thing stopping one today is that `create_campaign` is gated and no campaign
exists. **The operator's part is one decision** — whether a change under `src/`,
owing a fresh suite reference, is acceptable in the week of a first live send.

---

## 3. CRITERION 9 — MET AT `e84108f5d`, AND THE PLANTS PROVE IT

**One sentence.** There is a kill switch the operator can operate alone,
named, tested, and effective without asking anyone for permission.

**Authority: inside the repo at T2** — `src/haltfile.py`
(`STOP_SENDING_PATH`, `BRAKE_OPERATIONS`, `OperatorStop`,
`require_released()`) plus seven test modules. **The switch's own state is
outside**: `C:\Users\Zvonimir\Desktop\resonate-ops\STOP-SENDING`, a file whose
mere presence refuses the transport. Only the operator needs to read or write
it, which is the point — the brake is a filesystem fact, not an API call, so
it needs no credential, no deploy and no session.

**At T1 (`008aa86dd`) `src/haltfile.py` does not exist and no `stop_sending`
test module exists. Criterion 9 is NOT MET there.**

**Measured at T2:**

    py -3 -B -m unittest -v <the seven brake modules>
      Ran 36 tests — OK          failing names: none

      no_path_reaches_a_transport_without_passing_the_stop_sending_brake   OK
      bisonfactory_consults_the_stop_sending_brake_before_each_transport   OK
      the_operator_can_pull_the_stop_sending_brake_alone                   OK
      the_stop_sending_brake_asks_nobody_for_permission                    OK
      the_stop_sending_brake_fails_closed_when_it_cannot_be_read           OK
      the_stop_sending_brake_refuses_the_transport_immediately             OK
      the_stop_sending_brake_stops_the_resume_scripts                      OK

### The plants — because a check that passes has to be shown capable of failing

Five violations planted one at a time in T2, each file restored
byte-identically and verified by sha256, `PYTHONDONTWRITEBYTECODE=1`
throughout. **The real `STOP-SENDING` file was asserted absent before and after
and was never created** — every plant is a source edit.

    P1  the door stops consulting the brake              CAUGHT by 5 names
        (providerwrites: `if operation not in BRAKE_OPERATIONS` -> `if False`)
          test_an_unreadable_brake_refuses_the_transport
          test_the_brake_pulled_after_the_last_gate_still_refuses
          test_the_file_present_refuses_and_the_transport_is_unreached  (+2)

    P2  bisonfactory stops consulting the brake          CAUGHT by 1
          test_every_mutating_provider_call_is_door_wired_or_a_brake

    P3  the resume script stops consulting the brake     CAUGHT by 2
          test_every_mutating_provider_call_is_door_wired_or_a_brake
          test_the_brake_refuses_every_resume_in_the_batch

    P4  the brake asks for a permission first            CAUGHT by 15
        (`require_released` returns early unless ALLOW_THE_BRAKE is set)
          test_a_path_it_cannot_stat_refuses_rather_than_sends
          test_a_permission_error_on_lstat_refuses_rather_than_sends
          test_absent_present_and_unreadable_with_no_machinery          (+12)

    P5  a NEW ungated mutating provider call site        CAUGHT by 1
        (a bare `bison.resume_campaign` added to batch_activate.py)
          test_every_mutating_provider_call_is_door_wired_or_a_brake

    undetected: none        every file restored, sha256 identical

**P5 is the one that matters most**, because it is the claim "58 sites, 0
violations" put under attack: a brand-new ungated mutating call site **is**
caught by the inventory. The inventory has reach, not just a clean count.

**P4 is the second most important.** A brake that can be made to ask for
permission is not a brake the operator can pull alone, and fifteen tests go red
rather than one — the property is held at several levels, not pinned once.

**VERDICT: MET at `e84108f5d`. NOT MET at T1. The global verdict is therefore
not "MET" but "MET on a branch that nothing has merged."**

**Next action: CONSTRUCTION, and it is an integration, not a build.**
`e84108f5d` has to reach a tree that also holds criteria 1, 2, 4 and 7's
mechanism — which today is T1's lineage, and T1 does not contain it. The merge
owes a fresh suite reference (both trees change `src/`). **Nobody's decision is
blocking it.**

---

## 4. THE FINDING THAT STILL OUTRANKS ALL THREE

0160 recorded that **no tree holds more than one proof**. Still true, and now
with a sharper second instance measured in both directions:

    at T1 008aa86dd      src/suppression.py              PRESENT  (crit 1, 2)
                         tests/test_no_new_write_bypasses PRESENT  (crit 5 pin)
                         src/haltfile.py                 ABSENT   (crit 9)

    at T2 e84108f5d      src/haltfile.py                 PRESENT  (crit 9)
                         src/suppression.py              ABSENT
                         tests/test_no_new_write_bypasses ABSENT

**Each tree's criterion-5 instrument is missing from the other tree, and so is
each tree's strongest proof.** The two lanes did not disagree about anything;
they built in places that have never been brought together. "All nine true at
once" has still never been measured anywhere, and tonight did not change that.

---

## 5. WHAT WAS NOT MEASURED, NAMED RATHER THAN GLOSSED

- **No full suite was run.** Three criteria, measured by their own named
  instruments. The merge gate for either branch is **UNMET** and is not claimed.
- **Criteria 1, 2, 4, 6, 7 and 8 were not in this task's scope.** 7 is
  pilotcaps 0200 (`docs/CANARY-01-POOL-READBACK-2026-10-16.md`); 6 and 8 rest on
  artifacts outside the repository and were last measured 2026-10-14/15.
- **`test_a_suppressed_address_cannot_reach_a_provider` errors at T2** with
  `ModuleNotFoundError` because `src/suppression.py` is absent. That is a
  tree-composition fact, recorded in §4, not a regression in glm-c's work.
- **The measurement tree is removed after this audit.** To recreate it:
  `git worktree add --detach <path> e84108f5d`. It was detached at a named SHA
  that no track owns, per the standing rule, so nothing could move under it
  while it was measured.
