# Suppression: what was measured, what was built, and what it cannot see

Lane `task-suppression-2026-10-14`, worktree `Desktop/wt-suppression-2026-10-14`,
based on `2bf7b8a571fe11bada4f56fbebeee768ab1e78a8`.

Long pole for CANARY-01. No prospect-facing send, no activation, no provider
call, no push, no merge. Everything below is measured from disk or demonstrated
in a test; nothing is inferred from a handoff.

---

## 0. Corrections to the brief

Four of the five premises hold exactly. Two need correcting and one needs
sharpening.

| Premise | Verdict |
|---|---|
| 90 of 94 who asked to be removed are on no suppression list | **Confirmed, exactly.** |
| `src/suppression.py` does not exist | **Confirmed, and stronger than stated** — see §1. |
| 90-day cooling is correct; thresholds are provisional config | **Confirmed and implemented as config.** |
| Attribution and suppression are separate questions | **Confirmed** — it is already a standing rule in CLAUDE.md, operator 2026-10-02. |
| `inbound.py` discards computed safety holds | **Confirmed, and worse than "no writer" — now fixed** — see §4. |
| "Every reply since 2026-09-25 is unmatched" | **The date is wrong.** See §4. |
| `agencydnc` loses a row to a torn append | **Confirmed by reproduction, and fixed** — see §5. |

### `src/suppression.py` has never existed

Not "was deleted", not "was never finished". Checked three ways:

    git log --all -- src/suppression.py          -> empty
    git log --all --diff-filter=A --name-only    -> no such path, ever
    git ls-tree -r <every local and remote ref>  -> absent from all

So this is a first write, not a restoration. Nothing in this lane is
re-establishing prior behaviour.

Corroborated independently by the C11e measurement
(`resonate-ops/c11e-2026-10-14/C11E-REPORT.json`): the pre-registered module
list declares **17** modules, **16** import, and the single failure is
`suppression.py — ModuleNotFoundError: No module named 'src.suppression'`. The
ghost in that list is exactly this module; on this branch that import now
succeeds.

What *does* exist, and is easy to mistake for it:

* `src/optout.py` (32 lines) — **the outbound wording only.** It appends
  `"If this isn't relevant, reply STOP and I'll close the file."` to every
  rendered body. Nothing in the repository consumes a STOP. The system invites
  an opt-out through a channel it does not read.
* `src/agencydnc.py` (201 lines) — a real, hashed, agency-wide DNC store. Its
  own docstring says it is **"never derived"**: only a super admin writes to it.
  That single sentence explains the 90.
* `src/operatorexclusion.py` (791 lines) — permanent per-person exclusion.
* `config/suppress.txt` — **not a removal-request list.** It is live/paying
  customer *domains*, so cold sequences skip clients. Different concern.

---

## 1. Where removal requests land today

**Nowhere, automatically.** The chain exists end to end and is broken at the
first link:

    reply arrives at provider
      -> inbound.ingest            reply watcher: events_inspected = 0
      -> accountpolicy.apply_reply writes contact["unsubscribed"]
      -> eligibility.must_not_contact reads that flag
      -> executionguard gate 4 / revalidate enforces it

Every link below `apply_reply` works. The two above it do not run.

### The live DNC ledger

`work/agency-dnc.jsonl`, 15 rows: 2 `internal`, 13 `requested`. All 13
`requested` rows carry the identical timestamp `2026-10-02T08:41:48+00:00` —
one manual backfill, not an ongoing process.

### Suppression state on the records

`work/queue.jsonl`, 1,584 records / 1,381 contacts:

| flag | contacts |
|---|---|
| `unsubscribed` | 76 |
| `suppressed` | 76 |
| `stopped` | 10 |
| `paused` | 4 |

The 76 are **not 76 people who asked**. They are the 2026-09-23 blank-email
incident recipients, suppressed in one batch at `2026-09-25T16:30:13` as a
precaution. Do not read that number as removal requests honoured.

### Where a send path consults suppression

Three places before this lane, which is the problem rather than the answer:

1. `eligibility.must_not_contact` — the person-level question. The real one.
2. `executionguard.authorize` gate 4 — compares `eligibility.decide`'s reasons
   against `SUPPRESSION_REASONS` when minting a token.
3. `providerwrites.CONDITIONAL[EMAIL_RESUME]` — re-reads suppression from disk
   for exactly one verb, because a resume is not `facing` and therefore skips
   the guard entirely.

