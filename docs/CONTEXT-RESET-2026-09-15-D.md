# Context reset checkpoint D, 2026-09-15 overnight

Supersedes `CONTEXT-RESET-2026-09-14-C.md` where they disagree. Everything
here was read from git, from a provider, or from a test process this session.
Nothing is inferred from a plan.

**THE TWO LINES THAT MATTER MOST, and one of them is a stop:**

    EmailBison carries step AND variant identity - verified end to end
    LEADS ARE BLOCKED - the copy that passes every gate fails a human

---

## 1. THE HEADLINE, AND IT IS NOT A VICTORY

The system got closer to sending and then deliberately did not send.

Two independent human reads - TASK-064 on LinkedIn, TASK-063 on email -
found that copy passing **every automated gate this repository has** fails a
person reading it. Productive named zero times in the 12 pushable LinkedIn
messages, sender identity in zero of 165 email steps, and four askings of one
question where the ladder asks for six different jobs.

**And on both channels the operator's hand-written fallbacks beat everything
the model produced.** The contacts that FAIL the gates fall back to those
lines, so they would have sent better copy than the contacts that PASS.

`docs/LEADS-ARE-BLOCKED-2026-09-14.md` is the decision and the reasoning.
Read it before touching leads.

## 2. GIT - VERIFIED

    master HEAD     fed88e3   (git log --oneline -1 is the authority)
    origin/master   identical, pushed
    worktree        clean
    commits         21 on master this session, all pushed

Round-1 worker branches (`qwen-worker`, `-2`..`-8`) are UNCHANGED and still
pushed. Round-2 and round-3 branches (`-r2`, `-r3`) were cut fresh from
master because the round-1 branches predate the HeyReach write and would
delete four files and two test modules if merged. **Never merge a worker
branch wholesale.** Every integration this session took named files only.

## 3. PROVIDER TRUTH - THE BIG WIN

`docs/BISON-PROVIDER-TRUTH-2026-09-14.md` with TWO Claude review sections
appended, and `docs/BISON-API-CAPABILITY-MAP-2026-09-14.md`.

**Step-level AND variant-level attribution are REAL.** Verified end to end by
Claude against the live estate:

    reply 1609180
      -> scheduled_email 22290485
      -> sequence_step_id 4039
      -> variant=True, variant_from_step=4037

A real reply resolving to the exact VARIANT that was sent, through provider
fields alone. So five-variants-per-position is measurable AT THE PROVIDER and
**no Resonate-owned experiment ledger is needed.**

    A  historical per-lead/per-step sends with timestamps   PROVIDER FACT
    B  reply -> step                      PROVIDER FACT, but TWO HOPS
    C  position reconstructable           yes, fallback only
    D  variant identifier                 PROVIDER FACT

**B is two hops, not one.** TASK-069 said "directly supported" and TASK-071
disagreed; TASK-071 was right. A reply carries `scheduled_email_id` and NOT
`sequence_step_id`. Calling it direct sends the next reader hunting a field
that does not exist.

### Three corrections that would each have produced a false number

    sent_at is NOT uniform    campaign 274 has 30,411 scheduled rows and
                              ZERO of its first 100 pages are sent. Count
                              rows WHERE sent_at IS PRESENT, never meta.total.
    the reply feed is 270,047 rows, not 750. An earlier read stopped at 750
                              and mistook its paginator for the provider.
    open_tracking is FALSE on every campaign. Zero opens is an ABSENT
                              MEASUREMENT. Any open-rate number is fiction.

### The constraint nobody had measured: PAGINATION

    per_page=15  -> 15 rows
    per_page=100 -> 15 rows

`per_page` is accepted and ignored on every route. Offset pagination is
REFUSED with 422 beyond ~500 pages. Campaign 352 is ~95,000 scheduled emails,
so a full walk is ~6,400 sequential requests plus one per reply for the join.

