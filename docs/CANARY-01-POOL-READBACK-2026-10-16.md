# CANARY-01 CRITERION 7 — THE PER-CAMPAIGN READ-BACK, AND THE FENCE THAT ADMITTED A SECOND ENDPOINT

TASK 0200 (pilotcaps), 2026-10-16.

    measured tree   wt-pilotcaps-2026-10-14   (CRLF, CR=15 in requirements.txt)
    measured SHA    adf7b650a324876056e4fd5c61fd6cd77698e98f
    branch          task-pilotcaps-pool-readback-2026-10-16
                    = f06d764ab (0190) merged with 919ccc01e (0180), so one
                      tree holds the repaired instrument AND the read record
    origin/master   b1f290c84   unchanged

**Nothing was attached. No provider was dialled. No campaign exists.** Every
route in this document was taken at the transport seam with a raising
transport installed first; no credential was read from disk, printed or
logged. The 2026-09-26 production freeze stands and provider writes from this
system remain 0.

---

## 0. THE SHORT VERSION

**Criterion 7 is still NOT MET, and it is now NOT MET for exactly one reason
instead of three.** The per-campaign check exists, is fail-closed, and is
mutation-proven — 20 mutations, every one killed by a named test. What it has
no input for is the membership: nothing is attached, so there is nothing to
read back. `verdict_over_campaigns({}, …)` returns **UNKNOWN**, which is the
honest verdict and not a placeholder.

**Two things were settled that were open at the end of 0190.**

1. **Which call resolves an id to an address: none.** There is no per-id
   endpoint. The resolution is a join onto the estate walk 0180 already made,
   and it is **entirely offline**. Measured below.
2. **One finding that outranks the read-back.** 0180's fence enforced its
   one-endpoint authorisation by comparing the path's **last segment**, and
   the per-campaign sender route **shares that segment**. So 0180's fence
   returns ALLOWED for a second endpoint the authorisation did not cover. It
   was not breached in fact. The *proof* of narrowness was a straw.

---

## 1. THE RESOLUTION STEP — AND IT IS OFFLINE

The brief asks which call turns a sender id into an address, and whether it
exists on the provider or has to be composed from 0180's recorded rows.

**Measured at the transport seam.** A raising transport was installed before
the first call, `urllib.request.urlopen` was replaced by a tripwire, and the
key was a placeholder (`test-key-not-real`) so URL construction could finish.
Nothing was sent; the raiser is what guarantees that.

    bison.sender_emails()        ->  GET /api/sender-emails?page=1        (13 pages)
    bison.campaign_senders(499)  ->  GET /api/campaigns/499/sender-emails?page=1
    bison.campaign(499)          ->  GET /api/campaigns/499
    bison.list_all_campaigns()   ->  GET /api/campaigns

`bison` exposes **62 public callables**; the only two sender reads are the
first two, and `sender_emails` takes no id (`per_page=None,
expect_workspace=None`). **There is no per-id sender endpoint in the adapter.**

So the resolution is: membership ids → left-join onto the estate walk → row
carrying `email`, `name` and `email_signature`. And the estate walk already
exists — the one authorised read, 181 rows, `meta.total` 181, digest
`2c928a2652fd2c414976f83dfb8bddd5701e4dbdbfbb20b1512c8470a9107439`.

**All ten approved pool ids are in those 181 rows**, verified by id:

    2763 2760 2751 2750 2778 2772 2748 2745 2741 2775     all present
    2757 2766   reserves, approved but NOT in the pool    both present
    2738        carried the pool's old attestation        ABSENT

**Therefore the resolution step costs no provider call at all**, and
`scripts/canary_pool_readback.py` takes `estate_rows` as an argument and never
fetches them. A function that *could* silently dial is a function that will.

### The owner histogram reproduces, through different code

Independently recomputed from the recorded rows through the *repaired* 0190
ladder (`estate_row_from_provider` → `owner_of_signature`), rather than
through 0180's reader:

    px-387dd1f77205   61        px-894888e9f1c3    6
    px-19834114d0e7   41        px-2f1dd920a186    5
    px-494dc227d91e   17        px-d065203e066c    3
    px-c82dcaabaec1   17        px-40bfd9825a08    1
    px-7513d195dfb1   17        px-e7b9ecb0a51e    1
    px-fc7d1255b8a3   12   <-- the pool's owner

