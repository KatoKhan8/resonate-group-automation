# canary/0002 — THE 13 ASK FUNCTIONS: BUILT, AND PROVEN ON SYNTHETIC RECORDS

Lane: canary/0002, brief `queue/canary/RUNNING/0002-build-the-13-ask-functions.md`.
Date: 2026-10-18. Branch: `task-canary-0002-13-ask-functions-2026-10-18`. Base (the SHA audit/0001 measured):
`1ba54cdda541adee1a97e0401f0b3f678e1bbb3d`. Lane commits, in order:

| commit | what | key blobs (hash = bytes) |
|---|---|---|
| `fba139ceec362e37511f0793dbd76b8598daf7a3` | the 13 ask functions + the TASK-0250 fixture repair | `src/preflight.py` `237c92a552854751cebd991ab831d2f8d2481b7a` = 134632 B (LF; was `a3877f8b78e9b93616ff65a2b30f7c9aa77e8527` = 100,833 B); `tests/test_a_recorded_bounce_the_cell_could_not_report.py` `d5383412bb9883c80eed68418f7f72375c406601` = 26737 B (LF; 27,287 B CRLF on disk, the 550-line gap) |
| `6c978b7c17604054b97342f7077c85e871e025cf` | the control module: 3 arms × 13 rows + both other answers | `tests/test_canary_0002_the_13_ask_functions.py` `7b8c4a87500f7ca5fb3ce8be0ad3cdcbd073fd6f` = 40793 B |
| `fbc9e3ef246e5e0cd51c0c9fb89bde8061471d6b` | the operator's collapsed step: join + run | `scripts/preflight_join_and_run.py` `c687eae02b89be5ac69485abd0dd71b9993f7f9d` = 10095 B |

`src/preflight.py` is identical in all three commits, so every preflight.py
line number below holds at any of them. origin/master at write time:
`b1f290c847eb2500b7eb39987ac34f6d6a8d00d2`. **Every anchor in this file was re-derived by `grep -n`
at the lane HEAD on 2026-10-18 — audit/0001's table was the map, not the
evidence, and no line number here was inherited from it or from anywhere
else.**

## THE ONE QUESTION, ANSWERED

> For each of the 13, what is the function that returns a verdict from a
> record, and does it return the right verdict on synthetic records built
> to satisfy, to violate, and to be missing the field?

The function for row *N* is `_ask_<rule>(ctx)` in `src/preflight.py` (lines
in the table below), wired into its `RULES` slot. Each one goes THROUGH
its row's declared decider — never a re-implementation — and each is
composed the same way: **FAIL first** (an exclusion found on a partial
record is still an exclusion, evaluate()'s own fires-on-partial
asymmetry), **absence floor second** (`Undecided` → UNKNOWN: a missing
authority must never read as clearance), **PASS last** (only a PASS needs
every field present). Where one decider serves two rows, the rows split
its branches and each reads the other's branch as "did not fire", so no
exclusion can be lost between rows.

And yes: **13/13 return the right verdict on all three arms.** Measured,
not claimed — section "THE COUNT" below.

## DELIVERABLE 1 — THE 13, EACH WITH ITS AUTHORITY AND ANCHORS