**Cadence learning is limited by REQUEST BUDGET, not by provider truth.** Any
analysis must sample deliberately and say what it sampled.

## 4. WHAT THE LEARNING ACTUALLY SAYS

`docs/BISON-CADENCE-FINDINGS-2026-09-14.md`. Every number a lower bound from
a sample.

    campaign 352   0.4% reply    409 / 92,806 sent
    campaign 327   0.3% reply    114 / 44,976
    subjects       82.1% statement-led, 17.9% question-led
    delays         0-14 days between steps, 3-day gaps most common
    variants       39 across 5 parent positions, but 14-28 sends each and
                   0-1 replies - NOT a sample anybody can rank arms on

**The 8.49% reply rate for 8-step sequences is NOT REPRODUCED.** It has been
carried in handoffs since an earlier session. TASK-070 tried to re-derive it,
could not, and said so instead of repeating it. The reply sample reaches back
about two months; older campaigns' replies sit outside it. Settling it needs
the full 270,047-row feed, roughly 7.5 hours. **Do not quote 8.49% as a
finding.**

### The classifier number that reframed itself

73.6% of LinkedIn replies were "unreadable". TASK-066 classified all 3,869
unknowns by failure mode:

    53.4%  GENUINELY AMBIGUOUS, correctly unknown   "thanks", "hi", "ok"
    23.8%  no pattern matched
    11.9%  missed positive, most still ambiguous
     4.8%  emoji only
     2.5%  missed negative
     2.3%  missed not_relevant

The largest bucket is the classifier being RIGHT. The real gap is about a
third of replies, not three quarters. Unknown moved 73.6% -> 70.0%.

**A hypothesis died:** `unknown_direction_count` is 0 across all 76,315
touches. The unreadable bucket is NOT our own outbound copy. Extraction is
not the defect; it is purely a pattern gap. That question is closed.

## 5. THE REPLY TAXONOMY - MEASURED, AND MOST OF IT WAS WRONG

    category         precision  recall
    INTERESTED            0.44    0.62     <- more than half wrong
    MEETING_INTENT        1.00    1.00
    OBJECTION             1.00    0.67

263 replies, 200 drawn at random from the UNKNOWN pool, hand-labelled.

ONE pattern - a bare `interesting|intriguing|intrigued` - caused 21 of 29
false positives. **In outbound sales "interesting" is a politeness marker,
not an interest signal.** "Sounds interesting, but..." was a refusal 29 times
out of 52.

MEETING_INTENT and OBJECTION measured 1.00 because they were built out of
ACTS (naming a time, stating a constraint) rather than manners. That is the
distinction, and it is worth keeping.

Acted on: the bare adjectives are removed and replaced with specific
constructions. The NOUN-PHRASE form is refused entirely - "that's an
intriguing approach" and "this is an interesting waste of my time" are the
same shape and the noun decides which is which, so no pattern separates them.
A genuine one is lost with it, on purpose.

    MEETING_INTENT and OBJECTION  may carry learning claims, recall stated
    INTERESTED                    may NOT - 0.44 was the OLD pattern set and
                                  the new one is UNMEASURED, which is not the
                                  same as good. A re-measure is owed and unqueued.

## 6. THE TWO RULES THAT SAVED THE NIGHT

**A wrong POSITIVE lets automation keep contacting somebody who said no.**
TASK-067's taxonomy turned 10 of 13 refusals into POSITIVE - "Not
interesting.", "interesting spam", "Tell me how you got my number." Rejected.
Its own 16 tests passed because they only ever tested "not interested" with a
**d**, which production rules already catch, and never "not interesting" with
a **g**. A green suite written around its own assumption, for the third time
in this repository.

**Approval is a human act and it held.** TASK-072 found `pushable` stuck at
3 of 15 and the blocker is `approval`, not copy quality - eight contacts have
every step generated and none approved. That is `src/approve.py` working
exactly as designed. TASK-064 says the copy must not be sent; TASK-072 says
nobody approved it. **A human has not approved it because a human should not
approve it.** Anyone reading "the structural blocker" as an invitation to
bulk-approve has misread it, and doing so would be the single most damaging
action available.

