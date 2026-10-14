# GLM lane B — adversarial review of `src/suppression.py`, and the second list

Written 2026-10-14, GLM lane B, worktree `wt-glm-b-2026-10-14`, branch
`task-glm-b-2026-10-14`, based on `origin/master` `2bf7b8a57`.

**What was reviewed.** The suppression lane's tree as it stands, which is two
states at once and this report keeps them apart:

* **committed** on `task-suppression-2026-10-14` (`e77938697`): `src/suppression.py`
  (new, 354 lines), `src/executionguard.py`, `src/providerwrites.py`,
  `src/agencydnc.py`, `docs/SUPPRESSION-MEASUREMENT-2026-10-14.md`, two test files;
* **uncommitted in `wt-suppression-2026-10-14`** (read as files on disk):
  `src/bisonfactory.py` (`_refuse_suppressed_leads`, +76), `src/inbound.py`
  (the B2 reply-write fix, +41), further test and doc growth.

Every finding below names which state it is in. Read-only throughout; the only
Python executed against their tree ran `suppression.decide` on plain dicts.

Method: read the module end to end, then every consult site, then the owners it
consults (`eligibility`, `account`, `ingest`, `agencydnc`, `operatorexclusion`),
then the door (`providerwrites`) and the guard (`executionguard`), then the
send-enabling scripts. Every claimed defect was reproduced by running the module
before it was written down; the repro commands are inline and re-runnable from
`wt-suppression-2026-10-14`'s root.

---

## TASK 1 — the module, attacked

### 1.0 The design claims, tested rather than accepted

| Claim | Verdict |
|---|---|
| one consulted entry point, no fourth copy | **True for BLOCK, false in spirit** — `decide` is the one implementation, but the HOLD half of it has no caller at all (§1.1) |
| three-valued verdict ALLOW/HOLD/BLOCK | **True** — and `_verdict` is the only place one is built, so every exit is recorded |
| `UNKNOWN_IS_NOT_A_PASS` with an explicit reason | **Holds at exactly one branch** — the absent-`provider_touches` branch. Everywhere else unknown silently becomes ALLOW or is skipped (§1.3) |
| thresholds from config, not constants | **True** — `thresholds()` resolves per call, tests cover override and defaults |
| `consultations()` proves the module was asked | **True and good** — records ALLOWs too, not just refusals; but the record is scope-blind, which costs it more than it first appears (§1.6 S1) |

### 1.1 Q1 — can you reach a send without passing it? Yes, four ways

First, the structure. `executionguard.revalidate` — where the suppression
consult lives — has exactly ONE production caller: `providerwrites._perform`
line 2581, and only on the `if facing:` branch. So suppression is consulted
exactly where a **prospect-facing verb goes through the door**. Everything else
is a way around:

**(a) Direct transports that bypass the door entirely.** The door's own
docstring (providerwrites.py:4-14) names eight `bisonfactory` writes that never
pass `perform`: `set_limits`, `set_schedule`, `attach_senders`,
`ensure_custom_variables`, `create_lead`, `attach_leads`, `update_lead`,
`pause_campaign`. Two of those put a person in front of the provider's
scheduler (`create_lead`, `attach_leads`); the uncommitted
`_refuse_suppressed_leads` (bisonfactory.py:2497, called as the last gate
before the first lead write) closes exactly that pair, at `SCOPE_SEND`. The
other six carry no person question, which is defensible for `set_limits` or
`pause_campaign` (campaign-level) — but `attach_senders` and `set_schedule`
are what make a campaign holding people able to send at all, and neither asks
anything about the people already in it.

**(b) Scripts that call the transport bare.** `scripts/batch_activate.py:144`
calls `bison.resume_campaign(provider_id, expect_leads=leads)` directly, inside
`providers.allow_writes(...)`. It carries the transport's `expect_leads`
readback and an operator-authorization banner, but it does not pass `perform`,
so it gets no action-ledger row, no `revalidate`, and no
`CONDITIONAL[EMAIL_RESUME]` — the one predicate whose entire job is
`_resume_revalidates_suppression`. This script is the thing that activated
491-498 on 2026-09-22; it is still runnable with `--live`. A resume of a
campaign holding a suppressed contact through this script consults suppression
nowhere. `scripts/resume_487.py:269` is the same shape (its grant is spent, but
the code path is live).

