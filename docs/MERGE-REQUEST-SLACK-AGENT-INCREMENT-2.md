# Merge request — increment 2: one account vocabulary, and a Monday report that can be stopped

**Branch `slack-agent`. Two commits, `23e7e599` and `e391b0a7`, on top of a
merge of master (`700c1943`).**

    700c1943  Merge master into slack-agent: infra TASK-251..265 and D3/D4
    23e7e599  Eight items from an OSS survey, and six premises that did not
              survive being checked            <- additive, operator's own
    e391b0a7  One account vocabulary, and a Monday report that can be
              stopped                          <- THIS INCREMENT

---

## 0. THE OPERATOR'S DECISIONS, AND WHERE EACH ONE LANDED

| Decision | Where it is |
|---|---|
| 1. `_accounts` takes the operator vocabulary; old keys **retired, not aliased**; `unanswerable` its own tile | `src/accountstate.py` (new), `src/clientreport.py`, `src/web/api.py`, `src/slackagenttools.py` |
| 2. Version guard flips to a rule **hash** once rules-4 lands | **Not done — rules-4 has not landed.** `replies.VERSION` is still `"rules-3"` on master and on disk, and there is no rule hash anywhere in the tree. The guard is unchanged and correct to leave unchanged. See §6. |
| 3. Croatian correction sent by the operator | **Closed.** Nothing in this diff touches it. |

---

## 1. FIRST, THE VERIFICATION THE OPERATOR ASKED FOR

**The loop runs merged code.** Measured, not read off a log:

    agent loop    pid 32072   started 17:02:25
    followup loop pid 39440   started 17:02:27   <- beating for the first time
    latest touched module     17:00:19

Both processes start **after** every module's mtime, so there is no stale
import. This is the first deploy in this project's recent history where
"a merge is not a deploy" did not bite.

**And `sends_today` answers correctly against live provider membership.**
The knowledge pack rebuilt at 17:02:25 with the newest-first ordering:

    would read : 498 497 496 495 494 493 492 491   ->  553 emails
    hidden (6) : 489 487 485 484 481 451           ->    6 emails

The six the cap hides are two drafts, one paused, one completed and two
near-idle. **Every campaign that is actually sending sits inside the cap**,
and `campaigns_not_read: 6` carries the floor note. The 2026-09-22 defect —
eight OLDEST campaigns read, 231 of 296 sends reported — is fixed in the
running process.

**One live fault found and not touched**, because `scripts/*_watch_loop.py`
is on the forbidden list: `work/heartbeat/bison-491.json` reads
`READ-ERROR 100x PartialInventory` at 17:17, while `campaign_by_id(491)`
answers fine from here — 272 emails, 645 queue rows. So 491 is readable and
it is the **watcher's deeper inventory read** that is failing, a hundred
times over. 491 is the campaign behind the Croatian incident. Production's
to fix.

**D5 did not merge.** `ab421a5c..812b461f` — the two-client isolation suite
and the `sender_summary` count fix — is still the only outstanding stack
item. Productive 156 → 158 and ContactOut 1 → 2 are still not live.

---

## 2. THE VOCABULARY WAS IN TWO PLACES AND THEY SHARED A WORD

`SLACK-AGENT-HANDOFF-2026-09-23-EVENING.md` §5a refused to write the adapter
and asked for a decision. This is the decision, implemented.

    slackagenttools   untouched / sequenced / engaged / replied / meeting /
                      won / lost / do_not_contact
    web/api           targeted / contacted / engaged / positive /
                      multi_dm / referrals

**Both spelled `engaged` and neither meant the same thing by it.** In the PDF
it was "at least one reply"; here it is deliberately *short* of a reply.

### 2a. The collision is now a test rather than a paragraph

    test_a_reply_is_replied_and_not_engaged

