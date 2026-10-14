# §6a measured: the blacklist is still unreadable, the effect is not, and the
# reconciliation has no caller

TASK 0010. Lane `task-suppression-2026-10-14`, worktree
`Desktop/wt-suppression-2026-10-14`, on top of `d7e09f9aa`.

**No provider call was made.** Every byte below came off disk. Nothing was
written to a provider, no campaign was touched, nothing was resumed or
activated, and no local suppression was applied. `UNKNOWN_IS_NOT_A_PASS` is
still `True` and nothing here changed it.

---

## 0. The answer to the question asked first

**The provider's blacklist CANNOT be read from what is on disk. Not partially,
not stalely — the list does not exist anywhere in stored state.** That is the
finding and it is the same finding §6a already recorded, now checked rather
than cited:

| checked | result |
|---|---|
| `/blocklist/emails`, `/blocklist/domains` | **404**, `docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md:612-613` |
| `/unsubscribes`, `/suppressions`, `/blocklist`, `/do-not-contact` | **404**, `scripts/reengagement_provider_confirmed.py:512-513` |
| any blacklist route in `src/providers/bison.py` | **none declared** — grep for `blocklist\|blacklist\|unsubscribes\|do-not-contact` returns two comment lines and no route |
| any stored file naming a provider blacklist, blocklist or suppression list | **none** |

**What authority would supply it:** only EmailBison itself, and only through a
route it does not expose. There is no second source. ContactOut, Reoon and
Deliverable answer *deliverability*, which is a different question and already
shown below to disagree with the provider's own send result. A list-to-list
reconciliation is unavailable at any price, exactly as §6a says.

**A per-lead snapshot of the blacklist's EFFECT can be assembled, and was.** It
is not the list and it is not a substitute for it; §6a is built for precisely
this and takes a status string rather than fetching one. 749 addresses. What it
can and cannot witness is §2.

---

## 1. The snapshot, and where every entry came from

`scripts/suppression_snapshot.py`, new. Two artifacts, because one of them
holds real addresses:

| artifact | contents |
|---|---|
| `work/suppression-measure/PROVIDER-SUPPRESSION-SNAPSHOT-FULL.json` | plaintext addresses, per-person findings. **Gitignored**, like the rest of `work/` — 1,584 real companies' people, not ours to publish. |
| `docs/state/PROVIDER-SUPPRESSION-SNAPSHOT.json` | `agencydnc.fingerprint` digests, counts, provenance. Committed. Scanned: **0 occurrences of `@`.** |

Six sources, every one stat'd before it was read:

| file | mtime (UTC) | rows | status pairs | witness |
|---|---|---|---|---|
| `stage/pc-leads.jsonl` | 2026-09-24T18:12:20 | 2,111 | 4,766 | campaign membership |
| `stage/pc-sends.jsonl` | 2026-09-24T18:12:21 | 9,454 | 9,454 | queue row |
| `stage/pc-lead-sends.jsonl` | 2026-09-24T18:27:49 | 20,221 | 20,221 | queue row |
| `stage/reengagement-inventory.jsonl` | 2026-09-23T21:05:31 | 2,081 | 2,081 | campaign membership |
| `lead-observations.jsonl` | 2026-09-13T09:28:53 | 2 | 1 | lead observation, keyed on email, no join |
| `work/queue.jsonl` | 2026-10-03T20:41:37 | 1,584 | — | the join key |

0 damaged lines in any of them. 0 declared sources absent.

**A MISSING SOURCE FAILS THE RUN.** `store.read_jsonl` answers a missing file
with an empty list, which would turn "the file is gone" into "nobody is
suppressed there" — invariant 0. The refusal is not theoretical: the first run
of this script resolved `work/` to **this worktree's** (empty) one, because
`store.main_checkout_work()` returns `None` when `git rev-parse` fails, and it
was failing on a broken `GIT_CONFIG_VALUE_0` in the environment. The script
refused by name instead of reporting a clean estate of zero.

### The join, and its ceiling

The stored provider rows carry a lead id and **no address**; the queue's
contacts carry both. `bison_lead_id` is the join.

    contacts in the production queue        1,381
      carrying an email                     1,313
      carrying a bison_lead_id                805
      joinable (both)                         805
    provider lead ids in stored state       2,081
      joined to an address                    749
      WE CANNOT NAME                        1,332
    addresses in the snapshot                 749

