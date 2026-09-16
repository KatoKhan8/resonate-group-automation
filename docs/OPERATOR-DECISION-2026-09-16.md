# What is blocked, what is decided, and what is yours - 2026-09-16

Written by Claude during the overnight autonomous run. Everything below is read
off the code, off provider truth, or off a measured run. Where an earlier
version of this document was wrong, the correction is marked and the wrong
claim is left visible, because it was wrong in a direction that mattered.

---

## CORRECTION, AND IT IS THE MOST IMPORTANT THING HERE

An earlier version of this file said:

> Every verb that adds a person, and every verb that starts a campaign, is
> unauthorized on both channels. [...] Nobody can be put in it.

**That is wrong for EmailBison.** `providerwrites.SUPPORTED` gates only the
operations routed through `providerwrites.perform`. The Bison staging path does
not route through it for leads, and says so in its own comments:

    `_ensure_leads` calls `bison.create_lead` and `bison.attach_leads`
    directly, bypassing `executionguard.authorize()` and every gate it runs.

So `bison.add_lead` being absent from `SUPPORTED` does **not** mean leads
cannot be staged. `bisonfactory.stage(campaign_id, live=True)` stages them,
behind a different and genuinely substantial set of gates it applies itself:
workspace killswitch, account-level collision via `collision.check_account`,
approval of every draft step, lint, and a configured daily cap.

Two consequences.

1. **The real EmailBison blocker is approval and activation, not lead-adding.**
   `_ensure_leads` refuses with "Generate and approve the missing steps, then
   stage again" when a step lacks approval, and approval is
   `operator-control-arm`, which is a human. Activation (`bison.activate`) is
   separately unwired.
2. **`SUPPORTED` is not a complete description of what this system can write.**
   Reading it as one is the mistake this correction records. `set_limits`,
   `attach_senders`, `create_lead` and `attach_leads` are all called directly
   by the factory. That is not necessarily wrong - the factory's own gates are
   real and were added after measured incidents - but anyone auditing the write
   surface by reading `SUPPORTED` will get the wrong answer, and I did.

HeyReach is unaffected: its list path was built this morning to route through
`perform`, and `heyreach.add_lead` is both in `SUPPORTED` and conditional.

---

## WHAT HAPPENED TO THE EMAILBISON WRITE

I intended to perform it and could not. The work is finished, the path is
rehearsed, and the last step needs you.

**Everything up to the write is done:**

- **TASK-159** - the CONTROL sequence from the audited templates.
  `persona_pain -> comparable_proof -> breakup`, threading F/T/F on the
  `thread_reply` boolean, subject carried on the reply with "Re:" prepended by
  the provider. Copy generation stays closed.
- **TASK-167** - resolved against the real queue. All 17 contacts render, all
  51 step-renderings pass lint, all 51 pass the claims gate. Payload in
  `docs/BISON-CONTROL-PAYLOAD-2026-09-16.md`.
- **TASK-170** - the seven-check pre-write check, fail-closed, provider-or-local
  annotated per value. On its first real run against campaign 481 it failed
  check 7 and named a genuine collision: one domain has 13 prior emails at the
  provider, from the client's own history.
- **TASK-177** - the cohort after that gate spoke: **16 of 17 survive**, zero
  UNDETERMINED, and 6 of the 16 carry `persona=None`.
- **TASK-174** - campaign 481 is the wrong destination. It holds 23 people, all
  with 6-40 historical touches, under a five-step sequence that is not CONTROL.
- **TASK-184** - rehearsed the write against a fake and proved the fact that
  governs it: **`set_sequence` APPENDS.** A second write yields six steps, not
  three. The brake is `_ensure_sequence`, which reads the provider's current
  steps first, skips on identical and refuses on different. Recovery procedure
  for a half-failed write is in `docs/BISON-WRITE-REHEARSAL-2026-09-16.md`.

**A dry run of the real thing, just now, succeeded.** Local campaign row
`productive-email-control-v1` created (local state only, no provider call):

    provider name  RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS - CONTROL
                   [productive/productive-email-control-v1]
    sequence       3 steps, {SUBJECT_N}/{BODY_N}, waits 3/4/0
    leads          []          <- record_ids is empty, deliberately
    senders        none        <- "choosing an inbox would be choosing who a
                                   prospect hears from"

