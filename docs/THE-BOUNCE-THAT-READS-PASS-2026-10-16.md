# The bounce cell never read PASS — it could not read EXCLUDED either. TASK-0250, 2026-10-16

Measured in `wt-suppression-2026-10-14`, a **CRLF** tree (`requirements.txt`
CR=15, 812 bytes), on branch `task-suppression-bounce-RULE-2026-10-15`.
`src/preflight.py` is itself **LF** (CR=0), which is why `provenance()`
compares through `git diff` rather than a raw hash.

    before the repair    a29391ee94eafc69e03e31e3cf0a874455317f5c
    after the repair     c45fa20dfb677bcb8a3539e65bc89bd3ffc47727
    origin/master        b1f290c847eb2500b7eb39987ac34f6d6a8d00d2   re-fetched, unchanged

No provider call, no network call, no send, no activation, nothing
prospect-facing, no cap or gate change, no copy change. `config/.env`,
production `work/` state, `src/providers/*` and the monitor loops were not
read or modified. No push or merge to master.

`scripts/citecheck.py` (TASK-0210) on this file: **18 citations, OK=18,
MOVED=0, BROKEN=0, UNVERIFIABLE=0, REFUSED=0, ERROR=0.** The first draft
cited by symbol name only and that checker's own warning caught it — *"NO
CITATION WAS FOUND AT ALL ... a checker that finds nothing always reports
clean"* — so every claim below carries a line a reader can open.

---

## 0. THE ANSWER, FIRST, AND THE PREMISE DID NOT SURVIVE

TASK-0250 was dispatched to make `bounce_history` answer UNKNOWN when its
authority is **absent, empty, or resolved against the wrong tree**, on the
strength of TASK-0220 §0:

> "a bounce that was never recorded makes the preflight's `bounce_history`
> cell read **PASS**, not UNKNOWN"

**All three were already UNKNOWN, and all three already named the resolved
path.** `bounce_history` declares `needs: ("queue",)`, so TASK-0190's
authority gate covers it exactly as it covers the other thirteen queue rules.
Nothing in step 3 of the brief needed building.

The sentence is **right about `channels._bounced`** — it really does answer
`False` for a missing event, and on the send path, through
`channels.email_verdict` and `eligibility.decide`, that `False` is exactly as
dangerous as TASK-0220 said. It is **wrong about the CELL**, which was not
asking. TASK-0220's own §3 says so three paragraphs below its table — *"with
the queue authority absent or empty, TASK-0190's authority gate makes all 14
rules UNKNOWN before they are asked"* — so the document contradicts its own
headline. §3's table column reads "PASS" because it was reasoning from what
the decider returns to what the cell would say, and the cell never called the
decider.

**And the measurement found the opposite defect, in the one world that
matters.** The rule carried `ask: None`. So with the queue
PRESENT_POPULATED, the record supplied, and an `EMAIL_BOUNCED` event sitting
in its `events` list, the cell read:

    UNKNOWN   "this rule has no form that can be evaluated without a record
               or a provider read"

The one rule in the table whose whole job is to see a bounce could not report
one it was holding. That is an instrument which **only ever refuses**, and
the brief named the hazard itself: as useless as one that only ever passes,
and harder to see, because every control built for the other seven rows is
satisfied by it. Seven controls existed; not one of them touched this rule.

---

## 1. THE AUTHORITY, BY PATH, READ OUT OF THE CODE

Step 1 of the brief: establish which file `bounce_history` actually reads, by
path, at the SHA. Not inferred from the name.

Every line below was opened and read in this tree at `c45fa20df`.

| link | where | what it says |
| --- | --- | --- |
| the rule row | `src/preflight.py:904` `bounce_history` | `needs: ("queue",)`, `needs_record: True`, `channel: "email"` |
| the authority row | `src/preflight.py:430` `queue_path` is its `resolver`, counted by `src/preflight.py:281` `_count_queue_records` | the queue authority's two halves |
| the resolver | `src/store.py:34` `queue_path` | `os.environ.get("QUEUE")` **or** `os.path.join(ROOT, "work", "queue.jsonl")`, where `ROOT` is `src/..` — the CALLING tree |
| the counter's reader | `src/store.py:359` `read_jsonl` | one row per line; a non-JSON line raises, which is PRESENT_UNREADABLE and not an empty queue |
| the decider the row declares | `src/channels.py:103` `_bounced` | iterates `rec["events"]` for `type == events.EMAIL_BOUNCED`, matching on `contact` key or, when the event names no contact, on the address |
| the one state that licenses a PASS | `src/preflight.py:171` `ANSWERABLE` | `(PRESENT_POPULATED,)`, named once so a weakening is visible |
| the tree refusal | `src/preflight.py:191` `_inside` | normcased `commonpath`; a different drive raises and that is NOT inside |