## 7. PRODUCTION STATE

    HeyReach 599020   DRAFT, 0 leads, 27/27 readback PASS
                      re-verified at the END of the session, after every
                      change. No provider regression.
    EmailBison 451    completed, 1 sent, 0 bounced. Unchanged.
    EmailBison 481    paused, 23 leads, 5 provider steps, 0 sent. Unchanged.
    pushable          3 of 15, and that is NO LONGER the promotion criterion
    leads added       ZERO. Deliberately.
    sends             ZERO this session. Deliberately.

**Nothing was written to any provider this session.** Every provider call was
a read. That is the correct outcome given what the human reads found.

### `pushable` is retired as the promotion criterion

A contact is promotable when it passes the gates AND a person has read its
sequence end to end and would send it. Raising `pushable` while the human
read fails just manufactures more copy nobody should send.

## 8. WHAT WAS FIXED IN THE GENERATOR

    ladder rung 1     now REQUIRES sender identity - all 15 connection notes
                      were anonymous compliments
    ladder rungs 2-6  each now states what the previous rung already spent,
                      so "ask a discovery question" cannot satisfy all six
    email prompt      got the SAME fix, which TASK-075 had missed - sender
                      identity was in ZERO of 165 email steps
    claims rule       grew its FOURTH missing phrase, and checkpoint C
                      predicted it: "as a fellow founder" is an assertion
                      about the SENDER where the rule watched the PROSPECT
    name gate         now checks the campaign GRAPH, not per-lead custom
                      fields. The previous attempt broke 17 tests because
                      custom fields are where a name BELONGS
    bison trimmer     stopped discarding variant, variant_from_step and
                      thread_reply, which the provider populates

A full regeneration against the corrected ladder was RUNNING when this was
written. It does not survive the reset; it is idempotent, re-run it.

## 8b. THE REGENERATION RAN AND REACHED ALMOST NOTHING

**Added after the regeneration completed, exit 0.** Full write-up in
`docs/THE-LADDER-MOVED-AND-THE-COPY-DID-NOT-2026-09-15.md`.

    per-SEQUENCE naming Productive   68%   exactly the pre-work baseline
    li1 says who is writing          33%
    email says who is writing         0%   unchanged
    email "i noticed" openers          49   TASK-063 counted 47

`plan` re-plans a step that FAILS A GATE. That is correct and is what makes
regeneration idempotent. But a stored step records nothing about what
produced it - the complete field list across the estate is `approval, body,
channel, generated, note, subject, template`. No ladder version, no prompt
fingerprint. So when the ladder changes, the old copy still passes every
gate, `plan` says "nothing to generate", and the fix never lands. There is
no `--force` flag either.

**The trap for the next reader:** the copy looks much like what TASK-064 and
TASK-063 condemned, so the tempting conclusion is that the ladder fix did not
work. It did. It was never applied. The numbers above are how to tell those
apart. `ogpartner-dk/jacob-faertz` is a sequence where it DID run - six
rungs, six different jobs, product named once at rung 4, easy out at rung 6.

TASK-079 is the fix. Its deliverable is a dry-run count of how many steps and
approvals a ladder change would invalidate - because an approval is bound to
exact words, so invalidating copy revokes approval, and that must be counted
and visible rather than discovered.

## 9. RUNNING JOBS AT CHECKPOINT

    49280  py -3 -m src.generate --live --client productive
           the regeneration. Safe to lose - store.transaction() commits per
           record. Re-run it; the planner only re-plans failing steps.
    62980  scripts/bison_outcomes_analysis.py
           TASK-070's read-only collection. Left running deliberately; it is
           gathering the evidence the 8.49% question needs.
    47904  qwen worker 4, TASK-059, running since the previous session
    worker 7  TASK-077, dispatched late

