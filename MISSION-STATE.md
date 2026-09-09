# Overnight mission: what is done, what remains

> **Superseded.** Read `RESUME-CHECKPOINT.md` first. The numbers in this
> file are from an earlier night and are stale: HEAD, the suite counts and
> the Productive state have all moved. What follows is kept for the
> reasoning it records, not for the figures.

## RESUME CHECKPOINT

Read `RESUME-NEXT.md` first if you are a fresh session. It is written for
one and repeats what matters. Then `RELEASE-CANDIDATE.md`, which carries
the three verdicts and tomorrow's runbook.

| | |
| --- | --- |
| HEAD | `1309079`, plus the commit carrying these numbers |
| Git status | clean; untracked: `AGENTS.md` (see below) |
| Full suite | 4,774 tests, OK |
| Offline harness | 4,774 tests, OK - nothing reached off this machine |
| Mutation audit | 392/392 caught |
| Mutation process active | no |
| Source restoration | verified - clean tree |

**`AGENTS.md` is the only intentionally uncommitted file.** It is an
untracked copy of an earlier `CLAUDE.md`, it was not created by these
sessions, and it has been left untracked deliberately in every commit. It
is not work in progress, and it no longer tracks `CLAUDE.md`.

**Last fully completed phase.** Production authentication and the first
live provider reads, reported in `PRODUCTION-AUTH.md` and
`PRODUCTION-TRANSITION.md`. Before it: the demonstration deployment, and
before that the overnight release-candidate mission, reported in
`RELEASE-CANDIDATE.md` and `FINAL-SYSTEM-INTEGRITY-AUDIT.md`.

**The finding that outranks the rest.** Productive has ~160,000 prospects
mid-sequence in 42 live HeyReach campaigns across 39 sender accounts.
Canonical state knows about none of them, so the hygiene check that exists
to prevent a double approach would pass. `PRODUCT-GAPS.md` §15,
`PRODUCTIVE-PILOT-PLAN.md` §1. No Productive contact may be selected until
the exclusivity question is answered.
The build is frozen: correctness, security, tenancy, deployment,
observability and operating documentation are in scope; new product is
not.

**Exact current task.** Nothing in flight. The tree is clean and every
battery is green.

**Exact next step.** One decision, and it is not a task: **how does a
person prove they are who they say they are.** Signing in is a POST of an
email address, which is why an instance holding real client data cannot go
online and why the process now refuses to try. `RESUME-NEXT.md` has the
full statement. Everything else on the list is smaller than it.

The demonstration deployment does not wait on that decision and can be
done tomorrow: `RELEASE-CANDIDATE.md` §8, under an hour, nothing real
touched.

**The phase before this one.** The cadence experimentation mission,
reported in `CADENCE-EXPERIMENTATION-REPORT.md`. An operator can put an
experiment on a campaign, preparing it assigns each account to an arm, the
arm decides what is built and sent, and eight modules measure what
happened - none of which can talk itself into a verdict.

**Tests already written.** `test_cadence_sequence.py`,
`test_cadence_arms.py`, `test_cadence_exposure.py`,
`test_cadence_maturity.py`, `test_cadence_replies.py`,
`test_cadence_value.py`, `test_cadence_safety.py`,
`test_cadence_report.py`, `test_cadence_experiment_authoring.py`,
`test_variant_cadence_end_to_end.py`, `test_campaign_cadence_wiring.py`,
`test_campaign_cadence_sweep.py`, `test_mutation_anchors.py`. All mutated
and proven to bite.

**Known bugs.** None open.

**Owed.** Nothing. The fifty mutations owed at the last checkpoint are in
`tools/mutation_audit.py`, along with forty-nine more.

**Known external dependencies.** Everything in `LIVE-READINESS.md` §"Live
validation required". Nothing in the cadence mission needs a provider:
arms, assignment, exposure and reporting are all local.

**Owed.** Fifty mutations verified by hand and not yet in
`tools/mutation_audit.py`: seven for `cadence.steps_for` /
`validate_steps`, nine for `cadencearms`, ten for
`cadenceexposure`, eight for `cadencematurity` and sixteen for the
campaign wiring sweep.

**Files relevant right now.** `src/cadencearms.py`, `src/cadence.py`,
`src/account.py`, `src/touch.py`, `src/variants.py`,
`CADENCE-EXPERIMENTS.md`.

