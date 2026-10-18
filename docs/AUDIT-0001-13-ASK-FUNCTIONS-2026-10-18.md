# audit/0001 — the 13 ask functions, named, anchored and attributed

Measured 2026-10-18 in a fresh worktree (`wt-audit-0001-13ask-2026-10-18`)
on branch `task-audit-0001-13-ask-functions-2026-10-18`, base local master
`0355fe7b72c9497b12819c37d16795a66039c943` (commit, 3,419 B). Measurement and
specification only: nothing built, nothing changed, nothing applied, no
guard/gate/cap/config change, no `src/providers/*` read, no `config/.env`, no
production `work/` read, no main-checkout entry, no network beyond pushing this
lane branch, no suite run, no suite lock, nothing on master.

Every hash below was copied from command output in this session, never retyped,
and carries its byte count beside it. Every line anchor was re-derived at the
named SHA in this session from the named blob; none is inherited from a brief
or a lane entry.

---

## 0. WHERE THE 13 LIVE, AND THE ONE THING THAT IS TRUE OF ALL OF THEM

The instrument is `src/preflight.py` + `scripts/preflight_one_command.py` +
`scripts/canary_preflight.py`, and it is **ABSENT from local master**
`0355fe7b72c9497b12819c37d16795a66039c943` (measured:
`git cat-file -e 0355fe7b72:src/preflight.py` → fatal, path does not exist).
It exists on branch `task-qwen-coder-0260-b4b-preflight-one-command-2026-10-17`
@ tip `1ba54cdda541adee1a97e0401f0b3f678e1bbb3d` (commit, 733 B), carrying:

- `src/preflight.py` blob `a3877f8b78e9b93616ff65a2b30f7c9aa77e8527` (100,833 B)
- `scripts/preflight_one_command.py` blob `2db8ca48f32676966c143f147e2d143f1ed8ca30` (15,967 B)
- `scripts/canary_preflight.py` blob `7e6fb21f05fd4639e4d68a06c0714bdbaff9e870` (15,608 B)

The `RULES` tuple at `src/preflight.py:798-968` (blob `a3877f8b…`, the only
blob these `src/preflight.py` line numbers resolve against) declares **23
rules**, measured by AST parse of the blob, not by counting prose. Of those 23:
2 carry an ask and PASS anywhere (the operator-exclusion pair), 1 carries an
ask that can exclude but never pass (`bounce_history`), 4 declare
`needs_provider_read` and have `ask: None` (the hold/cooling rules), and **13
declare `needs: ("queue",)`, `needs_record: True` and `"ask": None`** — measured
by the same AST parse: `ask=None` 17, provider-read 4, `needs_record` 14, and
13 = ask=None minus the provider-read four. Those 13 are the 13 ask functions.
They are **unbuilt on every branch in this repository** — no `_ask_*` function
exists for any of them on master, on the 0260 branch, or on
`task-qwen-coder-0001-preflight-table-proof-2026-10-18` @
`6df4c4a967275f27df48b53c76859adb3bd154ed` (commit, 406 B), which carries the
same instrument blobs.

The rule the evaluation follows (this is why the 13 are UNKNOWN **in every
tree**, the main checkout included): `evaluate()` at
`src/preflight.py:1232-1283` refuses the rule unless the `queue` authority is
`PRESENT_POPULATED`; `:1290-1295` refuses it unless the contact carries its
queue record; and `:1312-1322` — the branch the other two let a main-checkout
run reach — sets UNKNOWN with the sentence *"this rule has no form that can be
evaluated without a record or a provider read"*. Building the record join
without building the function changes nothing; building the function without
the record changes nothing; both are needed per rule.

**The production decision functions the 13 would wrap are all measured
identical between master `0355fe7b72…` and the 0260 tip `1ba54cdda…`**
(`git diff --stat` empty for every file cited from master below), so a master
anchor is also a 0260 anchor for those files. The one exception is
`src/suppression.py`, which is absent from master and exists only on branches
(see row 9).

