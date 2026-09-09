# Resume checkpoint

## Read this first: both canaries are resolved, and LinkedIn is the one to run

EmailBison Productive tenancy is **GREEN** as of 2026-09-09. Verified in a
fresh process with the environment scrubbed: `BISON_KEY` is the consumed
variable, `require_workspace(10)` passes, `require_workspace(29)` raises, the
inventory walks to **225 unique Productive inboxes** across 86 Productive-branded
domains with no Bluewave leakage, and the binding was re-asserted after the
sweep. `work/senders.jsonl` rebuilt: **202 READY, 23 DEGRADED, 3,030 sends/day**.
No EmailBison UI action is outstanding.

**The recommendation is the LinkedIn connection request to Dana Marsh, and
the reason is that the email lane cannot produce a first message.**

| | EMAIL CANARY | LINKEDIN CANARY |
| --- | --- | --- |
| prospect | Dana Marsh, Head of Production, Ninefields | same |
| account ICP | qualified 53.0, tier C, confidence medium | same |
| persona / angle | champion / operations | champion / operations |
| address / profile | `dana@ninefields.test` | `danamarsh` |
| verification | 2/2, contactout + reoon, sendable | n/a |
| MX | `known_allowed`, microsoft, eligible | n/a |
| prior contact, person | **CLEAR** (EmailBison ws 10) | **CLEAR** (12 conversations scanned) |
| prior contact, account | **TOUCHED** - a colleague got 9 emails on campaigns 328 and 352, both ended, 0 replies | company-level **UNANSWERABLE** (PRODUCT-GAPS 35b) |
| first step | day1 email | day3 connection request |
| **is the first step renderable** | **NO - day1 is LLM-generated and no model ships** | **YES** |
| copy | day5 onward render CLEAN; day1 and day15 cannot | 125 chars, lint CLEAN, claims CLEAN |
| sender | 202 ready inboxes, 3,030/day | seat 116968 Mina Ruzicic, READY, 40 requests left |
| vehicle | exists and is proven | **must be created in the HeyReach UI** (no create route in this build) |
| blocking | the first message does not exist | one UI action |

**Why LinkedIn wins.** The email cadence opens with day1, which is generated
and needs a model this repository does not ship. Starting at day5 instead means
the first thing a prospect receives is a mid-sequence follow-up. The LinkedIn
note is the cadence's own first step, it renders, and it asserts nothing.

**What the day-5 email would have said until today.** `you are running
utilisation at Ninefields` - a fabricated claim about how somebody runs their
agency, and the only email text this system could ever have sent, because the
evidence branch it prefers has never once had anything to read. Both guards
passed it. Fixed and pinned; PRODUCT-GAPS 36.

**The other thing real execution surfaced.** The new HeyReach-side
prior-contact check found seat 208242 already four messages deep with Austin
Ball and with Anthony Andreatos - the latter **five days ago**. Those were the
primary contacts at the other two qualified accounts. PRODUCT-GAPS 35.

**Three candidates at ninefields.test, all clear on both channels:** Dana Marsh,
Dale Morgan, and Russell Garnaut (capped out, not blocking).

Written for a session with no memory of how any of this came to be. Read this
first, then PRODUCT-GAPS.md and HUMAN-ACTIONS-REQUIRED.md, which are the two
that stop a claim being made in front of a client.

## Where the tree is

| | |
| --- | --- |
| HEAD | the commit carrying this file |
| Git status | clean; untracked `AGENTS.md` only, deliberate, never committed |
| Live sending | OFF, refused in code - `push.run(live=True)` raises `LiveSendNotEnabled`, **and `prototype/bin/push.py` no longer sends either** |
| Suite | 6,530 tests, green, and green network-blocked. Verified 2026-09-09 |

## Read this first: the canary is three human decisions away, not any code

The funnel was run for real. 43 ContactOut credits over the cohort, then a
re-score:

| | before | after |
| --- | --- | --- |
| qualified | 3 | 3 |
| review | 9 | 12 |
| unknown | 38 | **27** |
| rejected | 0 | **8** |
| people selected | 3 | **7** |
| verified / sendable | 0 | **4** |

Eleven unknowns resolved on evidence. The first verified contacts in the
estate: four at `ninefields.test`, every one 2 of 2 confirmations, sendable, with
a LinkedIn profile, and three of the four collision-clear.

**Everything technical for a canary is now in place. Three things are not, and
all three are decisions rather than engineering.**

**1. The prospect: a targeting decision.** `ninefields.test` is qualified at 53.0
and only `touched` rather than in-sequence. Its four contacts are verified,
sendable and LinkedIn-ready. All four titles - Head of Production, Design
Studio Manager, Project Director, Design Director - fail Productive's declared
persona lists, so `personas.select` excludes every one. Simulated in memory:
accept those titles and all four render a day-3 LinkedIn note that is CLEAN on
lint and claims, 124-126 characters against a 300 limit. The copy, the
verification and the collision are already good. Widening a client's own
persona definition to make a contact pass is not ours to do - HUMAN-ACTIONS-
REQUIRED 5.

