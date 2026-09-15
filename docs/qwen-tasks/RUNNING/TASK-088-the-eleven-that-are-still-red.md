# TASK-088 - the eleven tests that are still red, and were red before

## THE FACTS

The full suite was run twice on 2026-09-15, before and after the session's
integrations:

    first run   8954 tests, 1937s, 17 red
    final run   9065 tests, 1810s, 12 red

Six were fixed, one was introduced and then fixed. **Eleven remain, and every
one of them was red in the FIRST run** - verified by diffing the two failure
lists. None is caused by the 2026-09-14/15 work. TASK-086 and TASK-085
already handled the tenancy set and the crash seam; these are the rest.

    tests.test_ingest
      TestPhase1Csv.test_every_dropped_record_carries_its_reason      ERROR
      TestPhase1Csv.test_queue_has_a_record_for_every_row             ERROR

    tests.test_no_write_happens_without_every_gate
      TheAccountIsAskedToo.test_a_finished_campaign_with_no_reply_still_authorizes
                                                                     ERROR

    tests.test_a_bounced_address_stops_being_sendable
      TheSENDPathReadsIt.test_decide_blocks_a_bounced_address         FAIL

    tests.test_replaysim
      TestThePositiveChain.test_the_company_is_paused_afterwards      FAIL
      TestTheScenarios.test_each_one_classifies_as_documented         FAIL

    tests.test_referral
      TheWholeChain.test_a_plain_hand_off_holds_the_referrer          FAIL

    tests.test_mutation_anchors
      EveryAnchorStillMatches.test_every_guard_appears_exactly_once   FAIL

    tests.test_fixture_hygiene
      TestKnownSets.test_every_phone_number_is_a_reserved_fiction     FAIL
      TestNoRealDataAnywhereInGit.test_every_email_address_is_on_a_reserved_domain
      TestNoRealDataAnywhereInGit.test_no_real_person_or_client_named FAIL

## WHAT EACH ONE GUARDS - START WITH THE FIRST FOUR

**`test_decide_blocks_a_bounced_address`** is send safety. A bounced address
that stays sendable is how a domain reputation dies, and its class is called
`TheSENDPathReadsIt` - the "is it actually consumed" question this repository
keeps getting wrong.

**`test_a_finished_campaign_with_no_reply_still_authorizes`** is the write
door. The module name is the guarantee.

**`test_the_company_is_paused_afterwards`** and
**`test_a_plain_hand_off_holds_the_referrer`** are both about a reply
producing a PAUSE. Note the first expects `pause_reason == "reply_received"`
and gets `"positive"`, and the second finds no contact-level pause at all.
Those two smell related and may share one cause - check that before treating
them separately. A pause that does not happen is invisible until somebody is
contacted after saying no.

**`test_every_guard_appears_exactly_once`** is the mutation-anchor check: it
asserts that each named guard still exists exactly once so the mutation tests
can still fire. Its failure says "these mutations can no longer fire; the
code moved under them", and it named two involving a second unclassified
reply. A mutation test that cannot fire proves nothing, so this one silently
disarms other tests.

**`test_ingest` x2** are ingest integrity - "never delete a queue record,
drop it with a reason" is a rule in `CLAUDE.md` and this is its test.

**`test_fixture_hygiene` x3** are real client data in tracked files. A fourth
one in this class was tripped and fixed during the session, so the mechanism
works; these three are older. Note that redaction fixes the working tree and
NOT git history, so say plainly what a fix does and does not achieve.

## THE QUESTION, EVERY TIME

**Is the TEST stale, or is the GUARANTEE gone?** Opposite fixes, opposite
consequences, and reporting the wrong one is worse than reporting nothing.

The session's evidence cuts both ways and both precedents are worth knowing:

- TASK-086 found three tenancy tests that looked like leaks and were STALE -
  production had got stricter and nobody updated them.
- TASK-085 found one that looked stale and was a REAL regression from the
  previous day: a reply had stopped pausing the company.

So do not assume either answer. Show the evidence.

## HOW TO WORK

1. Run each ALONE first. These all reproduce in isolation, so none is the
   `unittest discover` / `tests.offline` teardown overlap `CLAUDE.md` warns
   about - but confirm rather than assume.
2. Read the traceback. Four of eleven are ERRORs, which often means a broken
   fixture or import rather than a broken assertion - the cheap explanation,
   and it may cover several at once.
3. Classify: fixture, assumption, disconnected consumer, wrong canonical
   model, stale state, wrong identity, wrong tenancy, swallowed exception, or
   a real bug.
4. Fix the smallest root cause.
5. Verify by breaking the thing deliberately and confirming the test fails
   for the intended REASON, and that a different guard did not fire first.

**If any of the send-safety, write-door or pause failures turns out to be a
real broken guarantee, STOP and report it in the first line of your result
block** rather than continuing down the list.

## HOW LONG HAVE THEY BEEN RED

`git log` each test file and the module it exercises and name the commit that
most plausibly broke each. The suite takes 32 minutes, so nobody had run it
end to end - a guarantee untested for weeks is a different problem from one
that broke yesterday, and the session found examples of both.

## WHAT YOU MAY NOT DO

- **Do not delete, skip, `@expectedFailure` or weaken any of these tests.**
- Do not "fix" one by changing what the code guarantees.
- Do not rewrite git history for the hygiene failures. Redact the working
  tree and say what that does not achieve; history is an operator decision.
- READS ONLY at every provider.

## RESULT BLOCK

STATUS, COMMIT SHA, TESTS (exact commands, exact counts, exit codes read off
the process and never through a pipe), FILES CHANGED, FINDINGS - per failure:
classification, TEST-wrong or CODE-wrong, how long red - RISKS, RECOMMENDED
CLAUDE ACTION.

---

## SCOPE NARROWED, 2026-09-15

The three `test_fixture_hygiene` failures are split out into **TASK-095** and
are NOT yours. They guard prospect PII rather than correctness and they need
a leak-or-stale verdict written up separately.

This task is the remaining EIGHT:

    test_ingest              TestPhase1Csv x2
    test_no_write_happens_without_every_gate   the write door
    test_a_bounced_address_stops_being_sendable  send safety
    test_replaysim           x2
    test_referral            TheWholeChain
    test_mutation_anchors    EveryAnchorStillMatches

Start with the write door and send safety. Those two guard a prospect-facing
action; the rest guard correctness. Same question for each, and it has had
both answers in this repository within one session: **STALE TEST, or REAL
REGRESSION?** Check it, do not accept it, and if it is real, say what breaks
in production rather than only what the assertion says.
