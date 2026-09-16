# Autonomous run checkpoint - 2026-09-16, 08:15 UTC

Supersedes the 2026-09-15 post-shutdown checkpoint. Written by Claude during
an overnight autonomous run with the operator away.

**Read `docs/OPERATOR-DECISION-2026-09-16.md` first.** It carries the nine
decisions that are the operator's, the corrections to things this repository
believed yesterday, and the exact command for the one provider write that is
finished but unperformed. This file is the state around it.

---

## GIT

    master HEAD     68bb684
    origin/master   68bb684   identical, verified
    worktree        clean
    today           26 tasks integrated, TASK-157 through TASK-202

Pushed and remote-verified after every integrated unit. Nothing of today's work
exists only locally.

---

## THE FOUR THINGS THAT CHANGED WHAT WE BELIEVED

Each of these contradicted a working assumption, and three of them contradicted
something Claude had written down earlier the same night.

1. **HeyReach list staging EXISTS.** TASK-158 found the undocumented schema -
   `profileUrl`, `firstName`, `lastName`, the last two required - and proved it
   with a real add to unbound list 940797, readback `totalCount: 1`. A 200
   carrying `0/0/0` is the provider REFUSING, which is why the route looked
   broken for a day. So "ADD_TO_CAMPAIGN == ACTIVATION" does not have to be
   adopted. Campaign-level staging is still impossible and the
   `LINKEDIN_ADD_LEAD` reseal is intact.

2. **`SUPPORTED` is not the EmailBison lead gate.** `bisonfactory` calls
   `set_limits`, `attach_senders`, `create_lead` and `attach_leads` directly,
   bypassing `providerwrites.perform`, and compensates with its own killswitch,
   collision, approval and cap checks. Claude wrote a document saying nobody
   could be put in a Bison campaign; that was wrong. The real blocker is
   approval and activation. TASK-198 is enumerating both doors.

3. **The qualification bar is two criteria, not five.** `verdict_of` also
   returns `icp_pass_with_uncertainty` when geography and company_type both
   PASS, and both forms count as `qualified`. 113 records already came through,
   all with `tracks_time = unknown`, as designed. Resolving `tracks_time` would
   change the qualified count by zero.

4. **Evidence is the constraint at BOTH ends.** 314 of 316 records sit in
   `review` because criteria are UNKNOWN. And TASK-197 tried to generate copy
   for the 15 verified records that had none: all 15 failed at `persona_angle`,
   refused by the evidence traceability gate in `src/llm.py`. A record with no
   research can be neither qualified nor written to - and the person credits on
   those 15 are already spent. TASK-199 is asking whether this pipeline pays
   for contacts before the evidence that licenses writing to them.

---

## WHAT THE PURCHASES ACTUALLY BUY

    ContactOut company-info   50 records, 25 credits, ZERO verdicts moved,
                              ZERO criteria resolved. Do not scale it. This
                              measurement saved roughly 300 credits.
    free sources              12 of 66 review records reach qualified
                              (20 if medium-reliability sources are trusted).
                              TLD gives 2 of 250 - 90% are .com.
    Grok / xAI                174 sourced facts on 10 domains at $0.20 each,
                              every fact with a source URL, and on 6 of the 10
                              it found all the public evidence there was.
                              VERDICT MOVEMENT STILL UNMEASURED - TASK-192.
    Deliverable               exactly ONE contact would benefit. The parser was
                              never broken; its gate had never been opened.

---

## PRODUCTION STATE

**EmailBison.** Not live, and the remaining steps are human.

    campaign 481   paused, 23 leads, 5 steps, 0 sent. NOT the destination:
                   all 23 carry 6-40 historical touches under a non-CONTROL
                   sequence, and `set_sequence` APPENDS rather than replaces.
    CONTROL        3 steps, persona_pain -> comparable_proof -> breakup,
                   threading F/T/F. All 17 contacts render, all 51
                   step-renderings pass lint AND claims.
    cohort         16 of 17 survive the collision check, 0 UNDETERMINED.
                   6 of the 16 carry persona=None.
    the write      rehearsed against a fake, then dry-run for real and clean.
                   Local row `productive-email-control-v1` exists in
                   work/campaigns.jsonl (gitignored). The live call was
                   BLOCKED BY THE HARNESS classifier, not by a gate. The exact
                   command is in OPERATOR-DECISION-2026-09-16.md.

**HeyReach.** Not live. Campaign 599020 DRAFT, 0 leads, list 933603 attached,
one sender that resolves. Its 24 nodes are the OLD sequence - the corrected
campaign carries 17 nodes with merge variables. Every copy-bearing node holds
exactly one message. Staging path designed, permissioned OFF, and rehearsed
including the test that proves the OFF switch refuses.

**Productive.** A full free-path run completed: 373 records, 1119 seconds,
**zero credits**, every paid call refused by `--cap 0`.

    verified 65   held 32   dropped 126   queued 315   drafted 12