## 10. QWEN - WHAT ACTUALLY HAPPENED

    dispatched     16 task-runs across 8 workers
    integrated     17 tasks
    rejected       1 (TASK-067's taxonomy half) - later reworked and landed
    corrected      5 needed Claude to fix or re-scope something material

    TODO      036, 037, 040, 059, 077 (running), 078
    RUNNING   0 on master (workers commit to their own branches)
    REVIEW    0
    REWORK    0
    DONE      70

**Review is not a formality and this session proves it again.** Five of
seventeen integrations needed material correction: a taxonomy that inverted
refusals into positives, a test asserting a stale example, a branch that
would have reverted four files, a "no model access" refusal that was false,
and a precision number that demanded a pattern be deleted.

### The documentation defect worth remembering

`QWEN.md` told every worker that `config/.env` lived only in Claude's
worktree and that generation could not run in theirs. That was true in the
morning and false by the evening. **TASK-075 declined its regeneration on the
strength of that paragraph while holding all three `LLM_*` variables.** The
worker reasoned correctly from a document that lied to it. Fixed in `b0d6a49`.
Check a claim about the environment before you act on it.

### Dispatch mechanics - unchanged and still true

    C:\Users\Zvonimir\AppData\Local\qwen-code\bin\qwen.cmd
        --approval-mode yolo  "<prompt>"

Absolute path; `qwen` is NOT on PATH. Do NOT pass `--max-tool-calls`.
Run each from inside its own worktree. Credentials are in all eight.

## 11. TESTS

    tests.test_replies                        76   REAL_EXIT=0
    tests.test_taxonomy_safety                29   REAL_EXIT=0
    seven classifier modules                 297   REAL_EXIT=0
    name-gate modules                         75   REAL_EXIT=0
    ladder/prompt/claim modules              163   REAL_EXIT=0
    variantgen + generate + lint             125   REAL_EXIT=0
    tests.test_invariants                     80   REAL_EXIT=0

Every exit code read off the process. **Never through a pipe** - a pipe
reports the filter's status.

`tests.test_crash_restart_idempotency` FAILS ON CLEAN MASTER -
`test_crash_between_first_and_second_lead`. Verified pre-existing by running
it on master alone. Not caused by anything this session. Unqueued.

Two module names that DO NOT EXIST and keep getting written into tasks:
`tests/test_accountpolicy.py` (it is `test_account_policy.py`) and
`tests/test_inbound_classification.py`. Check a name before using it.

## 12. FIRST ACTIONS AFTER THIS RESET, IN ORDER

**1. Confirm nothing regressed, cheaply:**

    py -3 scripts/heyreach_readback.py productive-linkedin-production-v1 --expect
    echo $?      # WITHOUT a pipe. Expect 0, 27/27 PASS.

**2. Finish the regeneration if it is not complete:**

    py -3 -m src.generate --live --client productive

**3. TASK-078 - read the regenerated copy.** This is the gate that lifts the
lead block, and the question is not "is it acceptable" but **"does it beat
the hand-written fallbacks"**, which beat all 165 generated emails and all 15
connection notes.

**4. Only if TASK-078 passes:** approve per step, deliberately, then consider
leads. `LINKEDIN_ADD_LEAD` is still not in `providerwrites.SUPPORTED` and
enabling it is a separate operator decision.

**5. Keep eight workers saturated.** TODO has 036, 037, 040, 059, 078.

## 13. WHAT MUST NOT BE REPEATED

- **Do not bulk-approve to raise `pushable`.** It would skip the human read
  and is the most damaging action currently available.
- **Do not re-run the HeyReach write.** It is done and proven. Readback is
  free; a write is an action.
- **Do not widen any gate**, `SUBJECT_VOCABULARY` included. Measured and
  rejected twice now.
- **Do not quote 8.49%.** It is unreproduced.
- **Do not quote any open rate.** `open_tracking` is False estate-wide.
- **Do not count an UNKNOWN as negative**, and do not reduce unknown by
  guessing. 53.4% of unknowns are correctly unknown.
- **Do not read a test verdict through a pipe.**
- **Do not trust a Qwen "tests pass"** without running the NEIGHBOURS.
- **Do not merge a worker branch wholesale.** Take named files.
- **Do not believe a document about the environment** without checking.
  `QWEN.md` cost a whole task tonight.

---

## 14. THE FULL SUITE RAN, AND MASTER WAS ALREADY RED

Run to completion for the first time this session:

    8954 tests, 1937s (32 min)
    10 failures, 7 errors, 5 skipped, 16 expected failures

**Seven of them were then run at `a519954`** - the commit this session
started from - in a detached worktree. They fail there IDENTICALLY: same
names, same count. **Nothing in the 2026-09-14/15 work caused any of them.**

    test_workspace_isolation_attacks    LEAK_the_sanctioned_write_path_
                                        accepts_a_null_client
                                        the_unscoped_default_reads_the_
                                        whole_estate
    test_the_second_client_runs_on_the_same_engine
                                        an_unowned_record_belongs_to_nobody_
                                        rather_than_to_everybody
    test_no_write_happens_without_every_gate   the write door
    test_a_bounced_address_stops_being_sendable
                                        class TheSENDPathReadsIt
    test_ingest TestPhase1Csv           x2, ingest integrity

Three tenancy, one write door, one send safety, two ingest. TASK-086 is
queued and told to start with the tenancy three and STOP if any is a real
leak rather than a stale test. TASK-085 covers the other two
(`test_crash_restart_idempotency`, `test_cadence` company pause).

**The lesson is not that the tests are red. It is that nobody knew.** The
suite takes 32 minutes, so it had not been run end to end, and seven
guarantees - including the ones with LEAK in the name - had been untested for
an unknown length of time. Run it.

### And one of the failures WAS mine

`tests/test_fixture_hygiene` guards against real client data in tracked
files. I tripped it by integrating worker documents without reading them for
PII - the same rule I had written into those workers' own task files.

    docs/LEADS-ARE-BLOCKED-2026-09-14.md
    docs/qwen-tasks/DONE/TASK-072-...md
    docs/qwen-tasks/DONE/TASK-078-...md
    scripts/task065_run_bcd.py          fifteen real prospect domains, baked
                                        into a literal list

All four redacted; the script now reads its record ids from the queue.
`test_no_real_client_prospect_or_roster_domain` passes. The remaining hygiene
failures are pre-existing, verified present at `a519954`.

**Note what this means and does not mean.** Redaction fixes the working tree.
The domains remain in git HISTORY, so this is mitigation rather than
erasure. Anyone who needs them genuinely gone needs a history rewrite, which
is an operator decision.

## 15. THE PROPAGATION FIX LANDED - AND ITS HEADLINE NUMBER WAS WRONG

TASK-083. A ladder change finally reaches the copy, opt-in:

    plan(rec)                             0 ops      <- the defect
    plan(rec, regen_stale_ladder=True)   11 ops      <- the sequence re-plans
    plan(rec) == plan(rec, regen_stale_ladder=False)  True

    py -3 -m src.generate --regen-stale-ladder --client productive
      steps to re-plan:               560
      approvals that would be revoked:  83
      (dry run - nothing was changed)

**That 83 read 0 until Claude fixed it.** The count keyed its approval lookup
on `op["contact"]`, which is the display name "Jacob Faertz", while the
cadence is keyed "jacob-faertz". It missed every time. "0 approvals would be
revoked" is the most reassuring possible wrong answer to the one question the
operator has to decide, and it would have made a destructive run look free.

**So the decision now has real numbers on it: regenerating costs 560 steps
and 83 human approvals.** That is the operator's call, not Claude's, and it
is why the flag is opt-in and reports before it acts.