**2. The vehicle: a campaign decision.** All 17 non-finished HeyReach campaigns
were classified against their real sequence graphs, the first ever read from
this repository. 11 refused for `SEND_LEAD_TO_BISON`; 5 refused for an
unrecognised `INMAIL` node, failing closed; **2 provably LinkedIn-only**.

  - **524002** - the only one both RUNNING and LinkedIn-only, and every one of
    its 33 senders is inside the attested 33. One hazard, and it decides the
    matter: **its connection request carries no note at all**, so our rendered
    copy would never reach the prospect. A push here sends a bare invite.
  - **524026** - LinkedIn-only and its request does carry a note, but DRAFT,
    and it includes two seats outside the attested 33 (129531, 194061).
  - **567683** - single-sender on the proposed canary seat 116968, clean, no
    hazards. FINISHED, so it may not action a new lead.

So the vehicle is a choice between using a note-less running campaign, starting
a draft after removing two unattested seats, or creating a dedicated
single-sender campaign - which is a live provider mutation.

**3. The other qualified accounts are not available.** The
`qualified x collision-clear` cell is empty. Both other qualified accounts have
someone mid-sequence in the client's own campaigns right now.

## The cohort was already being worked

`GET /leads?search=` over the Productive workspace, read-only, all fifty pilot
accounts: **8 clear, 21 touched, 20 with somebody in sequence right now**, 1
unresolvable. The two contacts picked for the one-person canary had received 21
emails and 4 emails from the client's own campaigns; the second was
`in_sequence` at the moment it was checked.

`work/queue.jsonl` said zero confirmed touches for both and was right about what
THIS system had done. The client's estate has worked the same list since April:
dozens of campaigns, a few active, hundreds of inboxes, a six-figure send
volume and a five-figure lead list
loaded.

**So there is no safe canary candidate today, and it is a data conclusion
rather than a code blocker.** All three qualified accounts are touched or
in-sequence; the eight clear accounts have no discovered people. The best
candidate is the one clear account at `review` 38.0 - one ContactOut credit
takes it to `qualified` 51.0, and person discovery is ten more.

`src/collision.py` is the check, and the query is the hard part: `?email=`,
`?filter[email]=` and `?q=` are all ignored and return the whole five-figure lead
estate, and `?search=` breaks on a term containing a dot - returning the same
a five-figure row count rows for an account with no leads at all. So the bare label is searched,
the address matched locally, and a broad-looking response raises rather than
answering. On the first sweep that guard refused 7 accounts a naive check would
have called clear. PRODUCT-GAPS 32.

**What is still missing on this front:** there is no HeyReach-side
prior-contact check, and a live campaign is HeyReach-fed, so the LinkedIn lane can
collide with nothing detecting it. And nothing on the send path calls
`collision` yet - deliberately: it belongs at the JIT check immediately before
an external mutation, not at planning time hours earlier.

## The provider inventories, reconciled

| | operator said | API reconciled |
| --- | --- | --- |
| EmailBison inboxes | 225 | **225. Match.** All Connected, 86 Productive-branded domains, 0 Greenfield |
| HeyReach seats | 33 approved | **41 total, 33 `authIsValid AND isActive`. Match.** 32 approved after excluding the one seat carrying a `productive.test` address |

**Why the first read said 15 inboxes.** `meta.per_page` 15, `meta.last_page`
15. Fifteen was the page size, and the read looked at `data` and never at the
envelope. `bison.sender_emails` now walks every page and raises
`PartialInventory` rather than returning a short list. An inventory is what
capacity is planned against, so a short read does not look like a failure - it
looks like a small estate.

`work/senders.jsonl` is rebuilt from provider truth on both channels: **225
inboxes (202 ready, 23 degraded, 3,030/day)** and **32 seats (29 ready, 3
degraded, 1,160 connection requests/day, 970 left today)**. The fixture
`productive.test` addresses and the `bison-1..64` / `4002-4005` ids are gone.
Every row has `sender_id: None`, which is honest - neither provider knows who
owns an inbox - and it means `heyreach._account_id_for` still degrades to
account `0` rather than refusing. PRODUCT-GAPS 33d.

Proposed canary seat, deterministic (fewest active campaigns, then lowest id,
READY only): **116968**, 8 active campaigns, 40 connection requests available.

## Read this too: the send claim was false, and is now true

`prototype/bin/push.py --live` did a real `requests.post` to
`campaign/AddLeadsToCampaignV2` and to EmailBison, with no eligibility,
approval, killswitch, cap, fatigue, sequence or suppression check, and then
rewrote `work/queue.jsonl` outside `src/store.py`. It needed an API key in the
environment and a flag. `out/heyreach.csv` still holds three real prospects
staged for it.

Three documents rested on "there is no code path to either provider" -
`LIVE-READINESS.md` section 3, `RELEASE-CANDIDATE.md`'s NO-GO, and blocker 5
below. All three were derived by reading `src/`, and `prototype/` was outside
every audit that established the claim. The one test that mentions the
directory puts it explicitly out of scope - an exclusion written for fixture
naming that quietly became an exclusion for the safety audit.

Refused now, on all four paths, with `tests/test_the_prototype_cannot_send.py`.
The sweep it prompted is finished: `prototype/bin/check.py` and `verify.py` can
spend Reoon credits outside the ledger, neither can send, and neither was
disabled - they are manual tools. **The corrected claim is "nothing in `src/`
or `prototype/` can reach a prospect", and it should be written that way
wherever the old one appears.** PRODUCT-GAPS 28.

## What this session did, newest first

Six commits. The pattern to carry forward is not any single fix: it is that
**four of the six defects were invisible to a green suite and visible on the
first contact with real data or a real wire**.

