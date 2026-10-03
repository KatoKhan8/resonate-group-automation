# TASK-976 — the three entry gates: `research_required`, `proof_required`, `offer_unapproved`

The generation-time and send-time half of the operator's copy order, 2026-10-02.
The sequence-level half is TASK-964 and is DONE on `task-copy-exemplars`
(`c49dcefb`); this is what that task file lists as deliberately left out.

**FOUR MEASUREMENTS FIRST, because two of them make this smaller than it
looks and one makes it bigger.**

## 1. None of the three holds exists, and the convention for them does

    grep -rn "research_required|proof_required|offer_unapproved" src/ tests/ scripts/
    -> nothing

`src/eligibility.py:43-99` is the convention: `HELD = "held"`, a `VERDICTS`
tuple, and one constant per reason — `HELD_APPROVAL_MISSING =
"held:draft_not_approved"`, `HELD_EVIDENCE_AGED_OUT`, `HELD_APPROVAL_STALE`.
The three new ones are spelled the same way and go in the same place.

## 2. em3's "never invented" IS ALREADY ENFORCED, and on the right path

`claims.customer_outcome_claim(text, exclude=...)` returns a refusal reason for
a customer-outcome claim with no licensed evidence. It is NOT dead code — the
first reading of the greps said 153 mentions in `tests/` against 2 in `src/`,
which is this repository's signature defect shape, and it was WRONG: the second
`src` mention is `claims.py:747`, inside `def check(text, rec, contact=None,
chosen=())`, and `src/generate.py` calls `claims.check` at **five** sites
(1002, 1107, 1408, 1489, 1669). The rule is live on the generation path.

**So the operator's em3 requirement is a DELTA, not a build:**

- today: a customer-outcome claim with **no** licensed evidence is refused;
- wanted: **at least TWO licensed proof rows per client** before a sequence may
  pass em3, because proofs rotate and TASK-964's rule 4 refuses the same proof
  in two steps;
- and the outcome should be **HELD**, not a regeneration. Today the writer is
  told to try again; the operator asked for the step to be held and reported,
  which is a different verdict with a different consumer.

Licence classes already exist too (`CLIENT_SUPPLIED` vs `CLIENT_APPROVED`,
`claims.py:35-90`) and the 2026-09-27 decision already says `CLIENT_SUPPLIED`
may not license a prospect-facing claim. **Do not invent a licence class.**

## 3. `src/eligibility.py` CONTAINS THE WORD "offer" ZERO TIMES

    grep -n "offer" src/eligibility.py   ->  no matches

So "eligibility holds it HELD `offer_unapproved` until the flag is true" cannot
be a one-line addition: the send gate does not know what offer a step is
written against. Either the offer id travels into `decide` (it already takes
`step`, the exact content, so the natural route is the step record carrying its
offer id), or the hold lives at the call site that DOES hold the offer and
`decide` learns the answer rather than the offer. That is a design choice with
a tenancy edge — `offers.py` is single-tenant (TASK-564 finding 3) — so it is
named here rather than guessed.

The offer itself is already data: `OFFER-GIVE-001` in
`config/clients/productive-offers.yaml` with `client_approved: false`,
committed at `4099a130` with the approver, the date and the SHA recorded.

## 4. The research-row count is already known at generation

`src/generate.py:110` and `:246` both reason about a record's research rows
("695 research rows sit on 203 records"), so `research_required` needs a
threshold and a verdict, not a new data source.

## Scope

1. `HELD_RESEARCH_REQUIRED`, `HELD_PROOF_REQUIRED`, `HELD_OFFER_UNAPPROVED` in
   `src/eligibility.py`, added to `VERDICTS`' neighbourhood the way the
   existing nine are.
2. em1 with **zero** research rows: HELD `research_required`, at generation.
3. em3 with **fewer than two** `CLIENT_APPROVED` proof rows for the client:
   HELD `proof_required`. Reuse `claims`' licence classes and its existing
   refusal; add the count, do not add a second rule.
4. An unapproved offer: **generation ALLOWED, sending HELD.** This is the
   operator's explicit split — "the writer may generate with it in sandbox and
   copy-review, but eligibility holds it HELD `offer_unapproved` until the flag
   is true; same for proof rows: `client_approved: false` blocks sending, not
   generation."

