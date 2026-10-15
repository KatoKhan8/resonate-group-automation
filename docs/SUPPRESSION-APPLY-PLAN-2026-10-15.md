# THE APPLY PLAN AND THE REVERSAL PLAN FOR THE 90

TASK 0020, suppression lane, 2026-10-15. Branch `task-suppression-2026-10-14`.

**Nothing was applied. No production `work/` state was written. No provider
call was made.** Every number below was measured in this tree or in an
isolated temporary file, and each says where.

---

## 0. The headline: the recorded apply command does not exist

Every handoff since 2026-10-12 — the proposal, `LANE-suppression.md` four
times, and `docs/SUPPRESSION-MEASUREMENT-2026-10-14.md` §7 item 2 — records
the apply step as **`agencydnc.add(...)` × 90**.

That command cannot be run. Not refused: **not executable.** Measured
2026-10-15:

    >>> agencydnc.add("email", "827c317f84021d6d…")      # a 64-hex digest
    ValueError: not a usable identifier

`add(kind, value)` takes the **plaintext** identifier and computes the digest
itself — `fingerprint()` is the only thing in the system that ever sees an
address, which is the whole privacy model. The proposal deliberately stores
`sha256` digests and no plaintext, and so does
`work/suppression-measure/the-94-classified.json` derived from it. There is
no address on disk to hand to `add`, and recovering one needs a provider
read.

§7 item 7 of the measurement doc already said *"applying the list is possible
(the fingerprints match what `add()` writes)"* — which is true, and is not
the same statement as "`add` can do it". The gap between those two sentences
is this section.

**So the apply writes the digest directly.** That is sound, and it is sound
for a specific reason rather than by convenience: the digest is the entire
key. `load()` indexes by `fingerprint` and nothing else; `kind` is **not
stored at all**; `lookup()` hashes the candidate it is handed and asks the
index. A row appended with a correct email digest is indistinguishable, to
every reader in the system, from a row `add()` wrote.

Proven end to end in an isolated file, 2026-10-15 — one row appended
directly, no `add()`, no restart, no cache flush:

    before:  lookup -> None          must_not_contact -> []
    after:   lookup -> "suppressed by agency safety policy (asked us directly)"
             must_not_contact -> ['blocked:agency_dnc']

That the proposal's digests **are** `agencydnc.fingerprint` digests is a
measurement, not an assumption: 4 of the 94 were found already on
`work/agency-dnc.jsonl`, a file only `add()` has ever written, by exact
intersection of 256-bit digests. Those 4 are precisely the 4 this plan does
not write, and they are the proof the arithmetic is right.

---

## 1. "The 90" is ambiguous, and two different readings both come to 90

This has to be settled before anything is written, because **the two sets are
not the same people.**

| reading | n | what it is |
|---|---|---|
| **A — the-90** | 90 | every person not already on the list; the proposal's own `to_add: 90` |
| **B** | 90 | the independent pass's 85 `suppressed` + 5 `needs-review` |

**Reading A is the one the operator has been asked about.** The authority is
the proposal's own counts, quoted in `SUPPRESSION-MEASUREMENT-2026-10-14.md`
line 117: `people: 94, already_on_list: 4, to_add: 90`. Confirmed in this
tree: `already_on_dnc == False` is exactly 90 of the 94 in
`the-94-classified.json`.

A is **not** this lane's 85-suppressed set. Composition of the 90, measured:

    82   bucket = suppressed      explicit opt-out phrase in their own words
     3   bucket = hold            2 gdpr-erasure, 1 company-closed
     5   bucket = needs-review    the rules declined to decide

So applying the 90 suppresses **8 people this lane's classifier did not call
a clean opt-out**. That direction is conservative — over-suppressing costs a
lead, under-suppressing contacts somebody who asked us to stop — but it is a
disagreement between two classifications and it should be made knowingly.

**Nobody in the 85-suppressed set is left out.** 82 are in the 90 and the
other 3 are already on the list. Verified by set arithmetic, not by count.

A detail that removes one decision entirely: the one `hold` the independent
pass liked least — `wrong-target`, *"wrong company, please remove"*, where
the removal may be about mis-targeting rather than about the person — is
**already on the DNC**. It is one of the 4. Nothing here has to decide it.

**Recommendation (operator's call, written down per the standing rules rather
than waited on): apply `the-90` with `--reason-undecided requested`.** The 5
undecided are, per §2 of the measurement doc, four courteous prose replies
containing a removal phrase and one `"No thx please remove"` — all five read
as removal requests to a human, and `needs-review` means *a rule* declined,
not that a reader would. A human reading them is the cheaper alternative and
is strictly better; `--set the-82` is the option that waits for it.

