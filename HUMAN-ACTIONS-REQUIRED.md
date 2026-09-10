# Things only a person can do

Everything here is blocked on an action with a consequence outside this
repository - a credential, a paid call, a provider mutation, a business
decision. Nothing in this list stops other work, and none of it has been
attempted autonomously.

No secret values appear in this file, and none should ever be added to it.

---

## 1. WITHDRAWN 2026-09-09 by operator decision - do not rotate

The operator has instructed, explicitly and more than once, that no provider
credential is to be rotated and that this must not be asked again. The
Productive EmailBison credential was replaced with a new one on 2026-09-09 and
binds to workspace 10 (item 4c), which supersedes the original finding below.

**Nothing here is an open request.** It is kept because the exposure reasoning
is evidence, and because a future reader should know the decision was taken
rather than overlooked.

## 1-old. The original finding, kept because it is the evidence

**What** Issue a new EmailBison key and put it into Railway's service
variables as `BISON_KEY`. Revoke the previous one.

**Why** The current key was pasted into a chat transcript during an earlier
session. It has to be treated as public.

**Risk of leaving it** Anyone holding it can read the whole lead base and
reply history for this instance, and can write to campaigns.

**Verified** The value is not in the working tree, not in any committed
file, and not anywhere in git history. It was passed to read-only probes
through the environment only.

**Exact action** EmailBison → API keys → create, copy into Railway → revoke
the old one. Then `python -m src.replywatch --status` should still report a
recent success.

---

## 2. BLOCKING for the current cohort - confirm Deliverable, then arm it

**What** One live verification of an address you control that is genuinely
deliverable, then set `DELIVERABLE_RESULT_SHAPE=confirmed`.

**Why** The response shape has now been read - one canary on an address that
certainly does not exist returned `data.email_status: undeliverable`, and the
adapter has been corrected to read `email_status` and `processing_status`,
which are the fields this provider actually sends. It previously looked for
`status`/`result`/`state`/`verdict`, so every real answer classified as
`unknown`: armed, it would have spent a credit per address and confirmed
nothing. Only the negative branch is proven. A verifier whose positive branch
has never been seen is the one that must not be trusted to say `valid`.

**Cost** One credit.

**What it unblocks** Catch-all domains. `accept_all` is not a confirmation, so
a catch-all address tops out at one of the two required approvals no matter
how many vendors answer - and Reoon is the only vendor this policy trusts to
clear one. It does not unblock the email lane generally: ContactOut and Reoon
already give two independent opinions on ordinary addresses.

**This is no longer theoretical.** Both remaining Productive contacts are on
`brightpath.test`, which is confirmed catch-all: ContactOut returned
`accept_all` for both addresses and Reoon, in power mode, returned
`is_catch_all: true, is_safe_to_send: false`. Tested directly - even if Reoon
had said *safe*, the address still resolves to `held`, "catch-all cleared by
reoon, but only 1 of 2 required independent confirmations". `CONFIRMING_STATUSES`
is `('valid',)`, so a catch-all can never be the confirmation itself, and the
only vendor that could supply the second cannot make a call.

**So Jonathan Gessert and Briley Brind'amour are structurally un-emailable,
not merely unverified**, and no further verification spend can change that.
One Reoon credit remains unspent on Briley for exactly this reason: it would
buy an answer that cannot alter the outcome.

**It is also costing money to leave shut.** An `error` is deliberately not an
answer, so `verify()` re-attempts Deliverable on every run, for every
MX-allowed contact, forever. Each attempt charges a unit of the per-contact
cap and buys nothing, because `require_contract` refuses before any HTTP call.
Negligible on three contacts; material at list scale, and it silently eats a
third of the three-credit per-contact cap on every address.

**Exact action** Verify one address you own, check the answer is
`email_status: deliverable` and that `classify` returns `valid`, then set
`DELIVERABLE_RESULT_SHAPE=confirmed` in Railway. The validation harness does
it for one credit:
`py -m src.validate --provider deliverable --live-validation --max-credits 1`.

