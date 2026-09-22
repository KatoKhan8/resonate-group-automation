# Production handoff — 2026-09-22 evening

For a session with no conversation context. **Supersedes
`docs/PRODUCTION-HANDOFF-2026-09-22-AFTERNOON.md`**, whose send figures and
"0 bounced / 0 replied" headline are both superseded.

---

## 1. THE FOUR INSTRUCTIONS THAT WERE ALREADY DONE

Do not redo these. Each was verified live, not read off a doc.

**The PII guard is GREEN, 13/13**, on a clean master tree (`9a77028e`, 15:45).
It was reported red at 3 of 13. It is not. Because this guard was once closed
as "catches nothing" while it was catching real leaks, it was ATTACKED rather
than trusted: a planted address on a live domain and a live-range phone in a
tracked file turned it red on both, naming file and domain. **Green AND it
bites.** ISSUE-006 is already reopened with its note; the 13 files are already
redacted.

**Infra's five are merged** (`d88d08db`, 15:51). **Slack C1+C2 are merged**
(`cd143eda`, 14:25). **Only Slack C3 remains**, 12-14 commits on `slack-agent`.

## 2. THE LIVE NUMBERS, FROM MEMBERSHIP AT ~16:05Z

    camp  human       leads   sent  repl  bounce   contacted
    491   kresimir      330     63     2       1          63
    492   bernarda      206     50     2       1          50
    494   fran           76     21     0       0          21
    495   tomislav       60      9     0       0           9
    493/496/497/498     122      0     0       0           0
    489   (us-cohort)     5      5     0       0           5
    -----------------------------------------------------------
    TOTAL               738    148     4       2

    scheduled rows: 1071 scheduled - 146 sent - 2 bounced - 8 stopped

**148 sent, not the afternoon's 25. Bounces and replies are no longer zero.**

**Replies today: 6, every one `automated_reply=True`, 0 interested, 0 human.**
The standing automated-vs-human split, on its first live day, is **6-0
automated** - the afternoon handoff's thesis holding on live data.

All 33 HeyReach campaigns read IN_PROGRESS. `campaign_read` does NOT expose
the connection-request counters and `progressStats` is empty here, so the
per-campaign request count still needs the per-lead `GetLeadsFromCampaign`
walk on `leadMessageStatus`. **Not run.**

## 3. THE MONITORS

All twelve from the afternoon handoff are alive on the SAME pids - checked.
Filter on `Name -eq python.exe`; the `nohup.exe`/`py.exe` wrappers are not
duplicates, and counting them as such is how a session nearly killed four
watchers before a send window.

**`slack_agent_loop` (pid 116292) started 13:18:29 - 67 minutes BEFORE the
14:25 C1/C2 merge.** It has served pre-merge code all afternoon. A merge is
not a deploy: these loops import at start and never reload. **It still needs
a bare restart** - the highest-value unstarted action here.

## 4. THE WALKER FAULT, WHICH WOULD HAVE POISONED THE LEARNING DOC

Two `learning_walk_replies.py` processes ran against ONE cursor and ONE
append-mode file with no lock. A second walker does not walk twice as fast -
it re-walks the same pages and writes every row again:

    32,025 rows in the file - 16,650 distinct - 15,375 duplicate extras

**The duplication was invisible in `state["rows"]`**, which counts only what
that process fetched, so state read 16,650 and was right while the file was
92% inflated. The file is what analysis reads, so the file is what was fixed:
deduped to 17,700 against a kept backup
(`work/learning-replies.jsonl.dupbak.2026-09-22`), and an O_EXCL lock now
refuses a second walker while reclaiming one whose holder is dead. Both
refusal and reclaim are tested.

One walker runs bare, **pid 122204, holding the lock, 0 duplicates**.

**THE WALK IS NOT COMPLETE.** `complete: false`, cursor at 2026-04-01. A
background task reported "completed" having **exited 127** - the `py -3` shim
is not on PATH. A task that exits 127 has not done the work.

**THE INTERPRETER ON THIS MACHINE** is
`C:\Users\Zvonimir\AppData\Local\Python\pythoncore-3.14-64\python.exe`.
No venv, `python` is the Store shim, `py -3` fails, and **pytest is NOT
installed** - the suite is `unittest`:
`& $PY -m unittest tests.test_fixture_hygiene`.