| what | how it was found |
| --- | --- |
| The prototype could send | tracing an unrelated HeyReach question |
| Blitz sent the wrong request field name, so every call would have failed | one metered call |
| Blitz read `employees` where the wire says `employees_on_linkedin` | the same call |
| 25 credits a run re-buying company facts already on the record | running the new planner over `work/queue.jsonl` |
| `waterfall.STAGES` declared an order nothing executed | building a consumer for it |
| A contact-less verdict had overwritten paid negative evidence | reading the event log |

### Verification evidence, restored at zero credits

Two addresses at `brightpath.test` read `state: unknown`, `evidence: []`
while their own event log held eight `verification_result` events and seven
`email_verification` waterfall rows. A batch run hit its budget ceiling,
emitted a `verification_result` carrying `contact: null` and `state: unknown`,
and that contact-less verdict landed on contacts that did have evidence.

The direction is what mattered: `accept_all_uncleared` means "do not send",
`unknown` means "ask again", so the loss converted a refusal into an
instruction to re-buy - and the ledger shows the re-buy had already happened
once, at 13:27 then 15:17.

`src/evidencerepair.py` restores it from the record's own append-only log.
Only `provider_call_completed` rows with `operation == "verify"` are read, and
only their provider, status and timestamp; no prose is parsed and no provider
field is invented, so the recomputed reason is deliberately less specific than
the one originally logged. The verdict is recomputed by `verification.decide`,
never copied - a test feeds a log whose recorded state says `verified` and
proves the evidence still wins.

**Measured on the real record, with the module's own predicates: a re-verify
called ContactOut, Deliverable and Reoon for 4 chargeable credits before, and
calls Deliverable alone for 0 after.** Deliverable is correctly still retried -
an error is not an answer - and costs nothing while `require_contract` refuses
pre-HTTP.

### The waterfall routes per field now

`enrich.usable_contacts` asked "does this contact have an email" and that
answer gated all person-level work, so somebody with an address and no
LinkedIn URL read as finished. `src/fieldplan.py` gives each field its own
state and its own next step, routed from `waterfall.STAGES` - which finally
has a consumer. Every stage now reads ContactOut -> Blitz -> AI Ark, and
`linkedin_url` has the Blitz rung it never had. `enrich.plan` and
`enrich_record` share one predicate rather than two that agree today.

PRODUCT-GAPS 29 has the four things it exposed and did not close. The one to
know: **the waterfall ledger has no `contact` column**, so a per-person Blitz
call cannot be attributed. Costless today because none has a call site; it must
be closed before one does.

### Blitz: one record, three defects, and a contract still one-eighth known

See PRODUCT-GAPS 30. The operative conclusion is the last line of it: **a Blitz
call for real client data is not yet safe.** One request field name was wrong,
so the other six are suspect rather than merely unproven - and a deliberately
empty request body returns 422 naming the field it expected, at zero records,
which is how the first one was found. Six routes could be confirmed for free
that way.

### A LinkedIn-only predicate exists, with no subject

`heyreach.linkedin_only` is an allowlist over the node types a sequence
actually reaches, failing closed on anything it cannot classify, and
`push.payloads` carries its verdict instead of discarding it. **It has never
been run against a real graph, because no recorded HeyReach sequence exists
anywhere in this repository.** The next action is a read, not a write:
`python -m src.mapping list --provider heyreach`, then
`--sequence <id>` per candidate, persisted under `work/`. PRODUCT-GAPS 31.

### Two contaminated state files now say so

`work/report-drafts.jsonl` (4,944 rows, every one `created_by: a@b.test`) and
`work/replywatch.json` were deliberately **not** cleared - that is a
destructive write to client state. `src/contamination.py` registers them with
what may not be concluded from each, and `python -m src.check` fails while
either stands. Clearing them remains a human decision.

## The 2026-09-09 machine restart

The machine restarted unexpectedly with `tools/mutation_audit.py` mid-run.
**Nothing was lost and nothing needs reconciling**, and the useful part is how
that was established rather than that it was.

| question | answer, and how it was settled |
| --- | --- |
| Was mutated source committed? | No. `git diff HEAD` empty, no `.orig`/`.bak`/mutant residue. The `src/` mtimes of 03:38-03:41 are the audit restoring files, which is the outcome the rule in CLAUDE.md exists to produce |
| Was a provider call in flight? | No. Last audited action is `batch.committed` 2026-09-07T18:54:58Z with nothing after it; both pollers unconfigured; `work/checkpoints.json` unmoved since 2026-08-26. The interrupted processes were a mutation audit and a test run, neither of which touches a provider |
| Did canonical state drift? | No. The funnel re-derived from `work/queue.jsonl` is 3 QUALIFIED / 9 REVIEW / 38 UNKNOWN with 3 contacts at `verdict: null` - identical to what this file already claimed |
| Is the mutation number still true? | **UNKNOWN.** 546/549 was interrupted and is not carried forward as a pass |

**Python is not on PATH after the restart.** The interpreter is at
`%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe` (registered in
`HKCU\SOFTWARE\Python\PythonCore`, 3.14.3). A fresh shell will report
"Python was not found" and offer the Microsoft Store shim, which is not it.

### What the restart audit found, which is the part that matters

**The second barrier covered one file out of twenty-odd.** Fixed in
`a191a2a`. `_refuse_production_write` was called only from the queue writer
while its docstring claimed "every state write ... the only path that
matters". Found by diffing `work/` against a backup across a suite run: the
run had added sixteen `a@b.test` draft rows to the real
`work/report-drafts.jsonl`, where 4,944 had accumulated at sixteen per run
since 2026-08-28, and `work/replywatch.json` held `RuntimeError: still on
fire` from `tests/test_replywatch.py:305`.