**Two inputs, and the distinction the count turns on.** Each of the 13 needs
(i) the function itself — code in `src/preflight.py` on a lane branch, and only
a lane builds instrument code — and (ii) the data the function consumes: this
contact's queue record (and for three rows, more than that), which exists only
in the main checkout's gitignored `work/`, which no lane may enter. The
classification below answers the brief's question — **who can supply the
INPUT** — on axis (ii). On axis (i) all 13 are lane-buildable, and that is the
only part of this that any weekend lane can do.

---

## 1. THE THIRTEEN ROWS

Per row: the rule, the `ask: None` slot it would fill (line in the
`src/preflight.py` blob `a3877f8b…` at `1ba54cdda…`), the production function
the ask would wrap (file:line at master `0355fe7b72…` unless a branch is
named, with the blob and byte count that pins the anchor), the input it is
missing today, and who can supply that input.

### 1. client_suppressed_drop
- ask slot: `src/preflight.py:858` (`"ask": None`; rule row `:855`).
- wraps: `eligibility._suppressed`, the `drop_reason` branch —
  `src/eligibility.py:358` (function at `:342`), blob
  `f2c744aca310ba7ea06bd6528b9cd5cb81e7350b` (47,841 B).
- missing input: this contact's queue record — `rec["drop_reason"]` — from
  `work/queue.jsonl` via `store.load()` (`src/store.py:849`, blob
  `f8bc166f989ca21623c98c12031d28a03a46fc1d`, 85,300 B).
- who: **OPERATOR-ONLY** — the `queue` authority
  (`work/queue.jsonl` in the main checkout, per-tree in every worktree,
  gitignored; `store.PRODUCTION_WORK` resolves against the calling tree).

### 2. client_own_domain
- ask slot: `src/preflight.py:863` (rule row `:860`).
- wraps: `eligibility._client_own_domain` — `src/eligibility.py:368`.
- missing input: the record (`rec["client"]` names the client file); the other
  half — `config/clients/<client>.yaml`, read by `clients.load`
  (`src/clients.py:224`) — is TRACKED and lane-readable, but the record gates
  the rule (`needs_record`).
- who: **OPERATOR-ONLY** (queue record).

### 3. record_state
- ask slot: `src/preflight.py:869` (rule row `:866`).
- wraps: `eligibility._record_state` — `src/eligibility.py:393`.
- missing input: the record (`rec["state"]`, `rec["drop_reason"]`).
- who: **OPERATOR-ONLY** (queue record).

### 4. contact_flags
- ask slot: `src/preflight.py:876` (rule row `:873`).
- wraps: `eligibility._replied`, the flag branch — `src/eligibility.py:448`,
  flags at `:467-472`.
- missing input: the record's contact entry (`unsubscribed` / `suppressed` /
  `stopped` / `paused` flags) — the cohort contact carries email and key only.
- who: **OPERATOR-ONLY** (queue record).

### 5. contact_reply_event
- ask slot: `src/preflight.py:881` (rule row `:878`).
- wraps: `eligibility._replied`, the event branch — `src/eligibility.py:448`,
  events at `:474-476`.
- missing input: the record's `events` list.
- who: **OPERATOR-ONLY** (queue record).

### 6. account_suppressed
- ask slot: `src/preflight.py:886` (rule row `:883`).
- wraps: `eligibility._paused`, the account-suppression branch —
  `src/eligibility.py:401`, branch at `:407`.
- missing input: the record (`rec["suppression"]["unsubscribed"]`).
- who: **OPERATOR-ONLY** (queue record).

### 7. account_review_open
- ask slot: `src/preflight.py:891` (rule row `:888`).
- wraps: `eligibility._paused`, the open-review branch — `src/eligibility.py:401`,
  branch at `:409`.
- missing input: the record (`rec["review"]["open"]`).
- who: **OPERATOR-ONLY** (queue record).

### 8. account_paused
- ask slot: `src/preflight.py:896` (rule row `:893`).
- wraps: `eligibility._paused` via `cadence.pause_state` —
  `src/eligibility.py:413` + `src/cadence.py:1091` (blob
  `af827c1a402eb655210a372a2b218f6050dcf8fa`, 69,345 B).
- missing input: the record (account suppression, `rec["paused"]`, meeting and
  reply events); the client config half is tracked (`config/clients/…`).