Byte-identical to 0180's histogram, with **zero unreadable and zero
ownerless rows**. Two readers, two code paths, one answer.

### What is NOT offline, and it is the whole remaining blocker

The **membership**. There is no canary campaign — not at the provider, not in
`work/campaigns.jsonl` — so there is no membership to read back and no
recorded read-back file. `GET /api/campaigns/{id}/sender-emails` is a second
endpoint outside the spent authorisation.

`verdict_for_campaign` therefore distinguishes three states that a lesser
instrument would collapse:

    membership is None    UNKNOWN   no read-back was made
    membership is []      UNKNOWN   read back, and nothing is attached
    membership is [...]   judged

**An unread pool is not an empty one, and an empty pool is not one owner.**

---

## 2. THE FINDING: 0180's FENCE MATCHED THE LEAF

0180's fence, verbatim from `resonate-ops/pilotcaps-0180-one-authorised-read.py:78-94`:

    leaf = parts.path.rstrip("/").rsplit("/", 1)[-1]
    if (method != "GET" or leaf != "sender-emails" or bool(body)):
        REFUSE

Evaluated against the routes the adapter actually generates:

    GET  /api/sender-emails                    leaf sender-emails   ALLOWED
    GET  /api/campaigns/499/sender-emails      leaf sender-emails   ALLOWED  <-- !!
    GET  /api/campaigns/499                    leaf 499             REFUSED
    GET  /api/campaigns                        leaf campaigns       REFUSED

And the three negative controls 0180 ran, re-evaluated:

    POST /api/sender-emails                    leaf sender-emails   REFUSED  (method)
    GET  /api/campaigns                        leaf campaigns       REFUSED  (leaf)
    GET  /api/campaigns/499/senders            leaf senders         REFUSED  (leaf)

**The third control is a straw path.** `/campaigns/{id}/senders` is generated
by nothing in this repository — measured against both sender reads, not argued
from the name. `CANARY-01-ATTACH-PAYLOAD-2026-10-15.md` §4A names that path
too, and it is also wrong there. So the one control meant to prove the fence
could not reach the campaign endpoints refused on a leaf that could never have
arrived, and said nothing about the one neighbouring route that exists.

**Was the authorisation breached? No.** 0180's own self-check records 13
requests, `distinct_paths == ["/api/sender-emails"]`, `refused_during_read ==
[]`, `fence_observed_the_transport == true`. One path, one method, 13 pages.
The read was narrow. **The enforcement was not, and the control that was
supposed to prove it was not capable of failing.**

A guard that cannot fire, reported as a guard that held, is this project's
signature defect. It has now appeared inside the instrument built to make a
once-authorised read safe.

### The repair

`path_exact_fence(allowed_paths, allowed_method="GET")` compares the **whole
path** against a set, refuses any body and any other method, and **drops
`headers`** — never recorded, never printed, never returned. It wraps no inner
transport, so an allowed path still sends nothing: this module has no live
mode.

0180's leaf predicate is **kept** in the module as
`fence_0180_leaf_verdict`, because the repair is only provably a repair if the
thing it repairs can still be run. Two tests hold that pairing: the leaf
predicate must still say ALLOWED for the per-campaign route, and the
path-exact fence must refuse the same request.

### The corrected negative-control set

Five, and the third is the route that exists:

    POST /api/sender-emails
    GET  /api/campaigns
    GET  /api/campaigns/499/sender-emails     <-- the correction
    GET  /api/campaigns/499
    POST /api/campaigns/499/sender-emails

All five refuse under the path-exact fence, asserted as a set, with the count
checked so a silently shortened list cannot pass.

---

## 3. THE CHECK, IN ITS PER-CAMPAIGN FORM

`scripts/canary_pool_readback.py`. Per campaign: the senders actually
attached → resolved to rows → one owner → compared against the approved pool.

