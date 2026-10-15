# CANARY-01 — the nine exit criteria, audited as a set

TASK 0160 (pilotcaps), 2026-10-15. Entirely offline: no provider, Apify, Slack
or network call was made, nothing was attached, no cap or gate was changed, and
no decision file was edited.

`resonate-ops/CANARY-01.md` says activation happens "only when all of these are
true, **each with the command that proves it**." Nobody had audited the nine as
a set since they were written on 2026-10-14. Several were answered by lanes in
passing, in different files, on different SHAs, which is not the same as being
met. Every verdict below was re-measured at the moment it was taken.

**No prospect name, prospect domain or sender address appears in this file.**
The ten are named by their approval-sheet row number; mailboxes are named by
provider id and by `px-` hash, both of which already appear in tracked
documents. The cohort itself is named in `resonate-ops/`, outside this
repository, where the rest of the canary artifacts live.

---

## 0. THE VERDICTS

| # | criterion | verdict |
|---|---|---|
| 1 | a suppressed address cannot reach the transport by any path | **MET-WITH-CAVEAT** — proven on the paths that have a gate; 21 of 58 write paths have no suppression consult, 2 of them prospect-facing on email |
| 2 | a removal request writes a suppression row, demonstrated | **MET** |
| 3 | li1 renders a real connection note, RED on empty | **NOT MET** — and it contradicts a standing operator decision |
| 4 | every template passes the ceiling and the floor, RED on escape | **MET** on `32cb420f7`, **NOT MET** on `93162471d`, and merging the two turns the suite red |
| 5 | zero write paths bypass the gate, against a real denominator | **NOT MET** — 26 of 58 |
| 6 | mailbox health, answered from the estate export | **MET**, with two corrections to its own text |
| 7 | one owner across the attached pool, bodies signed by that owner | **NOT MET** — the mechanism is green, the fact it asserts is red |
| 8 | the review file is approved by the owner | **MET-WITH-CAVEAT** — 48/48 row digests reproduce; it was a bulk approval binding no mailbox |
| 9 | a kill switch the owner can operate alone, named and tested | **NOT MET** — the module is a reader with no setter |

**Four of the nine are NOT MET and one more is MET only on a branch that
collides with another branch. CANARY-01 does not activate today.**

---

## 0a. THE FINDING THAT OUTRANKS THE NINE: NO TREE HOLDS MORE THAN ONE PROOF

The candidate proofs live on five branches whose only common ancestor is
`2bf7b8a57`, and **not one of them contains `origin/master`**.

    origin/master                          b1f290c84   the authority
    refs/heads/master (main checkout)      5fc5784fc   moved 00:13, unpushed
    common ancestor of all five lanes      2bf7b8a57

    criterion   proof lives on                            contains b1f290c84?
    1, 2        task-suppression-2026-10-14  fa964f8cc    NO
    4           task-glm-c-2026-10-14        32cb420f7    NO
    4, 7        task-glm-review-2026-10-14   93162471d    NO
    5           task-pilotcaps-enforcer      22c7ace62    NO
    9 (part)    task-glm-halt-failopen       b77cd4b20    NO

`src/suppression.py` — the module criteria 1 and 2 rest on — exists on
`task-suppression-2026-10-14` and **on no other ref**, checked by
`git cat-file -e <ref>:src/suppression.py` across eight refs including both
masters.

So "all nine true at once" has never been measured anywhere and cannot be until
the lanes are integrated. Each verdict below is true in the tree it names and
nowhere else. This is not pedantry: criterion 4 is MET in one tree and NOT MET
in another, and §4 shows by measurement that putting those two trees together
turns the suite red.

---

## 0b. THE TREES, AND THEIR LINE ENDINGS

Standing rules: name the SHA of every measurement, and say which tree.

| tag | path | SHA | CR in `requirements.txt` |
|---|---|---|---|
| T1 | `wt-pilotcaps-2026-10-14` (branch `task-pilotcaps-enforcer-2026-10-14`) | `22c7ace62` | 15 — **CRLF** |
| T2 | `resonate-trees/audit0160-suppression` (detached) | `fa964f8cc` | 0 — LF |
| T3 | `resonate-trees/audit0160-glmc` (detached) | `32cb420f7` | 0 — LF |
| T4 | `resonate-trees/audit0160-glmreview` (detached) | `93162471d` | 0 — LF |
| T5 | `resonate-trees/audit0160-haltopen` (detached) | `b77cd4b20` | 0 — LF |

T2-T5 are detached checkouts at named SHAs that no track owns, created for this
audit and removed at the end of it. They are reproducible exactly:

    git worktree add --detach <path> <SHA>

**T1 is CRLF and T2-T5 are LF**, because this shell runs with
`GIT_CONFIG_SYSTEM` pointing at an empty file, so `core.autocrlf` reads `false`
and a worktree created here comes out LF — the same reason the `webapp` tree is
LF while the five hand-made lane trees are CRLF. Nothing below is a name-set
comparison against a reference measured in another tree, so the difference does
not invalidate any verdict; it is recorded because a future reader comparing
one of these numbers against a CRLF reference has to account for it first.

`task-suppression-2026-10-14` was still moving while this ran — `fa964f8cc`
local against `617c2a1ac` at origin, and `suppression/0100` was applying the
three bounced addresses at the time. T2 is detached at `fa964f8cc` so the
branch moving cannot change what was measured; a later tip is a later
measurement and not this one.

---

## 1. A suppressed address cannot reach the transport by any path

### MET-WITH-CAVEAT. The gate is load-bearing. "By any path" is false.

**The command, in T2 (`fa964f8cc`):**

    cd resonate-trees/audit0160-suppression
    py -3 -B -m unittest tests.test_a_suppressed_address_cannot_reach_a_provider

**Result: Ran 37 tests, OK.** All 37 green, including the module's own two
in-file mutation tests and both positive controls.

### The RED-on-removal half, performed independently rather than taken on trust

The module carries its own mutations. The brief says re-run it, so the check
was also made from outside, against the source:

    # src/suppression.py, after `detail` is bound at line 275:
    sed -i '276i\    return _verdict([], detail, rec, contact, at)  # MUTATION-0160' src/suppression.py