- who: **OPERATOR-ONLY** (queue record).

### 9. account_reply_log
- ask slot: `src/preflight.py:901` (rule row `:898`).
- wraps: `suppression.decide` step 2 via `account.replies` —
  `src/suppression.py:253`, the step-2 call at `:290` (blob
  `5cce88debcca761b92fd2a29de7db17ebc349961`, 20,910 B) **on branch
  `task-qwen-coder-0260-b4b-preflight-one-command-2026-10-17` @ `1ba54cdda…`
  — ABSENT from master `0355fe7b72…`, measured: not in master's `src/`
  tree. Its own origin is commit `40d0d7d56` (also carried by
  `integ/canary-nine-2026-10-15` and others)**; plus `src/account.py:149`
  (blob `74657d99e6ed5d591fbc65b4d16b11326a7b037c`, 20,577 B), which IS at
  master and carries the whole projection the ask needs.
- missing input: the record's `events` list (reply events keyed to this
  contact).
- who: **OPERATOR-ONLY** (queue record). The ask can be written against
  `account.replies` at master alone; naming `suppression.decide` requires the
  0260 branch.

### 10. mx_and_verification
- ask slot: `src/preflight.py:920` (rule row `:916`).
- wraps: `channels.email_verdict` — `src/channels.py:164` (blob
  `0eb28c033d144b4baa5712e60c6c48df0bb3fd00`, 15,201 B), MX leg at `:184`
  (`mx.allows_email`, `src/mx.py:646`, blob
  `328a1e8aaac9ac5b6754cf2b2de15b896ba75227`, 30,478 B) and verification leg
  at `:205` (`lint.sendable` + `lint.policy_for_record`, `src/lint.py:418` /
  `:436`, blob `92340af938c78f9e2254f9d6e4f570ac08b646ca`, 44,518 B).
- missing input: the record — the contact's STORED MX hostnames (MX is
  re-derived from stored hostnames, `mx.stored_decision` at `src/mx.py:620`;
  no DNS call is needed for a verdict) and the stored verification evidence,
  plus `rec["client"]` for the policy. **No network and no provider read is
  needed to return a verdict**: a contact with no stored evidence answers
  EXCLUDED (`NOT_VERIFIED`), which is a verdict, not an UNKNOWN.
- who: **OPERATOR-ONLY** (queue record).

### 11. hygiene_workspace_history
- ask slot: `src/preflight.py:927` (rule row `:924`).
- wraps: `hygiene.check` step 2 — `src/hygiene.py:337`, step 2 at `:382`, via
  `hygiene.index` at `src/hygiene.py:214` (blob
  `25190113d207274526253b43c34d7443368fabb9`, 18,599 B).
- missing input: **more than this contact's record — the WHOLE production
  queue**, because `hygiene.index(recs=None)` calls `store.load()` and keys
  every contact we have ever worked by strong identity. The one record the
  cohort join supplies is not this rule's input; the estate is.
- who: **OPERATOR-ONLY** (the whole main-checkout `work/queue.jsonl`).

### 12. hygiene_account_history
- ask slot: `src/preflight.py:932` (rule row `:929`).
- wraps: `hygiene.check` step 3 — `src/hygiene.py:337`, step 3 at `:389`.
- missing input: the same whole-queue index (by domain).
- who: **OPERATOR-ONLY** (the whole main-checkout queue).

### 13. client_approval_register
- ask slot: `src/preflight.py:937` (rule row `:934`).
- wraps: `hygiene.check` step 0 via `clientapproval.is_suppressed` —
  `src/hygiene.py:361` + `src/clientapproval.py:193` (blob
  `b88934d5b81a9942819d3aca7d8e70c8ccea185a`, 18,814 B), loading
  `clientapproval.path()` at `src/clientapproval.py:127` —
  **`work/client-approval.jsonl`, beside the queue**.
- missing input: the record (`rec["client"]`, the domain) AND the approval
  register file. **Specification hazard for whoever builds the ask**:
  `clientapproval.load()` returns `[]` for an ABSENT register and
  `is_suppressed` then returns False, so a naive ask would report PASS from a
  file that is not there — the exact TASK-0190 shape. The register is **not
  one of the 8 declared authorities** (`AUTHORITIES` at
  `src/preflight.py:325-437`); the built ask must declare it or check its
  state fail-closed, or this rule will be the one that fakes the clear.