With no records and no senders, `stage(live=True)` would create the campaign,
cap it at 20/day, write the schedule, write the CONTROL sequence through the
authorized door, stop the campaign, and add nobody. Non-prospect-facing, and
the furthest this channel can go without you.

**Then the harness refused it.** Claude Code's auto-mode classifier blocked the
live provider call from this session. I did not work around it. The row is in
`work/campaigns.jsonl`, which is gitignored, so if that file is lost the row is
recreated by the snippet in the rehearsal document.

To perform it yourself:

    py -3 -c "from src import bisonfactory; import json; \
      print(json.dumps(bisonfactory.stage('productive-email-control-v1', \
      live=True, by='operator'), indent=1))"

Run `scripts/bison_prewrite_check.py` against the returned campaign id
afterwards. **Do not re-run `stage` if it fails partway** - read
`bison.sequence_steps(provider_id)` first; three correct steps means it is
done, six means the append trap fired.

---

## HEYREACH - the staging question is conclusively resolved, the better way

**Campaign-level staging does not exist.** `AddLeadsToCampaign` is refused in
DRAFT; in PAUSED and FINISHED, adding a lead can ACTIVATE the campaign. No
campaign state is safe. `CAMPAIGN_LEVEL_STAGING_IS_PROVEN = False` stands, and
`LINKEDIN_ADD_LEAD`'s reseal is intact - its condition
`_campaign_is_a_declared_staging_campaign` can no longer be satisfied by any
campaign, so the verb is sealed in practice. **Do not weaken that.**

**List-level staging does exist, and it was found, not invented.** TASK-158
established the schema HeyReach does not document:

    POST /list/AddLeadsToListV2
    {"listId": <id>, "leads": [{"profileUrl", "firstName", "lastName"}]}

`firstName` and `lastName` are REQUIRED and the provider **silently drops** a
lead missing either, answering HTTP success with
`addedLeadsCount: 0, updatedLeadsCount: 0, failedLeadsCount: 0`. Twelve other
body shapes returned the same 0/0/0 - which is why the route looked broken for
a day. A 200 is not a success on this route. Proven by a real add to unbound
list **940797**, readback `totalCount: 1`.

So **adopting "ADD_TO_CAMPAIGN == ACTIVATION" is not necessary.**

What is missing is a permission. TASK-172 defined
`heyreach.add_lead_to_list` with the predicate
`liststaging.assert_list_safe` - ours, our tenant, `campaignIds` empty, read
from the provider at the moment of the write - and left it in **neither
`SUPPORTED` nor `CONDITIONAL`**. TASK-165 designed the path with 42 tests;
TASK-186 rehearsed it, including the test that proves the OFF switch refuses
loudly and names the missing permission, and the test that treats 0/0/0 as
failure.

**What the condition cannot promise:** a list unbound now can be attached a
second later by anyone with account access, and attaching it makes every lead
in it a lead in a campaign. Campaign 599020 already has list 933603 attached,
so "a list we created" was never the safety property.

LinkedIn's other blocker is copy approval, not schema: of the three canary
contacts on rung 3 of the ladder, one has `operator-control-arm` approval on
all eight roles, one has seven fallbacks and a generated `li1` that fails lint
(em dash) and claims (a flat assertion about the prospect), and one has no
approved copy at all. TASK-179 confirmed the CONTROL fallbacks pass lint and
claims for **all three** - so approving those fallbacks makes a three-contact
canary possible.

---

## THE DECISIONS THAT ARE YOURS

None of these has been taken.

1. **Approve the CONTROL steps for the email cohort.** `_ensure_leads` refuses
   without it. This is the gate that stands between a staged campaign and a
   staged campaign with people in it.
2. **Enable `bison.activate`**, or activate in the UI. This is what makes
   EmailBison send. Prospect-facing.
3. **Enable `heyreach.add_lead_to_list`** (defined, left off). Not
   prospect-facing while its condition holds - an unbound list sends nothing -
   and the cheapest of these to say yes to.
4. **Approve the LinkedIn CONTROL fallbacks** for the two unapproved canary
   contacts, or accept a canary of one.