The queue was never at risk, because the queue was the only file behind the
guard. The two barriers are meant to be independent, and one covering a
twenty-second of the other is not independence.

**It had already cost something.** PRODUCT-GAPS 22 item 9 cited
`work/replywatch.json` as evidence that reply detection is down. The
conclusion happens to be true, but a red team had read test fixtures as a
production signal. That item is now marked corrected.

`write_jsonl` now asks, covering campaigns, drafts, senders, signals and the
tag outbox; `mx`, `poller` and `replywatch` build their own
temp-file-and-replace and each asks for itself. **Proof it is consumed rather
than merely present: `work/` is byte-identical before and after a full
6,417-test run, and again across the offline run** - where the same run
previously added sixteen rows. Each of the five call sites was attacked
individually and each intended test went red for the intended reason.

Two tests were wrong rather than the code. `tests/test_report_editor.py` had
four classes creating real drafts with no isolation, beside `WebTest` classes
that always had it; they now get a throwaway directory. And
`test_the_bare_write_is_private` searched function source for the substring
`_write(`, which `refuse_production_write(` contains, so it reported that
`write_jsonl` "writes without the lock" - a function that does not call
`_write` at all. It now asserts over the parsed call graph, and checks that it
examined at least one writer rather than silently none.

**Two files still hold fixture data and were deliberately not cleared.**
`work/report-drafts.jsonl` is 4,944 rows of which every single one carries
`created_by: a@b.test` - there is no genuine client draft in it - and
`work/replywatch.json` is a mix of real-looking poller rows and test errors.
Clearing them is a destructive write to client state and is a human decision;
until it is taken, nothing in either should be quoted as evidence. Copies of
both are in this session's scratchpad.

**Three read-only audits ran alongside** - provider waterfall, canary send
path, Productive artefacts. Twelve findings are recorded in **PRODUCT-GAPS
section 27**. The two to know before anything else:

1. **27a is a spend item.** On `brightpath-com`, paid *negative*
   verification evidence was overwritten by `unknown`. Seven
   `email_verification` waterfall rows and eight `accept_all_uncleared`
   events survive, but both contacts now read `state: unknown, cost: 0,
   evidence: []`. The 13:27 -> 15:17 pair shows the re-buy already happened
   once, and a third is guaranteed if anything re-verifies. The loss predates
   `store.refuse_evidence_loss` by two and a half hours, so it is not a hole
   in that guard - but **the verdict is recoverable from the append-only
   event log at zero credits**, and that repair has not been attempted here.
2. **27c blocks the standing direction.** The waterfall is not field-aware:
   every gate tests `usable_contacts`, an email-presence test, so "ContactOut
   missed the LinkedIn URL" cannot be expressed at all. Field-aware routing is
   the prerequisite for the Blitz rung, not a refinement of it. And 27b: the
   ordered table `waterfall.STAGES` routes nothing - the executed order is the
   statement order inside `enrich.enrich_record`.


### The 2026-09-08/09 overnight run, newest first

Eleven commits. Every one of them closed the same defect in a different
place - **a safety check computed correctly that nothing downstream read** -
so that pattern is the thing to carry forward rather than the individual
fixes.

| what | where it was | what it is now |
| --- | --- | --- |
| Reply checkpoint keyed by provider alone | a mark earned in one EmailBison workspace silenced replies in another, invisibly | scoped per workspace; `GET /api/users` states the binding and `poller.run` refuses a mismatch |
| `sequence_hazards` | called by nothing but its own test | `push.payloads` *can* refuse a campaign whose copy it cannot render - but **no caller arms it.** All four callers pass no `heyreach_sequence`, so the gate is still unreachable. Corrected 2026-09-09; see PRODUCT-GAPS 27h |
| `killswitch` | one importer, and only to describe a setting | reported by `push.run`; `require()` is the enforcing form, for the sender that does not exist yet |
| `pilotcaps` | no importer at all | reported by `push.run`; same staging |
| `fatigue.account_check` | enforced by `revival` and `oooreturn`, ignored by the path that sends most | `eligibility.decide` holds on it, before any content work |
| `events.pause_company` | dead, with a docstring claiming a caller | deleted; `accountpolicy._hold_account` is canonical |
| BlitzAPI | absent | declared behind ContactOut, no call site, fixture-only |

**Two defects were mine, introduced the same night and found the same night.**
The evidence guard keyed provider answers on their timestamp, so re-stamping
the same answer read as deletion - one intermittent failure in 6,380 tests,
and a false positive on a safety guard is the shortest path to somebody
weakening it. And `supplied_field_names` merged each row over a probe, so a
lead missing a personalisation field still reported one. Both are fixed, both
have attacks pinning them, and neither was found by the suite: the first by
diagnosing an intermittent rather than re-running it, the second by
`tests/test_red_team_tonights_guards.py`, which exists to attack the guards
added that night.

## Validation

| | |
| --- | --- |
| Full suite | **6,410 tests OK** at `decb401` |
| Offline / network-blocked | **6,410 tests OK, nothing reached off this machine.** Six socket entry points blocked; loopback permitted because the web tests drive a real server on an ephemeral port |
| Mutation audit | 546/549 at `0295567`; the three misses were closed in `ac55184` |
| `work/` integrity | 50 Productive records, 0 identity problems |