- who: **OPERATOR-ONLY** (queue record + `work/client-approval.jsonl`, both
  main checkout only).

---

## 2. THE COUNT THAT DECIDES THE WEEKEND

On the input axis (who can supply what the function consumes):

- **lane-closable: 0 of 13.** Not one of the 13 can be closed end-to-end by a
  lane. Every one of them consumes data that lives in the main checkout's
  gitignored `work/` (the contact's queue record for 12 rows, the whole queue
  for rows 11 and 12, and the approval register for row 13), and no lane may
  enter the main checkout or read production `work/`. This lane could not even
  verify that the 23 contacts HAVE queue records — that is UNKNOWN from here,
  answered only by the main checkout itself.
- **operator: 13 of 13.** The operator supplies the input by running the joined
  command from the main checkout, where the `queue` authority is the production
  `work/queue.jsonl` (5 of the 8 declared authorities exist only there; the
  other four main-only ones feed rules outside the 13).
- **provider read: 0 of 13.** The paginated EmailBison + HeyReach read
  (`eligib/0001`, `eligib/0002`) serves the FOUR hold/cooling rules, which are
  not among the 13. No row in the table above consumes provider truth.

**0 + 13 + 0 = 13.** On the code axis, the complementary fact: 13 of 13 ask
functions are lane-buildable and unowned, and building them against synthetic
records is exactly the work `qwen-coder/0001` proved possible for the five
asks that exist. The weekend's honest division: a lane can build all thirteen
and prove them blind; only the operator can make them see.

---

## 3. THE SECOND QUESTION — WOULD 13 VERDICTS + THE PROVIDER READ MAKE IT 23/23?

**No. Something else is missing — three things, and the first two are
structural, not data.** The denominator: 23 contacts × 23 rules = 529 cells;
cleared means every cell PASS or not-applicable, 0 EXCLUDED, 0 UNKNOWN,
per `evaluate()`'s `"cleared": not excluded and not unknown`
(`src/preflight.py:1360`).

**a) `bounce_history` can EXCLUDE and can NEVER PASS — 23 cells stay UNKNOWN
forever at this SHA.** It is not one of the 13; it already has an ask
(`_ask_bounce_history`, `src/preflight.py:730`). But when no bounce event is
recorded, it returns `Undecided` — *"no EMAIL_BOUNCED event is recorded …
AND THAT IS NOT A PASS"* (`src/preflight.py:791-795`) — because the bounce
recorder's own failure line has ONE writer (`scripts/bison_watch_loop.py`)
and ZERO readers, so an empty event list cannot be told apart from a recorder
that has been failing while the watcher reports UP. `WHAT_WOULD_ANSWER`
names it at `src/preflight.py:1192-1202`: until a reader of that failure
reaches a verdict, a missing bounce event licenses no PASS. **A
bounce-recorder health reader must be built — that is a 14th piece of
instrument work nobody has specified, and without it the cohort cannot be
cleared even with the record join perfect.**

**b) `internal_campaign_membership` cannot PASS against any real listing — 23
more cells stay UNKNOWN.** Its PASS requires every internal-or-unknown
campaign in the listing PROVEN COMPLETE (`campaignmembership.proven_complete`
at `src/campaignmembership.py:220` on the 0260 branch, blob
`8341f5b0690c84807663e6fb2acd9e7ba46136d3`, 14,584 B), and completeness needs
`leads_reported` compared against `leads_read` — but the producer discards the
provider's own total at `scripts/build_collision_index.py:73` (blob
`955dec0e05b68c940e1d025a029de11a3c4553a7`, 8,379 B, at `1ba54cdda…`), so a
walk truncated at the page cap is indistinguishable from a finished one. The
provider read landing does not fix this: it re-runs the same producer. The fix
is one line in the producer (keep `_total`) and then a re-walk — build work
and a provider read, not just a read.