**Run first after resume.**

```
git status --short
tasklist /FI "IMAGENAME eq python.exe"
py -m unittest tests.test_cadence_arms tests.test_cadence_sequence -q
```

Do not run `unittest discover` and `tests.offline` concurrently. Both bind
loopback and build demo estates, and a web test fails intermittently when
they overlap - diagnosed, not dismissed: it passes alone, as a class, and
in an isolated full suite.

Two corrections to that, from 2026-09-07. It is **not only the
client-report test**: the same failure appeared in
`test_production_auth.AnInvitationBecomesAccessOnlyThroughGoogle`, as a
connection error inside `http.client.HTTPResponse.begin`, so it is a
property of the loopback web tests rather than of one of them. And it
happened in a run with **nothing deliberately concurrent** - the offline
suite had finished long before - so "when they overlap" is a reliable way
to provoke it and not the only way. Treat a lone connection-level error in
a web test as this, and confirm it the way the rule says: alone, as a
class, as a module, and in an isolated full run. All four were clean.

---


Durable state for the master overnight mission, so it can be reconstructed
from the repository rather than from conversation. Updated at each
checkpoint.

**Live sending is disabled and stays disabled.** No provider is called
anywhere in this work.

---

## Done, committed

| commit | what it changed |
| --- | --- |
| `fd5be18` | **Same-domain collapse, at the root.** Five people at one company imported as one company with *zero* contacts: rows 2..N were discarded as duplicates, and `commit` built records from domain and company alone, dropping the parsed contact columns. Strong identity (normalised mailbox, canonical profile URL) now makes a row a person; a name never does. |
| `b5091c7` | **Estate read once per screen.** `store.load()` caches nothing, and three screens parsed the whole queue inside a loop. `campaign_rows` 9.86s -> 0.31s at 30k, `batch_list` 2.48s -> 0.85s. Tests count file reads, not seconds. |
| `f808e57` | **Sidebar and import discoverability.** 40 flat links -> 7 sections, one open; 9 items on screen for an operator, 5 for a viewer. `/upload` had *no* nav entry and nothing linked to it - the only way in was to know the URL. Now a nav entry and the primary dashboard action. |
| `d1771ce` | **Delta discovery.** `discovery.py`: a subtraction, not a search. Seven checks; what cannot be checked is named on every result. |
| `75b7219` | **Client review roundtrip.** `clientreview.py`: canonical columns echoed and compared, ids hashed with the workspace, thirteen statuses, silence never a decision. |
| `a17144c` | **Cohort learning** (`learning.py`) and the **credential sweep widened** from 25 to 42 screens - 17 reachable screens had never been checked for a leaked credential. |
| `74c1f95` | **Discovery reachable.** `/discovery` screen and review CSV export. Removed a demo fixture import from the production API path. |
| `b045d13` | **Rate suppression.** The experiments screen printed `0.0%` from three sends while its own evaluator refuses to judge below thirty. |
| `7f369a9` | **Suppression read per contact.** Seven call sites in per-contact loops. Contacts page 7.47s -> 0.60s, analytics 9.22s -> 1.86s at 30k. `analytics_rows` loaded the set and never passed it. |
| `3f63415` | **Pagination.** 100 rows a page, the window stated, size not widenable from the URL. 46KB and under 0.7s at 30,000 records over HTTP. |
| `82c37be` | **Audience screen.** The §68 funnel. First draft printed "122% of 27". |
| `4ad23b1` | **Segment health.** `eligible_for_splitting` was computed on every qualification run and read by nothing. Surfaced, with examples; no automatic split, because splitting on the wrong axis makes copy wrong rather than dull. |
| `a0510d8` | **The QA claim scan said how much it read.** `recs[:200]`, silent, on the check that runs before approval. |

## Cadence experimentation mission

