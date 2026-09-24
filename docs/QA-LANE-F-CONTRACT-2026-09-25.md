# The QA suite contract — `scripts/qa/`, 2026-09-25

**Operator specification, 2026-09-25 ~00:40.** A set of checks that run
**before every push** and **after every activation**, on **both providers**,
**from provider readback wherever one exists**. Each check is a script under
`scripts/qa/`. Each returns **pass/fail with the offending ids**. **A push is
REFUSED if any pre-push check fails.** **One QA table per push in
`#resonate-os`.**

This document is the interface. It is written before the checks so that eight
workers can implement eight check groups in parallel without waiting on each
other, and so that the table can be rendered mechanically from their output
rather than by hand.

    Lane F is Qwen-owned.  Qwen implements with tests.
                           GLM reviews the refusal logic.
                           The production session wires the push refusal and
                           the watchers.

**Nothing in this document is implemented yet.** `scripts/qa/` does not exist
on any branch as of `24acafff`. The eight tasks TASK-292 … TASK-299 build it.

---

## 0. THE THREE THINGS THIS CONTRACT EXISTS TO PREVENT

Every shape below is measured in this repository, not imagined.

**A check that passes because the thing it checks is absent.** ISSUE-041:
`inbound._stop_at_provider` gates the LinkedIn stop on
`contact["heyreach_lead_id"]`, and **ZERO contacts in `work/queue.jsonl` carry
it.** `summarise_stops` renders that as `"linkedin: no lead"`, explicitly NOT
a refusal. Every cross-channel stop this estate ever ran therefore reported
success without calling `heyreach.stop_lead_in_campaign` once — and read
exactly like a working one. **So: a check whose subject set is empty is never
a PASS.** It is `VACUOUS`, it exits 2, and pre-push it refuses.

**A check that reports a count.** `74 failures` and `74 failures` compare
equal while a different 74 tests fail; the 2026-09-23 host comparison hid 17
host-only failures behind two counts that differed by exactly 17. **So: every
verdict in this suite carries the SET of offending ids, and any diff against a
previous run is taken in BOTH directions.**

**A check that is green against a fixture.** ~30 tests were green against
three Apify actor ids that answer 404, because the cassette and the code
agreed with each other and neither agreed with Apify. **So: a check whose
subject exists at a provider reads THE PROVIDER.** A green unit suite is
evidence that the check's logic is right; it is never evidence that the estate
is right.

---

## 1. WHERE A CHECK LIVES

    scripts/qa/__init__.py          the registry: CHECKS, PHASES, verdicts
    scripts/qa/run.py               the runner and the table renderer
    scripts/qa/check_<group>.py     one module per check group

One module per **check group**, not per rule. A group is the set of rules that
share a subject (a lead, a campaign) and a phase, and whose failures force the
same decision: regenerate the copy, re-research the account, fix the campaign
at the provider, or hold the lead. Eight groups:

    lead_state        TASK-293  pre_push   subject: lead
    lead_pack         TASK-294  pre_push   subject: lead
    lead_copy         TASK-295  pre_push   subject: lead
    campaign_bison    TASK-296  pre_push   subject: campaign
    campaign_heyreach TASK-297  pre_push   subject: campaign
    readback          TASK-298  post_push  subject: campaign
    reconcile         TASK-299  ongoing    subject: lead

plus the harness itself, TASK-292.

**A check module that is not listed in `scripts/qa/__init__.py::CHECKS` does
not run.** This is deliberate and it is the answer to the recurring defect in
this codebase — `heyreach.linkedin_sequence` built the whole LinkedIn graph
and had no caller; `run_with_copylint` matched only its own `.pyc`. A check
with no registration is a check with no caller, and the runner's own test
asserts that every `check_*.py` on disk appears in `CHECKS`.

---

## 2. HOW A CHECK IS INVOKED

