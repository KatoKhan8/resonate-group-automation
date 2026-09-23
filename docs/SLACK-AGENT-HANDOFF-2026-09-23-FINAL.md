# Slack agent — handoff, 2026-09-23 final

Supersedes `-LATE.md`, `-NIGHT.md` and `-EVENING.md`. Written to the test
`CLAUDE.md` sets: a fresh session on another machine, with a clone and the
secrets supplied separately, should be able to read this and say what
happened and what to do next.

**Branch `slack-agent` at `48041869`.** It merges master at `9b04873a`.
**Master moved five times during this session** — check before writing
anything. See §7.

---

## 1. THE STACK: FIVE MERGE REQUESTS, NONE MERGED

    1  MERGE-REQUEST-SLACK-AGENT-PHASE-D5.md              ab421a5c..812b461f
       the synthetic second client, both-sided isolation, 41 tests, and the
       sender_summary count fix.  OLDEST, STILL UNMERGED.
       Productive 156 -> 158 and ContactOut 1 -> 2 are still not live.

    2  MERGE-REQUEST-SLACK-AGENT-INCREMENT-2.md                  .. d91ea474
       one account vocabulary; the Monday report and its stop
       + increment 3 (b4114fb8), the PDF-assertion fix (93b4ace2),
         the PII fix (30bf9920)

    3  MERGE-REQUEST-SLACK-AGENT-INCREMENT-4.md                  .. cc05cb4d
       the catalogue enumerated both ways; briefing additions

    4  MERGE-REQUEST-SLACK-AGENT-INTERNAL-ASSISTANT-MODE.md      .. 296d49f9
       internal assistant mode

    5  (no separate doc)                                 f072ddc6..48041869
       the hygiene exemption, `working_on`, and the portal DESIGN

30 non-merge commits since `9788ce2e`.

---

## 2. THE OPERATOR'S QUEUE, AND WHAT EACH ONE ACTUALLY NEEDED

| asked for | delivered |
|---|---|
| increment 2 — Monday report, PDF, new vocabulary | done, MR 2 |
| increment 3 — a `rules-3` verdict is never counted | done, `b4114fb8` |
| increment 4 — catalogue second pass, briefing additions | done, MR 3 |
| internal assistant mode | done, MR 4 |
| the vacuous PDF assertion | done, `93b4ace2` |
| the PII fix, then the guard exemption | done, **13/13** |
| "what are we working on" | done, `f8f848e0` |
| account status from the ledger | **BLOCKED — nothing built, see §5** |
| `CLIENT-PORTAL-DESIGN.md` | done, `48041869` — proposal, no code |
| the standing Friday OSS survey | **LIVE**, see §6 |

---

## 3. VERIFICATION

    baseline  9788ce2e   11,917 tests   126 failures/errors
    inc 2+3   30bf9920   12,011          121    NEW 0   GONE 5
    inc 4     7fe619a3   12,055          121    NEW 0   GONE 5
    assistant b1647328   12,116          125    NEW 3 — ALL THREE ON MASTER
    the queue 48041869   running at the time of writing

Diffed **by NAME, both directions**. The three that appeared at `b1647328`
were **not this branch's**: they arrived with the master merge, and that was
proved rather than assumed — `d35fd014` was checked out in a separate
worktree and the same three fail there. One of them,
`test_a_real_prospect_does_not_match`, is one of master's own brand-new
tests.

**`tests/test_fixture_hygiene` is 13 of 13, from 10 at the start.**

Three earlier runs were discarded rather than reported: one contaminated by
a mid-run source edit, one that was the nohup wrapper exiting rather than
the suite finishing, and `scripts/suite_verdict.txt`, which is a **committed
file from 2026-09-21** pointing at the production checkout.

---

## 4. THE HYGIENE GUARD, AND THE DECISION BEHIND IT

The operator's decision, 2026-09-23: **one narrow exemption for
`src/testidentity.py` and its test, documented in the guard itself.**

`TEST_IDENTITY_FILES` sits beside `SELF`, which turned out to be the same
argument already made once — that file is exempt from its own scan because
it has to name what it forbids in order to forbid it.

**Scoped to the three identity checks** — the name, the handle and the
address — because the module holds `CONTACT_KEYS`, `LINKEDIN_SLUGS` and
`EMAILS` and cannot match on a value it may not hold. `tracked_files` does
**not** skip those files, so phone numbers, live account figures, client
domains and CRM narrative are still checked there and a real PROSPECT
reaching either file still fails.

Config was rejected as the alternative for a stated reason: a read that
fails would leave the exclusion silently not working, and a suppression that
quietly stops suppressing is worse than a name we chose to put in git.

**Everything else now says "the test identity."** Along the way the guard
also caught, and this session removed: the operator's email address from two
tracked files, a client seat holder's name from a handoff, a name in a
`config/clients/productive.yaml` COMMENT (one line, no key, no value, no
behaviour), a real German agency's address that was fixture data in
`src/replies.py`'s comment and in the class-layer test — and `zbeslic` in
**this session's own handoff**, written while explaining the tension.