Entry 3 is the shape of the defect: a verb that bypassed the guard needed its
own copy of the question.

---

## 2. The 94, classified

Source: `work/review/SUPPRESSION-PROPOSAL-2026-10-12.json`, generated
2026-10-11 from the **EmailBison reply feed, fully walked, cursor exhausted,
559 inbound replies**. Status recorded in the file itself: `PROPOSAL - NOT
APPLIED. No provider write. No ledger write.`

Its own counts — `people: 94, already_on_list: 4, to_add: 90` — and I verified
the 4 independently by intersecting all 94 fingerprints against
`work/agency-dnc.jsonl`:

    overlap = exactly 4   (4 of the 94; identified by fingerprint in the gitignored artefact)

**All four are among the eleven replies the rules classifier missed.** The only
people who reached the DNC list are the ones a human read by hand. That is the
clearest available evidence that the automated path has never written a row.

### My own independent pass

I did not inherit the proposal's buckets. `work/suppression-measure/classify94.py`
re-classifies from the reply excerpts under explicit rules, with every rule
asserted against a positive *and* a negative case before any person is
classified — because a regex that silently matches nothing returns a plausible,
stable, wrong answer. (It did: an early version wrote `\x08` where `\b` belonged
and ran inert, reporting unchanged buckets.)

| bucket | n | rule |
|---|---|---|
| **suppressed** | 85 | an explicit opt-out phrase, or a bare opt-out token *leading* their own words |
| **hold** | 4 | a stop is warranted but the permanent flag needs a person |
| **needs-review** | 5 | the rules decline to decide |

The hold bucket, and why each is not a clean permanent opt-out:

| domain | reason |
|---|---|
| `HOLD-1` | company closed permanently — not a personal opt-out |
| `HOLD-2` | GDPR erasure — broader legal request than an opt-out |
| `HOLD-3` | GDPR erasure |
| `HOLD-4` | "wrong company, please remove" — may be mis-targeting, not the person |