**1,332 of the 2,081 lead ids the provider has told us about cannot be turned
into a person.** They are leads at EmailBison we hold no queue contact for.
That is not a gap this join can close and no provider read would close it
either — it is the asymmetry §6a names from the other end: *a person on their
blacklist whom we have never staged is invisible.*

### Everything deliberately excluded, and why

* `work/collision-index.json`, `work/stage/s6-collision-walk.json`,
  `work/validation/emailbison-collision-sweep.json` — keyed on **domain**.
  `reconcile_all` keys on email because that is the identifier both sides
  share. A domain-level status is not a person's status and feeding one in
  would suppress or clear colleagues who were never touched.
* `work/heartbeat/bison-*.json`, `work/watch-events/bison-*.jsonl` — fresh
  (2026-10-14T23:4x) but **campaign-level only**. All 5,329 watch events
  across 16 kinds carry a campaign id and never a lead id. Used below as a
  cross-check, never as a snapshot row.
* `docs/state/PROVIDER-CAMPAIGNS.json` — campaign-level, and carries no
  `unsubscribed` field at all (keys: `bison_campaign_id`, `lead_count`,
  `name`, `owner`, `status`).

---

## 2. The snapshot cannot witness a single unsubscribe. Measured.

This is the most important number in this document.

`suppression.PROVIDER_STOPPED` holds eleven words. **Across all 749 addresses
and all 36,523 status pairs read, exactly one of them ever appears:**

    PROVIDER_STOPPED words observed   bounced  (9 rows, 3 people)
    PROVIDER_ACTIVE words observed    in_sequence, scheduled
    in NEITHER set                    stopped, sent, sequence_finished,
                                      replied, sending_paused

Counted directly, over the four per-lead source files:

| word | occurrences |
|---|---|
| `unsubscribed` | **0** |
| `unsubscribe` | **0** |
| `opted_out` | **0** |
| `complained`, `complaint` | **0** |
| `blocked` | **0** |
| `suppressed` | **0** |
| `hard_bounced`, `soft_bounced` | **0** |
| `bounced` | 90 |

Corroborated three independent ways:

1. **Campaign counters, freshest reading.** All 20 watched EmailBison
   campaigns, read 2026-10-14T23:4x: `unsubscribed: 0` in every one. Total 0.
2. **Campaign counters, the 33-campaign walk** (`work/stage/pc-campaigns.json`):
   `unsubscribed` total **0**, against `bounced` total 2,149.
3. **Every watch event ever written.** 5,329 events across 20 campaigns:
   **0 lines mention an unsubscribe**, and the event vocabulary has no
   `UNSUBSCRIBE` kind at all (`WATCHING`, `STATUS`, `CAMPAIGN-STOPPED`,
   `TOUCHED`, `MEMBERSHIP`, `QUEUED`, `SCHEDULE-MOVED`, `DISAGREEMENT`,
   `BLANK-CONTENT`, `READ-ERROR`, `PROVIDER-VOLUME`, `SEND`, `COHORT`,
   `REPLY`, `BOUNCE`, `AGREEMENT`).

**So the reconciliation can detect provider BOUNCES and nothing else.** Ten of
the eleven stop-words are unexercised, and the one direction §6a most wants —
somebody on their blacklist we think is contactable — is undetectable from
stored state not because the snapshot is stale but because no stored artifact
has ever carried the word.

There is a coherent reason, and it is already in `CLAUDE.md`: the copy in
487/489/493 carried **no opt-out route**. Nobody could click an unsubscribe
link, so the provider's blacklist never learned about them, so its counters
read zero. That is consistent with §2 of the 2026-10-14 measurement — 94 people
asked to be removed, **by replying**, and a reply is not an unsubscribe as far
as EmailBison's list is concerned. **The zero is not reassuring. It means the
two lists have never had an opportunity to disagree about an unsubscribe, and
will the moment a compliant footer ships.**

### Five of the eight observed words are in neither vocabulary

`stopped` is the single most common status in stored state (762 rows in the
snapshot, 1,629 memberships in the raw file) and it proves nothing — as
`s6-collision-walk.json` already says in its own `why` field: *"a campaign at
this account ended early (stopped) and the status does not say whether we
stopped it, they unsubscribed, or the provider stopped it."* `reconcile`
answering `UNKNOWN_THERE` for it is correct.