5. **The email canary: 16 or 10?** Six of the 16 carry `persona=None` and get
   the champion persona's finance angle regardless of role. Configured
   behaviour, passes every gate, and precisely the shape of thing
   `docs/LEADS-ARE-BLOCKED-2026-09-14.md` found fails a human read. My
   recommendation is the 10 whose angle is their own.
6. **Campaign 481's 23 leads.** Blocks nothing now that a new campaign is the
   plan, but somebody must eventually say what they are for.
7. **The record-id convention.** Record ids derive from prospect domains, so
   a record id of the form `<company>-com` identifies a prospect as well as `<company>.com` does.
   TASK-189's verdict is that the PII guard is right to flag them and
   allowlisting would open a hole the size of the queue. Changing the
   convention reaches provider state we do not own: leads at EmailBison carry
   `record_id` in custom fields with no bulk update route.
8. **The PII leak in git history** - a sender's real name at `abae39b`,
   scrubbed at `ca53cb5`, plus everything scrubbed today. The working tree is
   clean; history is not. A rewrite is yours.
9. **Whether to grant this session permission to make provider writes**, if you
   want Claude to finish item 2's mechanics rather than doing it yourself.

---

## THROUGHPUT - the wall moved twice and is not where anyone thought

**The free path is safe and it is done.** TASK-163 proved an evidence-free
record cannot reach `dropped`: `icpstructural.verdict_of` needs at least one
FAIL, absent evidence every criterion returns UNKNOWN, and UNKNOWN with no FAIL
is review. A full run over the estate then completed: **373 records, 1119
seconds, ZERO credits spent**, every paid call refused by `--cap 0`.

    states after   verified 65   held 32   dropped 126   queued 315   drafted 12

**The qualification bar is two criteria, not five.** TASK-187 corrected the
premise everyone including me was working from. `verdict_of` also returns
`icp_pass_with_uncertainty` when **geography and company_type** both PASS, and
both forms map to `icp_status = "qualified"`, which is what gates person-credit
spend. 113 records have already come through that door, every one with
`tracks_time = unknown`, as designed. Resolving `tracks_time` would change the
qualified count by **zero**.

**Buying structured data does not work.** TASK-185 spent 25 credits on
ContactOut company-info across 50 records and moved **zero** verdicts and
resolved **zero** criteria. Geography did not resolve because the offices
returned sit in countries outside the client's include list; company_type was
already PASS wherever any industry was known. **This saves roughly 300 credits
that the obvious plan would have spent.** Do not scale it.

**Grok does find things, at a price.** TASK-166, on 10 real domains: 174 facts
the free path lacks, **every one with a source URL**, at **$0.20/domain**. Six
of the ten had zero usable free-crawl evidence and for those Grok found all the
public evidence there was - webfetch is same-domain-only and cannot reach a news
article or a registry. It also caught a rebrand three structured providers have
stale. It also revealed that TASK-157's adapter targeted an endpoint xAI has
withdrawn (`live_search`, HTTP 410); TASK-182 moved it to the Responses API and
added a drift test. TASK-192 measures whether Grok moves *verdicts* rather than
adds facts - the only number that matters, and it is unmeasured.

### THE ANSWER, AND IT HAS A PRICE ON IT

TASK-199 closed this. **`company_facts` is the field that serves both gates:**
industry feeds ICP's company_type and the copy gate's fact pool, offices feed
geography and the pool, employees feed both. `research[].fact` serves only the
copy gate; `segment.country` only ICP. So one purchase can unblock a record at
both ends - if it populates `company_facts`.

    blocked at ICP (geography or company_type UNKNOWN)      349
    blocked at generation (verified, zero usable research)    20
    overlap                                                    0
      (sequential stages: an ICP-blocked record never reaches verified)

One Grok call returns industry, offices, employees, specialties and description
with source URLs, at $0.20 a domain.

    **$73.80 to attempt the entire blocked estate, all 369 records.**

ContactOut cannot do it - measured, zero. Free webfetch cannot - it produced
weak boilerplate for exactly these records. TASK-192 is measuring verdict
movement on 25 before anything is scaled, and that measurement is the gate on
spending the $73.80.