## 5. OPERATOR DECISIONS RECORDED TODAY

All verbatim with name and date in
`docs/OPERATOR-AUTHORIZATION-2026-09-22-BOUNCE-DENOMINATOR-AND-HEADCOUNT.md`.

**A. Bounce denominator.** A mailbox with fewer than 20 sends in the trailing
7 days has an UNDEFINED bounce rate and cannot trip the stop. It tripped on
1/2 and 1/3 sends while the estate sat at 1.34%. **UNDEFINED IS NOT PASS**:
both mailboxes are held out of NEW enrollment until they reach 20 sends;
their scheduled rows continue. The stop is CLEARED.

**B. Export route.** AI ARK company filters are accepted and INERT - identical
`totalElements` (72,657,969) and byte-identical row hashes across all four
filter combinations - so country x industry x headcount slicing cannot
partition anything. Today's export ships QUALIFIED-only from the estate held.
In parallel measure AI-ARK `people_search` AND ContactOut
`/v1/company/search` (free `/count` first); whichever honours its filters
becomes tomorrow's path. **Record the finding.**

**D. Headcount, one-off.** Headcount comes out of the S3 verdict for the
2026-09-07 Productive file (24,404 domains) ONLY. Geo and industry unchanged;
unknown country stays FLAGGED. **`config/clients/productive.yaml` IS NOT
EDITED** - the 20+ floor still applies to sourced accounts and future exports.
Diff the re-run against IN 5,094 / OUT 15,642 / FLAGGED 3,668 **as a SET of
domains, not as counts**: two runs can agree on a count and disagree on every
member.

**E. Pacing.** Backlog ceiling 3 days -> **7 days** of first-step capacity.
Target 100-200 leads per campaign where mailboxes support it; luka, jakov,
bojan stay small. HeyReach **25 requests/seat/day where TASK-257's ledger
shows room, 10 where the client's usage is UNKNOWN** - unknown is not room.
Per-mailbox cap stays 15. Capacity is per MAILBOX NAMED on the campaign,
never per mailbox attested to the human.

## 6. NOT DONE, IN PICK-UP ORDER

1. **Restart `slack_agent_loop` bare.** Then merge Slack **C3**, post "Phase C
   live" in #resonate-os, and verify with "@Resonate OS what was sent today"
   to prove it answers from provider membership.
2. **Adopt `scripts/slack_history.py --loop` as a bare heartbeating monitor
   WITH CHANNEL EXCLUSIONS**: never pull any channel whose name or purpose is
   finance, payroll, HR, admin or credentials. **List the excluded channels in
   the register.** Raw history stays in `work/`, gitignored.
3. **Report before anyone edits it**: does `productive_li_heavy_v1` carry 5 or
   6 LinkedIn steps, and which is the approved cadence? The agent session's
   `variants.py` change is additive and the engine's 218 tests pass.
4. **The 18:00 #resonate-os summary was NOT POSTED.** Its numbers are in
   section 2 and are the real ones.
5. **The QUALIFIED-only client export (decision B).** The client deliverable,
   promised today. Not started.
6. **The S3 re-run under decision D**, then MX, collision with the recency
   rule, client suppression, S5 in the recorded order, S7.
7. **Re-size open batches to decision E**; report per campaign leads, backlog
   days, first-step capacity, and the HeyReach rate used.
8. **The AU ninth campaign and the 289 US re-engagement leads.** The bounce
   stop that blocked these is cleared, so they are buildable: stats,
   15-minute veto, push.
9. **37 REVIVE drafts to #replies-productive**, 20 a day. Not started.
10. **The learning doc** once the walk completes, automated-vs-human first.
11. **The 90k lead walk**, resumable, paused in sending windows.

## 7. THE THING MOST LIKELY TO BITE THE NEXT SESSION

**Four of the eight instructions this session received described work that was
already finished, and one described a method that had been measured and
disproved.** The handoff said so in both cases; the instruction did not.
Checking cost four tool calls. Re-running the "fix" for a green guard would
have meant editing files that were already correct.

Verify before acting, including against the operator's own instruction. Twice
today that was the only thing between a stale premise and a production write.
