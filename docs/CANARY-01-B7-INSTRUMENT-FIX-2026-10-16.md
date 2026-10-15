# CANARY-01 — the B7 instrument that passed while seeing nothing, fixed

TASK 0190 (pilotcaps). 2026-10-16.
Branch `task-pilotcaps-b7-control-2026-10-16`, commit of the fix `6a6665f45`,
parent `cc112ae60` (`integ/canary-nine-2026-10-15`).
Measured in a fresh worktree `resonate-trees\wt-pilotcaps-b7-2026-10-16`,
created off `cc112ae60`, **LF line endings** (`requirements.txt` CR=0, 797 B),
which matches `wt-integ-nine-2026-10-15` and therefore the reference this
branch is diffed against. `origin/master` untouched at `b1f290c84`; nothing
pushed to master, nothing merged, nothing attached.

**No provider call of any kind was made.** 0180's authorisation (operator,
2026-10-15 23:00, one GET walk of `/sender-emails`) is spent and did not carry.
Everything below is the 13 page bodies 0180 captured, replayed from disk.
Their digest in page order is byte-identical to the one 0180 recorded:

    2c928a2652fd2c414976f83dfb8bddd5701e4dbdbfbb20b1512c8470a9107439

---

## 0. THE ANSWER IN ONE TABLE

The same 181 rows, the same cassette, the same process. Nothing differs but
the instrument:

    OLD  tests/...pools_owner.py @ cc112ae60   run=1 failures=0   *** REPORTED OK ***
    NEW  the same file @ 6a6665f45            run=1 failures=1   169 of 181, each id named

The old leg's own arithmetic on the real estate:

    AS THE OLD INSTRUMENT READ IT  : {'no-owner': 181}  -> mismatch == 0 -> ok
    AS THE FIXED INSTRUMENT READS IT: {'mismatch': 169, 'match': 12}

**And the pool's ten all agree with their signatures.** Criterion 7's string
comparison holds on the pool, by the ladder, on provider bytes — which is what
0180 concluded by a different route and is now reproducible from an instrument
that can be shown to go red.

Replay harness and full output (clear-text, so outside git):
`resonate-ops\pilotcaps-b7-0190\replay_0190.py`, `replay-0190.out`,
`old_instrument.py` (the pristine `cc112ae60` copy, sha256 `f3e28cdbb564fa…`).

---

## 1. THE FIELD — `email_signature`, proven by name from the 181 rows

Key-set over **every** row, not a sample, not an inference. 24 distinct keys,
each present on all 181:

    bounced_count created_at daily_limit email email_signature
    emails_sent_count id imap_port imap_server interested_leads_count name
    smtp_port smtp_server status tags total_leads_contacted_count
    total_opened_count total_replied_count type unique_opened_count
    unique_replied_count unsubscribed_count updated_at warmup_enabled

    'email_signature'  present on 181 of 181 rows
    'signature'        present on   0 of 181 rows
    'Signature'        present on   0 of 181 rows

Both keys the old instrument read are **absent from the entire estate**. The
field name now lives in one constant, `PROVIDER_SIGNATURE_FIELD`, and a row
that does not carry it raises `SignatureFieldMissing` instead of being
classified — because reading a key the provider does not have returns `None`
silently, and `None` read as "no attested owner" is the whole defect.

## 2. THE REGEX — one shape, 181 of 181, and the old pattern matches none of it

Every captured signature reduces to exactly one shape. There is no second form:

     181  '<p>TEXT<br>TEXT</p>'

    the OLD pattern  <p[^>]*>([^<]+)</p>   matches   0 of 181
    the NEW pattern  \A<p[^>]*>\s*([^<]+?)\s*<    reads 181 of 181

`[^<]+` stops at the `<br>`, so `</p>` never follows: **the old pattern fails
on the only shape it will ever see, even given the right field.** Either defect
alone was sufficient.

The replacement terminates the owner on *any* tag rather than on `</p>`, and is
deliberately not a general HTML parser and not looser than the measured shape —
the operator's 2026-10-15 decision is that a loose matcher passes spellings it
must not. Anything that is not this shape is **UNREADABLE**, not re-read by a
fallback.

## 3. RUNG 0 — UNKNOWN is no longer spelled "ownerless"

The ladder gains one rung ahead of the operator's four, and it is the reason
the rest of the fix holds:

    0. an owner is attested but this code cannot read it  ->  "unreadable"