Every check module is a script AND an importable function. Both, because the
runner imports it and a person debugging one runs it alone.

    py -3 scripts/qa/check_lead_state.py \
        --phase pre_push \
        --batch batch-2-2026-09-25 \
        --campaign 502 --campaign 503 \
        --workspaces <path to a copy of production work/> \
        --json work/qa/2026-09-25T06-00Z/lead_state.json

    from scripts.qa import check_lead_state
    result = check_lead_state.run(phase="pre_push", batch=..., campaigns=[...])

Arguments every check accepts, and ignores when they do not apply:

    --phase       pre_push | post_push | ongoing      REQUIRED
    --batch       batch id                            the subject set
    --campaign    repeatable; provider campaign ids
    --workspaces  path to the `work/` tree to read    REQUIRED, see §7
    --json        where to write the result document
    --live-reads  permit provider reads (default ON for pre_push and
                  post_push; a run without it is marked
                  `"provider_reads": "SKIPPED"` and can never be PASS)

**No check takes a `--fix`, a `--apply`, or anything that writes.** A QA check
is a READ. It may read EmailBison, HeyReach, Apify and the store; it may write
its own result JSON under `work/qa/`; it may write nothing else. A check that
repaired what it found would be a check nobody can re-run to see the defect.

---

## 3. EXIT CODES, AND WHY THERE ARE FOUR

    0   PASS         every subject checked, every rule clear
    1   FAIL         at least one subject offends at least one rule
    2   UNCONFIRMED  the check ran and could not establish the answer:
                     a provider read failed, a window expired, or the
                     subject set was EMPTY (VACUOUS)
    3   ERROR        the check itself broke — import error, bad argv,
                     arithmetic that does not close (§4)

**2 exists because of ISSUE-043 and ISSUE-041, and folding it into either
neighbour reproduces a measured incident.**

Folded into 0: `attach_leads` reads membership back 6 times over ~15s and the
campaign-membership index took **~30 seconds** on 2026-09-24 — lead 205079
answered 200, raised "not in campaign 491 after 6 readbacks", and was present
at t+30s with the count moved 332 → 333. A readback that calls "absent within
the window" a PASS is wrong; one that calls it a FAIL makes a caller re-push a
good push. It is UNCONFIRMED, and UNCONFIRMED is retried.

Folded into 1: every `"linkedin: no lead"` would become a screaming failure on
the ~100% of contacts legitimately staged on one channel only, and the alert
would be turned off within a day.

**Refusal semantics by phase:**

    pre_push    0 proceeds.  1, 2 and 3 all REFUSE THE PUSH.
                There is no retry: nothing has been written, so the cost of
                refusing is a delay and the cost of proceeding is an estate.
                VACUOUS refuses — "0 leads failed the eligibility check"
                is the sentence ISSUE-041 was made of.

    post_push   0 proceeds.  1 raises a CRITICAL notification.
                2 is RETRIED — a fixed schedule, not a loop: t+60s, t+180s,
                t+600s from the push. Still 2 at t+600s becomes 1.
                3 raises a CRITICAL naming the check, not the estate.

    ongoing     0 proceeds.  **1 is ALWAYS A CRITICAL** — operator's word.
                2 is a CRITICAL if it persists across two consecutive cycles.
                3 is a CRITICAL naming the check.

The runner's own exit code is the **worst** of its checks, with a
phase-appropriate mapping. It is not the count of failures and it is not
`0 if not failures else 1` computed from a filter's output — three "green"
runs meant nothing in this repository because a test run was piped into a
filter and the filter's exit code was read.

---

## 4. THE RESULT DOCUMENT

One JSON object per check, on stdout and to `--json`. The shape is
deliberately the one `copylint.check_batch` already returns, extended — the
table renderer, the push refusal and the lint all read the same shape, and a
second shape is how two consumers come to disagree about what failed.