**The suite went 80 failures -> 0, and the categorisation is the useful part.**
Nothing was papered over and no invariant needed relocating:

| cause | count | category |
| --- | --- | --- |
| identity invariant in `store.validate` | **0** | it caused nothing |
| evidence guard, in fixture builders | 18 | legitimate invariant exposing bad fixture state |
| LinkedIn angle guard | 1 | same |
| downstream cascade from the above | 61 | test coupling |
| genuine production regression | **0** | |

The cascade is worth understanding because it will happen again.
`ProviderTest.setUp` replaces `urllib.request.urlopen` with a network tripwire
and restores it only in `tearDown` - which `unittest` never calls when a
`setUp` raises. Forty-two classes extend it, so one failing fixture left the
tripwire installed for the whole process, and self-perpetuated: the next
`setUp` captured `_forbidden` as "the original". `test_slack_route` posts with
`urlopen` (15 failures) and `src/web/oidc.py` fetches discovery and token with
it (48), which is exactly the 63. The evidence guard was only the trigger.

## What `4546712` changed

Six defects, each one a value the system computed correctly and a consumer
that disagreed with it. None could send anything; four told a person
something untrue. Every test was proven red first, and the two guards proven
to fail when the guard is removed.

- **An upload preview committed into whichever workspace you were in.**
  `/upload/commit` keyed the parsed batch by session token and re-resolved
  `repo`, so parse in one workspace, switch, commit, and the rows landed in
  the other - merged against its records, stamped with its client, hygiene-
  and suppression-checked against neither. Reproduced before the fix: two
  domains landed in Bravo from Alpha's preview. Guard is in `upload.commit`.
- **The contact outreach screen discarded the eligibility verdict.**
  `api.outreach` emits `status`/`eligible`/`eligibility_reasons`; its only
  reader asked for `state`/`would_send`/`why`. Engine said
  eligible/unapproved/eligible/waiting/eligible/eligible/eligible; screen said
  `planned` seven times. Nothing had ever tested that function.
- **A contact who said "not interested" rendered ENGAGED, in green.**
  `_contact_state` never read `contact["stopped"]`. `eligibility` reads it and
  refuses correctly - only the display disagreed. `fatigue` now counts
  STOPPED so `account.max_active_contacts` sees the same population: a
  display fix does not relax a volume cap.
- **`render_draft` wrote report history on a GET at viewer permission.** Now
  asks `repo.require(REPORTING_EXPORT)` at the service. The route prefix is
  deliberately untouched.
- **`/reporting` appended the operator breakdown for a client**, including
  "a reply here came from a rehearsal, not from a mailbox".
- **Client PDFs printed `Out_Of_Office` and `Account_Do_Not_Contact`.**
  `str(k).title()` keeps the underscore. Fixing it exposed the reverse bug -
  `_humanise` passes single words through, so `positive` went lowercase.
  The canary is planted, not hoped for: the demo estate's only classification
  is `positive`, so a test that merely rendered the demo report passed against
  the broken code. Vendor canary widened to `monthly`, previously untested.

Also: `_audience_breakdowns` ended `or rows`, so a campaign filter matching
nothing widened the report to the whole workspace under a campaign heading.

Twelve further findings are recorded in **PRODUCT-GAPS.md section 21** rather
than fixed. The one to know about before any send path is built: nothing
refuses a contact with no sender assignment. `push._sender_of` says the launch
checklist refuses it; `senders.check_mapping` reads `campaign["senders"]` and
never looks at a contact. `heyreach._account_id_for` then falls back to
account id `0`. Inert today, and deliberately not closed ahead of the send
path it belongs with.

## THE INCIDENT - read this first

On 2026-09-08 the real Productive queue was destroyed by a test.

`tests/base.py::ProviderTest` isolated the network and the credentials and
left the store pointing wherever it already pointed. `store.save` replaces the
whole file rather than appending. So
`tests/test_signals.py::TheEstateWalksReadTheSignalFileOnce`, which inherits
that base class, wrote twenty-five `walk-N` fixtures over fifty real records.
The module docstring of `tests/base.py` had promised "every test runs against
a throwaway queue file" since before the incident. It was not true.

Reproduced deterministically: plant a three-record queue, run that one class,
get back fifty fixture rows.

**Loss window**, from timestamps: `batch.committed` 2026-09-07T18:54:58Z,
newest real export Sep 7 23:45 local, first fixture snapshot Sep 8 10:35.

**Two barriers now**, deliberately independent. `0835ead` gives `ProviderTest`
its throwaway directory - the known way in. `87c95fe` makes `store` refuse any
write to the real `work/` while `unittest` is loaded - the class of way in.
The second does not depend on any test remembering anything, because the thing
being prevented is a forgotten setup step. `tests/test_tests_cannot_write_client_state.py`
reproduces the incident and proves each barrier fires alone.

**What was permanently lost.** `waterfall` and `events` are fields *on the
record*, so the spend ledger and the event log died with the queue and cannot
be reconstructed from any log. Gone: 47 original ICP verdicts, all
verification evidence, the genuine 94-credit ledger, every per-record event
log, 13 of 16 discovered people, and summit-usa.test's 18
collision-excluded people.

