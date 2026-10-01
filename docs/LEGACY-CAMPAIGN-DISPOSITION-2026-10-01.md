# Legacy campaign disposition — proposed, 2026-10-01

**THIS IS A DOCUMENT. NOTHING WAS WRITTEN TO ANY PROVIDER.** Every number
below came from a `GET`. No stop, archive, pause, resume, activate, enrol,
attach or create was issued, no credit was spent, no source file was changed.
What this proposes needs the operator's explicit `APPROVED` before any of it
runs, and §5 is written out precisely so that approval is one step.

Measured at **2026-10-01, 10:10–10:40Z**, from the production root, against
the live EmailBison instance. Authority for every campaign-level number is the
provider: `bison.campaign(id)`, `bison.scheduled_emails(id)` and
`bison.membership(id)`. Authority for the record-side numbers is
`work/queue.jsonl` through `src/store.py`. Where the two disagree the provider
wins, and the disagreement is reported rather than smoothed.

## 0. THE THREE THINGS THAT CHANGED WHILE MEASURING

**491 IS NO LONGER UNKNOWN. It is 182 pending rows and 268 pending people.**
The refusal was real — `scheduled_emails(491)` raises `PartialInventory`
("45 pages to walk and this read stops at 40") at the default `PAGE_CAP`. The
adapter's own escape hatch settles it: `scheduled_emails(491, cap=80)`
completes, and `_paged` still compares the accumulated count against
`meta.total`, so the walk is complete or it raises. 665 rows, 45 pages, total
matched. See §6 for what remains UNKNOWN about 491 anyway, because every
monitor in this repository still reads it at the default cap and is still
blind.

**A ROW WITH AN EMPTY SUBJECT IS QUEUED IN 481 AND IT IS DUE TODAY.**
Row `22364357`, sequence step 4730, `thread_reply: false`, subject `''`
(genuinely empty, not whitespace), body 511 characters, scheduled
`2026-10-01T12:49:00Z`. A non-thread-reply row with an empty subject is not a
convention — it is the exact shape of incident A, the 77 emails with an empty
subject and a `<p></p>` body on 09-23. Four barriers are the only reason it
has not gone out. **It is the single strongest argument for disposing of these
campaigns rather than leaving them paused**, and it moves 481 to the front of
the queue despite being one of the smallest.

**1,708 OF 1,737 PENDING ROWS ARE ALREADY DUE OR OVERDUE.** A resume is not a
gradual restart, it is an immediate release. The earliest overdue row is
`2026-09-25T14:02Z`. The daily caps do not contain it: the eleven campaigns
carry 5,145 emails/day of cap between them, 3,000 of it on 503/504/505 alone.

## 1. THE PER-CAMPAIGN TABLE — measured read-only from the provider

The twenty campaigns `work/campaigns.jsonl` claims through
`bison_campaign_id`. That list is the ownership authority used here; the
provider carries no owner field, so a campaign our ledger does not claim is
not treated as ours (§6).

| id | status | leads | sent | pending rows | pending people | REPLIED | last send | cap/day |
|----|--------|------:|-----:|-------------:|---------------:|---------|-----------|--------:|
| 451 | completed | 1 | 1 | 0 | 0 | no | 2026-09-14 | — |
| 481 | paused | 23 | 0 | **10** | **9** | no | never | 20 |
| 484 | draft | 0 | 0 | 0 | 0 | no | never | — |
| 485 | draft | 10 | 0 | 0 | 0 | no | never | — |
| 487 | paused | 10 | 6 | **14** | **10** | no | 2026-09-28 | 20 |
| 489 | paused | 5 | 10 | **5** | **5** | no | 2026-09-25 | 5 |
| 491 | paused | 333 | 411 | **182** | **268** | **YES — 11** | 2026-09-25 | 945 |
| 492 | paused | 206 | 245 | **122** | **165** | **YES — 11** | 2026-09-25 | 705 |
| 493 | paused | 22 | 22 | **40** | **20** | no | 2026-09-23 | 195 |
| 494 | paused | 76 | 95 | **50** | **68** | **YES — 1** | 2026-09-25 | 180 |
| 495 | archived | 60 | 42 | 0 | 0 | no | 2026-09-23 | — |
| 496 | paused | 43 | 3 | **1** | **1** | no | 2026-09-24 | 75 |
| 497 | completed | 20 | 7 | 0 | 0 | **YES — 1** | 2026-09-23 | — |
| 498 | completed | 15 | 10 | 0 | 0 | no | 2026-09-24 | — |
| 500 | paused | 0 | 0 | 0 | 0 | no | never | — |
| 501 | completed | 1 | 1 | 0 | 0 | **YES — 1** | 2026-09-25 | — |
| 503 | paused | 250 | 25 | **473** | **248** | no | 2026-09-25 | 1000 |
| 504 | paused | 223 | 14 | **431** | **222** | **YES — 1** | 2026-09-25 | 1000 |
| 505 | paused | 217 | 25 | **409** | **217** | no | 2026-09-25 | 1000 |
| 506 | completed | 1 | 1 | 0 | 0 | **YES — 1** | 2026-09-25 | — |
| | | | | **1,737** | **1,233 pairs** | **28 replies** | | |