So the authority is **one file**: `<tree>/work/queue.jsonl`, overridable by
`$QUEUE`. In this worktree it is
`C:\Users\Zvonimir\Desktop\wt-suppression-2026-10-14\work\queue.jsonl` and it
is **ABSENT** — which is why all 23 canary cells read UNKNOWN today and why
the preflight reports the main checkout's path through `production_work()`
rather than reading it.

There is a second, subtler fact and it is the reason the no-event case cannot
be a PASS: **the preflight does not read the record out of that file.** The
record arrives as the `record` key on the cohort contact, an argument to the
run. The queue authority gates whether the question may be asked at all; the
answer comes from whatever record the caller supplied. The repair therefore
names what it read — *the record supplied for them* — and makes no claim
about which file that record came from.

---

## 2. THE FOUR WORLDS, AS MEASURED, BEFORE AND AFTER

Step 2. Planted with `preflight._planted_state`, each world asked about its
own temporary tree, the contact always carrying a record so no cell is
UNKNOWN for the unrelated `needs_record` reason.

| world | queue authority state | cell BEFORE `a29391ee9` | cell AFTER `c45fa20df` |
| --- | --- | --- | --- |
| authority absent | `ABSENT` | UNKNOWN, path named | UNKNOWN, path named |
| present and empty | `PRESENT_EMPTY` | UNKNOWN, path named, `WHICH MEANS` | unchanged |
| resolved against another tree, **populated there** | `OUTSIDE_TREE` | UNKNOWN, `HARD REFUSAL`, both paths | unchanged |
| populated, record carries a hard bounce | `PRESENT_POPULATED` | **UNKNOWN** — "no form that can be evaluated" | **EXCLUDED**, event named |
| populated, record carries no events | `PRESENT_POPULATED` | UNKNOWN — "no form that can be evaluated" | UNKNOWN — naming the recorder and the soft count |
| populated, no record on the contact | `PRESENT_POPULATED` | UNKNOWN — `needs_record` | unchanged |

**One row moved.** It is the row the brief's C2 demands and the only one that
was wrong. The table is pinned as a test —
`TheFourWorlds.test_the_four_worlds_this_cell_was_asked_about` — so the claim
cannot drift away from the code.

Also measured directly, since the premise turns on it:

    channels._bounced(rec with EMAIL_BOUNCED) -> True
    channels._bounced({"events": []})         -> False
    channels._bounced({})                     -> False

---

## 3. THE REPAIR, AND WHY IT IS A READ AND NOT A GATE

`_STANDING-RULES.md` forbids a gate change. This is not one, and the shape is
TASK-0190's and TASK-0200's: a check that answers UNKNOWN instead of passing
by omission.

`src/preflight.py:730` `_ask_bounce_history` is new and the rule row's ask at
`src/preflight.py:913` `_ask_bounce_history` points at it. Three answers, and
PASS is not among them:

* **EXCLUDED** when `channels._bounced` finds a recorded `EMAIL_BOUNCED`,
  with the sentence naming the event, that `src/bouncepolicy.py:244` `decide`
  writes it for a hard bounce and for the third consecutive soft one, and
  that `src/channels.py:164` `email_verdict` refuses the address on it.
* **`Undecided` → UNKNOWN** when the event is absent, naming the soft count
  (`k of 3`, from `src/bouncepolicy.py:193` `consecutive_soft`) and
  `src/preflight.py:1192` `bounce_recorder`.
* **PASS: unreachable, on purpose.**

Four deliberate choices in it:

1. **Through the decider the row declares, not a second reading of it.**
   `channels._bounced` is private and is called anyway, for the same reason
   `_count_queue_records` calls `store.read_jsonl` rather than counting
   lines: a second definition of "what a recorded bounce is" would drift from
   the one the send path consults, and then the preflight and
   `email_verdict` would disagree about the same person. `email_verdict`
   itself is the wrong seam — it composes `_bounced` with MX and
   verification, which is `mx_and_verification`'s row.
   Pinned by `test_the_ask_reads_the_decider_the_row_declares`: blind
   `channels._bounced` and the cell must stop excluding.
