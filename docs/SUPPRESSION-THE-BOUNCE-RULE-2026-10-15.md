# THE BOUNCE RULE — RULE 3 PASSED, SO RULES 1, 2 AND 4 ARE BUILT
**TASK 0120 · suppression lane · 2026-10-15 · branch
`task-suppression-bounce-RULE-2026-10-15` · trunk `1c77a06c1` ·
commits `d81307bd6`, `438e22112`**

The operator's rule of 2026-10-15 23:30
(`resonate-ops/DECISION-bounce-rule-2026-10-15.md`), implemented whole rather
than simplified. **Nothing is applied**: the branch is not merged, the twenty
watchers run the old code, and `origin/master` is untouched.

Three things in this document are worth the operator's attention before the
rest of it:

1. **Rule 3 PASSED.** An out-of-office cannot be classified as a bounce, and
   it is proven three ways rather than argued. The feature is not blocked.
2. **Rule 4 is the whole classifier, and today it classifies 98.25% of the
   estate HARD.** EmailBison states no bounce class anywhere; the fallback is
   "has this address ever accepted mail from us", and **23 of 1,313 addressed
   contacts ever have**. Rule 2 is real and it protects 1.75% of the book.
3. **There is no reversal, and that is measured rather than an omission.**
   `store.refuse_history_loss` refuses to drop an event, with no opt-out.
   Once the rule closes an address, nothing in this system reopens it. That
   makes rule 2's two survivable soft bounces the only forgiveness there is.

---

## 1. RULE 3 — THE BLOCKING CONDITION, AND IT IS SATISFIED

The operator's condition: *"If OOO classification cannot be proven separate
from bounce classification, the rule does not go live."* It can be. Measured
on `1c77a06c1` before any of the rest was written.

### 1.1 By import graph

The transitive import closure of every module that produces or consumes a
bounce is **111 modules** and contains **none** of `ooo`, `oooreturn`,
`replies`:

    leadobserve   111   ooo=False  oooreturn=False  replies=False
    adapters      110   ooo=False  oooreturn=False  replies=False
    bison         110   ooo=False  oooreturn=False  replies=False
    channels      110   ooo=False  oooreturn=False  replies=False
    eligibility   110   ooo=False  oooreturn=False  replies=False

Only **one** module in `src/` imports both halves — `src/inbound.py` — and it
is a consumer, not a classifier.

### 1.2 By classifier input

Both bounce producers decide on **provider structure** and never on a body:

| producer | what it reads | the allowlist |
|---|---|---|
| `leadobserve._email_state` | the queue row's `status` | `scheduled, sent, bounced, stopped` |
| `bison.classify_reply_row` | `event`, `type`, `folder` | `WEBHOOK_BOUNCE`, `BOUNCE_TYPES`, `folder == "bounced"` |

Neither takes a `text` argument. `ooo.detect` and `replies.classify` take
nothing else.

### 1.3 By control flow

`src/inbound.py:437` — `if not events.is_reply(...): return  # delivered,
bounced, connected`. The function returns **before** any text classifier
runs, so an event that is not a reply never reaches the words at all.

### 1.4 And structurally, for the caller actually wired

The production recorder reads the **outbound scheduled-email queue**. An
out-of-office is an **inbound reply**. It is not a row on that surface at
all.

### 1.5 What is NOT proven, stated rather than glossed

**EmailBison's own filing.** If the provider ever put an autoresponder in its
`bounced` folder, we would follow it — its status is the authority we read.
Settling that needs a probe of a real bounce row's full key set, which this
lane may not make. It is the one residual and it is upstream of every
assertion above.

### 1.6 The mutation that proves the import graph alone is not enough

Mutation **M5** wired a body check into `src/adapters.py` — `if kind ==
"bounce" or "undeliverable" in body` — **without importing anything**. The
import-graph test stayed green. Only the end-to-end out-of-office tests
caught it. That is why the control is asserted three ways and not one, and
it is the single most useful thing the mutation run produced.