| commit | what it changed |
| --- | --- |
| `d43f7d1` | Sixteen pilot-hardening guards into the permanent mutation list. 285/285. |
| `0e5eb72` | **The cadence became a property of the campaign.** `cadence.STEPS` was a module constant - seven steps, fixed days, for every campaign in every workspace - so cadence length was not a variable in this system. `steps_for` resolves it; a campaign without one behaves identically, proven by building the whole timeline both ways. Found by its own tests: the first version read `config["cadence"]["steps"]`, and that key holds a string in every real client file. |
| `5f88f02` | **Cadence arms.** Experiment and arm model, deterministic sticky account-level assignment, channel eligibility, and - the part that matters - the arm resolving into the executed step graph. Forty accounts through the same `cadence.build`: four-step arm yields four steps, seven yields seven. Shares renormalise across eligible arms, because otherwise a contact ineligible for two of four lands on the last arm half the time. |

| `1545d23` | **Cadence exposure and censoring.** ASSIGNED / STARTED / IN_PROGRESS / COMPLETED / STOPPED_EARLY, with `censored_by` separating an outcome from a safety stop. A contact assigned to seven steps who replies after three is never reported as having received seven. Found and fixed on the way: `push.mark_pushed` accepted an `at` and half-applied it, so a step recorded the caller's time and its event recorded the wall clock. |
| `f69062b` | **Cadence maturity.** A four-step arm finishes on day twelve and a seven-step arm on day thirty-five; compared on day fifteen the short one wins on a difference that is entirely when somebody looked. Maturity is per arm, the experiment is as mature as its slowest, and time is counted from each contact's own assignment. `comparable` is false until every arm has had its span. |
| `c25648e` | **Engineering guardrails into CLAUDE.md.** How the work is done, not only what the system may do - trace-the-chain, test behaviour not source text, mutation safety, decide-don't-ask for local reversible work. The durable lessons had been living in RESUME-NEXT.md, which is rewritten every mission. |
| `a3e6db5` | **The campaign reaches the send path.** `cadence.build` takes `campaign=` and one call site out of thirty-five passed it, so the campaign's cadence - and every cadence arm - reached one preview screen and nothing else. The approval fingerprint of a four-step and a three-step campaign were identical. Root cause was one-directional membership; `campaigns.by_record` is the missing direction. Uncovered worse: the last gate before a payload was skipping every campaign-level guard, freeze and already-launched included, because nothing ever handed it a campaign. |
| `5dcadfd` | **The rest of the readers.** Plan, QA, funnel, preview, replay, touch history, duplicate scan, coherence, and drafting approval - where a four-step campaign's records could never reach `approved`, so one arm of a four-against-seven experiment could not have run. Three measurement and demo modules deliberately left, named in PRODUCT-GAPS §11. |


## In flight

Nothing. The working tree is clean at `82c37be`; a full mutation audit is
running.

---