An account that replied scores `replied` 1 and `engaged` 0. Under the old
vocabulary the identical account scored `engaged` 1. **That is what an alias
would have hidden**: the number moves from one tile to another in a document
a client receives, and nothing asserts it moved. `test_the_retired_keys_are_
gone_rather_than_aliased` pins the other half.

### 2b. `src/accountstate.py` — the one definition

`state_of()` moved out of `slackagenttools` whole; the precedence is
unchanged in the move. Both readers import it. `IN_FLIGHT` is exported as an
explicit **sum** and is deliberately not a member of `ACCOUNT_STATES`, so
nothing can iterate the eight, add it, and double-count every account in it —
`accounts_in_flight_is_a_sum_of` names its members in the payload.

`src/account.py`'s contact-level `ENGAGED` is **not** imported. That one
means "this person replied" and is a different question; importing it to save
a line is how the collision happened the first time.

### 2c. What changed in the numbers

`weekly_report` used to emit `meetings` (plural) and fold `SEQUENCED` into
`in_flight`, so **`sequenced`, `won` and `lost` had no key at all** — and a
renderer cannot draw a tile for a key it is never handed. All eight are now
emitted by name, at zero when zero.

`_accounts` renders `Cannot be placed` **as its own tile, at zero too**. A
tile that appears only when the number is non-zero is a tile nobody notices
has appeared. And it carries a sentence saying why `won` and `lost` are zero:
nothing in this tree records a deal, and `0 won` read as a measurement rather
than as the absence of any source is the failure that prevents.

---

## 3. THE PREVIEW IS THE FEATURE, SO MISSING ITS WINDOW IS NOT A NEAR MISS

`src/weeklyreportwatch.py` — Monday, 07:30 preview to `#resonate-os`, 08:00
to the client channel, Europe/Zagreb, idempotent per workspace per Monday.

**A tick that first runs after 08:00 posts nothing.** It returns
`MISSED_PREVIEW`. Nobody had the half hour in which to stop the document, and
posting anyway puts an **unreviewed client document in a client channel** —
the exact thing the window exists to prevent. Late is not approved. This
project has posted a wrong number to a client channel once; the correction
still has to be sent by hand because the channel is Slack Connect.

**A stop carries a name and is refused without one.** The first question on a
Monday a client has no document is who stopped it, and an anonymous stop is
indistinguishable from a bug that suppressed a report.

`scripts/weekly_report_loop.py` is in the **same commit** as the module.
`digestwatch` and `slackfollowup.due()` both shipped correct and called by
nothing; this is the third instance, so the caller is not deferred.

---

## 4. THE PDF: THREE SECTIONS, ON PURPOSE

`src/weeklyreportpdf.py` hands `clientreport.build` the weekly report's own
dict, **unchanged** — not a translation of it. That is the one-vocabulary
decision made structural.

The handoff measured the overlap at **one key of thirty-three**. Handing the
monthly template a dict that feeds three of its twenty-five sections produces
a document that is mostly "Not tracked" boxes, and a client reading
twenty-two of those does not conclude "those are monthly questions". They
conclude we measured and found nothing. So the weekly document is short:
`accounts`, `replies` when the ledger was readable, and the appendix that
bounds the rest. **Absence by omission, not absence dressed as a
measurement.**

### 4a. One gap, stated rather than worked around

`src/providers/slack.py` has `post()` and **no file-upload route**. So the
loop writes the PDF to `work/reports/` and the message names the path; a
person attaches the file. Adding an upload route means editing a provider
module, which is on this session's forbidden list. **The preview text says
this out loud** rather than leaving somebody to discover it on a Monday.

---

## 5. TWO FINDINGS THE TESTS PRODUCED, NOT THE CODE

### 5a. Five of six attacks moved exactly one test

28 tests, green on the first run. Attacked six ways, and **five attacks moved
exactly one test each** — which by this repository's own rule
(`SLACK-AGENT-HANDOFF-2026-09-23-EVENING.md` §9) is a finding about the file.
Three were genuinely under-asked and now move 2–3:

    delivered must outrank a LATE stop   1 -> 2
    the section list vs the rendered doc 1 -> 2
    a silent UTC fallback                1 -> 2