**THE TWO PENDING COLUMNS ARE DIFFERENT QUESTIONS AND NEITHER IS WRONG.**

*Pending rows* are `scheduled_emails` rows whose status is `sending_paused` —
the queue, what would actually be transmitted. 1,737 of them; the ten the
brief names sum to exactly **1,555**, reproduced to the row (503→473, 504→431,
505→409, 492→122, 494→50, 493→40, 487→14, 481→10, 489→5, 496→1), and 491's
182 sits on top as the brief said it would.

*Pending people* are members whose `lead_campaign_data` status for that
campaign is `sending_paused` — the population. 1,233 lead-campaign pairs.

They diverge in both directions and the direction matters:

    503/504/505   MORE ROWS THAN PEOPLE  (473 rows / 248 people)
                  ~2 queued steps each. The row count overstates reach.
    491/492/494   MORE PEOPLE THAN ROWS  (268 people / 182 rows)
                  86 people in 491, 43 in 492 and 18 in 494 are
                  `sending_paused` with NO queued row at all today.

The second is the dangerous one. EmailBison's scheduler rebuilds rows at the
end of every sending day — measured 2026-09-21, when 489 re-planned itself
three days earlier with no write from us. So **1,737 is a floor on what a
resume releases, not a ceiling**: 147 people currently hold no row and could
acquire one.

**THE REPLY COLUMN IS READ FROM `status`, NOT FROM A COUNT.** The trap was
checked explicitly rather than assumed: across all 1,488 people read, 28
memberships carry `status: replied`, and for all 28 the row's own `replies`
field and the lead's `overall_stats.replies` are ≥ 1. **Today the trap does
not fire on our estate.** It is still the rule — `status` decided this column —
and 503 is the case that proves why it must be: the campaign-level `replied`
counter reads 0 there, and the only thing that could contradict it is a member
status, so the counter was never allowed to answer on its own.

Corroboration, bounded and not authority: the newest page of `GET /replies`
(15 rows) carries 9 rows from 352 and 6 from 327 and none of ours — 7 tracked
replies, 7 bounces, 1 of our own outgoing emails in the same feed. That is a
head read of a workspace-scale feed, not a walk, and the per-campaign
membership status remains the authority.

## 2. RECOMMENDED DISPOSITION, PER CAMPAIGN

Three verdicts. **STOP** means `stop-future-emails` for the named members.
**LEAVE** means nothing is approved and nothing is done. **ARCHIVE is
recommended for nothing** — §4 explains that it is not reachable from this
codebase at all and that what it does to rows is unmeasured.

### STOP — 11 campaigns, 1,737 rows, 1,224 distinct people