---

## 2. APPLY PLAN

### Which records change, from what to what, in which file

**File:** `C:\Users\Zvonimir\Desktop\resonate-group-automation\work\agency-dnc.jsonl`
— the MAIN checkout's, confirmed against
`docs/state/PROVIDER-SUPPRESSION-SNAPSHOT.json` → `provenance.agency_dnc`.

**No existing record changes.** The file is append-only and nothing is
rewritten. 90 new lines are added, each in `agencydnc`'s exact on-disk shape,
keys sorted:

    {"at": "2026-10-15T…+00:00", "fingerprint": "<64-hex>", "reason": "requested"}

**From → to**, measured against the last production audit (15 physical rows,
15 fingerprints, 0 damaged lines, 2026-10-14):

| | before | after |
|---|---|---|
| fingerprints | 15 | 105 |
| physical rows | 15 | 105 |
| damaged lines | NONE | NONE |

Per-person state change: `agencydnc.lookup(contact)` goes from `None` to
`"suppressed by agency safety policy (…)"`, and
`eligibility.must_not_contact` gains `blocked:agency_dnc`. Nothing else about
any queue record changes — **no record, contact, campaign or event is
touched**, and `work/queue.jsonl` is not opened.

**Reason categories are derived from the rule that classified each person,
never guessed.** `agencydnc.REASONS` is a closed vocabulary and the wrong
member of it mislabels why somebody is suppressed permanently.

| bucket / rule | reason | n |
|---|---|---|
| `suppressed` | `requested` | 82 |
| `hold` + `gdpr-erasure` | `legal` | 2 |
| `hold` + `company-closed` | `internal` | 1 |
| `needs-review` | operator-supplied via `--reason-undecided` | 5 |

Totals, measured in rehearsal: `{'requested': 87, 'legal': 2,
'internal': 1}`.

### In what order

Sorted by fingerprint, ascending. Not cosmetic: it makes two runs of the same
set produce identical bytes, so a diff between them is a real difference. The
`at` stamp is one value for the whole run, so the 90 are identifiable as one
batch afterwards.

### The single command

Run **from the main checkout**, not from a worktree (see the guard below):

    py -3 scripts/apply_the_90.py --set the-90 --reason-undecided requested \
        --apply --backup work/dnc-backup

Dry run first — same command without `--apply`, writes nothing, prints the
before state, the reason split and the predicted after state. `--apply`
without `--backup` is refused.

`scripts/apply_the_90.py` is new on this branch and is committed with this
document. It is the deliverable; it was exercised end to end, and it has
never been pointed at production.

### What it refuses, and why each refusal is the right failure

All fail closed. Every one was exercised.

1. **The resolved file does not exist → REFUSED.** This is the sharpest trap
   here and it does not look like a failure. `agencydnc.path()` resolves
   against `store.queue_path()`, which resolves against **this tree's**
   ROOT, and `work/` is gitignored, so every worktree has its own. Measured:
   from `wt-suppression-2026-10-14`, `path()` returns
   `wt-suppression-2026-10-14\work\agency-dnc.jsonl`, which **does not
   exist**. Unguarded, the dry run would report `before fingerprints=0`, no
   target would collide with an empty index, the apply would create a fresh
   90-row file, and the read-back would prove the name-set perfectly — a
   silent no-op reporting `APPLIED AND PROVEN`. Same root cause as the suite
   lock in CLAUDE.md, refused the same way rather than resolved cleverly.
2. **Any target already on the list → the WHOLE run stops.** Not a skip. If
   a target were already present for an independent reason, the reversal
   would delete somebody who asked to be removed before this task existed —
   the worst outcome available, worse than not applying at all. The 90 were
   measured absent on 2026-10-14 against a file that can change, so it is
   re-measured at apply time. Exercised: a second run of the same set
   refuses all 90.
3. **`damaged_lines()` non-empty → REFUSED.** A reversal cannot prove itself
   complete against a roster that cannot be fully read.
4. **The set does not resolve to its own name → REFUSED.** `--set the-90`
   that resolves to 85 people writes nothing. Exercised: without
   `--reason-undecided` it resolves to 85 and refuses, naming the 5.
5. **A fingerprint that is not 64 lowercase hex → REFUSED.**
6. **`the-94-classified.json` missing → REFUSED**, naming it. It is
   gitignored, so it exists only in the tree that produced it.