**Recovery is exhausted.** Six independent read-only agents searched git (all
965 trees, all 1,660 blobs, fsck, stash, reflog), 1.2GB of temp, five session
scratchpads, `~/.claude/file-history`, 76 transcripts, the Recycle Bin,
OneDrive and D:. No pre-corruption copy exists. `work/` is gitignored and was
never committed. **One avenue remains and needs a human: Volume Shadow Copies
require an elevated shell.**

**What was recovered, at zero credits.** 50 domains from the input CSV;
firmographics for 3 from `out/domains/` (the genuine purchase) and 25 more
from the client's own Desktop ICP export (a different vintage, marked as
such); 61 rows of free local research for 26 accounts; 3 contacts and 18
exclusion decisions. Twenty-five records carry an explicit `recovered_from`
block naming path, vintage and confidence.

**The trustworthiness check that matters:** the three accounts with genuine
surviving data re-score to exactly their pre-corruption values -
northbeam 59, ninefields 53, brightpath 47. Accounts restored from
the weaker source carry `low` confidence against `medium`.

**A caution learned twice.** "The file exists", "the hash did not change" and
"the API returned 200" were each treated as proof of correctness during this
work and each was wrong. The md5 checks reported `work/` integrity while the
file held fixtures; a recovery estimate counted `company.json` files without
reading them, and 47 of 50 were empty shells. Read the content.

---

## Productive: current state

Batch `productive-pilot-2026-09-07`, 50 real domains, rebuilt after the
incident. **This is a reconstruction, not the original estate.**

| | |
| --- | --- |
| Accounts | 50 |
| QUALIFIED | 3 - northbeam.test (59), ninefields.test (53), brightpath.test (47) |
| REVIEW | 9 |
| UNKNOWN | 38 - no firmographics survive and none could be recovered free |
| People | 3, at 2 accounts |
| Verified / sendable | **0** - no verification evidence survived, and none has been re-bought |
| **Actually sent** | **0** |

Pre-corruption the split was 5 QUALIFIED / 36 REVIEW / 9 REJECTED.
`summit-usa.test` (was 54) and `arcadia.test` (was 49) are now REVIEW at
33, because the evidence behind them is the weaker recovered source rather
than the ContactOut purchase. That is honest, not restored.

**A real campaign preview exists.** Rendered through the production cadence
path - five of seven steps are template-based and need no LLM. Personalization
resolves; no unresolved variables. Two copy defects found by inspecting it:

- `{angle_word}` renders the internal key, giving the subject "how teams your
  size handle founder". Substituting the client's own phrase yields 77
  characters against `MAX_SUBJECT = 60`, and widening a lint rule to pass a
  draft is forbidden. **Needs a short client-supplied topic per angle.**
- The `{line}` opener asserts "you are running X at Y" from a fallback,
  because the `rec["evidence"]` lookup it prefers has never fired - no record
  has that key.

## Providers

| Provider | State |
| --- | --- |
| ContactOut | **Verifier fixed and live-proven.** Route is `GET /v1/email/verify?email=`, not the `/email-verifier/verify` that 404'd nine times out of nine - that was the MCP tool name with a verb bolted on. Confirmed on three real addresses across two runs. |
| Reoon | Working. The only vendor trusted to clear a catch-all. |
| Deliverable | Adapter fixed, **contract gate still shut**. It read status/result/state/verdict; the vendor sends `email_status`, so every real answer classified as unknown. Only the negative branch is proven live. |
| Apify | Working for the first time. Three defects fixed: proxy config refused outright, `wait_for` polled 30s against an advertised 120s bound so billed runs were abandoned, and 404 pages were kept as evidence. |
| EmailBison | 13 workspaces, PRODUCTIVE is id 10, 225 sender-emails. Ownership unprovable - see blockers. |
| HeyReach | 41 accounts, 33 auth-valid and active, 1 active on invalid auth (id 129531). No tenant concept in the API at all. |

## Spend, reconciled

| Call | Credits |
| --- | --- |
| `company-information-from-domain` | 50 |
| `decision-makers` | 40 |
| `aiark-people-search` | 4 |
| **Ledger total** | **94** |

Verifier calls visible in stored evidence: ContactOut 4, Reoon 2 - **6
chargeable**. Deliverable's 4 cost nothing: `require_contract` refuses before
any HTTP call.

**Disclosed blind spots.** Verification did not reach the waterfall ledger
until `92c4630`, so this batch's ledger under-records it and the six above are
counted from evidence rather than from the ledger. Contacts excluded before
`b749418` had their evidence stripped, so roughly four earlier Reoon calls are
no longer reconstructable from canonical state. Agent probes outside the
ledger: about 2 ContactOut verifier credits, 1 Deliverable credit, 1 further
ContactOut verify. Apify ran roughly 36 times; its price is in compute units,
**UNKNOWN** to this system and not zero.

**Known unnecessary spend: 10 credits.** Restoring a persona-excluded contact
produced a stub with no address, `usable_contacts` went false, and enrichment
re-bought `decision-makers` for a company whose people were already on the
record. Root cause fixed in `b749418`.

## Blockers preventing a live canary

Live sending is **NO-GO**, on evidence rather than caution.

1. **PROVIDER, BLOCKING - the EmailBison credential is reading another
   client.** `GET /sender-emails` returns 32 inboxes today, every one a
   Greenfield domain, zero mentioning Productive; yesterday it returned 225 with
   153 tagged Productive. Six query forms and eight header forms, real ids and
   nonexistent, all return byte-identical data. There is no workspace selector
   and no "who am I" route. **A canary armed against workspace_id=10 would
   have sent Productive's mail from Greenfield's inboxes and got HTTP 200.**
   HUMAN-ACTIONS-REQUIRED 4.