2. **The absent event is not a PASS.** TASK-0220 measured why: the bounce
   recorder's failure line has **one writer and zero readers**, so the only
   production caller of `src/leadobserve.py:753` `record_bounces` can fail for
   an **unbounded** time with the watcher still reporting UP. "This address never
   bounced" and "the recorder stopped working on a date nobody can name" are
   the same empty `events` list, and no authority state can tell them apart —
   §3 of that document says exactly this and it is still true. A `False` from
   `_bounced` is a fact about the log, not about the address.
3. **The soft count is reported rather than rounded to none,** because the row
   declares `bouncepolicy.decide for the hard/soft split` and "2 of 3
   consecutive softs" is a materially different UNKNOWN from "none". A raise
   while counting reports `UNCOUNTED (<ExcType>)` — it may not lose the
   refusal and it may not be reported as zero.
4. **The recorder's failure string is deliberately not written into `src/` or
   into the new test file.** TASK-0220 pins ZERO occurrences of it anywhere
   under `src/`, because `src/` is where a reader of it would live and any
   occurrence there is worth looking at. The first draft of this repair put it
   in a docstring and in an assertion, and
   `test_the_estate_search_finds_the_writer_and_no_reader` went red with four
   hits where it demands one. **That test was right and the repair was
   wrong** — a mention in prose would have been a permanent false positive in
   the one search that proves the failure has no reader, which is how a
   working instrument gets taught to ignore itself. The string is named by
   emitting module instead, and both ends carry the reason so nobody helpfully
   puts it back.

### What would make PASS reachable

Not a code change here. `WHAT_WOULD_ANSWER["bounce_recorder"]` states it:
something that reaches a verdict from the bounce recorder's own health. Until
a reader of that failure exists, a missing bounce event licenses no PASS.
Pinned in both directions by
`test_pass_is_unreachable_and_the_reason_is_named`, so the refusal cannot
outlive its reason.

### Controls 8 and 9 — the repair is wired, not argued

The brief: *"If the preflight's cell cannot be shown to change with the
repair, the repair is unwired."* `preflight.controls()` goes from seven rows
to nine, the same pair-shape TASK-0200 used, and both appear in
`py -3 scripts/canary_preflight.py --controls-only`, which exits **0**:

    CONTROL OK   a RECORDED bounce in the queue authority is EXCLUDED with the event named, not UNKNOWN
                 expected ['PRESENT_POPULATED', 1, 'EXCLUDED', True, 1]
                 observed ['PRESENT_POPULATED', 1, 'EXCLUDED', True, 1]
    CONTROL OK   the same record with NO bounce event is UNKNOWN naming the recorder, not PASS
                 expected ['PRESENT_POPULATED', 1, 'UNKNOWN', True]
                 observed ['PRESENT_POPULATED', 1, 'UNKNOWN', True]

`src/preflight.py:1930` `_control_eight` plants ONE real queue record
carrying the bounce, written by `src/preflight.py:1905` `_bounce_queue_row`
and read back **through `store.read_jsonl`** so the record handed to
`evaluate` is the authority's own row rather than a dict built beside the
file. `src/preflight.py:1968` `_control_nine` is that record with an empty
`events` list. Their only difference is one event.

---

## 4. THE CONTROLS, AND TWO OF MY OWN ASSUMPTIONS THAT DID NOT SURVIVE

`tests/test_a_recorded_bounce_the_cell_could_not_report.py`, 21 tests, all
green. C1, C3 and C4 were already true and are pinned here **for this rule by
name** rather than only inside a loop over fourteen queue rules, because a
loop is where one rule's regression hides.

I wrote two tests asserting that `ask: None` fails control 8 and leaves 9
green, and that an ask which excludes everybody fails 9 and leaves 8 green.
**Both failed.** Each control's fourth observation watches the cell's
**reason**, not only its verdict, so `ask: None` reddens both — 8 on the
verdict, 9 on the reason alone. Corrected to what is measured, and the
discriminating mutations are the **reason-preserving** ones: an `ask` that
returns the real exclusion sentence to everybody satisfies control 8
completely and only 9 catches it; an `ask` that returns the real UNKNOWN
sentence to everybody satisfies 9 completely and only 8 catches it. Both
directions are now tests.

