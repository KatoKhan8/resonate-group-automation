# Learned from a survey of comparable agents — 2026-09-23

Operator, 2026-09-23: eight items from a GitHub survey of comparable outbound
agents, handed over **as data** and additive to the Slack-agent increments.
This file records them, and — the part that is worth more than the list —
**what this repository actually holds against each one**, measured rather
than assumed.

Every item became a Qwen task: **TASK-266 .. TASK-273**, all in
`docs/qwen-tasks/TODO/`, all sized S or M.

---

## 0. READ THIS FIRST: six of the eight premises were wrong in a way that changes the work

The survey items describe features. Before writing a task for each, the
repository was measured against it. **Six of the eight descriptions did not
match what is here**, and in four cases the mismatch changes what the task
should build. They are recorded per item below and collected here because a
task written from an unchecked premise is a task that builds the wrong thing:

| # | The premise | What is actually true |
|---|---|---|
| 1 | "wire the existing learning doc and the Friday scorecard into this shape" | **Neither exists.** The learning doc is a pending deliverable; `WORKFORCE-SCORECARD.md` is named in a handoff and marked NOT STARTED. There is nothing to wire. |
| 2 | "the 3,668 FLAGGED domains" | **Stale by hours.** The re-judge already ran — `work/stage/s3-icp-amended-PRODUCTIVE-2026-09-07.jsonl`, written today at 17:17, reads **8,370 flagged**, not 3,668. |
| 3 | "the provider-resolved profile" and "test with the 151 enrolled" | **There is no provider-resolved profile.** We supply the URL; HeyReach resolves nothing back. And 151 is three different numbers depending on the witness. |
| 4 | "strip honorifics … test on DE/AT/HR samples" | **HR has no leads at all.** DE 2,006 and AT 270 exist. Croatian in this system is the *sending* estate, not the prospects. |
| 5 | "lead-recovery levers … assign per account" | "Lever" does not exist; **"angle" does**, and `src/revival.py` already answers "which angles has this account been written with". Build on it, not beside it. |
| 8 | "a sequencer adapter is correct iff the suite is green" | There is **no base class, Protocol or registry** the two adapters conform to. What they share is a *transport* contract, not a sequencer interface. |

Items 6 and 7 survived contact with the code: `COMPLIANCE.md` genuinely does
not exist, and the client export genuinely carries no per-domain reason.

---

## 1. Learnings A/B/C — observations, proposed rules, approved rules

**The item.** Learning output splits three ways: **A** observations, **B**
proposed rules, **C** operator-approved rules. The system never writes C. A
rule reaches copy, ICP or routing **only** from C.

**What is here.** The A/C boundary is already the house rule, stated in prose
in every module that could break it and enforced structurally rather than by a
flag:

- `src/learning.py` — cohort performance. `baseline()` :155, `describe()`
  :175, `recommend()` :283. Its own docstring, :21-27: *"**Move the ICP.** …
  there is no code path from here to `qualify`."* `recommend()` returns
  `prioritise` / `examine`, phrased "Consider …".
- `src/gtm.py` — the decision log. `decision()` :113, `record()` :195,
  `supersede()` :212. **Records decisions, enforces nothing** (:17-28).
- `src/clientreview.py:357` `learning_signal()` — "never something that acts".
- `src/variants.py:134-155` — no client answer changes "until somebody
  **promotes a variant on purpose**".

**So A and C exist and B does not.** There is no representation of a
*proposed* rule: today an observation is prose in a `recommend()` row and an
approved rule is a hand-edit to `config/clients/*.yaml`. The step between them
happens in somebody's head and leaves no artifact.

**The finding worth more than the item.** `learning.boost()` (:325) would
nudge priority from measured performance — **it has zero callers.** Grep across
`src/` and `scripts/` returns only its own definition. It is this
repository's named recurring defect, in the one module whose whole subject is
learning: a thing computed correctly that nothing downstream reads. Under an
A/B/C scheme `boost()` is exactly a **B** that was never promoted, and a
scheme that cannot tell "proposed and awaiting approval" from "written and
silently unwired" has not solved the problem it was brought in for.