### AND A FREE FIX WORTH MORE THAN THE PURCHASE

`enrich.outcome()` checks `any(sendable contacts)` and **not** research, not
evidence, not the verdict's basis. So this pipeline pays for contacts before
the evidence that licenses writing to them.

Twenty records reached `verified` with zero usable research - all twenty
holding `icp_pass_with_uncertainty` from ContactOut's structured fields, which
satisfy ICP and carry no prose for a claim to trace to. TASK-197 then failed to
generate copy for fifteen of them, at `persona_angle`, on `check_evidence`.

    ~240 credits already spent on contacts who cannot be written to.

`CLAUDE.md`'s company-first rule was honoured to the letter and defeated in
substance: there IS a verdict, and the verdict is reachable without the prose
the copy gate needs. TASK-205 is adding the precondition using
`research.why()`, which already computes it. **Zero provider credits.** Expect
`verified` and `enriched` counts to FALL when it lands - that is the fix
working, not a regression.

### ONE CORRECTION TO CARRY FORWARD

An earlier version of this file, and a commit message, called a broken
Deliverable parser "the largest recoverable inventory in the system" on
TASK-194's figure of 143 contacts held by insufficient confirmations.

**That figure came from the stale snapshot and is wrong.** TASK-196 measured
it: 159 contacts have no verification evidence at all because they never
entered the waterfall, 81 did enter and all 81 carry `Deliverable=error`, and
68 of those were verified anyway via ContactOut + Reoon. **Exactly one contact
would benefit from a working Deliverable.** The parser was never broken - its
gate had never been opened, because `DELIVERABLE_RESULT_SHAPE` was never set.

A tenth decision for you, therefore: **set `DELIVERABLE_RESULT_SHAPE=confirmed`
or leave it.** The response shape IS known and documented in
`src/providers/deliverable.py`; what the variable actually buys is the
verification waterfall for those 159 contacts at up to 3 credits each. TASK-196
opened that gate in code and it was reverted - documenting a response shape and
accepting a provider's cost are different decisions.

TASK-203 is establishing why the 159 were never offered to the waterfall at
all, which is the same shape as TASK-160's answer about the 250: no runner.

**Three open leads on throughput, all delegated and running:**

- **TASK-190** - how much of geography/company_type is answerable for free: a
  TLD, the MX cache, an existing segment classification, a page already
  crawled. Held to one hard rule: an inference may move a criterion UNKNOWN to
  PASS and **never** to FAIL, because a FAIL is terminal.
- **TASK-193** - company-info *did* return office data for records whose
  geography stayed UNKNOWN. If those offices are outside the include list the
  honest verdict is FAIL, and a FAIL is the cheapest outcome there is:
  terminal, zero person credits, out of a review queue a human would read. We
  may be holding records in review that our own data says to reject.
- **TASK-194** - the end of the pipe nobody examined. 113 qualified, 32
  campaign-ready: 22 never entered person discovery, 24 enriched but not
  verified, and 35 verified records - **all already paid for** - are not ready.
  At a 28% conversion, growing qualified from 113 to 179 is worth nothing.

---

## WHAT DID NOT GET WEAKENED

Stated explicitly because the objective was LIVE and the temptation runs one
way. No gate, threshold, cap, lint rule, sender limit or ICP rule was relaxed.
Nothing was added to `SUPPORTED` or `CONDITIONAL`; verified after every merge -
it still holds the same eight verbs. The `LINKEDIN_ADD_LEAD` reseal is intact.
No approval was set. No record was moved to `dropped`. **No provider write was
performed by Claude all night.** The only provider write of the session was
TASK-158's single lead into unbound list 940797, which is what proved the
schema and can send nothing.

**The PII guard is green** for the first time since it was strengthened - 77
real domains and 107 real names down to zero in the working tree, hashed
consistently with `px-` + SHA-256 over a public salt. 455 tests pass.

Two of my own mistakes, both caught and both worth knowing: I reset a worktree
whose worker was still running and lost TASK-164's commits, recovering them
from the reflog; and I hashed names inside
`tests/test_fixture_hygiene.py`, which is the one file where the real strings
must stay, disabling the detector for about a minute before reverting.
