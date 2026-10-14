# GLM review queue — findings, 2026-10-14

## CROSS-LANE — route these five first

Each: the finding in one line with file:line, the repro in the next.

1. **pilotcaps lane** — the GateToken "sink" is not the sink: eight
   `bison.*` write calls bypass `perform` entirely
   (`src/bisonfactory.py:1820` set_limits, `:1853` set_schedule, `:1884`
   attach_senders, `:2467` update_lead, `:2476` create_lead, `:2571`
   attach_leads, `:2777` pause_campaign, plus `stop_lead` via leadstop's
   path; zero GateToken references under `src/providers/` at 41ee6589c).
   `git grep -n "bison\.\(set_limits\|set_schedule\|attach_senders\|pause_campaign\|create_lead\|update_lead\|attach_leads\|stop_lead\)" 41ee6589c -- src/bisonfactory.py && git grep -c GateToken 41ee6589c -- src/providers/ || echo "zero token refs in providers"`
2. **suppression lane** — `src/inbound.py:552-556` saves the store only
   when an outcome was "applied", which is structurally impossible for an
   unmatched reply, so computed safety holds are discarded in memory and no
   suppression row is ever written (last matched reply 2026-09-25).
   `sed -n '545,560p' src/inbound.py`
3. **suppression lane** — `src/agencydnc.py:123-126` `except ValueError:
   continue` on a corrupt line: a torn append not only loses its own row,
   the NEXT successful `add()` glues onto the torn line and loses that row
   too (measured; a written DNC is silently not suppressed).
   `cd wt-glm-review-2026-10-14 && py -3 ../../Desktop/resonate-ops/glm-review-2026-10-14/verify_sweep_1.py`
4. **copy lane** — three templates over the 90-word ceiling are rendered
   live by `scripts/stage_s7_copy.py:359-361` (angle_shift_champion 127,
   angle_shift_economic_buyer 122, rung3_economic_buyer 104), and no floor
   check exists anywhere (comparable_proof_short 42 vs contract floors
   45-60).  Repro = the render loop in section 1b below.
5. **review/guard lane** — `tests/test_no_write_happens_without_every_gate.py:965-975`
   asserts the test's OWN `Provider` spy refuses a dict: a fixture
   self-check that reads as a demonstration of the production write layer
   but demonstrates nothing about `providerwrites`.
   `sed -n '960,980p' tests/test_no_write_happens_without_every_gate.py`

---

Worktree `wt-glm-review-2026-10-14`, branch `task-glm-review-2026-10-14`.
Read-only on production code throughout; the only file written is
`tests/test_bisonfactory_find_or_create.py` (task 3's deliverable).
Branch pushed 2026-10-14 with the operator's authorisation (review branch
only, never master). Measurements live in
`Desktop/resonate-ops/glm-review-2026-10-14/` (outside git, survives the
worktree): `verify_sweep_1.py` (agencydnc + contamination repros),
`mutate_foc.py` (the four bisonfactory mutation demos), `debug_foc.py`,
extracted branch copies (`providerwrites-41ee6589c.py`,
`pilotcaps-41ee6589c.py`, `cadence-c60eb3006.py`,
`test-template-guard-c60eb3006.py`). Scratch worktrees
`wt-scratch-t999-review` (at c60eb3006) and `wt-scratch-skeleton` (at
19ca1a144) were used for cross-branch reads and are still present.

---

## 1. Adversarial review: template branch at c60eb3006

Branch `task-template-evidence-2026-10-12`. The acceptance suite passes and
the four acceptances in `docs/qwen-tasks/REVIEW/TASK-999-templates-stop-diagnosing-the-prospect.md`
were run. What they do not cover:

**1a. Eight of twelve email templates are invisible to every body check.**
`tests/test_a_template_does_not_diagnose_the-prospect.py`'s `_email_templates()`
(lines 113-124) walks only `cadence.STEPS` plus `variant_if_accepted` — five
email templates plus one variant. `cadence.TEMPLATES` ships twelve. The
`rung3_*`, `angle_shift_*` and `close_*` bodies are rendered only by
`_subject_groups()` for SUBJECTS, never for words or diagnoses. So the word
ceiling, the diagnosis matcher and the unbacked-offers matcher each watch
six templates and silently skip eight.