| `45eeafc` | **Provider naming + between-steps tests.** `providername.py`. Four tests for a reply arriving between step 1 and step 4, including a colleague stopped by a company-wide removal request. |
| `265f87f` | **Reply alert carries the state the policy produced.** Passed through, never recomputed. |
| `b59b29b` | **Split axes.** How an oversized cohort could be divided, and whether the children would be campaignable. |
| `a9d595c` | **Segment strategy.** What we would say to a segment, labelled a hypothesis. |
| `e1b2c59` | **Operational health.** Every path that fails already recorded its own failure; nothing read them together. `/health` lists them with `retry_safe` and why, and names the two areas it is *not* watching. Settings split: it had grown to ten children and the nav invariant caught it. |
| `0595670` | **The Slack button had no other side.** `interactions.py` verified, deduplicated and applied a click since it was written, and its docstring named the HTTP layer it needed. Nothing built it, so every Approve / Reject button in an approval notification posted to a URL that did not exist. `/slack/interactions` now terminates it: raw body, three headers, `handle()`, its status. It answers 401 without saying which check refused it, 200 for anything past verification so Slack does not redeliver a permanent failure, and drains an over-long body before refusing it - without which the 413 arrived as a connection reset about half the time. |
| `9d56560` | **Evidence stopped ageing the day it was found.** `evidence.make` freezes `freshness_bucket` and `quality` onto the row, and every reader since trusted them - so a fact found in February was still called recent in September. Approval could not catch it: it is a fingerprint of the *text*, and the text does not change when the fact behind it gets old. `recheck` re-derives what time touched and nothing else; the read paths re-age; a draft whose selected evidence has aged out is HELD with an instruction to regenerate. `BACKGROUND` had been computed and read by nothing, so a three-year-old article could lead a cold email on relevance alone. The whole 4,136-test suite passed unchanged when this was added, which is the argument for the new file. |
| `b75e595` | **Weekly refresh.** `refresh.py`: which known accounts are worth spending on again. Staleness is per kind with its own threshold and its own cost read from `enrich.COSTS`; never-researched is marked and sorted apart from stale; four states are excluded before anything is ranked; person credits wait for an explicit ICP verdict; and the priority floor *reduces* an account to its free work rather than dropping it, because a company scores low partly because nothing is known about it. Plans, never spends. Caught while writing it: the ICP verdict lives at `qualification.verdict.icp_status`, and my first version read one level above - which would have blocked every person-level refresh in the estate while looking like a working check. |
| `9dbe380` | **The refresh plan on a screen.** Exclusions became labelled rows rather than counts keyed by a code - the shape the `pages.py` invariant requires, since a template that had to look the sentence up could reach a decision module. |
| `de988bf` | **Revival.** `revival.py`: a timer means re-evaluate, not send. Four verdicts, and NEVER and NOT_YET are deliberately not the same answer. A case needs a new signal, an untouched decision maker, an unused angle or an employment change - because reviving with the angle that already failed is the same campaign with a later date on it. Signals dated before the last touch do not count, nor do ones past the freshness floor, nor engagement signals, which are readings of our own outreach. Three of twelve mutations survived the first pass; each was a fixture that could not tell two rules apart. |
| `6534b0d` | **Revival on a screen**, including the quiet-with-nothing-new queue. Found: removing the permission check inside an API function failed no test, because the route table was refusing the viewer alone. Both gates are pinned now, here and on /refresh. |
| `a81bc99` | **Observation licensing.** `observations.py`: knowing something and being allowed to say it are different questions. A signal never licenses a sentence - it carries a reading, not a citation - and the refusal is explicit rather than by omission, because a system that silently declines to mention something looks exactly like one that never knew it. Four things stay unspoken with their own reasons; `may_call_it_now` is carried apart from `allowed`, because "recent" is itself a claim. Ten mutations, all caught first pass. |
| `a4efadb` | **Cross-tenant tests for the three new aggregate screens**, asserted on the counts rather than the page, plus `LIVE-READINESS.md`: one strict class per capability, and sending is BLOCKING by construction rather than by a flag. |
| `8331307` | **Final validation.** Full suite and offline harness at 4278 tests. Mutation audit run twice: 239/239 on the list as it stood, which covered nothing written tonight, then 27 entries added for tonight's guards and 266/266. One guard deliberately left out with the reason written beside the list: it is caught three runs in five, and a flaky entry teaches people to skim past a red line. |
| `970aab5` | **Every screen swept for Python that leaked into it.** Found the defect in the sweep itself: the smoke test's screen list was hand-written, so the three screens added tonight had never joined it. Derived from the navigation now, and asserted. |
| `8a31fd5` | **The §35 sweeps.** One stale TODO in `lint.py` claiming a guard was missing that has existed for some time. And `stepstate` - the step state machine, named by `DATABASE-MIGRATION.md` as the status column's vocabulary - referenced by nothing in `src/`: both guards that need "is this step final" spelled it out as `== "pushed"`, so a `confirmed` or `cancelled` step answered "not sent yet". Latent, not live; `confirmed` is what a provider callback would write. Final: 4286 tests, offline clean, 269/269 mutations caught. |
| `633b895` | Handoff document corrected to name the right commit. |
| `d3a10ed` | **Confirmed cross-channel history in the context pack.** Confirmed and planned are two collections, not one list with a flag; the boundary raises rather than filters; the actor is read off the event, so Mark stays Mark after the account is reassigned to Anna. Plus `pilotpath.py`: 29 stages, each naming its canonical state, idempotency key, tenancy boundary and test modules, with a test that every named module exists. |
| `e05a256` | **Fifteen lifecycle attacks** - all already held; every first-run failure was my harness. Plus `killswitch.py` (six layers, most restrictive wins, default off, cannot turn anything on) and `pilotcaps.py` (ceilings a configuration cannot raise; refused rather than trimmed; pilot mode defaults *on*). |
| `6389cba` | **The variant never reached the event.** `account.touches` read `variant_id` off events nothing wrote it to, so every experiment reported INSUFFICIENT_DATA forever - indistinguishable from an evaluator waiting for volume. `mark_pushed` now records the copy as sent. The other half is named rather than built: nothing calls `apply_to_step`, and a test asserts that gap in both directions. |