---

## 3. Confirm which LinkedIn accounts are Productive's

**What** Confirm that `HEYREACH_KEY` belongs to Productive's workspace, and
name the accounts approved for the pilot.

**Why** A read of `/li_account/GetAll` returns 41 accounts - 33 with valid
auth and active, one active on invalid auth. **No field on any of them names a
workspace, client, team or owner**, and `src/providers/heyreach.py` contains
no tenant concept because the API exposes none. So the credential is the only
boundary there is, and nothing in this repository records whose credential it
is. Building a sender roster from those accounts would be assuming ownership.

**Risk of leaving it** The LinkedIn lane cannot open. The local roster's
`provider_account_id` values (`4002`-`4005`) match nothing live - real ids run
116968 to 212356 - so sender selection would choose accounts that do not
exist.

**Exact action** Confirm the key's workspace, and list the account ids that
may send for this pilot.

---

## 4. RESOLVED 2026-09-09 - a workspace-scoped EmailBison credential exists

**A new credential was supplied and verified read-only.** `GET /api/users`
reports `workspace.id == 10`, `workspace.name == "PRODUCTIVE"`, and
`GET /sender-emails` returns **15 inboxes across 11 domains, every one
Productive-branded** - `goacme.test`, `goacme-net.test`,
`tryacme.test`, `withacme.test/.org/.net`,
`goacmelab.test/.org/.live/.shop`, `goacmelabs.test` - and **zero
Greenfield domains**. `GET /replies` answers for that workspace with 0 rows, which
is correct: nothing has been sent for Productive.

Compare the old credential, below: 32 inboxes, every one Greenfield, and 225 the
day before. That was cross-tenant, and this is not.

**What this does NOT do.** It opens the read side of the email lane. It does
not make anything sendable, and four things still stand between here and a
send:

  - `push.run(live=True)` still raises. There is no send path, by design.
  - **`work/senders.jsonl` is still entirely fixture** - `productive.test`
    addresses with `provider_account_id` `bison-1..64`. The 15 real inboxes
    above share no domain and no id with it, so sender selection still cannot
    address a real inbox. This is now the sharpest remaining code blocker and
    it is newly actionable: it can be rebuilt from the read above.
  - No contact is verified. 0 of 3 are sendable.
  - Deliverable's contract is still shut, so a catch-all cannot be cleared.

**The binding is a window, not a fix, and that has not changed.** `workspace_id`
is still accepted and discarded by every list route, so the only thing making
this credential trustworthy is `GET /api/users` agreeing at the moment of the
call. Any send must re-check the binding immediately before it, not once at the
start of a run. `poller.run` already refuses a mismatch and the reply
checkpoint is scoped per workspace, so the read side enforces this today.

**The key was supplied in a chat transcript**, so item 1 below - rotate the
EmailBison API key - now applies to this one and is worth doing once it is in
`config/.env`. Note also that the code reads `BISON_KEY`; `EMAILBISON_API_KEY`
is not a name anything looks at.

---

## 4-old. The original finding, kept because it is the evidence



**What** Obtain a workspace-scoped EmailBison credential for PRODUCTIVE
(workspace id 10), or prove the current one's context another way.

**Why** Re-read read-only on 2026-09-08. `GET /sender-emails` returned
**32 inboxes, every one of them a Greenfield domain** - `gogreenfield.test`,
`trygreenfield.test`, `greenfielddigital.test` and thirteen more, tagged
`Resonate - CI` and `Nada Outlook - CI`. **Not one row mentions Productive.**
`GET /campaigns` returned 25 campaigns, all Greenfield's. `PRODUCTIVE` is still
present in `GET /workspaces` as id 10, looking perfectly addressable.

The same call has now returned three different estates in two days - 51, then
225 with 153 rows tagged Productive, now 32 with none - **with nothing in this
repository changing**. The credential's workspace context is selected outside
this system and moves silently.