**1b. Three of the eight unwatched templates are over the 90-word ceiling
today.** Measured by rendering every template in `cadence.TEMPLATES` via
`cadence.expand_step` with a probe spec (the same render path the test's
`_render` uses for unattached templates) and counting with
`lint.countable_words` and raw `.split()`:

    angle_shift_champion        127 words (raw split 127)
    angle_shift_economic_buyer  122 (124 raw)
    rung3_economic_buyer        104 (106 raw)
    ceiling (writer contract max, em1/em3 upper bound)   90

These are not dead copy: `scripts/stage_s7_copy.py:359-361` renders exactly
`rung3_{persona}`, `angle_shift_{persona}`, `close_{persona}` (fields "3",
"4", "5") for batch-1, and `scripts/batch1_build.py:165-169` resolves them
per persona. `stage_s7_copy` lints only the SUBJECT (60 chars); no word
count runs anywhere on that path. The gate that exists
(`test_every_shipped_email_body_is_inside_the_ceiling`) cannot see them.

**1c. No floor anywhere.** `comparable_proof_short` renders 42 words; the
writer contract's per-step floors run 45-60 (em1 60, em2 45, em3 60, em4 45,
em5 45). Nothing asserts a minimum for any template — an under-length
opener would pass every check in the suite.

**1d. Acceptance command 4 (the "independent re-measure") has four gaps.**
It renders only the champion persona; it forces `accepted=False` so the
day-10 variant body is never re-measured under its own spec; it counts with
raw `.split()`, making it a second word authority beside
`lint.countable_words` (TASK-943 made the writer contract the one
authority); and it uses `ceil = max(...)` over all contract rows — a global
90 — rather than each step's own bounds.

Reproduce 1b (in the c60eb3006 worktree):

    py -3 - <<'EOF'
    from src import cadence, clients, lint
    cfg = clients.load("productive")
    rec = {"id":"m","domain":"x.invalid","client":"productive","company":"X",
           "lane":"cold","signal":"s","company_facts":{},"research":[],
           "contacts":[{"key":"k","name":"A B","persona":"champion",
             "title":"T","angle":"operations","primary":True,
             "email":"a@x.invalid"}],"events":[],"stages":{}}
    for name in cadence.TEMPLATES:
        step = cadence.expand_step(rec, rec["contacts"][0],
            {"key":"probe","day":5,"channel":"email","template":name},
            cfg, accepted=False) or {}
        body = step.get("body") or ""
        if body:
            print(f"{name:32s} countable={len(lint.countable_words(body)):4d} "
                  f"raw={len(body.split()):4d}")
    EOF

---

## 2. C11e disposition: SIMULATED_PATH_MODULES says 17, class D says 16

Measured on every branch that carries `src/sandboxclock.py`
(task-secondbrain-ablation-2026-10-12, task-sandbox-run-2026-10-12,
task-sandbox-phase2-horizon, task-template-evidence-2026-10-12 — identical
blobs) and on this tree's HEAD:

- The frozenset at `src/sandboxclock.py:271` names **17** modules (parsed
  by AST, not by grep: `call.args[0].elts`).
- **16 of 17 exist** in every tree checked. The one that does not is
  `suppression.py`.
- `git log --all --oneline -- src/suppression.py` is **empty**: the file
  was never added, never deleted, never existed in any commit. It is not a
  removed module; it is a ghost entry. No suppression-named module exists
  under `src/` in any ref.

**The 17 is the wrong number; the pre-registered 16 is right.**
`docs/decisions/PREREG-C11-wall-clock-2026-10-13.md:39` says class D is
"the 16 modules whose clock reads can change a horizon answer" — a module
that has never existed holds no clock reads, so it cannot be in that class,
and the measured membership of the list is exactly 16. The list drifted;
the criterion did not.

**Disposition, without touching the pre-registered criterion:**

1. C11e's LOADED-vs-EXECUTED enumeration should record a third state for a
   list member that cannot be imported — `MISSING` — counted as neither
   loaded nor executed, with the report carrying an explicit
   `ghosts: ["suppression.py"]` field (or exiting non-zero) so the
   discrepancy is visible rather than swallowed. LOADED alone satisfies
   nothing per the skeleton doc; MISSING satisfies less.
2. The one-line repair (delete the ghost from the frozenset) touches
   `src/sandboxclock.py` on a branch whose own test
   (`test_src_is_identical_to_the_fork_point`) requires an empty diff
   against the fork point under `src/` — it needs explicit authorization,
   and this document is the request for it.