```json
{
  "check": "lead_state",
  "phase": "pre_push",
  "verdict": "FAIL",
  "batch": "batch-2-2026-09-25",
  "campaigns": ["502", "503"],

  "subjects": 128,
  "clean": 121,
  "refused": true,

  "rules": {
    "unverified_by_two_providers": "the address has fewer than two independent verification confirmations",
    "in_live_sequence_elsewhere":  "this person is in_sequence at a provider right now"
  },
  "counts": {
    "unverified_by_two_providers": 5,
    "in_live_sequence_elsewhere": 3
  },
  "offenders": {
    "unverified_by_two_providers": ["rec-0912:jane.doe@…", "…"],
    "in_live_sequence_elsewhere": ["rec-1188:…", "…"]
  },
  "unverifiable": {
    "in_live_sequence_elsewhere": ["rec-0440:…"]
  },

  "evidence": {
    "provider_reads": [
      {"provider": "emailbison", "call": "campaign_lead_ids(491)", "rows": 333, "at": "2026-09-25T06:01:12Z"},
      {"provider": "heyreach",   "call": "campaigns_for_lead(profile_url=…)", "rows": 2, "at": "…"}
    ],
    "files_read": [
      {"path": "…/work-copy-2026-09-25T06-00Z/queue.jsonl", "rows": 1582, "mtime": "2026-09-25T05:58:41Z"}
    ],
    "provider_reads_skipped": false
  },

  "measured_at": "2026-09-25T06:01:40Z",
  "commit": "af7c2539",
  "workspaces": "…/work-copy-2026-09-25T06-00Z"
}
```

### The five invariants the runner enforces on every result

A result that breaks one of these is **ERROR (3)**, not a verdict. The runner
asserts them; it does not trust the check.

1. **`offenders` and `unverifiable` hold IDS, never counts and never
   summaries.** Each id must be one a person can paste into a provider UI or
   grep in `work/queue.jsonl`. `"7 leads"` is not an id. `"…"` truncation is
   not an id.
2. **The arithmetic closes.**
   `clean + |union(offenders) ∪ union(unverifiable)| == subjects`.
   A subject may offend several rules and is counted once. A check whose
   arithmetic does not close has dropped subjects somewhere, and a dropped
   subject is the one that was wrong.
3. **`subjects == 0` is `VACUOUS`, exit 2, and never PASS.** The result must
   also say WHY the set was empty — "the batch has no LinkedIn leads" is a
   legitimate vacuum; "the field this check keys on is absent from every row"
   is ISSUE-041 and must be reported as such.
4. **Every key in `counts`, `offenders` and `unverifiable` exists in `rules`,
   and every key in `rules` exists in `counts`.** A rule that never appears in
   the output is a rule nobody can tell apart from a rule that always passes.
   Rules present with count 0 are printed. That is the point.
5. **`rules` sentences are rendered from THIS RUN's parameters.**
   `copylint.RULES` today reads `"one of the %d steps is empty" %
   STEPS_EXPECTED`, with the module constant at **5** — so a three-step
   campaign under Option A renders a table row saying "one of the 5 steps is
   empty" while the check itself was correctly run at 3, because
   `bisonfactory._copylint_report` passes `steps_expected=len(plan["sequence"])`.
   The check is right and the sentence is wrong, and the sentence is what goes
   in the Slack table. Render rule text at run time.

### `verdict` values

    PASS  FAIL  UNCONFIRMED  VACUOUS  ERROR

`VACUOUS` exits 2 alongside `UNCONFIRMED` because both mean "this did not
establish anything", but they are named apart because they have different
fixes: UNCONFIRMED retries, VACUOUS means the subject set or the field is
missing and somebody has to look.

---

## 5. THE PUSH REFUSAL — WHERE IT GOES, AND WHERE IT MUST NOT

**It goes inside the factory, before the first provider call.**

`src/bisonfactory.stage` already has exactly the right seam. Lane D put the
batch copy lint at line 86 on branch `worktree-agent-a63bd2d9102384dba` @
`c38c5934`, with this comment, which is the whole argument:

> THE BATCH COPY LINT, BEFORE THE FIRST PROVIDER CALL OF ANY KIND. It is here
> and not inside `_ensure_leads` for the reason ISSUE-037 is open: the
> blank-render gate refuses AFTER the attach and its refusal does not roll
> back, so a campaign can be left holding leads a gate has already condemned.

