# Slack agent — handoff, 2026-09-23 late

Supersedes `SLACK-AGENT-HANDOFF-2026-09-23-NIGHT.md`, which superseded the
evening one. Written to the test `CLAUDE.md` sets: a fresh session on another
machine, with a clone and the secrets supplied separately, should be able to
read this and say what happened and what to do next.

**Branch `slack-agent` at `296d49f9`, pushed.** It merges master at
`9b04873a`. **Master has moved four times today** and may well have moved
again — check before writing anything. See §6.

---

## 1. THE STACK: THREE MERGE REQUESTS, NONE MERGED

    1  docs/MERGE-REQUEST-SLACK-AGENT-PHASE-D5.md
       ab421a5c .. 812b461f — the synthetic second client, both-sided
       isolation, 41 tests, and the sender_summary count fix.
       OLDEST AND STILL UNMERGED. Productive 156 -> 158 and ContactOut
       1 -> 2 are still not live.

    2  docs/MERGE-REQUEST-SLACK-AGENT-INCREMENT-2.md    .. d91ea474
       one account vocabulary; the Monday report and its stop.
       Plus increment 3 (b4114fb8), the PDF-assertion fix (93b4ace2) and
       the PII fix (30bf9920).

    3  docs/MERGE-REQUEST-SLACK-AGENT-INCREMENT-4.md    .. cc05cb4d
       the catalogue enumerated both ways; briefing additions.

    4  docs/MERGE-REQUEST-SLACK-AGENT-INTERNAL-ASSISTANT-MODE.md .. 296d49f9
       internal assistant mode.  NEW

All four are independent of each other except that 2, 3 and 4 stack in
order.

---

## 2. VERIFICATION: ZERO NEW FAILURES, BY NAME, EVERY TIME

    baseline  9788ce2e   11,917 tests   126 failures/errors
    inc 2+3   30bf9920   12,011 tests   121   NEW 0   GONE 5
    inc 4     7fe619a3   12,055 tests   121   NEW 0   GONE 5
    assistant b1647328   running at the time of writing

Diffed **by NAME, both directions**, against the master this branch actually
merged. The failure sets live in the session scratchpad as `base-names.txt`,
`final-names.txt` and `inc4-names.txt`, one fully-qualified name per line.

**Three earlier runs were discarded rather than reported**, and the reasons
matter more than the result:

- one was contaminated by a **mid-run source edit** — `unittest discover`
  imports modules as it walks, so the result described neither tree;
- one was the **nohup wrapper exiting**, not the suite finishing;
- and `scripts/suite_verdict.txt` is a **committed file from 2026-09-21**
  whose `log_file` points at the production checkout. Reading it as your own
  result gives you twelve failures from a two-day-old tree.

---

## 3. WHAT WAS DELIVERED

**Increment 2** — `src/accountstate.py` is now the one account vocabulary;
`slackagenttools` and `web/api` both import it and the four old PDF keys are
retired, not aliased. `src/weeklyreportwatch.py` + `scripts/weekly_report_loop.py`
are the Monday 08:00 schedule with the 07:30 preview and its stop;
`src/weeklyreportpdf.py` feeds `clientreport` the weekly report's own dict.

**Increment 3** — `src/replyverdict.py`. A stored positive is counted only
when its classifier is provably the current RULE SET. Today nothing can show
that, so `positive_confirmed` is 0 and Phase D item 4 reading it posts
nothing.

**Increment 4** — `run_scheduled`, the briefing additions, the catalogue
enumerated in both directions, and the scope refusal no longer naming the
tool to a client.

**Internal assistant mode** — `licence_for(scope)` and the compose opener.

**Additive** — `docs/LEARNED-FROM-OSS-2026-09-23.md` and TASK-266..273.

---

## 4. THE FIVE LIVE DEFECTS THIS SESSION FOUND, AND WHERE EACH WENT

| what | where it ended up |
|---|---|
| `sends_today` correct against live provider membership after the 17:01 merge — 553 of today's sends inside the cap of eight | verified, reported |
| `bison-491` `READ-ERROR 100x PartialInventory` while `campaign_by_id(491)` answered fine — the watcher's inventory read, not the campaign | **production fixed it**, `059b338f` |
| the operator's LinkedIn URL in `HUMAN-ACTIONS-REQUIRED.md`, and the name in `stage_s3_icp.py` | fixed, `30bf9920` |
| the 07:15 briefing asking for six readbacks against a cap of five, so `monitors` was dropped **every morning** | fixed, `7fe619a3` |
| the scope refusal naming the internal tool in a client channel's material; `check_outbound` catches 1 of 5 such sentences | fixed, `7fe619a3` |

---

## 5. THE ONE THING THAT NEEDS THE OPERATOR AND IS NOT A BUG

**`src/testidentity.py` and the hygiene guard cannot both be satisfied as
they stand.**

That module arrived with the master merge. It exists because the operator
replied to their own LinkedIn three times to exercise the cross-channel
stop, and the first reply routed a `positive_reply` to **Productive's own
channel** — a client nearly told the operator was an interested prospect. To
suppress that, the module must name `zbeslic` in `LINKEDIN_SLUGS`.