"Ownerless" is a **fact about a mailbox** — two real ones carried no signature
at all in the 09-21 export. "I could not read the signature this mailbox
carries" is **not that fact**; it is the absence of a reading. Collapsing the
second into the first is precisely how an instrument passes while seeing
nothing. They are now separate rungs and the caller refuses on rung 0.
Invariant 0: an unreadable authority means UNKNOWN, and UNKNOWN never becomes
PASS.

Measured apart, because the distinction is the point:

    ""  /  "   "  /  "<p></p>"  /  "<p> </p>"      no text at all  -> no-owner
    "<p><br>Productive</p>"                        text, empty slot -> unreadable
    "Ada Lovelace<br>Productive"  (no wrapper)     text, no match   -> unreadable

Both refuse. They refuse with *different reasons*, which is what a reader needs.

## 4. THE LADDER IT CLAIMED TO USE

The old leg re-implemented the classification inline, so *"classifies under the
same ladder"* was the name of the test rather than a fact about it. It now
calls `classify()` through `classify_provider_rows()`, and the judgement is one
function, `refuse_unless_one_owner()`, with four refusals in order:

1. `unreadable > 0` — UNKNOWN.
2. **nothing observed** — zero rows reached an equality test, so "no mismatch"
   is a statement about this code and not about the estate.
3. `no-owner > 0` — a mailbox with no attested owner can never satisfy the
   one-owner rule, so it refuses rather than being outvoted.
4. `mismatch > 0` — the question the instrument exists for.

Refusal 2 is the only **positive** member: the other three ask *did I find
something wrong*, and it asks *did I see an owner name at all*. That is exactly
the question the old instrument never asked.

The live leg also now asserts `len(rows) == meta["total"]` before classifying.
Completeness is not implied by agreement: 181 of 225 rows all attesting one
owner says nothing about the other 44.

---

## 5. THE POSITIVE CONTROL — and its first version was the defect again

`ThePositiveControlForTheLiveLeg`, 13 tests. Each one runs **the gated
method's real body**, with the walk injected and `bison.sender_emails`
replaced, so no transport, URL or credential is reachable, and the stub's call
count is asserted — a stub that is never called is itself a control that sees
nothing.

**The first version of this control was the same defect, rebuilt.**
`unittest.skipUnless` replaces the method with a wrapper that raises
`SkipTest` *when called*, so calling the method directly made all seven cases
report as **skipped** and the run said `OK (skipped=8)`. A control that skips
is a control that cannot go red. The body is now reached through
`inspect.unwrap` (the documented way to follow `functools.wraps`'
`__wrapped__`), and both halves of that arrangement are pinned by
`test_the_live_leg_is_still_gated_and_its_body_is_reachable`: the live read
must stay behind the env var, **and** the control must still be able to reach
the body. If either changes, that test fails loudly instead of seven cases
going quiet.

### Twelve mutations, every one killed by a named test

Measured with `PYTHONDONTWRITEBYTECODE=1`, source restored **byte-identical**
(sha256 `7268f7b9bf2279c681b7d0d42357094bfca95fc34c7b01509fd87f4182a65352`)
after each. Baseline: `Ran 39 tests — OK (skipped=1, expected failures=4)`.

| mutation | killed by |
|---|---|
| M1 field back to `signature` | `test_a_row_carrying_only_the_old_field_is_a_loud_refusal`, `test_the_whole_old_defect_cannot_report_ok` |
| M1b missing field returns a row instead of raising | the same two |
| M2 regex back to the old pattern | `test_the_pattern_the_old_instrument_used_reads_nothing_here`, `test_the_measured_shape_yields_the_owner_name`, `test_an_estate_of_one_owner_passes`, `test_one_differing_owner_turns_the_live_leg_RED_and_names_it`, `test_an_empty_signature_is_ownerless_and_still_refuses` |
| M3 drop the `unreadable` rung from `classify` | `test_a_block_with_text_but_no_name_slot_is_unreadable`, `test_an_unreadable_signature_is_refused_not_counted_ownerless` |
| M3b never mark a row unreadable | the same two |
| M4 drop the nothing-observed seal | `test_the_nothing_observed_seal_refuses_on_its_own` |
| M5 stop refusing a partial walk | `test_a_partial_walk_is_refused_even_when_every_row_matches` |
| M6 drop the `no-owner` refusal | `test_an_empty_signature_is_ownerless_and_still_refuses` |
| M7 drop the `mismatch` refusal | `test_one_differing_owner_turns_the_live_leg_RED_and_names_it` |
| M8 drop the `unreadable` refusal | the two rung-0 tests |
| M9 live leg back to `assertEqual(mismatch, 0)` | five of them |
| M10 the gate on the live read removed | `test_the_live_leg_is_still_gated_and_its_body_is_reachable`, and the leg itself errors |