## The provider/Slack requirement, audited

| § | classification | evidence |
| --- | --- | --- |
| §20 provider naming | **built** | `providername.py`, 19 tests. No creation call site exists - `bison`/`heyreach` expose lead-adding only - so the name is surfaced as what to call the campaign when a person creates it. |
| §21 Slack ordering | **already correct** | `apply_reply` runs before `_announce`; the notification cannot raise; `notification_id` is idempotent per workspace; ambiguous client resolution announces nowhere. |
| §21 alert content | **completed** | The alert now carries the account state the policy produced and the next action, passed through rather than recomputed. |
| §22 tag sync | **complete, do not rebuild** | `tagsync.py`: 12 tags, provider-id-first identity, outbox with retry, `send()` refuses unconditionally. Tested by name, including that a provider failure cannot touch canonical state and an outbox failure cannot unwind a reply. |
| §5 account-aware reply | **already correct** | `apply_reply` decides per contact, per other DMs, per account, and `_activate_referred` handles referrals. |

`LIVE CONTRACT VALIDATION REQUIRED` for: whether either provider accepts
custom campaign metadata, and whether either accepts the tag writes the
outbox has been holding.

---

## Remaining, in dependency order

### 1. Large-audience scale - DONE and measured

Fixed: `campaign_rows`, `batch_list`, `signals.index`, the per-contact
suppression read, and pagination on the two list screens that can reach
30,000 rows.

Measured at 30,000 records, served over HTTP:

    /companies      0.42s   46 KB   100 rows
    /contacts       0.66s   41 KB   100 rows
    analytics rows  1.86s   (was 9.22s)
    search          0.33s

**The `priority.assess` cost recorded here earlier was wrong** - an
extrapolation written down as a measurement. Scoring is ~0.3ms per
account and was never the bottleneck; the suppression read was.

Remaining and honest: `search` is a linear scan without an index, and the
campaign/outreach screens are not paginated because they are scoped to one
campaign rather than to the estate.

### 2. Audience intelligence - PARTLY DONE

`/audience` shows the §68 funnel and the distributions. Company
dimensions exist in `segments`, provenance in `signals`.

**§20's staged enrichment ladder already exists.** Audited rather than
assumed, and it is in three places:

- `qualify.py` - `STAGES` runs normalise -> dedupe -> suppress -> classify
  -> score -> segment -> route -> plan, and then **stops**. Its docstring
  names the stop as the point: person enrichment is the first genuinely
  expensive operation and is the last thing the module does not do.
- `dmplan.may_enrich` - the single gate. A rejected company is refused
  permanently; a human "reject" outranks a qualified verdict; review and
  unknown are gated on explicit policy.
- `waterfall.STAGES` - provider escalation per stage, where a second
  provider requires a named reason the first failed.

Building a new ladder would have duplicated all three. Nothing to do here
beyond what is already committed.

### 3. Micro-segmentation (§13, §14, §22-30) - DONE

The segments screen now answers three questions for an oversized cohort:

1. **Is it too broad?** `eligible_for_splitting`, which `campaignseg` had
   computed on every qualification run and nothing read.
2. **How could it be divided?** Split axes with known-data shares and
   viable-child counts. Two refusals kept distinguishable - "we do not
   know this" and "they are all the same" are different facts.
3. **What would we say to it?** Primary pain, personas, playbooks, and a
   confidence in words rather than a score.

Explainable membership (§27) was already `campaignseg.why_together`.
Hierarchy (§26) was already `segment_tree` plus the merge ladder.

Nothing splits automatically and there is no control that does: a test
asserts the proposal carries no `apply` or `campaign_ids` key.

### 3b. Long cadences (§16) - ALREADY DONE

Audited, not built. `cadencegraph.node(phase=...)` labels a node, nodes
inherit the previous node's phase, and `phases_of` returns the groups.
`pages._cadence_phases` renders one collapsible block per phase with the
first open, and its docstring already had the reasoning: *"A long cadence
is read phase by phase - what happens after the connection request is a
question about a phase, not about node 14."*

