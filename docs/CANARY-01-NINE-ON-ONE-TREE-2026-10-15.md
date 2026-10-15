# CANARY-01 — the nine, measured on ONE tree

TASK 0170 (pilotcaps), 2026-10-15. Entirely offline: no provider, Apify, Slack
or network call; nothing attached; no cap or gate changed; no decision file
edited; nothing merged or pushed to master.

TASK 0160 returned the finding that outranked its own audit: **no tree held
more than one proof.** Five lane branches, one common ancestor, and not one of
them contained `origin/master`. Every one of the nine verdicts was therefore a
claim about a tree rather than about the system, and "all nine true at once"
had never been measured anywhere.

This file is that measurement. It is taken on a single integration branch that
contains `origin/master` and all five lanes.

**It is a measuring instrument, not a release.** It is not merged to master and
must not be. Nothing here fixes a NOT MET.

---

## 0. THE HEADLINE

**Nothing fell over.** No criterion that was MET in its own tree is NOT MET
here. That was the result this task was most alert for and it did not happen.

**Two things did happen, and both are the same lesson twice:**

1. **Criterion 4's collision reproduced exactly as predicted** — three
   `expectedFailure` names disappeared and the same three appeared as
   unexpected successes, so the scalar did not move. Paid off in M5a.
2. **Criterion 5 collided in a way nobody had predicted**, and it is the more
   interesting of the two. The bypass count is **26 before and 26 after**, and
   the pinned key-set moved by exactly one name in each direction. The
   instrument built for criterion 5 caught its own author's branch being
   integrated with someone else's.

**And criterion 4 was MET on a weaker instrument than it looked.** In glm-c's
own tree the criterion could only be asked of **9 tests**, because the module
that asks the harder half of the question does not exist there. In
glm-review's own tree it was **23 tests with the defect pinned, not fixed**. On
the integrated tree it is **29 tests, all green**. The integrated MET is a
different and stronger statement than either tree could make.

---

## 1. THE SHAPE, PUBLISHED — WHICH PROOF LIVES WHERE