**And the two artifacts the item says to wire in do not exist.** The learning
doc is pending (`PRODUCTION-HANDOFF-2026-09-22-EVENING.md:147`, repeated
overnight); `WORKFORCE-SCORECARD.md` is NOT STARTED
(`PRODUCTION-HANDOFF-2026-09-23-AFTERNOON.md:275`). The nearest real recurring
artifact is **Monday**, not Friday: `slackagenttools.weekly_report` :987.
TASK-266 therefore builds the A/B/C shape and the promotion record, and treats
"wire the learning doc in" as a follow-on for when a learning doc exists.

→ **TASK-266**, size M.

---

## 2. LLM tiebreaker on FLAGGED only

**The item.** A second-stage judge over the FLAGGED domains, given the
operator's ICP narrative. Verdict, confidence, one-sentence reason per domain.
Cost reported.

**The count moved, and it moved today.** `work/stage/s3-icp.jsonl` holds
24,404 rows — `out 15,642 / in 5,094 / flagged 3,668`, the baseline in
`OPERATOR-AUTHORIZATION-2026-09-22-BOUNCE-DENOMINATOR-AND-HEADCOUNT.md:100`.
But `scripts/stage_s3_rejudge_amended.py` has since run:
`work/stage/s3-icp-amended-PRODUCTIVE-2026-09-07.jsonl`, written **2026-09-23
17:17**, same 24,404 domains — **`in 15,943 / flagged 8,370 / out 91`**.

The flagged reasons split cleanly, and the split decides the design:

    5,851   headcount not judged (2026-09-22 amendment), geo not confirmed
    2,519   provider returned no company for this domain

**2,519 of the 8,370 are unresolvable, and no judge can fix them.** There is
no company behind the domain to reason about. Sending them to a model is
spending money to be told what the journal already says. The tiebreaker's
population is the **5,851**, and TASK-267 says so rather than quoting 8,370
and letting the bill arrive.

**Two qualification engines, and the item means the snapshot one.**
`scripts/stage_s3_icp.py` `judge()` :111 returns `in/out/flagged`;
`src/icp.py` `score()` :208 is the canonical product path with
`STATUSES`/`TIERS`/`CONFIDENCE` (:35-51). They are not the same vocabulary.

