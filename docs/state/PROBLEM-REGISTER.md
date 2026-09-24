# Problem register — canonical

One place for confirmed problems, so the same ones stop being rediscovered.
Started 2026-09-20 after a session found, independently and from scratch, two
defects that were already written down: the geo ISO fix (fixed on master three
days earlier) and the vacuous coverage default (in Buggie's audit that morning).

**Rules for this file.**

- A row is CONFIRMED only with a reproduction or a measurement. A finding that
  has not been reproduced is UNVERIFIED and says so.
- **Code written is not FIXED.** FIXED means merged with a regression test.
  PRODUCTION_VERIFIED means the behaviour was observed against the real
  providers, and nothing reaches it on the strength of a passing test.
- REFUTED rows stay. Deleting them is how a disproven hypothesis gets
  resurrected six days later.
- Every row names its evidence. "Somebody said" is not evidence.

Sources folded in: `work/BUGGIE-FINDINGS-2026-09-20.md` (13 specialists, 16
adversarial skeptics, 83 pre-existing suite failures excluded), this session's
own measurements, and the GLM review docs.

---

## OPEN — ordered by production impact

_9 open at creation. ISSUE-001, 002, 003 and 006 are now closed._

_ ISSUE-010 added 2026-09-20 from the sender-utilisation review._

_ISSUE-011 and REFUTED-006 added 2026-09-23 from the post-reboot reply-stop sweep._

_ISSUE-012 added 2026-09-23: the sourcing ceiling is the provider's, not ours._

_ISSUE-025 added 2026-09-23 night: the adoption path, and the 76 blank
emails it sent. `ISSUE-013` was already taken by a closed row - numbers are
not reused._

_ISSUE-038, 039 and 040 added 2026-09-24 lane 1, and renumbered TWICE:
master moved under the session and took 034, then 035 and 036, for other
findings. 037 is left free deliberately - a gap is cheaper than a third
renumber. **AND MASTER ALREADY CARRIES ISSUE-038's TEXT UNDER THE NUMBER
034**: another session staged this file mid-edit and committed the row
before it was numbered. When this branch merges, master's second
`ISSUE-034 - The research pack named three Apify actors that do not exist`
is the SAME finding and must be deleted, not kept beside ISSUE-038._

---

### ISSUE-040 · The undeclared-write guard reports 54 copies of itself · MEDIUM · OPEN

**Reproduced 2026-09-24.** `tests/test_nothing_writes_to_a_provider.py`
walks the filesystem from the repository root, and the Claude Code harness
keeps agent worktrees under `.claude/worktrees/`. Those are full checkouts,
so every declared write in `src/providers/*` appears again at a path the
allowlist does not match - 54 findings, all of them the same declared calls
seen through a second path.

`ALLOWED` is keyed on repo-relative paths, which is correct; the walk is what
is too broad. The test is currently RED for anybody with a worktree present,
and this file's own warning applies to it: a guard that cries wolf is a guard
somebody switches off. It caught a real finding the same day
(`src/researchpack/pack.py` POST, now declared), which is exactly why it must
not be left noisy.

**Not fixed here.** Narrowing the walk of a security guard is a decision that
deserves its own review rather than a drive-by in a research-pack commit, and
the worktrees belong to other sessions.

---

### ISSUE-039 · 70% of the `open_roles` rows were another company, and every one would have become a fact · HIGH · **FIXED**

**Measured 2026-09-24 over 24 real accounts** (`docs/RESEARCH-PACK-PILOT-2026-09-24.md`).
`bebity/linkedin-jobs-scraper` is aimed with `companyName`, which is a TEXT
FILTER, not an identity. Of the 71 rows it returned across the eight accounts
that got any, **50 were a different company** that merely shares part of a
name - and on four of those eight accounts, **all ten rows were**.

`actors.slug_from_jobs` already applied an identity test before accepting a
company's LinkedIn SLUG from a row. The FACTS were made from every row with
no check at all, so a pack would have asserted that somebody else is hiring
on five of the eight accounts that had roles - and an `open_role` fact is
exactly what a first line leans on. This is the wrong-company shape of
`WRONG-PERSON-REPORT-2026-09-11.md`, one entity up.

**Fixed.** `actors.is_this_company(row, domain, site_key)` is now the one
identity test - the row's own `companyWebsite` has to be on this record's
domain - and it is applied to the facts as well as the slug. It FAILS CLOSED:
a caller with no domain to check against gets no roles rather than unchecked
ones, and a row with no website field proves nothing and is refused.

Regression: `tests/test_researchpack.py::test_another_companys_job_makes_no_fact`
and `::test_and_with_no_domain_to_check_against_nothing_passes`, both verified
by deleting the guard and confirming those two - and only those two - go red.

**Not production-verified.** The corrected coverage figure is recomputed from
the pilot's cached rows, not from a fresh paid run.

---

### ISSUE-038 · The research pack named three Apify actors that do not exist · HIGH · **FIXED**

**Confirmed 2026-09-24 by asking Apify.** `src/researchpack/actors.py`, as
merged, named `apify~linkedin-company-posts-scraper`,
`apify~job-listings-scraper` and `apify~linkedin-profile-posts-scraper`.
Every one answers **404 `record-not-found`** on `GET /v2/acts/{id}` with the
live token. `apify~website-content-crawler`, the one id that was not
invented, answers 200 - so this is the ids, not the credential.

**Why nothing caught it.** `tests/fixtures/cassettes/00-researchpack.json`
matched on `url_contains: "linkedin-company-posts-scraper"`, so the cassette
and the code agreed with each other and neither agreed with Apify. Thirty-odd
tests were green against a provider surface nobody in this codebase had ever
seen - the same shape as "a green test that cannot fail", one layer further
out: not an invented fixture for a real actor, an invented fixture for an
actor that does not exist.

The input shapes were invented with the ids and were wrong in a way that
matters: `proxyConfiguration` was set on all three, and none of the three
real actors declares that field. The date field was read by a flat key list
that cannot see `postedAt.date`, where the real actor puts it, so every post
would have come back undated.

**Fixed.** Four verified ids, each confirmed with `GET /v2/acts/{id}` and
then RUN live; input shapes read from each actor's declared input schema; the
cassette rewritten to the real field SHAPE with identifiers replaced.
Evidence and the pilot numbers: `docs/RESEARCH-PACK-PILOT-2026-09-24.md`.
Regression test: `tests/test_researchpack.py::EveryActorIdIsOneApifyKnows`,
which cannot itself reach the network and says so - it asserts the id SHAPE
and points at the dated live check, because the three wrong ones all claimed
to be on Apify's own account.

**A second defect found in the same file and fixed with it.** The person
cache was keyed on the ROLE (`champion`) and not on the person, so an account
whose champion changed read the previous champion's posts out of the cache
and attributed them to the new one. The test that covered this asserted zero
new runs after a champion change and called that the point of having two
keys - it was asserting the defect, under a docstring that said the opposite.

---

### ISSUE-034 · the blank-render gate refuses AFTER the attach, so a refusal leaves leads enrolled

**Status: OPEN, and it cost a real divergence on 2026-09-24.**

`bisonfactory.stage` ensures leads, ATTACHES them, and only then reads the
provider's rendered queue back. So control (a) refuses *after* the write it
is meant to gate, and the refusal does not roll anything back.

**Measured tonight.** Three pushes, all reporting `REFUSED` and
`enrolled at the provider 0`:

    campaign   before   after   push report
    496          9       43     REFUSED (blank-render gate)
    497          7       20     REFUSED (attach readback)
    498         13       15     REFUSED (attach readback)
                        ----
                         49 leads attached

496 is the pure case: the gate refused on 11 of 17 rendered rows being blank
— **the incident's own stopped blanks, still sitting in that campaign's
queue** — and 34 leads went in anyway.

**Two consequences, and the second is worse than the first.**

1. A campaign carrying settled blank rows can never be pushed into again,
   because the gate counts them. The incident's residue is now a permanent
   block on 496 until those rows leave the queue, and ISSUE-030 means there
   is no verb to remove them.
2. **A refusal reads as "nothing happened" and is not.** The operator was
   told `enrolled 0` three times while 49 leads went live in three ACTIVE
   campaigns.

**Not a safety incident, and the distinction matters:** 0 pending blanks in
all three, verified immediately after and again fifteen minutes later; the
leads are verified, carry approved copy, and were the cohort cleared through
the veto window. The fault is that our report of what happened was false.

**The fix is ordering, not a new guard.** The rendered-queue read has to
happen against a staged-but-unattached state, or the attach has to be
reversible — and it is not, which is ISSUE-030 again from a third direction.

---

### ISSUE-016 · `attach_leads` reports REFUSED on a write that succeeded · MEDIUM — **RECURRED 2026-09-24, with a cost**

Already in this register. Tonight it produced the 497 and 498 halves of
ISSUE-034: *"the provider answered 200 but 13 of 16 / 2 of 15 leads are not
in campaign after 6 readbacks over ~15s"*. Minutes later every one of them
was there. The readback window is too short for the provider's own
visibility lag, and the failure mode is not a missing write — it is a
truthful write reported as a failure, which is the shape that makes an
operator act on a false negative.

---

### ISSUE-032 · the bot cannot post or upload in a Slack Connect channel

**Status: OPEN, FROZEN until October by the FOCUS window. Client deliverables
go through a person until it is solved.**

Measured 2026-09-24 against `#productive-resonate-outbound` (`C0ADUMGQX8S`),
which is externally shared with The Productive Company:

    slack_complete_file_upload  ->  mcp_externally_shared_channel_restricted

and the message tool documents the same restriction for posting. So the bot
can neither attach a file nor send a message there.

**THE OBVIOUS WORKAROUND IS WORSE THAN NOTHING, and that is the part worth
recording.** Posting the internal `#resonate-os` file links into the client
channel looks like a fix and is not: a Slack file link is not an access
grant, those files live in the Resonate workspace, and the client is not in
that channel. The client would see a message announcing three files and
three links that do not resolve, in front of them. Not attempted.

**Candidates, for October:**

1. A Resonate-side channel shared TO the client, so the files live on our
   side of the boundary and the bot posts into its own workspace.
2. The Slack Connect file API with the scope that permits it, if one exists -
   this needs checking rather than assuming, because the refusal above is
   from the MCP layer and may or may not reflect a Slack-level limit.

**AMENDED 2026-09-24: the bot CAN draft there, it cannot send.**
`slack_send_message` is refused, and its own error names the route:
`slack_send_message_draft` succeeds against the same channel and lands the
text in the operator's Drafts, one click from sent. So a client deliverable
can be composed, scope-checked and staged by the bot; only the send is human.
That is a materially better position than "client deliverables go through a
person", and the earlier line in this row overstated the limit.

**Files still cannot go that way** - only text. The three CSVs went by hand.

---

### ISSUE-033 · REFUTED — 481 was refused on two findings that were both mine and both wrong

**Status: REFUTED 2026-09-24, same day, by re-reading the provider. 481 is
RESUMED and clean. Kept because a disproven hypothesis that is deleted gets
resurrected, and because the two mistakes are different and both worth
naming.**

**MISTAKE 1 — I read keys that do not exist.** A sequence step carries
`email_subject` and `email_body`. My script read `subject` and `body`, got
`None` from both, and I reported "ALL FIVE EMPTY - subject '', body length
0" as a measurement. The real steps are `{SUBJECT_1}` / `<p>{BODY_1}</p>`
through `{SUBJECT_5}`, identical in shape to 491's. **A `.get()` on an absent
key returns None, and None is not evidence of emptiness** - the provider's
own reply was in hand and I did not check its keys against it.

**MISTAKE 2 — I joined two counts in prose and called it a finding.** I
counted 9 foreign leads among 23, counted 9 `sending_paused` among 23, and
wrote "the 9 sending_paused leads are the 9 foreign ones". Cross-tabulated:

    sending_paused   ours=True   has_copy=True    9   <- sendable, fine
    stopped          ours=False  has_copy=False   9   <- foreign, contained
    stopped          ours=True   has_copy=True    5

The foreign leads were already stopped. **Two counts that match in size are
not the same set**, and nothing checked.

**The containment script is what caught it.** It selected targets by reading
each lead rather than by trusting the membership label, found 0 to stop, and
did nothing. Written the obvious way - "stop the 9 `sending_paused`" - it
would have stopped nine healthy leads on a false premise. Select by the
property you care about, never by the label you inferred it from.

**What survives:** "an empty queue is not a clean queue". 481 had 0 queued
rows, so nothing had been render-checked; that is true of every resumed
campaign until its scheduler builds rows and the watcher scans them.

The original, wrong text follows so the correction is legible.

**Status: OPEN. 481 stays PAUSED. The blank-render gate refused it on
2026-09-24 against an explicit operator instruction to un-pause everything,
which is the gate working.**

    sequence steps      5      ALL FIVE EMPTY - subject '', body length 0
    leads              23
      foreign (no record_id / contact_key)      9
      those same 9 missing subject_1, body_1    9
    membership         stopped 14, sending_paused 9
    queue rows          0   -> blank_render_verified = FALSE, never a pass

**The 9 `sending_paused` leads are the 9 foreign ones**, held by nothing but
the campaign's pause - ISSUE-026's shape exactly. Resuming 481 sends 9 blank
emails to the client's own leads: the 2026-09-22/23 incident reproduced in
full, and the steps being empty templates means no variable fix would save
it.

**An empty queue is not a clean queue.** 481's queue has zero rows, so the
gate reads `blank_render_verified: False` and refuses rather than passing on
an absence of evidence. This is the first time that clause has done real work.

**To make 481 safe rather than merely paused:** stop the 9 leads, so the
containment is a lead-level stop instead of a campaign status anybody can
lift. It forfeits no outreach - all five steps are empty. The copy has to be
written and the foreign leads detached (ISSUE-030, frozen) before 481 is
anything but a trap.

---

### ISSUE-031 · the QUALIFIED-only ruling was enforced at the writer and absent at the reader

**Status: FIXED 2026-09-24 (`d7f3128a`). The export remains STOPPED on
ISSUE-023, which this does not touch.**

**ISSUE-019 a second time, from the other end.** `4afb54d5` implemented the
operator's ruling in `nightlysourcing`, where records ENTER the candidate
list, and **this register recorded it as "implemented and standing"**. It is,
for records added after it landed.

`candidates.jsonl` already held **1,394 REVIEW records** at that moment, and
`candidateexport.exportable_candidates()` filtered on `state == "new"` and
nothing else. Measured 2026-09-24 **by calling the function**:

    exportable_candidates()          1508 rows
    of which icp_status == review    1394
    rows at icp_score 0.0            1410
    median headcount               16,745

Productive sells to 20+ person marketing and creative agencies.

**A gate at the writer protects the future. A gate at the reader protects the
file as it is** — and the defective rows were already on disk, where no amount
of correct writing reaches them. The gate is now in both places.

**RETIRED, operator decision 2026-09-24 (`a3c02e08`).** The whole 1,508-row
pool is out of every export path. `exportable_candidates()` now RAISES
`RetiredCandidatePool` rather than returning an empty list - an empty CSV
reads as a quiet week rather than a stopped export, and this project has
shipped that confusion before.

**Gated on PROVENANCE, not a flag, so it clears itself.**
`qualify_sourced_supply.py` stamps `_sourced_at` and nothing that produced
the legacy pool ever did, so a rebuilt row passes with nobody remembering to
flip anything back. ONE legacy row stops the whole export: a partially
rebuilt pool must not quietly ship its good half.

**It did not unblock the export.** Before the retirement the fix left 114
rows, and those are ISSUE-023. `ThisDoesNotUnblockTheExport` asserts the
zero-scoring enterprise row still passes, so a green suite is never read as
permission.

**AND THE TWO POOLS HAD BEEN CONFLATED.** The 48,017-domain chain does not
use `candidates.jsonl` at all. `work/qualified-supply.jsonl` is a different,
later pool and is sound on every measure the other one fails:

                          candidates.jsonl   qualified-supply.jsonl
    icp_score == 0.0            58 of 114            0 of 32,951
    median headcount               16,996                     44
    in the 20-200 band            0 of 114         29,763 (90.3%)

So supply proceeds on the sourced pool; the legacy weekly export does not.

---

### ISSUE-026 · `emptyrender.scan` called a PAUSED campaign contained

**Status: FIXED 2026-09-24 (`5257adbe`), PRODUCTION_VERIFIED** — the offending
row was read back from the provider, stopped, and re-read as `stopped`.

The split used an **allowlist** of sendable statuses,
`{"scheduled", "queued", "pending", ""}`, and filed everything else under
`already` — a bucket whose own comment read "already sent or stopped".
`sending_paused` is neither.

Campaign 491 was paused, so all 275 of its undelivered rows read
`sending_paused`, and blank row 22356723 (lead 204724, `Re: ` / `<p></p>`)
was counted as contained when the only thing containing it was the
campaign's pause. One click on resume and it sends.

**Both witnesses reported `pending: 0` and both were wrong in the same way**,
because the watcher heartbeat and an independent provider read share this
predicate. Worse: pausing the campaign is what moved the row out of
`pending`, so the halt erased the evidence of its own necessity.

Fix: a **denylist**, `SETTLED_STATUSES = {sent, stopped, bounced}`. An
allowlist fails closed on a status nobody anticipated, and failing closed
here means calling an unknown row safe. A row halts only when it is both
faulty AND unsettled, so an unrecognised status on good copy costs nothing.

Tests: 6 new on the real rows, 30 in the file; restoring the allowlist
fails 3. Sweep of all 275: exactly one fault, the known blank.

---

### ISSUE-027 · every external-stop CRITICAL this estate raised named campaign 487

**Status: FIXED 2026-09-24 (`d6a719c2`).**

`_alert_if_stopped_by_someone_else` was called with the module constant
`PROVIDER_ID` (= 487) instead of `watched`, the loop's `--campaign`
argument. One script runs nine times over nine campaigns.

The figures came from the real campaign's snapshot, which is what made it
unreadable rather than merely wrong. 2026-09-23T22:18:46Z:

    {"campaign": "487", "was": "active", "now": "paused",
     "emails_sent": 322, "leads": 332}

487 has 0 sends and 10 leads and was active throughout. **A CRITICAL naming
a campaign anybody can see is healthy reads as a false alarm**, and that one
went unactioned into the morning — which is how the pause of the largest
sending campaign was not noticed until it was read off the provider the next
day.

The existing tests could not catch it: they call the function with
`provider_id` and `watched` set to the same value, so the fixture agreed
with the bug. The new test reads the CALL SITE by `ast`.

---

### ISSUE-028 · witness 1 was unsatisfiable, so the reboot drill could never pass

**Status: FIXED 2026-09-24 (`c1d93e94`), PRODUCTION_VERIFIED** — `20 of 20
monitors have two witnesses`, exit 0, on the live estate.

`supervisor.witnesses` wants a live pid from a state file written after the
boot, plus a fresh beat. **Only `supervise.py` ever wrote that state file,
and this estate is started by `scripts/start_monitors.py`** — so
`work/supervisor/` did not exist and no monitor could ever hold witness 1.

`cold_start --verify` therefore answered `0 of 20` while
`start_monitors --status` read `20 UP` on `beat+process` and the table
`--verify` prints directly underneath showed every monitor beating within a
minute. **Four handoffs read this as a reason to refuse the drill.** Refusing
was right; the diagnosis stopped one layer short. Adopting infra `46474c6c`
fixed the monitor-name → heartbeat-file map — the NAME half — and the first
verify after merging it still answered 0 of 20.

Fix: `supervisor.record_started(name, pid)` is public and
`start_monitors.spawn` calls it. Deliberately not a change to the process
model: making the supervisor the only thing allowed to start a monitor would
mean changing how a live estate is run to satisfy a measuring instrument.

Tests assert the CALL SITE by `ast`, because `record_started` alone is easy
to keep green and what failed for four days is that nobody called it.

---

### ISSUE-029 · a gagged client question reached nobody

**Status: FIXED 2026-09-24 (`c62c6309`).**

`CLIENT_CHANNEL_GAG` is correct and stays. What was not correct is what the
gagged path did next: one row to `work/slack-agent.jsonl`, one line to
stdout, return. No Slack post, no ticket, no internal notification.

The gag was set to stop the agent saying something **wrong** to a client. It
was also stopping the operator finding out the client had **asked** — 11 of
32 questions in the replay audit, 34% of real traffic, answered with silence
that nothing reported.

`notify.CLIENT_QUESTION_UNANSWERED`, ACTION_REQUIRED, internal only.

---

### ISSUE-030 · there is no documented route for removing a lead from a campaign

**Status: OPEN, and it BLOCKS the operator-approved remove-lead verb.**

OPERATOR DECISION 2026-09-24 approved a narrow remove-lead-from-campaign
write verb so the 91 foreign leads could be detached from 491–498 rather
than only stopped. **It cannot be built on evidence today.**

`docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md` enumerates 50 routes across
CODE, PROBED and DOCS evidence and **none of them removes a lead from a
campaign.** There is `attach-leads`, `attach-lead-list`,
`stop-future-emails`, and detach routes for senders and tags — no lead
detach.

**`DELETE /leads/{id}` is not the verb and must not be reached for.** It
deletes the lead outright, and these 91 are the CLIENT'S OWN leads, months
old, members of their campaigns 327/328/352. Deleting them would destroy
client data — considerably worse than leaving them attached.

Inferring `leads/remove-leads` from the `attach-sender-emails` /
`remove-sender-emails` symmetry is exactly what that document forbids:
*"No route is inferred from naming patterns alone."* And this module's
history is three wrong conclusions that a route did not exist, each reached
by guessing a URL and reading the failure as absence — so a probe can
establish presence but never absence.

**What unblocks it:** a vendor documentation page for a lead-detach route,
or an independent implementation (the `remove-sender-emails` precedent was
adopted on the vendor's own page plus `bcharleson/emailbison-cli`). Until
one exists, the foreign leads stay **stopped and attached**, which is safe —
0 sendable rows, verified per lead — and unhygienic.

---

### ISSUE-025 · adopting a lead by email carries the CLIENT's lead into our campaign

**Status: FIXED in code 2026-09-23 (`7bb23d6d`), NOT production-verified** —
no staging run has exercised the fix against a live adoption yet. The
incident it caused is closed: `docs/INCIDENT-2026-09-23-BLANK-EMAILS.md`.

**76 blank emails reached real prospects on 2026-09-22/23** — subject `''`,
body `'<p></p>'` — and one prospect replied to one.

`bisonfactory._ensure_leads` calls `bison.create_lead`. When the provider
answers *"email has already been taken"* the branch called
`find_lead_by_email` and used the id it got back. That refusal was read as
**"we lost a race with ourselves"**, and it also means **"this address is
already in the CLIENT'S OWN ESTATE"**. In that case the lookup returns
*their* lead — months old, carrying *their* `headline` and `location` and
none of our copy — and the branch attached it **without ever writing our
variables onto it**.

Our sequence steps are pure merge templates (`{SUBJECT_1}`,
`<p>{BODY_1}</p>`), so the provider rendered them against a lead that had
neither and sent the empty result.

    foreign leads in 491-498                              91
    recorded in OUR store as `bison_lead_id` on OUR contacts   90
    `sequence_finished` members of the client's campaign 352   85
    members of the client's 327 / 328                     55 / 23
    created_at 2026-04-08 / 2026-04-23                    55 / 23
    control: factory leads in 327/328/352            0 and 1 of 120

**We attached them. Nobody else did**, and the action ledger cannot say so
because it records no bison lead attachment at all — its silence is not
evidence.

**REFUTED on the way: the revive lane did not do this.** Two independent
grounds — `reengagement_inventory.py` is read-only and `revival.py` makes no
provider calls, so the lane has no attach path; and **0 of the 91** appear in
its 1,415-row inventory. All eight campaigns are `lanes=['domains']`, created
fresh at 19:18Z on 09-21, not from a list. It is still a lane crossing, by a
different route.

**Why every local check passed.** Every guard in `bisonfactory` inspects
`wanted` — the leads we stage — and 73 of the 76 went to leads that were in
`wanted` only as an address, whose provider row we never wrote. The other 3
carry correct copy **to this day**: they were re-staged and patched at 13:58,
up to 54 minutes *after* the empty row had been queued and sent. **The render
is a snapshot; patching a lead does not rebuild an existing queue row.**

**Fix.** `_refuse_unvariabled_leads` reads every lead the run touched back
from the provider and refuses the attach unless our variables are on it — an
invariant over `ids` rather than a patch to one branch, because `ids` is
assembled from three paths. The adoption branch writes the copy first.
`adopted` is counted separately in the report. Controls (a) and (b) of the
incident gate (`5c9fb515`) cover the rendered queue itself.

**Containment, 2026-09-23 22:4xZ.** 85 of the 91 were already stopped; the
2 still `in_sequence` were stopped and read back `stopped`; the 4 `replied`
stay `replied` — **the provider will not move a `replied` lead to `stopped`**
— and all four have **0 sendable rows**, verified per lead. **Removal from
the campaigns was NOT done: there is no remove-lead-from-campaign route on
`bison.WRITE_ROUTES`**, so it needs a new write verb and an operator decision.

Tests: `tests/test_a_blank_email_can_never_be_sent_again.py` (24), and the
factory fakes now RENDER — `tests/fakebison.RendersTheQueue` substitutes
variables into the step template and substitutes nothing where one is absent,
so this regression fails in the suite instead of in production. A
`scheduled_emails` stub returning `[]` would have kept all 782 tests green
while modelling away the entire incident.


---

### ISSUE-012 · a company-search slice can never yield more than 400 pages

**Status: MEASURED, not fixed. It is not a bug — it is a ceiling, and the
strategy above it was built without knowing where it was.**

The 2026-09-22 sourcing run left five slices at page 401, recorded as
"hit `MAX_PAGES_PER_SLICE`, not exhaustion. Resumable." **They are not
resumable.** Probed directly on 2026-09-23 against
`Software Development|51_200|United States`:

    page 399   OK, 11 companies        page 401   HTTP 500
    page 400   OK, 11 companies        page 402   HTTP 500
                                       page 450   HTTP 500

`MAX_PAGES_PER_SLICE = 400` coincidentally equals **ContactOut's own
ceiling**. Raising it to 800 and re-running spent zero credits and added
zero domains: all five slices broke on the first request, and the walk
correctly reported *"stopped: slices exhausted EXCEPT 5 that BROKE and were
not walked to the end"* — `4854964b`'s false-completion fix doing its job.

**What this costs.** Three of the five have 273k–326k people behind them on
the free count and are unreachable through that query shape. More generally:

    a single company-search query surfaces at most ~400 pages of companies,
    however large the population behind it is

So "walk the slice until it is exhausted" is not a thing that can happen for
any large slice, and the 48,017 domains are not a partial walk of a reachable
larger set — for the big slices they are at the provider's hard limit.

**The fix is subdivision, not a bigger number.** Narrower industry, tighter
size band, region rather than country — each sub-query landing inside 400
pages. That is a sourcing-design change and an operator spend decision, not a
constant to edit.

Filed beside the Canada finding (`PRODUCTION-HANDOFF-2026-09-23-OVERNIGHT.md`
§1), which is the same lesson from the other end: **what the provider will
not give you is not visible in what it returns.** Canada returned two Spanish
companies and read as done; these slices returned a 500 and read as a cap.


---

### ISSUE-011 · the LinkedIn ownership allowlist went stale and nothing said so

**Status: FIXED in code 2026-09-23, NOT production-verified** — the stop path
it guards has still never run live. See REFUTED-006 for what this is *not*.

`src/inbound.OWNED_SEATS` held the single literal `{174892}` and
`OWNED_CAMPAIGNS` four ids, both read back from the provider on 2026-09-20,
when the account held 86 campaigns of which 4 were ours. Measured 2026-09-23:
the account holds **119 campaigns and 37 are ours** — the 33 `RESONATE
PRODUCTIVE LI B1 SEAT <n>` campaigns, ids 613724-613761, on **33 distinct
seats**, none of them 174892.

So `_positively_not_ours()` answered **True for our own campaigns**, and the
unmatched-reply notification for a reply to one of them would have been
dropped as "positively not ours" with nobody told.

**Why it had not fired.** Provider truth, 2026-09-23: across all 33 B1
campaigns, **75 connection requests, 3 accepted, 0 messages, 0 replies**. The
window was open; nothing had walked through it. Three connections are already
accepted, so the first real reply is imminent.

    was         OWNED_SEATS {174892}            1 seat,   4 campaigns
    provider    613724-613761 + the four       33 seats, 37 campaigns
    readback    docs/state/PROVIDER-CAMPAIGNS.json, 2026-09-20 → 63h stale

**Fix.** `inbound._readback()` / `_owned()` derive both sets from
`docs/state/PROVIDER-CAMPAIGNS.json`, union the literals in as a floor so a
lossy readback cannot make us disown a campaign, and **return `None` — refuse
— when the file is missing, undated, unparseable or older than
`OWNERSHIP_MAX_AGE_HOURS` (24)**. On a refusal `_positively_not_ours` drops
nothing. Refusing costs a notification nobody needed; dropping wrongly costs a
reply nobody saw, and those are not symmetric.

This is the register's own recurring shape — a value true when written, cached
where nothing could notice it had gone stale — and the structural answer it
already prescribes: carry the date and the source, and refuse rather than
answer when currency cannot be proven. `senderheadroom` was the model.

Tests: `tests/test_ownership_readback_staleness.py`, 13 cases including the
2026-09-23 case in both directions. `tests/test_task238_attribution.py` now
pins a fresh readback in `setUp` — its 35 cases are about the drop logic, not
about staleness. Readback refreshed live: 33 seats, 37 campaigns, our B1 reply
kept, a foreign seat still dropped.

**Still open on this:** LinkedIn pushes are HALTED in
`scripts/batch_linkedin_push.py` (`HALT`), and the halt is not lifted by this
fix. The cross-channel stop has never been exercised on HeyReach. Clear it
only when a real reply is shown to stop the email side within 15 minutes.


### ISSUE-001 · Reply ingestion discarded the reply event · CRITICAL · **FIXED `0379958d`**

- **Mechanism confirmed by reading, consequence narrower than first claimed,
  and it never fired.** `store.digest()` is a content hash, `_record` did
  commit a real mutation inside ingest's window, so the outer
  `save(expect_digest=base)` refused. But `_record`'s own transaction
  committed, so **PROVIDER_STOP_CONFIRMED survived** - what was discarded was
  the REPLY_RECEIVED event, its classification and the account pause. And it
  raised rather than failing quietly.
- **Never fired in production:** `_record` is reached only after a provider
  stop has SUCCEEDED, and no reply has arrived on any live campaign.
- **The fix could not be "delete the transaction".** GLM's review caught it:
  `sweep` and the CLI reach `_record` outside any ingest window, where that
  commit is the only write. So the caller declares ownership -
  `persist=True` by default keeps the commit; `inbound._stop_at_provider`
  passes `persist=False` and rides ingest's single save.
- **Both call sites covered**, including the LinkedIn recorder TASK-235 added
  hours earlier, which had inherited the same shape. Both now go through one
  `_stop_event` writer so they cannot drift.
- 8 tests, including one that REPRODUCES the defect and asserts the exact
  asymmetry. 125 green across every inbound-touching suite.

### ISSUE-002 · A DNC could not stop a HeyReach sequence · HIGH · **FIXED `abfc844a`**

- `heyreach.stop_lead_in_campaign` was implemented, on `WRITE_ROUTES`, with a
  fail-closed readback, and had **no caller anywhere**. No LinkedIn
  counterpart to `EMAIL_STOP_LEAD` existed.
- Invisible because `leadstop.sweep` skipped LinkedIn-staged contacts
  **without incrementing `report['checked']`** - it reported clean because it
  counted nobody. Fixed first and separately.
- TASK-235 adds `LINKEDIN_STOP_LEAD`, `stop_linkedin_contact`, per-channel
  sweep counting, and persists `heyreach_lead_id` on the staging path.
  **The seal holds: NOT in SUPPORTED or CONDITIONAL**, verified after merge
  (still 14 verbs). 28 new tests; 135 write-safety tests green.
- **Carried forward:** `_record_linkedin` opens its own `store.transaction()`,
  the same shape as `_record`, so it extends ISSUE-001 to the LinkedIn path.
  It follows the existing convention and diverging would be worse. Fix both
  together.

### ISSUE-003 · The reconciler settled nothing · MEDIUM · **FIXED `ac6f7996`**

- `CHECKABLE = ("heyreach.add_lead",)` while every stuck key is an activate
  verb, so it settled zero and reported success doing it.
- TASK-237 adds both activate verbs and a new UNCONFIRMABLE state, so an
  operation checkable against no provider is settled WITH A REASON rather
  than skipped by a `continue` that printed "0 settled, 0 problems".
- **A guard was added in review:** the loop walks `unsettled()`, which is
  ATTEMPTED *and* UNRESOLVED, and applied one rule to both. Settling an
  UNRESOLVED key FAILED would make it reservable and re-open the
  duplicate-send path REFUTED-001 confirmed closed. Positive evidence still
  settles; absence never does.
- **CORRECTED:** this register previously said 26 unresolved. That counted
  ROWS in an append-only log. It is **18 distinct keys - 14 unresolved, 4
  attempted**, which is what Buggie said. The dry run now leaves 13 for a
  person.

### ISSUE-004 · The dispatcher is starved, and the "stranded" count was wrong · HIGH

**The count this register carried was wrong, and merging on it would have
caused a regression.** Corrected 2026-09-21.

`scripts/task173_scan.py --unintegrated` compares the TASK FILE'S STAGE on
each branch against its stage on master. It does not look at the code. So a
task whose work is already integrated - in a BETTER form - still reports as
"finished on a branch, available on master", and the obvious response to
that report is to merge the branch.

Caught on TASK-232. Its branch carries a `stoppedcause.py` that classifies
from the events feed. Master already carries a NEWER one with a
`NEVER_CONTACTED` outcome the branch lacks, and
`docs/THE-THIRTY-THREE-ANSWERED-2026-09-18.md` says explicitly that the
events feed **could not** have answered the question - it replays ten days
and the memberships are months old. **Merging the branch would have deleted
the classification that actually works and reverted to the approach that
does not.**

Verified integrated and moved to DONE, so the scan stops reporting them:

    TASK-212, TASK-224   no code at all - a finding, already recorded
    TASK-227             the geo ISO fix is on master as 27bcdb67
    TASK-232             master's stoppedcause.py is strictly newer
    TASK-234             integrated as 98b05550
    TASK-237             integrated today as ac6f7996

So the real figure is **6 branches carrying code that is genuinely not on
master** - 067, 213, 214, 225, 229, 230, 231 - and each needs the same
per-branch check before merging, not a bulk merge.

- **Still true:** the backlog empties fast. 0 ready, 0 claims after five
  workers consumed the three briefs written on the 20th.
- **Still true:** 89 stale branches. That noise is what makes the scan's
  output hard to trust in the first place.
- **NEXT:** TASK-229 (READY reservoir) is the highest-value of the six by
  the current mission - it serves cohort expansion directly.

### ISSUE-005 · No notification is delivered anywhere · HIGH

- **Component** `src/notify.py`, `src/providers/slack.py`
- **Impact** **A positive reply on a live campaign would be written to a JSONL
  file and told to nobody.** 216 notifications produced, **207 `unconfigured`**.
  203 of those are `unmatched_reply_needs_review` at severity
  `action_required`, still arriving (last 2026-09-20T18:01Z).
- **Root cause** NOT an engineering defect. `SLACK_BOT_TOKEN`,
  `SLACK_SIGNING_SECRET`, `SLACK_OPS_CHANNEL` and `SLACK_LIVE` are all unset.
  The adapter and the routing table work correctly and refuse without a
  destination, exactly as SLACK-NOTIFICATIONS.md specifies.
- **Blocked on** operator. Channels already exist and must not be created:
  `#resonate-notifications` (C0C34GCAR27) for the global ops channel,
  `#productive-resonate-outbound` (C0ADUMGQX8S) and `#replies-productive`
  (C0BFUF4JRK9) for the per-workspace one.
- **Note a policy conflict before wiring** the standing contract routes
  `negative_reply`, `unsubscribe` and `neutral_reply` to NOWHERE deliberately.
  A recent instruction asks for NEGATIVE_REPLY and UNSUBSCRIBE alerts. That is
  an operator decision and a visible edit to the routing table, not a bug.
  STILL OPEN as of 2026-09-21 and deliberately untouched by the wiring below.
- **UNBLOCKED 2026-09-21T11:3xZ.** The operator set `SLACK_BOT_TOKEN`,
  `SLACK_OPS_CHANNEL` and `SLACK_LIVE` in `config/.env`, on a NEW ops channel
  `#resonate-notifications` (C0C34GCAR27) rather than the `#resonate-notifs`
  this row named. `scripts/slack_smoke.py` posted one message and Slack
  returned `ts 1789990679.422989` - a receipt is only issued for a message
  Slack accepted, so the transport, token, channel and membership are all
  proven together.
- **The backlog is NOT replayed and that is deliberate.** 236 rows now, 15 of
  them today; `scripts/slack_replay_today.py` delivers only rows at or after
  today 00:00Z and stays UNRUN pending an operator decision. All 15 are
  `unmatched_reply_needs_review` from HeyReach carrying no campaign, workspace
  or lead, and they cannot be ours: 605732 has `sent = 0`, so no reply event
  can originate from it. They are the client's inbox traffic arriving on a
  workspace-wide key. See the addendum in `docs/SLACK-ACTIVATION-2026-09-21.md`
  for the two routing options, neither applied.
- **The two per-workspace ids are BOTH Productive, which answers a question
  that was open this morning.** This row already records them:
  `#productive-resonate-outbound` (C0ADUMGQX8S) and `#replies-productive`
  (C0BFUF4JRK9). A session had been trying to pair them against the two
  workspaces carrying a `slack.workspace_channel` policy, `productive` and
  `contactout`, and refused to guess. It was right to: NEITHER belongs to
  contactout. `productive` has two channels serving different purposes, so
  which one is `slack.workspace_channel` and which is `slack.approvals_channel`
  is an operator decision, and `contactout` still has no id at all.
  Both policies still hold channel NAMES, and `slack.post` resolves no names -
  it passes the string to `chat.postMessage` - so they should become ids.
  NOT WRITTEN: `scripts/slack_map_channels.py` reads `conversations.info` and
  refuses unless the names pair one-to-one, which they do not.
- **Status** OPEN, narrowed: the ops channel is LIVE and proven; what remains
  is the per-workspace ids and the NOWHERE-routes decision, both operator
  calls. Global-destination notifications now have somewhere to go.

### ISSUE-006 · The PII guard was red · HIGH · **REOPENED 2026-09-22, green again**

**REOPENED, and the reason is worth more than the fix.** On 2026-09-22 the
guard was red again - 3 of 13 - on files that landed 2026-09-21 and 09-22.

**A RED GUARD WAS CLOSED AS "CATCHES NOTHING" WHILE IT WAS CATCHING THESE.**
That is the sentence this row exists for now. The original entry reasoned that
a red guard catches nothing, so every leak after it went red was invisible -
correct, and it is exactly what happened the second time. The guard was not
silent. It was red, and red was read as noise.

**What it was catching this time**, all of it in TRACKED files on master:

    docs/state/PROBLEM-REGISTER.md      2 prospect addresses on live domains
    src/collision.py                    a prospect address and account domain
    tests/test_an_active_campaign...py  the same, in a docstring
    docs/SLACK-AGENT-HANDOFF-2026-09-22 the client's own mail domain
    docs/HEYREACH-CADENCES-2026-09-21   an agency name and a seat-holder
    docs/MERGE-REQUEST-...-PHASE-C1     a live sending domain
    scripts/slack_question_catalogue.py two agency names
    src/slackagenttools.py              a live sending domain stem
    src/slackconversation.py            the same
    tests/test_a_client_can_never...py  a sending domain and a seat-holder
    scripts/batch1_build.py             our own mail domain
    src/clientapproval.py               a real agency domain
    tests/test_client_approval...py     the same

**FOUR OF THEM WERE MINE, WRITTEN TODAY.** Documenting ISSUE-014 and ISSUE-018
in this very register meant quoting the live rows that proved them, and the
quotes carried real prospect addresses into git. The register's own rule -
"every row names its evidence" - is what did it. Evidence can be named without
being identifying, and from now on it is: `<prospect-a>@example.test`,
`<account-c>.example.test`, which read the same and resolve nowhere.

Everything is redacted to reserved domains and placeholder names. 13/13 green,
and 218 tests across the suites that use those fixtures pass with the renames.

**Git history still holds the identifiers**, as it did after the 09-17 and
09-18 redactions. Rewriting a pushed history is the operator's decision.

---

### ISSUE-006 (original) · The PII guard was red · HIGH · **FIXED `cecd4223`**

- Red since ~2026-09-18, reported green on the 16th, never triaged. **A red
  guard catches nothing**, so every leak after that date was invisible.
- What it was flagging: two seat-holders' real names and sending addresses
  across five tracked files, and **five real prospects hardcoded** in
  `scripts/build_us_cohort_row_and_approvals.py` - the cohort 489 enrolls.
- Fixed: identifiers redacted in place to placeholders keeping provider ids,
  and the prospect list moved to a gitignored sidecar the script reads,
  refusing when absent. **13/13 green.**
- Git history still holds the identifiers; rewriting a pushed history is the
  operator's decision, as recorded on the 09-17 redaction.

### ISSUE-010 · Zero senders are eligible, on either provider · HIGH

**Not a capacity problem. Answered, re-measured 2026-09-20T19:40Z.**

- **EmailBison** 225 inboxes, 210 connected, 207 healthy, **2,025 measured
  headroom slots**, 210 proven free on some day, 0 that could not be proven
  free. And `HUMAN_IDENTITY_ATTESTED = 0` across all 12 humans, so
  `SAFE_FOR_PRODUCTIVE = 0`. Every unallocated eligible sender classifies as
  **HUMAN_IDENTITY_MISMATCH** - no attested owner - not as
  `NO_COMPATIBLE_CAMPAIGN` or `DAILY_LIMIT`.
- **A second, independent cap:** `MAX_SENDERS_ONE_CAMPAIGN_MAY_NAME = 1`,
  enforced by `executionguard._sender_for` - "a guarded action is attributed
  to exactly one". The usable pool is the MINIMUM of the two, so it is zero
  twice over. This is DESIGN, not a defect: the replacement is already
  written as `docs/SENDER-ATTRIBUTION-DESIGN-2026-09-17.md`, status DESIGN
  ONLY, moving arity from the campaign to the action.
- **HeyReach** 41 accounts, 34 active, 33 with valid auth, and **0
  unallocated** - all 33 are already in campaigns, mostly the client's (we
  own 4 of 86). Classification: **EXISTING_COMMITMENT**. Connection limit is
  40/day per seat; 605732 has used **0** of its seat's 40.
- **So adding senders would change nothing on either channel today.** 487
  waits on an authorized resume, 489 on a stale plan, 605732 on 30 hours of
  graph delay and a weekend. None is a capacity constraint.
- **What must NOT be done:** attest a human to a mailbox to gain capacity.
  Attestation records who genuinely operates an inbox; inventing one
  fabricates the thing the gate checks.
- **3941 / 3930 / 3919 — reconciled 2026-09-21T10:2xZ, read-only, one
  readback each.** This line previously called them DEGRADED and a session
  report the same day called them contention-free capacity. NEITHER IS WHAT
  THE PROVIDER SAYS. All three read identically off `bison.sender_emails()`:

      status Connected · daily_limit 15 · warmup_enabled True
      emails_sent_count 0 · bounced_count 0

  `Connected` is the provider's own status field, so DEGRADED was an
  inference from a zero lifetime count rather than a reading - corrected.
  But they are equally not available capacity: never sent, still in warmup,
  and therefore NOT PROVEN DELIVERABLE, which is exactly how
  `scripts/email_sender_estate.py` labels its own UNCOMMITTED section.
  **Either way they change nothing here**, because this issue's binding
  constraints are `HUMAN_IDENTITY_ATTESTED = 0` and
  `MAX_SENDERS_ONE_CAMPAIGN_MAY_NAME = 1`, and a connected mailbox satisfies
  neither. Not attached anywhere.
- **The bounded, honest unlock** is one genuine attestation of one human to
  one healthy uncommitted mailbox - an operator act, not an engineering one.
- **Status** BLOCKED on operator (attestation) · design exists for the arity
  half · `docs/THE-LATENCY-IS-ATTESTATION-NOT-CAPACITY-2026-09-19.md`

### ISSUE-007 · 489 is planned onto a full mailbox-day while Monday has room · MEDIUM

- `docs/489-COULD-GO-THREE-DAYS-EARLIER-2026-09-20.md`
- **Impact** three days of avoidable latency on a five-lead cohort.
- **Root cause** a stale plan, not a scheduler defect: placed when sender
  3437's Monday book read 16, which has since fallen to 3.
- **Blocked on** operator. The only mechanism is a pause/resume, named twice
  under "what is NOT authorized" in the standing grant.
- **Status** BLOCKED on operator decision

### ISSUE-008 · GLM's last review returned a truncated response · LOW

- Both targets came back `finish_reason='length'` with an empty completion.
  The adapter correctly refused rather than returning `""`. Auth is fine —
  `glm-5.3` verified live at 200 in 1840ms.
- **Fix** smaller review targets, or a raised output budget.
- **Status** NEW

### ISSUE-014 · An ACTIVATED campaign can never be topped up — the continuous-cohort model is deadlocked · CRITICAL

**Found 2026-09-22 by batch 3's push being refused. Nothing unsafe happened;
the guard refused, which is the safe direction. But it refuses forever.**

`batch1_push --live --only ivan` returned:

    FactoryRefused: 20 contact(s) collided with the client's own estate:
    leo-santizo (<prospect-a>@example.test): stop - somebody at this account is
    mid-sequence right now

**The mid-sequence campaign is OURS.** Read per lead at the provider:

    <prospect-b>@example.test  274 sequence_finished 8 · 327 sequence_finished 8
                            352 sequence_finished 5 · 495 in_sequence 0

The client's three campaigns are all FINISHED - which `account_policy` calls
ALLOW, "history, not a live conflict". The only `in_sequence` row is campaign
495, which this system created and activated last night, and which has sent
**zero** emails.

`without_our_staging` exists precisely to remove our own rows, and it excluded
**nothing**. `staging_artifact_evidence(495)` says why:

    ours       true   "claimed by productive/productive-email-batch1-tomislav
                       on both sides"
    zero_send  FALSE  "campaign 495 reads status 'active', which is not a
                       state this system has verified means `not sending`;
                       a campaign that started a moment ago also reports zero"

That reasoning is CORRECT as written. A campaign that started a moment ago
does report zero, and treating `active` as inert would be the unsafe read.

**But it makes the CONTINUOUS grant unsatisfiable.** That grant's whole shape
is batches 2..N filling the eight standing campaigns. The moment those
campaigns were activated, every account they hold began reading `in_sequence`
from our own membership, so every subsequent batch is refused at every
account already enrolled - and the factory refuses the WHOLE stage rather
than skipping the lead, by design.

Measured across the four campaigns sending today: **95 of 95 accounts read
STOP**, and a sampled check found **zero** client-side `in_sequence` rows on
any of them. Every stop is ours.

**THE 13:02Z SENDS ARE NOT AFFECTED and must not be paused over this.** They
are already scheduled, the client's sequences at those accounts are finished,
and nothing here is evidence of a real collision.

**The narrow fix, not yet applied.** The campaign-level `zero_send` arm is the
wrong granularity. The per-lead membership row carries that lead's OWN
`emails_sent` for that campaign, and it reads 0 - which is strictly stronger
evidence than the campaign counter and immune to the "started a moment ago"
objection, because it is the lead's own row rather than an aggregate. So a
membership row may be excluded as our staging when the campaign is ours AND
that row's own `emails_sent` is 0. A lead we have actually emailed still
counts, which is what the guard is for.

Deliberately NOT applied under time pressure an hour before the first
provider-confirmed batch send in this project's history. It is a collision
safety path and it gets tests first.

- **Status** OPEN · blocks every batch after activation · batch 3 is written
  to canonical state (515 records, 1,719 steps approved) and waiting on it

### ISSUE-015 · The planted-cohort-name guard flags ordinary English · HIGH

**Measured 2026-09-22 while pushing batch 3. It is a guard PRECISION defect,
not a copy defect, and it blocks three of five campaigns.**

`bisonfactory._check_greetings` check 3 flags a lead whose BODY contains any
other cohort member's first name, as a whole word, case-insensitively. Across
the five campaigns carrying batch 3:

    kresimir   269 record/name pairs, overwhelmingly name='Will'
    bernarda     4   'Rich', 'Terri', 'Sandy', 'Sobe'
    tomislav     2   'Russell', 'Star'
    ivan, fran, bojan, jakov, luka   clean

**`Will` is a first name and an ordinary English auxiliary verb.** One cohort
member named Will makes every body containing the word "will" a defect. The
rest are company names that contain a person's name: `<account-e>.example.test`,
`<account-f>.example.test`, `<account-g>.example.test`, `<account-h>.example.test`,
`<account-i>.example.test`. Every one of the 275 is a false positive.

Checks 1 and 2 in the same function scan `first_line` - the greeting. Check 3
scans the whole body, and that is where the imprecision comes from: the
hi-jacob defect is a MIS-PERSONALISED GREETING, and a body legitimately
contains ordinary prose and the recipient's own company name.

**The guard is not wrong to exist and must not be widened to pass a draft.**
The rule in CLAUDE.md is explicit, and dropping 269 records from kresimir to
satisfy an imprecise check would destroy a batch for no safety gain. The fix
is precision - flag a name where a greeting would put it, not anywhere in
prose - and it is a copy-safety path, so it gets tests and it does not get
written an hour before the first provider-confirmed batch send.

- **Status** OPEN · blocks batch 3 on kresimir, bernarda, tomislav · ivan and
  fran pushed clean

### ISSUE-016 · `attach_leads` reports REFUSED on a write that succeeded · MEDIUM

Pushing batch 3 into campaign 493 raised:

    emailbison attach_leads: the provider answered 200 but 2 of 22 leads are
    not in campaign 493 on readback: [204342, 204343]

The provider had applied it. Read immediately afterwards, 493 holds **22
leads and 22 scheduled rows** - up from 20 - and both named leads resolve to
the two batch-3 contacts at `admarketplace.com`. The membership readback was
simply taken before the provider made them visible on that route.

The docstring already records one fix for this exact symptom - the readback
used to list the campaign's members, which serves fifteen rows whatever it is
asked for, and now asks about the named leads instead. This is the remaining
half: the named-lead read is exact but not immediately consistent, and there
is no retry.

**The failure direction is the expensive one.** A refusal on a successful
write invites a re-run, and it leaves canonical state unwritten while the
provider holds the leads - so the campaign row does not record record_ids the
provider already has. `attach_leads` is idempotent on both sides, so a re-run
is safe, but "safe to re-run" is not the same as "reported correctly".

- **Fix** a bounded retry on the after-read, the same shape `stop_lead`
  already uses, and only then raise.
- **Status** OPEN · worked around by reading the provider after every push

### ISSUE-017 · The re-engagement inventory stores a lane that goes stale with campaign status · HIGH

**Found 2026-09-22 while acting on the operator's approval of the
re-engagement copy. I reported the supply as missing, and it was not - the
stored value was.**

`work/stage/reengagement-inventory.jsonl` carries a `lane` per lead, written
at walk time. Read today it says:

    NEVER 1360 · UNKNOWN 38 · ACTIVE 17 · REENGAGE 0 · REVIVE 0

The morning handoff recorded 973 REENGAGE / 37 REVIVE / 379 UNKNOWN / 17
ACTIVE / 9 NEVER, and the file has not been rewritten since 09-21 21:53, so
one of the two had to be wrong.

**Neither was. The lane is DERIVED FROM CAMPAIGN STATUS and was cached.**
`lane_for` reads:

    if state in STOPPED_STATES:
        if campaign_live:
            return NEVER, "... an unknown stop is a NEVER by the rule"
        ... else classify on age -> REENGAGE

So the same lead is NEVER while its campaign is running and REENGAGE once that
campaign is archived. Recomputed against the campaigns' CURRENT statuses -
3 archived, 1 draft, 1 completed, 1 paused, 10 active:

    NEVER 89 · ACTIVE 17 · REENGAGE 985 · UNKNOWN 287 · REVIVE 37

which matches the handoff's shape and its REVIVE count exactly. The supply is
real; the stored lane is a cached value on a decision path, which is the
recurring defect this register's closing section already names.

**What it nearly cost.** I told the operator the 973 REENGAGE leads did not
exist and that there was nothing to enroll against copy they had just
approved. That was wrong, and it was wrong in the direction of inaction rather
than of sending - but a session that believed it would have idled the largest
untouched supply in the estate.

**The geography is the real constraint, and it is not what anybody assumed:**

    262  480  PRODUCTIVE - MARKETING AGENCY - AUSTRALIA   archived
    263  214  v2 PRODUCTIVE - MARKETING AGENCY - AUSTRALIA archived
    264  289  PRODUCTIVE - MARKETING AGENCY - USA          archived
    481    2  RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS paused

**694 of the 985 are Australian**, and Australia has no campaign window - the
same constraint that held 46 Australians out of batch 3. The actionable
US-first supply is **289**, not 973.

### RESOLVED, and the diagnosis was narrower than the first write-up

**`report()` was never wrong.** It already fetched live campaign statuses and
recomputed every lane, and it has always answered REENGAGE 985 / REVIVE 37 /
NEVER 89 / UNKNOWN 287 / ACTIVE 17. The canonical path was correct the whole
time.

**`walk()` was writing a lane it had no basis for.** The line was
`row["lane"], row["why"] = lane_for(row)` — called with NO campaign status. So
every stored lane was computed as though no campaign were live, and the stored
text does not even match the current classifier's wording, which means the
file also predates a change to it. A field that is stale, unbasis'd and
authoritative-looking, that the only correct consumer ignores.

So the defect was never a wrong count. It was a decorative field that invited
exactly one misreading, and got it — mine.

**Fixed:**

- `walk()` now passes the campaign's status, and writes `lane_at_walk`,
  `why_at_walk` and `campaign_status_at_walk`. The bare `lane` key is gone: it
  read as current truth and was not.
- `lanes_now(statuses=None, path=None)` is the one way to read the inventory.
  It recomputes every lane against current status and deliberately does not
  consult what was stored. `report()` is now a thin caller of it.
- `live_statuses()` REFUSES rather than returning a partial map. A campaign
  missing from that map reads as not-running, which reclassifies its stopped
  leads — so a partial map silently moves leads between lanes.
- The unreadable-statuses path used to print a warning and carry on, and its
  own warning said what that costs: "every stop will be read as the lead's
  own, which OVER-counts NEVER". It now raises `StatusesUnreadable`. A count
  nobody can trust is worse than a refusal, because it looks like an answer.
- 7 tests, including the defect in one assertion — the identical row is NEVER
  with its campaign live and REENGAGE with it archived — and one proving a
  stored lane that disagrees is not believed in either direction.

- **Status** FIXED · `--report` output unchanged before and after, which is
  the point: the canonical answer never moved

### ISSUE-019 · The candidate pipeline passes ICP REVIEW as though it were IN · CRITICAL

**Found 2026-09-22 while producing the first candidate export the operator
asked to send Productive. The export was stopped. Nothing was sent.**

`_icp_verdict` survives on `QUALIFIED` **or** `REVIEW`:

    if status in (icp.QUALIFIED, icp.REVIEW): survived.append(company)

REVIEW means "not enough evidence to decide", which this register already
settled in REFUTED-002 - those records carry no criterion at `fail` and are an
enrichment task rather than a verdict. Passing them writes undecided accounts
into the candidate list as though they had qualified.

**What 1,508 candidates actually contain:**

    median headcount 16,745 · min 9,620 · max 130,377
    under 20 staff   0 of 1,508
    countries        US 416 · India 133 · Brazil 117 · France 86 · UK 77
    industries       retail 138 · banking 109 · government administration 100

    <large-bank>.example.test      Santander, 130,377 staff, Spain, banking
                       icp_score 0.0, icp_status "review"
    <a national education ministry>  the French Ministry of Education

Productive sells to 20+ person marketing and creative agencies in eight named
markets. A zero-scored bank is in the list.

**IT BREAKS THE PREMISE OF THE 2026-09-22 AMENDMENT.** The operator authorized
post-filtering explicitly "because S3 re-verifies headcount and country per
domain for free and only IN domains proceed". S3 does not restrict to IN, and
with no headcount or geo filter available at the source there is nothing else
between AI Ark's 72.6m-row index and the candidate list.

`why_matched` reads "scored above threshold" on every row including the 0.0
ones. That column is the evidence a client reads.

**The harder question underneath.** AI Ark sorts by headcount DESCENDING and
its headcount filter does not exist, so reaching agencies of 20-200 people
means walking a very long way down 726,580 pages. 40-50k qualified agency
domains may not be reachable through `company_search` at all - a provider
question rather than a tuning one.

- **Status** OPEN · export STOPPED and nothing sent to the client · the fix
  (QUALIFIED only) is one line but changes what "supply" means, so it is the
  operator's call

### ISSUE-024 · The channel-exclusion list was English-only in a Croatian workspace · HIGH · **CLOSED 2026-09-22**

Operator decision, 2026-09-22: the Slack history monitor never pulls a
finance, payroll, HR, admin or credentials channel. Implemented in
`scripts/slack_history.py` (`SENSITIVE_TERMS`, `is_sensitive`), which matches
NAME **and** purpose/topic, folds Croatian diacritics before matching, and
fails CLOSED on a shape it cannot read.

**The first version of the list was English-only, and it read `#računi`
straight past** - Croatian for invoices, in a workspace whose people write
Croatian every day. A safety list in one language has a hole in it exactly
where the local team files the invoices. Croatian terms added and folded, so
`racuni` catches `računi` and `place` catches `plaće`.

**Excluded today, of 21 member channels:**

    #računi                 matched `racun`   - invoices. The real catch.
    #finance-weekend-team   matched `finance` - SEE BELOW

**`#finance-weekend-team` was a FALSE POSITIVE, and is now allow-listed.**
"Finance Weekend" is a Resonate campaign, not a finance function - the estate
holds `campaign_Finance weekend199_replies_*.csv`. Operator confirmed
2026-09-22.

**Fixed with a NAME-LEVEL ALLOWLIST (`ALLOWED_BY_NAME`), not a weaker term.**
Narrowing or dropping the `finance` term to let this one channel through
would stop excluding real finance rooms, which is the entire point of the
list. Naming the single exception keeps the term intact and makes every
future exception something somebody has to write down. A test asserts both
halves: the campaign channel passes AND `#finance`, `#finance-ops` and
`#team-finance` are still refused.

**So one channel is excluded today: `#računi`.** 20 member channels pull.

The other 19 member channels are pulled as before. Raw history stays in
`work/`, gitignored. Tests: `tests/test_a_payroll_channel_is_never_pulled.py`,
10 of them, including the innocuous-name-sensitive-purpose case and
fail-closed.

### ISSUE-023 · QUALIFIED is as wrong as REVIEW was, and the export still cannot ship · CRITICAL

**Found 2026-09-22 while implementing the operator's QUALIFIED-only ruling for
ISSUE-019. The ruling is implemented and correct. It does not rescue this
export, because the QUALIFIED bucket is defective in the same direction.**

Of the 1,508 candidates, **114 are QUALIFIED and 1,394 are REVIEW.** The 114:

    median headcount 16,996 · min 9,620 · max 121,205
    under 20 staff        0 of 114
    in the 20-200 range   0 of 114
    industries            software development 62 · telecommunications 24
                          advertising services 11
    icp_score             0.0 on 58 of them, 8.0 on 55, 16.0 on one
                          median 0.0

The top rows by headcount are a Spanish telecom at 121,205 staff, a Swedish
one at 107,286, a Finnish one at 101,120 and a US cable operator at 96,438 -
all four **QUALIFIED at `icp_score` 0.0**. Productive sells to 20+ person
marketing and creative agencies in eight named markets.

**A ZERO SCORE THAT READS QUALIFIED IS THE DEFECT.** `score()` returns a
`structural` verdict alongside the numeric one, and a record can take
`icp_pass` structurally while scoring nothing. Geography contributes
`"status": "not_required"`, which is how `why_matched` comes to say **"Other
is a market this client sells to"** - a sentence that passes every country.
`why_matched` still reads "scored above threshold" on eight rows that scored
0.0, and that column is what the client reads.

**So the ISSUE-019 fix was necessary and is not sufficient.** Dropping REVIEW
removes 1,394 undecided rows; it does not remove a 121,205-employee telecom
that the scorer affirmatively qualified. Shipping the 114 would send a client
who sells to small agencies a list of 62 enterprise software companies and 24
telecoms, which is worse than shipping nothing.

- **Status** OPEN · the export is STOPPED for the second time and nothing has
  been sent · the QUALIFIED-only ruling is implemented (`4afb54d5`) and stands
- **Not a tuning question.** Two separate gates - the REVIEW pass and the
  structural-pass-at-zero-score - both admitted enterprise accounts. The
  scorer's threshold semantics are the thing to settle, and that is the
  operator's call, not a weight to nudge.

### ISSUE-020 · Successive sourcing runs re-walked page one and added nothing · MEDIUM · **FIXED**

`domains_already_known()` removes what is held, so a run that always starts at
page 1 re-fetches the same companies, discards every one as already known, and
adds NOTHING. Measured 2026-09-22: the loop reached 1,508 candidates and then
ran eleven further rounds adding zero, because AI Ark's order is stable -
sorted by staff descending - so every round saw the same first pages.

Fixed: the page position is persisted beside the candidate list and each run
continues from it. Verified - a fresh run resumed at page 17 and sourced 319
companies none of which were already held.

### ISSUE-022 · The store's atomic write loses to a concurrent reader on Windows · HIGH

**Found 2026-09-22 pushing batch 3, and it is not a batch-3 quirk.**

    productive-email-batch1-tomislav  REFUSED PermissionError: [WinError 5]
    Access is denied: 'work/queue.jsonl.122688.tmp' -> 'work/queue.jsonl'

The 23MB temp file wrote perfectly. The `os.replace` that makes it live was
denied. On Windows a rename over an open file fails, and this estate runs
ELEVEN python processes that read `work/` continuously - six bison watchers,
the heyreach watcher, reply watch, notify-deliver, digest and the Slack agent.

So the store's atomic-write contract holds on POSIX and is probabilistic here,
and the moment it is most likely to lose is a batch push: the one write that
matters, taken while every watcher is polling.

**The failure direction is the good one and that is why it needs recording.**
The replace failing means the OLD file survives intact - no partial write, no
corruption. What is lost is the WRITE, and the caller reported REFUSED, so
nothing believed it had succeeded. A retry a minute later succeeded and
campaign 495 went 26 -> 60 leads. But "retry until the readers blink" is not a
durability model, and a write that silently needed three attempts would look
identical to one that needed none.

**It also leaves litter that looks like state.** Three abandoned temp files sit
in `work/` right now - 23MB from today, 9MB from 2026-09-14, and one from
09-15. A future session reading the directory sees files named like the queue.

- **Fix** retry the replace with a short backoff and raise only after, the same
  shape `attach_leads` now uses for its readback (ISSUE-016); and sweep stale
  `*.tmp` on startup. The stronger answer is the SQLite store infra landed
  today, which is inert by design and takes a lock rather than a rename.
- **Status** OPEN · worked around by retrying · no data was lost

### ISSUE-011 · The forward book's COVERING property decays silently as campaigns are created · HIGH

**Found and worked around 2026-09-22. The census is not wrong; its state file
goes stale in a way nothing reports.**

`bison_forward_book_census` derives its campaign set from the provider - F-002
fixed the hardcoded list and the fix is sound. But the DERIVATION HAPPENS AT
WALK TIME and the result is frozen into `work/forward-book-census.json`. The
18:50Z walk on 2026-09-21 correctly derived `{327, 328, 352, 481, 487, 489}`.
By 2026-09-22 the bookable set was fourteen: 491-498 had been created and
activated overnight and held **243 scheduled rows on the same attested
mailboxes**.

- **`freshness()` still said FRESH** - 16.2 hours, inside the 24-hour window -
  because freshness asks when the walk ran, not what it walked.
- **`completeness()` still said COMPLETE**, because every walk it holds did
  reach its end.
- **`coverage()` is the one that would have caught it**, and only if the
  caller passes the CURRENT bookable set. A caller that passes
  `walked_campaigns(state)` - the obvious thing to pass - is asking the state
  whether it covers itself, which it always does.

So the handoff's 1,470 counted 243 booked slots as free. Corrected figure for
2026-09-22 is **1,301 free first-step slots**, and it also revealed that
496/497/498 have ZERO room today and through the 25th while 493 has two.

**Worked around, not fixed:** the walk was extended over 491-498 (243 rows, 19
pages) and the state now covers all fourteen. The defect is that nothing made
that necessary visible. The structural fix is the one the register's closing
section already names - a cached value on a safety path carries the source it
was derived from and refuses rather than answers when it cannot prove it is
current. Here that means the state file should record the campaign set as
derived AT WALK TIME and `freshness`/`coverage` should re-derive and compare.

- **Status** OPEN · worked around for today · `docs/THE-7-DAY-BOUNCE-STOP-2026-09-22.md` is unrelated; the correction itself is in the 2026-09-22 batch-3 stats post

### ISSUE-012 · The collision gate refused a batch's whole supply as NOT WALKED · HIGH · **FIXED**

`batch_eligibility.collision_cleared()` read `work/stage/batch1-candidates.json`
- the 868 addresses batch 1's walk cleared on 2026-09-21 - and refused every
account outside it. On 2026-09-22 that refused **5,488 verified contacts on
3,080 accounts**, and the refusal reason is NOT_WALKED rather than COLLIDES.

Fail-closed is the right direction and the gate was not unsafe. The defect is
that a cached clearance from an earlier batch was standing in for the current
question, and the report said "collision: account not cleared", which reads as
a collision finding rather than as a walk nobody had run.

- Fixed by `scripts/s6_collision_walk.py` - resumable, checkpointed, records
  ALLOW/HOLD/STOP beside the estate verdict, and carries a domain the provider
  could not be read for as REFUSED rather than folding it into clear.
- `collision_cleared()` now prefers the fresh walk and keeps batch 1's file as
  a fallback, unioned so a re-run cannot go backwards.
- **Measured on the walk:** roughly 27% of accounts come back ALLOW. Batch 3's
  supply is that set, not the 850 rendered - of which 636 are people already
  enrolled, 195 are deferred at accounts already in a batch, and 19 are
  Australian with no campaign window.

### ISSUE-013 · `batch_eligibility` could not finish · MEDIUM · **FIXED**

`clientapproval.is_approved()` re-reads a 7.4MB, 24,711-row journal on every
call when `rows` is None, and the walk called it once per candidate. At 9,140
candidates the run did not finish - it was killed twice at fifteen minutes
with no output, which looks identical to a hang.

Fixed by loading the ledger once and passing it through. The gate is unchanged
and it now reads one consistent snapshot rather than re-reading a live file
per candidate, which is also the stricter reading of "walk every gate again".

### ISSUE-009 · Two model workers are invisible to credential health · LOW

- `ZAI_API_KEY` (GLM) and `XAI_API_KEY` (Grok) are absent from
  `config.VARIABLES`, so `scripts/credential_health.py` structurally cannot
  report on them. That is the honest failure by design, and it is still a gap.
- **Status** NEW

---

## FIXED THIS SESSION — regression-tested, pushed

| ID | Issue | Commit | Tests | Production |
| --- | --- | --- | --- | --- |
| F-001 | The write guard refused every HeyReach READ. The live 605732 watcher survived only because it predates the guard by 3h and holds the old module in memory; any restart would have killed the only LinkedIn monitor | `28f4766e` | 13 new, verified by disabling the exemption | **PRODUCTION_VERIFIED** — `provider_truth.py` completed live against all four HeyReach campaigns |
| F-002 | The forward-book census walked a hardcoded 3 campaigns while 6 can book a mailbox, so `senderheadroom` REFUSED every mailbox and capacity planning had no input at all | `d321c2ef` | 11 new, verified by breaking paging and by re-adding `paused` to the terminal set | **PRODUCTION_VERIFIED** — derived set matches the provider exactly; 487 and 489 headroom answerable again |
| F-003 | `active_campaign_ids` defaulted to `()`, making `coverage()` pass vacuously — the exact trap that produced a wrong ROOM reading for 489 earlier in this same session | `c9ddf35d` | 6 new, verified by restoring the old default | not yet — no production caller exists |
| F-004 | `senderheadroom` counted weekdays from 0 while the repo is ISO, so `sending_days=geo.windows()["days"]` read Mon-Fri as Tue-**Saturday** | `5ff914d1` | 3 new, one end-to-end through `geo.windows` | not yet — no production caller exists |
| F-005 | LIVE-READINESS.md and PRODUCT-GAPS.md asserted `SUPPORTED = ()`, "nothing sends" and "a pedal that is not connected to anything" while 14 verbs were enabled and a real email had been sent | `03d9da3f` | docs; corrections marked in place | n/a |

## FIXED EARLIER — verified still fixed today

| ID | Issue | Evidence |
| --- | --- | --- |
| F-006 | The stop button did not stop EmailBison 487: `staged_already` refused the pause before the transport, because a state-SETTING verb was being deduplicated by material fingerprint | `repeatable` is now declared in `providerwrites` (`98b05550`, TASK-234). Verified present 2026-09-20 |
| F-007 | `python -m src.scalesim` overwrote the live queue — 550 companies and 277 contacts, in a gitignored directory with no git recovery, three times per published benchmark run | `55ccb7b6` (TASK-233) |
| F-008 | `senderheadroom.walked_at` took the NEWEST stamp, so a walk resumed today read as fresh while carrying days-old rows | now takes `min()`, with the reasoning in the docstring. Verified 2026-09-20 |
| F-009 | The geo resolver matched country NAMES while the evidence is a two-letter CODE | `27bcdb67`, 2026-09-17 |

## PRODUCTION_VERIFIED — the first one, and it took the whole project to get here

### EmailBison 489 sent a real email at 2026-09-21T13:34:48Z

**This is the first provider-confirmed send in this project's history.** Every
prior claim of progress was a campaign reading `active`, a lead reading
`in_sequence`, or a row reading `scheduled` - and the register's own rule is
that none of those is a send.

Three independent witnesses, read back before it was believed, because the
watcher's own alert says to:

    campaign counter      emails_sent 0 -> 1, updated_at 13:34:51Z
    the scheduled row     id 22341193, status `sent`, sent_at 13:34:48Z,
                          against scheduled_date 13:34:00Z
    the watcher           SEND on the counter AND SEND on the queue row,
                          which are its two deliberately separate witnesses

`bounced 0, replied 0, unsubscribed 0`. Seven rows remain `scheduled` of eight.

**WHAT THIS DOES AND DOES NOT SETTLE.** It settles that the whole chain works
end to end: approval, staging, activation, the scheduler, a healthy mailbox
and the provider's own sending window. It does NOT settle deliverability -
one accepted send is not an inbox placement - and it is one email, not a
campaign. Do not let `emails_sent 1` be read as a cohort in flight.

It also satisfies the SEND half of the push gate for the 24k track. The other
half is unchanged: operator approval per batch of 500 READY, before any push.

No write was made to 489 at any point today. It re-planned itself on
2026-09-20T22:01Z and sent on its own schedule. The pause/resume proposed on
Sunday and correctly refused would have achieved nothing except risk.

---

## OPERATOR DECISIONS — 2026-09-24

**491 RESUMED, on the operator's authority.** Zvonimir Bešlić, 2026-09-24.
The client did not answer within the stated window and the technical case was
clean: 0 blank rows sendable, 273 of 273 leads carrying every used variable,
0 foreign leads, watcher live. Recorded on the provider write itself as the
`allow_writes` reason, so the authority travels with the action rather than
living only here. Read back `paused -> active`, 274 `sending_paused` became
274 `scheduled`, 0 pending blanks.

**Who paused it is still unknown and that is now a closed question**, not a
pending one: no provider rule did it (no auto-pause setting exists, limits
were 945 not zero, all 63 mailboxes `Connected`, no account or campaign event
in a feed window spanning the pause, 1 bounce in 322), and no Resonate
session did it. It was a person in the client's workspace.

**CREDENTIAL ROTATION DEFERRED.** Zvonimir Bešlić, 2026-09-24. Five values
were found live - OpenRouter, a Slack bot token, a Slack app token, a 24-char
value from `work/slack-history/`, and the Apify proxy password this session
printed into a transcript. **The operator has deferred rotation**, judging
the on-disk redaction sufficient for now. Do not raise it under NEEDS ME
again and do not block work on it. Recorded here so a later session finds the
decision rather than rediscovering the exposure and escalating it a third
time.

---

## EXCLUDED — named, decided, and not capacity

### The 51 mailboxes of three identities · operator decision, Zvonimir, 2026-09-21

**<seat:dcea4084e023>, <seat:a4f632be942d> and <seat:9a5813964024> are NOT to be used.** Not added
to the roster, not attested, not named as a sender in any campaign. The
operator has not confirmed they are real people, and an attestation records
that a real named human operates a mailbox - so attesting them would record
the one thing this module exists to prevent.

They were never added: verified 2026-09-21, 0 of their 51 mailboxes carry an
attestation and no roster entry exists for any of the three.

**THIS ROW EXISTS SO NOBODY READS THEM AS CAPACITY WAITING FOR A NAME.** They
are 51 Connected mailboxes with 15/day limits each, they will keep appearing
at the top of any headroom ranking, and a future session that sees
`SAFE_FOR_PRODUCTIVE = 159` against 210 connected inboxes will find exactly
this gap and be tempted to close it. It is closed deliberately.

Their history, recorded because it was asked for separately and because a
future argument for using them should have to answer it:

    identity          mailboxes   lifetime sent   bounces   bounce rate
    <seat:dcea4084e023>             17           8,947       165         1.84%
    <seat:a4f632be942d>             17           8,911       161         1.81%
    <seat:9a5813964024>             17           8,878       200         2.25%
    -------------------------------------------------------------------
    EXCLUDED, all three      51          26,736       526         1.97%
    attested nine           174         171,645     1,423         0.83%

**Their bounce rate is 2.4x the attested estate's.** That is not why they are
excluded - identity is - but it means nothing is being given up. Reversing
this needs a named operator confirmation that these are real people, not an
engineering judgement that the mailboxes look healthy.

---

## REFUTED — kept so they are not resurrected

| ID | Claim | Why it is wrong |
| --- | --- | --- |
| REFUTED-001 | The 26 `unresolved` ledger keys permit a re-attempt and risk a duplicate send | Three independent refusals — `require_clear`, `reserve` under the lock, and `perform`'s ATTEMPTED-only check. Buggie attacked this and it held. The interrupted-write window on the facing path is correctly fail-closed. ISSUE-003 is about reporting, not safety |
| REFUTED-002 | The 215 ICP_REVIEW records are a backlog awaiting a human verdict | Zero of the 215 have any criterion at `fail`, none carries a contact, all are still `queued`, and 184 hold no company evidence at all. It is an enrichment task. Carried as an operator action in three consecutive handoffs |
| REFUTED-003 | Cohort expansion is blocked on an unauthenticated ContactOut | Four credential names were invented. Real names verified, ~36,700 credits remain. `docs/THE-CREDENTIAL-WAS-THERE-ALL-ALONG-2026-09-20.md` |
| REFUTED-004 | HeyReach 605732 has stalled — no connection request in two days | The graph spends 3h + 3h + 1 day before `CONNECTION_REQUEST`, and 09-19/09-20 were the weekend on a Mon-Fri campaign. `error_code` is null on all three leads and every one reads `InSequence`. The falsifier can only run on Monday |
| REFUTED-005 | 487 was paused by the provider, or by a decision about the campaign | An audit agent's throwaway probe paused it at 2026-09-20T12:44:45Z by passing a bare dict to `orchestrator.pause`. Nobody decided anything about 487, which is why resuming it overrides no judgement. **12:44:45Z is correct and stands** - it is the campaign's own `updated_at` at the provider. A 2026-09-21 forensic note gave 12:47:36Z; that is the WATCHER's observation time, the moment `bison_watch_loop` next polled and printed `STATUS 487 active -> paused`, and it is 171 seconds later because the loop runs at `--interval 180`. Provider time and observation time are different clocks and the provider's is the one this row records |
| REFUTED-006 | HeyReach replies were never ingested, so the reply-stop has been failing live and email stops were missed | **No stop was missed, because no reply arrived.** The 33 conversations behind `replywatch.json`'s `ambiguous_identities: 33` are the CLIENT's traffic on seats we share with them — the HeyReach key is workspace-wide and the inbox holds 26,973 conversations. Of the 400 most recent, 12 end with a correspondent message and **none matches any record in our store**. Provider truth: our 33 B1 campaigns have sent 75 connection requests, 0 messages, and received **0 replies**. Separately, `inbound._positively_not_ours` was misread as gating the stop — it gates the unmatched-reply NOTIFICATION only, inside the `unmatched`/`unknown` branch, and the `applied` stop path never consults it. The real defect is ISSUE-011, which is visibility, not a missed stop |

---

## The pattern under most of these

Six of the rows above are the same shape: **a value that was true when it was
written, cached somewhere that had no way to notice it had gone stale.**

    a hardcoded campaign list          F-002
    a hardcoded credential name        REFUTED-003
    a 0-based weekday constant         F-004
    a safety claim in a document       F-005
    a scheduler plan against an
      old forward book                 ISSUE-007
    a verdict computed before the
      resolver was fixed               REFUTED-002

The standing correction — **ask the thing that knows** — covers all six. The
registry names the credential, the provider names its campaigns, `geo` names
the weekday convention, and the queue can be re-qualified. Where a literal
stands in for one of those, it will drift, and nothing will report it.

The structural response is not more vigilance. It is that a cached value on a
safety path carries the date and the source it was derived from, and refuses
rather than answers when it cannot prove it is current. `senderheadroom`
already does exactly this and it is the model: complete, covering, fresh, or
REFUSED.
