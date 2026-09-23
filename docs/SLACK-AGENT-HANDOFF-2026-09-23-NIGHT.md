# Slack agent — handoff, 2026-09-23 night

Supersedes `SLACK-AGENT-HANDOFF-2026-09-23-EVENING.md` and everything before
it. Written to the test `CLAUDE.md` sets: a fresh session on another machine,
with a clone and the secrets supplied separately, should be able to read this
and say what happened and what to do next.

**Branch `slack-agent` at `d91ea474`.** Master was `9788ce2e` when this
branch merged up; master has since moved to **`e1f93730`** (17:35, "The geo
decisions, and per-mailbox room without the 12,438-page walk"). **That one
commit is not in this branch.** See §7.

---

## 1. THE STACK IS TWO ITEMS NOW, NOT FIVE

Production merged four of the evening's five at 17:01 (`9788ce2e`): D3, D4,
the reply counting and accounts-first. What is left:

    1  docs/MERGE-REQUEST-SLACK-AGENT-PHASE-D5.md     ab421a5c .. 812b461f
       a synthetic second client; both-sided isolation; 41 tests; and the
       sender_summary count fix. STILL UNMERGED, still the oldest item.
       Productive 156 -> 158 and ContactOut 1 -> 2 are NOT live.

    2  docs/MERGE-REQUEST-SLACK-AGENT-INCREMENT-2.md  23e7e599 .. d91ea474
       one account vocabulary; the Monday report and its stop; NEW

Both are merge-ready. Increment 2 does not depend on D5.

---

## 2. THE VERIFICATION THE OPERATOR ASKED FOR — BOTH PARTS PASS

**The loop runs merged code.** This is the first deploy in this project's
recent history where "a merge is not a deploy" did not bite:

    agent loop     pid 32072   started 17:02:25
    followup loop  pid 39440   started 17:02:27  <- BEATING, first time ever
    latest touched module      17:00:19

Both start **after** every module's mtime. No stale import. The followup
loop's heartbeat (`work/heartbeat/slack-followup.json`) exists for the first
time, which means D3's offer is now real rather than promised.

**`sends_today` is correct against live provider membership.** Knowledge pack
rebuilt 17:02:25, newest-first ordering live:

    would read : 498 497 496 495 494 493 492 491   ->  553 emails
    hidden (6) : 489 487 485 484 481 451           ->    6 emails

The six hidden are two drafts, one paused, one completed, two near-idle.
**Every sending campaign is inside the cap of eight**, and
`campaigns_not_read: 6` carries the floor note. The 2026-09-22 defect is
fixed in the running process.

### 2a. One live fault, reported and not touched

`work/heartbeat/bison-491.json` reads **`READ-ERROR 100x PartialInventory`**
at 17:17, while `slackagentreadback.campaign_by_id(491)` answers fine from
here — 272 emails, 645 queue rows. **So 491 is readable and it is the
watcher's deeper inventory read that is failing**, a hundred times over.
491 is the campaign behind the Croatian incident.
`scripts/*_watch_loop.py` is on this session's forbidden list, so this is
production's. It has been failing since at least 17:17 and nothing else
reports it.

---

## 3. WHAT THIS SESSION DELIVERED

### 3a. Increment 2 — `docs/MERGE-REQUEST-SLACK-AGENT-INCREMENT-2.md`

Decision 1 in full. `src/accountstate.py` is now the **one** account
vocabulary; `slackagenttools` and `web/api` both import it, and the four old
PDF keys are retired rather than aliased. `src/weeklyreportwatch.py` +
`scripts/weekly_report_loop.py` are the Monday 08:00 schedule with the 07:30
preview and its stop; `src/weeklyreportpdf.py` feeds `clientreport` the
weekly report's own dict unchanged.

The argument is in the merge request. The two things worth carrying here:

- **A tick that first runs after 08:00 posts nothing** (`MISSED_PREVIEW`).
  Nobody had the half hour in which to stop it, and late is not approved.
- **The PDF is three sections on purpose.** The evening handoff measured the
  overlap at one key of thirty-three; twenty-two "Not tracked" boxes read as
  "we measured and found nothing", not as "those are monthly questions".

### 3b. The additive OSS work — `docs/LEARNED-FROM-OSS-2026-09-23.md`

Eight items, eight tasks (**TASK-266..273**, all in `TODO/`, all S or M).
**Six of the eight premises did not survive being checked against the code**,
four in ways that change what the task should build. The full table is in the
doc; the two that cost money if unchecked:

- item 2's FLAGGED population is **5,851**, not 3,668 (stale) and not 8,370
  (today's re-judge) — 2,519 of the 8,370 have no company behind them and no
  model can judge them.
- item 3's "provider-resolved profile" **is a step that does not exist**. We
  supply the URL; `heyreach.lead_profile()` is called by nothing in `src/`.

---

## 4. TWO FINDINGS ABOUT THE TESTS, WHICH ARE WORTH MORE THAN THE DIFF

### 4a. `assertNotIn` against raw PDF bytes cannot fail

`clientreport` writes page content as **FlateDecode streams**. So

    self.assertNotIn(b"is not assembled for this report", raw)

can never fail — the words are not findable in either direction.
**`tests/test_report_sections.py` has exactly that assertion and it is green
on master for no reason.** `tests/test_the_monday_report_can_be_stopped.py`
carries a `text_of()` helper that decompresses the streams and every new page
assertion reads real rendered text.

**This is not fixed.** It is a one-line change in a file this increment
already touches, and folding an unrelated correctness fix into a vocabulary
commit would hide it. It is the next small thing.

### 4b. Five of six attacks moved exactly one test

28 tests, green first run, attacked six ways — and **five attacks moved
exactly one test each**, which by §9 of the evening handoff is a finding
about the file. Three were genuinely under-asked and now move 2–3. The worst
would have shipped: **every schedule test built its `now` with
`tzinfo=watch.zone()`**, so a silent UTC fallback moved both sides of every
comparison together and nothing complained — while every real post moved two
hours. That test now fixes a UTC instant.

### 4c. And one trap this session nearly fell into

`scripts/suite_verdict.txt` is a **committed file from 2026-09-21 21:29**
whose `log_file` points at the production checkout. It is not the result of
any run in this worktree. Reading it as one gives you twelve failures from a
two-day-old tree.

---

## 5. THE SUITE — READ THIS BEFORE BELIEVING ANY GREEN

The targeted set is green: `test_report_sections`,
`test_the_report_counts_accounts_before_emails`,
`test_two_clients_cannot_see_each_other` and
`test_the_monday_report_can_be_stopped` together are **118 tests, OK**.

**The full-suite by-name diff is the outstanding verification.**

- A first full run was started at 17:23 and **discarded**: source was edited
  at 17:28 while `unittest discover` was still importing modules, so its
  result describes neither tree. Do not resurrect it.
- A clean run on this HEAD was started at 17:43
  (`python -m tests.offline -v`).
- A baseline worktree is staged at **`9788ce2e`** — the master this branch
  actually merged — in the session scratchpad as `wt-base`. Run the same
  command there and **diff the failure set by NAME, both directions**. A
  count-to-count comparison would say the same thing and prove nothing; the
  evening handoff's §9 is explicit about this.
- Do not run both at once. `CLAUDE.md`: `unittest discover` and
  `tests.offline` both bind loopback, and run back to back they still
  overlap during teardown.

---

## 6. THE THREE DECISIONS, AND THE ONE THAT MUST NOT BE ACTIONED YET

1. **Client-report vocabulary** — done, §3a.
2. **Version drift** — *deliberately not done.* `replies.VERSION` is still
   `"rules-3"` on master and on disk, and grep finds **no `rule_hash`, no
   `RULE_HASH` and no `"rules-4"`** anywhere in `src/` or `tests/`. The guard
   in `test_the_report_counts_accounts_before_emails.py` still asserts the
   string, which is correct until the bump lands. **Flip it to the hash when
   rules-4 is on master, and not before.**
3. **The Croatian correction** — closed. The operator sends it. The text is
   in `SLACK-AGENT-HANDOFF-2026-09-23-EVENING.md` §7 and its one caveat still
   stands: the "494" is 2026-09-22's figure as it stood that afternoon;
   re-read it if the watchers have read back further.

---

## 7. THE FIRST THING THE NEXT SESSION SHOULD DO

**Merge master in again.** This branch merged `9788ce2e`; master is now
`e1f93730`. One commit, "The geo decisions, and per-mailbox room without the
12,438-page walk". A merge request written on a stale base reads as a
deletion of everything the base is missing — this session lost time to
exactly that, because the branch was behind the whole infra merge
(`bbc5df69`, TASK-251..265) and `git diff master..slack-agent` showed 16,117
deletions that were not deletions.

Check `git merge-base --is-ancestor master HEAD` before writing anything.

---

## 8. WHAT IS NOT STARTED

In the operator's own order:

    3. Phase D item 4 (positives to the client channel) once rules-4 and the
       ledger write-back are live. UNTIL THEN: a test that a `rules-3`
       verdict is never counted. NOT STARTED, and the evening handoff's §3a
       argues it is now the more valuable half - the version guard provably
       does not catch the drift, because the rules moved twice on 2026-09-23
       (0b78fd68 at 13:18, 83a30652 at 14:46) under an unchanged VERSION.

    4. Increments 3 and 4: catalogue second pass with scope tests; briefing
       additions; "what are we working on" as a client answer; account status
       from the ledger as the write-back lands; then
       docs/CLIENT-PORTAL-DESIGN.md for review, BUILD NOTHING until approved.

    -  The Monday loop has NEVER BEEN STARTED. There is no
       work/heartbeat/weekly-report.json. Starting it is production's, and
       the first Monday it would fire is 2026-09-28.

    -  Slack has NO FILE-UPLOAD ROUTE. src/providers/slack.py has post() and
       nothing else, so the weekly PDF is written to work/reports/ and a
       person attaches it. Adding the route means editing a provider module,
       which is on this session's forbidden list.

---

## 9. THE RULES THIS SESSION WORKED UNDER

Unchanged, restated by the operator, verified for every commit:

- Never merges to master, never pushes to it. Delivery is a merge-request doc
  in `docs/` plus one line in `#resonate-os` (`C0C3C6MDN9L`).
- Never edits `config/.env`, `work/`, `src/providers/*` or
  `scripts/*_watch_loop.py`. **Verified**: this session's diff touches
  `src/accountstate.py`, `src/clientreport.py`, `src/slackagenttools.py`,
  `src/web/api.py`, `src/weeklyreportpdf.py`, `src/weeklyreportwatch.py`,
  `scripts/weekly_report_loop.py` (not a `*_watch_loop.py`), three test files
  and three docs plus eight task files. Production's `work/` was **read** —
  heartbeats, `knowledge-pack.json`, the two ICP journals, `queue.jsonl` —
  and never written.
- A merge request per increment; a handoff before context runs out.
- Adversarial probes offline only. The six attacks ran against temp dirs and
  a restored copy each time. The only live reads were production's `work/`
  files and `campaign_by_id` GETs for the membership check the operator
  asked for.

---

## 10. THE THING THIS SESSION LEARNED THAT IS NOT IN A DIFF

**A test can be green because it is unfalsifiable, and that looks exactly
like a test that passes.**

Two instances in one afternoon, from the same cause — an assertion whose
subject the test could not actually see. `assertNotIn(b"...", raw)` against a
compressed PDF is one. Every schedule test building its `now` from the same
function it was trying to pin is the other: the zone could have silently
become UTC and both sides of the comparison would have moved together.

Neither was caught by writing more tests. Both were caught by **breaking the
code deliberately and being unsatisfied with how little complained** — which
is the lesson the evening handoff wrote down, applied twice more, and the
second time it found a defect in a file that was already on master.
