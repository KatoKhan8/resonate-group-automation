# Compliance: what the system enforces and what the operator must do

This document separates **system guarantees** from **operator obligations**.
A compliance claim that lists an operator obligation under "enforced" is the
most dangerous artifact this repository could produce, because it is the claim
a regulator will test against and the claim an auditor will rely on.

**Current state: the system enforces suppression on send. Nothing else on this
page is a system guarantee yet.**

---

## 1. What the system enforces

### 1.1 Suppression on send

Every prospect-facing provider write passes through `executionguard.authorize`,
which runs a suppression check against a closed vocabulary of reasons:

| Reason | Source | Enforced at |
| --- | --- | --- |
| `blocked:suppressed` | `eligibility._suppressed` :276 | gate 4 |
| `blocked:client_suppressed` | client list via `ingest.load_suppress` :109 | gate 4 |
| `blocked:agency_dnc` | `agencydnc.lookup` — sha256 fingerprints, closed reasons `REQUESTED`/`LEGAL`/`COMPLAINT`/`INTERNAL` | gate 4 |
| `blocked:account_suppressed` | account-level stop | gate 4 |
| `blocked:unsubscribed` | reply classifier via `accountpolicy.apply_reply` :604 | gate 4 |
| `blocked:contact_stopped` | per-person stop | gate 4 |
| `blocked:replied` | reply on record | gate 4 |

The suppression check is a **set intersection** against `SUPPRESSION_REASONS`
(`executionguard.py:115-123`), not a substring match on serialised JSON. The
comment at `executionguard.py:608-615` records why:

> This was `"suppress" not in json.dumps(decided).lower()` which refuses on
> any reason containing the word — including a CLEAR one such as
> "suppression: none" — and passes a suppression whose reason happens to be
> spelled differently.

A gate that misfires is a gate somebody deletes. The declared reasons are the
contract.

### 1.2 Provider-side stop sweep

`leadstop.sweep` :192 stops prospects at the provider (HeyReach) when they
must not be contacted. The sweep is operator-initiated and the stop is
provider-confirmed: a stop that cannot be confirmed raises `StopUnverified`.

### 1.3 The killswitch

`killswitch.require` refuses every send when the global layer is off.
`push.run(live=True)` raises `LiveSendNotEnabled` in code. This is the
strongest guarantee in the repository and it has never been wrong.

---

## 2. What the system does NOT enforce

Each of these is a sentence the operator must be able to answer, and none of
them is a system guarantee today.

### 2.1 There is no unsubscribe mechanism

`src/replies.py:161-163` records the fact:

> the estate has no unsubscribe link so opt-out arrives only as a reply
> somebody has to classify.

Opt-out today is `UNSUBSCRIBE_PATTERNS` (`replies.py:157`) plus
`accountpolicy.apply_reply()` :604 — a classifier that reads a reply and
moves the record's state. There is no `List-Unsubscribe` header on outbound
mail. There is no provider field through which to set one: the EmailBison
sequence-step payload is `{order, email_subject, email_body, wait_in_days,
active, variant, variant_from_step, thread_reply}` (`providers/bison.py:1467-
1513`), and `bison.headers()` :34 is the API's HTTP authorization header, not
a mail header.

`List-Unsubscribe` appears **nowhere** in this repository — zero hits across
`*.py`, `*.md`, `*.json`, `*.yaml`.

**Operator obligation:** until an unsubscribe affordance is added to every
cadence step or a provider-level setting is named and evidenced, the estate
relies on reply classification to honour opt-out. A compliance gate in
`executionguard.py` refuses any cadence step that carries neither.

### 2.2 The 180-day silence is declared and dead

`src/replyengine.py:138-139` holds two constants quoting the operator:

```python
POST_DECLINE_QUESTIONS = 1
DECLINE_QUIET_DAYS = 180
```

**Neither constant is referenced anywhere else** — not `src/`, not `tests/`,
not `docs/`. There is no `last_touched`, `dormant` or `quiet_until` field on
any record. `src/fatigue.py` is a per-week touch cap and a different rule.

**Operator obligation:** after a decline, one short non-sales question at
most, then silence for 180 days. The system does not enforce this. A test
(`test_compliance_gate.test_decline_quiet_days_has_no_enforcing_caller`)
asserts that these constants have no enforcing caller, so the day somebody
wires them up this document gets corrected.

### 2.3 GDPR / legitimate interest / DPA are absent

The only hits for "gdpr", "consent" or "dpa" in this repository are
incidental:

- `evidence.py:197-230` uses "gdpr"/"consent" as vocabulary to recognise that
  a scraped page is a cookie notice, so the classifier can skip it.
- `replyengine.py:149` has `dpa` as a topic the reply engine **refuses** to
  discuss — a commitment topic, not a legal-basis field.

There is no lawful-basis field, no DPA record, no consent store.

**Operator obligation:** the lawful basis for outreach (legitimate interest
under GDPR Art. 6(1)(f)), the data processing agreements with each client,
and the consent record for any contact who was not reached under legitimate
interest are all operator-held, not system-held. A compliance claim that
lists them as system guarantees is false.

---

## 3. The compliance gate

`executionguard.authorize` includes a `compliance` gate inside gate 4 (the JIT
suppression/collision/fatigue block). The gate refuses a cadence step when
neither of these is demonstrable:

1. An unsubscribe **link present in `email_body`** on every email cadence step.
2. A **provider-level setting** outside this module, **named and evidenced**.

The refusal names which affordance the estate is relying on. A gate that
passes because it checked the wrong thing is the failure mode this repository
has hit most often.

The gate is **skipped for staging writes** (`staging=True`), because staging
reaches nobody and a preview that refuses every step is the whole product
refusing itself — exactly the dead end `killswitch.py:277-293` names for
wiring a send-only refusal into `eligibility.decide`.

The gate raises `NotAuthorized("compliance", why, gates)`, carrying the
passed-gate trace so a test can assert that the intended gate fired rather
than merely that something did.

---

## 4. What this document is not

This document does not implement the 180-day silence, the consent store or
the DPA record. Implementing them is separate work and must not be smuggled
in behind a documentation task.

This document does not claim compliance with any specific regulation. It
claims to describe accurately what the system enforces and what it does not,
so that the operator can answer the question a regulator asks.

---

## 5. Operator checklist

The operator must be able to answer yes to each of these, with evidence:

- [ ] Every client has a signed DPA naming the lawful basis for outreach.
- [ ] The 180-day silence after a decline is tracked and honoured, even though
  the system does not enforce it.
- [ ] An unsubscribe affordance is present in every outbound email, or a
  provider-level setting is named and evidenced as handling opt-out.
- [ ] The agency-wide do-not-contact list is reviewed weekly and the reasons
  are closed (`REQUESTED`, `LEGAL`, `COMPLAINT`, `INTERNAL`).
- [ ] The killswitch is tested monthly by an operator who is not the one who
  would turn it off in a real incident.
