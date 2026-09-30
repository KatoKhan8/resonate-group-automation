# Canary handoff — 2026-09-30

Format: CLAIM / AUTHORITY / MEASURED AT / STATE. Invariant 0 applies: an
unreadable authority is UNKNOWN, and **UNKNOWN never becomes PASS**. A PID, a
branch name or a grep hit is not evidence.

**No prospect PII in this file.** Names, addresses and full copy live outside
the repository at:

    C:/Users/Zvonimir/Desktop/resonate-canary-log/canary-candidates-2026-09-30.txt

---

## a) Scoped generation

    CLAIM      no generation process is running
    AUTHORITY  process table (`ps -W | grep -c python` -> 0) AND the
               harness task notification for job bk58g7a6w reporting
               "completed (exit code 0)"
    MEASURED   2026-09-30, after the obexp/aimclear scoped run
    STATE      FINISHED. There is nothing to protect or resume.

    CLAIM      two candidates produced all five emails, merged to the record
    AUTHORITY  work/queue.jsonl via store.load()
    MEASURED   2026-09-30
    STATE      obexp-com (source row 73)       em1..em5 stored, FIRST attempt
               aimclear-com (source row 116)   em1..em5 stored, FIRST attempt

    CLAIM      westcarygroup-com (source row 1) did NOT converge
    AUTHORITY  the record: em1(105w) em2(88w) em3(81w); no em4, no em5
    MEASURED   2026-09-30, 3 rounds x 10 attempts = 30 attempts
    STATE      HELD. Exact gate message, repeated 6-9 times per 10 attempts:
               "em4: the body is under 40 words" / "em5: the body is under
               40 words". Retry budget for that record: EXHAUSTED.

    CLAIM      both converged candidates are blocked at ONE gate
    AUTHORITY  lint.check via the email-only evaluator
    MEASURED   2026-09-30
    STATE      `domains_contact_no_angle` on em1..em5 for both. The contact
               carries no `angle`.

    CLAIM      the angle stage refuses for both
    AUTHORITY  generate.persona_angle
    MEASURED   2026-09-30
    STATE      SchemaError after 3 attempts: "evidence not traceable to the
               record: contact record: <contact> is <title>; contact
               record: persona is economic_buyer; contact
               record: angle is 'finance'. Every specific claim must come
               from the record." obexp-com has 3 admitted rows and all three
               are site NAV BOILERPLATE ("MENU 01 Home 02 Work 03 About...").

    LOGS       repo-external log above; run outputs under the session
               scratchpad `.../scratchpad/scoped_next.txt`,
               `.../scratchpad/serial_run.txt`, `.../scratchpad/cand_*.txt`

## b) Exact command to resume

    cd /c/Users/Zvonimir/Desktop/resonate-group-automation
    QUEUE_LOCK_TIMEOUT=280 LLM_MODEL="openai/gpt-4.1" PYTHONUTF8=1 \
      PYTHONPATH=. py -3 scripts/generate_one_contact.py <record-id> \
      <contact-key> <rounds>

`scripts/generate_one_contact.py` is the committed copy of the scoped
generator. It deep-copies the record with ONE contact, generates, and merges
only email steps back inside one `store.transaction`.

**PARALLEL GENERATION ON ONE QUEUE IS FORBIDDEN.** `store.transaction` holds
a cross-process lock across the whole read-modify-write and the model calls
happen inside it; `LOCK_TIMEOUT` is 10s by default so siblings fail, and
raising it past `LOCK_STALE_AFTER` (300) would let a waiter steal a live
lock and have both rewrite the whole queue file. Use
`QUEUE_LOCK_TIMEOUT=280` and run one at a time.

## c) Fallback candidate order

    rkconnect-com  -> obexp-com -> nuvolum-com -> aimclear-com