The QA gate goes in the same place, in the same shape, immediately after
`_refuse_copylint`:

```python
    _refuse_copylint(plan, recs, report)
    _refuse_qa(plan, recs, report)          # <- the pre-push suite
    workspace = bison.bound_workspace()      # first provider call
```

and `heyreachfactory.stage` takes the same pair at its own equivalent seam.

`_refuse_qa` raises `FactoryRefused` carrying **the runner's own table**, not a
sentence written at the raise site — the same rule lane D's `_refuse_copylint`
follows, so a rule that did not exist when the function was written still
names itself in the refusal.

**It must NOT go in `scripts/batch1_push.py`, `scripts/batch_preflight.py`, or
any other caller.** TASK-277 is the precedent and it is two days old: the copy
lint was wired into `src/push.py`, a module whose `run()` raises on
`live=True` — *"live push is not implemented in this build… No code here can
reach EmailBison or HeyReach"* — through `run_with_copylint`, a function
nothing called, proved by eight tests that all called it directly and none of
which called `push.run(`. A gate in the caller is a gate the next caller
skips. The real send path is `scripts/batch1_push.py` → `bisonfactory.stage`,
and the gate belongs at the bottom of that arrow.

`scripts/batch_preflight.py` stays what it is: a **pruner** that runs the
factory's refusals early so one colliding contact does not cost forty-four
others their push. It may call the same checks. It is not the gate, and a
green pre-flight is not a licence to skip one.

### The killswitch and the bypass

There is no `--skip-qa` and no `--force`. If the operator needs to push past a
failing check, the check is wrong and the fix is to fix the check — CLAUDE.md
already forbids widening a lint rule to make a draft pass, and this is the
same rule one level up. The one permitted escape is `CHECKS`: a check may be
marked `blocking=False` **in the registry, in a commit, with a reason**, which
makes it advisory in the table and not in the refusal. That is visible in
`git log`. A flag on a command line is not.

---

## 6. THE QA TABLE IN `#resonate-os`

**One table per push.** Not one per check, not one per campaign, not a thread
of them. The notifications channel already went from 103 posts in 72 hours to
4 for exactly this reason, and of those 103, 99 were the client's own traffic
and 2 were ours — two real unmatched replies invisible in the noise for three
days.

Rendered by `scripts/qa/run.py --table`, posted through `src/notify.py` at
`WARNING` when refused and `INFO` when cleared. Never assembled by hand and
never assembled in the Slack agent — one renderer, so the table in Slack and
the table in the refusal text are the same bytes.

```
QA · batch-2-2026-09-25 · pre_push · REFUSED
campaigns 502, 503 · 128 leads · commit af7c2539 · 2026-09-25T06:01:40Z

check              verdict  subj  clean  offending
lead_state         FAIL      128    121  8 (5 unverified_by_two_providers,
                                          3 in_live_sequence_elsewhere)
lead_pack          PASS      128    128  -
lead_copy          FAIL      128    119  9 (9 step1_without_pack_fact)
campaign_bison     PASS        2      2  -
campaign_heyreach  VACUOUS     0      0  no LinkedIn campaign in this batch
readback           -           -      -  post_push, not run

REFUSED. Nothing was written to either provider.
offending ids: work/qa/2026-09-25T06-00Z/TABLE.md
```

Rules for the table, each of which is a defect this project has already
shipped:

- **Every registered check gets a row, including the ones that passed and the
  ones that were VACUOUS.** A table that lists only failures cannot be told
  apart from a table where nothing ran. `campaign_heyreach VACUOUS · no
  LinkedIn campaign in this batch` is a row; silence is not.
- **The header says what was NOT written.** "REFUSED. Nothing was written to
  either provider" is the sentence that stops somebody re-pushing.