---

## 2. RULE 4 — NAME THE FIELD. THERE IS NO FIELD.

**No EmailBison surface this repository reads carries a bounce code, class,
SMTP status or diagnostic field.** Re-measured from the code and the recorded
walks; no probe was made.

| surface | what a bounce carries | class? |
|---|---|---|
| queue rows (`scheduled-emails`) | `status`, one word | none |
| `/replies` | `type`, `folder` | none |
| `/events` | `EMAIL_BOUNCED`, 15 of 1,200 real events walked 2026-09-17 | none |

`hard_bounced` and `soft_bounced` exist only in **our own** allowlists —
`suppression.PROVIDER_STOPPED` and
`scripts/reengagement_provider_confirmed.py:109` — and the 2026-10-15 status
snapshot observes **0** of each. They are honoured anyway (see §3), because
the alternative is that the day the provider starts saying `hard_bounced` we
read it as "the provider did not say".

So the class is **derived from first-party data**, exactly as rule 4
instructs. The question is *has this address ever accepted mail from us*, and
the answer is an event on our own records.

### What counts as acceptance, and the number that decides everything

`EMAIL_DELIVERED` or `REPLY_RECEIVED`. **Not `PUSH_MARKED`** — EmailBison's
`sent` says it handed the message to SMTP and says nothing about a mailbox
accepting it, which `leadobserve` states twice in its own comments.

Measured on the production store, **1,584 records**:

    email_delivered events in the whole store      0
    reply_received                                29   across 23 contacts
    push_marked                                    1   against ~912 sends
    email_bounced                                  0   (the gate has never fired)

    contacts holding an address                1,313
    of those, ever accepted mail from us          23   =  1.75%

**So rule 4 classifies 98.25% of this estate HARD on a first bounce.** That
is not a defect in the rule — it is the honest size of the evidence. There
are zero `email_delivered` events because nothing produces them:
`adapters.emailbison_delivered` has no caller on the confirmed surface, and
the provider does not emit delivery. Acceptance is therefore, structurally,
"did they reply". The rule gets stronger exactly as that evidence does.

### The rule agrees with the human who went first

All **three** bounce fingerprints applied by hand on 2026-10-15 (TASK 0100)
read **never accepted**:

    0a5148a392af   ever accepted mail from us: False
    d13e93d56e31   ever accepted mail from us: False
    f38022b4e74b   ever accepted mail from us: False

Rule 4, run retroactively, reaches the same verdict a person reached by
hand. That is the closest thing to a validation set this estate has.

---

## 3. WHAT WAS BUILT