**Eight ordered rungs. Every finding is reported, not only the first**, so a
human reads the whole state of the campaign.

    0  estate walk partial (len(rows) != meta.total)        UNKNOWN
    1  membership not read                                  UNKNOWN
    2  membership empty                                     UNKNOWN
    3  an attached id resolves to no row                    UNKNOWN
    3b an id appears twice in the read-back                 UNKNOWN
    4  a row carries no `email_signature`                   UNKNOWN
    5  a signature this code cannot read                    UNKNOWN
    5b a mailbox attests NO owner (empty block)             NOT MET
    5c the pool attests more than one owner                 NOT MET
    6  one owner, but not the bodies' signer                NOT MET
    7  an unapproved id attached / an approved id absent    NOT MET

**UNKNOWN dominates NOT MET.** `_PRECEDENCE = {UNKNOWN: 2, NOT_MET: 1,
MET: 0}`, and MET requires every rung evaluated and clean. A verdict built on
a partial reading is not a verdict, even a negative one.

**5b against 5 is deliberate and it is 0190's distinction, preserved.** A
signature block with no text at all attests no owner — a *measured fact* about
the mailbox, so NOT MET. A block with text this code cannot read is an
*unreadable authority*, so UNKNOWN. Collapsing those two is what made 181
blind rows look like a clean estate.

**An empty scope is UNKNOWN, never MET.** "No campaign failed" is a statement
about the scope and not about the estate. This is 0190's defect one level up,
and it is the live case today.

### Run against the real recorded walk

    py -3 -B scripts/canary_pool_readback.py \
        --estate resonate-ops/canary/sender-emails-live-2026-10-15.json

    estate walk     181 rows, meta.total 181
    approved pool   [2741, 2745, 2748, 2750, 2751, 2760, 2763, 2772, 2775, 2778]
    approved owner  px-fc7d1255b8a3
    campaigns       NONE IN SCOPE

    OVERALL  UNKNOWN - the scope holds no campaign, so nothing was examined;
             an empty scope proves nothing and is never MET          exit 1

### And what it WOULD say, on the real bytes, if the ten were attached

Membership supplied by hand. **This is a conditional, not a read-back**, and
it does not move criterion 7:

    --campaign 499:2763,2760,2751,2750,2778,2772,2748,2745,2741,2775

    campaign 499: MET      owner px-fc7d1255b8a3      exit 0

0190 predicted this ("which the pool numbers above say it will"). It is now
measured against the provider's own captured bytes. **The string comparison
was already settled; what this adds is that the per-campaign instrument agrees
on the real rows and is not merely green on fixtures.**

### The same instrument, red on the real bytes

An eleventh **real** mailbox from the estate, `2739`, owned by
`px-387dd1f77205`:

    campaign 499: NOT MET
      [NOT MET] the pool has 2 distinct owners:
                px-387dd1f77205 x1 (2739);
                px-fc7d1255b8a3 x10 (2763 2760 2751 2750 2778 2772 2748 2745 2741 2775)
      [NOT MET] sender id(s) [2739] are attached and were not approved

Both rungs fire, both name the offending id, and the ten correct mailboxes are
not accused.

---

## 4. THE MUTATION PROOF