- **Ids do not go in Slack; a path to them does.** Prospect identifiers are
  not posted to a channel. The table names the artefact under `work/qa/<run
  id>/` and the counts; the ids live in the file. `docs/PII-SCRUB-2026-09-16.md`
  and the history scan are the standing rule here.
- **The rule names in the table are the check's own `rules` keys**, rendered
  from the run's parameters (§4, invariant 5).
- **A check that did not run is `-`, never `PASS`.** The post-push rows in a
  pre-push table are `-` with the phase named.
- **The commit is in the header.** A table with no commit describes a
  codebase nobody can return to.

The post-push table is the same renderer with `--phase post_push`, posted
within one cycle of the push, and it carries the first scheduled send time per
campaign — because *enrolled is not sent*, and this project's register exists
largely because `active`, `in_sequence` and `scheduled` were each read as a
send.

---

## 7. READING THE ESTATE, AND THE WORKTREE TRAP

**`--workspaces` is required and there is no default.** A worktree has its own
stale `work/`: most worker worktrees have no `work/queue.jsonl` at all, and
the one that did held a copy **37 minutes behind production**. A check that
silently read the local one would answer a question about a file nobody
sends from.

Every check therefore:

- takes `--workspaces <path>`, names that path in `evidence.files_read`, and
  records each file's **mtime** alongside its row count;
- refuses (ERROR) if the path does not exist or the file is empty, rather than
  reporting zero subjects;
- is run by production against a **copy of production's `work/` taken for the
  run**, and the copy's timestamp goes in the result and in the table footer.

**Provider reads are the evidence wherever a provider has the answer.** The
read surface that already exists and must be used rather than re-implemented:

    EmailBison   bison.campaign(id) · campaign_lead_ids(id) · membership(id, ids)
                 sequence_steps(id) · schedule(id) · sending_schedule(id, day)
                 campaign_senders(id) · scheduled_emails(id) · lead(id)
                 find_lead_by_email(email) · fetch_replies() · fetch_events()

    HeyReach     heyreach.campaign_read(id) · campaign_status(id)
                 campaign_leads(id) · campaign_stats(id) · campaigns_for_lead(...)
                 campaign_sequence(id) · connection_notes(seq) · li_accounts()
                 lead_state(row) · readback_membership(id, urls)

**`campaign_stats` before calling a reply ours.** The HeyReach inbox is ~27k
conversations and is mostly the client's; a seat is not a campaign.

**No check makes a provider write.** Not `stop_lead`, not `pause_campaign`,
not `update_lead`, not `attach_leads`. `src/providerwrites.py` `SUPPORTED` is
the authority on what may be written at all, and nothing in `scripts/qa/`
asks it for anything.

---

## 8. THE TWO HOUSE RULES, IN THE ACCEPTANCE BAR OF EVERY TASK

**A suite baseline is a LIST, not a count.** Diff sets in both directions.
`scripts/suite_baseline.py` already measures names and diffs sets; the last
baselines are `docs/state/SUITE-BASELINE-2026-09-23.json` (74 entries, 11,738
tests) and `-MERGED.json`. Report `new`, `gone` and `common` by name. A
one-directional diff hides exactly the case that matters, and a result block
carrying a number and no set is rejected.

**A green suite proves nothing live.** Read the provider and read
`work/*.jsonl`. Fixtures get invented and then mock the buggy function. Every
check in this suite must be demonstrated against the real estate at least
once, with the provider's own named response fields quoted, before its task is
DONE — and the demonstration must include **one constructed failure per rule**
that shows the check firing, because a check nobody has seen fire is
indistinguishable from a check that cannot.

And, operationally: **do not grep for `^FAIL:` mid-run.** A running suite
shows no failures and the grep returns 0. Wait for `suite_verdict.txt`. One
test process at a time; this machine has already died from a runaway
`unittest` process.

---

## 9. WHAT THE CHECKS MUST NOT ASSUME IS FALSE

These are measured. A check written as though they were not is a check that
will be argued with instead of believed.