Six files, 1,468 insertions, one new module, **one** production caller and
**zero** extra provider calls.

    src/bouncepolicy.py                      NEW   the rule and its proofs
    src/events.py                            +25   EMAIL_BOUNCED_SOFT
    src/leadobserve.py                      +113   vocabulary + policy hook
    scripts/bison_watch_loop.py              +78   the one caller
    scripts/revert_bounce_suppression.py     NEW   §5
    tests/...bounce_rule_the_operator...     NEW   24 tests
    tests/...provider_bounce_reaches...     +127   15 tests (0110's, extended)

**The caller.** `_bounce_recorder` inside `bison_watch_loop`'s existing
cycle. `snapshot` has already paid for the queue read and hands the rows
over, so the recorder costs nothing — and a second reader would also be a
*smaller* read: `scheduled_rows` passes no cap, takes `bison.PAGE_CAP = 40`
and refuses any queue past 600 rows, and 491 is 665.

**The vocabulary.** `bounce`, `hard_bounced` and `soft_bounced` now fold onto
`BOUNCED` instead of falling through to `email_state_unknown` and being
reported as *"nothing has happened to anybody"*. The word is kept on
`raw_status` so the class is not lost by the folding — which is how rules 1
and 2 get a provider-stated class on the day one exists.

**The decision, per row:**

    provider said hard_bounced   -> HARD  -> EMAIL_BOUNCED,       closed
    provider said soft_bounced   -> SOFT  -> counted
    provider said bounced        -> never accepted  -> HARD,      closed
                                 -> has accepted    -> SOFT,      counted
    the 3rd consecutive SOFT     -> EMAIL_BOUNCED,                closed

### Where the soft counter lives, and why that survives a restore

**In the record's own append-only event log in `work/queue.jsonl`**, as
`EMAIL_BOUNCED_SOFT` entries, **derived on read** by
`bouncepolicy.consecutive_soft` and never stored as a number.

* **Outside `agencydnc`, as the decision requires.** `agencydnc.REASONS` is a
  closed four with no free-text field; the list could not hold a count even
  if it should.
* **No second representation.** A stored counter is free to drift from the
  log it summarises. A derivation cannot.
* **Inside the half of suppression a restore has actually been proven to
  keep.** Using `0050`'s result rather than re-deriving it: that drill ran a
  fixture estate through `scripts/server/backup.py`, restored it, and
  asserted every BLOCK row present **by name** through `src/suppression.py`,
  with a mutation dropping one row going red and naming it. Those rows were
  rows of `work/queue.jsonl` and `work/agency-dnc.jsonl`. An event on a queue
  record is inside that proof. A new counter file beside it would be in the
  half nothing has ever restored — and `0050` also named what is still NOT
  proven: the host's nightly archive and the encryption leg.

### It counts events, not polls — and that needed proving

A bounced queue row stays `bounced` for ever and twenty watchers re-read
their queues every 180s. A counter reading polls would reach three in **nine
minutes** and close an address on one soft bounce. `events.record` prevents
it, and **measurement corrected the attribution**: it refuses a repeat on
*both* `provider_event_id` and the derived `id`, and on this path the two are
**redundant** — removing either alone leaves the test green (M6, M6c) and
only removing both turns it red (M6b).

---

## 4. THE COST, IN PEOPLE

Rate re-derived, not quoted: `canary/sender-estate-export-2026-10-15b.csv`,
179 connected mailboxes, **174,579 sent, 1,766 bounces = 1.0116%**, caps
2,685/day. (Across all 181 it is 1.0106% — and the estate's `Replies` total
is also 1,771, which is a coincidence of two columns and not a column read
twice.)

| scenario | emails | **closed/period** | of which **soft-only** |
|---|---|---|---|
| whole connected estate at its caps, 5 days | 13,425 | **135.8 /wk** | 2.38 |
| real-owner mailboxes only, 1,920/day @ 0.8376% | 9,600 | **80.4 /wk** | 1.41 |
| CLAUDE.md forward book, 1,470/day | 7,350 | **74.4 /wk** | 1.30 |
| **CANARY-01 openers, ten companies** | 10 | **0.10** | 0.002 |
| CANARY-01 ten contacts, all five steps | 50 | **0.51** | 0.009 |
| CANARY-01 cohort of 23, all five steps | 115 | **1.16** | 0.020 |

Five email steps, not four: `config/clients/productive.yaml:643-676` declares
`em1..em5`.

**The soft-only column is what the rule buys, and it is small — by
measurement, not by opinion.** It is `closed × 1.75%`, and it is an **upper
bound**: an address that bounces is less likely than average to have accepted
mail from us before, so the true figure is at or below it.

**At canary volume it is zero, and exactly zero.** All ten canary contacts
were found in the store and **none of the ten has ever accepted mail from
us**, so every one of them would be classified HARD on a first bounce. Rule 2
protects nobody in CANARY-01. That is not an argument against the rule — at
0.10 expected bounces across the ten openers, the whole question is worth a
tenth of a person — but the operator asked what the difference between the
two buys, and for the canary the answer is **nothing**.

**Where it does buy something** is the estate at volume: ~2 people a week who
are known to have talked to us, who would otherwise be closed for ever by a
single full mailbox. Given §5, "for ever" is literal.

---

## 5. THE REVERSAL — THE PREMISE THAT DID NOT SURVIVE

The task asked for the reversal command verbatim, as 0100 gave one. **0100's
reversal took rows off `agency-dnc.jsonl`, a file with no history guard. This
mechanism writes an EVENT, and an event cannot be removed from a record by
any sanctioned write path in this repository.**

Measured by running it, not by reading:

    src.store.HistoryLost: this write would forget what happened or lift a
    stop nobody lifted: rec-1: 1 event(s) dropped: ev_302e8d176bd34479.
    Reload and re-apply rather than writing a stale snapshot back over it.

`store.refuse_history_loss` (`src/store.py:1400-1455`) runs inside
`store.transaction()` at line 339 and inside `store.save` at 1674 — both
sanctioned writers — and its own docstring says why there is no flag:
*"Strict, with no opt-out... If a deliberate lift is ever wanted, it should
have to argue with this function rather than slip past it."*

### The command, verbatim

Dry — the weekly report `0090` and `0110` both recommended beside a hard
rule:

    py -3 scripts/revert_bounce_suppression.py --json

Scoped to one campaign, one contact, or everything since a date:

    py -3 scripts/revert_bounce_suppression.py --campaign 492 --json
    py -3 scripts/revert_bounce_suppression.py --contact <key> --json
    py -3 scripts/revert_bounce_suppression.py --since 2026-10-16 --json

And the attempt, which **exits 1 and prints the store's own refusal**:

    py -3 scripts/revert_bounce_suppression.py --campaign 492 --apply --json

It is kept rather than removed because a reversal documented as working that
has never been run is how this project ends up with one nobody can execute.
It removes only events it can positively identify as the mechanism's own —
four-part `provider_event_id`, `scheduled_email_id` present — so a bounce
from the replies feed or a webhook is named and left alone.

### What happens to someone suppressed by a bounce that later proves transient

1. **The address is closed from the moment the event is written and nothing
   reopens it.** No decay, no expiry, no re-verification path, and per the
   above, not by hand either.
2. **Only the EMAIL channel and only that ADDRESS.** `channels._bounced` is
   keyed to the contact, so a colleague at the same company is untouched and
   LinkedIn is untouched. `nextaction` already reports
   `contact:email_bounced` and names the remedy that is actually available:
   **a new address for that person**.
3. **They are not on the agency DNC.** The mechanism never writes there — a
   row on that list is "written deliberately by a super admin, never
   derived" — so nothing about them is person-level or permanent across
   channels, and no human decision has been recorded against their name.

### The two ways to get a real reversal, and the recommendation

1. **A retraction event** — `EMAIL_BOUNCE_RETRACTED`, appended, which
   `channels._bounced` honours when it is newer than the bounce it names.
   Additive, auditable, does not fight the store.
2. **Widen the guard** to permit a removal carrying a named reason and an
   operator stamp — which is what its docstring invites.

**RECOMMENDED: 1**, gated so only this script with `--apply` can write the
retraction and only against events the mechanism itself wrote.
**NOT BUILT, and deliberately.** It is an un-suppression path that
`refuse_history_loss` cannot see, in a codebase whose suppression model rests
on stops being one-way. A lane asked for a reversal command should not be
the thing that puts a hole in that model. **One word from the operator and it
is a small change.**

---

## 6. THE BAR

**39 tests green** across the two modules. **Born red, proven by reverting
the source and keeping the tests**, three states:

| state | result |
|---|---|
| **A** every source file reverted to `1c77a06c1` | the new module cannot import; the sibling's 7 original names fail |
| **B'** the policy kept, the wiring reverted | **21 names red** — every bounce test by name, and **the five out-of-office tests GREEN** |
| **C** the change as written | **0 failing** |

Restoration after each state verified **byte-exact by sha256** on all four
source files.

**B' is the informative one.** It shows the four classes failing for the
intended reason — there is no producer — while the rule 3 control is green
before and after, which is what a control is supposed to do.

### Mutations — seven applied, each byte-exact reverted

| # | mutation | caught by |
|---|---|---|
| M1 | any bounce suppresses (the thing the task forbids) | 8 names |
| M2 | an acceptance does not reset the counter | the 2 reset tests |
| M3 | off by one on the third | 3 names |
| M4 | the other bounce words fall through again | 2 names |
| M5 | a message **body** decides it is a bounce | the 2 end-to-end OOO tests |
| M6 | drop the `provider_event_id` idempotency check | **SURVIVED** |
| M7 | the reversal reports success | 2 names |

**M6 survived and is reported rather than quietly dropped.** Two follow-up
mutations explain it: **M6c** (drop only the `id` check) also survives, and
**M6b** (drop both) turns `test_the_same_row_polled_three_times_suppresses
_nobody` and `test_two_cycles_record_one_bounce` red. The two guards in
`events.record` are redundant on this path. The test is load-bearing; a test
naming either guard alone would not be. The comment that attributed it to
`provider_event_id` has been corrected in both files.

---

## 7. WHAT IS OWED, AND WHAT IS NOT DONE

### The name-set diff that was taken instead: ZERO NEW NAMES

Every test module mentioning `leadobserve`, `bison_watch_loop`,
`EMAIL_BOUNCED`, `events.EXTERNAL`, `events.KNOWN` or `_email_state` - 32
modules - run on `438e22112` and diffed by NAME, both directions, against the
233-name reference measured in THIS tree on `9bd8648f5`:

    reference names                         233
    of those, in the modules run here        24
    failing on this commit, same modules     18
    NEW names                                 0
    names the reference carries that PASS     6

The six are exactly the born-red bounce names this change exists to turn
green, and they are verified **positively** rather than by absence: all 15
names in `test_a_provider_bounce_reaches_the_record` were watched running and
passing. Five are fixed by the producer. The sixth,
`TheSendPathRefusesIt.test_without_a_bounce_the_refusal_is_the_other_one`,
is `0110`'s `lint.forget_policies()` line - it only ever failed INSIDE a full
run, so a 32-module subset cannot confirm that one and 0110's seeded
reproduction remains its proof.

**The parser was wrong on its first run and is named here for the next
reader.** `unittest -v` prints `FAIL: test_x (tests.mod.Class.test_x)` and
the reference carries the dotted form; splitting on the first space compared
a bare method name against a path and reported **every** name as NEW. The
same shape as this lane's earlier `_parse_failures` defect, caught because
the result was implausible rather than because anything errored.

### What is owed

* **A full suite reference is OWED and not taken.** The machine-wide lock was
  held by a **live** holder — `integ/canary-nine-2026-10-15`, pid 83472,
  started 22:57:57, verified through `Get-CimInstance Win32_Process` with a
  self-check (545 processes, own pid present) — with **two** waiters already
  queued (90192, 4840). A third waiter would have started hours later and
  finished after this session ended, which is the failure the standing rules
  name. The per-module name-set diff was done instead, as the rule prescribes
  for a waiting track. **This change touches `src/` and `tests/`, so a merge
  needs its own full run against a fresh reference. There is no shortcut.**
* **Nothing is applied.** No merge, no push to master, no provider call, no
  network call, no send. `origin/master` untouched. The watchers run the old
  code and `confirm_email_touches` still has zero production callers in
  production.
* **The provider-filing residual (§1.5)** needs one read of a real bounce
  row's full key set to close.
* **The retraction path (§5)** needs one word.
* **`EMAIL_DELIVERED` has no producer**, which is what holds rule 2 down to
  1.75% of the book. Not this task's to fix, and worth naming: the acceptance
  evidence is the rule's strength, and we currently record almost none of it.