`resonate-ops/pilotcaps-0200/mutate_0200.py`. Twenty mutations, each removing
or weakening exactly one guard, run against both modules (83 tests). Source
restored byte-identically after every one, verified by sha256
`ce5ce3c81f16a73453823fcd04d9b2f694a5b0b81381737541da63f0b7b0bb4b`, with
`PYTHONDONTWRITEBYTECODE=1` — because a harness that lets the interpreter
cache is measuring the previous mutation (0190's own finding).

    BASELINE  Ran 83 - OK (skipped=1, expected failures=4)   failing names: none

    M1   worst(nothing) is MET                    KILLED  test_worst_of_nothing_is_UNKNOWN
    M2   unread membership read as empty          KILLED  4 names
    M3   empty attach not refused                 KILLED  test_an_empty_membership_is_UNKNOWN_not_MET
    M4   unresolvable id dropped                  KILLED  2 names
    M5   partial estate walk accepted             KILLED  test_a_partial_estate_walk_is_UNKNOWN...
    M6   NOT MET dominates UNKNOWN                KILLED  6 names
    M7   eleventh unapproved sender passes        KILLED  test_an_eleventh_unapproved_sender_is_NOT_MET
    M8   short attach passes                      KILLED  test_a_short_attach_is_NOT_MET
    M9   owner not compared to the signer         KILLED  test_one_owner_who_is_the_wrong_owner_is_NOT_MET
    M10  unreadable signature not refused         KILLED  test_an_unreadable_signature_is_UNKNOWN
    M11  missing signature field swallowed        KILLED  test_a_row_without_the_signature_field_is_UNKNOWN
    M12  duplicated id accepted                   KILLED  test_a_duplicated_id_is_UNKNOWN
    M13  empty scope reports MET                  KILLED  test_an_empty_scope_is_UNKNOWN
    M14  fence compares the LEAF again            KILLED  2 names  <-- the 0180 defect
    M15  fence stops refusing a body              KILLED  test_the_fence_refuses_a_body_and_a_wrong_method
    M16  fence records its headers                KILLED  test_the_fence_never_records_a_header
    M17  resolve() returns no unresolved ids      KILLED  3 names
    M18  corrected control dropped from the set   KILLED  test_the_corrected_controls_include_the_route_that_exists
    M19  the kept 0180 predicate is "fixed"       KILLED  test_the_leaf_fence_allows_the_per_campaign_route
    M20  ownerless mailbox no longer refuses      KILLED  test_an_ownerless_mailbox_is_NOT_MET_and_not_UNKNOWN

    unkilled: none      restored sha256 IDENTICAL

**M19 is the control for the control.** "Fixing" the kept leaf predicate so it
compares whole paths turns the finding in §2 unfalsifiable — and it goes red,
so the finding cannot quietly become an assertion.

### M14's first pass found nothing, and that is recorded

M14's search pattern was written with single quotes against a source line
using double quotes. The harness reported `!! PATTERN NOT FOUND` and counted
it unkilled rather than silently skipping it. A mutation whose pattern misses
is indistinguishable from a guard nothing proves unless the harness says which
happened.

---

## 5. TWO DEFECTS FOUND IN THIS TASK'S OWN TESTS, BOTH BY THEIR OWN ASSERTIONS

**One. The route tests first measured nothing.** `tests/__init__`'s credential
firewall pops every key and points `providers.ENV_FILE` at a path that cannot
exist, so `campaign_senders` raises `MissingKey` **before building a URL**. The
first version of the class caught `Exception` broadly and then asserted on an
empty record — and all three tests failed on their own
`assertTrue(self.seen)` rather than passing while seeing nothing. The fix is
a placeholder key plus a narrow `Sealed` exception, so a `MissingKey` can
never again be swallowed into an empty measurement. **This is 0190's lesson
arriving by a different door: the firewall buys one step of warning.**

**Two. Importing a `TestCase` runs it twice.** `from
tests.test_every_body_is_signed_by_the_pools_owner import TheLiveRead` made
the loader discover `TheLiveRead` **from this module too**, minting a
duplicate test name and a second skip in this module's tally — a name the
merge gate would have seen appear out of nowhere. Measured: `Ran 45 …
skipped=1` before, `Ran 44 … OK` after reaching the class through the module
object instead.

### The reachability pin, carried forward

`TheGatedLegStaysReachable` pins both halves of 0190's arrangement: the
`/sender-emails` leg stays gated behind `B7_LIVE_ESTATE`, **and** its body is
still reachable through `inspect.unwrap`. A third test demonstrates the trap
itself — calling the gated method directly raises `SkipTest` — so nobody has
to take the docstring's word for it. If either half changes, this module fails
loudly instead of the driven controls going quiet.

---

## 6. THE OPERATOR'S ONE COMMAND

**DO NOT RUN THIS. It is a provider write and it needs the operator's explicit
`APPROVED`.**

    py -3 -m src.bisonfactory <canonical-campaign-id>          # DRY first
    py -3 -m src.bisonfactory <canonical-campaign-id> --live   # the attach

### What it writes, to which campaign, with which senders

**It is not a sender-only command, and there is no sender-only command.**
`bison.attach_senders(campaign_id, sender_email_ids)` needs a campaign that
exists at the provider, and none does. So the one entry point performs the
whole stage, in this order (`src/bisonfactory.stage`):

    1  bison.create_campaign      POST  /api/campaigns              through the door
    2  (local scope bind)
    3  bison.set_limits           PATCH /api/campaigns/{id}/update   BYPASS
    4  bison.set_schedule         POST  /api/campaigns/{id}/schedule BYPASS
    5  bison.attach_senders       POST  /api/campaigns/{id}/attach-sender-emails
                                  body `sender_email_ids`            BYPASS
    6  bison.set_sequence         POST  /api/campaigns/{id}/sequence-steps
    7  bison.pause_campaign       PATCH /api/campaigns/{id}/pause    BYPASS
    8  lead writes                POST  /api/leads, attach-leads     BYPASS
    9  readback                   GET   /api/campaigns/{id}

    campaign id        assigned by EmailBison on create; UNKNOWN until then
    sender ids         2763 2760 2751 2750 2778 2772 2748 2745 2741 2775
                       drawn from the canonical campaign row's
                       senders.email[].provider_account_id, NOT from a flag
    daily capacity     10 x 15, contended: the estate averages 6.3 campaigns
                       per mailbox and EmailBison does not divide volume
                       between them

**I did not run the dry command.** A dry run calls `bison.bound_workspace()`,
which is a provider read, and this brief authorises no provider call.

### What it does if run twice

**The sender step is idempotent and that is measured in code, not assumed.**
`_ensure_senders` calls `bison.campaign_senders(provider_id)` first and
returns `"N sender(s) already bound"` when `set(wanted) <= set(bound)` — no
second write. And `bison.attach_senders` reads the membership back itself: the
provider answers `200` with `success: false` when it attaches nothing, so the
function raises unless every sender asked for is actually bound.

Two steps are **not** safe twice, and they are not the senders:

- **`bison.set_sequence` APPENDS.** A second run duplicates the copy. This is
  recorded in `bisonfactory`'s own comment from the 484 incident.
- **The lead writes.** Step 7 pauses before step 8 deliberately: a lead
  attached to an unpaused campaign reads `in_sequence` at once, and a lead
  that is `in_sequence` anywhere cannot be attached to any other campaign —
  the provider refuses the whole batch with one unattributed 422.

So: running it twice is safe for the **pool**, and is not safe for the
**campaign**.

### What refuses it today — and the door is NOT what stops the attach

Measured on `adf7b650a`:

    RESONATE_PROVIDER_WRITES set in this environment       NO
    bison.assign_sender in providerwrites.SUPPORTED        YES (CONDITIONAL)
    _ensure_senders routes through providerwrites.perform  NO - it calls
                                                           bison.attach_senders
                                                           DIRECTLY
    scripts/known_write_bypasses.json names attach_senders YES

**So the door does not refuse the pool attach.** What it refuses is **step 1**:
`_find_or_create` *does* route `bison.create_campaign` through
`providerwrites.perform`, so with no `RESONATE_PROVIDER_WRITES` and no
`allow_writes()` scope the campaign is never created and step 5 is never
reached. **The attach is stopped by the create, not by a gate on itself.** If a
campaign already existed, the sender attach would go through ungated.

**The workspace killswitch does not gate the attach either.** It is consulted
in `_ensure_leads` — step 8, *after* the senders — and `bisonfactory`'s own
comment says why: the global layer refuses sending, which staging is not.

The three things that actually stand in front of this command today:

    1  campaigns.require(<id>) - `stage` refuses a campaign that is not in
       work/campaigns.jsonl naming a client. No canonical row exists.
    2  providerwrites.perform on bison.create_campaign - no env flag, no
       allow_writes() scope.
    3  The operator's explicit APPROVED, absent. The 2026-09-26 production
       freeze covers launches, activations, enrolments and attachments.

For it to go through, all three must change, and the first two are
consequences of the third.

### How to undo it

**The pool attach itself:** `bison.detach_senders(campaign_id,
sender_email_ids)` exists in the adapter — signature measured, not inferred.

    py -3 -c "from src.providers import bison; \
              print(bison.detach_senders(<provider_id>, \
                    [2763,2760,2751,2750,2778,2772,2748,2745,2741,2775])); \
              print(bison.campaign_senders(<provider_id>))"

**Three honest caveats on that undo:**

- `detach_senders` has **no CLI and does not go through the door**. The undo
  is itself an ungated provider write typed at a prompt, which is worse
  ergonomics than the thing it undoes.
- It does not undo steps 1, 3, 4, 6 or 8. A campaign, a schedule, a sequence
  and ten leads would remain. The campaign is left **paused** by step 7, which
  is the state that matters for safety, and un-creating a campaign is not in
  the adapter at all.
- A detach does not un-contend the capacity another campaign may already have
  taken for that day.

**Recommendation, the operator's to take:** before any approval, route
`bison.attach_senders` through `providerwrites.perform` under the
`bison.assign_sender` verb that is already in `SUPPORTED`. It costs a change
under `src/` and therefore a fresh suite reference, and it closes the gap
where the only thing stopping a pool attach is that the campaign does not
exist yet. Filed, not done: this task writes no production code.

---

## 7. THE NINE, RE-STATED — measured on `adf7b650a`, this tree

Verdicts are re-measured here, not carried. Where the instrument was run, the
command is named; where the authority is outside git, it is named as such.

| # | criterion | verdict HERE | sourced by |
|---|---|---|---|
| 1 | a suppressed address cannot reach the transport by any path | **MET-WITH-CAVEAT** | `test_a_suppressed_address_cannot_reach_a_provider` OK |
| 2 | a removal request writes a suppression row | **MET** | same module; 0170's verdict reproduces |
| 3 | li1 renders a real connection note, RED on empty | **NOT MET** | `test_the_empty_connection_note_is_an_operator_decision` OK — it PINS the gap as a decision |
| 4 | every template passes the ceiling and the floor | **MET** | `test_every_template_is_inside_the_word_contract` OK, `test_no_template_escapes_the_word_contract` OK |
| 5 | zero write paths bypass the gate | **NOT MET** | `test_no_new_write_bypasses_the_door` FAILED (2 names) |
| 6 | mailbox health, from the estate export | **UNKNOWN on this tree** | the authority is `resonate-ops/canary/sender-estate-export-2026-10-15b.csv`, outside git; not re-measured here |
| 7 | one owner across the **attached** pool | **NOT MET** | this task |
| 8 | the review file is approved by the owner | **UNKNOWN on this tree** | the authority is `resonate-ops/canary/APPROVAL-SHEET-2026-10-15.md`, outside git; not re-measured here |
| 9 | a kill switch the owner can operate alone | **NOT MET here** | measured: `src/killswitch` exposes no setter-shaped callable; `OFF` is a constant |

### Each NOT MET, in one line: what is missing, and what kind of thing it needs

**3 — NOT MET. Needs a DECISION, not construction.** The criterion as written
contradicts a standing operator decision that an empty connection note is
acceptable. The test on this tree pins that contradiction rather than
resolving it. Nobody can code past it.

**5 — NOT MET. Needs CONSTRUCTION, and the fixes already exist unapplied.**
25–26 of 58 write paths do not pass the door. On this tree the pin is red in
both directions over one call site that is not in the baseline —
`scripts/batch_linkedin_push.py::stage_rows_to_list::heyreach.add_leads_to_list`
— which reproduces the "2 new failing names" 0170 recorded for the integration
tree. **Not mine:** this task touched neither file. The baseline must not be
regenerated to make it green.

**7 — NOT MET. Needs CONSTRUCTION, and the construction is now one
operator-gated write.** The instrument exists, is per-campaign, is fail-closed
and is mutation-proven; the resolution step is offline; the verdict on the real
recorded rows would be MET for exactly the ten. What is missing is the
**membership**, which requires a campaign to exist with the ten attached — a
provider write under §6. After the attach, the read-back needs
`GET /api/campaigns/{id}/sender-emails`, which is a **second endpoint** and
needs its own authorisation. The spent 2026-10-15 23:00 grant does not cover
it, and §2 is why that matters: a leaf-matching fence would have let it
through without anyone noticing.

**9 — NOT MET on this tree. CONSTRUCTED ELSEWHERE, not certified by me.**
`src/killswitch` is a reader: of its public surface nothing is setter-shaped.
A candidate proof exists on `task-glm-c-2026-10-14` at `e84108f5d` ("TASK 0210
(GLM-C): STOP-SENDING — the brake the operator can pull alone"), which adds
`src/haltfile.py` and two tests. **This tree does not contain it and I did not
re-measure its gate**, so for this tree the verdict is NOT MET and the global
verdict is UNKNOWN until someone certifies that branch at the moment they look.

### And the finding that still outranks the nine

0160 recorded that no tree held more than one proof. **That is better and still
true.** This tree holds criteria 1, 2, 4 and the whole of 7's mechanism
together — but criterion 9's candidate proof is on a branch this tree does not
contain, so "all nine true at once" has still never been measured anywhere.

---

## 8. PROHIBITIONS, EACH CHECKED

    provider call of any kind     NONE. Every route was taken at the transport
                                  seam with a raising transport installed
                                  first; urllib.request.urlopen was replaced
                                  by a tripwire; the key was the placeholder
                                  `test-key-not-real`. The one estate read is
                                  0180's recorded capture, read from disk.
    anything attached             NONE. No campaign exists.
    a provider write              NONE. The §6 command was NOT run, in either
                                  mode - a dry run reads `bound_workspace`.
    activation / --live           NONE.
    a cap or gate change          NONE. The door, the killswitch, SUPPORTED
                                  and known_write_bypasses.json are unchanged.
    STOP-SENDING created          NO. It does not exist on this tree at all.
    push or merge to master       NONE. origin/master b1f290c84, verified.
    config/.env                   NEVER OPENED. providers.ENV_FILE points at
                                  a path verified non-existent at runtime.
    src/providers/*               NOT MODIFIED and NOT READ. Routes and
                                  signatures were measured through
                                  inspect.signature, dir() and the transport
                                  seam, never off the source.
    another lane's worktree       NOT ENTERED. task-pilotcaps-b7-control and
                                  task-glm-c were read through `git show` and
                                  `git grep` only.
    a name in clear               NONE. Sender mailboxes are provider ids,
                                  owners are px values, the synthetic owners
                                  are abstract. Both new files were scanned
                                  against test_fixture_hygiene's own
                                  FORBIDDEN_DOMAINS (44), FORBIDDEN_NAMES (59)
                                  and FORBIDDEN_FIGURES (15) - CLEAN on all
                                  three - and every address in them is on a
                                  SAFE_SUFFIXES domain. This matters because
                                  five hygiene tests are ALREADY RED on this
                                  tree, and a new violation would hide inside
                                  an existing failure.

## 9. TEST EVIDENCE

    the new module alone        Ran 44 - OK          (no skips, no expected failures)
    with 0190's instrument      Ran 83 - OK          (skipped=1, expected failures=4)
                                the 1 skip and the 4 are 0190's, unchanged

    the five hygiene names already red on this tree, BEFORE and AFTER:
      test_every_email_address_is_on_a_reserved_domain
      test_no_linkedin_url_with_real_vanity_name
      test_no_real_client_prospect_or_roster_domain
      test_no_real_person_or_client_named
      test_the_identifiers_appear_nowhere_ELSE_in_the_repository
    Same five, same set. None is mine, and my files were checked against the
    constants directly because a failing test masks a new violation.

**A change under `tests/` and a new `scripts/` file always owe a new suite
reference** (operator, 2026-10-02). That reference is NOT measured in this
task and the merge gate for this branch is therefore **UNMET**. Stated as a
gap, not worked around: the branch is durable on its own ref and is not
proposed for master.