---

## 5. ACCOUNT STATUS FROM THE LEDGER — VERIFIED BLOCKED, NOTHING BUILT

`_ledger_carries_sends("productive")` is **`False`** against production's own
`work/`. The write-back has not landed.

`account_status` already degrades honestly: it returns `status: None` with
an explicit reason rather than calling an account `untouched` it may have
emailed yesterday. **That degradation is already covered** by 49 tests in
`tests/test_what_is_happening_with_this_account.py`, including the witness
asserted in all three of its states.

So there was nothing to build, and building something would have been the
wrong answer. Re-check `_ledger_carries_sends` before assuming otherwise.

**Phase D item 4 is blocked the same way and for the same kind of reason:**
`replies.VERSION` is still `"rules-3"` and grep finds no `RULE_HASH` /
`RULES_HASH` / `RULE_FINGERPRINT` in `src/`. `replyverdict` returns
`positive_confirmed` 0, so a feature reading it posts nothing.

---

## 6. THE STANDING FRIDAY SURVEY IS LIVE

    trig_01Nhz6SfKB3efg7JpAhqR3gd
    Fridays 07:00 UTC (09:03 first run, 2026-09-25) = 09:03 Zagreb
    claude-sonnet-5 · Slack connector attached
    branch oss-survey-<date> + a PR, never master

**It cannot check every premise, and its prompt says so.** `work/` is
gitignored, so a cloud agent grounds in code and docs and must write
anything else as `UNVERIFIED (needs work/): <file, count>` rather than guess
a number. Of the eight checks on 2026-09-23, five were code-grounded and
three needed `work/`.

The cron is UTC, so after the 2026-10-25 DST change it fires at 08:00
Zagreb — the same drift `digestwatch` already carries.

---

## 7. THE FIRST THING THE NEXT SESSION MUST DO

**Merge master in, and check it has not moved again.** During this session
master went `9788ce2e` → `e1f93730` → `059b338f` → `d35fd014` → and beyond.

    git fetch origin
    git merge-base --is-ancestor origin/master HEAD && echo current

This session lost time to a stale base once: `git diff master..slack-agent`
reported **16,117 deletions that were not deletions**.

---

## 8. STILL OPEN, AND NOT THIS BRANCH'S

- **`CLIENT_CHANNEL_GAG` is still on.** No client channel answers anything.
  `TheGagIsStillOn` asserts the real constant, so the suite goes red the day
  it is lifted — which is when the client-path tests want re-reading.
- **The briefing loop is unsupervised** — not in `start_monitors.py`'s
  `MONITORS` table, so it is not restarted on reboot and `--status` never
  reports it.
- **The Monday report loop has never been started.** No
  `work/heartbeat/weekly-report.json`. First fire would be 2026-09-28.
- **Slack has no file-upload route**, so the weekly PDF is written to
  `work/reports/` and a person attaches it.
- **`report_link`** — the fifth tool `SLACK-AGENT-QUESTION-CATALOGUE.md` §4
  ordered. Smaller now that `weeklyreportpdf` exists.
- **The portal's five decisions**, `CLIENT-PORTAL-DESIGN.md` §9. **Build
  nothing until the operator answers them.**

---

## 9. THE RULES THIS SESSION WORKED UNDER

Never merges or pushes to master — **verified**. Never edits `config/.env`,
`work/`, `src/providers/*` or `scripts/*_watch_loop.py`; production's
`work/` was read and never written. The one `config/` edit was a comment in
`clients/productive.yaml`, diffed to prove it. A merge request per
increment, delivered as a doc plus one line in `#resonate-os`. Adversarial
probes offline only.

---

## 10. THE THING THIS SESSION LEARNED, AND IT HAPPENED SIX TIMES

**A test can be green because it is unfalsifiable, and that looks exactly
like a test that passes.**

    assertNotIn(b"...", raw) against a Flate-compressed PDF
    every schedule test building `now` from the zone it was pinning
    a version guard that catches a BUMP but not the DRIFT
    an internal-tool enumeration derived from the registry it polices
    an override test whose sentence never opened with a compose verb
    "it is a count" with no control proving it is ever a list

Not one was found by writing more tests. All six came from **breaking the
code deliberately and being unsatisfied with how little complained** — and
three were in files written minutes earlier, by this session, after it had
written the rule down twice.

The working rule: **an attack that moves exactly one test is a finding about
the test file, not evidence of a well-defended code path.**

### 10a. And the corollary that saved the most work

**Check the premise before building to it.** Six of eight OSS survey
premises did not survive contact with the code. "Drafting is refused
internally" was false — the refused case was `stop` matching as a **noun**.
"There is no local way to tell a stale verdict apart" was half false — the
`classifier` field was on the events and dropped in projection, and
projecting it did not help, which was the finding. "Account status needs
building" was false: it was already correct and already tested, and the
honest deliverable was a measurement saying so.
