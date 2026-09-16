PRIORITY: P0
DEPENDS:

# TASK-170 - the pre-write check for the EmailBison campaign, as a script

## WHERE THIS SITS

EmailBison is the channel closest to sending. Provider truth, measured:

    481   paused, 23 leads, 5 steps, 0 sent     ours
    451   completed, 1 sent, 0 bounced          ours
    15 campaigns total, the rest the client's own history

TASK-159 fixed the sequence: `persona_pain -> comparable_proof -> breakup`,
threading F/T/F. TASK-167 is resolving it against the real queue into an exact
payload. What is missing is the thing that runs in the seconds BEFORE the
provider write, and answers one question: is the world still what we measured?

Claude performs that write. Claude should not perform it by reading a document
and believing it.

## THE QUESTION

Write ONE script that Claude runs immediately before the campaign write, which
exits non-zero and says why if any of the following is not true. Read-only
against the provider.

1. **Identity.** The campaign we are about to write to is the campaign we
   think it is - by id, by name, and by workspace/tenant. A campaign that
   matched by name three days ago is not an identity check. A readback that
   paged 83 campaigns to find one and timed out is already in this
   repository's history - do not reintroduce it, fetch by id.
2. **Tenancy and ownership.** It belongs to Resonate's declared workspace, and
   it is one of OUR campaigns and not one of the client's 13.
3. **State.** Its actual provider state, quoted from the provider, not from
   `PROVIDER-CAMPAIGNS.json`. Local state is a cache and this check exists
   because caches lie.
4. **Emptiness, or a known population.** How many leads it holds and how many
   it has sent. A campaign that has sent is a campaign with history, and
   writing into it is not the same operation as writing into an empty one.
5. **The senders.** Which seats are attached, whether each resolves, is active,
   and has authorization that is currently valid. One seat in the estate is
   active-but-auth-invalid; that state must be detected, not assumed away.
6. **Caps, fatigue, killswitch.** Read the modules that own these and report
   what they currently say for this campaign and these seats. If the killswitch
   is engaged, that is a hard stop and the script must say so first.
7. **Prior contact and collision.** For the contacts in the payload: has any
   been contacted before, on any channel, and is any account already being
   worked. Report per contact.

Every check reports PASS or FAIL with the value it read. A check that cannot
read its input reports FAIL, never PASS - and say in the code why fail-closed
is the only correct default here.

## THE TRAP

A pre-write check that reads local JSON is a pre-write check that passes while
the provider disagrees. For each of the seven, state in a comment whether the
value came from the provider or from local state, and justify every local one.

Second trap: do not make this script capable of the write. No POST, no PATCH,
no PUT, no DELETE, no code path that could become one by a flag. It reads and
it reports.

## WHAT YOU MAY NOT DO

- **No provider writes.** Reads only. Do not create, modify or activate a
  campaign, do not add a lead, do not send.
- Do not add anything to `providerwrites.SUPPORTED`.
- Do not print or commit an API key, an email address, a person's name or a
  domain. Hash identifiers, env var NAME only.
- Do not skip a check because its input is missing - that is a FAIL and a
  finding.

## FILES ALLOWED

    scripts/bison_prewrite_check.py   (new)
    tests/test_bison_prewrite_check.py   (new, fake transport)
    docs/BISON-PREWRITE-2026-09-16.md   (new)

## FILES FORBIDDEN

    src/providerwrites.py   work/   config/

## DELIVERABLE

The script, its tests green with the exit code read off the process, one real
read-only run against campaign 481 with the seven checks and the values they
read, and the fail-closed justification per check.

## RESULT

STATUS: DONE
COMMIT: 80c45f5
TESTS: 32/32 green in tests/test_bison_prewrite_check.py. Full suite running
       at time of writing (scripts/run_suite.py, ~865s expected).
FILES CHANGED:
  scripts/bison_prewrite_check.py   (new, 567 lines)
  tests/test_bison_prewrite_check.py   (new, 505 lines)
  docs/BISON-PREWRITE-2026-09-16.md   (new, 147 lines)

FINDINGS:
  Real run against campaign 481: 6 of 7 checks PASS, 1 FAIL.

  Check 7 (prior contact) correctly detected that ogpartner.dk has 13 prior
  emails at the provider. This is the client's own estate history, not
  something this system wrote. The campaign holds 23 leads with 14 in
  terminal states, confirming real history.

  Check 1 (identity) initially failed because the canonical name did not
  include the [client/campaign_id] suffix that bisonfactory derives. Fixed
  to compare against the derived name.

  Check 6 (killswitch) reports the global layer as OFF (expected - push.run
  raises by design) and the campaign layer as OFF (expected - local status
  is "draft" at staging time). Only a frozen campaign would fail this check.

  All seven checks are fail-closed: cannot read input -> FAIL, never PASS.
  Source annotation on each result states provider vs local, with
  justification for every local value in the check's docstring.

  The script makes no provider writes. No POST, PATCH, PUT, or DELETE.
  No code path can become one by adding a flag.

RISKS:
  - The collision check (check 7) pages through the provider's lead list by
    domain. For very large estates this could be slow. The current campaign
    has 9 unique domains and completed in seconds.
  - The sender health check (check 5) reads the local sender inventory. If
    the inventory is stale, the health assessment may not reflect current
    provider state. The provider-side attachment is always read fresh.

RECOMMENDED CLAUDE ACTION:
  Review the check 7 finding: ogpartner.dk has 13 prior emails. Decide
  whether to proceed with the campaign write or remove that contact from
  the payload. The script did its job - it surfaced a real collision.