**(c) Non-facing verbs through the door skip `revalidate` by construction.**
`LINKEDIN_ADD_LEAD_TO_LIST` (SUPPORTED, not facing) stages a person into a
HeyReach list with `assert_list_safe` proving the list is unbound — and no
suppression consult anywhere. The list is one bind away from being an audience:
`LINKEDIN_CREATE_CAMPAIGN` binds `linkedInUserListId` at creation, and its
CONDITIONAL — `_list_is_ours_and_unbound_and_holds_approved`
(providerwrites.py:1089) — **checks "ours" and "unbound" and never checks
"holds approved"**, despite the name and despite `OPERATIONS` claiming "holding
only approved leads, all read live" (providerwrites.py:626-630). The function
returns `True` at the tenant-readability step. So the LinkedIn route to a
person is: add a suppressed lead to a list (no consult) → create a campaign on
that list (condition does not look at the leads) → activate (facing; consults
suppression for **the contact named on the activation token only**, not the
campaign's audience). Today the blast radius is bounded by
`_is_the_authorized_linkedin_canary` refusing every campaign but 604869 — the
pattern, not the number, is the finding. This is pre-existing master behaviour,
not the suppression lane's diff, but it answers this task's question.

**(d) The HOLD rules have no caller at all.** Grep across their whole tree:
every `suppression.decide` call in `src/` passes `scope=SCOPE_SEND`
(bisonfactory.py:2054, executionguard.py:1071, providerwrites.py:1482). **No
production code and no test calls `SCOPE_ENROL`.** `suppression.require` has
zero callers anywhere. At `SCOPE_SEND` the holds are skipped by design, so as
this branch stands the active-sequence, recency and volume rules — and the
headline `hold:provider_touch_history_unknown` — execute only when somebody
types them into a REPL. This is the repository's recurring defect in the exact
shape CLAUDE.md names: a thing computed correctly that nothing downstream
reads. The lane's own §7.4 says "in practice every enrolment decision today
answers HOLD on `hold:provider_touch_history_unknown`" — that sentence
overstates: there is no enrolment decision today. Nothing answers.

### 1.1a — send-path enumeration

Two independent traces (email, LinkedIn) over the suppression lane's tree,
verified against the door's own admission (providerwrites.py:4-14) and against
the pilotcaps denominator the lane quotes (58 write paths, 32 through the
door, 26 not — my count of call sites lands at 60/32/28; the 32-through
matches exactly, the residue differs by counting unit: call sites vs paths).

**Counts.** Email: 26 production write call sites, 13 through `perform`, 13
bypassing. LinkedIn: 34 sites, 19 through, 15 bypassing. **Suppression is
consulted on exactly three live paths in the whole system:** email activation
through the door (`revalidate`), email resume through the door
(`CONDITIONAL[EMAIL_RESUME]`), and email lead staging
(`_refuse_suppressed_leads`). On LinkedIn, the only consult is activation via
the door; `heyreach.add_lead` is resealed and `heyreachfactory.ensure_leads`
has no production caller, so nothing else even reaches the question.

**Email paths to a send** (P = prospect-facing):

| Path | Adapter write | Through door | Consults suppression | P |
|---|---|---|---|---|
| Activate/resume campaign holding leads | `resume_campaign` via `perform(EMAIL_ACTIVATE)` — activate_us_cohort_campaign.py:333, activate_control_campaign_v3.py:261 (Authorization minted) | yes | **yes, twice** (mint gate 4 + revalidate) | yes |
| Resume via web/orchestrator | `perform(EMAIL_RESUME)` — orchestrator.py:681 ← web/api.py:3223 | yes | **yes** (`_resume_revalidates_suppression`) | yes |
| Stage leads (create/update/attach) | `create_lead`/`update_lead`/`attach_leads` direct — bisonfactory.py:2534/2543/2601/2638 | no | **yes** (`_refuse_suppressed_leads` at 2497) | yes |
| Attach senders (makes sending possible) | `attach_senders` direct — bisonfactory.py:1879; via door — activate_control_campaign.py:192, attach_sender_to_487.py:174 | mixed | **no** — and the factory's runs before the lead consult | yes |
| Sequence, limits, schedule, variables, pause, stop | various | mixed | no (copy/cap/protective) | no |
| `perform(EMAIL_ACTIVATE)` with no Authorization | nudge_487_scheduler.py:127, activate_control_campaign.py:220 | door | dies at the door (facing op demands a token) | — |
| **Resume via script, bare** | `bison.resume_campaign` direct — **batch_activate.py:144** (activated 491-498, still `--live`-runnable), **resume_487.py:269** (grant spent, code live) | **no** | **no — no door, no CONDITIONAL, no revalidate; only adapter-internal `reviewapproval.require` + `expect_leads`** | **yes** |

**LinkedIn paths to a send:**

| Path | Adapter write | Through door | Consults suppression | P |
|---|---|---|---|---|
| Activate campaign holding leads | `perform(LINKEDIN_ACTIVATE)` — activate_linkedin_canary/cohort/cohort_b (Authorization minted) | yes | **yes** (revalidate, for the token's contact) | yes |
| Add lead to campaign | `perform(LINKEDIN_ADD_LEAD)` — heyreachfactory.py:1482 | yes (but verb resealed; `ensure_leads` has no production caller) | would, via revalidate | yes |
| Stage lead to list → create campaign on it → activate | `perform(LINKEDIN_ADD_LEAD_TO_LIST)` liststaging.py:323; `perform(LINKEDIN_CREATE_CAMPAIGN)` (condition never checks the leads, §1.1c) | yes | **no, at either step** | becomes yes at bind |
| **Activate 33 batch campaigns via script** | `heyreach.activate_campaign` direct — **linkedin_activate.py:157,160**, self-opened `allow_writes` | **no** | **no** | **yes** |
| batch_linkedin_push.py:485-505 (list+leads+campaign+sequence), batch_linkedin_reconcile.py:112, write_linkedin_lead_variables.py:161, probe/task158 scripts | direct | **no** | **no** (push has "no eligibility/suppression/collision gate" — the agent's words, verified against the factory's gate list) | mixed |

**Two cross-cutting findings the enumeration surfaced:**

* **The stop path — suppression's enforcement arm — is inert for the LinkedIn
  estate that actually exists.** `contact["heyreach_lead_id"]` is written only
  by the door-mediated `heyreachfactory._remember_linkedin_lead`
  (heyreachfactory.py:1052), which has no production caller; the 33 batch
  campaigns were enrolled by `batch_linkedin_push.py` (bypass), which writes
  `campaign_id_linkedin`/`linkedin_list_id` (524-525) but never the lead id.
  `leadstop.stop_linkedin_contact` refuses a contact with no
  `heyreach_lead_id` (leadstop.py:154) and `sweep` skips them — so a BLOCK
  verdict on any of those leads cannot be executed per-lead by code. The
  cross-channel stop that was measured live (7.7 minutes) holds only for leads
  this system enrolled through the front door, which is none of the LinkedIn
  estate. A suppression verdict that cannot be enforced at the provider is a
  report, not a control — and nobody is reading the report.
* **Scripts self-authorize at the transport layer.** Below the door sits
  `providers.refuse_unauthorized_write` (providers/__init__.py:769): any
  prospect-facing POST is refused unless the process opened
  `providers.allow_writes(...)` or exported `RESONATE_PROVIDER_WRITES=1`.
  That guard is why the bypasses are not wide open — but the bypassing scripts
  open the scope THEMSELVES (batch_activate.py:138, linkedin_activate.py:151,
  batch_linkedin_push.py:464), so the transport guard checks only that the
  script said please. It is a lock on the same keyring as the door.

Noted in passing (drift, not write paths): `src/web/api.py:3155`'s pause
docstring still claims "IT DOES NOT REACH THE PROVIDER" while its chain runs
`perform(EMAIL_PAUSE)` to the provider, and the audit row hardcodes
`provider_stopped: False`.

### 1.2 Q2 — where it answers ALLOW on absence

Each with the input that produces it. All verified by execution; run from
`wt-suppression-2026-10-14`'s root.

```python
py -3 -c "import sys; sys.path.insert(0,'.'); from src import suppression as s
REC={'id':'r1','domain':'prospect.test','contacts':[],'events':[]}
C={'key':'c1','email':'jane@prospect.test'}
print(s.decide(REC,C,now='2026-10-14T00:00:00+00:00',provider_touches={'total_sends':0}))"
```

* **A1 — a partial `provider_touches` dict passes.** `{"total_sends": 0}`
  answers **ALLOW** while `last_touch_at` and `active_sequence` were never
  supplied. The three fields are treated asymmetrically: a missing
  `total_sends` is UNKNOWN (holds), a missing `last_touch_at` is "never
  touched" (passes), a missing `active_sequence` is "not in one" (passes). The
  docstring says passing `{}` "is not a way to say 'no touches'" — but
  `{"total_sends": 0}` is a way to say it that the code cannot tell from a
  caller who forgot two-thirds of the truth. Same hole one level up:
  `{"last_touch_at": "2026-01-01T00:00:00Z", "total_sends": 50}` (cooled,
  volume high, `active_sequence` ABSENT) → **ALLOW** — the active-sequence
  question was never asked. *suppression.py:315-344.*

* **A2 — a type-confused `total_sends` silently disables the volume hold.**
  With a last touch 74 days old (past the 30-day hold, inside the 90-day
  cooling) and `total_sends=50`: int → `hold:total_sends_above_threshold`;
  `"50"` (string), `50.0` (float), `True` (bool) → **ALLOW**, and no
  `hold:provider_touch_history_unknown` either, because the value is not
  `None`. The guard at suppression.py:337-339 recognises exactly one unreadable
  spelling of a number. This is an `UNKNOWN_IS_NOT_A_PASS` violation inside the
  module's own hold block: unreadable volume reads as fine.

* **A3 — a naive `now` is silently replaced by the wall clock.** `_parse`'s
  own docstring (suppression.py:209) says "a naive stamp is unreadable, not
  assumed UTC" — but `_now` (suppression.py:220-223) takes a naive
  `datetime`, ignores it, and evaluates against the real clock. Repro:
  `now=datetime.datetime(2026,9,20)` (naive) with `last_touch_at` 2026-08-25
  answers **ALLOW**, while the same call with the aware spelling
  `"2026-09-20T00:00:00+00:00"` answers `hold:last_touch_within_window`. An
  intended HOLD became ALLOW because a caller's clock input was unreadable and
  the module substituted a default. Tests that freeze time naively will pass or
  fail with the season. The same branch has a second input spelling, found on
  the second pass and verified: `now="not-a-timestamp"` (any unparseable
  STRING) also falls to the wall clock via `_parse(now) or datetime.now(...)`
  — same last touch, `now="2026-09-10T00:00:00+00:00"` →
  `hold:last_touch_within_window` (16 days), `now="garbage"` → ALLOW against
  the real clock (50.9 days).

* **A4 — nobody at all is ALLOW at the send scope.**
  `decide(None, None, scope=SCOPE_SEND)` → **ALLOW**, zero reasons. No live
  caller feeds it empties (revalidate refuses a missing record;
  `_refuse_suppressed_leads` refuses a lead naming nobody), but the module
  accepts `rec=None, contact=None` and answers the question "may we contact
  this person" about no person with "yes". The shape a fourth caller could trip
  on; the `Verdict` class exists precisely because "a caller must not be able
  to hand the write layer something shaped like a pass" (suppression.py:166-169)
  — this is the module handing itself one.

* **A5 — the `agency` argument is accepted and never read.**
  `decide(rec, contact, agency=X)` runs the agency DNC through
  `agencydnc.lookup(contact, index=None)`, i.e. loads the default index from
  disk; the caller's `X` is dropped on the floor (suppression.py:253-254
  accepts it; the body never mentions it). Verified by passing an object whose
  every attribute access raises — no exception, verdict computed. The real list
  is still consulted, so this is not an ALLOW hole today; it is a dead
  parameter whose silence will bite the first caller (or test) that supplies a
  specific index and believes it was used.

* **A6 — the two batch consults disagree about a person who cannot be found.**
  `_resume_revalidates_suppression` (providerwrites.py:1477-1480) does
  `rec = store.get(rid); if rec is None: continue` — a record the campaign
  names that is not in the queue is skipped, and its people are never asked.
  `_refuse_suppressed_leads` (bisonfactory.py:2046-2053) refuses the identical
  situation with the right sentence: "a question that cannot be asked is not
  answered yes". The resume path fails open on missing records, the staging
  path fails closed, and the resume shape is pre-existing — but this lane
  rewrote the function and left the asymmetry standing.

* **A7 — below the module, all three BLOCK-set owners fail open on an
  unreadable authority.** This is where absence most nearly becomes ALLOW,
  because these produce BLOCK reasons:

  * `ingest._read_suppress` (ingest.py:86-96): missing file → `set()`. A
    worktree without the gitignored local roster silently applies no local
    suppression, and nothing on the consult path consults
    `suppress_sources()` (ingest.py:99-106), which exists precisely to tell
    "empty" from "missing" and is consulted by nobody on this path.
  * `agencydnc.load` (agencydnc.py:150-181): `strict=False` by default because
    `lookup` is on the send path; a genuinely unreadable line's rows are lost
    and `lookup` returns None. The lane's torn-append fix recovers glued rows;
    unreadable bytes still read as "not on the list". The docstring argues the
    tradeoff ("a damaged byte must not take the whole estate down") — that is a
    decision to fail open on a do-not-contact list, and it should be the
    operator's, stated, not a default.
  * `operatorexclusion.resolve` (operatorexclusion.py:331-347): `rows()`
    returns `(ordered, _bad)` and `_bad` is discarded — damaged register lines
    silently remove exclusions.

  Invariant 0 says an unreadable authority means UNKNOWN, which never becomes a
  pass. The module honors that for provider touch history and not for its own
  BLOCK authorities.

### 1.3 Q3 — does `UNKNOWN_IS_NOT_A_PASS` hold at every branch?

No. Branch inventory:

| Branch | Unknown input | Outcome |
|---|---|---|
| `SCOPE_ENROL`, `provider_touches` absent or non-dict | — | **HOLD** ✓ (the one branch where it is written) |
| `SCOPE_ENROL`, dict missing `total_sends` | — | **HOLD** ✓ |
| `SCOPE_ENROL`, dict missing `last_touch_at` / `active_sequence` | — | **ALLOW** ✗ (A1) |
| `SCOPE_ENROL`, `total_sends` non-int | — | **ALLOW** ✗ (A2) |
| `SCOPE_ENROL`, `last_touch_at` present but unparseable/naive | — | **HOLD** ✓ (suppression.py:331-333 — this branch is right) |
| `SCOPE_ENROL`, naive `now` | — | wall clock substituted, HOLD can become **ALLOW** ✗ (A3) |
| `SCOPE_SEND` (all three consult sites) | any | holds not evaluated, by design ✗ — compensated only by an enrolment consult that does not exist |
| BLOCK owners' files missing/damaged | — | **ALLOW** ✗ (A7) |

The design intent — holds belong to enrolment, permanent refusals to the door
— is coherent and the module's own docstring argues it honestly. What is not
coherent is shipping the second half of the module with no caller: as this
branch stands, the only rules standing between any person and any send are the
permanent refusals at three `SCOPE_SEND` consults, and "UNKNOWN means do-not-
touch" (CLAUDE.md, the 2026-10-01 rules) is true only of provider touch
history, only at a scope nothing uses, only when the dict is entirely absent.

### 1.4 Q4 — mutations that SHOULD go red (for the suppression lane to write)

Not written here; that lane owns its tests. Ordered by what they protect:

1. **`total_sends` type confusion (A2).** Feed
   `provider_touches=dict(base_74d, total_sends="50")` and require NOT-ALLOW
   (HOLD_UNKNOWN or a raised refusal — either is fail-closed). Mutation:
   delete the `isinstance` gate so the comparison crashes, or widen `total is
   None` to `total is None or not isinstance(total, int)`, and confirm the test
   still refuses rather than passing.
2. **Partial dict (A1).** Require: a `provider_touches` dict that lacks ANY of
   the three keys answers `hold:provider_touch_history_unknown`, and only the
   full three-key dict may answer anything else. Mutation: restore the
   `bool(provider_touches)` liveness check alone and confirm the test catches a
   half-populated dict passing.
3. **Naive `now` (A3).** Freeze time with a naive datetime and a last touch
   that holds only at that time; require HOLD. Mutation: make `_now` return
   the wall clock for naive input (as now) and confirm RED.
4. **The dead `agency` parameter (A5).** Pass a sentinel index that would
   answer differently from disk; require the verdict to reflect it — or delete
   the parameter. Mutation: swallow it (as now) and confirm RED.
5. **Enrolment wiring (§1.1d)** — the important one. When the `SCOPE_ENROL`
   consult is added at lead selection / cohort build, the mutation is: delete
   that call and require the enrolment test RED, the same way
   `test_the_guard_is_load_bearing` does for `_ensure_leads`. Until that caller
   exists, `UNKNOWN_IS_NOT_A_PASS` is a module property, not a system one.
6. **`batch_activate.py:144` (b).** Route it through
   `perform(EMAIL_RESUME, ...)` and add the suppression assertion the door now
   provides; mutation: revert to the bare call and require RED. (This may
   belong to the B5/pilotcaps lane — the bypass count is theirs — but the
   suppressed-contact-in-a-resumed-campaign test is suppression's.)
7. **The list-condition name (c).** `_list_is_ours_and_unbound_and_holds_approved`
   should either check the leads or lose the third clause of its name; the
   mutation for whichever the operator picks is a list holding an unapproved or
   suppressed lead refusing `LINKEDIN_CREATE_CAMPAIGN`.
8. **Roster missing vs empty (A7).** Remove the local roster file and require
   the consult path to refuse-or-flag rather than pass; `suppress_sources()`
   already exists and has no consumer on this path.
9. Already covered by the lane, verified present: door-consult mutation,
   `_refuse_suppressed_leads` call-site mutation (md5-documented), resume-verb
   mutation, `UNKNOWN_IS_NOT_A_PASS=False` mutation (goes red via
   `test_unknown_touch_history_holds_rather_than_passes`).

### 1.5 What survived the attack

Said plainly, because a review that only lists wounds misprices the module:

* The BLOCK set is genuinely single-implementation — `must_not_contact`
  called, not cloned, and the `CONDITIONAL[EMAIL_RESUME]` reroute removed the
  second copy of the question.
* `_verdict` as the only verdict constructor, with `_CONSULTATIONS` appended
  on every exit including ALLOWs, is the right shape and is more than most
  guards in this repository can show.
* The ordering inside `revalidate` (suppression before `eligibility.decide`,
  with the measured reason why second would hide it) is correct and the reason
  is recorded where the next reader needs it.
* `_refuse_suppressed_leads` refusing a lead that names nobody in the queue —
  "a question that cannot be asked is not answered yes" — is invariant 0
  applied correctly, and the whole-run-stops stance matches the module's.
* The reply-direction tests (text never drives suppression; disinterest never
  sums into an opt-out) cover the two ways this class of module eats people.
* `SCOPE_SEND`'s refusal to *report* unevaluatable holds is argued, not
  accidental, and the argument (a hold nobody can lift would stop the estate)
  is sound — the gap is the missing enrolment caller, not the scope split.

### 1.6 Second pass — what going back over it found

Both tasks closed with budget left, so the module was re-read end to end
hunting the classes the first pass did not check: address normalization
across every BLOCK authority, the consumer side of the verdict, `require()`'s
behaviour on HOLD, and non-dict truthy `provider_touches`. **It found one new
defect, one strengthening of an existing one, and four attacks that failed.**
All verified by execution before being written down.

**S1 (new) — the consultation record erases the scope, so a scope downgrade at
a consult site is invisible to the module's own proof mechanism.**
`_CONSULTATIONS` appends `(rec_id, contact_key, action)` — three fields, no
scope (suppression.py:249). Verified: the same record/contact at
`SCOPE_ENROL` (full three-key touch history) and at `SCOPE_SEND` leaves
**byte-identical records** — `[('r1','c1','allow'), ('r1','c1','allow')]`.
The scope exists in `Verdict.detail` (suppression.py:274) but not in the
record `consultations()` returns, and the module's own docstring
(suppression.py:146-150) sells that record as how a test proves the module
was asked. Consequence: once the `SCOPE_ENROL` caller lands, a mutation that
changes that site to `scope=SCOPE_SEND` — silently disabling every HOLD rule
and `UNKNOWN_IS_NOT_A_PASS` at enrolment — keeps every consultations()-based
assertion GREEN, provided the test's fixture supplies complete touch history
(both scopes answer `allow`). With absent touch history the actions differ
(`hold` vs `allow`) and the downgrade would go red — so catchability hangs on
a fixture choice the lane has not made yet, which is the argument for fixing
the record rather than relying on the fixture. The mutation the lane should
write: extend the tuple with the scope (or the reasons) and assert the ENROL
consult is recorded as an ENROL consult; then downgrade the site and require
RED. One field buys a whole class of silent downgrades.

**S2 (strengthens A3)** — folded into A3 above: `_now`'s wall-clock
substitution fires for unparseable `now` STRINGS as well as naive datetimes.

**Four attacks that failed, said plainly:**

* **Case/whitespace escapes of the BLOCK set: none found.** Every BLOCK
  authority normalizes on both the write and the read side —
  `agencydnc.add` (agencydnc.py:217) and `keys_for` (agencydnc.py:103) both
  pass through `dedupe.normalise_email`; `_operator_excluded` lowercases and
  strips the contact address before `blocks_address` (eligibility.py:333);
  `_suppressed` lowercases the domain (eligibility.py:354);
  `_client_own_domain` lowercases both sides (eligibility.py:384-388). The
  plus-addressing asymmetry in `blocks_address` is deliberate and documented
  (operatorexclusion.py:393-406 — the tag is stripped at the prohibition, not
  in identity, because the two errors are not symmetric). `Jane@Example.com`
  from a CSV import does not escape any of them.
* **`require()` raises on HOLD as well as BLOCK** (suppression.py:352 —
  `!= ALLOW` raises), so the convenience form cannot quietly convert a
  three-valued verdict into a two-valued pass.
* **A truthy non-dict `provider_touches` fails closed**: `isinstance(...,
  dict)` gates `known`, so a list or string → `HOLD_TOUCH_HISTORY_UNKNOWN`.
* **Their tests reset the consultation log** (test file lines 120-121, reset
  plus `addCleanup`), so the cross-test contamination the process-global list
  invites is handled where it matters today. (The list does grow unboundedly
  in a long-lived process — entries are 3-tuples, so it is a note, not a
  defect; the module's own docstring owns the "fifteen loops import once"
  reality that makes the log process-global at all.)

---

## TASK 2 — the second suppression list, reconciled: a design

Design only. Nothing here is implemented, and nothing here should be
implemented from this document without the suppression lane and the operator
taking it through their own gates.

### 2.1 What the two lists are, and how each is read

**Ours — four local authorities, no provider call needed to read any of them:**

| Authority | Where | Grain | Read path |
|---|---|---|---|
| agency DNC ledger | `work/agency-dnc.jsonl` (per `agencydnc.path()`) | person, sha256 fingerprints by design | `agencydnc.load()` — local file |
| client suppression roster | `ingest.SUPPRESS` + gitignored `SUPPRESS_LOCAL` | domain | `ingest.load_suppress()` — local files |
| person flags on queue records | `work/queue.jsonl` contacts | person | `store` / record fields (`unsubscribed`, `suppressed`, `stopped`) |
| account-level suppression | record `suppression.unsubscribed`, `drop_reason` prefix, `accountstate.DO_NOT_CONTACT` | company | record fields |

One caveat the design must carry: the agency ledger stores **one-way
fingerprints, deliberately** (§7.7 of the lane's measurement doc). Reconciliation
must therefore always run **hash-theirs, look-up-in-ours**: take the provider's
plaintext address, `agencydnc.fingerprint("email", addr)`, look that up in the
local index. The reverse direction — enumerating who WE hold — can only be
answered by matching our fingerprints against known contacts, never by
un-hashing. And the local list is itself in flux: the 94 classified DNCs are
**not yet applied** (§7.2), so an early reconciliation will show a large
ours-not-theirs delta that is really an application backlog, not a disagreement.

**Theirs — EmailBison's blacklist — cannot be read today.** The adapter
(`src/providers/bison.py`) has no blacklist route; nothing in `WRITE_ROUTES`,
the read surface, or the observed event vocabulary names one. The FAQ (per
CANARY-01) names the list and a "remove blacklisted contacts" UI action, which
proves the list exists and proves nothing about an API read. Two things ARE
established that bear on it:

* the provider's per-lead status vocabulary, as observed in
  `lead_campaign_data` — `STOPPED_STATES = ("stopped", "replied", "bounced",
  "sequence_finished", "unsubscribed")` (bison.py:782-783) — which is where the
  blacklist's **effect** would surface: a blacklisted lead reads as one of
  these while our local state says active;
* `find_lead_by_email` (bison.py:601) — an exact, ambiguity-refusing per-address
  provider read.

So the design is two-tier, and the tier boundary is explicit:

* **Tier 1, establishable now: reconcile the EFFECT.** Compare our expectation
  (this lead is active in campaign X) against provider truth (the lead's
  status in `lead_campaign_data`). A lead in a stopped state we did not cause,
  with no local reply/bounce/unsubscribe event explaining it, is a
  reconciliation hit. This catches the bad direction — silently dead leads —
  with routes that already exist.
* **Tier 2, blocked on route establishment: reconcile the LISTS.** Reading
  their blacklist needs either a documented API route (established read-only,
  per the providerwrites doctrine that guessing routes against a live estate
  is how you discover one by mutating production) or a one-time UI export by
  the operator. Until one exists, the list-level comparison's answer is
  **UNKNOWN**, and an UNKNOWN reconciliation is not "reconciled" — it is
  reported as unknown, exactly as `provider_truth.py` reports campaigns it
  could not read.

### 2.2 What a disagreement in each direction means, and what should happen

**Direction 1 — on ours, not on theirs.** We hold a DNC; Bison does not. What
it means: our local refusal protects nothing outside this system. The same
workspace runs internal Resonate campaigns by hand and — per the corrected
2026-10-01 finding — campaigns of unknown owner; a human enrolling one of our
DNC'd people into any of those gets no warning, because our list is invisible
to the provider. What should happen: **report, do not write.** The standing
rule is already decided twice — internal campaigns' negative replies "go into
the local suppression/touch ledger, never back to a provider" (CLAUDE.md,
2026-10-01) and the lane's §7.2 repeats it for the 94. So the reconciliation
never pushes ours onto theirs; it surfaces the delta to the operator, who owns
the UI action. The one write this system may make in this direction already
exists and stays per-campaign: `EMAIL_STOP_LEAD` / `LINKEDIN_STOP_LEAD` —
which stop a person's progression in OUR campaigns, and which internal
campaigns are explicitly never touched by.

**Direction 2 — on theirs, not on ours.** Bison silently stops the sequence:
the lead sits in the campaign reading a stopped state, sends never happen, and
— the operational trap CANARY-01 already records for deleted senders —
"those contacts do not recover on their own". What it means: leads the client
paid for are dead with no signal, and any metric built on scheduled volume
overcounts. What should happen: **detect and import-or-flag, operator
decides.** Tier 1 detects it (unexpected stopped state); the report names the
lead, the campaign, the observed state and the absence of a local explaining
event. Whether a provider-side blacklist entry becomes a local suppression row
is an operator decision made once, as policy — not per-row in code. The
default action is the conservative one: the lead is flagged NOT CLEAN (a
provider refused them; that is evidence about them), and nothing enrols them
anywhere else until a human says why.

**Both directions share one non-action:** the reconciliation never edits
either list itself. It is a comparison with a report; the two lists keep their
own owners.

### 2.3 Where the comparison belongs

The gate token lives at `providerwrites.perform` because that is the one point
every write passes — fourteen call sites each remembering to ask was the
failure mode. The same reasoning applied here:

* The **enrolment consult** (the `SCOPE_ENROL` caller that does not exist yet,
  §1.1d) is the sink for person-questions at the moment a person is placed in
  front of the provider. Provider touch history is already specified to be
  read there ("that is the moment at which reading it is cheap and correct",
  suppression.py:122-124). The provider-side-suppression question belongs in
  the SAME read, feeding the same verdict — as one more authority
  `provider_touches` carries, or a sibling field (`provider_refusal`), not as
  a second consult at a second call site. One enrolment decision, all
  authorities, one HOLD reason per unknown.
* The **post-attach readback** in `_ensure_leads` is the sink for "did the
  provider take them as we meant" — attach already re-reads membership; the
  design adds: every just-attached lead's status must be a resumable state,
  and a stopped state with no local cause is a staging failure (the whole run
  stops, matching the function's existing stance for missing copy).
* The **estate-level comparison** is a report job in the `provider_truth.py`
  family — `scripts/` entry point, reads both sides, writes
  `docs/state/SUPPRESSION-RECONCILIATION.json` with `generated_at`,
  per-direction counts, `compared`, and `unknown` — never inside a send or
  enrolment path, because it walks whole lists and a walk is not a gate.

What must NOT happen is the comparison smeared across call sites: not in
`eligibility`, not in each factory, not in the watcher. One enrolment consult,
one readback check, one report job.

### 2.4 What would prove it runs, and that it can fail

Runs:

* `docs/state/SUPPRESSION-RECONCILIATION.json` exists with a fresh
  `generated_at`, and `compared > 0` — a reconciliation that compared nobody
  is a green dashboard watching nothing (the exact defect CLAUDE.md records
  for spend audits).
* At enrolment: the consultation record (`suppression.consultations()` or its
  successor) shows the provider-refusal question was part of the verdict, the
  same way the door-consult test proves the module was asked.
* At staging: the attach readback's report carries a per-lead status, so "the
  provider took them and they are alive" is a recorded fact, not an assumed
  one.

Fails:

* **Mutation 1 (the comparison is load-bearing):** delete the compare call in
  the report job → the state file's counts all read zero while the fixture
  holds disagreements → a test asserting the counts non-zero on a planted
  fixture goes RED.
* **Mutation 2 (UNKNOWN is not agreement):** make the provider read raise (or
  return an unestablished shape) → the report must record `unknown` and must
  NOT record "agree"; a test asserting the file says reconciled-clean with a
  failing read goes RED. This is the mutation that keeps tier 2 honest while
  the route is unestablished.
* **Mutation 3 (the readback notices the dead):** stage a lead whose provider
  status reads stopped with no local cause → `_ensure_leads` (or its successor)
  refuses the run; delete the status check and the test goes RED.
* **Mutation 4 (no silent direction-1 writes):** attempt any code path that
  writes our list to the provider → it must refuse (no route, no verb, no
  grant — the test asserts the refusal, so the standing "never back to a
  provider" rule is enforced rather than remembered).

### 2.5 Does the same problem exist on HeyReach?

**Cannot be told from what this repository establishes, and I am saying so
rather than guessing.** The HeyReach adapter's observed surface —
`WRITE_ROUTES`, the read routes, the lead-state vocabulary in `lead_state` —
names no suppression, DNC or blacklist concept. That absence is evidence
about the ADAPTER, not about the provider: HeyReach may well keep account- or
workspace-level safety lists in its UI that this system has never had a reason
to read. What CAN be said:

* the same *structural* exposure exists — HeyReach campaigns run under the
  same roof as the client's, an operator can add people by hand, and our local
  list is invisible to their UI;
* the same tier-1 effect-detection is available in principle —
  `campaign_leads` / `lead_state` reads exist — but whether HeyReach's lead
  states distinguish "stopped by provider safety list" from "stopped by
  sequence end" is unestablished;
* establishing it needs the same read-only route discipline as tier 2 on the
  Bison side, plus one question to whoever owns the HeyReach account: does the
  UI expose a suppression/blacklist list, and does it stop sequences silently?

Until then the HeyReach reconciliation question is UNKNOWN, and it should be
carried as an open item in the state file, not folded into either "done" or
"not applicable".