| id | rows | people | reason |
|----|-----:|-------:|--------|
| **481** | 10 | 9 | **DO THIS ONE FIRST AFTER THE REHEARSAL.** Holds the empty-subject row due 2026-10-01T12:49Z. Never sent a single email (0 sent against 23 leads), so there is no conversation to protect and nothing to lose. |
| 496 | 1 | 1 | **THE REHEARSAL.** One row, one person. Whether `stop-future-emails` works on a *paused* campaign is UNKNOWN (§6); this is the cheapest possible place to find out. |
| 489 | 5 | 5 | Paused by the operator by hand on 09-28 for this exact reason — old copy, no signature, no opt-out. 10 sent, 0 replies. The pause is reversible by one click; a stop is not. |
| 487 | 14 | 10 | Same 09-28 pause, same reason. 8 of its 14 rows are already overdue. Its resume grant from 09-21 is SPENT and must not be reused; a stop retires the campaign instead of leaving a spent grant next to a live queue. |
| 493 | 40 | 20 | Same 09-28 pause. 22 sent, 0 replies, 20 rows overdue. |
| 494 | 50 | 68 | 1 real reply, already protected by its own `replied` status. The other 68 are mid-sequence on copy with no CTA. 18 of the 68 hold no row today — stop the people, not the rows. |
| 492 | 122 | 165 | 11 real replies. The campaign has already proved it reaches people; everything still queued is the un-gated copy that produced them. 1 pending person is live in an active campaign we do not own. |
| 491 | 182 | 268 | 11 real replies, 411 sent, the largest sent volume of ours. 86 pending people hold no row today. All 182 rows overdue. |
| 503 | 473 | 248 | Never approved under the 09-30/10-01 gates; 0 CTA links, 0 opt-out routes, 248 of its rows carry no question either. 2 bounces already. 3 pending people are live in an active campaign we do not own. |
| 504 | 431 | 222 | As 503. 1 reply, already protected. Exactly 1 of its 431 rows carries anything resembling an opt-out. 2 pending people live elsewhere. |
| 505 | 409 | 217 | As 503. 25 sent, 0 replies, every row overdue. 1 pending person live elsewhere. |