7. **`store.refuse_production_write` is called before any filesystem
   mutation**, exactly as `add` does, so the barrier still fires under test.

### Durability

Mirrors `add`: heal a trailing tear before appending (so a previous torn
write cannot glue itself to the first new row), one row per line, then
`flush()` **and** `os.fsync()`. A do-not-contact row returned as written
while sitting in a buffer a crash discards is the same false success the glue
effect produced.

### Read-back, in the command itself

The apply re-reads the file off disk and compares **name-sets**:

    NEW   (in after, not before)  must equal the 90 target digests exactly
    GONE  (in before, not after)  must be empty
    physical_rows                 must equal before + 90
    damaged_lines                 must be NONE

Any mismatch prints the reversal command and exits non-zero. Measured in
rehearsal: `NEW 90, GONE 0, 15 -> 105, damaged NONE`.

---

## 3. REVERSAL PLAN

    py -3 scripts/apply_the_90.py --revert work/dnc-backup/REVERSAL-<stamp>.json
    py -3 scripts/apply_the_90.py --revert work/dnc-backup/REVERSAL-<stamp>.json --apply

Dry run first; it prints what it would remove and keep and writes nothing.

### It is NOT a byte-restore from the backup, and that is the whole point

`agencydnc` has no remover, by design. The obvious reversal — copy the backup
back over the file — is **wrong**, and this is the single most important line
in this document after §0.

Between apply and reversal somebody may legitimately add a row: the web layer
can, and `scripts/record_self_send_exclusions.py` can. A byte-restore
silently destroys it — it un-suppresses a person who asked to be removed, and
leaves no trace that they ever did.

So the reversal **rewrites the file keeping every physical row whose
fingerprint is not in this run's manifest**, in order. The byte backup is
still taken, and is used only as the authority for the before name-set that
the reversal is proved against.

Exercised: a row was added through `add()` after the apply, then the manifest
was reverted. The foreign row was kept and **named** in the output —

    would remove  90 physical row(s) of 90 fingerprint(s)
    would keep    16 row(s)
    ARRIVED AFTER THE APPLY, kept: 1 ['c5dec4adad1206cd']

— and the read-back proved 16 fingerprints, 0 from the manifest still
present, 0 lost, 0 unexpected.

### The proof it is complete — a name-set comparison, both directions

Not a count. The reversal reloads the file off disk and reports:

| check | requirement |
|---|---|
| still present from the manifest | **0** — every digest the apply added is gone |
| GONE that should be here | **0** — `before ∪ arrived-after`, nothing lost |
| HERE that should not be | **0** — nothing gained |
| `damaged_lines` | NONE |

The fingerprints **are** the names here, so `load()`'s key set is exactly the
right primitive — but `load()` returns a dict and therefore cannot see a
duplicate physical row, so the physical row count is carried alongside it.
Measured clean reversal: `15 fingerprints, 0 / 0 / 0, damaged NONE`.

**Byte-identity as cheap corroboration.** On a reversal with nothing arriving
in between, the file comes back byte-identical to the pre-apply backup —
confirmed independently with `cmp`, not only by the script's own hash. That
check needed a fix to be worth anything: `agencydnc.add` opens in text mode
without `newline=`, so the real `work/agency-dnc.jsonl` is **CRLF** on
Windows (measured). A reversal writing `"\n"` reads back identically —
`load()` strips — while changing every line in the file, which would have
made a byte-comparison permanently useless. The reversal now writes the same
bytes `add` does.

### Reversal refusals

- The manifest names a different file than this tree resolves to → REFUSED.
- `damaged_lines()` non-empty → REFUSED.
- The same wrong-tree guard as the apply.

### What a reversal does not undo

Nothing else is written, so there is nothing else to undo — but say it
plainly: if anything was *acted on* while the suppression stood (a cohort
re-selected around it, an enrolment refused and re-planned, a sweep issued),
reversing the list does not reverse that. The list is reversible; decisions
taken in its presence are not.

---

## 4. BLAST RADIUS

Every reader of these records, traced by import graph and call site in this
tree, and what each does differently afterwards.

**Scope of the live effect, measured: currently latent.** The 90 digests were
intersected against `docs/state/PROVIDER-SUPPRESSION-SNAPSHOT.json`'s 749
staged-lead email fingerprints — **0 overlap** (94 × 749 is also 0). So none
of the 90 is in the snapshot of people staged at EmailBison.