3. `setdrift.py` (E section) consumes the list only as a filter over
   `unpatched_business_clock_reads`, so the ghost costs nothing there — it
   filters rows from a module that has no rows. The cost is to C11e's
   LOADED/EXECUTED bookkeeping, where 17 named minus 16 answerable is
   exactly the kind of silent skip the report exists to surface.

---

## 3. `bisonfactory._find_or_create` now has a test that goes red

Deliverable: `tests/test_bisonfactory_find_or_create.py` — seven tests,
all naming and calling `bisonfactory._find_or_create` directly (existing
coverage reached it only through `stage()`; the refusal branches had zero
assertions, and `docs/MERGE-REQUEST-2026-09-25` §9.3 records that disabling
the `bound` reuse made no test fail at the time).

Branches pinned: REUSE (bound + live), REFUSE-stale-binding,
REFUSE-pending-deletion, RECOVER-one-orphan, REFUSE-two-orphans,
CREATE-through-perform, REFUSE-no-id. Every test wraps the fake provider's
methods with counters armed AFTER fixture construction and asserts the
counter moved — a green run with a zero counter is impossible.

**Mutations demonstrated** (each applied to `src/bisonfactory.py` on disk,
test run, file restored; `git diff` verified empty afterwards):

| Mutation | Tests that went red |
|---|---|
| M1 orphan lookup stubbed to `[]` | one_orphan_recovered, two_orphans_ambiguity |
| M2 ambiguity guard `if len(orphans) > 1:` → `if False:` | two_orphans_ambiguity |
| M3 pending-deletion guard → `if False:` | pending_deletion_refused |
| M4 `bound` branch removed (`bound = None`) | live_bound_reused, stale_binding_refused, pending_deletion_refused |

M4 is the 09-25 mutation that used to be invisible; three tests catch it
now. Run: `py -3 -m unittest tests.test_bisonfactory_find_or_create -v`
(7 tests, OK, ~0.2s, fake transport only).

---

## 4. actionledger two-calendar check — closed (prior report)

actionledger has no `day` field at all: every writer writes `at`
(`store.now()`, UTC, `src/store.py:232-233`) and every reader derives the
day from `at` (`_day` at `src/actionledger.py:124-125`). Production file:
136/136 rows carry `at`, 0 carry `day`. executionguard reads the same UTC
clock (`src/executionguard.py:710` + `_utcnow` at 211-212) — **same clock,
no CROSS-LANE flag** for the 1000/2000 ceiling. Reader-clock inventory
(one writer, N readers): `actionledger.reserve` (same string) ✓,
`executionguard` ✓, `seatledger.daily` (forwards the same day) ✓,
`main --day` (human-supplied) —, and **one mismatched reader**:
`scripts/qa/check_campaign_heyreach.py:455` → `_today_iso()` at 109-110
uses `datetime.date.today()` — LOCAL date, off by the UTC offset window
(00:00-02:00 local at UTC+2). It undercounts, so a seat reads as
under-cap. It gates the QA report, not the reserve-time cap.

---

## 5. Adversarial review: GateToken / grant design at 41ee6589c

Branch `task-pilotcaps-enforcer-2026-10-14` at 41ee6589c (reviewed from an
extracted copy verified byte-identical to the commit). Headline findings,
most severe first; F1/F2/F3 verified by direct grep/read of the commit:

**F1 — the sink is not the sink (verified).** `GateToken`'s docstring
claims gating "AT THE SINK... the thirteenth script is refused too", but
`src/providers/bison.py` and `src/providers/heyreach.py` at 41ee6589c
contain **zero** references to GateToken (measured: `git grep -c GateToken
41ee6589c -- src/providers/` → no matches), and `src/bisonfactory.py`
calls the write transports directly: `bison.set_limits` (:1820),
`bison.set_schedule` (:1853), `bison.attach_senders` (:1884),
`bison.update_lead` (:2467), `bison.create_lead` (:2476),
`bison.attach_leads` (:2571), `bison.pause_campaign` (:2777) — the last is
the verb CLAUDE.md says needs the operator's explicit APPROVED. A caller
`from src.providers import bison; bison.pause_campaign(327)` reaches an
internal campaign with no token anywhere. The nine gated call sites are
real but they are nine of seventeen doors.

