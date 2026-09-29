PRIORITY: READ WITH THE RACHELE MILESTONE

# RACHELE — REVOKED, REGENERATED, AND BLOCKED ON TWO GATE BLIND SPOTS

    milestone SHA   53dc50c8   (local == origin/master, stamped, unmoved)
    account         2020 Companies / 2020companies.com
    contact         Rachele Crumpler, CFO, rachele-crumpler
    approval hash   7a88ddb693515854   (this artifact, not approved)

    MACHINE APPROVAL   REVOKED CANONICALLY
    LEGACY li6         RETIRED CANONICALLY
    STRUCTURE 5+5      PASS
    GATES              PASS (lint, claims, copylint, repetition)
    COPY QUALITY       **FAIL** — two items no gate enforces
    SLACK              NOT POSTED

Nothing sent by this work. Provider writes 0, enrolments 0, prospect-facing
sends 0, campaign activation 0, `sending.live` false. `work/campaigns.jsonl`
unchanged.

---

## 1. WHAT THE OPERATOR AUTHORISED WAS DONE, EXACTLY

**Revocation** through `approve.revoke()`, with a scope guard that asserted
`by == "claude"` and `at == "2026-09-13T21:47:32+00:00"` on every step before
touching it. Five approvals revoked, fingerprints recorded:

    em1 2d94c3ced8e27065   em2 02bd385015c54ce4   em3 75d6f1510b2bfe27
    em4 84f3646f34fe617b   em5 3b0dc03315f80f73

`is_approved` is now False for all five; nothing else on the record was
touched, and `rachele-crumpler` is the only contact on it.

**li6 retired** through the canonical `stepstate` path — `CANCELLED`
("ended deliberately", terminal), with history provenance
`{from: null, to: cancelled, at: ...}` and a `step_retired` log line naming
it a legacy step outside `cadencelibrary.LINKEDIN_WRITER_KEYS`. **Not
deleted** — "never delete, drop it with a reason".

**Regenerated** through `generate.run(live=True)`, the real entrypoint. The
old 2026-09-13 copy is gone; subjects are now
`"project margin visibility during execution"` and
`"tracking budget burn in real time"`, and the old
`"Driving Measurable Retail Growth"` copy that failed the claim gate no
longer exists on the record.

## 2. EVERY MEASURABLE GATE PASSES

    lint                 clean on all 10 steps
    claims (TASK-917)    clean on all 10 steps
    copylint             refused=False, clean=1, zero non-zero counts
    campaign_repetition  NONE for em1..em5 and NONE for li1..li5
    opt-out              exactly 1 per email
    signature            exactly 1 per email ("Ivan / Productive")
    verification         verified, sendable, 3 of 2 confirmations

    WRITER/STORED/RENDERED   5 email + 5 LinkedIn
    SEQUENCEPLAN             em1..em5, ps_em1, ps_em3, li1..li5
    BISON projection         5 email steps
    HEYREACH projection      li1..li5, li5 present, li6 ABSENT
    approval hash            7a88ddb693515854

## 3. BLOCKER ONE — AN UNSUPPORTED CUSTOMER OUTCOME THE DETECTOR MISSES

`em4` ships this sentence:

    "Can I share a brief example of how real-time margin insights have
     improved resource decisions for others?"

*"...improved resource decisions **for others**"* is a customer-outcome claim
with no licensed evidence — the exact class TASK-914/915/916/917 exists to
refuse. Measured:

    claims.check(...)              -> []      (no problem reported)
    claims.customer_outcome_claim  -> None    (rule does not fire)

**Why it escapes:** the customer-subject alternation is
`clients|customers|users|teams|companies|firms|agencies|studios`. **"others"
is not in it**, and neither is the bare possessive construction "for others".
The sentence names no customer noun, so no branch fires — and the same hole
covers "for a similar firm", "for someone in your position", "elsewhere".

`em4` carries a second, softer one: *"having margin visibility in real time
often leads to smarter resource choices that directly affect profitability"*.

This is the same defect shape as the original TASK-914 escape, one pronoun
further out. It is a **detector gap, not a copy accident** — regenerating
rolls the dice rather than fixing it, because no gate can refuse it.

## 4. BLOCKER TWO — THE SERVICE-LIST P.S. IS BACK

`em3`'s P.S.:

    "Their services include retail merchandising, product training, and
     display installation."

This is verbatim the defect the 2026-09-29 handoff named in section H.3 —
*"a service list ... weak and not a reason to reply"* — and which the
operator's own instruction lists as unacceptable. It regenerated into the
identical failure because **no gate scores P.S. quality**: `copylint` checks
opt-out, dashes, buzzwords, pack-fact support and case studies, and none of
those refuse a list of the prospect's own services.

`em1`'s P.S. is fine by contrast: *"Since 2022, 2020 Companies has supported
Christ's Haven through donations and volunteerism."*

## 5. A THIRD, NON-BLOCKING FINDING — A PLANNER THAT CANNOT SETTLE

`plan()` permanently reports three ops that no run clears:

    linkedin_note li1 ... (angle_wording_leakage)
    linkedin_note li2 ... (angle_wording_leakage)
    linkedin_note li4 ... (angle_wording_leakage)

`quality.gate` fails those notes for carrying the client's own phrasings
(`"profitability visible on monday not two weeks late"`,
`"utilisation and capacity across live projects"`, `"margin per project"`),
which the LinkedIn rule says to never put in.

**But the storage gate never checks it.** `generate._step_refusals`'s LinkedIn
branch runs `lint` and `claims` only — no quality check — while the planner's
LinkedIn branch runs `_note_quality`, which does. So the planner asks forever
for a regeneration the storage path will accept unchanged, and
`generate._quality_of` reports these same notes **clean**. Two authorities,
one question, opposite answers.

This did not block the artifact, because the notes are stored and pass every
enforcing gate. It means `plan()` can never reach zero ops for this contact.

## 6. WHAT WAS NOT DONE

No sentence was rewritten by hand. No gate was weakened. TASK-917 was not
touched. No Slack post — the artifact is not approval-ready. No other
prospect, no estate sweep, no batching, no canary, no enrolment, no send.

## 7. WHAT WOULD UNBLOCK IT

1. **Widen the customer-subject alternation** to cover the indefinite
   third-party forms — "others", "a similar firm", "someone in your
   position", "elsewhere" — so §3's sentence is refused rather than allowed.
   That is a TASK-917-shaped change to `src/claims.py` and needs the same
   adversarial matrix plus its own negative controls (a bare "others" must
   not become a banned word).
2. **Give the P.S. a gate**, or drop `ps_variant` values that render a list
   of the prospect's own services. Today nothing can refuse one.
3. **Reconcile the two LinkedIn quality authorities** so `plan()` and
   `_step_refusals` answer the same question — either the storage gate
   enforces `angle_wording_leakage` or the planner stops demanding it.

Items 1 and 3 are real defects and should be tasks. Item 2 is a product
decision about P.S. quality.