**The shared reason, measured rather than asserted.** Of the 1,737 pending
rows: **0 carry a CTA link** (no `http(s)` URL in any rendered body — this is
`copylint`'s sense of CTA, the `cta_link_*` rules), **1 carries any opt-out
route at all** (one row in 504; 1,736 carry none), 687 carry no question mark
either, and 1 carries an empty subject. The bodies are read rendered, from
`scheduled_emails`, so this is what a person would actually receive and not
what a template claims. And **0 of 3,005 stored approvals bind any of it** —
§3.

### LEAVE — 8 campaigns, 0 rows, 0 people, nothing to approve

| id | status | reason |
|----|--------|--------|
| 497 | completed | 0 pending rows, 0 pending people. 19 members `stopped`, 1 `replied`. Needs nothing. |
| 498 | completed | 0 pending. All 15 members `stopped`. Needs nothing. |
| 501 | completed | The 09-24 stop test. 1 member, `replied`. Needs nothing. |
| 506 | completed | The 09-25 stop test. 1 member, `replied`. Needs nothing. |
| 451 | completed | The 09-13 canary. 1 member, `sequence_finished`. Needs nothing. |
| 495 | archived | Already archived. 0 pending rows; 59 members `stopped`, 1 `bounced`. Needs nothing. |
| 485 | draft | 10 members, all already `stopped`, 0 queue rows. A stop here would be a write that changes nothing. |
| 484 / 500 | draft / paused | 0 leads, 0 rows. Empty. |

A stop on any of these eight would be a provider write with no effect on any
person, which is the one kind of write that is never worth an approval.

### OUT OF SCOPE — not ours, or not ours to decide

**327, 328, 352 — not touched, by order.** Owner UNKNOWN and not knowable from
the provider; the operator is asking the client. Nothing in this document
reads or proposes anything against them beyond the memberships of OUR OWN
leads, which §3 had to read because that is where the risk is.

**418, 502, 423, 424, 274 and the pre-May archived set** — `work/campaigns.jsonl`
does not claim them, so they are not ours to dispose of. 502 is paused and
418 is active and still sending.

## 3. THE RECIPIENTS QUESTION — who is actually in there

**1,233 pending lead-campaign pairs resolve to 1,224 DISTINCT PEOPLE.** Nine
people sit in two paused campaigns each (9 in 481∩487, which is also why 481
and 487 should be approved together). Nobody is in three.

Counts only below. No address, name, company or lead id is recorded in this
repository by this measurement, and none was written to any file under `docs/`.

### Have any of them since replied, unsubscribed or bounced elsewhere?

    replied in another campaign            1       (in 352 — not ours, ACTIVE)
    unsubscribed in any campaign           0
    bounced in any campaign                0

    in_sequence RIGHT NOW in an ACTIVE
    campaign we do not own                 6       (all 6 in 352)

**Seven people of the 1,224 are mid-flight somewhere else**, and they are the
reason this is the part that matters. They sit in 492 (1), 503 (3), 504 (2)
and 505 (1). 352 is active, still sending, and its owner is UNKNOWN. Stopping
them in our campaign does not interfere with 352 — a stop is per
campaign-membership, not per lead record (§4) — so **the disposition is safe
for all seven, and archiving instead of stopping would not be**, because
archive's effect on a membership is unmeasured.

The zero on unsubscribed and bounced is a real zero, read from each person's
whole `lead_campaign_data` array across every campaign they belong to, not an
absence of evidence: 1,488 people were read and every one of their campaign
memberships was classified.

### How exposed are these people already?

    also hold a row in a campaign we do
    not own (274/327/328/334/352/262/263)   304  of 1,224   (24.8%)
    of those, in an ACTIVE one              302  of 1,224
    never received a single email from us
    (overall_stats.emails_sent == 0)         429  of 1,224   (35.0%)
    received at least one                    795  of 1,224

**429 people have never been emailed at all.** For them a resume is not a
re-touch, it is a first impression made with copy that carries no CTA and no
opt-out. That is a stronger argument for stopping than the re-contact risk,
and it was not visible from the row counts.

The 304 figure is the one to watch over the next days: a quarter of our
pending population also sits in the estate whose ownership the operator is
currently asking the client about. If those campaigns turn out to be the
client's, 304 of these people were being approached twice from the same
workspace. That does not change the disposition — stop is still right — but it
does change what has to be said to the client, and it belongs in that
conversation rather than in this one.

Not alarming, stated so nobody later reads it as alarming: all 1,224 carry
`lead.status: unverified` at the provider. That is EmailBison's default and it
does not gate anything — `docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md`
records that the provider does not require verification before attach. Our own
verification lives in `channels.email_verdict`, not here.

### The part of this that our own ledger cannot see

**682 of the 1,224 (56%) have no `bison_lead_id` on any contact in
`work/queue.jsonl`.** 805 contacts in the store carry a provider lead id;
542 of our pending people match one. This is load-bearing for §5: the audited
stop path, `leadstop.stop_contact`, is record-driven and refuses with
`StopRefused` for a contact with no `bison_lead_id` — "do NOT search by
address and guess". So it can reach 542 of these people and not the other 682.

## 4. WHAT A STOP OR AN ARCHIVE ACTUALLY DOES — read from `src/providers/bison.py`

### Stop — `bison.stop_lead(campaign_id, lead_ids)` (line 1000)

**The function the operator would be approving.** `POST
/campaigns/{campaign_id}/leads/stop-future-emails`, declared in
`bison.WRITE_ROUTES` as "stop ONE person".

- **What it touches.** The membership row only — `lead_campaign_data[].status`
  for that one campaign moves to `stopped`. **It does not touch the lead
  record**: no field on `/leads/{id}` changes, the lead stays in the
  workspace, its other campaign memberships are untouched. This is what makes
  it safe for the seven people live in 352.
- **Is it reversible?** **From this codebase, no.** There is no un-stop route
  in `WRITE_ROUTES` and `_allow()` refuses any path not on that list, so
  nothing here can undo it. And `stopped` is deliberately absent from
  `RESUMABLE_STATES` while `sending_paused` is present — the module's own
  comment says `sending_paused` "reverses the moment somebody resumes", which
  is precisely why today's state is not safety. A stop converts a reversible
  state into an irreversible one. That is the point of it, and it is the part
  that needs the approval.
- **One call or many.** One `POST` per campaign carries the whole
  `lead_ids` list. The *verification* is many: `stop_lead` reads
  `membership(campaign, ids)` first, which is **one `GET /leads/{id}` per
  named person**, then polls the same read after the write until every named
  lead reads as stopped, then takes a 2-page `_sample` before and after as a
  blast-radius check that reports its own denominator. For 503 that is ~250
  GETs before, ~250 per poll attempt, and 1 POST — call it 10–20 minutes for
  the largest campaign. **It raises rather than reporting an unconfirmed
  stop**: the route answers 200 for a lead it does not hold and does nothing,
  so the status code is explicitly not the proof.
- **It refuses rather than partially acting** if any named lead is not in the
  campaign.

### Archive — THERE IS NO SUCH FUNCTION, AND THAT IS THE ANSWER

`src/providers/bison.py` contains no archive function and no archive route.
`WRITE_ROUTES` names twelve paths and archive is not among them, so
`_allow("PATCH", "/campaigns/503/archive")` raises before any request is
built. The same is true of campaign DELETE. This is already on the record:
`docs/BISON-ARCHIVE-ROOT-CAUSE-2026-09-16.md` ruled out "we archived them"
on exactly this basis.

So **"archive" is not a disposition this system can perform.** It is a thing a
person can do in the EmailBison UI, and what it does to 473 queued rows is
*inferred*, not measured: 495 is archived and its 114 rows read 72 `stopped`
and 41 `sent` with 0 pending, which is consistent with archive stopping rows
but is one campaign and not a controlled observation. `archived` is also in
none of `bison.py`'s classification tuples — not `STARTED_STATES`, not
`NOT_STARTED_STATES` — so a preflight that reads a status falls through every
branch on an archived campaign and still says PASS.

**Recommendation on archive: stop first, archive second or never.** An archive
without a stop leaves 1,737 rows in a state nobody has measured, inside a
status our own code cannot classify. A stop leaves them in `stopped`, which
every reader here understands. If the operator wants the estate tidy
afterwards, archiving by hand in the UI *after* a confirmed stop costs
nothing and risks nothing.

### For completeness — pause is not a disposition either

`bison.pause_campaign` (line 1974) is `PATCH /campaigns/{id}/pause` and reads
the status back. All eleven are already `paused`, and pause is reversible by
one click on `/resume` — which is the whole problem this document exists to
close.

## 5. THE EXACT INVOCATION — WRITTEN OUT, NOT RUN

**NOT RUN. NOT APPROVED. Requires the operator's explicit `APPROVED`.**

One campaign per invocation. Not a loop over all eleven: the blast radius of a
typo in a loop is the whole estate, and the per-campaign `EXPECT` below is the
guard that makes each call refuse if the provider has moved since this
document was measured.

Order: **496 first** (one person, the rehearsal — it also settles the UNKNOWN
about whether the route works on a paused campaign), then **481** (the
empty-subject row), then 487+489 together, then 493, 494, 492, 491, then
503, 504, 505.

```sh
# NOT RUN — awaiting operator APPROVED.
# Run from the production root. Substitute CID/EXPECT from the table below.
PYTHONUTF8=1 PYTHONPATH=. py -3 -c "
from src import providers
from src.providers import bison, load_env
load_env()

CID, EXPECT = 496, 1          # <- one campaign, one expected count

ids = sorted(l for l, s in bison.membership(CID).items()
             if str(s).lower() == 'sending_paused')
if len(ids) != EXPECT:
    raise SystemExit('REFUSING: campaign %s holds %d sending_paused members, '
                     'the approval was taken against %d. Re-measure before '
                     'stopping anybody.' % (CID, len(ids), EXPECT))

with providers.allow_writes(
        'docs/LEGACY-CAMPAIGN-DISPOSITION-2026-10-01.md: operator APPROVED '
        '<date>. Stop legacy rows: old copy, 0 CTA links, no opt-out, '
        '0 of 3,005 approvals valid.',
        only=('stop-future-emails',)):
    print(bison.stop_lead(CID, ids))
"
```

    CID  EXPECT          CID  EXPECT          CID  EXPECT
    496       1          493      20          503     248
    481       9          494      68          504     222
    489       5          492     165          505     217
    487      10          491     268

`EXPECT` is the **pending-people** count, not the row count: the stop route
takes lead ids, so the population is what it addresses. Stopping 1,224 people
retires all 1,737 rows and the 147 rows the scheduler has not built yet.

Three properties of that command, each deliberate:

- **`only=('stop-future-emails',)`** scopes the authorization to the one
  route. Resume, pause, attach and create stay refused for the duration, so a
  mistake inside the block cannot start a campaign. Note that `allow_writes`
  matches URL **fragments**, not function names, and that the scope is a
  `ContextVar` — it is **not inherited by `ThreadPoolExecutor` workers**, so
  this must stay single-threaded as written.
- **The reason string is mandatory** and ends up in the provider-write ledger.
  Fill in the approval date before running; `allow_writes` refuses an empty
  reason.
- **It derives the ids from the provider at run time** instead of carrying a
  list of 1,224 lead ids in a repository file. That keeps PII out of git and
  makes the `EXPECT` check meaningful.

**What this command does NOT do, stated so it is not discovered later.** It
calls the adapter directly, so it writes no record-side history: no
`leadstop._record` event, no `providerwrites` ledger entry, no
`stop_event` on the contact. For the 542 people who *do* have a
`bison_lead_id` binding, the audited path exists and is better —
`py -3 -m src.leadstop --live` / `leadstop.sweep(live=True)` — but it cannot
reach the other 682 (§3), and running both would stop the same people through
two paths with two different audit trails. **Proposed: one path for everybody
(the command above), and a single disposition note appended to this document
recording what was stopped, when, on whose approval.** The operator should
confirm that trade rather than inherit it.

## 6. UNKNOWN — and REFUSED IS NOT ZERO

**491's queue is readable here and still UNREADABLE to every monitor.**
Settled for this document at `cap=80`. But `hard_stop_check.py`,
`bison_watch_loop` and `slackagentreadback` read it at the default, and on
2026-09-23 that refusal took down a whole snapshot —
`work/heartbeat/bison-491.json` read `READ-ERROR 122x PartialInventory` for
hours. **The number is established; the blindness is not fixed.** Any claim
about 491 from one of those readers is UNKNOWN, not zero. Filed as a task, not
raised as an operator question.

**What a resume would release is a FLOOR, not a figure.** 147 people are
`sending_paused` with no queue row today (86 in 491, 43 in 492, 18 in 494).
The provider's scheduler rebuilds rows at the end of each sending day, so
what they would receive is UNKNOWN until it is built. 1,737 is the minimum.

**Whether `stop-future-emails` works on a PAUSED campaign.** Never exercised
against one. The stop tests (501, 506) ran against campaigns that were
sending. The route is documented per campaign-membership with no stated
campaign-status precondition, and `bison.py` records no precondition, but
absence of a documented precondition is not evidence there is none. **This is
why 496 goes first.** If it refuses, the whole §5 plan is UNKNOWN and needs a
different route, not a retry on a bigger campaign.

**Whether a stop can be reversed at all.** From this codebase, no — there is
no route. Whether the EmailBison UI can return a `stopped` membership to
`sending_paused` is UNKNOWN and was not probed, because probing it means
writing. The operator should approve on the assumption that it cannot.

**What archive does to a queued row.** Inferred from one campaign (495),
never measured causally, and unreachable from code. UNKNOWN. §4.

**Who owns 327, 328, 352, 418 and 502.** Not knowable from the provider —
EmailBison's campaign record carries no owner, creator, user, team or tenant
field, confirmed across all 29 listing keys. `work/campaigns.jsonl` begins
2026-09-02 and claims none of them. The operator is asking the client. **302
of our 1,224 pending people hold a row in one of those campaigns and 7 are
live or have replied there**, so this UNKNOWN sits directly on top of the
disposition. It does not block it — stop is right either way — but it must be
resolved before anyone reports to the client on who contacted whom.

**Whether anything replied that the membership status does not show.** The
reply feed was read for one page (15 rows, newest first) as corroboration. A
complete walk was not done and is not cheap. The per-campaign membership
status is the authority and it was read in full for all twenty campaigns; the
feed is a second opinion that happened to agree.

## 7. THE BARRIERS, RE-MEASURED 2026-10-01 — there are FOUR, not three

    killswitch, layer 1   push.run(live=True) -> LiveSendNotEnabled:
                          "live push is not implemented in this build"
    killswitch, layer 2   tagsync.send -> TagSyncRefused, unconditionally
    sending.live          killswitch.workspace_state('productive') ->
                          {'sending': False, 'why': 'sending.live is off
                          for productive'}
    approvals             0 of 3,005 valid
    THE FOURTH            providers.writes_allowed() ->
                          (False, 'no RESONATE_PROVIDER_WRITES and no
                          allow_writes() scope')

The fourth was not in the brief and belongs in the count: the transport itself
refuses every provider write, for the stop route as much as for a resume
(checked against the literal stop URL, not just the default). It is also the
barrier that §5 deliberately lifts, for one route, for one block — which is
the right shape for an approved write and worth seeing stated next to the
others.

**The approval number, re-measured rather than quoted.** `work/queue.jsonl`
holds 1,584 records. 851 of them carry at least one approval stamp, 3,005
stamps in total. Under the words-only question (`approval.is_approved(...,
config=None)`) **2,998 are still valid**. Under the whole question — these
words, from this mailbox, with this signature — **0 are valid.** The reason is
sharper than "they went stale": **0 of 3,005 stamps carry a
`sender_fingerprint` at all**, because none was taken after the binding
existed, and `sender_fingerprint` fingerprints even the absence of a declared
sender so a stamp that recorded nothing cannot match anything. It fails closed
in every direction, by construction.

That gap is also the one barrier that survives somebody turning the killswitch
back on, which is why it is the real one. And it has a visible inconsistency
the operator should know about before reading any dashboard:
`campaigns.approval_is_current` and the reporting surfaces still ask the
words-only question, so they will show "approved" for records the send gate
refuses. 2,998 versus 0 is that inconsistency, quantified.

---

## Reproducing every number here

Read-only. The three walks took about twenty minutes against the live
provider and cost nothing.

```sh
# campaign-level: status, leads, sent, replies, bounces
PYTHONUTF8=1 PYTHONPATH=. py -3 -c "
from src.providers import bison, load_env; load_env()
print(bison.campaign(503))"

# the queue, per campaign. 491 needs the raised cap or it refuses at 40 pages.
PYTHONUTF8=1 PYTHONPATH=. py -3 -c "
from src.providers import bison, load_env; load_env()
import collections
print(collections.Counter(r['status'] for r in bison.scheduled_emails(503)))
print(collections.Counter(r['status'] for r in bison.scheduled_emails(491, cap=80)))"

# the population, per campaign. STATUS is authoritative, never a reply count.
PYTHONUTF8=1 PYTHONPATH=. py -3 -c "
from src.providers import bison, load_env; load_env()
import collections
print(collections.Counter(bison.membership(503).values()))"

# the cross-campaign recipient check: keep the WHOLE lead_campaign_data array
# that membership() filters away, one walk per campaign instead of one GET
# per person. Counts only - never persist the rows, they carry addresses.
PYTHONUTF8=1 PYTHONPATH=. py -3 -c "
from src.providers import bison, load_env; load_env()
rows, total = bison._paged('membership-full',
    lambda p: bison.query(bison.leads_endpoint(503), {'page': p}))
print(len(rows), total, rows[0]['lead_campaign_data'])"

# the four barriers
PYTHONUTF8=1 PYTHONPATH=. py -3 -c "
from src import killswitch, providers, push, tagsync
print(killswitch.workspace_state('productive'))
print(providers.writes_allowed())
try: push.run(day=21, live=True)
except Exception as e: print(type(e).__name__, e)"

# the approvals: 3,005 stamps, 0 valid under the whole question
PYTHONUTF8=1 PYTHONPATH=. py -3 -c "
from src import store, approval, clients
cfg = clients.load('productive')
n = ok = 0
for rec in store.load():
    for ck, steps in (rec.get('cadence') or {}).items():
        for sk, st in (steps or {}).items():
            if isinstance(st, dict) and st.get('approval'):
                n += 1
                ok += bool(approval.is_approved(rec, ck, sk, config=cfg))
print(n, ok)"
```

**Nothing in this document was written to a provider. The disposition it
proposes is not performed, and cannot be performed by anything in this
repository until somebody both approves it and lifts the write gate for the
one route named in §5.**