**F2 — the token is forgeable (verified by read).** `GateToken.__init__`
sets three plain attributes; the write site checks only
`isinstance(gate, GateToken)` and `gate.operation == operation`.
`grant()`'s validation (by/why non-empty) exists only at mint time and is
never re-run — `GateToken(EMAIL_PAUSE, "", "")` passes the sink check.

**F3 — the audit trail is dropped (verified by read).** The docstring
justifies the gate with "it cannot write without writing down who granted
it and why"; in fact `_ledger` records `kw.get("by")`, which defaults to
`"system"` and is disconnected from `gate.by`; `gate.why` reaches no
durable store, and `grant()` itself writes no ledger row. One-line fix:
`by=gate.by if gate else kw.get("by")` in `_ledger`.

**F4 — no scope, no expiry, no spend.** A token binds only an operation
string; one grant in a module global authorises unlimited pauses of every
campaign forever. Honest per the docstring ("not a permission system"),
but combined with F2 the token contributes a type check.

**F5 — the transport is unbound.** Everything is validated
(`operation`, `provider_campaign_id`, `campaign`) and then an arbitrary
caller-injected callable writes: `transport=lambda p:
bison.pause_campaign(327)` passes every check naming 487. The facing
branch has `_require_approved_words` binding payload to authorization; the
non-facing branch has no analogue.

**F6 — `EMAIL_RESUME` is classified non-facing**, so restarting a paused
sequence in front of real people sits behind the weak token with no
operator-approval representation (the 2026-09-29 executionscope requirement
was reverted, documented in-file at 1415-1426).

**F7 — `_resume_revalidates_suppression` fails open on unresolvable
records** (`rec = store.get(rid); if rec is None: continue`, 1466-1468):
their contacts are never checked for suppression.

**F8 — `INTERNAL_CAMPAIGNS` env var can neutralize the operator's
internal-campaign declaration** (missing file reads as empty declaration,
1964-2028): the control that outranks the ledger goes quiet with no error.

**F9 — `_list_is_ours_and_unbound_and_holds_approved` never checks "holds
approved leads"** (1089-1139): the third promised check does not exist;
the live permission for a SUPPORTED verb is weaker than its name.

Also noted: `CONDITIONAL`-absence passes (unlike OPERATIONS/SUPPORTED
absence, which refuse); `_provider_key` crashes fail-closed on
"nan"/"inf"; the pilotcaps companion has `require(plan, not_checking=...)`
accepting unverified free-text "who enforces it" values, `enabled()` off
switch, and `asked=None` treated as not-a-breach.

Properly guarded (checked): the in-file `_perform` chain itself — gate
None default refuses, isinstance + operation equality unconditional and
first, no early return skips them; ownership default-refuse on both
branches; post-write discipline (transport exception → WriteUnverified,
never retried); the nine real grant sites all route through `perform` with
real tokens.

---

## 6/7. The sweep: controls that cannot fail

Shape hunted: pass-by-absence, empty set, swallowed exception,
filtered-to-nothing, default=allow, format-coupled parsing of own output.
The test_invariants allowlist is FIXED on `task-guard-scope-is-relative`
(not re-found). Ranked, verified-by-me first:

**S1. `scripts/qa/check_reconcile.py` rule 2 — the reply/bounce
reconciliation rule is VACUOUS every run (format-coupled; widest blast
radius).** `_extract_event_type` (:451), `_extract_lead_id` (:485),
`_extract_campaign_id` (:500) read an envelope EmailBison never sends
(`payload.type` / `payload.lead_id`; the real shape, measured 2026-09-17
and documented in `src/bisonevents.py`, is
`payload.event.type` / `payload.data.lead.id`), and
`RELEVANT_EVENT_TYPES` (:72-79) holds lowercase `replied`/`bounced` that
never match the provider's `LEAD_REPLIED`/`EMAIL_BOUNCED`. Triple
independent mismatch → `relevant == []` → `subjects == 0` → verdict ladder
(read and confirmed: `subjects == 0 → VACUOUS`) → the rule named for the
"912 provider sends vs 1 recorded touch" incident class reports VACUOUS
forever. Zero test coverage on the extractors. In-memory demo run this
session: real-shaped row → `unknown / None / None / not relevant`.

