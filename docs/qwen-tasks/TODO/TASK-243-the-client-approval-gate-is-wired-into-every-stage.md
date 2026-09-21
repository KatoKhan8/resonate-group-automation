# TASK-243 — client approval is a gate in the same class as verification

OPERATOR DECISION, 2026-09-21, Zvonimir, additive and binding:

> Client account approval is a hard gate for Productive. Nothing reaches S4
> persona discovery, S5 verification, S7 copy or any enrollment unless
> `client_approval = approved`. This is a gate in the same class as
> verification and collision, and "verification rule weakened" hard-stop
> logic covers it. Show `client_approval` in the account dossier and the
> funnel, and add "awaiting client approval" as its own bucket in the daily
> digest so the supply constraint is visible.

## THE STATE ALREADY EXISTS. YOU DO NOT WRITE IT.

Claude is landing `src/clientapproval.py` on master tonight, because batch 1
cannot push without it. **Rebase onto master before you start** and use it as
given. Its contract, which is fixed:

    clientapproval.state_of(domain, client="productive") -> dict | None
        the effective decision. Latest wins. A `rejected` row is PERMANENT:
        only a row carrying `reverses` + `evidence` can lift it.

    clientapproval.is_approved(domain, client="productive") -> bool
        False for unknown domains. Unknown is pending, pending is refused.

    clientapproval.require_approved(domain, client="productive")
        returns None or raises ClientApprovalRequired(domain, state)

    clientapproval.record(domain, client, state, who, source, at=None,
                          reverses=None, evidence=None, pending_confirmation=False)

    clientapproval.counts(client="productive") -> {"approved": n,
                          "pending": n, "rejected": n}

    store: work/client-approval.jsonl, append-only, one row per decision.

## WHAT YOU BUILD

**1. The gate at four stages, fail-closed, each with its own test.**

    S4 persona discovery      scripts/ and src/ paths that fan an account
                              out into people
    S5 verification           scripts/stage_s5_verify.py, at the point a
                              contact is selected for verification
    S7 copy                   wherever rendered copy is produced per contact
    enrollment                every path that attaches a lead to a campaign

A refused account is SKIPPED WITH A COUNTED REASON, never dropped silently.
The counter name is `awaiting_client_approval`. A stage that skips an account
without incrementing it is the exact defect ISSUE-002 records - `leadstop.sweep`
reported clean because it counted nobody.

**2. The hard-stop class.** The authorization's hard stop 8 names
"verification weakened". A gate that can be turned off by a config flag, an
env var or a default argument is a weakened gate. There must be NO way to
call these stages with the check disabled - no `skip_approval=True`, no
`enforce=False`. Write the test that proves the parameter does not exist.

**3. The surfaces.**

    dossier      `client_approval` with who, when, source
    funnel       a row BEFORE icp_pass: "client-approved accounts"
    digest       a bucket "awaiting client approval" with its count

## ACCEPTANCE - a number

Full offline suite, diffed by test name both directions against the master
baseline at the time you run it. **Zero new failures, zero new errors.**
Report the diff explicitly. Baseline as of tonight: 10,671 / 50 / 33.

New tests required, and they are the deliverable as much as the code is:

- one per stage proving an unapproved account cannot pass
- one proving `pending` and unknown are both refused (fail-closed)
- one proving the skip is COUNTED
- one proving no kill-switch parameter exists on any of the four
- one per surface

## FILES FORBIDDEN

    src/clientapproval.py        ← Claude owns it, rebase and use it
    src/providers/*   config/    work/*.jsonl
    tests/test_the_second_client_runs_on_the_same_engine.py