The scoping trap is worse than previously recorded. Re-probed across six query
forms (`workspace_id`, `team_id`, `workspace`) and eight header forms
(`X-Workspace-Id`, `X-Team-Id`, `Workspace-Id`, `X-Workspace`), with both a
real id and a nonexistent one: **every variant returns 200 with a
byte-identical id set.** `/workspaces/10/sender-emails`, `/workspaces/current`,
`/me`, `/user` and `/account` are all 404. There is no request-side workspace
selector. No sender row carries a workspace, team, tenant or owner field - 24
fields, checked.

**Corrected 2026-09-08, and it makes this action much smaller.** This section
previously said there was no "who am I" route. There is one, and it is the
plural: `GET /api/users` returns 200 with the credential's single bound
workspace under `data.workspace`. `/me`, `/user`, `/account`, `/whoami` and
`/workspaces/current` are all 404, which is why it was missed. The estate
moved again on the re-read - it is now **Bluewave** (workspace 29), 32
Bluewave-family inboxes, 0 campaigns - so the count is four estates in three
days, not three in two.

Two consequences. First, the binding is now **machine-verifiable**, so the
manual control in (b) below is no longer standing in for a proof:
`src/providers/bison.bound_workspace()` reads it, and `poller.run` refuses to
poll when it does not match `BISON_WORKSPACE_ID`. Second, `GET /campaigns/417`
returns 403 with a body naming the remedy in the vendor's own words - *"consider
using api-user keys or switch to the workspace this record is on"* - which
strongly implies a per-workspace credential class exists and is worth asking
for by name.

One defect was found and fixed off the back of this, and it was live rather
than theoretical: the reply checkpoint was keyed by provider alone while the
feed is per-workspace, so a poll taken while bound to Bluewave stored
Bluewave's newest reply timestamp and would have made every older Productive
reply invisible for ever - on the path whose job is to stop a cadence when
somebody answers. The mark is now scoped per workspace.

The `tags` fallback is gone too: yesterday 153 of 225 rows said "Productive",
today 0 of 32. Operator-typed free text is not an ownership boundary, and this
is what its failure looks like.

**Risk of leaving it** A canary armed today against "workspace_id=10" would
have sent Productive's mail **from Greenfield's inboxes**, received HTTP 200, and
recorded a success. Nothing in this build could have detected it, because the
API does not expose the fact. This is not a theoretical tenancy concern; it is
the live state of the credential.

**Exact action** One of:
- **(a) Preferred.** Get a credential issued for PRODUCTIVE only, then re-run
  the read and confirm the sender list comes back as Productive domains. This
  is the only option that makes the boundary machine-checkable.
- **(b) Now sufficient, and it takes about a minute.** Log into
  send.resonategroup.co as the account owner and switch the active workspace
  from `Bluewave` to `PRODUCTIVE`, then set `BISON_WORKSPACE_ID=10`. This is
  no longer a manual control standing in for a proof: afterwards
  `GET /api/users` must report `workspace.id == 10`, and every poll re-checks
  it and refuses on mismatch. Confirm with a read - campaigns 417 and 418
  should become listable, and the sender list should return Productive domains.

  Two things to know before relying on it. The switch is **global**: it moves
  the workspace for the whole account, so anyone working Bluewave or Greenfield
  in that UI moves the context back, which has happened four times in three
  days. It is a window, not a fix. And any send must re-check the binding
  immediately before it, not once at the start of a run.
- **(c)** Ask the vendor how a credential's workspace is selected, and whether
  a per-workspace key can be issued at all.

**Until (a) or (b) is done the email lane cannot open for Productive.** No code
change fixes this.

---

## 4b. RESOLVED 2026-09-09 - the operator attested the org unit and the pool

**Attested:** `organizationUnitId 118832` is the HeyReach org unit for this
Productive pilot, and the 33 accounts that are `authIsValid AND isActive` are
the approved Productive sender pool.