`decide` then always ALLOWs while still recording the consult, which is exactly
"the suppression check removed" and not "the module broken".

    Ran 37 tests — FAILED (failures=13), zero errors

The four names that answer the criterion went red:

    RED  NoPathReachesTheTransport.test_a_suppressed_address_does_not_reach_the_transport
    RED  NoPathReachesTheTransport.test_the_resume_verb_is_covered_too
    RED  TheDoorConsultsSuppression.test_a_suppressed_contact_is_refused_at_the_suppression_gate
    RED  NobodySuppressedIsEnrolledAtTheProvider.test_one_suppressed_contact_stops_the_whole_lead_write

and both positive controls stayed GREEN —
`NoPathReachesTheTransport.test_the_positive_control_the_transport_is_reachable`
and `NobodySuppressedIsEnrolledAtTheProvider.test_the_positive_control_two_clean_leads_are_created`
— so the red is attributable to the removed check and not to a broken fixture.

Restored and re-verified: `md5 32de76ef900236317b0a98d53082dd27` (identical to
before), `git status --short` empty, `__pycache__` wiped, module green again
(Ran 37, OK).

**The first attempt at that mutation is recorded because it was not a proof.**
Inserting the same line one line earlier, before `detail` is bound, produced
**19 ERRORs** rather than failures — a `NameError`, so the module went red for
a reason that had nothing to do with suppression. A red test is not proof by
itself; it has to fail for the intended reason.

### Why "by any path" does not hold, measured

`scripts/suppression_on_every_write_path.py` (new, this task) asks the
criterion-5 denominator a different question: of the provider write paths that
exist, how many have a suppression consult standing on them.

    py -3 -B scripts/suppression_on_every_write_path.py resonate-trees/audit0160-suppression

    provider write paths                  : 58
    a suppression consult in the function : 5
    through the door, consult per verb    : 32
    NO SUPPRESSION CONSULT ON THIS PATH   : 21  (a floor, not a ceiling)

**The door has no blanket suppression check**, and that is the structural point.
There are three consult sites in `src/`, each covering a different slice:

    src/executionguard.py:991   revalidate()        -> suppression.decide SCOPE_SEND
                                reached by `perform` only for a facing=True verb
    src/providerwrites.py:1429  _resume_revalidates_suppression()
                                CONDITIONAL[bison.resume] only, because that
                                verb is facing=False and so skips revalidate
    src/bisonfactory.py:1998    _refuse_suppressed_leads()
                                called from _ensure_leads() at :2497, so the
                                lead writes carry a consult even though they
                                bypass `perform` entirely

So "passes the door" is not the same as "is consulted" — it depends on the
verb's `facing` flag. The 21 with no consult at all break down as:

| what | sites | does it matter for criterion 1 |
|---|---|---|
| `bison.resume_campaign` — `scripts/batch_activate.py:144`, `scripts/resume_487.py:269` | 2 | **YES. Prospect-facing, on email.** A resume restarts a paused sequence in front of everybody in the campaign, and ten of our campaigns hold 1,555 rows in `sending_paused`. Neither script imports `killswitch`, `providerwrites` or `suppression` — verified by grep over both files. |
| `heyreach.*` — `add_leads_to_list`, `create_list`, `create_campaign`, `set_sequence`, `activate_campaign` across 6 scripts | 11 | LinkedIn, deferred from this canary by `DECISION-canary-channels-2026-10-15.md`. Inherited by the next one. |
| `bison.stop_lead` ×2, `bison.pause_campaign` ×1 | 3 | **NO, and they must stay that way.** A safety write has to fail OPEN; gating a stop or a pause makes it refusable, which is strictly worse than leaving it ungated. |
| `bison.set_limits`, `bison.set_schedule`, `bison.attach_senders` | 3 | NO — none carries a lead, so none can put an address in front of the transport. |
| remainder (`_ensure_leads` helpers already counted as consulted) | 2 | NO |

The classifier uses the same enclosing-function rule as the denominator, which
over-credits in the same direction, so **21 is a floor on the unconsulted paths
and not a ceiling**.

**Independent convergence.** `tests/test_the_eight_write_path_proposals_are_unapplied`
(T1) ranks `scripts/batch_activate.py:144` as proposal **P1, rank 0, the only
prospect-facing one**, written from a different measurement on a different day.
Two instruments arriving at the same site is the strongest thing the audit
found.

### The contested question: does `leadobserve.confirm_email_touches` touch this?

**No. It touches bounce recording and a different gate, and the call graph says
so rather than the names.**

`confirm_email_touches` has exactly **one** caller outside `tests/`:

    src/leadobserve.py:579  def confirm_email_touches(campaign_id, recs=None, live=False)
    src/leadobserve.py:699      out = confirm_email_touches(a.campaign, live=a.live)

and line 699 is inside `main(argv=None)` (declared at :680), behind
`--confirm` and `--live`. No scheduled host, loop or orchestrator reaches it.
`suppression/0090`'s "zero production callers" is confirmed.

Now follow the suppression verdict down instead of guessing from the word
"touch". `suppression.decide` delegates every permanent refusal to
`eligibility.must_not_contact`, which returns exactly six slots:

    _operator_excluded   _suppressed   _client_own_domain
    _record_state        _replied      _paused

**Not one of them reads a bounce event.** So whether `EMAIL_BOUNCED` is ever
written changes no suppression verdict, and the dead producer cannot make a
*suppressed* address reachable. Criterion 1 is a closure property of the
suppression gate and it is untouched.

What the dead producer does break is a **different** gate.
`channels._bounced(rec, contact)` walks `rec["events"]` for
`entry["type"] == events.EMAIL_BOUNCED`, keyed to the contact. Its own docstring
records that a bounce "was read by no gate at all" until 2026-09-13. With no
production writer for that event, `channels.email_verdict` returns sendable for
addresses the provider has already rejected — which is what `suppression/0070`
measured. That is criterion-1-adjacent and it is real, but it is bounce
recording, and it is `suppression/0100`'s work, in flight at the time of this
audit. Not duplicated here and not waited on.