**That is not a clean bill of health, and absence proves nothing here.** The
snapshot is built by joining our queue's contacts to provider stage files; it
covers the staged estate, not the queue. **Whether any of the 90 holds a
queue record is UNKNOWN.** The authority is
`C:\Users\Zvonimir\Desktop\resonate-group-automation\work\queue.jsonl`, which
the standing rules put out of bounds for this task, so it was not read and no
number is guessed. It is one read-only command and belongs in the pre-apply
step:

    py -3 -c "import json,sys; sys.path.insert(0,'.'); from src import agencydnc, store; \
      t={p['fingerprint'] for p in json.load(open('work/suppression-measure/the-94-classified.json'))['people'] if not p['already_on_dnc']}; \
      hits=[(r['id'],c.get('key')) for r in store.load() for c in (r.get('contacts') or []) \
            if t & set(agencydnc.keys_for(c).values())]; \
      print(len(hits),'of 90 hold a queue record'); print(hits[:20])"

Run from the main checkout. If that prints 0, everything below is armed for
future imports and changes nothing today. If it prints more than 0, items 2,
4 and 6 are live and should be read before applying.

### No consumer sends more. The three that behave differently are named.

| # | consumer | call site | after the change |
|---|---|---|---|
| 1 | `eligibility.must_not_contact` → `_suppressed` → `agencydnc.lookup` | `eligibility.py:363` | returns `blocked:agency_dnc`. **The root.** Read from disk on every call, no index passed, so it takes effect with no restart and no cache to flush — proven. |
| 2 | `nextaction.decide` | `nextaction.py:521`, `750` | `blocked:agency_dnc` is in both `TERMINAL_CONTACT_REASONS` and `ACCOUNT_TERMINAL_REASONS`, and the `account_terminal` loop runs **before** candidate selection → `STOP / suppressed` for the **whole company**, not just the person. Strictly fewer. |
| 3 | `eligibility.decide` | `eligibility.py:756` | `BLOCKED` instead of a step. Fewer. |
| 4 | `bisonfactory._ensure_leads` → `_refuse_suppressed_leads` → `suppression.decide` | `bisonfactory.py:2497`, `2054` | **the WHOLE enrolment run refuses**, by design — "a cohort quietly short by one is a cohort nobody notices is wrong". Fewer, but loud: a cohort containing one of the 90 stops dead and will look like a breakage. |
| 5 | `executionguard.revalidate` → `suppression.decide` | `executionguard.py:1071` | the send door refuses; `blocked:agency_dnc` is in `SUPPRESSION_REASONS`. Fewer. |
| 6 | `providerwrites.CONDITIONAL[EMAIL_RESUME]` | `providerwrites.py:1482` | a resume refuses when **any** contact on **any** record the campaign names is suppressed. Relevant to 487 / 489 / 493: applying the 90 can only make those resumes harder to pass. Fewer. |
| 7 | `leadstop.sweep` → `_must_stop` | `leadstop.py:345` | **more provider STOP writes** — see the loud item below. No sends. |
| 8 | `heyreachfactory.ensure_leads` | `heyreachfactory.py:1225` | refuses the LinkedIn push. Fewer. |
| 9 | `hygiene.check` (agency index) | `hygiene.py:374` | verdict `agency_suppressed` → action `suppress`. |
| 10 | `web/upload.parse` import preview | `upload.py:307`, `app.py:1275` | the row is **labelled, not dropped** — deliberate, so the operator can read why ("a suppressed company reaches this function by design", `upload.py:560`). The record still imports; the send gates refuse. A gap, not a leak. |
| 11 | `web/api.py` hygiene/screen routes | `api.py:6304`, `6364` | the screen reports suppressed. Read-only. |
| 12 | `referral.resolve` promotion | `referral.py:284` | a referred person on the list is `SUPPRESSED` instead of `READY` — the promotion path stops. Fewer. |
| 13 | `operatorexclusion.origins` | `operatorexclusion.py:661` | reports a `COMPLIANCE` origin for the record. Read-only. |
| 14 | `suppression.reconcile` / `reconcile_all` | — | **zero callers in `src/` or `scripts/`.** Unchanged by this, and still inert. |
| 15 | `scripts/build_control_cohort.py` | line 153 | the substitution effect — below. |

### Checked specifically for a send-more path, and it is not there

- **Account concurrency does not free a slot.** The plausible mechanism was
  `fatigue.account_check`'s `max_active_contacts`: block one person, open
  another. It does not happen. `active` is derived from `confirmed_touches`
  and account state (`ACTIVE`/`ENGAGED`/`STOPPED`) — `fatigue.py:243` — and
  is **blind to eligibility and to the DNC**. A suppressed contact with
  touches still occupies its slot. Nothing in `account.py` reads `agencydnc`.