| # | rule | ask fn @ preflight.py | RULES slot | the authority it consumes (decider @ file:line) | what it reads |
|---|---|---|---|---|---|
| 1 | client_suppressed_drop | `_ask_client_suppressed_drop` :887 | :1533 | `eligibility._suppressed` :342, drop_reason branch only (the ask passes an empty suppressed-set, so the domain branch is unreachable by construction) | `rec["drop_reason"]` |
| 2 | client_own_domain | `_ask_client_own_domain` :921 | :1538 | `eligibility._client_own_domain` :368 + `clients.load` (client yaml under CLIENTS_DIR) | `rec["client"]`, contact email, client domain |
| 3 | record_state | `_ask_record_state` :970 | :1544 | `eligibility._record_state` :393 + `lint.UNSHIPPABLE` :557 | `rec["state"]`, `rec["drop_reason"]` |
| 4 | contact_flags | `_ask_contact_flags` :996 | :1551 | `eligibility._replied` :448 FLAG branch, entry found via `_matched_record_entry` :849 (`lint.find_contact` :476, `dedupe.normalise_email` :85) | entry `unsubscribed`/`stopped`/`paused` |
| 5 | contact_reply_event | `_ask_contact_reply_event` :1029 | :1556 | `eligibility._replied` :448 EVENT branch (`events.is_reply` :340, `REPLY_TYPES` events.py :264) | `rec["events"]` vs contact key |
| 6 | account_suppressed | `_ask_account_suppressed` :1067 | :1561 | `eligibility._paused` :401 suppression branch (`BLOCKED_ACCOUNT_SUPPRESSED` :69) | `rec["suppression"]["unsubscribed"]` |
| 7 | account_review_open | `_ask_account_review_open` :1108 | :1566 | `eligibility._paused` :401 review branch (`BLOCKED_REVIEW_REQUIRED` :71) | `rec["review"]["open"]` |
| 8 | account_paused | `_ask_account_paused` :1136 | :1571 | `eligibility._paused` :401 cadence branch → `cadence.pause_state` :1091 (`accountpolicy.effects` :426) | `rec["paused"]`, `rec["events"]` (MEETING_MARKED :131), reply outcomes |
| 9 | account_reply_log | `_ask_account_reply_log` :1174 | :1576 | `account.replies` :149 (REPLY_RECEIVED :67 + REPLY_TYPES :264) | `rec["events"]` filtered by contact key |
| 10 | mx_and_verification | `_ask_mx_and_verification` :1216 | :1594 | `lint.policy_for_record` :436 + `lint.sendable` :418 (`verification.evidence_for` :196, `verification.decide` :345, `verification.resolve` :496) AND `mx.allows_email` :646 (`stored_decision` :620, `fresh_decision` :624) | entry `verification`, entry `mx` |
| 11 | hygiene_workspace_history | `_ask_hygiene_workspace_history` :1292 | :1602 | `hygiene.index` :214 over `store.load` :849, `hygiene._candidate_keys` :244, `hygiene._from_contact` :258, `hygiene.worst` :158 | the WHOLE queue, matched on strong identity only |
| 12 | hygiene_account_history | `_ask_hygiene_account_history` :1344 | :1607 | `hygiene.index` :214, `hygiene._from_account` :284, `hygiene.worst` :158, `dedupe.normalise_domain` :257 | the WHOLE queue, matched on domain |
| 13 | client_approval_register | `_ask_client_approval_register` :1398 | :1612 | `clientapproval.path` :127 / `load` :154 / `state_of` :164 / `is_suppressed` :193 | the register file beside the queue |

Row 13's register is NOT among the eight declared authorities, so
evaluate()'s five-state gate never sees it; the ask self-polices
ABSENT / UNREADABLE / EMPTY / POPULATED (stat before read — the SPEC
HAZARD audit/0001 named, `load()` → `[]` → `is_suppressed` False →
manufactured PASS, is the absent arm and is refused).