### If NOT MET: the smallest thing, and who owns it

Criterion 1 is met on the gated paths. To make "by any path" true on the email
channel it is **two sites, not twenty-six**: apply proposal P1 to
`scripts/batch_activate.py:144` and P2 to `scripts/resume_487.py:269`, both
already covered by a RED test that turns green when they land. Owner: the
operator orders (it is his B decision, and P1 is rank 0 of 0030's own ranking);
the pilotcaps lane applies.

---

## 2. A reply that asks for removal results in a written suppression row

### MET.

**The command, in T2 (`fa964f8cc`)** — the same module, the write classes:

    cd resonate-trees/audit0160-suppression
    py -3 -B -m unittest tests.test_a_suppressed_address_cannot_reach_a_provider

**Result: Ran 37 tests, OK**, of which the eight that answer this criterion:

    ARemovalRequestIsWrittenAndSurvivesARestart
      test_an_attributed_removal_request_writes_a_suppression_row       ok
      test_an_unattributable_removal_request_still_writes_a_held_row    ok
      test_a_hold_is_a_hold_and_not_a_silent_permanent_opt_out          ok
      test_the_reader_process_can_see_a_known_row                       ok   <- positive control
      test_the_mutation_goes_red                                        ok
    TheDncLedgerDoesNotDropARowItReportedWriting
      test_a_torn_append_does_not_swallow_the_next_row                  ok
      test_a_healthy_file_reports_no_damage                             ok   <- positive control
      test_genuinely_unreadable_bytes_are_reported_not_hidden           ok
      test_a_file_already_glued_by_an_older_crash_still_recovers_both   ok

**"Demonstrated, not assumed" is satisfied in the strict sense.** The row is
read back **in a separate interpreter**, and `test_the_reader_process_can_see_a_known_row`
is the control that proves the reader process works at all — without it, "the
row is there" and "the reader is broken" would be indistinguishable. The ledger
class then covers the failure mode that would make a reported write a lie: a
torn append that swallows the next row, with a healthy-file control so that
`damaged_lines() == []` cannot pass vacuously.

`ARemovalRequestIsWrittenAndSurvivesARestart.test_the_mutation_goes_red` is
B2 itself: it reverts `inbound.mutated_records` to the old `status == "applied"`
condition — the defect in `src/inbound.py:552-556` that discarded computed
safety holds in memory — and asserts the written hold disappears.

**A note that strengthens the verdict rather than qualifying it.** Those four
write tests stayed **GREEN** under §1's `suppression.decide` mutation, which
took 13 other names red. Criteria 1 and 2 therefore have genuinely independent
proofs: breaking the gate does not fake the write, and vice versa.

Caveat for the record, not against the verdict: measured only in T2, because
`src/suppression.py` exists on no other ref.

---

## 3. li1 renders a real connection note for every contact, RED if empty

### NOT MET — and it cannot be met as written without the operator reversing or scoping a standing decision of his own.

Reported as it stands, per the brief. LinkedIn is deferred from CANARY-01 by
`DECISION-canary-channels-2026-10-15.md`; the criterion does not disappear with
the channel and the next canary inherits it.

**The command, in T3 (`32cb420f7`):**

    cd resonate-trees/audit0160-glmc
    sed -n '85,105p' config/linkedin/productive-standard.json

**Result** — the `CONNECTION_REQUEST` node ships an empty string, not a merge
variable and not a placeholder:

    "nodeType": "CONNECTION_REQUEST",
    "payload": {
      "messages": [ "" ],
      "fallbackMessage": "",
      "toBeWithdrawnAfterDays": 21
    }

This matters more than "unset". `docs/CONTEXT-RESET-2026-09-15-E.md` records
that the HeyReach sequence holds **merge variables** and the words arrive per
lead, which is why no sequence write is needed. An empty string is not a merge
variable: there is no slot for the per-lead words to arrive in. So the note does
not render because nothing downstream reads one.

**And no test goes RED on an empty li1.** The nearest test in the tree pins the
exact opposite:

    tests/test_a_connection_request_may_carry_no_note.py
      "OPERATOR DECISION, 2026-09-22: 'allow the note-less connection request'."

That decision narrowed `validate_sequence_for_write`, which had refused any
payload with no non-empty `messages` on MESSAGE, INMAIL and CONNECTION_REQUEST
alike. The narrowing is deliberate and well-argued — LinkedIn genuinely sends a
request with no note, it is what clicking Connect without typing does, and the
client's best-performing campaign does exactly that at 13.6% accepted. The
tests exist to keep the narrowing a narrowing.

**So two authorities contradict each other and neither is wrong on its own
terms.** Exit criterion 3 (2026-10-14) wants a rendered note for every contact
with a RED-on-empty test. The operator's decision (2026-09-22) permits no note
at all. A task that "made criterion 3 pass" would be reversing a decision it
has no standing to reverse.

### The smallest thing that would make it true, and who owns it

The operator decides whether the note-less permission is **global** or
**per-campaign**. That is one sentence from him and it is the whole blocker.

- If global, criterion 3 is withdrawn and said to be withdrawn, in
  `CANARY-01.md`, so the next canary does not rediscover this.
- If per-campaign, then: a campaign-scoped predicate that a canary
  `CONNECTION_REQUEST` must carry a rendered, non-empty, claim-checked note;
  the merge variable put back in `productive-standard.json` so there is a slot;
  and a RED-on-empty test alongside the existing permission tests, which stay
  green. Owner: operator for the scope; GLM lane for the predicate and the test.

Both forms also still need the two things
`DECISION-canary-channels-2026-10-15.md` already names: `batch_linkedin_push.py`
routed through `heyreachfactory.ensure_leads`, and whether
`heyreach.add_leads_to_list` self-gates, which needs a task permitted to read
`src/providers/heyreach.py`.

### One unrelated failure found while measuring, reported and not attributed

    cd resonate-trees/audit0160-glmc
    py -3 -B -m unittest tests.test_linkedin_note tests.test_a_linkedin_message_is_not_a_connection_request
    Ran 43 tests — FAILED (failures=1)

    FAIL  test_linkedin_note.TestTheNoteGoesThroughTheSameDoorTheEmailDoes
          .test_an_em_dash_is_normalised_rather_than_spending_an_attempt

Whether this name is in that branch's own reference was not measured here, so
it is reported as present and not charged to anything. A name-set diff against
the branch's reference answers it.

---

## 4. Every template `stage_s7_copy` can render passes the ceiling and the floor

### MET in T3 (`32cb420f7`). NOT MET in T4 (`93162471d`). Merging the two turns the suite RED, and that is measured below, not argued.

**The command, in T3:**

    cd resonate-trees/audit0160-glmc
    py -3 -B -m unittest tests.test_every_template_is_inside_the_word_contract

**Result: Ran 7 tests, OK.**

The four bodies B4 named are inside their contracts. Measured directly through
the test's own render helpers rather than taken from its verdict — the counts
are the whole-angle-space minimum and maximum, since the angle phrase sits
inside the body:

    contract (writer, floor..ceiling)   rendered
    em1  60..90    BODY_1               76..83
    em2  45..90    BODY_2               87
    em2  45..90    comparable_proof_short  59   (B4 recorded 42 against the 45 floor)
    em3  60..90    rung3_champion       88
    em3  60..90    rung3_economic_buyer 78     (B4: 104, over)
    em4  45..90    angle_shift_champion 74     (B4: 127, over)
    em4  45..90    angle_shift_economic_buyer  81..86   (B4: 122, over)
    em5  45..90    close_champion       62..68
    em5  45..90    close_economic_buyer 59..64

The trims that did it are `21dae6a70` ("the four approved copy trims, applied
mechanically") and `38c0db9c4` ("b1-b-trim, the operator option A").

### Both bounds attacked, in both directions, by me

The criterion asks for a test that goes RED when a template escapes the check.
The module's own `TestCoverageIsStructural` (3 green) covers *escaping the
check* — it plants a probe template into the real `cadence.TEMPLATES` and
demands the guard name it, and covers the other direction too. What was checked
from outside is that the bounds themselves are live on real templates:

    CEILING   +40 filler words on close_champion's body in src/cadence.py
              Ran 7 — FAILED (failures=1)
              "close_champion: 104 words, contract 45-90, OVER by 14
               (persona 'champion', angle family 'delivery')"

    FLOOR     close_champion's body replaced with a 9-word sentence
              Ran 7 — FAILED (failures=1)
              "close_champion: 9 words, contract 45-90, UNDER by 36"

Both restored by `git checkout -- src/cadence.py`;
`md5 dd8310db8464be8faa1d6a28df88be61` before and after, `git status --short`
empty, module green again (Ran 7, OK). The refusal names the template, the
count, the contract and the overage, so it is a diagnosis and not a boolean.

### T4 is the other answer, and it keeps the suite green over an unfixed defect

    cd resonate-trees/audit0160-glmreview
    py -3 -B -m unittest tests.test_no_template_escapes_the_word_contract
    Ran 8 tests — OK (expected failures=3)

      expected failure  test_angle_shift_champion_is_over_the_em4_ceiling
      expected failure  test_angle_shift_economic_buyer_is_over_the_em4_ceiling
      expected failure  test_rung3_economic_buyer_is_over_the_em3_ceiling

Each asserts the body is at or under its ceiling and carries
`@unittest.expectedFailure` because it is not. That is an honest pin, and it is
also why criterion 4 is NOT met on T4: the suite reports OK while the three
templates B4 named are still over.

### The collision, measured

In T4, `src/cadence.py` and `scripts/stage_s7_copy.py` were replaced with
`32cb420f7`'s blobs — exactly the post-merge content for the only two files
glm-c changed — and the module re-run:

    git show 32cb420f7:src/cadence.py          > src/cadence.py
    git show 32cb420f7:scripts/stage_s7_copy.py > scripts/stage_s7_copy.py
    py -3 -B -m unittest tests.test_no_template_escapes_the_word_contract

    Ran 8 tests — FAILED (unexpected successes=3)

Restored; both md5s identical (`0d868192bdad3e4ab96de65900922338`,
`7df3bbaca0b3dc6a1dc73041c17ec1f3`), tree clean.

**So whichever of `32cb420f7` and `93162471d` lands second must remove those
three `@unittest.expectedFailure` markers in the same commit, or the merge
gains three failing names that nobody will be able to attribute.** Owner:
whoever integrates. This is the kind of thing an every-merge name-set diff
catches — and the kind that a count would not, since 3 appear and 3 disappear.

### What criterion 4 does not reach, now with numbers

The contract is enforced on **templates**. Nothing counts the **composed body
that ships**. Recomputed from the approval sheet's own bytes, for the ten rows
of the canary cohort:

    body paragraphs only            77 .. 85 words   = the sheet's "gate" figure
    + CTA URL (1) + signature (3)   81 .. 89 words   = the sheet's "composed as sent"
    + the 11-word opt-out sentence  92 .. 100 words  = what the approved bytes contain

The opt-out sentence is **inside the bytes that were hashed and approved** and
**outside both printed counts**. If the 90-word hard ceiling applies to what
ships, all ten breach it by 2 to 10 words. If it does not, none does, and
nothing in code can tell the difference because nothing counts the composed
body at all.

This is open item 5 of `DECISION-canary-approval-2026-10-15.md`, which recorded
"the as-sent text at the widest shape is 91 against a ceiling of 90". **The
widest shape is 100.** The operator's call, and nothing below it can be decided
without it.

**Recommendation: exempt the opt-out footer from the word ceiling explicitly,
in the writer contract, in writing.** An opt-out route is a compliance
requirement, and a ceiling that counts it creates pressure to shorten or drop
the one sentence that must never be shortened or dropped. But it has to be
written down rather than left as a convention, because today two of the three
counts silently exclude it and the third silently includes it — which is two
authorities for one number, the shape TASK-943 already had to resolve once.

---

## 5. The count of write paths that bypass the gate is zero

### NOT MET. 26 of 58, and this is the one criterion whose denominator is derived rather than kept by hand.

**The command, in T1 (`22c7ace62`):**

    py -3 -B scripts/write_path_denominator.py .

    bison: 13 mutating public functions
       attach_leads, attach_senders, create_campaign, create_lead,
       detach_senders, ensure_custom_variables, pause_campaign,
       resume_campaign, set_limits, set_schedule, set_sequence, stop_lead,
       update_lead
    heyreach: 12 mutating public functions
       activate_campaign, add_leads_to_campaign, add_leads_to_list,
       add_senders, create_campaign, create_list, pause_campaign,
       remove_senders, resume_campaign, set_sequence, start_campaign,
       stop_lead_in_campaign

    write paths            : 58
    pass through the door  : 32
    BYPASS the door        : 26

**The same 26 of 58 in T2** (`py -3 -B scripts/write_path_denominator.py
resonate-trees/audit0160-suppression`), with line numbers shifted by that
branch's edits to `bisonfactory`. The number is stable across two trees.

### The denominator, and how it was derived

**Nothing is typed.** The set of mutating provider functions is the transitive
closure UP each provider module's own call graph from its HTTP mutating
helpers — `bison`: `_post`, `_patch`, `_put`, `_delete`; `heyreach`: `_write`,
`_write_body` — so a new write verb enters the denominator the day it is
written, without anyone remembering to add it. The baseline
`scripts/known_write_bypasses.json` is produced by
`scripts/regen_write_bypass_baseline.py` from that same analyzer. No filename
and no function name appears in either side.

`src/providers/*.py` is closed to the lanes by standing instruction. The
analyzer **parses** those two files with `ast` to derive the verb set; their
contents were not read.

**The classification rule, and the direction it is wrong in.** A call site
counts as gated when the mutating call and a `perform(...)` sit in the SAME
function. That over-credits a helper called only from a gated function, so
**26 is a floor on the bypasses and never a ceiling**. Every `src/` hit was then
read by eye. Two earlier rules were tried and both erred in the same direction
as the claim they were checking: a lexical "inside the `perform(...)` call" test
said 42 (it misses a transport defined as a named function just above the call),
and following `transport=<name>` to a `FunctionDef` or `Assign` said 30 (it
misses lambdas tuple-unpacked in a `for`, `src/orchestrator.py:672`).

"The door itself" is always 0 and that is not a defect: `perform` never calls a
provider — the caller hands it a `transport=` callable, so the provider call
always lives at the call site.

### Why this is stated as a fraction and not as a count

`sink_token_split.py` carried **fourteen hardcoded script basenames** and
reported "0 scripts with a token-free write" while **seven** scripts holding
ungated provider writes sat outside its own denominator: `batch_linkedin_push`,
`probe_list_staging`, `linkedin_activate`, `make_481_inert`, `batch_activate`,
`batch_linkedin_reconcile`, `resume_487`. A numerator presented against a
hand-kept denominator — `THE-CATALOGUE.md` entry 7, family 2. All seven are in
the 26 below, and six of them are also in §1's 21 unconsulted paths.

### The 26

    9 in src/bisonfactory.py
      _ensure_limits    bison.set_limits
      _ensure_schedule  bison.set_schedule
      _ensure_senders   bison.attach_senders
      _ensure_leads     bison.ensure_custom_variables, bison.create_lead,
                        bison.update_lead ×2, bison.attach_leads
      _ensure_stopped   bison.pause_campaign

    17 across 9 scripts
      batch_activate.py              bison.resume_campaign
      resume_487.py                  bison.resume_campaign
      make_481_inert.py              bison.stop_lead ×2
      batch_linkedin_push.py         heyreach.create_list, add_leads_to_list,
                                     create_campaign, set_sequence
      batch_linkedin_reconcile.py    heyreach.set_sequence
      linkedin_activate.py           heyreach.activate_campaign ×2
      probe_list_staging.py          heyreach.create_list, add_leads_to_list ×2
      stage_canary_lead.py           heyreach.add_leads_to_list
      write_linkedin_lead_variables.py  heyreach.add_leads_to_list ×2

### Pinned as a SET, both directions, with a vacuous-pass guard

    py -3 -B -m unittest tests.test_no_new_write_bypasses_the_door
    Ran 10 tests — OK

The baseline is compared by set keyed `file::function::call` with an occurrence
count, **never by a total** — because three finished suites once reported the
same 231 for different sets. It fails on a new site, on a site that gained an
occurrence, **and on a site that has vanished**, so the baseline cannot quietly
decay into a list of things that no longer exist. A stored total that disagrees
with the stored enumeration also fails.

`TheInstrumentIsNotDegenerate` (5 of the 10) is checked before any answer is
believed: both providers must contribute mutating functions, each must
contribute more than five, four known verbs must be found by name as a positive
control, the classifier must answer **both** ways, and there must be more than
twenty write paths at all. If the closure ever broke and returned an empty verb
set, every count would be zero, zero is not greater than the baseline, and this
module would pass while watching nothing — the exact shape of the controls this
repository has already found unable to fail.

### The fixes exist, are tested, and are unapplied

    py -3 -B -m unittest tests.test_the_eight_write_path_proposals_are_unapplied
    Ran 8 tests — FAILED (failures=8)

Eight RED-by-design tests, one per proposal from TASK 0030, in 0030's ranked
order, every one driving the real entry point with the real guards and
asserting on what the provider verb received. All eight red, none applied.

### If NOT MET: the smallest thing, and who owns it

**Apply P1 and P2 — the two `bison.resume_campaign` sites. That is the whole
prospect-facing email exposure, and it is 2 of 58.** The remaining 24 are 11
LinkedIn sites (channel deferred), 3 safety writes, 3 config writes carrying no
lead, and 7 lead writes in `_ensure_leads` that already consult suppression
before writing. Owner: the operator orders (both are his B decision); pilotcaps
applies; the RED tests turn green as the proof.

**And a recommendation on the criterion's own wording, because literal zero is
the wrong target.** Gating `bison.stop_lead` or `bison.pause_campaign` makes a
halt refusable, and a refusable halt is worse than an ungated one — which is
precisely what `b77cd4b20` had to fix the other way, making `bison.pause` need
no GateToken. Criterion 5 should read **"zero ungated write paths that can
PERFORM a prospect-facing action"**. Under that reading it is 2 of 58 today and
closable this week. Under the literal reading it can only be satisfied by
gating the brakes. Operator's call; recorded here with the recommendation
rather than quietly reinterpreted.

---

## 6. Mailbox health — ANSWERED 2026-10-14 from the estate export

### MET. Two sentences of its own text are stale, and the substance holds.

**The command** (offline, over the committed-by-hash exports in `resonate-ops`):

    sha256sum canary/sender-estate-export-2026-10-15b.csv
    # then a csv.DictReader tally over Status / Emails Sent / Bounces / Replies / Opens

**Both export hashes reproduce exactly** as recorded in
`DECISION-canary-cohort-and-pool-2026-10-15.md`:

    (a) 46860f5d0732e2324e160379ff62b3aea1aafdb59257685fdea35e3ece3506a8
    (b) 07f4c67144d3566356136ac9d3aa7f86d4be5d43ac3bf8cf4df3d3c65b881cca

**Result on export (b), 181 rows:**

    Status     Connected 179, Not connected 2
    Emails Sent   175,237
    Bounces         1,771   1.01%
    Replies         1,771   1.01%
    Opens               0   on all 181 rows

**Correction 1.** Criterion 6 says "All 181 mailboxes read Connected". On
export (b) **two are Not connected**. Neither is in the canary pool or its
reserve; both were already named in the addendum to the cohort decision. The
criterion's figures (174,342 sent, 1,753 bounces, 1,765 replies) are export
(a)'s and are also reproduced exactly — the numbers are not wrong, they are
dated, and `Status`, `Emails Sent`, `Bounces` and `Replies` are all time-varying
in this source. Any later statement about this estate names the export it was
measured on.

**Correction 2, so the next reader does not chase it.** On export (b) the
Bounces and Replies totals are **both 1,771**. The columns are genuinely
distinct: only 16 of 181 rows have `Replies == Bounces`, and the first row is
11 replies against 12 bounces in both exports. The equal totals are a
coincidence, not a duplicated column.

The substance of the criterion stands: 1.01% bounce across 175,237 sends, and
the distinction it insists on — a BOUNCE means the mail left and was rejected,
the October 88% was SEND FAILURE meaning the mail never left — is unaffected.
`Opens` reading 0 on all 181 across 175,237 sends is confirmed, so open tracking
is off or broken and no metric may be built on it.

---

## 7. One owner across the attached pool, every body signed with that owner's name

### NOT MET. The mechanism is built, green and mutation-shaped. The fact it asserts is red, the per-campaign form needs a provider read nobody has approved, and the offline arithmetic below shows the chosen pool's owner is not on the allowlist under the allowlist's own rule.

**The command, in T4 (`93162471d`):**

    cd resonate-trees/audit0160-glmreview
    py -3 -B -m unittest tests.test_every_body_is_signed_by_the_pools_owner
    Ran 26 tests — OK (skipped=1, expected failures=4)

### What IS satisfied: both "goes RED" clauses, as mechanisms

    ThePoolRule.test_a_two_owner_pool_is_refused_naming_both_owners_and_the_row   ok
    ThePoolRule.test_an_ownerless_mailbox_refuses_the_pool_by_id                  ok
    ThePoolRule.test_an_empty_pool_is_refused                                     ok
    ThePoolRule.test_the_real_thirteen_mailbox_pool_yields_its_single_owner       ok   <- positive control, real data
    TheBodyCarriesTheSignatureExactlyOnce.test_an_unsigned_body_is_refused        ok
    TheBodyCarriesTheSignatureExactlyOnce.test_a_doubled_body_is_refused_with_the_count  ok
    ComparisonIsNfcExact.test_a_diacritic_stripped_spelling_is_a_different_owner  ok
    ComparisonIsNfcExact.test_a_case_folded_spelling_is_a_different_owner         ok

The two-owner refusal asserts the message **names both px values**, so the test
can tell "it refused" from "it was never asked" — the distinction the dead
controls in this repository could not make.

### What is NOT satisfied: the four facts, and the one skipped test that matters most

    expected failure  TheFourRedTests.test_the_estate_backing_the_signature_is_one_pool_with_one_owner
                      the 225 mailboxes attest TEN owners; two attest none
    expected failure  TheFourRedTests.test_every_mailbox_owns_the_signature_it_is_made_to_send
                      NFC-exact: 0 match, 223 mismatch, 2 no-owner
    expected failure  TheFourRedTests.test_the_compose_path_refuses_a_body_that_already_carries_the_signature
                      the double-sign guard is unwired
    expected failure  TheFourRedTests.test_the_five_misspelled_display_names_are_corrected_in_emailbison

    skipped           TheLiveRead.test_the_live_estate_classifies_under_the_same_ladder
                      "set B7_LIVE_ESTATE=1 only after the operator approves the
                       /sender-emails read (full walk; page-1 is not
                       classifiable). NOT APPROVED as of 2026-10-15."

And the pool test's own docstring is explicit that the green one is a stand-in:
"This is the offline stand-in for the per-campaign pool check; the per-campaign
form needs the live sender read." **Criterion 7 asks for the per-campaign form**
— "a campaign's attached pool" — and that form does not exist and cannot be run.

### What this audit could settle offline, and it is the gate the attach sits on

`DECISION-canary-cohort-and-pool-2026-10-15.md` §2 named the open question:
"The fixture spells the owner with the diacritic; the export without. One of the
two is stale and the attach decision rests on which." That is answerable with
arithmetic, using this repository's own px function
(`scripts/task189_scrub_pii.py:35`, SALT `resonate-pii-salt-2026-09-16`, sha256
of SALT+value, first 12 hex):

    px(<the roster name, NFC, WITH the diacritic>)  =  px-75ee916b9999
    px(<the same name, plain ASCII>)                =  px-fc7d1255b8a3

(The two spellings are not written out here: the shorter one is on the
`test_fixture_hygiene` forbidden-name list, so a repository file may not
carry it. Both are in `resonate-ops/CANARY-01-ATTACH-PAYLOAD-2026-10-15.md`
and in the estate export, and the px values below are the whole argument.)

And against the two committed authorities:

    resonate-ops/CANARY-01-ALLOWLIST-2026-10-15.md
        "ivan — owner px-75ee916b9999 — 13 mailboxes"
        2738 2741 2745 2748 2750 2751 2757 2760 2763 2766 2772 2775 2778

    tests/fixtures/sender-estate-2026-09-21.json  (on 93162471d, 225 rows,
    keys id / name_px / owner_px / owner_present / damaged — no addresses)
        owner histogram:
          px-387dd1f77205  71
          px-19834114d0e7  58
          px-7513d195dfb1  17   px-c82dcaabaec1  17   px-494dc227d91e  17
          px-75ee916b9999  13   <-- the diacritic spelling
          px-898fe4fd21fe  12   px-a0e6d43e8d90  11
          px-894888e9f1c3   6   <no-owner> 2   px-523053400694 1

        ids under px-75ee916b9999: exactly the thirteen above

        px-fc7d1255b8a3 is present in the fixture: FALSE

**So the plain spelling — the one all twelve live mailboxes carry in their
`Signature` column, and the one all 24 approved bodies sign — exists in no
group of the allowlist and nowhere in the fixture's owner histogram.** Under the
allowlist's own owner authority (the signature string, NFC-exact), the ten
chosen mailboxes have an owner that is **not on the allowlist**.

Two readings, and nothing offline distinguishes them:

1. The provider's signature strings were edited between 2026-09-21 and
   2026-10-15, dropping diacritics. Then these are the same humans, the pool is
   right, and the allowlist's px values simply need regenerating from the
   current export. 13 against 12 is consistent with the allowlist's own note
   that 44 mailboxes have left the estate since the fixture was taken — and
   the estate already carries two spellings of one other person, 61 mailboxes
   against 5, with 5,441 emails sent under the shorter one.
2. They are different mailboxes. Then the pool is drawn from outside the
   allowlist and the canary must not use it.

**Reading 1 is far more likely and "far more likely" is not a pass.** UNKNOWN
is not a pass, and a canary must not be the thing that finds out.

### What IS verified offline, independently of glm-c/0150

Measured directly from export (b), not taken from the lane's `POOL OK`:

- all ten proposed mailboxes present, all `Connected`
- `Name` takes exactly **one** distinct value across the ten
- `Signature` takes exactly **one** distinct value across the ten
- bounce ranking 0.43% → 1.14%, reproducing the decision's ordering to two
  decimals
- 12 rows for that one local-part in the export, one owner name, `Campaigns Count` 10–11
- the reserve pair likewise, both Connected

So the *homogeneity* half of criterion 7 is verified for this specific pool on
this specific export. The *allowlist membership* half is UNKNOWN, and the
*per-campaign test* does not exist.

### If NOT MET: the smallest thing, and who owns it

1. **The operator approves one provider read**: `GET /sender-emails`, fully
   walked (15 per page, ignores `per_page`, so 13 pages for 181), returning id +
   address + signature. One read, no write. This single approval unblocks the
   id↔address map the attach needs (§ the attach payload), the allowlist
   currency gate, and `B7_LIVE_ESTATE=1`. Owner: **operator**.
2. Regenerate `tests/fixtures/sender-estate-2026-09-21.json` and the allowlist
   px values from that read, then remove the `expectedFailure` markers that the
   regeneration turns green and keep the ones it does not. Owner: GLM lane.
3. The per-campaign pool check, which is what criterion 7 actually asks for:
   given a campaign id, read its attached senders, refuse on more than one
   owner, and refuse a body whose signature is not that owner's — with a test
   that goes RED on two owners and RED on a foreign signature. The pool-rule
   primitive already exists and is green; this wires it to a campaign. Owner:
   GLM lane, after step 1.

Carried forward unchanged and not solved by any of the above:
`sendersignature.refuse_if_duplicate` has zero production callers, and every
mailbox in the estate carries a signature, so if the provider appends the
mailbox's own signature on send a double sign-off would not be caught in code.
That needs a measurement before the first send and it is live rather than
theoretical.

---

## 8. The review file is approved by the owner

### MET-WITH-CAVEAT. The bytes are intact and the 48 row digests reproduce. The caveats are the approval's own and they are load-bearing.

**The commands:**

    sha256sum resonate-ops/canary/APPROVAL-SHEET-2026-10-15.md
    # then recompute all 48 per-row digests from the sheet's own fenced bodies

**Result:**

    file sha256  eb6b93f516e457aef7427c34476ea4eeaae298669f9b6728f85ef710133244f4
                 identical to DECISION-canary-approval-2026-10-15.md

    composed digests reproduced: 24/24
    bare     digests reproduced: 24/24
    mismatches: []

    verdicts: 23 APPROVED; row 11 and row 24 left empty, as recorded

`DECISION-canary-approval-2026-10-15.md` made this the approval's own staleness
test — "A re-verification must reproduce all 48 row digests exactly; if it does
not, this approval is stale by construction". **It reproduces.** The
construction, written down so it stays repeatable without re-deriving it:

    composed bytes = everything between the ```text fence and its closing fence
    bare body      = the first three paragraphs of that, joined by a blank line

### The caveats, which are the approval's own

- **It was a bulk approval.** The 23 bodies were not read row by row; the
  operator was offered both options at 20:04 and chose B, and the sheet says so
  at the top. It amends `DECISION-review-rule-2026-10-15.md` option 3 for this
  sheet only.
- **It approves words, not sends.** The sheet's own words: every row's sender is
  **UNKNOWN until attach**, the sender pool is not approved, and Flag B is not
  cleared and cannot be cleared by it.
- **And the standing rule that bears hardest on it.** An approval in this system
  binds the mailbox and the signature — that binding is why 0 of 3,005 stored
  approvals are still valid. These 23 approvals name no mailbox. So the mailbox
  binding is still owed, and it is owed on exactly the pool §7 cannot yet
  classify. Criterion 8 is met on its own terms; it does not carry the weight
  that criterion 7 failing takes off it.

A third-party note on the word counts: the sheet's "gate" and "composed as sent"
figures both exclude the 11-word opt-out sentence that is inside the bytes they
hash. See §4 — it changes the ten from 81-89 to 92-100 against a hard ceiling
of 90, and it is the operator's open item 5.

---

## 9. A kill switch the owner can operate alone is named and tested

### NOT MET. `src/killswitch.py` is a reader. It has no setter, so there is nothing for the owner to operate.

**The commands, in T1 (`22c7ace62`):**

    py -3 -B -m unittest tests.test_killswitch tests.test_lead_writes_respect_the_killswitch
    Ran 32 tests — OK

    py -3 -m src.killswitch --workspace <slug>        # prints six layers, changes nothing

The 32 green tests prove the **layers** work: six of them, outermost first,
most restrictive wins, every verdict reported, default off at every layer that
has a setting. None of them proves anything about operating it, because the
module's own docstring is explicit:

> This module reads. There is no setter, no environment variable it consults
> that would enable anything, and `GLOBAL` is derived from the refusal in `push`
> rather than from a flag.

`global_state()` answers from `hasattr(push, "LiveSendNotEnabled")`. Changing
that is a code review, not a toggle — which is right for turning sending **on**
and is exactly the problem for turning it **off**.

**And CLAUDE.md already states the limit this produces, which no amount of
testing the layers changes:** the killswitch refuses to START an action and
cannot END a campaign already running. Turning `sending.live` off was never a
pause, and an active campaign kept sending through it exactly as documented.

**There is no halt command.** Measured, not assumed:

    ls scripts/ | grep -iE "halt|kill|stop|panic|pause|freeze"
      bounce_stop_7day.py     a check
      hard_stop_check.py      a check

`src/leadstop.py` has a `main()` and stops **one person's** next email at the
provider with a readback, which is a different and smaller thing than a kill
switch. The verb that would be one — `bison.pause` / `EMAIL_PAUSE` — is in
`providerwrites.SUPPORTED`, is `facing=False`, and as of `b77cd4b20` needs no
GateToken, so a halt can no longer be refused for want of a grant:

    cd resonate-trees/audit0160-haltopen        # T5, b77cd4b20
    py -3 -B -m unittest tests.test_a_safety_pause_fails_open
    Ran 1 test — OK
    TheHaltPausesWithoutAGateToken.test_the_pause_is_performed_with_no_gatetoken_presented

Its only callers are `scripts/bison_watch_loop.py` — the automated blank-content
/ harm-rate halt — and `scripts/nudge_487_scheduler.py`, one named campaign.
Neither is a thing the owner operates alone.

**So the owner's only working kill switch today is pausing the campaign by hand
in the EmailBison UI.** It is real, it is named in CLAUDE.md, and it is proven
in practice — he did exactly that to 487, 489 and 493 on 2026-09-28. It is also
outside this system, so it cannot be tested here, and criterion 9 asks for
"named **and tested**".

### If NOT MET: the smallest thing, and who owns it

One script and three tests. `scripts/canary_halt.py --live` that:

1. issues `EMAIL_PAUSE` for the canary campaign through
   `providerwrites.perform` — no GateToken needed, per `b77cd4b20`;
2. reads the campaign status back from the provider and **refuses to report
   success until it reads `paused`**, because a write that reported success is
   not evidence the pause landed;
3. prints the one-line invocation at the top of its own `--help`, so the owner
   does not have to find it.

Tests: the pause reaches the transport; it is **not** refusable by a missing
grant or by the killswitch (`b77cd4b20`'s property, re-asserted at this entry
point); and the readback is asserted rather than assumed. Plus one line in
`CANARY-01.md` naming the EmailBison UI pause as the fallback that always works
and the reason it is the fallback.

Owner: the pilotcaps lane writes it; **the operator confirms that the verb may
be issued by hand**, which is the only part a lane cannot decide. Note that
`b77cd4b20` is not merged, so the script's no-GateToken premise lands with it.

---

## 10. WHAT STANDS BETWEEN HERE AND THE ATTACH, IN ORDER

Four of the nine are NOT MET. Three of those four reduce to things only the
operator can do, and they are small:

1. **One provider read**: `GET /sender-emails`, fully walked. Unblocks criterion
   7, the allowlist currency gate, and the `sender_email_ids` the attach cannot
   be written without. *(operator)*
2. **One decision on the opt-out sentence**: does it count toward the 90-word
   hard ceiling? All ten rows are 92-100 words with it and 81-89 without. *(operator;
   open item 5 of his own approval decision)*
3. **One decision on criterion 3's scope**: is the note-less connection request
   permission global or per-campaign? *(operator; LinkedIn is deferred, so this
   is not on the critical path for CANARY-01, but criterion 3 cannot be marked
   either way without it)*
4. **An order to apply P1 and P2**, which closes the whole prospect-facing email
   half of criterion 5 and the "by any path" caveat on criterion 1 at the same
   time — they are the same two sites. *(operator orders; pilotcaps applies)*
5. **One script for criterion 9.** *(pilotcaps, once the operator confirms the
   verb may be issued by hand)*
6. **Integration.** None of this is true in one tree. The merge order has a
   measured trap in it: §4's three `expectedFailure` markers.

`resonate-ops/CANARY-01-ATTACH-PAYLOAD-2026-10-15.md` holds the payload this
task also produced — offline, written, not executed, and gated on item 1 above.

---

## 11. WHAT THIS TASK DID NOT DO

Attached nothing. Made no provider, Apify or network call. Did not open Door A.
Changed no cap and no gate. Did not edit the approval sheet or any decision
file. Did not push or merge to master. Did not touch the main checkout or any
other lane's worktree — T2 through T5 are detached checkouts at named SHAs that
no track owns, and they were removed when the audit ended.

Did not run a full suite. Every mutation above was performed against source in a
detached tree, restored by `git checkout --`, verified byte-identical by md5 and
by an empty `git status --short`, with `__pycache__` wiped on both sides of each
measurement. This branch adds one script under `scripts/` and this document
under `docs/`; a change under `src/` or `tests/` would owe a new full reference
and neither is made here.