---

## 5. MUTATIONS — KILL-SET BY NAME, EVERY REVERT PROVEN BY MD5

Committed state mutated, one mutation at a time, never staged.
`work/suppression-measure/0250/mutate.py`; the full sets are in
`mutations.json` beside it. Observation set: the six modules that read
`src/preflight.py`.

    CLEAN  c45fa20df  md5 7b2e5971bd6d8fda6b40d078a1bb4da0
           181 tests, ZERO failing names

| # | mutation | mutated md5 | kills, net of collateral | revert md5 |
| --- | --- | --- | --- | --- |
| M1 | `ANSWERABLE` widened to accept `PRESENT_EMPTY` — C1's empty check | `d70695bffed4a2c07e814ffe760bb0eb` | 12 of 13 | `7b2e5971bd6d8fda6b40d078a1bb4da0` |
| M2 | `ANSWERABLE` widened to accept `ABSENT` — C3's absent fallback | `76a7421950720781012c490859880988` | 8 of 9 | `7b2e5971bd6d8fda6b40d078a1bb4da0` |
| M3 | `"ask": _ask_bounce_history` → `None` — C2's repair removed | `f10da6f137a69f0da044a0edd9c56fac` | 14 of 15 | `7b2e5971bd6d8fda6b40d078a1bb4da0` |
| M4 | `_inside` always True — C4's tree refusal | `e05ecf27117cee38aac13b426efa07a2` | 4 of 5 | `7b2e5971bd6d8fda6b40d078a1bb4da0` |
| M5 | the missing-event branch returns `None` (PASS) — the UNKNOWN floor | `49c995a5820a95410bc0bbdbb9aaf658` | 8 of 9 | `7b2e5971bd6d8fda6b40d078a1bb4da0` |

Final state re-hashed: `7b2e5971bd6d8fda6b40d078a1bb4da0`, equal to clean,
`git status` clean.

**One name is in all five kill-sets and is therefore NOT a kill.**
`TheReportsOwnProvenanceIsMeasuredNotTyped.test_the_instrument_is_confirmed_at_head_in_this_tree`
reddens for *any* edit to `src/preflight.py`, because it compares the working
tree against HEAD. A test that reddens for every mutation of a file makes
every mutation look killed; it is excluded from every count below. (It is
also the test that confirms the repair is committed: it failed before the
commit and passes at `c45fa20df`.)

The named kills, collateral removed:

* **M1** — `C1ThePresentAndEmptyAuthority.test_an_empty_queue_makes_this_cell_unknown_and_names_the_path`, plus 11 of TASK-0190's own: `test_a_present_but_empty_authority_is_unknown_not_pass`, `test_not_one_pass_survives_when_every_authority_is_empty`, `test_an_empty_authority_file_is_present_empty_not_populated`, `test_control_four_observes_the_state_the_count_and_the_exit`, both `TheAsymmetryIsKept` names, `test_an_empty_listing_is_present_empty_and_not_nobody_in_327`, `test_the_markdown_names_the_state_the_count_the_path_and_the_tree`, both pinned-control-count names and `test_the_script_takes_its_cohort_as_an_argument`.
* **M2** — `C3TheAuthorityRemovedEntirely.test_an_absent_queue_makes_this_cell_unknown_and_names_the_path`, plus 7: `test_an_absent_dnc_makes_the_rule_unknown_not_pass`, the three `AnExclusionOnAPartialReadIsStillAnExclusion` names, `test_a_declared_internal_match_still_fires_without_the_ledger`, `test_the_authorities_run_counts_populated_rather_than_present`, `test_an_unknown_contact_exits_two_and_is_counted_in_the_third_total`.
* **M3** — the C2 trio (`test_a_recorded_bounce_is_excluded_with_the_event_named`, `test_the_whole_table_reports_it_as_an_exclusion`, `test_the_ask_reads_the_decider_the_row_declares`), all three `ThePassThatIsNotReachable` names, `TheFourWorlds.test_the_four_worlds_this_cell_was_asked_about`, `test_controls_eight_and_nine_hold_and_the_number_is_nine`, both C-mutation tests that assert C2 stays green under another mutation, the two pinned-control-count names, `test_the_script_takes_its_cohort_as_an_argument`, and TASK-0220's own `test_the_preflight_rule_that_reads_it_is_one_of_the_queue_rules`. **14.**
* **M4** — `C4TheAuthorityResolvedAgainstAnotherTree.test_a_populated_queue_in_another_tree_is_unknown_with_both_paths`, `TheFourWorlds.test_the_four_worlds_this_cell_was_asked_about`, and TASK-0190's two `AnAuthorityOutsideTheTreeIsAHardRefusal` names. **4.**
* **M5** — all three `ThePassThatIsNotReachable` names, `test_the_ask_reads_the_decider_the_row_declares`, `test_controls_eight_and_nine_hold_and_the_number_is_nine`, the two pinned-control-count names and `test_the_script_takes_its_cohort_as_an_argument`. **8.**