**c) The four hold/cooling rules have NO INPUT PATH in the instrument — the
provider read alone clears nothing.** `evaluate()` checks
`needs_provider_read` at `src/preflight.py:1284-1289` BEFORE any ask is
consulted, and there is no ask and no input parameter anywhere in the
instrument for provider touch truth (`grep provider_touches` over the blob:
zero hits). However `eligib/0001`/`eligib/0002` land their data, nothing in
`src/preflight.py` consumes it: those four rules stay UNKNOWN until asks (or
an input path) are built for them too. **The code work is 13 + 4 + 1
(bounce-recorder reader), not 13.**

**And the data precondition, named as UNKNOWN rather than assumed:** the 23
contacts' queue records must exist in the main checkout and be joined into
the cohort — whether `work/suppression-measure/0170/cohort-23.json` (or
anything in the queue) holds records for these 23 people is UNKNOWN from this
lane (production `work/` forbidden), and the 2026-10-16 preflight doc records
the cohort as derived from the approval sheet, not from the queue. The
authority for it is the file itself plus Monday's run header
(`cohort … (N contact(s))` and `authorities POPULATED p/8`).

**Shortest honest sentence for the operator: 23/23 cleared is NOT reachable
by Monday 2026-10-20 — with all 13 ask functions built and both provider
reads landed, `bounce_history` and `internal_campaign_membership` still
cannot PASS at this SHA and the four hold rules still have no input path at
all, so the cohort stays 0/23 NOT CLEARED (UNKNOWN).**

---

## 4. THE ARITHMETIC, RE-DERIVED

The brief said 22 × 23 = 506; `qwen-coder/0001` measured 529. **529 is
right**, re-derived here two ways: an AST parse of the instrument blob
`a3877f8b…` counts **23 rules** in `RULES`, and the proof run's rendered
table (`_0001_scratch/runM1_table23.out` on
`task-qwen-coder-0001-preflight-table-proof-2026-10-18` @ `6df4c4a96…`)
prints 23 rule blocks × 23 contacts with a cell census that sums to 529
(46 PASS + 92 provider-read UNKNOWN + 391 named offline-UNKNOWN + 0 blank).
**The 23rd rule is `internal_campaign_membership`** — added by TASK-0200,
commit `4d0ee90ba` (5,316 B), whose parent's `src/preflight.py` measures 22
`RULES` and whose own measures 23; the 2026-10-16 preflight doc that said
"22 rules" was written at `81475191a`, before that landing. A Monday artefact
reconciled against 506 would call a correct 529-cell run malformed — the
error is in the premise, not the run. The contact count is the cohort's own
N (23 expected; the header line of the Monday run is its authority, and this
lane could not read the real cohort).

---

## 5. BOUNDARIES AND BOOKS

- Fresh worktree `wt-audit-0001-13ask-2026-10-18`, branch
  `task-audit-0001-13-ask-functions-2026-10-18` off local master
  `0355fe7b72c9497b12819c37d16795a66039c943`. Nothing on master; this file is
  the only tree change besides untracked `_0001_scratch/`.
- No `src/providers/*` opened; no `config/.env`; no production `work/` (the
  queue authority was NAMED, never read, per the 2026-10-16 doc's own
  discipline); no main-checkout entry; no network beyond `git push` of this
  branch; no suite, no lock, no send, no activation, no credential printed.
- All python invocations `-B`; no `.pyc` written into the tree (zero
  `__pycache__` directories created — the AST parses read the extracted copy
  in scratch).
- Every UNKNOWN named as UNKNOWN: the 23 contacts' queue-record existence,
  the main checkout's authority states at Monday run time, and the cohort's
  real contact count are each carried as UNKNOWN with their answering
  authority, never subtracted.

**The one-line answer to the brief's headline question:** the 13 ask functions
are 13 per-rule wrappers in `src/preflight.py` (blob `a3877f8b…`, on the 0260
branch, absent from master) around production functions that already exist at
master `0355fe7b72…` — and every one of them is blocked on the operator's
main-checkout data, not on a lane, not on the provider read; while the cohort
cannot be cleared Monday anyway, because `bounce_history` can never PASS, the
internal-campaign listing can never be proven complete, and the four hold
rules have no input path in the instrument at all.