**The 5 I cannot classify**, which is the correct answer rather than a gap:
`REVIEW-1` … `REVIEW-5` (named by fingerprint and domain in the
gitignored artefact only). Four are courteous prose that opens warmly ("Thanks for
reaching out", "I appreciate the offer") and contains a removal phrase further
in; one is `"No thx please remove"`, clear to a reader and not to a rule that
refuses to guess. A rule that suppressed on a removal phrase anywhere in prose
would also suppress "please don't remove me, I'm interested".

Per-person output with fingerprints and domains:
`work/suppression-measure/the-94-classified.json`. **Deliberately not committed**
— it carries 94 real company domains, and `work/` is gitignored because that
data is not ours to publish.

### Genuine request vs. a generic unsubscribe footer

The structural hazard is real and specific: every rendered body carries
`optout.OPT_OUT_LINE`, which literally says *"reply STOP"*. A warm top-posted
reply that quotes the original therefore contains "STOP" in its quoted tail, and
19 of the 94 were matched on `'stop'`.

Measured on this corpus: **zero footer false positives.** I searched all 94
excerpts for fragments of our own opt-out line — `0` hits — and positionally
classified every `unsubscribe`/`unsub`/`opt out`/`gdpr` match against the first
quoted-reply marker: 18 of 20 sit in the person's own words before any quote,
and inspecting the other 2 shows both are genuine (a GDPR erasure demand and a
reply opening "DNC").

**But the corpus does not exercise the hazard**, and this is the part a green
result would hide: all 94 replies arrived on operator-internal campaigns
274/327/328/352, sent by hand by named operators, *before* the OS opt-out line
existed. The footer-quoting case will first appear when Resonate OS itself
sends. My classifier strips the quoted tail before matching for exactly that
reason, and `tests/…::test_an_unclassified_warm_reply_is_not_a_permanent_opt_out`
pins the behaviour.

---

## 3. What was built

`src/suppression.py` — one consulted entry point, `suppression.decide`.

* **The BLOCK set is not reimplemented.** It calls
  `eligibility.must_not_contact`, which owns it. A second implementation of
  "has this person unsubscribed" is the one thing this file must not become.
* **The HOLD rules are new**, and are the operator's 2026-10-02 rule verbatim:
  active sequence anywhere → HOLD, last touch inside the window → HOLD, more
  than the lifetime send count → HOLD for manual review, reply unchanged.
* **Every threshold is config**, resolved per call so an edit needs no restart:
  `hold_after_last_touch_days` 30, `hold_above_total_sends` 10, `cooling_days`
  90, `hold_on_active_sequence` true. All provisional except the 90.
* **90-day cooling lifts the recency and volume holds and nothing else.** A
  removal request is not a thing that cools off; asserted both ways.
* **UNKNOWN is not a pass.** The record's event log knows only touches *we*
  made. Suppression asks about all known provider touches whoever made them, so
  `provider_touches` is an argument — and when it is absent the answer is HOLD.
  The base commit this branch sits on is titled *"an internal campaign is never
  touched, and UNKNOWN is never a pass"*; this is that rule applied to touch
  history.
* **Two scopes, one implementation.** `SCOPE_ENROL` evaluates everything.
  `SCOPE_SEND` enforces the permanent refusals and skips the holds, because
  touch history is not readable at the door without a provider call — and a
  rule that cannot be evaluated must not be reported as a hold that stops every
  send in the estate.

### The enrolment path did not pass the door, and now does

**A hole in B1, found by reading the pilotcaps lane's write-path denominator
and verifying it here.** `executionguard.revalidate` has exactly one caller,
`providerwrites._perform`. `bisonfactory._ensure_leads` writes leads with
`bison.create_lead` and `bison.attach_leads` directly — its own comment states
it "does not go through `providerwrites.perform`" — so the suppression consult
was never reached on the staging path. Measured: before this lane it consulted
the workspace killswitch, `executionscope` and `_refuse_colliding_leads`, and
asked **nothing** about whether these people had asked not to be contacted. No
`eligibility`, no `suppression`, no `agencydnc`, no `unsubscribed`.

**Being ENROLLED is not being sent to, and that is why it still matters.** The
send door would have refused the send. But EmailBison's own scheduler sends
from the campaign, and CLAUDE.md already records the lesson: the killswitch
"refuses to START an action and cannot END a campaign already running". A
suppressed person attached to a live campaign is reached by the provider, with
no gate of ours in the path.

`_refuse_suppressed_leads` now runs as the last gate before the first lead
write, at `SCOPE_SEND`, and **stops the whole run** rather than skipping the
lead — the stance `_ensure_leads` already takes for a lead missing its copy,
and right for the same reason. A lead naming a record or contact not in the
queue is refused too, because a question that cannot be asked is not answered
yes.

Four tests on `test_lead_writes_respect_the_killswitch`'s fixture, which is the
one that established this path runs end to end. Removing the call site
(`md5 0723a269 → mutated, restored byte-identical`) turns two of them red,
including the one asserting the guard was *called*. The positive control — two
clean leads created — and the unit test stay green, which is the right
discrimination.

**Still not covered by this:** the other write paths pilotcaps measured. Their
denominator is **58 write paths, 32 through the door, 26 not** — 9 in
`bisonfactory`, 17 across 9 scripts. I closed the one that enrols people. The
remaining 25 are B5's territory and are *not* claimed as covered here.

### Where it is consulted

`executionguard.revalidate`, which `providerwrites._perform` calls for every
prospect-facing write, immediately before the transport. It is asked **before**
`eligibility.decide`, deliberately: the most final question first, the ordering
`must_not_contact` already uses for the permanent operator exclusion.

Asking it second would have hidden it. `eligibility.decide` can answer
`skipped:no_such_step`, which refuses — so behind it the consult is unreachable
for exactly the records with no planned step, and a test asserting the consult
happened would be satisfied by eligibility refusing first. That is the shape of
the four controls in this repository already found unable to fail.

`providerwrites.CONDITIONAL[EMAIL_RESUME]` was also rerouted through
`suppression.decide`, so the second caller of the same question is gone.

**This changed two existing assertions**, in
`tests/test_a_stop_beats_an_authorization.py`: a stopped contact now refuses at
gate `suppression` rather than `revalidate`, with a different sentence. The
property both tests exist to protect — the write refuses and nothing is
written — is unchanged and still asserted. Only the label moved, and it moved
to something more specific.

---

## 4. The reply writer: confirmed, and worse than "no writer"

`src/inbound.py:552-554`:

```python
if own and any(o["applied"] and o["applied"]["status"] == "applied"
               for o in outcomes):
    store.save(recs, expect_digest=base)
```

The hold is **not** missing. It is computed and thrown away. On an
`unmatched`/`unknown` reply, `handle` calls
`accountpolicy.hold_for_unattributed_reply`, which calls `_hold_contact`, which
mutates `contact["paused"]` and appends a `CONTACT_HELD` event — both in the
in-memory `recs`. If no outcome in the batch is `applied`, `store.save` is never
reached and every mutation is discarded. The code comment immediately above it
reads *"AN UNATTRIBUTABLE REPLY STILL STOPS THE CADENCE TO THAT PERSON."*

Reproduced in `work/suppression-measure/repro_hold.py` — two records carrying
one address, one reply saying *"Please remove me from your list."*:

    outcome status: unmatched   why: no record for this event
    held_unattributed (computed IN MEMORY): [('example-test-a','dave'), ('example-test-b','dave')]
    example-test-a   paused=None  events=0
    example-test-b   paused=None  events=0

**The date in the brief is wrong.** "Every reply since 2026-09-25 is unmatched"
does not hold: the store carries `reply_received` events on 2026-09-25 (×3) and
2026-09-27 (×1), so those were matched and saved. The measured facts are worse
in a different way:

* **29** `reply_received` events exist in the entire 1,584-record store, spanning
  2026-09-22 → **2026-09-27**. Nothing since.
* The EmailBison feed the proposal walked holds **559 inbound replies**;
  `work/learning-replies.jsonl` holds **179,715** rows.
* The reply watcher ran **today** (`last_succeeded: 2026-10-14T17:45:48`),
  reports `healthy: true`, and shows `events_inspected: 0`,
  `new_replies_ingested: 0`, `workspaces: {}`,
  `stops: "no provider binding to stop"` — while its EmailBison checkpoint has
  advanced to `2026-10-14T08:30:56`, past the backlog it never read.

So: a healthy-looking watcher inspecting nothing, with its cursor already past
the data, feeding a writer that discards what it computes.

### Fixed — the writer now saves what it computed

`ingest`'s save condition is now `mutated_records(outcome)`, a named predicate
rather than a longer boolean at the call site, because the argument for *which*
predicates are the complete set has to be written down somewhere:

```python
applied = outcome.get("applied") or {}
return (applied.get("status") == "applied"
        or bool(outcome.get("held_unattributed")))
```

`handle` mutates `recs` in exactly two independent ways — `events.apply` when
it attributes the event, and `hold_for_unattributed_reply` when it cannot.
Everything else (the account pause, the policy effects, the queue tags) is
downstream of an early `return` at `applied["status"] != "applied"`, so those
two are the complete set rather than a sample of it.

Re-run of the original reproduction against the fix: both contacts come back
with `paused={'since': ..., 'reason': 'reply_attribution_ambiguous', 'why':
...}` and one event each. The hold reaches the disk.

**Proved by a separate interpreter, not a reload.** The defect was a mutation
that existed in one process's memory and nowhere else, and an in-process
`store.load()` can be satisfied by a cache, a module global, or the very list
object that was mutated. So
`ARemovalRequestIsWrittenAndSurvivesARestart` shells out to a fresh `python`
that imports `src.store`, reads the queue, and prints what it can see. Its
positive control asserts the child resolves the same queue the parent is
writing — without it, every assertion could be read off an empty list and pass.

Mutation: reverting the condition to `status == "applied"` alone
(`md5 594ba3fa → fd6cdb7c`, `__pycache__` wiped, restored byte-identical)
turns 3 of the 25 tests red. The attributed-removal test and the positive
control correctly stay green — that path always worked, and the discrimination
is the point.

---

## 5. `agencydnc` loses a successfully-written row

Confirmed by reproduction, `work/suppression-measure/repro_glue.py`.

`add()` appends `json.dumps(...) + "\n"`. If a write is torn — the row lands,
the newline does not — the **next** append is glued onto it, producing one line
that is two JSON objects. `load()` hits `except ValueError: continue`, commented
*"a corrupt line suppresses nobody"*. Both rows vanish: the torn one, and the
next one, which `add()` had already returned a fingerprint for and therefore
reported as written.

    add alice -> 9b04913...
    torn append for bob (no newline)
    add carol -> db5398c...   (add() returned a fingerprint = reported SUCCESS)

    rows add() claimed to write: 3
    fingerprints load() can see: 1
      alice  on list? True
      bob    on list? False
      carol  on list? False
    lookup(carol) = None

For a do-not-contact ledger, failing open on an unreadable line is the wrong
default, and the failure is silent in both directions: nothing tells the caller
the row is gone.

### Fixed, with two independent defences

**Write side — heal before appending.** `add` now checks whether the file ends
in a newline and writes one first if it does not, so a torn row cannot have the
next row glued onto it. It also `flush`es and `fsync`s: `add` returns a
fingerprint, every caller reads that as "this person is now suppressed", and
returning it while the bytes sit in a buffer a crash discards is the same false
success.

**Read side — recover, and report.** `load` no longer skips a line it cannot
`json.loads`. `_rows_in` walks the line with `JSONDecoder.raw_decode` and
recovers every object on it, so an already-glued file — which a crash before
this fix would have left, and which heal-on-write cannot help — yields both
rows. Genuinely unparseable trailing bytes are recorded rather than swallowed:
`damaged_lines()` reports them, and `load(strict=True)` refuses rather than
return a roster that may be missing somebody who asked to be removed. The
default stays lenient because `lookup` is on the send path and one damaged byte
must not take the estate down — but it is now lenient about the *bytes* while
losing no recoverable row.

The original reproduction, re-run against the fix: `fingerprints load() can
see: 3`, and `lookup(carol)` returns the suppression notice. All three rows
survive, including the torn one.

Guarded by four tests in
`tests/test_a_suppressed_address_cannot_reach_a_provider.py`, and they are
load-bearing: reverting `load` to the old skip-the-line behaviour turns two of
them red. The torn-append test stays green under that mutation, correctly — the
write-side heal alone prevents that case, so the two defences are independent
and separately covered. A positive control asserts a healthy file reports no
damage, because an empty `damaged_lines()` is also what a reader that inspects
nothing returns.

---

## 6. The mutation, performed

`tests/test_a_suppressed_address_cannot_reach_a_provider.py`, 37 tests.

Every refusal is paired with a positive control and with proof of consultation.
`suppression.consultations()` records every verdict the module answers, so a
test can distinguish *"it refused"* from *"it was never asked"* — the
distinction the four dead controls could not make.

The gate was then removed from the source, not merely stubbed:

| state | result |
|---|---|
| intact | 16/16 **OK** |
| suppression consult deleted from `revalidate` (`md5 cb11e4aa → c8397ea8`, `__pycache__` wiped) | **7 FAIL** |
| restored (md5 back to `cb11e4aa`, byte-identical, cache wiped) | 16/16 **OK** |

The decisive one, `test_the_door_consults_suppression`, fails as
`('acme','acme-1','allow') not found in []` — suppression was not consulted at
all. No other gate can satisfy that assertion, and it needs no eligible estate
to observe.

Three deliberate anti-hollowing measures, each answering a way this file could
have proved nothing:

* **The killswitch is stubbed, and that is the most important stub here.**
  `killswitch.require` refuses globally and unconditionally today — *"live
  sending is refused in code"*. Unstubbed, every assertion that a suppressed
  address cannot reach the transport would be true because the killswitch did
  all the work. That would have been the fifth dead control.
* **`eligibility.decide` is held open** in the transport tests, so it cannot
  mask suppression; the mutation then proves suppression was the only gate
  refusing.
* **The mutation test asserts the stub was called.** If the stub never ran, the
  mutation never took effect and nothing else in that test is evidence.

Positive controls in both directions, against shipped `accountpolicy`
behaviour rather than a classifier written for this lane:

* `effects(UNKNOWN)` → replier `hold`, `review: True`, never `suppress`; and
  `classify_outcome` reads the recorded classification off the event, never the
  message text, so a warm reply carrying our own opt-out wording is `UNKNOWN`.
* `effects(UNSUBSCRIBE)` and `effects(ACCOUNT_DNC)` → replier `suppress`,
  `activate_referred: False`, never `POSITIVE`.
* And the converse, so the two directions cannot collapse: `NOT_NOW`,
  `NOT_ICP`, `NEGATIVE` stop the sequence and must **not** suppress.

### Regression status

Name-set diff, standalone-vs-standalone on the same 7 modules, both sides, same
method, against a detached reference at the base SHA
(`Desktop/ref-suppression-base-2bf7b8a5`):

    base   : {test_nothing_is_supported_until_it_has_actually_worked_once}
    branch : {test_nothing_is_supported_until_it_has_actually_worked_once}
    NEW: NONE

That one failure is pre-existing on untouched `2bf7b8a57`.

**This is not the merge gate, and one larger run was discarded rather than
reported.** The 285-test figure above is a tight set — ten modules, ten
seconds, none of them binding loopback — and its result was stable and matched
the base exactly.

A second, 52-module run was taken at 21:03-21:07 UTC and **its numbers are not
reported, because they are not trustworthy**: the pilotcaps lane's reference
suite (pid 69252, detached `resonate-ops/ref-2bf7b8a57`) started 22:58:17 local
and was still running. CLAUDE.md is explicit that concurrent runs make every
result suspect, because a port collision and a half-torn-down demo estate are
indistinguishable from a real failure. Its failures were concentrated in
exactly the heavy modules that would show that (`test_preproduction`,
`test_campaign_e2e`, `test_replaysim`, `test_compliance_gate`). **That overlap
is disclosed to the pilotcaps lane in `LANE-suppression.md`, because it may
equally have perturbed their reference measurement.**

The operator's rule requires a full suite with zero new names. It is owed, and
it must be QUEUED rather than run concurrently. Conveniently, pilotcaps' run in
flight is the reference on `2bf7b8a57` — **this branch's exact base SHA** — so
that run can serve as this lane's reference once it lands, and only one further
suite (this branch's own) is needed rather than two.

---

## 6a. The provider keeps a second list, and it cannot be read

Assigned to this lane by CANARY-01 at 23:03 on 2026-10-14, after the brief
this lane started from: *"EmailBison keeps its own blacklist and stops a
sequence for anyone on it. That is a second suppression list, provider-side,
which nothing in this system has ever reconciled against ours."*

**Confirmed that nothing reconciled it**, and the reason is stronger than
oversight: **the list is not readable.** Measured, with committed evidence
rather than a claim —

| route | result | source |
|---|---|---|
| `/blocklist/emails` | **404** | `docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md:612` |
| `/blocklist/domains` | **404** | `docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md:613` |
| `/unsubscribes`, `/suppressions`, `/do-not-contact` | **404** | `scripts/reengagement_provider_confirmed.py:513` |

`src/providers/bison.py` declares no such route, so nothing in this system
*could* have read one. A list-to-list reconciliation is unavailable at any
price.

**What is readable is the EFFECT, per lead.** A lead's campaign-membership
status and its queue-row status carry the provider's own verdict —
`unsubscribed`, `opted_out`, `complained`, `blocked`, `suppressed`, and the
bounce words. So `suppression.reconcile` is per-person, over people we already
hold, and takes a status string rather than fetching one — **no provider call
is made in this lane.** The vocabulary is taken from
`reengagement_provider_confirmed.py`, which established it against the live
instance, rather than invented here; a second vocabulary for one provider's
words is how two lists come to disagree.

It is **asymmetric in what it can prove**, and the asymmetry is the finding:

| finding | meaning |
|---|---|
| `AGREE` | both lists say the same thing |
| `BLOCKED_THERE_ONLY` | the provider stopped them, we did not. We keep trying and read their silence as "no reply" — which is how a stopped person becomes a cold lead again |
| `SUPPRESSED_HERE_ONLY` | **the dangerous one.** We stopped them; the provider still has them in an active sequence, so it keeps sending to somebody who asked *us* to stop, with no gate of ours in that path |
| `UNKNOWN_THERE` | the snapshot says nothing about them |

**`UNKNOWN_THERE` is a finding, not a pass**, and that is the load-bearing
decision. Because the blacklist is unreadable, "not in what we fetched" cannot
mean "not on their list". A reconciliation that scored absence as `AGREE` would
report a clean estate while watching nothing — the shape of the six controls
already found unable to fail. Mutating that one branch to return `AGREE`
(`md5 32de76ef`, restored byte-identical) turns exactly the two absence tests
red.

A status in neither vocabulary also does **not** clear a suppression: stopped
here plus a word we have never seen is not provably safe.

**Still not done:** nobody has run this against the estate, because the
snapshot has to come from a provider read and this lane makes none. The
mechanism exists and is tested; the measurement is owed and needs your say.

---

## 7. What suppression cannot see

Stated plainly, because the suite is green and the suite does not know any of
this.

1. **The writer is fixed; the READER is still inert, and that is now the whole
   gap.** `inbound.ingest` saves what it computes (§4), so a reply that reaches
   it produces a written row. But the watcher reports `healthy: true` with
   `events_inspected: 0` and its EmailBison checkpoint already advanced to
   `2026-10-14T08:30:56`, past the backlog it never read. **So suppression
   built from replies is still blind — not because nothing persists, but
   because nothing arrives.** Two consequences worth separating: new replies
   will now be written once polling delivers them, and the backlog behind the
   advanced cursor will not be, because an advanced checkpoint is not
   re-walked. Recovering those needs a deliberate provider re-read, which this
   lane did not do. No test in this repository will ever show any of this,
   because every test supplies its own events.
2. **The 90 are still not suppressed.** This lane classified them; it applied
   nothing. Applying them is `agencydnc.add(...)` × 90 and needs the operator,
   and per the proposal's own caveat those DNCs belong in the **local** ledger
   and are never pushed to a provider.
3. **The torn-append row loss is fixed** (§5) and production is clean —
   audited with the new health check, read-only:
   `physical rows 15, fingerprints loaded 15, damaged lines NONE`, with a
   planted-damage positive control confirming the checker can actually detect
   a bad line. So no row has been lost on disk to date. What that does *not*
   tell us is whether a row was lost before 2026-10-02 and is simply no longer
   visible; an append-only ledger cannot answer that about its own past.
4. **Touch history is a stub.** `provider_touches` must be supplied by the
   caller; nothing in this lane reads it from a provider. So in practice every
   enrolment decision today answers HOLD on
   `hold:provider_touch_history_unknown`. That is the safe answer and it is not
   a working rule — the active-sequence, recency and volume HOLDS have never
   been evaluated against real provider state.
5. **`SCOPE_SEND` does not evaluate the holds at all.** At the door only the
   permanent refusals are enforced. A person in an active sequence elsewhere is
   stopped at enrolment or not at all.
6. **The reply corpora carry no text.** `work/learning-replies.jsonl` (179,715
   rows) holds only `reply_id, campaign_id, lead_id, domain, received_at,
   interested, automated` — no body, no address. Record events carry only
   `type, contact, at, id`. So the 94 could only be classified from the
   2026-10-12 proposal's stored excerpts; **nothing on disk lets this be
   recomputed from scratch**, and re-deriving it needs a provider read.
7. **The 94 are fingerprints, not addresses.** The proposal stores
   `sha256` digests by design and states the plaintext is deliberately absent.
   Applying the list is possible (the fingerprints match what `add()` writes);
   producing a human-readable list of who they are is not, from disk alone.
8. **All 94 came from operator-internal campaigns**, so the corpus cannot
   exercise the footer-quoting false positive that OS sends will create (§2).
9. **The reply-definition divergence is guarded but latent.**
   `eligibility._replied` uses `events.is_reply` (3 types);
   `account.replies`, which suppression reads, counts 5. A contact carrying only
   `reply_classified` or `positive_reply_detected` is eligible to one and
   blocked by the other. **0 of 1,381 production contacts are in that state**
   today — the two events are written as a pair. Guarded, not live, and labelled
   as such in the test.
10. **The provider's own blacklist is a second list that cannot be read, and
    has never been reconciled** (§6a). `suppression.reconcile` now exists and
    is tested, but **no snapshot has been taken**, so the asymmetry is
    currently unmeasured in the live estate. Worse than unmeasured in one
    direction: a person on EmailBison's blacklist whom we have never staged is
    **invisible** until we stage them, at which point the provider silently
    stops them and we read "no reply".
11. **Nothing here has run against a provider.** No provider call was made in
    this lane.

---

## 8. Files

| path | state |
|---|---|
| `src/suppression.py` | new, ~490 lines, incl. `reconcile` / `reconcile_all` for the provider's second list |
| `src/inbound.py` | B2: `mutated_records` replaces the `status == "applied"` save condition, so computed holds persist |
| `src/executionguard.py` | consults suppression in `revalidate`, before `eligibility` |
| `src/providerwrites.py` | `EMAIL_RESUME` condition rerouted through `suppression.decide` |
| `tests/test_a_suppressed_address_cannot_reach_a_provider.py` | new, 37 tests |
| `tests/test_a_stop_beats_an_authorization.py` | two gate-label assertions updated, §3 |
| `src/bisonfactory.py` | `_refuse_suppressed_leads` before the first lead write — the enrolment path never passed the door |
| `src/agencydnc.py` | torn-append row loss fixed: heal-on-write, recover-on-read, `damaged_lines()`, `load(strict=)` |
| `work/suppression-measure/` | measurement scripts, reproductions, the 94 — **gitignored, holds real domains** |