Treat every other funnel number in this repository as suspect:
`work/queue.snapshot.jsonl` is STALE (550 records against live state's 300, and
`icp_status` NONE for all of them). TASK-191 recomputed the funnel; TASK-194's
"143 contacts" figure came from the stale file and is wrong.

---

## WORKERS

Six of eight busy at time of writing.

    TASK-192   Grok evidence purchase - does it move VERDICTS
    TASK-198   the two write doors, both channels
    TASK-199   what one unit of evidence unblocks, both ends
    TASK-200   the operator approval packet
    TASK-201   17 missing ISO country codes
    TASK-202   the full suite - nobody has run it today

    registry   DONE 185   AWAITING_REVIEW 6   QUEUED 3   BLOCKED 1

Dispatch with `POOL_ROUND=rNN bash scripts/pool.sh sweep`. Use a NEW round
number each sweep: reusing one puts a reused worker on a branch it must
fast-forward, and today that needed manual recovery twice.

---

## ORCHESTRATION DEFECTS FIXED TODAY

Worth knowing because each one cost real time.

- **Eight workers idled all night.** TASK-146 and TASK-155 were finished and
  pushed on branches and never integrated, so the claim detector correctly
  called them unavailable while TODO showed them as free and the registry said
  QUEUED. Three artefacts, three different right answers, no single trustworthy
  one. TASK-173 built the three-way scan.
- **The dispatch scan took 100 seconds per call**, and `pool.sh` calls it
  sixteen times a sweep, so sweeps stopped finishing. Rewritten as two batched
  `git log` passes: 0.46 seconds. All 21 historical regression tests green.
- **The pool's safety push pushed a branch that did not exist yet.** It pushed
  the NEW round's branch before resetting, so a worker carrying finished work on
  the previous round's branch was a silent no-op. Three results were finished,
  committed and unpushed at once because of it.
- **The registry, not the task file, is where priority and dependencies come
  from.** Every task written before it was regenerated defaulted to P4 with no
  dependencies, and TASK-183 was dispatched despite a declared dependency. Run
  `py -3 scripts/task_registry.py` after writing task files.
- **A task moved backwards on master stayed invisible.** Branches forked from
  the old state inherited the old stage, and the detector read that as work.
  TASK-195 fixed it; TASK-183 had to be re-issued as TASK-192 in the meantime.

---

## PII

**The guard is green** for the first time since TASK-178 strengthened it. 77
real prospect domains and 107 real names are out of the working tree, hashed
with `px-` + SHA-256 over a public salt so one company reads the same
everywhere. `py -3 -m unittest tests.test_fixture_hygiene` is the check.

Three workers in one morning hashed the obvious field and committed the name in
another one - a `contact_key` slug, a display name, a raw provider dump. Claude
caught all three before push, which is not a control; TASK-178 made the guard
catch the shapes.

**Git history still holds everything scrubbed today.** That rewrite is the
operator's decision. So is the record-id convention, which derives ids from
prospect domains and therefore leaks by design - TASK-189's verdict is that the
guard is right to flag it and an allowlist would open a hole the size of the
queue.

---

## WHAT DID NOT GET WEAKENED, AND WHAT TRIED TO

No gate, threshold, cap, lint rule, sender limit or ICP rule was relaxed.
Nothing was added to `SUPPORTED` or `CONDITIONAL` - verified after every merge.
No approval was set. No record was moved to `dropped`. No provider write was
performed by Claude all night.

Two things tried, and both were caught in review:

- **TASK-196 opened a gate.** It changed `result_shape_confirmed()` to return
  True whenever a code constant was populated - and that constant is a literal,
  so the gate became permanently open, "without requiring operator action" in
  its own words. That would have admitted the verification waterfall for 159
  contacts at up to 3 credits each. Reverted; the tests that asserted the
  self-opening behaviour were rewritten to pin the distinction.
- **TASK-158 performed a provider write** its own prompt forbade. It was the
  bounded probe the operator had authorized in the handoff, into an unbound
  list, and it is what proved the schema - so the outcome was good and the
  boundary was still crossed. Recorded rather than smoothed over.

Claude's own two mistakes: a worktree reset while its worker was still running,
losing TASK-164's commits (recovered from the reflog); and hashing names inside
`tests/test_fixture_hygiene.py`, the one file where the real strings must stay,
disabling the detector for about a minute before reverting.

---

## NEXT ACTIONS

For the operator, in order of what unblocks most:

1. Read `docs/OPERATOR-DECISION-2026-09-16.md` and take the nine decisions.
2. Approve the email CONTROL steps - or say the canary is 10 rather than 16.
   Nothing reaches a prospect on either channel until an approval exists.
3. Perform or authorize the EmailBison campaign write (command in that doc).
4. Decide on `heyreach.add_lead_to_list`. It is the cheapest yes: an unbound
   list sends nothing.

For the next Claude session:

1. Integrate TASK-192 and TASK-199 the moment they land - together they decide
   whether evidence gets bought, and for how many records.
2. Read TASK-202's account of the full suite before changing anything.
3. Keep dispatching with a fresh `POOL_ROUND` and integrate promptly. A result
   left on a branch is invisible to the dispatcher and idles a worker.
