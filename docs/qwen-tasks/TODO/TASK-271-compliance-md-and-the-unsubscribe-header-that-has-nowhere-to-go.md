# TASK-271 — COMPLIANCE.md, and the unsubscribe header that has nowhere to go

SIZE: M
Operator instruction, 2026-09-23: a document saying what the system enforces
(suppression on send, unsubscribe handling, 180-day account silence, GDPR
legitimate-interest basis, per-client DPA) and what the operator must do;
plus a fail-loud gate for `List-Unsubscribe` header presence on every
cadence.

## THE HEADER GATE IS DROPPED. OPERATOR DECISION, 2026-09-24

> *"There will be no unsubscribe link in any campaign. The opt-out mechanism
> is the REPLY."*

**This task is now the DOCUMENT only.** Do not implement the
`List-Unsubscribe` gate described under "THE GATE" below; that section is
kept, struck through in effect rather than deleted, because it records the
measurement that a header cannot be set through this provider at all - which
`COMPLIANCE.md` still has to say out loud.

The obligation the gate was standing in for did not go away, it moved to the
classifier and was implemented on 2026-09-24:

- `replies.UNSUBSCRIBE_PATTERNS` reads a removal request in every language
  this estate sends to, not only English;
- `accountpolicy._suppress_agency_wide` carries the suppression ACROSS
  WORKSPACES through `agencydnc`, which nothing in production wrote to before;
- the latency is measured rather than argued, in
  `tests/test_an_unsubscribe_stops_the_mail_inside_fifteen_minutes.py`.

See `docs/MERGE-REQUEST-2026-09-24-THE-REPLY-IS-THE-UNSUBSCRIBE.md`.

**What `COMPLIANCE.md` must now say about unsubscribe**, and it is a stronger
sentence than the original one: this estate sets no `List-Unsubscribe` header,
has no provider field through which to set one, ships no unsubscribe link, and
the reply classifier is therefore the entire opt-out mechanism - with the
languages it covers, the ones it does not, and the 15-minute figure all named.

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
   **2026-09-24: that is now the DESIGN rather than the gap.** The classifier
   is multilingual and the suppression crosses workspaces; what the document
   must carry is which languages are covered and which are not.
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

**Superseded by the 2026-09-24 decision at the top: the gate is not built.**
This task writes the document and **one** gate. It does not implement the
180-day silence, the consent store or the DPA record — it writes down that
they do not exist. Implementing them is separate work and must not be
smuggled in behind a documentation task.

## ACCEPTANCE

Full offline suite, zero new failures and zero new errors against the master
baseline, diffed by test NAME both directions.

Required tests: ~~a cadence with no unsubscribe affordance is refused; the
refusal names the `compliance` gate and carries the passed-gate trace; a
cadence relying on a provider-level setting must name it or be refused; a dry
preview is **not** refused by this gate~~ — **all four dropped 2026-09-24 with
the gate** — and a test that reads `DECLINE_QUIET_DAYS` and asserts it has no
enforcing caller, so the day somebody wires it up this test goes red and the
document gets corrected.

## FILES FORBIDDEN

    src/clientapproval.py    src/providers/*    config/    work/*.jsonl