**S1b. Same file, `_build_store_event_index` (:543)** — reader asks
`contact_key`, the same file's own writers (:187 etc.) and `src/events.py`
write `contact`, so the guard `and contact_key` is always falsy and every
contact's event matches every contact. Latent behind S1.

**S2. `src/agencydnc.py:123-126` — a torn append suppresses nobody
(MEASURED).** `except ValueError: continue` on a corrupt line, in a
do-not-contact registry, where the safe direction is the opposite. Repro
(`Desktop/resonate-ops/glm-review-2026-10-14/verify_sweep_1.py`): valid
row + truncated final
line → `load()` sees 1 of 2; the NEXT successful `add()` glues onto the
torn line (no newline) → even the new row is lost — `lookup(c)` → None
for a row written by a successful call. `add()` (:156) is a plain append
with no fsync/atomic replace, so a crash or disk-full mid-write is the
producer. The repo's own `providerwrites._parse_declared` raises on one
malformed line for exactly this reason. No corrupt-line test exists.

**S3. `src/contamination.py:61-65` — an unreadable state file reads as
clean (MEASURED).** `except OSError: return False` in `proven()` → entry
dropped → `check()` prints `ok: True, "no state file is holding known test
fixtures"` while the file sits unreadable (demo: path replaced by a
directory). Violates invariant 0 verbatim; the failure arms precisely when
something is already wrong (Windows sharing violation during the
temp-file-and-replace the registry itself documents for replywatch.json).

**S4. `scripts/glm_verify_branch.py:545-588` — a crashed test run parses
as zero failures (read-confirmed).** `result.returncode` is never
inspected; `failing` is built only from `line.startswith(("FAIL: ",
"ERROR: "))` after strip. A hard kill, OOM, or import-time death prints no
summary block → `failing = set()`, `error = None` → "Failing tests: 0
total, 0 new" about a run that never finished → the GLM merge gate
evaluates on a false green. (Same file: `_parse_verdict` (:839) takes the
FIRST `VERDICT:` line, so a review quoting an earlier verdict before its
own reads as that earlier verdict — FAIL→PASS one quoted paragraph away.)

**S5. `src/campaignqa.py:141-143` — the copy-QA section cancels itself
(read-confirmed).** `sample = next((r for r in (recs or []) if
r.get("contacts")), None); if sample is None: return out` — with no
contact-bearing record (a campaign reviewed before people-discovery), the
variants structural checks, the no-experiment WARNs and the per-variant
lint that emits BLOCK SAFETY findings all vanish, while `_structure` and
`_safety` in the same file convert cannot-check into explicit findings.
`_variants` alone converts it into silence.