2. **PROVIDER - HeyReach ownership is a written attestation away.** 41
   accounts, 33 `authIsValid AND isActive`, all 79 campaigns on one
   `organizationUnitId` (118832) - so no cross-tenant mixing inside the key.
   What is unproven is that 118832 is Productive's rather than Resonate's own
   agency org. Needs two sentences naming the key's owner and the approved
   account ids. HUMAN-ACTIONS-REQUIRED 4b.
3. **DATA - no contact is verifiable.** All 3 have `verdict: null`. Two
   independent vendors must approve the same address and no verification
   evidence survived the incident.
4. **CODE - `work/senders.jsonl` is entirely fixture.** Every Productive inbox
   is on the reserved `productive.test` TLD with `provider_account_id`
   `bison-1..64` and LinkedIn `4002-4005`; live ids are 3241-3991 and
   116968-212356. Zero overlap on either channel. Sender selection would
   address accounts that do not exist - it fails closed today only because the
   canary campaign has no senders at all.
5. **CODE - there is still no send path.** `push.run(live=True)` raises.

## What the red team found that is not yet fixed

An independent adversarial pass on the rebuilt cohort. The verification gate
held under three separate attacks and is genuinely good. These did not hold:

- **`outreachclaims` is not on the send path.** It is the authority on claims
  about our own prior outreach and has no consumer in `cadence`, `lint`,
  `claims`, `eligibility` or `push`. The breakup copy was corrected in
  `87c95fe` so it claims nothing, but the wiring is the real fix and it needs
  the confirmed-touch model to mean something in a build that cannot send.
- **The angle used in every message is one the record marks unsupported.**
  `qualification.messaging.unsupported_hypotheses` names it;
  `cadence.angle_words` never reads `qualification.messaging`.
- **Contact selection inverts its own persona plan.** `persona_priority` puts
  operations first and founder last; at both accounts the CEO was kept and the
  COO excluded by `cap_per_domain: 1` on a bucket holding both. Two parallel
  persona vocabularies, and the send path reads only one.
- **A contact is in `contacts` and `excluded` at once** (Connor D), and
  `eligibility._selected` reads a flag on the contact rather than the sibling
  list, so it never sees it. `Rivers Colyer` appears twice in `excluded`.
- **MX screening reads missing evidence as permission** - `mx.allows_email`
  returns True with "no MX check has been run". Wrong default behind a right
  one.
- **brightpath carries 2 contacts against a tier-C cap of 1.** Two caps
  disagree and the looser silently won.
- **`ninefields.test` has zero contacts because the title matcher exact-matches**
  and missed "Design Studio Manager" against its own target "Studio Manager".

## Multi-workspace isolation

Attacked with 50 adversarial tests. **Every read path held** - no attack
reached another client's records, contacts, campaigns, senders, approvals or
replies. Four write and control paths leaked; **all four are fixed**:

- `events.apply` skipped its tenancy check when an event carried no client -
  the ordinary shape of a LinkedIn reply - and matching returned the first
  record holding that address. Proven end to end: one tenant's reply paused
  another tenant's company. Ambiguous addresses are now refused.
- `Repo.audit` did not name a super admin's crossing. It carries role and via.
- `save_campaign` validated the campaign's client and never its record_ids.
- `save_records` appended rather than replaced a re-tenanted row, forking it
  into two rows sharing one id.

## Zero-code new-client onboarding

`tests/test_new_client_from_zero.py` creates a workspace, loads it, imports
through both the browser and CLI paths, scores it and proves isolation - with
no source edits. Three client-leakage bugs fixed: `campaignseg` had
client_prefix = PRODUCTIVE as a global default no client file could override;
`icp.settings` read `icp.markets` while the product writes `market.geos`; the
starter template named another client's cadence.

**Custom verticals: solved.** `segmentation.verticals` lets a client declare
its own market with a kind of agency, service or non_icp, and `icp` now asks
`segments.kind_of` rather than testing membership of the built-in tuples.
Renaming a built-in is still refused, because that orphans existing segment
keys.

## 30k readiness

Import survives 30,000 domain-only rows in 0.21s and 21MB. MAX_BYTES (8MB)
binds before MAX_ROWS (200,000), so a wide export is refused whole - a 30k TAM
upload is only safe if it is domain-only or near it. Checkpoint/resume verified
at record 12,000 with zero overlap.

**The 30,000-credit floor is not universal.** It is real for a bare domain
list. The 51,741-row vendor export already in `work/` carries headcount,
industry, tags, locations and founding year: 20,544 unique domains scored for
zero credits, and adding the free local read to the strongest twenty moved six
to `qualified`. Every row also carries a work email and a LinkedIn URL, and
41,566 match a Productive persona.

Free-first research measured on the pilot: 52% resolve locally, **74% Apify
avoidance**, 85 requests and 85 seconds for 50 domains at zero provider cost.

## The canary attempt, and what it cost to learn

A one-person LinkedIn canary was prepared and **not** proposed. Two independent
red teams found it unsafe, and the three most serious findings were caused by
state repairs made while assembling it.