So a **safety mechanism requires the exact value the PII guard forbids.**
`tests/test_fixture_hygiene.py` is now red in three assertions.

Two honest options, and this is the operator's call:

1. **Move the identity to gitignored config.** Keeps the guard green. But a
   config read that fails would silently stop the exclusion working, which
   is the "silent fallback on a safety path" `CLAUDE.md` forbids.
2. **Give the guard one narrow, documented exemption** for
   `src/testidentity.py` and its test — the files that must know the value
   in order to exclude it. **Recommended.**

Either way, four of the twelve hits are **comments** that do not need the
name — `notify.py:633`, `slackagenttools.py:2259` and the handoff prose
could say "the test identity".

**And the tempting wrong fix is recorded in the guard itself**: the vanity
test has a `FAKE_VANITY` allowlist of INVENTED handles. Adding a real one
there turns the assertion green by retiring the guard for exactly the person
it protects.

---

## 6. THE FIRST THING THE NEXT SESSION MUST DO

**Merge master in, and check it has not moved again.** Master went
`9788ce2e` → `e1f93730` → `059b338f` → `d35fd014` in one afternoon. This
session lost time to a stale base once: `git diff master..slack-agent`
reported **16,117 deletions that were not deletions**, because the branch
was behind the whole infra merge.

    git fetch origin
    git merge-base --is-ancestor origin/master HEAD && echo current

---

## 7. THE QUEUE, IN THE OPERATOR'S ORDER

    DONE  internal assistant mode                      296d49f9

    NEXT  Phase D item 4 - positives to the client channel - ONCE
          rules-4 IS ON MASTER. CHECKED AT 20:30 AND IT IS NOT:
          `replies.VERSION` is still "rules-3" and grep finds no
          RULE_HASH / RULES_HASH / RULE_FINGERPRINT anywhere in src/.
          `replyverdict.current_rule_identity()` returns None, so
          `positive_confirmed` is 0 and the feature correctly posts
          nothing. CHECK AGAIN BEFORE ASSUMING.

          "what are we working on" as a CLIENT answer, and account
          status from the ledger as the write-back lands.

          docs/CLIENT-PORTAL-DESIGN.md FOR REVIEW. **Build nothing
          until the operator approves it.**

    STANDING  The Friday OSS survey routine is LIVE:
          trig_01Nhz6SfKB3efg7JpAhqR3gd, first run 2026-09-25 07:03 UTC
          (09:03 Zagreb), claude-sonnet-5, Slack attached, branch
          `oss-survey-<date>` plus a PR, never master. It CANNOT check
          every premise: `work/` is gitignored, so it grounds in code and
          docs and must write anything else as
          `UNVERIFIED (needs work/): <file, count>` rather than guess.

---

## 8. STILL OPEN, AND NOT THIS BRANCH'S

- **`src/replies.py: erlebnismarketing.com`** — the last red hygiene
  assertion that is not the test-identity tension. Left deliberately: that
  file is production's live path to the `rules-4` bump, and this session
  stepped around that collision three times on purpose.
- **The briefing loop is unsupervised.** It is not in
  `scripts/start_monitors.py`'s `MONITORS` table, so it is not restarted on
  reboot and `--status` never reports it.
- **`CLIENT_CHANNEL_GAG` is still on.** No client channel answers anything.
- **The Monday report loop has never been started.** There is no
  `work/heartbeat/weekly-report.json`. First Monday it would fire is
  2026-09-28.
- **Slack has no file-upload route**, so the weekly PDF is written to
  `work/reports/` and a person attaches it.
- **`report_link`** — the fifth tool `SLACK-AGENT-QUESTION-CATALOGUE.md` §4
  ordered; the other four are built.

---

## 9. THE RULES THIS SESSION WORKED UNDER

Unchanged. Never merges or pushes to master — **verified, master is
`d35fd014` locally and at origin, untouched.** Never edits `config/.env`,
`work/`, `src/providers/*` or `scripts/*_watch_loop.py`; production's
`work/` was read and never written. A merge request per increment, delivered
as a doc plus one line in `#resonate-os`. Adversarial probes offline only.

---

## 10. THE THING THIS SESSION LEARNED, AND IT HAPPENED FIVE TIMES

**A test can be green because it is unfalsifiable, and that looks exactly
like a test that passes.**

    assertNotIn(b"...", raw) against a Flate-compressed PDF
      -> the words are not findable in either direction

    every schedule test building `now` from the zone it was pinning
      -> a silent UTC fallback moves both sides together

    a version guard that catches a BUMP but not the DRIFT
      -> the rules moved twice under an unchanged VERSION

    an internal-tool enumeration derived from the registry it polices
      -> a tool MOVED to client-visible shrinks the set, suite stays green

    an override test whose sentence did not open with a compose verb
      -> it never reached the precedence it claimed to test

Not one was found by writing more tests. All five came from **breaking the
code deliberately and being unsatisfied with how little complained** — and
the last two were in files written minutes earlier, by this session, after
it had already written the rule down twice.

The corollary is the working rule: **an attack that moves exactly one test
is a finding about the test file, not evidence of a well-defended code
path.** Five of six attacks moved one test on the first run of increment 2;
three of those were genuinely under-asked.