`replied` (41 rows) is the one worth flagging: it is the provider reporting
that it stopped sending **because the person answered**, and it is in neither
set. For somebody we have not blocked, `reconcile` therefore returns
`UNKNOWN_THERE` rather than `BLOCKED_THERE_ONLY`. Safe — UNKNOWN is a finding,
not a pass — but it understates a case the provider stated plainly.

---

## 3. §6a measured, by name

`suppression.reconcile` over the production estate, 1,381 contacts in 1,584
records, snapshot of 749 addresses. **3,008 `reconcile` calls and 3,008
consultations recorded** — so every call reached `decide` and none of them is
an answer nobody asked for.

`reconcile` takes **one** status per person and 749 people carry between one and
five. There is no precedence that is conservative in both directions: for
somebody we have stopped, a NON-stopped provider word is the dangerous reading;
for somebody we have not, a STOPPED word is the finding. So the reduction is not
chosen in advance — `reconcile` is asked once per distinct status and the **most
severe** answer is kept (`SUPPRESSED_HERE_ONLY` > `BLOCKED_THERE_ONLY` >
`UNKNOWN_THERE` > `AGREE`). `reconcile_all` was then handed exactly the status
that produced each answer and **reproduced the four counts exactly** — a control
on its own key normalisation, not an independent measurement, and reported as
such.

| finding | people |
|---|---|
| `provider_state_unknown` | **1,254** |
| `suppressed_here_still_active_there` | **123** |
| `blocked_at_provider_not_here` | **3** |
| `agree` | **1** |

1,254 + 123 + 3 + 1 = 1,381.

### `UNKNOWN_IS_NOT_A_PASS` holds, and here is what it is holding

Of the 1,254 `UNKNOWN_THERE`:

    no email on the contact at all                        68
    email present, absent from the snapshot              564
    ---- subtotal with no provider status whatsoever      632
    carried a PROVIDER_ACTIVE word, beaten by a word
      in neither vocabulary                              536
    carried only words in neither vocabulary              86

**Not one of those 632 became `AGREE`.** Absence scored `UNKNOWN_THERE` every
time, which is the decisive property §6a claims and the mutation test
(`md5 32de76ef`) protects. And the 536 are the property working in the other
direction: a person reading `in_sequence` in one campaign and `sent` in another
is **not** cleared by the campaign that would have agreed.

### The 3 that are real, named, and triple-sourced

`blocked_at_provider_not_here` — the provider stopped them, we did not:

**Named by FINGERPRINT, not by address.** The plaintext is deliberately absent
from this document, for `§7.7`'s reason in the 2026-10-14 measurement and because
`tests/test_fixture_hygiene.py` requires every address in git to be on a
reserved domain. All three are in the gitignored
`work/suppression-measure/PROVIDER-SUPPRESSION-SNAPSHOT-FULL.json`, keyed on
the same `agencydnc.fingerprint("email", ...)` that `add()` writes, so the list
is directly applicable without ever being published.

| fingerprint (first 16) | bison lead | bounced in | our verdict |
|---|---|---|---|
| `d13e93d56e314e02` | 204562 | 495 | **ALLOW**, zero reasons |
| `f38022b4e74b6e51` | 204472 | 492 | **ALLOW**, zero reasons |
| `0a5148a392afd2db` | 204668 | 491 | **ALLOW**, zero reasons |

Each is witnessed by **three independent source files** (`pc-leads`,
`pc-sends`, `reengagement-inventory`), and the 2026-10-14T23:4x heartbeat
independently reports **exactly one bounced member in each of 491, 492 and
495** — which is these three and nobody else.

All three records are at state `verified`. All three contacts carry
`sendable: true`, `verdict: "valid"` and
`verification.state: "verified"` with **two confirmations** — Deliverable *and*
Reoon both returned `valid` on 2026-09-21. The provider then sent, and the mail
bounced.

**Their records carry no bounce event.** Every event on all three is
`draft_approved`. So: a provider bounce is a permanent refusal under
`CLAUDE.md`'s lead rule 1, the provider recorded it three weeks ago, two paid
verifiers say the address is good, and nothing in our state knows. This is
§7.1's inert reader with three names attached.

### The 123 are not 123 live cases. They are 30 stale ones and 93 unknowns.

`suppressed_here_still_active_there` is §6a's "dangerous one". Split it:

    carried a PROVIDER_ACTIVE word                        30
    carried only words in neither vocabulary              93
    carried a PROVIDER_STOPPED word                        0
    had no provider status at all                          0