**Reconciled read-only against the API, first read of `/li_account/GetAll` from
this repository.** 41 seats total; `authIsValid AND isActive` is **exactly
33**, matching the attestation. The route was on no read allowlist - a comment
here said sender accounts were unavailable because `/linkedinaccount/GetAll`
answers 404, which was the wrong route name rather than an absent capability.

**32 are in the approved pool.** One of the 33 is excluded: it is the only seat
carrying a `productive.test` address and is most likely a real employee's own
profile, so a canary from it risks a person's LinkedIn rather than an agency
seat. That exclusion is a judgement, recorded as one.

**29 READY, 3 DEGRADED** - one exhausted against today's connection limit, two
cooling down. Real per-seat limits read for the first time: a ceiling of 40
connection requests each, **1,160/day across the ready pool, 970 remaining
today**. Account 129531 remains `isActive: true` with `authIsValid: false` and
one active campaign - outside the 33 by construction, and a HeyReach UI
reconnect rather than anything this system can fix.

**Proposed canary seat: 116968**, chosen deterministically - READY, fewest
active campaigns (8), lowest id on the tie. Not ordered on a limit: the limits
move between reads, and a tie-break on a moving field is a judgement wearing a
formula.

**What the attestation does not resolve.** HeyReach exposes no tenant, client,
owner or team field on an account - confirmed across all 15 keys - so ownership
cannot be re-derived and the attestation IS the field. It must stay written
down as exactly that. And `organizationUnitId` is on the CAMPAIGN, not the
account, so a seat in no campaign has no derivable org unit at all.

---

## 4b-old. The original request, kept because it is the evidence



**What** Two sentences in writing.

**Why** HeyReach is clean and readable - `POST /li_account/GetAll` returns 41
accounts, 33 with `authIsValid` and `isActive` both true, ids 116968-212356 -
and all 79 campaigns carry a single `organizationUnitId` (118832), so there is
no cross-tenant mixing inside the key. What is **not** proven is that org unit
118832 is Productive's rather than Resonate's own agency org holding several
clients' seats. The evidence points at the latter: 19 campaigns are named
`OMEGA`, `Warmup 1-6`, `inmail`, which is not Productive work. No field on any
account names a workspace, client, team or owner. Campaign-name matching would
give 38 accounts, but "the operator typed PRODUCTIVE in the name" is an
assumption about a string, not a proof.

**Risk of leaving it** LinkedIn is the only lane that could open at all, and it
cannot open on an assumption about a campaign name.

**Exact action**
1. Confirm that `HEYREACH_KEY` / org unit 118832 is authorised to send on
   Productive's behalf.
2. **Name the specific account ids approved for the canary** - one is enough.
   Choose from the 33 that are `authIsValid AND isActive`.

Then those ids become the canonical roster: a recorded human decision standing
in for a field the API does not have, which is honest as long as it is written
down as exactly that.

**Also fix, unrelated to the canary:** account **129531** (Andjela Operator) is
`isActive: true, authIsValid: false, activeCampaigns: 1` - assigned to a live
campaign and unable to send. Nothing in this build reads either field.

---

## 4c. RESOLVED 2026-09-09 - the credential binds to Productive workspace 10

**Was** The binding moved to workspace 29 (Bluewave) mid-session and three
prior-contact reads answered CLEAR against another client's empty estate
(PRODUCT-GAPS 34). All Productive EmailBison mutations were blocked.

**Now** The operator set the new credential and `BISON_WORKSPACE_ID=10`.
Verified in a fresh process with the environment scrubbed and `config/.env`
read from disk:

| check | result |
| --- | --- |
| variable actually consumed | `BISON_KEY`. Proved by pointing `ENV_FILE` at two distinct junk values and reading which one reached the header. `EMAILBISON_API_KEY` is read by no code in the repository |
| `require_workspace(10)` | passes |
| `require_workspace(29)` | raises `WorkspaceMismatch` - the pin is enforced, not merely reported |
| sender inventory | envelope `total=225`, 225 rows walked, **225 unique addresses**, 0 blank, 0 duplicate |
| leakage | 86 domains, every one Productive-branded; no Bluewave, Ironvault, Greenfield or Stagfield domain |
| campaigns / leads | 20 campaigns and 27,147 leads, all Productive-named |
| binding re-asserted after the sweep | still 10, so the sweep stands |

