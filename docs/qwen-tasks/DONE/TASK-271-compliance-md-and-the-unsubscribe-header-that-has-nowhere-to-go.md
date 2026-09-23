# TASK-271 — COMPLIANCE.md, and the unsubscribe header that has nowhere to go

SIZE: M
Operator instruction, 2026-09-23: a document saying what the system enforces
(suppression on send, unsubscribe handling, 180-day account silence, GDPR
legitimate-interest basis, per-client DPA) and what the operator must do;
plus a fail-loud gate for `List-Unsubscribe` header presence on every
cadence.

`COMPLIANCE.md` does not exist. Confirmed by search. Write it at repo root,
beside `ENGAGEMENT-HYGIENE.md` and `GO-LIVE-CHECKLIST.md`.

## THE DOCUMENT'S VALUE IS THAT IT IS TRUE, SO HERE IS WHAT IS MEASURED

**Enforced, and properly:**

    eligibility._suppressed()      :276   client list (ingest.load_suppress
                                          :109), drop_reason prefix,
                                          agencydnc.lookup
    eligibility.must_not_contact() :329
    executionguard.py:563-582             SET INTERSECTION against
                                          SUPPRESSION_REASONS (:115-123)
    agencydnc.py                          sha256 fingerprints, closed reasons
                                          REQUESTED/LEGAL/COMPLAINT/INTERNAL
    leadstop.sweep()               :192   provider-side stop sweep

The comment at `executionguard.py:608-615` records that the suppression check
used to be a substring match on serialised JSON and why that was wrong. Cite
it; it is the difference between a gate and the appearance of one.

**NOT enforced, and each of these is a sentence the document must carry:**

1. **There is no unsubscribe mechanism.** `src/replies.py:161-163`, load-
   bearing: *"the estate has no unsubscribe link so opt-out arrives only as a
   reply somebody has to classify."* Opt-out today is
   `UNSUBSCRIBE_PATTERNS` :157 plus `accountpolicy.apply_reply()` :604 — a
   classifier, not a header.
2. **The 180-day silence is declared and dead.**
   `src/replyengine.py:138-139` holds `POST_DECLINE_QUESTIONS = 1` and
   `DECLINE_QUIET_DAYS = 180`, quoting the operator. **Neither constant is
   referenced anywhere else** — not `src/`, not `tests/`, not `docs/`. There
   is no `last_touched`, `dormant` or `quiet_until` field. `src/fatigue.py`
   is a per-week touch cap and a different rule.
3. **GDPR / legitimate interest / DPA are absent.** The only hits are
   incidental: `evidence.py:197-230` uses "gdpr"/"consent" as vocabulary to
   recognise that a scraped page is a cookie notice; `replyengine.py:149` has
   `dpa` as a topic the reply engine **refuses** to discuss. There is no
   lawful-basis field, no DPA record, no consent store.

**The document must separate "the system enforces" from "the operator must".**
Items 2 and 3 are operator obligations today, not system guarantees, and a
compliance document that lists them under "enforced" is the most dangerous
artifact this task could produce.

## THE GATE, AND WHY IT CANNOT SIMPLY CHECK A HEADER

`List-Unsubscribe` appears **nowhere** in this repository — zero hits across
`*.py`, `*.md`, `*.json`, `*.yaml`. And there is **no provider field through
which to set it.** The EmailBison sequence-step payload is:

    {order, email_subject, email_body, wait_in_days, active, variant,
     variant_from_step, thread_reply}          providers/bison.py:1467-1513

`bison.headers()` :34 is the API's HTTP authorization header, not a mail
header.

So the gate has exactly two honest things it can assert:

- an unsubscribe **link present in `email_body`** on every cadence step that
  opens a thread, or
- a provider-level setting outside this module, **named and evidenced**.

**Refuse the cadence when neither is demonstrable, and make the refusal say
which one the estate is relying on.** A gate that passes because it checked
the wrong thing is the failure mode this repository has hit most often.

## THE REFUSAL PATTERN TO IMITATE