Why we have stopped them — `eligibility.must_not_contact`, measured per person:

    blocked:unsubscribed                                  76
    blocked:operator_excluded                             33
    blocked:company_paused                                18
    blocked:contact_stopped                                8
    blocked:replied                                        8
    blocked:review_required                                3

Then the cross-check that changes the conclusion. The snapshot claims **1,667
PROVIDER_ACTIVE rows**. Against the heartbeat read 20 hours ago:

| campaign | snapshot ACTIVE rows | heartbeat 2026-10-14 | membership |
|---|---|---|---|
| 491 | 806 | paused | `stopped 103, sending_paused 218, replied 11, bounced 1` |
| 492 | 496 | paused | `sending_paused 135, replied 11, stopped 59, bounced 1` |
| 494 | 199 | paused | `sending_paused 15, stopped 60, replied 1` |
| 493 | 49 | paused | `sending_paused 20, stopped 2` |
| 487 | 39 | paused | `sending_paused 10` |
| 481 | 27 | paused | `stopped 14, sending_paused 9` |
| 498 | 20 | completed | `stopped 15` |
| 489 | 17 | paused | `sending_paused 5` |
| 496 | 7 | paused | `stopped 42, sending_paused 1` |
| 497 | 4 | completed | `stopped 19, replied 1` |
| 451 | 1 | archived | `sequence_finished 1` |
| **352** | **2** | **NO WATCHER** | — |

**`in_sequence` across all 20 watched campaigns, as of 2026-10-14T23:4x: 0.**

So 1,665 of the snapshot's 1,667 ACTIVE rows are contradicted by a reading 20
hours old. The newest per-lead source is `pc-lead-sends.jsonl` at
2026-09-24T18:27Z — **21 days stale.** The 30 are therefore a stale reading,
not a live one, and **zero of the 123 are provably still being sent to.**

### The two that survive the cross-check are in the other direction

The only `in_sequence` rows a fresher reading does not contradict are in
campaign **352**, the one campaign with an ACTIVE row and no watcher. Per
`docs/state/PROVIDER-CAMPAIGNS.json` (2026-09-30), 352 is `status: active`,
21,665 leads, and is listed in `sending_now`. It is one of the four the
operator declared **internal** on 2026-10-01.

    2f0a66e55dc7c2e5     in_sequence (352), stopped
    50f2905f00a6db9b     in_sequence (352), sent, stopped

Both: `reconcile` → `UNKNOWN_THERE`. Our side → **ALLOW, zero reasons.**

They sit in a campaign that was confirmed still sending, our suppression says
nothing about them, and §6a's grading cannot say anything stronger than UNKNOWN
— because `reconcile` calls `decide` at `SCOPE_SEND`, where `HOLD_ACTIVE_SEQUENCE`
is **not evaluated at all**. The reconciliation is structurally unable to report
"they are in a live sequence" as a hold. `CLAUDE.md`'s lead rule 2 says ON HOLD
while the lead sits in a live campaign *belonging to anyone*.

Widened to every campaign whose owner is not provably ours — 274, 327, 328,
352, 418, the four still sending plus 274:

    people in our queue holding a lead row in one of them      223
      our verdict is BLOCK                                      78
      our verdict is ALLOW                                     145
        at record state verified                               140
        at record state drafted                                  4
        at record state approved                                 1

`CLAUDE.md`: *"anyone with a lead row in 327/328/352 is NOT CLEAN for outreach,
whoever owns them."* **145 of them are ALLOW today, and one is already
approved.**

### `AGREE` is one person, and it is the wrong word for them

The single `AGREE` is `973f2b1fabc61a5c`, statuses
`{in_sequence, scheduled}` in campaign 491, our verdict ALLOW. It comes from `reconcile`'s
`not stopped_here and active_there → AGREE` branch, which is literally true as a
*list* comparison: neither list has stopped them. But read as "clear", it would
enrol somebody the snapshot says is mid-sequence. Same root cause as the two
above — the holds are not evaluated at `SCOPE_SEND`. `AGREE` here means
**"neither list has stopped them"**, never **"it is safe to contact them"**, and
nothing in the return value says so.

---

## 4. Three defects in §6a's own machinery, found by using it