The `account_multichannel` template is **39 nodes across 7 phases**:
initial outreach, LinkedIn connection, multichannel follow-up, second
sender, secondary decision maker, re-engagement, close. §16 asks for
20-40+ nodes without a giant list; that is what exists.

### 3c. Workflow states (§51) - ALREADY DONE

`jobs.STATUSES` covers queued, running, completed, **completed_with_holds**
(§51's PARTIAL), failed and cancelled. A job tracks `processed` and
`failed` separately, so a failure reports what succeeded, and work is
resumable per record rather than per batch. `MAX_FAILURE_RATE` stops a
batch that is failing systematically rather than letting it grind
through: "one bad record must not kill a batch; five hundred bad records
is not a batch with a problem in it, it is a problem with the batch".

### 3d. Observability (§50) - GENUINELY THIN

`observability.count` exists with a persisted counter file, and has **9
call sites**, all Slack and webhook. §50 also asks for import,
enrichment, provider-contract, reply-ingestion, tag-sync, worker and
scheduler failures.

This is a real gap rather than an audit finding. It is deliberately not
urgent: every one of those paths already records its failure in canonical
state - a failed job carries its count, the tag outbox carries
`last_error`, a refused notification carries its reason - so nothing is
*lost*. What is missing is one place to read them together.

### 4. Message-time context and every-step personalization (§32-52)

**Audited: claims are enforced at QA, not at generation.** `generate.py`
never imports `outreachclaims`. The generator writes copy and
`campaignqa` refuses what is not licensed, before approval. That is a
deliberate split and it means the generator does not need rebuilding to
satisfy §37-39 - the enforcement point already exists and already works.

What that audit found instead was a silent cap in the claim scan, fixed
in `a0510d8`. A sweep for the same shape across every `for x in list[:N]`
in the codebase found nine more, all benign: "top three reasons" displays,
or previews that already report `shown` beside the total.

Still genuinely missing:

- **Message-time rebuild.** Context is assembled when a campaign is built,
  not before each step. §27 and §36 want the pack refreshed at the moment
  a message is prepared, so a reply or a DNC between step 1 and step 4
  changes what step 4 may say.
- **Cross-channel history in the pack.** `account.touches` and
  `outreachclaims` both know it; `contextpack` does not carry it.
- ~~**A claim type for observations.**~~ Done: `observations.py` and
  `ACCOUNT-INTELLIGENCE.md` §7. A separate module rather than an eighth
  `outreachclaims` type, because that module's split - claims about *us*
  against our own event log - is the thing that makes it readable, and an
  observation is a claim about *them*.

### 5. Weekly refresh (§49, §55, §72, §92) - selection DONE

`refresh.py` decides what a run would do and what it would cost, and
`DISCOVERY.md` §4 documents it. Still true, and still deliberate:
nothing runs on a timer. "Weekly" describes intent; a run happens when
somebody asks for one.

### 6. Revival (§96-101) - DONE

`revival.py` and `ACCOUNT-OUTREACH.md` §12. Verdicts only; nothing is
sent, drafted or queued, and a READY account goes through every gate a
first approach goes through.

### 7. Reporting additions (§106-115)

Discovery funnel and source performance.

---

## Intentionally deferred, with reasons

- **Live discovery provider.** `LIVE DISCOVERY PROVIDER REQUIRED`. Every
  candidate is a fixture or manual entry and says so.
- **CRM connector.** `LIVE CRM CONNECTOR REQUIRED`. Named on every delta
  result, because a delta without it is wrong rather than smaller.
- **Agency DNC at discovery time.** Person-level index; a candidate is a
  domain with nobody attached. Enforced at `hygiene` instead.
- **Signal retraction.** Append-only with no withdraw path. The fix is a
  retraction row, not a delete.
- **Score history.** Answers "now", cannot answer "why was it 92 in
  October".

---

## What tonight actually demonstrated

Nine of the eleven real defects were **invisible to a green suite** of
4,000+ tests. They needed: a realistic CSV, a 30,000-record estate, a
browser, an HTTP response header, and the mutation audit. Two of them were
my own hollow tests, asserting something other than what they claimed.

That is the argument for the parts of this mission that are not "write
more tests".