Email only, scoped, and an EXACT per-person provider lookup
(`bison.find_lead_by_email`) before generation — the collision index cannot
prove "never contacted" because campaigns 327 (10,008 leads) and 328
(10,915) refuse a partial walk.

    rkconnect-com  no persona -> offer selection will not resolve
    nuvolum-com    no persona -> same
    obexp-com      persona economic_buyer, L1, per-person lookup CLEAR
    aimclear-com   persona economic_buyer, L2, per-person lookup CLEAR

## d) Workers

    CLAIM      no Qwen or GLM worker holds any task
    AUTHORITY  scripts/claim_task.py --status -> "claims held: 0"
    MEASURED   2026-09-30
    STATE      idle. 243 tasks await integration on their branches.

    TASK-931 (GLM adversarial verify)  TODO, never claimed
    TASK-934 (step-scoped rewrite)     TODO, PARKED until after the canary:
                                       it edits the generation path and
                                       would contend with the store lock
    TASK-935 (collision check)         TODO, PARKED: its substance was done
                                       by hand today and the result is in
                                       `work/collision-index.json`

    Worktrees (git HEAD / last commit / dirty files):
      resonate-qwen-worker  a8bff653  2026-09-30T21:14  dirty=1
      resonate-qwen-2       8bc8e5e1  2026-09-30T19:53  dirty=1
      resonate-qwen-3       bbc8d24b  2026-09-30T19:40  clean
      resonate-qwen-4       980f3fdb  2026-09-27T23:10  dirty=2, DIVERGED
                            from its remote; NOT force-pushed, do not reset
      resonate-qwen-8       affe9c83  2026-09-30T19:47  clean

    NOTHING WAS DELETED. No worktree was removed and no task file was
    deleted; the three off-path tasks (281, 293, 372) are released by the
    registry, not destroyed.

## e) Canary checkpoint requirements

Post to `#resonate-os` (C0C3C6MDN9L) and then **STOP and wait for the
operator's GO**:

    all five emails in full text; company and role; personalization level
    L1-L4; licensed facts with their source; the pinned Ivan Mamic mailbox;
    its attested owner; the rendered signature appearing exactly once; the
    per-person collision result; the GLM verify result per item as
    PASS / FAIL / UNKNOWN, where UNKNOWN never becomes PASS.

Signature for the canary: pin ONE of the 12 CONNECTED mailboxes owned by
**Ivan Mamic** (e.g. id 2778 `i.mamic@withproductive-ai.com`) so the
rendered "Ivan / Productive" matches the mailbox owner. No renderer change
before the canary. Those mailboxes send from lookalike domains, not
`productive.io`.

## f) Post-canary list

    read back the actually sent message from the provider and confirm the
      signature resolved (not empty, not a raw {VARIABLE}) - incident C
    merge skills/resonate-v1            84e3b0a6
    merge task-permanent-operator-exclusion  1a3ed3e2  (verified NOT an
      ancestor of origin/master; touches src/channels.py, which changed
      today, so test on the MERGED tree)
    provider signature variable for the ramp, with a negative control for an
      unresolved variable
    durable controller
    re-contact rule with Bruno
    credential rotation before the ramp
    fix Qwen dispatch (the pool took backlog instead of the named tasks)
    LinkedIn ledger
    cross-channel stop

## g) Safety — unchanged

Freeze ON. `sending.live` = false. Zero provider writes. **Nothing sent by
this work.** 487/489/493 and the client's campaigns untouched. No send,
activate, resume, enrol or attach without the operator's explicit
APPROVED/GO. No gate weakened.

## The decision that blocks everything

`lint.MIN_WORDS = 40` refuses any body under 40 words, while the operator's
sequence-shape decision of 2026-09-30 defines em2 and em4 as **short**
thread replies. A real reply is 20-30 words. That contradiction is why
em4/em5 are refused on 6-9 of every 10 attempts and it is the top blocker.
Not changed here: `MIN_WORDS` is a gate and the decision is the operator's.