**What was achieved.** 20 authorised credits recovered the two approved COOs
with full details plus 11 other people whose data the incident destroyed. MX
screening, free, closed Northbeam's email lane on DNS alone and independently
reproduced a pre-corruption finding. Verification confirmed BrightPath is a
catch-all that Reoon declines. Selection now honours the strategy's own persona
priority, so a COO outranks a CEO where the plan says operations leads. Angles
match the person's job, and a CFO with no fitting angle is held rather than sent
founder copy.

**What the repairs broke.** Each was individually reasonable and the sequence
was not:

1. Stash-and-merge for discovery lost the contact keys. Reassigning them left
   11 events pointing at a key that resolves to nobody.
2. Re-running selection reset the contact objects and **wiped verification
   evidence bought with real credits** - a recorded "not safe to send" became
   "unknown", which is missing evidence overwriting negative evidence, and it
   guarantees a re-buy.
3. Re-running selection without re-exporting left the operator-facing artefact
   naming different people than the queue. `out/domains/.../people.csv` said
   Connor D and Jonathan Gessert; the queue said Austin Ball and Anthony
   Andreatos. **An approval request issued at that moment would have asked a
   human to authorise the wrong people.** Fixed by re-export; artefact and queue
   now agree.

**The lesson worth keeping.** Batching state repairs and validating at the end
hid each defect behind the next. One change, one verification, is not a
preference here - three of these would have been caught immediately.

**Copy blockers found and fixed** (`fa58e88`), all three introduced the same
day: the wrong-angle guard covered email and not LinkedIn, which is the channel
a canary uses; an angle written as a predicate clause made the connection note
unparseable for every economic buyer; and the breakup template still claimed
prior outreach after being documented as claiming nothing.

**HeyReach reconciliation is complete and clean.** 41 accounts, 33 with
`authIsValid AND isActive`, all 79 campaigns in `organizationUnitId 118832`.
**Ownership is not derivable from the API** - the full field inventory of both
objects contains no tenant, client, owner or team field. Only account 174810
carries a `productive.test` address and is most likely a real employee's personal
profile. One account, 129531, is active with invalid auth.

**A second blocker, unrelated to ownership.** The live action is
`AddLeadsToCampaignV2`, which adds a lead to an existing HeyReach campaign. Our
rendered note travels only as `customUserFields[0]`; the message the prospect
receives comes from that campaign's own sequence. The campaign object exposes
no sequence, step or message field, so **this system cannot see what would
actually be sent.**

## Next actions, in order

0aa. **There is no safe canary candidate.** Every qualified account has been
   worked by the client's own live campaigns. Either accept a second touch on an
   already-worked account - which is an operator decision about the client's own
   estate, not a technical one - or resolve one of the eight clear accounts.
   The cheapest path is 1 ContactOut credit to qualify the clear `review`
   account and 10 to discover people at it.

0ab. **Build the HeyReach-side prior-contact check.**
   `POST /inbox/GetConversationsV2` is already on the read allowlist. Without
   it the LinkedIn lane can collide and nothing will notice.

0. **Confirm the six remaining Blitz request contracts for zero records.** An
   empty request body returns 422 naming the field it expected. One field name
   was already wrong, so the rest are suspect, and no Blitz call for real
   client data is safe until they are read. Needs permission for provider
   calls; costs nothing.

0b. **Store one real HeyReach sequence.** `linkedin_only` is a predicate with
   no subject until a real graph exists to run it against. Read-only:
   `mapping list --provider heyreach`, then `--sequence <id>`.

0c. **Import the two company LinkedIn URLs that are already on disk, free.**
   Verified in the client's own export at
   `C:\Users\Operator\Desktop\PRODUCTIVE - MARKETING & ADVERTISEMENT.csv`:
   northbeam.test is `.../company/northbeam-marketing` and
   brightpath.test is `.../company/321-web-marketing`. That leaves exactly
   **one** justified paid Blitz call in the whole cohort - `ninefields.test`,
   which is not in the export. The export is dated 2026-03-20, so it wants the
   `recovered_from` vintage block the other 25 records already carry.

0d. **Clear the two contaminated state files**, or decide not to. They cannot
   be re-contaminated, and `python -m src.check` now fails while they stand.

1. **Get a workspace-scoped EmailBison credential** (HUMAN-ACTIONS-REQUIRED
   4). Until then the email lane cannot open for Productive, and no code
   change alters that.
2. **Attest the HeyReach org unit and name the approved account ids**
   (4b). LinkedIn is the only lane that could open at all.
3. **Try Volume Shadow Copies from an elevated shell** for a snapshot in the
   Sep 7 23:45 - Sep 8 10:35 window. The last chance at the original queue.
4. **Wire `outreachclaims` into the send path**, with the confirmed-touch
   model made meaningful first. See the red-team section.
5. **Fix contact selection to honour `persona_priority`** and recover the two
   COOs, and reconcile the two persona vocabularies.
6. **Decide the angle subject wording** - a short client-supplied topic per
   angle, so `comparable_proof` stops rendering "how teams your size handle
   founder" and stops overflowing `MAX_SUBJECT`.
7. **Rebuild `work/senders.jsonl` from a provider read.** It is fixture data
   on a reserved TLD and cannot support any send.
8. Answer the two Productive targeting questions (5), then Deliverable's
   positive branch (2).
9. If a live send path is ever wanted, that is a design decision nobody has
   taken. When it is taken, close PRODUCT-GAPS 21 item 12 first: nothing
   refuses a contact with no sender assignment, and HeyReach falls back to
   account id `0`.