**S6. `scripts/durable_state.py:247` — git()-swallow makes
`master_pushed: true` (read-confirmed).** `git()` (:52-58) returns `""`
on any exception; `git("rev-parse","master") == git("rev-parse",
"origin/master")` → `"" == ""` → True. A git that fails both ways is
reported as pushed — the durability alarm (`return 1 if unpushed or
dirty`) silenced on exactly the failure it exists to catch. Same class as
the recorded suitelock lesson ("a swallowed read error became a false
'the lock is free'").

**S7. `src/coherence.py:254-258` — a missing eligibility key means
"allowed" (latent ~60%).** `allowed = channel_verdict.get(f"{channel}_eligible");
if allowed is not False: continue` — absent key, or a string `"false"`,
exempts every step from the BLOCK-severity ineligible-channel check. Today's
producers populate both keys; `mx._decision` already sets only
`email_eligible`, so one refactor away.

**S8. `src/killswitch.py:99-107` — global layer proves "cannot send" by
`hasattr` (weak).** Class defined while the raise is removed/moved keeps
`sending: False, refused_in_code: True` on the operator's screen.
`tests/test_push.py:50` calls the real `push.run(live=True)` and would
catch it — the instrument, not the enforcement.

Agent-reported, shape spotted, not independently measured (queued for
verification): `check_reconcile` rule-1 PASS-on-unverifiable arithmetic;
`hard_stop_check` 0-read exit 0; `check_readback` summary reads `offenders`
which no rule writes (counts lie, verdict right); `history_pii_scan`
0-blobs CLEAN; `task173_scan`/`task_registry_scan` empty-set exits;
`glm_review._script` hasattr filter; `suite_baseline` truncated `--full-log`
→ zero-name baseline; `register_lint` heading regex; `test_audit.py`
relative `os.walk("src")`; real-CSV test gated on a gitignored path;
explorer filter tests with no non-empty pin; simulator CSV-injection
unpinned.

---

## 8. Reverse-test matrix — PARTIAL

**Correction, 2026-10-14 (operator):** the matrix below was built against
a Tier 1 = 20 / Tier 2 = 10 inventory. The corrected inventory is
**Tier 1 = 36 / Tier 2 = 9**, so the matrix covers **22 of 45** controls.
It is PARTIAL, not done; the 23 uncovered controls are unenumerated here
and the UNPROVEN/DEMONSTRATED verdicts below apply only to the 22 covered.

The covered set was assembled from the repo's declared control list
(CLAUDE.md's "outrank every preference" set + the two 2026-10-01 permanent
rules + the executionguard gate stack; no separate "Tier 1/2" scheme
exists in the repo). Verdicts over that covered set:

- **DEMONSTRATED (13):** killswitch layers; ownership classifier /
  UNKNOWN-never-passes; pre-send recheck; readback gate; approval gates;
  volume caps / pilot ceilings; action-ledger caps / exactly-once;
  action-path tenancy; suppression-on-send-path; claim licensing; spend
  ceilings; stoppability declaration; sender attribution.
- **UNPROVEN (9):** no-live-action restriction (16 refusal tests, removal
  experiment only offline); provider route/verb allowlist door; repo
  tenancy write guard; RBAC; canonical identity; DNC; positive-reply
  protection; double verification; waterfall ledger completeness.
- **ABSENT (0).**

Near-misses recorded: `test_no_write_happens_without_every_gate.py:965-975`
asserts the test's own spy refuses — a fixture self-check read as a
demonstration; the killswitch GLOBAL `refused_in_code` hasattr (see S8).
The repo's offline `tools/mutation_audit.py` corroborates most UNPROVEN
rows would be caught — corroboration, not in-suite proof.

---

## 9. Simulator timeline diagnosis — closed

`simulator_timeline_matches_cadence: false` because the two sides compare
disjoint step-KEY vocabularies. `src/simulator.py:60` walks the module
constant `cadence.STEPS` (7 steps keyed `day1..day21` — the retired
email-led shape, kept in `src/cadencelibrary.py:389-391` as "the shape
that ran before"), while `cadence.build` resolves the client's library
sequence — `config/clients/productive.yaml:313` names
`productive_li_heavy_v1`, ten steps keyed `li1..li5, em1..em5`. The
simulator's lookup misses on all seven keys and mints `not_planned` rows;
the comparison in `scripts/sandbox_run.py:1390-1395` is sorted-key-sets
only. Reproduced twice offline by the agent with synthetic `.invalid`
records. The +5-day buyer track is real but irrelevant to this check (it
shifts days, not keys). **The simulator is the wrong side**: it renders
the retired default for every client. Secondary: `expand_step` returns
None for a generated step with no stored copy, so even with matching keys
a bare record builds 5 of 10 keys.

## 10. Reply-ingestion diagnosis — closed

Chain walked end to end against live state (main checkout's `work/`,
process table, Task Scheduler). Source/fetch/classify ALIVE (poller pid
29528, heartbeat current, both providers polled OK). **First dead link:
the WRITE link for unattributed replies.** Every inbound reply since
2026-09-25 resolves to `events.apply` → `"unmatched"` (nothing of ours is
in sequence; internal campaigns' people are not records), and
`src/inbound.py:552-556` saves the store only when an outcome was
"applied" — so the safety holds computed in `handle()` (:396-403) are
discarded in memory, `replies.apply` is unreachable by construction, and
no suppression or hygiene row is ever written. The 2026-10-01 rule
(internal campaigns' negative replies → local suppression/touch ledger)
has no writer anywhere: branch `task-internal-campaign-learnings`
(ef2448b5d, unmerged) adds a 610-line measurement document and zero code.
Second dead link: the only durable output — notification rows — stopped
draining 2026-10-03 when `notify_deliver_loop` died with its supervisor
(43 planned rows undelivered in the last 24h; no scheduler entry exists;
everything alive today is an orphan a reboot kills). Latent, noted en
passant: `_positively_not_ours` (`src/inbound.py:168-174`) compares
EmailBison `external_campaign_id` against a HeyReach id allowlist — a
cross-provider id-space collision waiting on the ownership readback's
24-hour staleness window.