**M4 was UNKILLED on the first pass, and that is a finding about the fix, not
about the mutation.** Deleting the nothing-observed seal broke no test, because
every walk that observes nothing also trips rung 0 or the no-owner rung first —
the seal was shadowed and therefore removable by accident. It is kept, for the
reason given in §4, and tested at its own level by
`test_the_nothing_observed_seal_refuses_on_its_own`, which also exercises
`export-limited` so that the next version of the defect — a verdict label added
to the ladder and forgotten in the refusal list — is caught.

**A measurement hazard worth recording.** The first mutation batch reported M7
killed by the wrong test. Cause: M6 and M7 replace conditions of *identical
length*, so the two mutated files had the same size, were written inside one
mtime tick, and Python reused M6's `__pycache__` for M7. Every number above was
re-measured with bytecode writing disabled. A mutation harness that lets the
interpreter cache is measuring the previous mutation.

---

## 6. THE REPLAY — what the 181 rows say now

    walk: rows=181  meta.total=181  per_page=15  last_page=13
    transport: replayed 39 (13 pages x 3 walks), dialled 0, asserted 0

    expected px (the config's sender.name) = px-fc7d1255b8a3
    verdicts: {'mismatch': 169, 'match': 12}
    distinct owner px in the live estate: 11

      px-387dd1f77205  x61        px-fc7d1255b8a3  x12
      px-19834114d0e7  x41        px-894888e9f1c3  x6
      px-494dc227d91e  x17        px-2f1dd920a186  x5
      px-c82dcaabaec1  x17        px-d065203e066c  x3
      px-7513d195dfb1  x17        px-40bfd9825a08  x1
                                  px-e7b9ecb0a51e  x1

`no-owner` is **0** and `unreadable` is **0**: every one of the 181 mailboxes
attests a readable owner. The 169 are not a defect in the estate — they are
other people's mailboxes, correctly identified as such for the first time.

### The pool of ten, and the reserve — all twelve agree

    2763  match  px-fc7d1255b8a3  Connected  daily_limit 15
    2760  match  px-fc7d1255b8a3  Connected  daily_limit 15
    2751  match  px-fc7d1255b8a3  Connected  daily_limit 15
    2750  match  px-fc7d1255b8a3  Connected  daily_limit 15
    2778  match  px-fc7d1255b8a3  Connected  daily_limit 15
    2772  match  px-fc7d1255b8a3  Connected  daily_limit 15
    2748  match  px-fc7d1255b8a3  Connected  daily_limit 15
    2745  match  px-fc7d1255b8a3  Connected  daily_limit 15
    2741  match  px-fc7d1255b8a3  Connected  daily_limit 15
    2775  match  px-fc7d1255b8a3  Connected  daily_limit 15

    distinct owner px across the ten: 1 -> ['px-fc7d1255b8a3']
    pool_owner() = px-fc7d1255b8a3
    reserve 2757, 2766: both match, same single px, both Connected, limit 15

So **the answer to the brief's fourth question is yes**: the pool's ten agree
with their signatures, under NFC-exact, on provider bytes, and the offline
pool primitive returns the config's own px rather than refusing.

---

## 7. A MEASURED CORRECTION TO 0180's FRAMING

0180 wrote: *"Had the one authorised provider read been spent by simply setting
that variable, criterion 7 would have been recorded MET."* The instrument was
blind — that stands, and §0 now proves it by direct A/B. But the path from
*set the variable* to *MET recorded* has one more step than that sentence
implies, and the operator should have the exact shape of the risk:

    B7_LIVE_ESTATE=1 py -3 -m unittest tests...TheLiveRead
      -> ERROR: src.providers.MissingKey: no BISON_KEY in config/.env

`tests/__init__` is a credential firewall: it points `providers.ENV_FILE` at a
path that cannot exist and pops every key variable at package import. So the
gated leg **cannot dial from inside the suite** — it dies naming a missing key.
The vacuous pass needs a credential present in the process past that firewall,
which is what a replay (0180's, and this one's) supplies, and which is also
what anyone would have supplied next after seeing `MissingKey` and "fixing" it.
The firewall bought one step of warning, not safety. Nothing here relies on it:
the replay refuses any method or URL it holds no capture for and any request
carrying a body, and `_urllib_transport` is replaced by a raiser that is
asserted never called.

---

## 8. WHAT CRITERION 7 STILL NEEDS — the order, not a question

**Criterion 7 is NOT MET, and the remaining blocker is construction rather
than information.** 0180's verdict stands and this task does not move it: the
criterion is *"one owner across the **attached** pool"*, and nothing is
attached — no campaign exists, and `docs/CANARY-01-EXIT-CRITERIA-AUDIT-2026-10-15.md`
§7 records that the per-campaign form of the check does not exist and cannot be
run. For criterion 7 to be MET, three things must become true **in this order**:
first the instrument must be able to fail, which is what this commit delivers
and what the twelve mutations and the `inspect.unwrap` control demonstrate;
second a campaign must exist with that pool of ten actually attached, and the
attach must be read back from the provider rather than assumed, because
`providers/bison.py campaign_senders` returns membership **ids only** and
answers no question about who owns them; and third the check must be run in its
**per-campaign** form — `pool_owner()` over the senders the provider reports
for *that* campaign id — and return one px, with zero `unreadable` and zero
`no-owner` rows, which the pool-of-ten numbers in §6 say it will. The string
comparison is settled. The attachment is not, and the measurement cannot
precede the thing it measures: **fix the instrument, attach, then measure.**

Two things carried from 0180 and deliberately not acted on here. The
attestation binding the pool's owner sits on **eb-2738, which has left the
estate** — 2738 is not among the 181 rows — so 0180's recommendation to
re-attest on 2763 remains the operator's to approve; note that 2763 now
classifies `match` on provider bytes, which is evidence *for* that
recommendation but is not the attestation. And the endpoint carries **no owner,
creator, user, team or tenant field and no campaign membership**, so
`glm-c/0150`'s shared-estate check — none of the ten already in another ACTIVE
campaign — is still **not answerable** from it, and the standing 2026-10-15
23:45 rule it enforces depends on a read nobody has approved.

---

## 9. SCOPE, AND THE ONE FILE FROM ANOTHER LANE

One file was changed: **`tests/test_every_body_is_signed_by_the_pools_owner.py`**
(+493 / −11). It originates on `task-glm-review-2026-10-14` (the GLM lane) and
reached this lineage through `integ/canary-nine` merge M4. It was unavoidable:
the defect **is** that file, the task names it, and the fix needs the field,
the pattern, the ladder and the control to change together or it would ship a
reader whose control still cannot fail. No other lane's worktree was entered —
the work was done in a worktree created for this task off `cc112ae60`, so
`wt-glm-review-2026-10-14` and `wt-integ-nine-2026-10-15` were read and never
written. `integ/canary-nine-2026-10-15` still points at `cc112ae60`.

Hygiene: no name in clear. px values and ids only, abstract names
(`Ada Lovelacé`) in the controls, and the config's spelling read at runtime
through `clients.sender_identity` and never written into the file. The staged
diff was scanned for the client's surnames: zero hits.

## 10. TEST EVIDENCE

    module alone, this branch   Ran 39 tests - OK (skipped=1, expected failures=4)
                                (was 26 at cc112ae60; skipped=1 is the gated leg)

    five related modules, name-set A/B on the same tree and SHA:
      tests.test_fixture_hygiene
      tests.test_every_body_is_signed_by_the_pools_owner
      tests.test_the_signoff_name_is_the_mailbox_owners_full_name
      tests.test_sender_ownership
      tests.test_ownership_is_resolved_per_provider_not_by_a_set

      BEFORE (cc112ae60)  Ran 73 - FAILED (failures=5, skipped=1, expected failures=4)
      AFTER  (the fix)    Ran 86 - FAILED (failures=5, skipped=1, expected failures=4)
      NEW FAILING NAMES: none.   GONE: none.

The 5 are pre-existing and none is mine: four are `test_fixture_hygiene`
reporting the test identity named outside its two exempt files
(`scripts/record_self_send_exclusions.py`, `src/operatorexclusion.py`,
`tests/test_autonomous_production_is_not_a_self_stamp.py`,
`tests/test_we_are_never_our_own_recipient.py`), all untouched here.

**Full-suite reference, per the 2026-10-02 merge rule** (a change under
`tests/` always gets a new reference): the reference on the parent `cc112ae60`
is the `wt-integ-nine-2026-10-15` run of 2026-10-15 23:55 — `status=FAIL`,
`failures=294`, `failures_are_partial=False`, `wall_seconds=3456.1`, same LF
tree class. The branch's own full run is recorded in §11.

## 11. FULL SUITE ON THIS BRANCH

Pending at the time of writing; appended below when the run ends. Launched
`py -3 scripts/run_suite.py` (no flags — `-v` is not an option of that script
and it already passes `-v` to `unittest discover` internally; the stale
`suite_verdict.txt` and `suite_run.log` were deleted first, because a stale
verdict reads exactly like a finished run). Output:
`resonate-ops\pilotcaps-b7-0190\suite-0190.out`.