The only remaining `"ask": None` slots are the FOUR provider-read rows —
`hold_active_sequence` :1620, `hold_recent_touch` :1626,
`hold_total_sends` :1632, `cooling_90_days` :1639 — pinned by test
(`test_the_remaining_ask_none_rows_are_exactly_the_provider_rows`). The
wrapper's own count line renders `rules with no evaluable form at this
SHA: 0/23`.

## DELIVERABLE 2 — THE CODE, ON THE LANE BRANCH

`src/preflight.py` grew +691/−13 (one file): `_matched_record_entry` plus
the 13 asks, spliced byte-precisely between `_ask_bounce_history` and
`RULES`, and the 13 `"ask": None` slots filled by anchored regex, each
count=1. Verified by import at the time: 23 rules, 19 callable asks, all
13 slots wired to their own function. `preflight.controls()` UNCHANGED at
9/9 — no control, guard, gate, cap, assertion or client config was
touched anywhere in this lane.

One existing test module went red from the build and was repaired as a
FIXTURE, not an assertion: the TASK-0250 bounce module pinned
`excluded_by == ["bounce_history"]`, and its fixture contact carries no
verification evidence, so row 10's verification leg began excluding it
too — the WORLD was stale (row 10 answered UNKNOWN to everything when
that pin was written). `plant()` now makes the fixture address verified
and MX-allowed, rewritten INTO the queue authority and read back through
`store.read_jsonl`. Not one assertion touched; 21/21 green.

## DELIVERABLE 3 — THREE CONTROLS PER FUNCTION, ON SYNTHETIC RECORDS

`tests/test_canary_0002_the_13_ask_functions.py` — 51 tests, green first
run in 2.310s, run MODULE-ONLY (`py -3 -B -m unittest
tests.test_canary_0002_the_13_ask_functions`); no full-suite lock taken.
Worlds are planted by `preflight._planted_state` into a temp dir (the
eight authorities through their real writers), queue overwritten with
synthetic JSONL (reserved `.test` domains only, asserted on the module's
own bytes), QUEUE + CLIENTS_DIR env following the plant, and every cell
read through `evaluate()` itself under `_pointed(paths)` — gate,
needs_record floor and ask, never the ask called beside it.

The 39 core arms (per row: satisfies → PASS and NOT not_applicable;
violates → EXCLUDED with why-substring; absent → **assertEqual(UNKNOWN)
AND assertNotEqual(PASS)**, both halves pinned because the third arm is
the one that matters):

| # | rule | satisfies world | violates world | absent world |
|---|---|---|---|---|
| 1 | client_suppressed_drop | `drop_reason: None` | `drop_reason: "suppressed: client removal…"` | key deleted |
| 2 | client_own_domain | address not at client domain | address `insider@control-client.test` = the client's own domain | `client` key deleted |
| 3 | record_state | `state: "sourced"` | `state: "dropped"` | `state` key deleted |
| 4 | contact_flags | entry, no flags | entry `unsubscribed: True` | `contacts` key deleted |
| 5 | contact_reply_event | `events: []` present | `reply_received` event vs key | `events` key deleted |
| 6 | account_suppressed | `suppression: {"unsubscribed": False}` | `unsubscribed: True` | block never written |
| 7 | account_review_open | `review: {"open": False}` | `open: True` | block never written |
| 8 | account_paused | `paused: None` | `paused: {reason: positive_reply_hold…}` | field never written |
| 9 | account_reply_log | `events: []` present | `reply_classified` event vs key | `events` key deleted |
| 10 | mx_and_verification | 2 valid evidence bound to the address + google MX host | (a) no evidence; (b) `mx_records: []` no_mx | evidence valid, `mx` block absent |
| 11 | hygiene_workspace_history | unworked identity | same email, second record, `push_marked` | contact with NO strong identifier |
| 12 | hygiene_account_history | unworked company | different person, same domain, `push_marked` | contact with no domain |
| 13 | client_approval_register | register row `approved` | register row `suppressed` | register FILE absent (stat-verified) |

Seven extra arms pin the doctrines the build named: row 2 refuses to
inherit `_client_own_domain`'s fail-open (unreadable client config →
UNKNOWN); row 4 answers UNKNOWN — not a borrowed
`blocked:contact_not_on_record` — for a person not on the record, and
excludes on `stopped` as well as `unsubscribed`; row 8 EXCLUDES on a
MEETING_MARKED event with NO `paused` field at all (FAIL before the
floor); row 9's violates world asserts row 5 reads PASS in the SAME world
(`reply_classified` is in `account.replies`' set but not `events.is_reply`
— the branch split, asserted not claimed); row 10 pins BOTH halves of its
asymmetry (`verification.decide([])["sendable"] is False` cited beside
the cell; the absent-mx arm names `allows_email`'s "no MX check has been
run" fail-open being wrapped to UNKNOWN); row 13 pins PRESENT-EMPTY as
UNKNOWN too.

## THE INSTRUMENT SHOWN ABLE TO PRINT THE OTHER ANSWER — 13/13 EACH

A green cell proves nothing until the instrument has printed the other
one. Two mutation classes loop all 13 rows on the SAME satisfies registry
the arms proved:

* `ask: None` back in the slot — the exact defect audit/0001 measured —
  turns every satisfies world UNKNOWN again, for the gate's own reason
  ("no form that can be evaluated"). 13/13.
* An ask that refuses everybody — the subtler break that would pass every
  absent arm green — turns every satisfies world EXCLUDED. 13/13.

## DELIVERABLE 4 — THE COUNT

**Of 13, 13 return the correct verdict on all three arms.** Nothing is
short of 13/13, so there is nothing to name as short — and the count is
not rounded from anything: every arm is an individual assertion, and both
mutation loops append per row and assert the full `THE_THIRTEEN` list was
degraded and reddened.

## DELIVERABLE 5 — THE ONE COMMAND THAT POINTS THESE AT REAL `work/`

From the MAIN checkout (its `work/` is the production estate;
`store.queue_path()` is per-tree, and the script says loudly which tree
it read when it is not the main one):

```
cd C:\Users\Zvonimir\Desktop\resonate-group-automation
git fetch origin
git checkout task-canary-0002-13-ask-functions-2026-10-18
py -3 -B scripts\preflight_join_and_run.py --cohort C:\<absolute path to the cohort json> --no-addresses
```

`--cohort` takes the same JSON list of contacts `preflight_one_command.py`
always took (key/name/company/email/domain per contact); `record` is
optional — the join binds it. `--channel linkedin` and `--sha` pass
through. The joined cohort is written to `work\preflight-joined-cohort.json`
— under `work/`, gitignored, so real addresses and records never enter
git.

WHAT IT PRINTS: (1) a header naming the tree, the main checkout, and the
absolute queue path, with a WARNING if the tree is not the main checkout;
(2) the JOIN report — contacts / JOINED / NOT FOUND (each named, left
unbound so the 13 rows floor to UNKNOWN for it) / AMBIGUOUS (each named
with every matching record id, never bound — identity is proved, never
guessed) / rebound stale copies; (3) the fixed three-section table of
`preflight_one_command.py` unchanged — per-rule verdict, authority states
with record counts and paths, per-contact roll-up, summary with
denominators, provenance sha + CONFIRMED, controls 9/9 — and its closing
sentence; (4) exit 0 = every contact cleared, 1 = an exclusion fired,
2 = UNKNOWN / refusal / control failure / no contact / shape fault (2
outranks 1). Any join fault prints JOIN FAULT and exits 2 — never a
traceback, because an uncaught exception would exit 1 and a wrapper
crash must never read as a finding about a person.

Measured example (SYNTHETIC run from the lane worktree, planted
gitignored files only, one fully-satisfied control contact; the real run
differs only in whose data is read):

```
JOIN - cohort contacts bound to THIS tree's queue records
  contacts in cohort   1/1
  JOINED               1/1
  ...