**EmailBison Productive tenancy is GREEN.** `work/senders.jsonl` was rebuilt
from all 225: **202 READY, 23 DEGRADED, 3,030 sends/day**. Degradation is
lifetime bounce rate at or above 2% (20 inboxes) and warmup-on-with-nothing-sent
(3).

**No further EmailBison UI action is required.**

**Still true, and unchanged by any of this:** `workspace_id` is accepted and
discarded by every route, so the binding is a property of the credential and is
chosen in the vendor UI. `require_workspace` re-asserts before and after a long
sweep; the window between the check and the read cannot be closed from here
(PRODUCT-GAPS 34c).

---

## 5. One Productive targeting decision

**RESOLVED on 2026-09-09:** the persona half. The operator approved Head of
Production, Production Director, Design Studio Manager, Studio Manager, Project
Director and Design Director as a config-driven family expansion. All six now
classify as `champion` and route to `operations`, `delivery` or
`resource_management` rather than founder copy. Arbitrary titles still fail
closed. 16 tests pin it.

**What remains** Whether a **catch-all domain** may be approached at all.

**Why** `brightpath.test` is a catch-all where both verifiers agree and
Reoon explicitly declines it as unsafe. Briley Brind'amour there is
collision-clear on both channels and would otherwise be a candidate.

**What it unblocks** One additional candidate at one qualified account. It is
no longer the only thing standing between the pilot and a canary - `ninefields.test`
now has three.

**Exact action** One answer: may a catch-all domain be approached.

---

## 5b. The per-domain champion cap, if a third person at one account is wanted

**What** `cap_per_domain: 2` for champions at `ninefields.test`.

**Why** Dana Marsh and Dale Morgan took the two slots. Russell Garnaut
(Project Director) is a legitimate champion after the expansion, verified 2/2,
sendable, clear on **both** channels, and renders CLEAN - excluded only by the
cap. Ciara Kelleher is also capped out, and separately she is the one person at
this account who has already received email from the client's own campaigns.

**This is not blocking anything.** Two candidates are enough for a one-person
canary. It is recorded so the cap is a decision rather than a surprise.

---

## 5d. The pilot funnel has reached its legitimate boundary

**What** The 50-account pilot cannot produce another candidate without an ICP
decision, and the reason is a data fact rather than a missing capability.

**The whole cohort was collision-swept, read-only, against Productive
workspace 10.** Of the 39 accounts at `review` or `unknown` with nobody
discovered yet, **34 have already been worked by the client's own campaigns** -
touched or with somebody in sequence right now. Five are clear:

| domain | status | score |
| --- | --- | --- |
| **riverbend.test** | review | **47.0** |
| blendworks.test | unknown | 15.5 |
| clearwater.test | unknown | 15.0 |
| newagency.test | unknown | 9.0 |
| harperandco.test | unknown | 4.0 |

Only `riverbend.test` scores anywhere near qualifying, and the four below it are far
enough down that a credit on them is not defensible.

**`riverbend.test` needs no enrichment credit.** Its company facts are complete:
78 people, Advertising Services, New York, `research_outcome: HTTP_SUCCESS`. It
scores 47.0 with six positive signals and is held at `review` by a single
**-10 `contradictory_evidence`**: *"classified as Creative / Branding Agency
while its stated industry and specialties show education signals"*. The
specialty that triggers it is `COLLEGE MARKETING`.

**Why this was not fixed autonomously.** A specialty naming a client's vertical
is arguably not evidence about the agency's own industry - 28 ROW markets to
colleges, it is not a school - and that reads like a real modelling defect in
the contradiction rule. But changing the ICP scorer with one account in view is
the same move as widening a lint rule to pass a draft, and `CLAUDE.md` forbids
person-level credits at `review` in any case. So nothing was spent and nothing
was tuned.