- **ISSUE-045.** Every one of the 15 EmailBison campaigns is **09:00-17:00
  Mon-Fri in its own timezone**; at 21:36 UTC on 2026-09-24 all 15 were
  closed. HeyReach is 07:00-23:00 seven days. The "timezone cohort has a
  campaign window" check is real, it currently FAILS for out-of-hours cohorts,
  and the two halves of a cross-channel cadence are on different clocks. That
  is a finding to report, not a bug in the check.
- **Option A.** New campaigns get four steps; **485-500 stay three-step**;
  eleven rows legitimately hold three while new ones hold four. Any check
  comparing the provider sequence to "the cadence" must compare against **that
  campaign's own stored `cadence_steps`**, never a module constant.
- **The real step→variable mapping.** `thread_reply_pattern` is
  `[false, true, true, true]`; **em4 reads `{BODY_3}` and em5 reads
  `{BODY_4}`** — the step key is NOT the variable number. Lane B's config is
  on `worktree-agent-a68c1abeb4d3a99f5` @ `472960eb` and is **not landed**,
  deliberately: landing it raises `FactoryRefused` on eleven campaigns until
  the new four-step campaigns exist.
- **Lane D's measurements on the 927 rendered rows.** 636 matched a record and
  **ZERO carry a pack fact**. The researched set (394) and the rendered set
  (554) are **disjoint**. **291 rendered rows (31%) match no queue record at
  all.** 280 unsupported specifics, all at `body_1`, all the company's own
  name — `persona_pain` is the only one of eight templates pairing a direct
  address with `{company}`.
- **Lane D already built `src/packfacts.py` and `scripts/packfact_check.py`**,
  with identity answering **admitted / refused / unverifiable — and
  unverifiable is NOT a pass** — on
  `worktree-agent-a63bd2d9102384dba` @ `c38c5934`, along with the copylint
  wiring in `bisonfactory.stage`. **Build on these. Do not duplicate them.**
  Two copies of an identity test is how the two come to disagree about who a
  fact belongs to.

---

## 10. THE MINIMUM FOR TODAY'S 128

The first QA table runs on today's 128 UK/EU leads before they go, onto new
four-step EmailBison campaigns **502 and 503** (501 is consumed by the
stop-test campaign).

    MINIMUM   TASK-292  harness, return shape, refusal wiring, the table
              TASK-293  per-lead eligibility and state
              TASK-294  per-lead research pack
              TASK-295  per-lead copy
              TASK-296  per-campaign EmailBison
              TASK-298  post-push readback, within one cycle of the push

    NOT IN    TASK-297  per-campaign HeyReach — the 128 are an EMAIL push;
    THE 128'S           this is required before the 825 LinkedIn enrollment
    PATH                across 33 seats, not before today.
              TASK-299  ongoing reconciliation — runs continuously from the
                        first cycle after the push, not before it. It is the
                        one that catches ISSUE-041's class and it is a
                        CRITICAL when it fires, so it must land the same day.

TASK-292 is written so the other seven do not wait on it: the interface they
conform to is **this document**, which is committed and frozen. That is also
why every one of the eight carries an empty `DEPENDS:` line — see §11.

---

## 11. `DEPENDS:` IS PARSED, NOT READ

`scripts/task_registry.py` parses `DEPENDS:` as **comma-separated task ids**
and marks the task BLOCKED when an entry is not in `DONE/`. Lane E wrote prose
there on 2026-09-24 and **nine of its thirteen tasks were invisible to
`claim_task.py`, the tool a worker takes a task with** — ten tasks written to
clear a CRITICAL, four of them actually dispatchable, and green the whole
time.

So in lane F: **`DEPENDS:` carries task ids or nothing.** All eight carry
nothing, because the ordering constraint between them is about *what is useful
first*, not about *what is compilable first* — each conforms to this document
and none imports another's module. The ordering lives in §10 above and in a
`DISPATCH NOTE` block inside each task file, where it is for a person.

**Confirm it, do not assume it.** `py -3 scripts/task_registry.py` prints
READY and the ids; run it after writing and read your own ids in the list.