Measured 2026-10-15 20:27-20:46Z. `git cat-file -e <ref>:<path>` over nine
refs; `Y` means the artifact exists on that ref.

    OM   = origin/master              b1f290c84   the authority
    lm   = refs/heads/master (local)  5fc5784fc   moved 00:13 today, unpushed
    sup  = task-suppression-2026-10-14           9bd8648f5
    glmb = task-glm-b-2026-10-14                 9e7c7ec72
    glmc = task-glm-c-2026-10-14                 9949dc205
    glmr = task-glm-review-2026-10-14            fc78e9b4e
    halt = task-glm-halt-failopen-2026-10-15     b77cd4b20
    pilo = task-pilotcaps-enforcer-2026-10-14    7a2890022
    INTG = integ/canary-nine-2026-10-15          13e2e825d  <- this branch

    artifact (the thing a criterion's command needs)      OM lm sup glmb glmc glmr halt pilo INTG
    src/suppression.py                                     .  .   Y    .    .    .    .    .   Y
    tests/..._suppressed_address_cannot_reach_a_provider    .  .   Y    .    .    .    .    .   Y
    tests/..._a_provider_bounce_reaches_the_record          .  .   Y    .    .    .    .    .   Y
    tests/test_linkedin_note                                Y  Y   Y    Y    Y    Y    Y    Y   Y
    tests/..._empty_connection_note_is_an_operator_dec..    .  .   .    .    Y    .    .    .   Y
    tests/..._every_template_is_inside_the_word_contract    .  .   .    .    Y    .    .    .   Y
    tests/..._no_template_escapes_the_word_contract         .  .   .    .    .    Y    .    .   Y
    tests/..._word_ceiling_is_enforced_on_the_composed..    .  .   .    .    .    Y    .    .   Y
    tests/..._every_body_is_signed_by_the_pools_owner       .  .   .    .    .    Y    .    .   Y
    tests/..._the_provider_does_the_signing                 .  .   .    .    .    Y    .    .   Y
    tests/..._a_safety_pause_fails_open                     .  .   .    .    .    Y    Y    .   Y
    tests/..._no_new_write_bypasses_the_door                .  .   .    .    .    .    .    Y   Y
    scripts/write_path_denominator.py                       .  .   .    .    .    .    .    Y   Y
    scripts/suppression_on_every_write_path.py              .  .   .    .    .    .    .    Y   Y

Three things fall straight out of that table and none of them is rhetorical.

**Both masters hold exactly ONE of the fourteen**, and it is the one file that
predates all this work. Every other proof of every other criterion is
unmerged.

**`integ/canary-nine-2026-10-15` is the only ref where the fourteen coexist.**
Before it, the maximum over any single ref was six (glm-review).

**`task-glm-b-2026-10-14` holds NO proof of any of the nine.** It is the eighth
ref the 0160 audit counted, and it is deliberately NOT merged here — see §6.

### Ancestry, measured

    git merge-base --octopus <the five>                   2bf7b8a57
    git merge-base --is-ancestor 2bf7b8a57 b1f290c84  ->  YES

    branch                              tip         contains b1f290c84?  ahead  behind
    task-suppression-2026-10-14         9bd8648f5          NO             15      2
    task-glm-b-2026-10-14               9e7c7ec72          NO              6      2
    task-glm-c-2026-10-14               9949dc205          NO             11      2
    task-glm-review-2026-10-14          fc78e9b4e          NO             15      2
    task-pilotcaps-enforcer-2026-10-14  7a2890022          NO              8      2
    task-glm-halt-failopen-2026-10-15   b77cd4b20          NO              8      2

The two commits each branch is "behind" are `5fc5784fc` (four task files) and
`b1f290c84` (an empty push probe). Neither touches `src/` or `tests/`, which is
why no lane's measurements were invalidated by not having them — but it is the
reason none of the six contains `origin/master`, and that was the 0160 finding.

### Every branch tip had MOVED since 0160 audited it

This matters more than it looks, because 0160's verdicts are keyed to SHAs that
are no longer any branch's tip:

    criterion    0160 measured   tip now      delta
    1, 2         fa964f8cc       9bd8648f5    +1  (0100: the three bounces applied)
    4            32cb420f7       9949dc205    +3  (incl. 0180: the connection-note pin)
    4, 7         93162471d       fc78e9b4e    +2  (incl. 0067: ceiling on the COMPOSED body)
    5            22c7ace62       7a2890022    +1  (0160 itself)
    9 (part)     b77cd4b20       b77cd4b20    unchanged

**And one of them moved WHILE THIS TASK WAS RUNNING.** `task-glm-c-2026-10-14`
was `97fec582d` when the table above was first enumerated at 20:27Z and
`9949dc205` when M5 merged it at 20:34Z — glm-c committed TASK 0180 at
22:30:56+02:00, between the two. The merge took the newer tip. That is recorded
rather than hidden, and it is why every row below names the SECOND PARENT of a
merge commit and not a branch name: **a branch name is not a measurement.**

    merge  commit      second parent  what it carried
    M1     759659447   7a2890022      criterion 5's B5 instrument, CI, suitelock
    M2     dd154e381   b77cd4b20      criterion 9's part: bison.pause needs no GateToken
    M3     5bd62b707   9bd8648f5      criteria 1 and 2: src/suppression.py and its tests
    M4     511dee5ee   fc78e9b4e      criterion 4's register test, criterion 7
    M5     aa4a28d5f   9949dc205      criterion 4's trims. SECOND of the colliding pair
    M5a    13e2e825d   (not a merge)  the debt M5 incurred, paid

---

## 2. THE MERGE ORDER, AND WHY

Off `origin/master` (`b1f290c84`), `--no-ff` every time so each step is
attributable and revertible on its own.

1. **pilotcaps-enforcer first.** This lane's own branch, and `halt-failopen`
   descends from five of its commits (`1805ca7b8..a942a4b4a`), so putting it
   first makes step 2 nearly free.
2. **halt-failopen second**, for that reason. Its only new content over M1 is
   `1ea8105bf` and `b77cd4b20`.
3. **suppression third.** `src/suppression.py` exists on no other ref, so it is
   the easy case the task predicted — additive, with the only risk in
   `src/providerwrites.py` and `src/bisonfactory.py`, which M1/M2 had already
   changed.
4. **glm-review fourth**, so that
5. **glm-c lands FIFTH and therefore SECOND of the colliding pair**, and owes
   the three `expectedFailure` removals. Putting the debt at the end makes it
   one visible commit instead of a detail buried in the middle.

**Zero textual conflicts across all five.** `src/cadence.py` auto-merged
between glm-c and glm-review; `src/bisonfactory.py` took changes from three
branches; `src/providerwrites.py` from three;
`tests/test_a_safety_pause_fails_open.py` existed on two refs with an
**identical blob** (`e35c8d266744edd8fa0223705ca4eabe691439df`), so git had
nothing to resolve.

**A clean textual merge is not a clean semantic merge, and §3 and §4 are what
that sentence costs.** The whole value of this task is that both collisions
below are invisible to `git merge`.

---

## 3. COLLISION ONE — criterion 4, predicted, reproduced, paid

0160 predicted this by substituting `32cb420f7`'s blobs into a `93162471d`
tree. Here it is in a real integrated tree at the current tips.

    at M4 (511dee5ee)   expected_failures    = the 3 names
                        unexpected_successes = {}
    at M5 (aa4a28d5f)   expected_failures    = {}
                        unexpected_successes = the 3 names

        test_angle_shift_champion_is_over_the_em4_ceiling
        test_angle_shift_economic_buyer_is_over_the_em4_ceiling
        test_rung3_economic_buyer_is_over_the_em3_ceiling

**Three appear, three disappear. The scalar does not move.** A count-based gate
passes this merge and ships a suite that fails for a reason nobody can
attribute. This is the second time in two days that a 231-vs-231 shape has been
the thing that mattered.

### Paid in M5a (`13e2e825d`), in the step that merged the trims

The markers were removed and the file's docstring — which said three templates
are over ceiling TODAY — was corrected in the same commit, because the change
orphaned it.

Verified POSITIVELY rather than by absence:

- all three **run and report `ok` by name** in the verbose log, not merely
  absent from a failure list
- the module set is **29 ran / 0 failures / 0 errors / 0 unexpected / 0
  expected-failures / 0 skipped**
- **teeth**: +40 words into `angle_shift_champion`'s body in `src/cadence.py`
  turns THAT named test red for the intended reason — `AssertionError: 112 not
  less than or equal to 90` out of its own `assertLessEqual`, not a different
  guard firing first. Restored; `git hash-object src/cadence.py` equals the
  HEAD blob `d37f9638c1fc7a7aeb43c6002703323d975e671d`.

**No criterion was weakened.** The trims were approved and already merged; this
removed bookkeeping the merge made stale, and the assertions remain and go red
if any of the three bodies grows back.

---

## 4. COLLISION TWO — criterion 5, NOT predicted, and it is the better finding

Nobody flagged this. It was found because the task required carrying name-sets
through every merge step, and the pinned key-set is a name-set.

    scripts/write_path_denominator.py on pilotcaps own tree 7a2890022 : 26 of 58 BYPASS
    scripts/write_path_denominator.py on the integrated tree          : 26 of 58 BYPASS

**Both 26. The key-set moved by one name in each direction.**

    GONE   scripts/batch_linkedin_push.py::main::heyreach.add_leads_to_list
    ADDED  scripts/batch_linkedin_push.py::stage_rows_to_list::heyreach.add_leads_to_list

`tests/test_no_new_write_bypasses_the_door` goes RED on the integrated tree and
green on pilotcaps' own tree, in both of its two directions:

    test_no_bypassing_call_site_is_new               FAIL  (the ADDED name)
    test_the_baseline_has_not_fallen_behind_the_code  FAIL  (the GONE name)

Those two names are the **entire** integration-only delta for criterion 5. The
other eight failures (`test_p1`..`test_p8`) are identical on both trees: the
eight write-path proposals are deliberately RED until the operator orders the
fix, which is 0160's own design.

### The ADDED name is not a new ungated write. It is a FIX the analyzer cannot see — and that makes criterion 5's number wrong by one, pessimistically.

glm-c's TASK 0170 took the raw 100-row `heyreach.add_leads_to_list` call out of
`main()` and routed it through `liststaging.stage_lead`, one lead at a time.
Traced, not argued:

    scripts/batch_linkedin_push.py:444   heyreach.add_leads_to_list  (a lambda,
                                         handed to liststaging.stage_lead)
    src/liststaging.py:323               providerwrites.perform(...)
    src/liststaging.py:329                 gate=providerwrites.grant(...)

So the write goes **through the door**, with an execution grant, the ledgers and
the killswitch. The analyzer still calls it a BYPASS because its rule is
"a mutating call and a `perform(...)` in the SAME function" — and here the call
is a callback in one module while `perform` is in another.

0160 stated that rule **over-credits**, which makes 26 a floor. This is the
first measured instance of it **under-crediting**: a gated call reads as a
bypass. So the rule errs in BOTH directions, and 26 is neither a floor nor a
ceiling — it is 26 with one provable false positive.

    criterion 5 on the integrated tree, by the analyzer      26 of 58
    criterion 5 on the integrated tree, corrected by tracing 25 of 58

**Criterion 5 is still NOT MET either way.** It asks for literal zero. 25 and 26
are both not zero, and the correction changes the arithmetic, not the verdict.

### What is NOT done here, deliberately

**The baseline is NOT regenerated.** `scripts/regen_write_bypass_baseline.py`
exists and the failure message names it, and running it would turn both tests
green in one command. It was not run, and the reason is not timidity:

- the three `expectedFailure` removals in §3 cannot hide a defect — the
  assertion stays and goes red if the body grows back
- regenerating a bypass baseline **can** hide one. Its whole value is that a
  human looked at the delta and said whether a key that moved is a relocation
  or a new ungated write. That judgment is the lane's and the operator's, not
  this task's.

So the evidence is supplied and the decision is not taken. **Whoever lands
glm-c and pilotcaps together for real owes the regeneration, in the same
commit, naming this relocation** — exactly parallel to the three markers, and
discovered the same way.

### The same relocation in criterion 1's instrument, where it is CORRECT

    scripts/suppression_on_every_write_path.py, own tree  : 58 / 5 / 32 / 21
    scripts/suppression_on_every_write_path.py, integrated: 58 / 5 / 32 / 21

Identical headers; the same single key moved. Here the classification is right,
and that is not luck — it is a different question with a different answer, and
it was resolved by measurement:

    providerwrites.LINKEDIN_ADD_LEAD_TO_LIST == "heyreach.add_lead_to_list"
      in SUPPORTED            : True
      in PROSPECT_FACING      : FALSE   -> executionguard.revalidate does NOT
                                           run, and that is the facing-only
                                           suppression consult
      its CONDITIONAL         : _list_is_unbound_right_now
                                "True only for a list the provider says is
                                 attached to NO campaign" - a BINDING check,
                                 not a suppression check

**So the relocated site passes the door and still carries no suppression
consult.** Criterion 5 counts it wrongly and criterion 1 counts it rightly, for
the same site, at the same moment. That is the clearest available argument that
"through the door" and "suppression consulted" are two questions — which is the
operator's 2026-10-02 attribution/suppression rule showing up in the write path.

---

## 5. THE NINE, ON `13e2e825d`, IN `resonate-trees/wt-integ-nine-2026-10-15`

Every row was re-measured at the moment it was taken, in this one tree, and
every row names the tree it was compared against. "own tree" below means a
detached checkout at the exact SHA this branch merged — a frozen reference no
track owns, per the standing rule.

    CR in requirements.txt, this tree : 0  -> LF
    the five own-trees                : 0  -> LF   (so the comparison is clean)

**Line-ending note, because it is load-bearing here.** This tree and all five
own-trees are **LF**. The five hand-made lane worktrees are **CRLF**. Every
per-criterion number below is an LF-vs-LF comparison, so no name-set in this
file is compared across the boundary. Four of 0160's five trees (T2-T5) were
also LF; its T1 was CRLF, and criterion 5's two instruments parse with `ast`,
which line endings do not change.

| # | criterion | verdict HERE | vs its own tree |
|---|---|---|---|
| 1 | a suppressed address cannot reach the transport by any path | **MET-WITH-CAVEAT** | unchanged |
| 2 | a removal request writes a suppression row, demonstrated | **MET** | unchanged |
| 3 | li1 renders a real connection note, RED on empty | **NOT MET** | unchanged |
| 4 | every template passes the ceiling and the floor, RED on escape | **MET** | **STRONGER** — 29 tests here vs 9 (glm-c) and 23-with-3-pinned (glm-review) |
| 5 | zero write paths bypass the gate, against a real denominator | **NOT MET** — 25 of 58 corrected, 26 by the analyzer | **2 new failing names** (§4) |
| 6 | mailbox health, answered from the estate export | **MET** | tree-independent |
| 7 | one owner across the pool, bodies signed by that owner | **NOT MET** | unchanged |
| 8 | the review file is approved by the owner | **MET-WITH-CAVEAT** | tree-independent |
| 9 | a kill switch the owner can operate alone, named and tested | **NOT MET** | unchanged |

**Four NOT MET. CANARY-01 does not activate on this tree either.** The count is
the same as 0160's and that is the point: the four were real work, not an
artefact of the proofs being scattered.

### 1 — a suppressed address cannot reach the transport by any path

    cd resonate-trees/wt-integ-nine-2026-10-15
    py -3 -B -m unittest tests.test_a_suppressed_address_cannot_reach_a_provider
    py -3 -B scripts/suppression_on_every_write_path.py .

    the module set (6 suppression modules, 121 tests) : 7 failures, 0 errors
    the 7 names are IDENTICAL, both directions, to the same set in
      suppression's own tree at 9bd8648f5 - so they are inherited, not caused

    all 7 are in tests.test_a_provider_bounce_reaches_the_record, which
    suppression/0090 committed BORN RED. 0 failures in the module that proves
    this criterion.

    the enumeration : 58 write paths / 5 consult in-function / 32 through the
                      door / 21 NO SUPPRESSION CONSULT  (a floor, not a ceiling)

**MET-WITH-CAVEAT, and the caveat is the same 21.** Verdict unchanged by
integration. The one key that moved (§4) is still correctly counted as
no-consult, now proven by reading the verb's `PROSPECT_FACING` flag and its
`CONDITIONAL` rather than by inspection.

*Smallest thing that would make it MET: a suppression consult standing on the
21, or an argument per path for why each cannot carry a prospect address.
Owner: the suppression lane. Not this task's.*

### 2 — a removal request writes a suppression row, demonstrated

    py -3 -B -m unittest tests.test_a_suppressed_address_cannot_reach_a_provider
    (the write classes)

**MET.** Name-set identical to suppression's own tree, both directions. The
write is demonstrated, not assumed, and `src/suppression.py` — which exists on
exactly one other ref in the whole repository — is present and consulted here.

### 3 — li1 renders a real connection note, RED on empty

    py -3 -B -m unittest tests.test_linkedin_note \
        tests.test_a_linkedin_message_is_not_a_connection_request \
        tests.test_the_empty_connection_note_is_an_operator_decision

    46 ran, 1 failure, identical both directions to glm-c's own tree 9949dc205

    test_an_em_dash_is_normalised_rather_than_spending_an_attempt
      (tests.test_linkedin_note.TestTheNoteGoesThroughTheSameDoorTheEmailDoes)

**NOT MET**, for 0160's reason, unchanged. The one failure is the unattributed
one 0160 reported in T3 and declined to charge to anything; it reproduces here
and is still unattributed.

New since 0160: glm-c's `9949dc205` added
`tests/test_the_empty_connection_note_is_an_operator_decision.py`, which **pins
the empty note as an operator decision rather than fixing it**. It passes. A
test that pins a decision is not a test that renders a note, so the criterion's
verdict does not move.

*Smallest thing: the operator's answer to 0160's open item 5 (is the note-less
connection request permission global or per-campaign). LinkedIn is out of this
canary by `DECISION-canary-channels-2026-10-15.md`, so this blocks nothing
today and the next canary inherits it. Owner: the operator.*

### 4 — every template passes the ceiling and the floor, RED on escape

    py -3 -B -m unittest tests.test_no_template_escapes_the_word_contract \
        tests.test_every_template_is_inside_the_word_contract \
        tests.test_the_word_ceiling_is_enforced_on_the_composed_body

    integrated 13e2e825d : 29 ran, 0 failures, 0 errors, 0 unexpected,
                           0 expected-failures, 0 skipped
    glm-c      9949dc205 :  9 ran - the other two modules DO NOT EXIST there
    glm-review fc78e9b4e : 23 ran, 3 expectedFailures, 1 module missing

**MET, and this is the row worth reading twice.** It is MET here on the union of
three instruments; it was MET in glm-c's tree on **one third** of them. A
criterion asked of nine tests and a criterion asked of twenty-nine are not the
same criterion, and only an integrated tree can ask the second.

Both of glm-review's extra commits since `93162471d` are in that 29:
`06bd434de` moved the ceiling onto the COMPOSED body and `fc78e9b4e` added
`rung3_champion` to the trim set. Both green here.

**Standing caveat, undiminished: this is the WRITER CONTRACT's ceiling, and the
operator's open item on the opt-out footer is not settled.** 0160 measured the
ten approved bodies at 81-89 words without the 11-word opt-out sentence and
**92-100 with it**, against a hard ceiling of 90. The test suite above counts
the shape the contract declares. **If the ceiling applies to what ships, all
ten are over it**, and no test here would say so. Reported as both numbers,
measured against the wording as written, per this task's instruction. Owner:
the operator (0160 item 2).

### 5 — the count of write paths that bypass the gate is zero

    py -3 -B scripts/write_path_denominator.py .
    py -3 -B -m unittest tests.test_no_new_write_bypasses_the_door \
        tests.test_the_eight_write_path_proposals_are_unapplied \
        tests.test_a_non_facing_write_is_not_anonymous

    58 write paths / 32 through the door / 26 BYPASS   (analyzer)
                                           25 BYPASS   (corrected, §4)
    31 ran, 10 failures. 8 are the born-red P1..P8, identical on both trees.
    2 are integration-only and are the whole §4 finding.

**NOT MET.** The denominator is derived, not hand-kept: `bison` contributes 13
mutating public functions and `heyreach` 12, parsed with `ast`, and the same 25
names appear on both trees. Stated as a fraction of that denominator and not of
a list anybody maintains, which is the defect the catalogue's family 2
documents.

**On criterion 5's own wording, which is in front of the operator.** It asks for
literal zero. Literal zero is reachable only by gating the brakes —
`bison.pause_campaign` and `bison.stop_lead` are among the 25, and `b77cd4b20`
had to make `bison.pause` need NO GateToken precisely so a halt cannot fail
closed. A gate on the brake is a worse system than an ungated brake. 0160's
recommended rewording — "zero ungated writes that can PERFORM a prospect-facing
action", 2 of 58 today — is item 6 in front of him. **Measured against the
wording as written: NOT MET, 25 of 58. Both numbers reported; neither criterion
weakened.**

*Smallest thing: his order on P1 and P2, the two `bison.resume_campaign` sites.
Those two close the prospect-facing email half of this criterion and the "by any
path" caveat on criterion 1 at the same time — they are the same two sites.
Owner: the operator (0160 item 4).*

### 6 — mailbox health, answered from the estate export

    sha256sum resonate-ops/canary/sender-estate-export-2026-10-15.csv
    sha256sum resonate-ops/canary/sender-estate-export-2026-10-15b.csv
    # then a csv.DictReader tally

    (a) 46860f5d0732e2324e160379ff62b3aea1aafdb59257685fdea35e3ece3506a8  reproduces
    (b) 07f4c67144d3566356136ac9d3aa7f86d4be5d43ac3bf8cf4df3d3c65b881cca  reproduces

    export (b), 181 rows: Connected 179, Not connected 2
    Emails Sent 175,237   Bounces 1,771 (1.01%)   Replies 1,771 (1.01%)   Opens 0
    rows where Replies == Bounces: 16 of 181

**MET.** Re-measured at 20:46Z, independently of 0160's arithmetic, and it
reproduces to the digit. Tree-independent: the authority is a hashed export in
`resonate-ops`, so integration cannot move it. 0160's two corrections both
stand — two mailboxes read Not connected against the criterion's text, and the
equal Bounces/Replies totals are a coincidence rather than a duplicated column.

### 7 — one owner across the pool, every body signed with that owner's name

    py -3 -B -m unittest tests.test_every_body_is_signed_by_the_pools_owner \
        tests.test_the_provider_does_the_signing

    32 ran, 0 failures, 7 expectedFailures, 1 skipped
    name-sets IDENTICAL, both directions, to glm-review's own tree fc78e9b4e

**NOT MET**, unchanged. The mechanism is green and the **fact it asserts is
red**: seven pinned expected failures, and `TheLiveRead` SKIPPED because the
live read is NOT APPROVED as of today. A skipped test is not a passing one, and
seven expected failures are seven defects with a receipt.

*Smallest thing, and it is one read: `GET /sender-emails`, fully walked. It
returns id + address + signature and settles the owner question, the allowlist
currency gate and the ten `sender_email_ids` in one call. Owner: the operator
(0160 item 1).*

### 8 — the review file is approved by the owner

    sha256sum resonate-ops/canary/APPROVAL-SHEET-2026-10-15.md
    # then recompute all 48 per-row digests from the sheet's own fenced bodies

    file sha256 eb6b93f516e457aef7427c34476ea4eeaae298669f9b6728f85ef710133244f4
                identical to DECISION-canary-approval-2026-10-15.md
    claimed digest pairs 24 | ```text fences 24
    composed digests reproduced 24/24
    bare     digests reproduced 24/24
    mismatches []                      TOTAL 48/48

**MET-WITH-CAVEAT.** Re-derived at 20:45Z from the documented construction
(composed = the bytes between a text fence and its close; bare = the first
three paragraphs joined by a blank line), written fresh rather than by rerunning
0160's script, so the reproduction is independent. The approval's own staleness
test passes.

Caveats are the approval's own and are load-bearing: it was a **bulk** approval,
it approves **words and not sends**, and — the one that bears hardest — an
approval in this system **binds the mailbox and the signature**, which is why 0
of 3,005 stored approvals are still valid. These 23 approvals name **no
mailbox**. The mailbox binding is still owed, and it is owed on exactly the pool
criterion 7 cannot classify. **Criterion 8 does not carry the weight that
criterion 7 failing takes off it.**

### 9 — a kill switch the owner can operate alone is named and tested

    py -3 -B -m unittest tests.test_killswitch \
        tests.test_lead_writes_respect_the_killswitch \
        tests.test_a_safety_pause_fails_open

    33 ran, 0 failures, 0 errors, 0 skipped
    name-sets IDENTICAL, both directions, to halt-failopen's own tree b77cd4b20

**NOT MET, and 33 green tests do not change it.** Re-measured on the integrated
tree:

    src/killswitch.py public surface: global_state, workspace_state,
      campaign_state, account_state, contact_state, step_state, state,
      require, main - and NO SETTER. Its own docstring: "This module reads."
    scripts matching halt|kill|panic|stop : bounce_stop_7day.py,
      hard_stop_check.py - both CHECKS, neither a switch.

This is the distinction CLAUDE.md already carries: the killswitch refuses to
START an action and cannot END a campaign already running. **The owner's only
working kill switch is pausing by hand in the EmailBison UI** — real, proven on
487/489/493 on 2026-09-28, and untestable here by construction.

What integration adds is that `b77cd4b20` is now in a tree with everything
else, so its property can be asserted alongside the rest:
`tests.test_a_safety_pause_fails_open` is green here, meaning `bison.pause`
needs no GateToken and a halt therefore cannot fail closed for want of one.
That is a necessary condition for an operator-operable switch; it is not one.

*Smallest thing: a one-verb script the owner can run that pauses a named
campaign through `providerwrites.perform` with no GateToken required, plus the
`EMAIL_ADD_LEAD` routing 0160 named. Both are changes under `src/`, both owe a
full reference, and the canary's whole point is to be small. Owner: the operator
(0160 item 3).*

---

## 6. WHAT IS NOT IN THIS TREE, AND WHY

**`task-glm-b-2026-10-14` (`9e7c7ec72`) is NOT merged.** It is the eighth ref
0160 counted and §1's table shows it holds **no proof of any of the nine** —
`tests/test_linkedin_note.py` is the only listed artifact it carries and that
file is on `origin/master` too.

What it does carry is a **new lint rule** (`src/lint.py` +9,
`company_slot_domain`) and a **new refusal in `stage_s7_copy.render`** for a
domain-shaped company name. Both are plausibly good and both are confounds in an
instrument whose job is to measure the nine: a new refusal in the renderer that
criterion 4 drives is precisely the kind of change that would make a criterion-4
verdict here mean something other than what it says.

Measured, so this is not an argument from the kind of file: glm-b's
`scripts/stage_s7_copy.py` delta touches `render()` at line ~276 and glm-c's
touches `BODY_1` at line ~104, so **they do not even conflict** — the exclusion
is about attribution, not about difficulty. Merging it is one clean step for
whoever wants it.

**Nothing is merged or pushed to master.** `origin/master` is `b1f290c84`,
untouched. The local `refs/heads/master` divergence at `5fc5784fc` is the
operator's and was not approached.

---

## 7. THE FULL SUITE REFERENCE

0160's branch owed one and did not have it. This section is where this branch's
reference goes.

The suite lock was held by `task-suppression-2026-10-14` (pid 83540, started
22:00:18+02:00, `--timeout 5400`) throughout the measurement phase above, and
was still alive when this section was first written — verified through python's
`subprocess` with a positive self-check on the reader, because `tasklist` typed
in the bash tool returns zero rows for every query and a live PID would read as
GONE. **The lock was neither taken nor released.** `scripts/run_suite.py` queues
FIFO and waits.

**The reference is a named list and is compared by SET, never by count, and it
is valid only in `resonate-trees/wt-integ-nine-2026-10-15` (LF) at
`13e2e825d`.** See §7a, appended when the run finished.

---

## 8. DECISIONS TAKEN WITHOUT WAKING HIM

1. **Built the integration branch in a NEW worktree rather than in a lane
   tree.** `resonate-trees/wt-integ-nine-2026-10-15`, LF. A lane tree is
   forbidden; this lane's own tree is CRLF with an index recorded under
   `autocrlf=true`, so merging in it with `autocrlf=false` would have written
   mixed endings into a tree whose `git status` cannot detect it.
   `wt-pilotcaps-2026-10-14` was left on its own branch, clean, and never moved.
2. **Merged the branch TIPS, not 0160's audited SHAs.** The audited SHAs are
   nobody's tip any more and four of five branches had advanced. An instrument
   built on superseded commits would measure a state no lane is in. Both SHAs
   are tabulated in §1 so either reading is available.
3. **Removed the three `expectedFailure` markers** (§3) — sanctioned by this
   task and by the file's own docstring, and it cannot hide a defect.
4. **Did NOT regenerate the write-bypass baseline** (§4) — not sanctioned, and
   it CAN hide one. Evidence supplied, decision left.
5. **Did not merge `task-glm-b-2026-10-14`** (§6).
6. **Created five frozen detached reference worktrees** at the exact merged
   SHAs, so every "unchanged / changed" claim is an LF-vs-LF name-set diff
   rather than an appeal to a lane file. Reproducible exactly with
   `git worktree add --detach <path> <SHA>`. They are left in place, because a
   reference is only valid in the tree it was measured in.
7. **Regenerated `resonate-ops/pilotcaps-sheet-verify-2026-10-15/verify_sheet_0110.json`**
   by running TASK 0110's own script. Same byte length; the script is
   deterministic over an unchanged sheet. Recorded because it is another task's
   artifact and because a tool reporting success is not evidence.