**Exact action** One of: (a) confirm that a client-vertical word in
`specialties` should not raise `contradictory_evidence` about the agency's own
industry, which is a general scorer fix and would carry `riverbend.test` to
`qualified` at 57.0; or (b) accept `riverbend.test` at `review` as a one-off
targeting call; or (c) leave the pilot at three qualified accounts.

**What it unblocks** A fourth qualified account and the only untouched one in
the entire pilot. It does not block the canary - `ninefields.test` has three
cleared candidates today.

---

## 5c. Create a one-person HeyReach canary campaign

**What** A dedicated Productive campaign in the HeyReach UI: sender 116968
(Mina Ruzicic), exactly one lead, connection request **with** a note,
conservative limits.

**Why it cannot be done from here** `src/providers/heyreach.py` exposes read
routes and a not-implemented add-leads path. There is no campaign-create route
in this build, so this is a UI action by construction.

**Why no existing campaign can be used** All three candidates were read live
and classified against their real sequence graphs:

| campaign | state | LinkedIn-only | why it is refused |
| --- | --- | --- | --- |
| **524002** | IN_PROGRESS | yes | **50,563 leads** (28,849 in progress) and its connection request **carries no note**, so our copy would never reach the prospect |
| **524026** | DRAFT | yes | bound to `linkedInUserListId 605355` - **the same 50,563-lead list 524002 is running**. Activating it is a mass-send hazard, and it includes two seats outside the attested 33 (129531, 194061) |
| **567683** | FINISHED | yes | excluded by the operator; and its sequence is `CHECK_IS_CONNECTION -> MESSAGE`, so it messages existing connections and never sends a connection request at all |

**Exact action** HeyReach → new campaign → sender Mina Ruzicic (116968) → a new
list containing one lead → connection request with the approved note → daily
limit 1. Do not attach list 605355.

---

**What** Whether a Project Director is a Productive buyer, and whether
catch-all domains are in scope.

**Why** Both came out of the real 50-domain pilot. `ninefields.test` qualified
with an open email lane and four people who verify cleanly, and all four were
excluded as "not a persona": Head of Production, Design Studio Manager,
Project Director, Design Director. Three are plainly creative and delivery
roles. The fourth is arguable - the config lists Operations Manager *and*
Operations Director, so it targets both seniorities of a function, and lists
Project Manager without Project Director. That reads like an omission rather
than a decision, but it is a decision either way and not one to infer.
Separately, `brightpath.test` is a catch-all domain where both verifiers
agree and Reoon explicitly declines it as unsafe.

**What it unblocks** The pilot's only remaining candidates. Without one of
these two answers there is no sendable person in the current 50.

**Exact action** Two answers: is a Project Director in the persona set, and
may a catch-all domain be approached at all.

---

## 5e. Press unpause on campaign 594061 - the canary's only remaining step

**What** In the HeyReach UI, unpause `PRODUCTIVE - CANARY - 2026-09-09`
(campaign 594061). That is the whole execution. Nothing else is waiting on
anything.

**Why it is a human action and not a missing feature** `heyreach.activate`
has no documented route. Neither does `create_campaign`, `set_sequence`,
`assign_sender` or `pause`. This is recorded per-operation in
`providerwrites.OPERATIONS` with the reason for each, and `SUPPORTED` is
empty, so the write layer refuses every one of them by name rather than by
a flag. Activation is a vendor-UI action for this provider, and building a
route by guessing at an undocumented verb is the one thing that must not
happen on a prospect-facing path.

**What the system has established** Running the execution guard against
live provider truth on 2026-09-10, 13 of 14 gates pass:

    PASS tenancy  approval  campaign_approval  readback  eligibility
    PASS suppression  copy  claims  fatigue  collision  sender
    PASS pilot_cap  ledger
    STOP killswitch - global: live sending is refused in code

The killswitch is the only stop, and its global layer is derived from
`push.py` raising rather than read from a flag, so it is not something to
turn off. It is also not what is holding the canary back: the write layer
refuses independently, and the execution path is the UI.