`test_the_script_takes_its_cohort_as_an_argument` appears in three of the five
and is **not** collateral: it asserts
`canary_preflight.main(["--controls-only"]) == 0`, so it is the script's own
exit code reflecting a broken control. M2 and M4 do not break a control —
the controls plant into a temporary tree and pass `root=tmp`, so neither the
absent-gate nor `_inside` can move them — and that is why those two mutations
leave it green.

---

## 6. WHAT WAS NOT MEASURED

* **The full suite was not run.** No merge is proposed, so no merge gate
  applies. The measured reference is the six `src/preflight.py` modules:
  181 tests, zero failing names, at `c45fa20df` in this CRLF tree. A
  full-suite name-set claim would need a reference run on `a29391ee9` in the
  same tree as well — two suites, roughly 80 minutes — and is **NOT
  MEASURED**, not "clean".
* **Five failing names in two unrelated modules were checked and are
  pre-existing**, not caused by this change:
  `test_compare_bison.CompareBisonFailLeadCopy.test_alice_passes_when_only_bob_differs`,
  `test_compare_bison.CompareBisonPass.test_verdict_pass_when_everything_matches`,
  `test_threaded_sequence.ThreadedCampaignStaging.test_threaded_campaign_writes_subject_1_only`,
  `test_threaded_sequence.ThreadedCampaignStaging.test_threaded_campaign_clears_stale_subjects_on_existing_lead`,
  `test_threaded_sequence.VariablesForThreaded.test_all_bodies_are_written`.
  Measured by checking out `a29391ee9`'s `src/preflight.py`, running both
  modules — the **same five names, both directions** — restoring, and
  re-hashing to `7b2e5971bd6d8fda6b40d078a1bb4da0`. Neither module imports
  `src/preflight.py`; their "preflight" mentions are prose about the
  *activation* preflight, which is a different thing.
* **The 23-contact canary cell does not change in this tree**, and that is
  correct rather than a gap: the queue authority is ABSENT here, so
  `bounce_history` is UNKNOWN for all 23 before and after. The cell that moved
  is proven to move in a planted world and in `controls()`, which is the only
  way it can be shown without reading production `work/`.
* **The send path is untouched.** `channels._bounced` still answers `False`
  for a missing event and `channels.email_verdict` still clears the address on
  that `False`. TASK-0220's defect 4 and its §3 hazard are **OPEN**. This task
  changed what the preflight *reports*; it did not and must not change what
  `eligibility.must_not_contact` decides.

---

## 7. THE OPERATOR'S, NOT MINE

Step 4 of the brief. One item, and it is a refusal, so it is written down
rather than built.

**A send path that believes `channels._bounced`'s `False`.** The preflight
now refuses to call a missing bounce event a PASS. The send path still does
call it one, because `email_verdict` has two answers and no third. Making it
fail closed would be a **new refusal that stops a caller** — every contact
with no recorded bounce would become unsendable until the recorder's health
reaches a verdict, which is the whole estate. That is a gate change and an
operator decision, and `_STANDING-RULES.md` forbids me from taking it.

Recommended shape, for when it is taken: do not change `_bounced`. Give the
bounce recorder's failure a **reader** that reaches a verdict — the thing
`WHAT_WOULD_ANSWER["bounce_recorder"]` names — and let `email_verdict` consult
*that*, so the refusal fires when the recorder is known to be broken and not
when it is known to be working. A blanket fail-closed on a missing event
cannot tell those apart and would stop every send on the strength of a
condition nobody is measuring. Written into
`resonate-ops\LANE-suppression.md` and marked the operator's.