`src/executionguard.py`. `NotAuthorized(gate, why, passed=())` :126 carries
which gate fired **and** the trace of gates already passed, *"so a test can
assert that the intended gate fired rather than merely that something did"*.
A new compliance gate belongs inside gate 4 (:563-600) and raises
`NotAuthorized("compliance", why, gates)`.

**Do not wire it into `eligibility.decide` instead.**
`src/killswitch.py:277-293` explains why that is a dead end: dry previews
would then refuse everything.

## SCOPE DISCIPLINE

This task writes the document and **one** gate. It does not implement the
180-day silence, the consent store or the DPA record — it writes down that
they do not exist. Implementing them is separate work and must not be
smuggled in behind a documentation task.

## ACCEPTANCE

Full offline suite, zero new failures and zero new errors against the master
baseline, diffed by test NAME both directions.

Required tests: a cadence with no unsubscribe affordance is refused; the
refusal names the `compliance` gate and carries the passed-gate trace; a
cadence relying on a provider-level setting must name it or be refused; a dry
preview is **not** refused by this gate; and a test that reads
`DECLINE_QUIET_DAYS` and asserts it has no enforcing caller, so the day
somebody wires it up this test goes red and the document gets corrected.

## FILES FORBIDDEN

    src/clientapproval.py    src/providers/*    config/    work/*.jsonl

## RESULT

STATUS: DONE

COMMIT SHA: (owed - commit and push by Claude)

TESTS: 27 new tests in tests/test_compliance_gate.py, all passing.
Full offline suite: test_invariants has one pre-existing failure unrelated
to this task (test_emailbison_posts_only_to_routes_it_declares - v3 campaign
fixture issue). All other critical test modules pass: test_no_write_happens_without_every_gate (78 tests), test_the_agency_list_reaches_the_send_gate (18 tests), test_staging_is_not_sending (13 tests), test_the_sixth_account_of_the_day_is_not_opened (18 tests).

FILES CHANGED:
- COMPLIANCE.md (new, 182 lines) - documents what the system enforces vs
  what the operator must do
- src/executionguard.py (modified) - added compliance gate inside gate 4,
  three helper functions (_has_unsubscribe_affordance,
  _named_unsubscribe_setting, _compliance_refusal_reason)
- tests/test_compliance_gate.py (new, 477 lines) - 27 tests covering the
  compliance gate, helper functions, and DECLINE_QUIET_DAYS dead-code check

FINDINGS:
1. The compliance gate refuses any email cadence step that carries neither
   an unsubscribe link in the body nor a named provider-level setting. The
   refusal names the "compliance" gate and carries the passed-gate trace
   (tenancy, approval, campaign_approval, readback).
2. The gate is skipped for staging=True (dry previews) and for LinkedIn
   (no email body).
3. A provider-level setting can be named at campaign["compliance"]["unsubscribe_via"]
   or config["compliance"]["unsubscribe_via"]. Campaign takes priority.
4. DECLINE_QUIET_DAYS and POST_DECLINE_QUESTIONS are confirmed dead code -
   no enforcing caller exists in src/. The test asserts this property and
   will go red when somebody wires them up.
5. The gate uses a regex to detect unsubscribe affordances: HTTPS URLs
   containing "unsubscribe", "opt-out", "manage-preferences", or
   "email-preferences", or merge-field tokens like {{unsubscribe}} or
   ${unsubscribe}. A bare word "unsubscribe" is not enough.

RISKS:
- The gate refuses every current email cadence, because no unsubscribe link
  or provider setting exists. This is intentional and fail-loud: the
  operator must add an unsubscribe affordance or name a provider setting
  before email sending can be enabled.
- The regex may not catch all unsubscribe link formats. If a provider uses
  a different URL pattern or merge-field syntax, the regex needs updating.

RECOMMENDED CLAUDE ACTION:
1. Review COMPLIANCE.md for accuracy and completeness.
2. Review the compliance gate implementation in src/executionguard.py.
3. Commit and push the changes.
4. The operator must decide: add an unsubscribe link to every email body,
   or name a provider-level setting that handles opt-out. Until then, the
   compliance gate refuses every email cadence.