SECTION 3 - SUMMARY (denominators always)
  contacts assessed            1/1
  rules asked                  23/23  (RULES at this SHA: 23; channel email)
  contact verdicts             CLEARED 0/1  NOT CLEARED (EXCLUDED) 0/1  NOT CLEARED (UNKNOWN) 1/1
  rule verdicts                REFUSED 0/23  NOT CLEARED 0/23  UNKNOWN 6/23  CLEARED 17/23  NOT CONSULTED 0/23
  authorities POPULATED        8/8  refusals: none
  controls OK                  9/9
  rules with no evaluable form at this SHA: 0/23; provider-read rules: 4/23
  exit 2  (0=every contact cleared, 1=an exclusion fired, 2=UNKNOWN/refusal/control failure/no contact/shape fault)

  CANARY-01 IS NOT CLEARED TO SEND on the email path: 0 cleared of 1; 1 NOT CLEARED because at least one rule could not be asked at all. UNKNOWN is not a pass.
```

All 13 record rows rendered CLEARED ("asked, did not fire") for that
contact, and the contact STILL reads NOT CLEARED (UNKNOWN),
`unknown_on=6/23`: the 4 provider-read rows, plus
`internal_campaign_membership` (the listing cannot prove it covered
campaign 274) and `bounce_history` (no bounce evidence is not evidence of
no bouncing). That is the honest table, and it is the point: **the join
makes the 13 rows answer; it does not make anybody cleared.** Smoke-proven
too: NOT FOUND named and floored; AMBIGUOUS (`matched 2 records: r-0002,
r-0003`) never bound; empty queue refused before any table; the
OUTSIDE_TREE hard refusal fires through the script when an authority
resolves outside the tree.

## DELIVERABLE 6 — THE OPERATOR-ONLY ROWS: WHAT COULD AND COULD NOT BE BUILT

All 13 rows were audit/0001's OPERATOR class (0 lane-closable / 13
operator / 0 provider-read), for one reason: their input — the queue
record and its contact entries — lives only in the main checkout's
gitignored `work/`, and a lane may not read production `work/`, touch the
main checkout, or resolve authorities outside its tree (the
OUTSIDE_TREE refusal above is that boundary, in code).

* BUILT FROM THE LANE (everything but the sight): the 13 functions
  through their declared deciders; the three-arm proof per function on
  synthetic records; both mutation proofs; the fixture repair; the join;
  the one command. The operator's step has collapsed from "build the
  functions" to "check out the branch, run one command, read the table".
* NOT BUILDABLE FROM THE LANE: a verdict about any real contact. No real
  record was read, no real address appears anywhere in this lane, and no
  claim about the production estate is made or implied. When the command
  runs for real, rows 5–9 will read UNKNOWN on records no policy path has
  worked (next section) — that is the instrument being honest about the
  estate, not a defect in the build.

## WHAT THIS LANE DOES NOT CLAIM — THE HONEST UNKNOWNS

* **No contact is cleared.** These functions produce verdicts; clearance
  is a separate judgement over the whole table and it is not this lane's
  to make.
* **WRITER-ADDED ABSENCE.** `events`, `suppression`, `review` and
  `paused` are created by their writers, and NO production writer writes
  `unsubscribed: False` or `open: False` back. Real records no policy
  path ever touched will therefore read UNKNOWN on rows 5–9 — never
  clear, never excluded. The rows' satisfies arms (present-and-false
  blocks) are SYNTHETIC-ONLY except row 8's `paused: None`, the one
  production negative (inbound's restore may write it). The consequence
  is named here rather than hidden, exactly as the brief required.
* **Row 10 is asymmetric by its deciders' own answers:** absent
  verification evidence EXCLUDES (`verification.decide([])` is
  not-sendable; CLAUDE.md hard rule — no email for an unverified
  address); absent MX block is UNKNOWN (wrapping `mx.allows_email`'s
  fail-open "(True, no MX check has been run)" — the only fail-open wrap
  among the 13, one-directional: it can never manufacture a PASS).
* **Row 13 asks `is_suppressed` only.** `clientapproval.require_approved`
  — the stricter SPEND-side gate — is declared by NO row of this table,
  and nobody should read the register row as covering spend approval.
  `BLOCKED_WRONG_RECORD` likewise has no row.
* **23/23 is NOT reachable by Monday and this report does not pretend
  otherwise.** The 4 provider-read rows stay UNKNOWN without a fully
  paginated EmailBison/HeyReach read, which this lane's boundaries
  forbid; even a fully-satisfied synthetic contact renders
  NOT CLEARED (UNKNOWN) while any row cannot be asked.
* **Pre-existing reds, named not fixed** (not this lane's work):
  `test_compare_bison` 2 names (`test_alice_passes_when_only_bob_differs`,
  `test_verdict_pass_when_everything_matches`), `test_threaded_sequence`
  3 names (`test_all_bodies_are_written`,
  `test_threaded_campaign_clears_stale_subjects_on_existing_lead`,
  `test_threaded_campaign_writes_subject_1_only`), and
  `test_fixture_hygiene`'s 5-name set — all with byte-identical name
  sets at the frozen detached baseline `1ba54cdda541adee1a97e0401f0b3f678e1bbb3d`. **ZERO NEW NAMES
  from this lane**, compared by sorted name set, never by count.

## VERIFICATION APPENDIX — MEASURED, NOT REMEMBERED

* Controls: `py -3 -B -m unittest tests.test_canary_0002_the_13_ask_functions`
  → Ran 51, OK, 2.310s, first run, module-only.
* Bounce module re-run after the new file: Ran 21, OK.
* `tests.test_fixture_hygiene` lane-vs-baseline: 5 failures each side,
  sorted name sets `cmp`-identical.
* Join-script smokes (synthetic, lane tree, gitignored plants only,
  cleanup verified): RUN A/B/C/D all exit 2 with the prints quoted above.
* Regression discipline: module-by-module sweep of all preflight-referencing
  test modules against the frozen detached baseline — no full-suite lock
  was taken at any point in this lane.
* Every hash above is printed with its byte count beside it; every SHA was
  filled into this file from `git rev-parse` / `git cat-file` output by
  script, never retyped.