## Acceptance

```
python -c "import sys; sys.path.insert(0,'.'); from src import eligibility as e; missing=[n for n in ('HELD_RESEARCH_REQUIRED','HELD_PROOF_REQUIRED','HELD_OFFER_UNAPPROVED') if not hasattr(e,n)]; assert not missing, 'these holds do not exist: '+str(missing); vals={getattr(e,n) for n in ('HELD_RESEARCH_REQUIRED','HELD_PROOF_REQUIRED','HELD_OFFER_UNAPPROVED')}; assert all(v.startswith(e.HELD+':') for v in vals), vals; assert len(vals)==3, 'two holds share a spelling: '+str(vals); print('OK three holds exist and each is a held: reason -', sorted(vals))"
```

```
python -c "import sys; sys.path.insert(0,'.'); from src import offers; lib=offers.load(); give=lib.get('OFFER-GIVE-001'); assert give is not None, 'the give-first offer is not in the library'; assert give.get('client_approved') is False, give.get('client_approved'); flagged={k:v.get('client_approved') for k,v in lib.items() if v.get('client_approved') is not None}; silent=[k for k,v in lib.items() if v.get('client_approved') is None and v.get('approval_status')=='approved']; assert not silent, 'these offers are approval_status=approved but carry NO client_approved field, so a gate keyed on the flag would hold them: '+str(silent)+' - decide whether the field is backfilled or the gate is scoped, do not let omission decide it'; print('OK every approved offer carries the flag:', flagged)"
```

```
python -c "import sys; sys.path.insert(0,'.'); from src import claims; assert hasattr(claims,'licensed_proof_rows'), 'nothing counts licensed proof rows yet'; n=claims.licensed_proof_rows('productive'); assert isinstance(n,int), n; assert claims.proof_rotation_satisfied('productive') is (n>=2), 'the threshold is not two'; print('OK licensed proof rows for productive:', n, '- rotation satisfied:', n>=2)"
```

### NEGATIVE CONTROL

**All three fail today.** Command 1 on the three missing constants, command 3
on `licensed_proof_rows` not existing — and **command 2 fails for a reason I
predicted wrongly, which is why it is written down rather than quietly fixed.**

I expected it to pass as the control that both cases exist. Measured instead:

| offer | `client_approved` | `approval_status` |
|---|---|---|
| `OFFER-GIVE-001` | `False` | approved |
| 6 others | **absent** | pending |
| `OFFER-A-ECONOMIC-BUYER` | **absent** | approved |
| `OFFER-B-OPERATIONS` | **absent** | approved |

`client_approved` is a NEW field, introduced with the give-first offer. **A gate
keyed on `client_approved is True` would hold all nine offers, including the two
the operator has been running on** — A and B are the live spines in
`messaging_rules`. That is a blanket refusal wearing a gate, and it is the exact
shape this repository keeps finding.

It is also invariant 0 pointing in an uncomfortable direction: absence is
UNKNOWN, unknown must not become a pass, and applying that literally stops the
two offers in production. **So it is the operator's decision and not mine** —
either backfill `client_approved: true` on A and B, making the flag total, or
scope the gate to offers that carry the field and record why the others are
exempt. Either way the field's coverage must be settled BEFORE the hold is
built, which is what command 2 now asserts: no offer may be
`approval_status: approved` while silent on `client_approved`.

The fourth control is the operator's split and belongs in the implementation's
own tests: **generation with an unapproved offer must SUCCEED** while sending is
held. A change that refuses generation has broken the copy-review loop the
operator asked for, not implemented it.

## Files

`src/eligibility.py` (the three constants and the send-side hold),
`src/claims.py` (the count, reusing the licence classes),
`src/generate.py` (the two generation-side holds).

## Not in scope

The contract numbers. em1 90–140 target 120 against `WORD_CONTRACT`'s em1
ceiling of **90** intersect at exactly one value, which is A21 on a new line;
one authority has to be retired and that is the operator's decision, recorded
as §6 decision 2 of the morning handover.