The third is the worst and would have shipped. **Every schedule test built
its `now` with `tzinfo=watch.zone()`** — so if the zone silently fell back to
UTC, both sides of every comparison moved together and nothing complained,
while every real post moved by two hours. That test now fixes a UTC instant:
`2026-09-28 05:30Z` is 07:30 in Zagreb and must preview; `07:30Z` is 09:30
local and must be `MISSED_PREVIEW`.

### 5b. An existing master test is passing vacuously

`clientreport` writes page content as **FlateDecode streams**. So

    self.assertNotIn(b"is not assembled for this report", raw)

against the raw PDF bytes **can never fail** — the words are not findable in
either direction. `tests/test_report_sections.py` has exactly that assertion
today and it is green on master for no reason.

`tests/test_the_monday_report_can_be_stopped.py` carries a `text_of()` helper
that decompresses the streams, and every page assertion in the new file reads
real rendered text. The note is in that helper's docstring so the next reader
finds it. **Fixing the master test is not in this diff** — it is a one-line
change in a file this increment already touches for the vocabulary, and
folding an unrelated correctness fix into it would hide it. Recorded here as
the next small thing.

---

## 6. WHAT THIS DOES NOT DO

- **Decision 2 is not actioned, and should not be.** `replies.VERSION` is
  still `"rules-3"`; grep finds no `rule_hash`, no `RULE_HASH`, no
  `"rules-4"` anywhere in `src/` or `tests/`. The guard flips *once that
  lands*, and it has not.
- **The stale-verdict test is not written.** That is increment 3 and the
  handoff's §3a argues it is now the more valuable half, because the version
  guard provably does not catch the drift.
- **No Slack post was made** and nothing was sent. The loop has never been
  started; there is no `work/heartbeat/weekly-report.json`.
- **D5 is still unmerged** and this increment does not depend on it.

---

## 7. THE RULES THIS SESSION WORKED UNDER

- Never merges to master, never pushes to it. Delivery is this doc plus one
  line in `#resonate-os`.
- Never edits `config/.env`, `work/`, `src/providers/*` or
  `scripts/*_watch_loop.py`. **Verified**: this increment touches
  `src/accountstate.py`, `src/clientreport.py`, `src/slackagenttools.py`,
  `src/web/api.py`, two new `src/` modules, one new `scripts/` loop (not a
  `*_watch_loop.py`), and three test files. Production's `work/` was **read**
  — heartbeats, the knowledge pack, the ICP journals — and never written.
- Adversarial probes offline only. The six attacks ran against temp dirs. The
  only live reads were production's `work/` files and `campaign_by_id` GETs
  for the membership check the operator asked for.
- The branch was **merged up from master first**. It was behind by the whole
  infra merge (`bbcbf69`, TASK-251..265), and a merge request written on the
  stale base would have read as a 16,000-line deletion of infra's work.

---

## 8. THE SUITE

`tests/test_report_sections`, `test_the_report_counts_accounts_before_emails`,
`test_two_clients_cannot_see_each_other` and the new
`test_the_monday_report_can_be_stopped` run together: **118 tests, OK.**

**The full-suite diff is the outstanding verification.** A first run was
started at 17:23 and **discarded**: source was edited at 17:28 while
`unittest discover` was still importing modules, so its result describes
neither tree. A clean run on this HEAD was started at 17:43. Whoever picks
this up should diff the failure set **by NAME, both directions**, against a
clean run on master — a count-to-count comparison would say the same thing
and prove nothing.

And note `scripts/suite_verdict.txt` is a **committed file from 2026-09-21
21:29** whose `log_file` points at the production checkout. It is not the
result of any run in this worktree, and reading it as one is a trap this
session nearly fell into.