- **And it could not matter anyway**, because `nextaction` returns
  `STOP / suppressed` for the whole account (item 2) before any candidate is
  selected.
- **`channels.evaluate` never reaches the agency list** —
  `channels._suppressed` is a different function, domain-level only. Not a
  defect: `nextaction` asks `must_not_contact` at step 1, before channels at
  step 2.
- **The import path adds no send** (item 10): the record lands, the door
  refuses.

### LOUD — the one effect that creates new outbound activity

**`leadstop.sweep` would issue provider STOP writes.** Each of the 90 that
holds a staged lead becomes `_must_stop` with `blocked:agency_dnc`, and a
sweep run with `live=True` calls `stop_email_contact` / `stop_linkedin_contact`
against the provider.

Those are **provider writes**. CLAUDE.md records that provider writes from
this system remain **0**, and the 2026-09-26 production freeze covers
provider attachments and campaign state changes. Stopping somebody who asked
to be stopped is the *correct* write and it is still a write that has never
been performed, under a freeze, needing the operator's explicit `APPROVED`.

Measured mitigation: the overlap with the staged snapshot is **0**, so no
such write is currently reachable through it — but the queue overlap is
UNKNOWN (above), and `sweep` defaults to a dry run. **Do not run
`leadstop.sweep --live` as part of applying this list.** Applying the list
and sweeping the provider are two decisions; this plan is only the first.

### LOUD — the one substitution effect

`scripts/build_control_cohort.py` selects by **taking the first `limit`
eligible contacts** (`clear_of_collision(chooser, limit, …)`), after
filtering on `must_not_contact`. Removing 90 people from the eligible stream
does not shrink the cohort — **it moves the cut line down, and admits people
who would have been below it.**

Stated precisely, because the task asks for "sends MORE" and this is not
that: **total volume is unchanged** (the limit binds), but **the composition
changes**, and somebody gets contacted who would not have been. It is not a
defect — a cohort built around a do-not-contact list is the correct
behaviour — but any cohort built before the apply and shipped after it is a
**different cohort than the one that was reviewed**, and that is worth
catching before it is noticed afterwards.

**Recommendation: rebuild any unshipped cohort after applying, and re-review
it.** Hold at Batch 01 either way, per the standing rules.

### One performance note, not a safety one

`operatorexclusion.origins` calls `agencydnc.lookup(contact)` **with no
index**, inside a per-contact loop, and `lookup` calls `load()` when given
none — so it re-reads the whole file once per contact. The file goes 15 → 105
rows, a 7× growth. Irrelevant at this size; it becomes real if this list ever
reaches thousands. Filed, not fixed — it is outside this task.

---

## 5. Pre-apply checklist, in order

1. Run the queue-overlap command in §4. Record the number.
2. `py -3 scripts/apply_the_90.py --set the-90` (no `--apply`) **from the
   main checkout**. Confirm `before fingerprints=15`, `damaged_lines=NONE`,
   and that the path is `resonate-group-automation\work\…`. A `before` of 0
   means the wrong tree — the guard refuses, but read the path anyway.
3. Decide §1: `the-90 --reason-undecided requested`, or `the-82` and send the
   5 to a human. Recommendation above.
4. Apply with `--backup`. Read the read-back block; it must say
   `APPLIED AND PROVEN BY NAME-SET`.
5. Keep the manifest. It is the only thing that makes the reversal provable.
6. Do **not** run `leadstop.sweep --live`. Do **not** resume 487 / 489 / 493.
7. Rebuild and re-review any unshipped cohort.

---

## 6. What this task did not do

- **Applied nothing.** Production `work/` was not written. The only
  production-path read was `docs/state/PROVIDER-SUPPRESSION-SNAPSHOT.json`,
  which is committed, and `the-94-classified.json`, which is this
  worktree's own gitignored scratch.
- **Made no provider call.**
- **Did not read `work/queue.jsonl`** — standing rules — so the queue overlap
  is UNKNOWN with the authority named, rather than estimated.
- **Did not re-derive the 94.** The reply corpora carry no text
  (`SUPPRESSION-MEASUREMENT-2026-10-14.md` §7 item 6); re-deriving needs a
  provider read.
- **Did not resolve the 5 `needs-review` people.** A rule that would decide
  them would also suppress "please don't remove me, I'm interested". They
  need a reader, and `--reason-undecided` is where a reader's decision goes.
- **Did not change a threshold, a gate, a cap or `src/`.** The only files
  added are this document and `scripts/apply_the_90.py`.