**There is no LLM judge for ICP today.** Three LLM surfaces exist —
`src/llm.py` (`NoModel` is the default at :149, "so nothing calls a model by
accident"), `src/providers/xai.py` (`grok-4.6`, :49), `src/providers/glm.py`
(`glm-5.3`, :78) — and none judges a domain.

**The pattern to copy is already in the tree.**
`scripts/stage_s3_rejudge_amended.py` is the proof: read the journal,
re-decide, write a **separate** journal, print a SET diff with a
`LOST (must be zero)` assertion. A second stage should be that shape.

**Cost reporting is real and has three layers**, so "cost reported" is
plumbing rather than invention: `llm.record_usage_since()` :867 and
`token_usage()` :895 (which returns `UNKNOWN` rather than a number when any
call lacks a count), `spendledger.check()` :156 raising `BudgetExceeded`, and
`costs.reconcile()` :234. Note `spendledger` records **expected** cost at call
time and `costs.py` is what closes the loop to observed — a task that reports
only expected cost is reporting an estimate and must say so.

→ **TASK-267**, size M.

---

## 3. Match validation before any LinkedIn enrollment

**The item.** Surname uniqueness + company + location must agree between our
record and the provider-resolved profile; ambiguous matches quarantined, never
sent; test with the 151 enrolled.

**The premise names a step that does not exist.** HeyReach does not resolve a
profile for us. **We supply the `profileUrl`** and it accepts it:
`scripts/batch_linkedin_push.py:113-127` reads `contact["linkedin"]` straight
off the record; `heyreach.add_leads_to_list` sends three proven fields
(`providers/heyreach.py:2461-2464`); `readback_membership` :2560 compares
**URLs only**. `heyreach.lead_profile()` :3044 is the one read that could
resolve a profile and **nothing in `src/` calls it**.

So the task is not "compare our record against the resolved profile". It is
**"fetch a profile to compare against, then compare"** — and that is a
different, larger job, which is why the size is M and why the fetch is the
first acceptance criterion.

**It is a known, written-down gap.** `PRODUCT-GAPS.md:1734-1740`: *"Nothing
cross-checks the slug against the person's name… For an email a wrong address
bounces; a connection request to the wrong profile does not."* The one gate
that sees both URL and name — `collision.check_linkedin_profile()`
(`src/collision.py:1067`, called from `executionguard.py:606`) — uses the name
only as a **search term**; :1109-1117 says so. It answers "are we already
talking to this profile", not "is this profile this person".

**`heyreachfactory` is the worse of the two paths**: :1255-1272 derives
`"first_name"` from `contact_key.split("_")[0]` and sends `"last_name": ""`
and `"title": ""`. There is nothing there to validate *with*.

**"The 151" is three numbers.** Store: exactly 151 contacts in
`work/queue.jsonl` carry `campaign_id_linkedin`. Provider:
`docs/state/PROVIDER-CAMPAIGNS.json` (2026-09-23T10:02:24Z) reads **154**
across 34 IN_PROGRESS campaigns — a +3 drift nothing reconciles. And the
**email** side's "151" was separately re-measured at **393**
(`SLACK-AGENT-HANDOFF-2026-09-22-PM.md:25`). A test that says "the 151" without
naming channel and witness will pin the wrong set.

**There is no quarantine, but there is a hold.** `src/holdreasons.py` —
`set_hold_reason()` :119, five classes, unknown codes default to
`HUMAN_REVIEW`; `store.STATES` includes `held` (:28). The reason-code
namespace is `enrich:* / generation:* / undrop:*` only, so an identity hold
needs a **new code** (`identity:profile_unverified`, `HUMAN_REVIEW`) and a
writer — nothing on the LinkedIn path calls `set_hold_reason` today.

**And LinkedIn pushes are halted anyway.**
`scripts/batch_linkedin_push.py:246` carries a hard `HALT` dated 2026-09-23,
pending a live HeyReach reply-stop. This task lands on top of that halt, which
makes it the right time to build it and the wrong time to claim it is proven
live.

→ **TASK-268**, size M.

---

## 4. Honorifics and name hygiene

**The item.** Strip `Dr.` `Prof.` `Dipl.-Ing.` `Ing.` `Mag.` and similar from
`first_name` at render time; test on DE/AT/HR samples.

**This one is real, and the reason it is real is a lint rule that passes it.**
`src/lint.py:322` `_names_match(greeted, full_name)` splits the full name into
tokens and passes if the greeted word is **any** token. A record named
`"Ing Christoph Lemmer"` greeted `"Ing"` therefore **passes lint today**.
`bisonfactory._refuse_bad_greetings()` :484 catches an empty greeting, a
literal `undefined/null/None`, and planted cohort names — not a title used as
a given name.

**The repro case is already in our own data**, not hypothetical:
`work/Software_Agencies_All_Geo_cleaned - Sheet1.csv`, 51,741 rows, carries
`Country=Germany, First_Name="Ing", Last_Name="Lemmer", Full_Name="Ing
Christoph Lemmer"`. A whole-file scan found three honorific-prefixed rows —
that one, a US `"Dr Khan"`, and an Australian `"DI Chen"`.

**There are two different first-name derivations, which is its own bug.**

    src/cadence.py:582        (contact["name"] or "").split()[0]  -- ignores
                              contact["first_name"] ENTIRELY, for all copy
    src/bisonfactory.py:389   contact["first_name"] else name.split()[0]
    src/heyreachfactory.py:1266   contact_key.split("_")[0]

Of 1,013 contacts in `work/queue.jsonl`, **1,013 carry `name` and only 736
carry `first_name`** — and `cadence.py:582`, which renders every template,
uses the `name` path for all 1,013 regardless. A cleaner attached only to
`first_name` would therefore clean **nothing that ships**. That is the whole
point of the task and it is the first acceptance criterion.

**"HR samples" have no data behind them.** Germany 2,006, Austria 270,
**Croatia 0**. `work/croatian-domains-reply.txt` is our own *sender* estate.
The task tests DE and AT and says plainly that HR is untestable for lack of
leads rather than shipping an empty test that looks like coverage.

**Not yet a live defect.** All 151 LinkedIn-enrolled contacts' derived first
tokens were checked: zero honorifics, zero odd casing. This is prevention
before DE/AT sourcing lands, and the task is written as prevention.

→ **TASK-269**, size S.

---

## 5. Lead-recovery levers for the re-engagement lane

**The item.** Levers `fresh_face`, `value_first`, `trigger`, `close`; assigned
per account from history and signals; report the split.

**"Lever" does not exist. "Angle" does, and so does most of this task.**
`src/revival.py` already holds the thing the item is describing:

    angles_used(rec)            :146   every angle this account has actually
                                       been written with, from CONFIRMED touches
    angles_available(config)    :161   the client's angle vocabulary
    assess(rec, ...)            :255   NEVER / NOT_YET / NOTHING_NEW / READY
    last_touch(rec)             :135

Its docstring already states the rule the item implies: *"Reviving with the
angle that already failed is a repeat."* A lever assigned without reading
`angles_used` would do exactly that.

`src/playbooks.py` is the account-level "play" library — `LIBRARY` :104-197,
`recommend()` :302 — and its docstring is explicit: *"It recommends; it does
not assign."* Its only consumers are read-only web surfaces. That is the A/B
boundary of item 1 showing up again, which is why TASK-270 makes the lever a
**recommendation with a recorded reason**, not an assignment.

**The trap to avoid is written down and was measured.** `store.LANES` is
`("revive", "cold", "domains")` (:28) and **all 1,542 records are
`domains`** — declared, validated, filterable, unused. Separately,
`tests/test_a_reengagement_lane_is_not_a_stored_value.py` records that on
2026-09-22 the **stored** lane read `REENGAGE 0 / NEVER 1360` while the live
computation read `REENGAGE 985 / NEVER 89`. **The lane is a function of live
provider status and must never be persisted.** The only working classifier is
`scripts/reengagement_inventory.py` `lane_for()` :177 — in a script, not in
`src/`, and TASK-247 (its `src/` home) is still TODO.

So TASK-270 is sequenced **after** TASK-247 and computes the lever the same
way: live, from history, never stored.

→ **TASK-270**, size M.

---

## 6. COMPLIANCE.md and a List-Unsubscribe gate

**The item.** A document saying what the system enforces and what the operator
must do, plus a fail-loud gate for `List-Unsubscribe` presence on every
cadence.

**`COMPLIANCE.md` does not exist.** Confirmed by search. The adjacent
documents are `ENGAGEMENT-HYGIENE.md`, `GO-LIVE-CHECKLIST.md` and
`PROVIDER-ROUTING-POLICY.md`, all at repo root.

**What the system genuinely enforces, so the document can be true:**

- **Suppression at send time — yes, and properly.** `eligibility._suppressed()`
  :276 (client list via `ingest.load_suppress()` :109, `drop_reason` prefix,
  `agencydnc.lookup`), `must_not_contact()` :329, enforced at
  `executionguard.py:563-582` by a **set intersection** against
  `SUPPRESSION_REASONS` (:115-123). The comment at :608-615 records that this
  used to be a substring check on serialised JSON and why that was wrong.
- **Agency-wide DNC** — `src/agencydnc.py`, sha256 fingerprints, closed reason
  vocabulary `REQUESTED/LEGAL/COMPLAINT/INTERNAL` (:56-60).
- **Provider-side stop sweep** — `src/leadstop.py` `sweep()` :192.

**What it does not enforce, and each is a sentence the document must carry:**

- **There is no unsubscribe mechanism.** `src/replies.py:161-163`, load-bearing:
  *"the estate has no unsubscribe link so opt-out arrives only as a reply
  somebody has to classify."* Opt-out is `UNSUBSCRIBE_PATTERNS` :157 plus
  `accountpolicy.apply_reply()` :604 — a **classifier**, not a header.
- **`List-Unsubscribe` appears nowhere in the repository.** Zero hits across
  `*.py`, `*.md`, `*.json`, `*.yaml`. And — the part that decides the task's
  shape — **there is no provider field through which to set it.** The
  EmailBison sequence-step payload is
  `{order, email_subject, email_body, wait_in_days, active, variant,
  variant_from_step, thread_reply}` (`providers/bison.py:1467-1513`);
  `bison.headers()` :34 is the API's HTTP auth header, not a mail header. So
  the gate can assert a **link in `email_body`** or a provider-level setting
  outside this module, and TASK-271 requires the honest one: refuse the
  cadence, and say which of the two the estate is relying on.
- **The 180-day silence is declared and dead.** `src/replyengine.py:138-139`
  `POST_DECLINE_QUESTIONS = 1`, `DECLINE_QUIET_DAYS = 180`, quoting the
  operator. **Neither constant is referenced anywhere else** — not `src/`, not
  `tests/`, not `docs/`. There is no `last_touched`, `dormant` or `quiet_until`
  field. `src/fatigue.py` is a per-week touch cap, a different rule.
- **GDPR / legitimate interest / DPA are absent.** The only hits are
  incidental: `evidence.py:197-230` uses "gdpr"/"consent" as vocabulary to
  detect that a scraped page is a cookie notice; `replyengine.py:149` has
  `dpa` as a topic the reply engine **refuses** to discuss. No lawful-basis
  field, no DPA record, no consent store.

**The gate pattern to imitate** is `src/executionguard.py`:
`NotAuthorized(gate, why, passed=())` :126 — it carries which gate fired and
the trace of gates already passed, *"so a test can assert that the intended
gate fired rather than merely that something did"*. A new compliance gate
belongs in gate 4 (:563-600). Note `killswitch.py:277-293` explicitly warns
that wiring a gate into `eligibility.decide` instead is a dead end, because
dry previews would then refuse everything.

→ **TASK-271**, size M. The document is the deliverable; the gate is the half
that makes it true.

---

## 7. Explainable verdicts in the client export

**The item.** One plain-language reason per domain beside the QUALIFIED flag.

**There are three exports and the premise fits none of them exactly.**

- `src/clientexport.py` — the client-approval CSV. `EXPORT_COLUMNS` :37 is
  `domain, company, headcount, industry, country, website`. **Six columns, no
  reason field.** The QUALIFIED gate is `_icp_qualified()` :51.
- `src/candidateexport.py` — the weekly Monday 07:00 Zagreb export. **Already
  has it**: `EXPORT_COLUMNS` :28 carries `"why it matched"`, fed from
  `company["_icp_why"]` via `nightlysourcing._to_candidate()` :494-514, which
  comes from `icp._structural_verdict()` :859-905.
- `scripts/qualify_sourced_supply.py` — the one that produced the live
  figures. Writes **JSONL, not CSV**, and **there is no QUALIFIED column**:
  qualification is expressed as *file membership* — `qualified-supply.jsonl`
  (**32,951** rows) versus `review-to-enrichment.jsonl` (**4,083** rows), both
  counted directly. Rows carry `_icp_score` and `_icp_status` but no prose.

**So the work is to carry `candidateexport`'s column into the other two**,
which is smaller than it sounds and is why this is an S.

**The warning that must travel with it.** `icp.py:864-872` and
`nightlysourcing.py:313-334` both record that this column once read
`"scored above threshold"` on rows that scored **0.0** — a 121,205-employee
telecom and a 130,377-employee bank reached a client selling to 20+ person
agencies. That is ISSUE-019 / ISSUE-023, with tests
(`test_a_telecom_is_not_an_agency.py`, `test_review_is_not_qualified.py`). **A
reason string that is generated from the verdict rather than from the evidence
is how that happened**, and TASK-272's acceptance test is exactly that case: a
row that scores 0.0 must not be able to produce a reason that reads like a
pass.

→ **TASK-272**, size S.

---

## 8. Adapter conformance suite

**The item.** A sequencer adapter is correct iff the suite is green.
EmailBison and HeyReach first, so a third sequencer for the next client is a
generated adapter plus a green suite.

**There is no interface to conform to.** No base class, no ABC, no Protocol,
no registry. `src/providers/bison.py` (104 KB) and
`src/providers/heyreach.py` (152 KB) are independent modules. What they
genuinely share is enforced from `src/providers/__init__.py` and is a
**transport and safety** contract, not a sequencer one:

    ProviderError :48 · request() :763 · ok()/mapping()/first() :777,798,820
    guard_prospect_facing() :419 -- called at IMPORT
    refuse_unauthorized_write() :672 · ProviderWriteRefused :535
    module-level WRITE_ROUTES + a private allowlist door

Where the sequencer verbs overlap by name, **the signatures differ**:
`set_sequence(campaign_id, title, steps)` on Bison :1514 versus
`set_sequence(campaign_id, sequence)` on HeyReach :2061;
`resume_campaign` takes `expect_leads` on one side only. The convergence is
coincidental, not contractual.

**The asymmetries are the most valuable thing a conformance suite would
pin**, and they are already documented in the source:

- `bison.py:478-490` says its `WRITE_ROUTES` tuple **was only a comment until
  2026-09-14** and that HeyReach *"earns that claim with a chokepoint"* —
  HeyReach's write door came first and Bison's was retrofitted.
- HeyReach has a large sequence-validation surface — `validate_sequence_for_write`
  :938, `sequence_hazards` :393, `refuse_unsupported_sequence` :1322,
  `SequenceInvalid` :765 — and Bison has **none in the adapter**; its
  validation lives in `bisonfactory._refuse_unsupported()` :452, a layer up.
- There is a `tests/fakebison.py` and **no `fakeheyreach`**.

**Two existing things a suite must not break.**
`tests/test_nothing_writes_to_a_provider.py` is a table-driven **source**
audit (:68-119) that reads the HTTP verb as a **string literal** inside each
write function — `bison.py:491-500` says so explicitly. A conformance suite
that refactors those into one `_write(method, ...)` blinds that audit. And
`providerwrites.SUPPORTED` (:476) is a closed list of ten operations;
everything else raises `WriteUnsupported` **by design**, so asserting *that*
is itself a conformance check. Prospect-facing operations additionally need a
real `executionguard.Authorization` plus an open `actionledger` reservation —
`perform()` :1824 refuses hand-built tokens — so a suite must mint through
`executionguard.authorize()`.

TASK-273 therefore writes the suite **against the shared surface that exists**
and makes each asymmetry an explicit, named, expected-difference row rather
than a failure — because a suite that goes red on eleven known differences on
day one is a suite nobody runs.

→ **TASK-273**, size M.

---

## The thing this survey was actually worth

Not the eight features. **Six of eight premises did not survive being checked
against the code, and two of the six were wrong in the direction that costs
money** — item 2's population is 5,851 and not 3,668 or 8,370, and item 3's
"provider-resolved profile" is a step that would have to be built before the
comparison it describes is even possible.

The survey's real contribution is item 1, and not as a feature. **A/B/C is a
name for a gap this repository already has and could not previously point
at**: `learning.boost()` is a rule that was written, is correct, and is
wired to nothing — and until there is a word for "proposed but not approved",
that is indistinguishable from a bug. It is the same shape as the five
report sections that were rendered and never assembled, and as
`slackfollowup.due()` being read by nothing. **Three instances now.** The
value of B is that it makes the difference between *awaiting a decision* and
*silently unwired* a thing the system can state rather than a thing somebody
has to notice.