**Blast radius, exactly** One LinkedIn connection request, from seat 116968,
to the single lead already staged on campaign 594061, carrying the approved
connection note and no other text.

The prospect and the note are deliberately NOT reproduced here: this file is
tracked and published, and `test_fixture_hygiene` refuses a real person or
client name in any tracked file. Read both back from the provider instead -
`python -m src.providers.heyreach --sequence 594061` prints the note that is
actually configured, which is the copy that matters rather than a
transcription of it. It was verified against the approved fingerprint on
2026-09-10 and matched.

The campaign holds one lead and the approved configuration caps it at one,
so a second person cannot be reached by this campaign even by accident. The
seat's existing conversations were scanned and there is no prior invitation
to this person.

**THE RISK TO ACCEPT BEFORE PRESSING IT.** Once a HeyReach campaign is
running, nothing in this system can stop it. `heyreach.pause` has no route
either, so the killswitch cannot reach a running campaign - it can refuse
to start something, and it cannot end something already started. For this
canary that is bounded: one lead, one invitation, and pressing pause again
in the same UI is the stop. It is stated here because it is the honest
precondition, not because the canary is dangerous.

**Do not reply through this system.** No auto-reply exists and none is
authorised. A reply is a human's.

---

## 5f. The promotion ladder is gated on a stop, not on the canary's result

**What** 1 -> 3 -> 5 -> 10 -> 20 -> 50 cannot proceed on LinkedIn on the
strength of a good canary alone.

**Why** The pause asymmetry above does not scale with the ladder. At one
lead, "press pause in the UI" is a real stop and the exposure while
reaching for it is one person. At fifty, the killswitch is decorative: the
system would be running an outreach campaign it cannot halt, and the only
brake is a human in a vendor UI who may be asleep or on a plane. That is a
different risk from the one the canary carries, and it arrives at the step
where volume starts mattering rather than at fifty.

**Exact action, one of:**

1. Establish a HeyReach pause verb, read a successful response back, and
   add `heyreach.pause` to `SUPPORTED` - after which the killswitch reaches
   running campaigns and the ladder is a normal promotion decision; or
2. Agree an out-of-band stop and write it down: who can reach the HeyReach
   UI within what time, on which days. A named person with access is a
   real control. An unstated assumption that somebody is watching is not; or
3. Run the ladder on EmailBison instead, where the same gap exists
   (`bison.pause` is equally unrouted) - so this is not a way around the
   problem, only a note that switching channel does not solve it.

Until one of those is true, LinkedIn promotion stops at the canary. This is
a real blocker on a safety property, not architecture perfection: the
system would be asserting a killswitch it does not have.

---

## 6. Provide a Slack bot token and channel

**What** A bot token, an ops channel, and a signing secret.

**Why** The notification layer, the routing policy and the interactive
approval path are all built and fixture-proven. Nothing has ever been
posted, so none of it is live-validated.

**Risk** Low. Posting additionally requires `SLACK_LIVE`, which is a
separate switch, so a token alone changes nothing.

**Exact action** Set `SLACK_BOT_TOKEN`, `SLACK_OPS_CHANNEL` and
`SLACK_SIGNING_SECRET` in Railway. Leave `SLACK_LIVE` unset until the first
message has been reviewed.

---

## 7. Decide the Productive exclusivity question

**What** Agree whether Resonate owns a segment that HeyReach's existing
campaigns never touch.

**Why** Roughly 160,000 prospects are mid-sequence in that agency's own
HeyReach campaigns. The EmailBison side has been checked exhaustively and is
clean, but the LinkedIn side cannot be checked from here. Of the three ways
to avoid approaching somebody twice, only an agreed segment is correct by
construction rather than by two systems staying in sync.

**Risk of leaving it** A prospect hears from the same company twice, about
two different things, from two senders - and the first they know of it is
the second message.

**Exact action** A conversation with Productive, not a build.