**1. `reconcile` and `reconcile_all` have ZERO callers.** Grepped across `src/`
and `scripts/`: the only matches are `costs.reconcile`, `leadobserve.reconcile`
and `stepstate.reconcile`, which are different functions, plus this new script.
`suppression.decide` has three production callers (`bisonfactory:2054`,
`executionguard:1071`, `providerwrites:1482`); `reconcile` has none. So
`UNKNOWN_THERE` is a finding that stops nothing: it is computed correctly and
read by nobody. That is this repository's named recurring defect — *a thing
computed correctly that nothing downstream reads* — and §6a is currently an
instance of it.

**2. `reconcile` has no parameter for our own suppression roster, and from a
worktree it silently reads a shorter one.** `reconcile` → `decide` →
`eligibility.must_not_contact` → `ingest.load_suppress()`, and
`ingest.SUPPRESS_LOCAL` is anchored to the repository ROOT.
`config/suppress.local.txt` is gitignored, so **no worktree has one**. Measured:

    this worktree, unaided          2 domains   (config/suppress.txt, both fictional:
                                                 another-customer.test, example-customer.test)
    with the main checkout's local file        14 domains

`decide` accepts `suppressed=` and `reconcile` does not forward it, so there is
no way to supply the real roster to a reconciliation. **On today's estate this
costs nothing, and that is verified rather than assumed:** the run was repeated
with the 2-domain roster and produced byte-identical counts, because **none of
the 14 domains appears among the queue's 1,584 domains.** The exposure is
structural, not currently load-bearing — and a 2-domain roster reading as
healthy is exactly the shape that stops being harmless the first time a
suppressed domain enters the queue.

**3. `suppression.decide` accepts `agency=` and uses it nowhere.** Signature
line 254; the parameter appears in no other line of the function.
`must_not_contact` has no `agency` parameter at all, so the prebuilt index can
never reach `agencydnc.lookup`, which reads from disk on every call instead. No
caller passes it today. A future caller passing one would be silently ignored,
and a test supplying a fixture index would be testing the real ledger.

---

## 5. What is still owed

1. **The snapshot is 21 days old and cannot be refreshed without a provider
   read.** This lane makes none. A refresh is a lead-page walk over the
   campaigns in §3's table; the mechanism is `scripts/suppression_snapshot.py`
   and the sources it names, not new code.
2. **The three bounced addresses need suppressing.** Named in §3, all three
   `sendable: true` and ALLOW. That is `agencydnc.add(...)` × 3, local ledger
   only, and it needs the operator — the same condition as the 90.
3. **The 145 ALLOW people with a lead row in 274/327/328/352/418.** One is at
   `approved`. Under lead rule 2 they are ON HOLD; under today's code they are
   ALLOW, because `SCOPE_SEND` does not evaluate the holds and nothing calls
   `reconcile`.
4. **Nothing reads `reconcile`.** Until something does, this measurement is a
   document and not a gate.
5. **Ten of eleven stop-words are unexercised.** The first compliant footer
   that ships gives EmailBison's blacklist its first real entries, and on that
   day this snapshot's blind spot stops being academic.

---

## 6. Files

| path | state |
|---|---|
| `scripts/suppression_snapshot.py` | new. Assembles the snapshot from stored state and measures `reconcile` / `reconcile_all`. No provider call. |
| `tests/test_the_provider_snapshot_is_assembled_from_stored_state.py` | new. The refusal on a missing source, and that absence never becomes `AGREE`. |
| `docs/state/PROVIDER-SUPPRESSION-SNAPSHOT.json` | new, committed. Fingerprints, counts, provenance. No addresses. |
| `work/suppression-measure/PROVIDER-SUPPRESSION-SNAPSHOT-FULL.json` | new, gitignored. Addresses and per-person findings. |
| `docs/SUPPRESSION-SNAPSHOT-2026-10-15.md` | this document. |

**Reproduce:**

    py -3 scripts/suppression_snapshot.py \
      --suppress-local <main-checkout>/config/suppress.local.txt \
      --full-out work/suppression-measure/PROVIDER-SUPPRESSION-SNAPSHOT-FULL.json \
      --sanitised-out docs/state/PROVIDER-SUPPRESSION-SNAPSHOT.json

`--suppress-local` is not optional from a worktree; see §4.2.

**Tests:** `tests.test_a_suppressed_address_cannot_reach_a_provider` — 37
tests, all green, 8 of them §6a's, including
`test_absence_from_the_snapshot_is_never_agreement`. Plus the new module. A
full-suite reference is **owed** for this branch, because `tests/` changed.
