# What happened overnight

A durable account of one unattended session, written so that "what
happened overnight?" can be answered from the repository rather than from
a conversation.

Read `MISSION-STATE.md` for the running ledger, `LIVE-READINESS.md` for
what may and may not be promised, and `PRODUCT-GAPS.md` for what
deliberately does not exist.

---

## 1. Executive summary

Twelve commits. Three of them fix defects that a green suite of four
thousand tests could not see, and the shape of all three is the same one
this repository keeps producing:

> **The system computes the right thing and never uses it.**

- `interactions.py` had verified, deduplicated and applied a Slack button
  click since the day it was written. No HTTP route reached it, so every
  Approve button in an approval notification posted to a URL that did not
  exist.
- `stepstate.py` names three terminal states. Two guards read one of them,
  spelled `== "pushed"`, so a step recorded as `confirmed` or `cancelled`
  answered "not sent yet" and could go out again.
- The demo smoke test's screen list was hand-written, so three screens
  added tonight never joined the sweep whose job is catching exactly that.
- `evidence.make` froze a freshness verdict onto each row on the day the
  fact was found, and every reader since trusted it. Approval could not
  catch the drift, because approval is a fingerprint of the *text* and
  the text does not change when the fact behind it gets old.
- Every failing path already recorded its own failure in canonical state.
  There was nowhere to read them together.

The rest is the work the brief named: weekly refresh selection, revival,
observation licensing, and a strict readiness classification.

**Live sending remains disabled**, by construction rather than by a flag.
No provider was called, no message was sent, no Slack message was posted,
no credit was spent.

## 2. Current commit

`8a31fd5`. Working tree clean apart from `AGENTS.md`, which is untracked
and was not created by this session; it is left alone deliberately.

## 3. Checkpoints completed

| commit | what |
| --- | --- |
| `e1b2c59` | Operational health: every recorded failure on one screen, with whether a retry is safe |
| `0595670` | `/slack/interactions`: the HTTP terminator `interactions.py` was written for |
| `9d56560` | Evidence ages; the read paths re-derive it, and a draft whose evidence aged out is held |
| `b75e595` | `refresh.py`: which known accounts are worth spending on again |
| `9dbe380` | `/refresh` |
| `de988bf` | `revival.py`: whether a quiet account has anything new to hear |
| `6534b0d` | `/revival`, including the quiet-with-nothing-new queue |
| `a81bc99` | `observations.py`: what a message may say it noticed |
| `a4efadb` | Cross-tenant tests for the new screens, and `LIVE-READINESS.md` |
| `8331307` | 27 of tonight's guards added to the permanent mutation list, and this report |
| `970aab5` | Every screen swept for Python that leaked into it - and the sweep's own screen list derived from the navigation rather than hand-written |
| `8a31fd5` | All three terminal step states read rather than the one anything writes, and a stale TODO removed |

## 4. Implemented and tested

**Operational health** (`api.operational_health`, `/health`). Reads
failures already in canonical state: failed jobs with what they processed
first, notification rows with `last_error`, tag-outbox rows that failed or
are blocked. Every row carries `retry_safe` and why, because "it failed"
without "and the reply was still recorded" is the sentence that makes
somebody re-run a thing that already happened. The screen names the two
areas it is *not* watching.

**Slack interactions endpoint** (`/slack/interactions`). Above the session
gate, because Slack has no cookie and no CSRF token; it authenticates with
an HMAC over the raw body, checked before a single field is parsed. A
forged request gets 401 and is told nothing else. Anything past
verification gets 200 even when it failed, because a non-2xx asks Slack to
redeliver a permanent failure. An over-long body is drained before being
refused.

**Evidence ageing** (`evidence.recheck`, `usable`, `select`,
`personalization.stored`, `quality._selected`, `eligibility`). Time is the
one input that changes on its own, so it is the only thing re-derived;
relevance is left exactly as scored, because re-scoring it would need the
persona that produced it. `BACKGROUND` had been computed since the module
was written and read by nothing, so a three-year-old article could be the
sentence a cold email led with. A step whose selected evidence is no
longer usable is now `HELD` with an instruction to regenerate.

**Refresh selection** (`refresh.py`, `/refresh`). Staleness per kind with
its own threshold and its own cost read from `enrich.COSTS`. Never-done is
marked and sorted apart from stale. Four states excluded before anything
is ranked. Person credits wait for an explicit ICP verdict. The priority
floor reduces an account to its free work rather than dropping it.

**Revival** (`revival.py`, `/revival`). A timer means re-evaluate, not
send. Four verdicts, and `NEVER` and `NOT_YET` are deliberately not the
same answer. A case requires a new signal, an untouched decision maker, an
unused angle, or an employment change.

**Observation licensing** (`observations.py`). Knowing something and being
allowed to say it are different questions. A signal never licenses a
sentence, and the refusal is explicit rather than by omission.

## 5. Partial

**Message-time context.** The freshness half is closed. What is *not* here
is a full context rebuild immediately before each payload: cross-channel
history is known by `account.touches` and `outreachclaims` and is not
carried in `contextpack`. Eligibility, suppression, replies, DNC, approval
staleness and now evidence freshness are all re-derived at payload time,
which is the part that can block a step. The part that would *change the
words* is not.

**Provider campaign mapping.** `providername` renders the label. Nothing
creates a provider campaign, so the parent/child mapping has no live
counterpart to be validated against.

## 6. Fixture only

Discovery candidates, EmailBison and HeyReach payloads, provider tag sync.
Each is named in `LIVE-READINESS.md` §1 and §3.

## 7. Live validation required

Company enrichment, decision-maker discovery, the verification waterfall,
MX resolution, public research, draft generation, reply polling, Slack
posting, and the new Slack interactions endpoint. `LIVE-VALIDATION-PLAN.md`
is the sequence.

## 8. External blockers

None encountered that stopped local work. Every provider boundary was
implemented up to the wire, marked, and left.

## 9. Provider status

| provider | code | fixture | contract documented | live validated |
| --- | --- | --- | --- | --- |
| ContactOut | yes | yes | yes | **no** |
| Reoon | yes | yes | yes | **no** |
| Deliverable | yes | yes | yes | **no** |
| Apify | yes | yes | yes | **no** |
| EmailBison | yes | yes | yes | **no** |
| HeyReach | yes | yes | yes | **no** |
| Slack (out) | yes | yes | yes | **no** |
| Slack (in) | yes | yes | yes | **no** — new tonight |
| AI/ARK | yes | yes | partial | **no** |

## 10. Personalisation status

`personalization.decide` pools this contact's own evidence ahead of the
company's, and when neither is usable it says so and falls back to a
verified company fact plus persona pain rather than inventing specificity.
That is person, then account, then persona - the segment layer lives in
`strategy` and `contextpack.angles`, which keep "this company's own
evidence supports it" apart from "typical for the vertical, and nothing
here supports it".

Evidence is now re-aged at read time, so a decision made in March is
re-examined in September rather than trusted. `observations` licenses what
may be said about them; `outreachclaims` what may be said about us; and
`claims` refuses a finished draft that says more than either allowed.

## 11. Campaign status

Build, QA, approve and prepare all work end to end against the demo
estate. Approval is fingerprinted and an edit invalidates it. Eligibility
is re-derived immediately before a payload is built, and now includes
evidence that has aged out.

## 12. Reply and Slack status

Ingestion normalises three payload shapes to one event, applies it
idempotently, pauses the company before classifying, and only then
notifies. Slack failure cannot unwind business state. The outbox is
idempotent per occurrence and per workspace. The inbound button endpoint
exists as of tonight and has never received a request from Slack.

## 13. Discovery status

A subtraction, not a search, with seven checks and a named
`LIVE DISCOVERY PROVIDER REQUIRED` on every result. The refresh half - which
known accounts to re-work - was added tonight. Neither runs on a timer,
and both say so.

## 14. Revival status

Complete as a verdict engine. Nothing is sent, drafted or queued.

## 15. Reporting status

Analytics, comparison, per-sender, cohort performance, client PDF and the
report editor all work. Every rate carries its numerator and denominator.
Cohort learning correctly reports `INSUFFICIENT_DATA` at demo volume.

## 16. Security status

Hard workspace scoping through `Repo.for_user`, 404 rather than 403 on a
cross-tenant read, one permission table checked before the handler runs.
Tonight added cross-tenant tests for the three new screens that read the
whole estate and aggregate it - asserted on the *counts*, because that
failure mode is a number that quietly includes another tenant rather than
a visibly leaked row. The credential sweep is derived from the navigation,
so a new screen joins it automatically.

One finding worth carrying forward: removing the permission check inside
an API function failed no test, because the route table was refusing the
viewer on its own. Both gates are now pinned separately, here and on
`/refresh`.

## 17. Scale status

No regression. The measured 30,000-record improvements from earlier in
this session stand; nothing added tonight introduces a per-record file
read. `refresh.plan` assesses priority only for the stalest `scan_cap`
accounts and reports that it did.

## 18. Hosting readiness

`DEPLOYMENT-PLAN.md`, `PRODUCTION-READINESS.md` and `PRE-PRODUCTION.md`
cover it. Nothing was deployed and no infrastructure was created.

## 19. First pilot readiness

A pilot at `PILOT-PLAN.md` scale is a **preparation** pilot today: import,
qualify, enrich, verify, segment, build, personalise, QA, approve, and
inspect the payloads that would have gone out. `LIVE-READINESS.md` §"What
this means for a pilot" gives the ordered sequence for making it a sending
pilot, and every step in it is a human decision.

## 20. Test and mutation results

- Full suite: **4286 tests, OK**
- Offline harness: **4286 tests, OK — nothing reached off this machine**
- Focused mutation work tonight: roughly **seventy mutations applied by
  hand** across the guards added in these nine commits - each applied
  singly, each restored, and each restoration verified byte for byte
  against a copy taken before it. Nine of them survived a first pass. Two
  were bad anchors on my part; the other seven were weak tests, and §21
  lists all nine and what was wrong with each.
- Repository mutation audit: **269/269 mutations caught**, up from 239.
  The 30 new entries cover tonight's guards, so they are permanent rather
  than a one-off hand check.

## 21. What the weak tests were

Recorded because the pattern repeats and is worth recognising.

| what survived | why |
| --- | --- |
| `retry_safe` flipped on a blocked row | the assertion was behind `if rows:` against a fixture that could not produce one |
| failed tag rows never reported | the assertion was on the *area*, which a blocked row from the same fixture satisfied |
| `clean` forced true | nothing asserted the health view ever reports not-clean |
| the "since last touch" signal rule | the fixture also failed the age floor, so either rule alone was enough |
| engagement signals counted as news | the derived signal shared the touch's own timestamp, so the "since" rule refused it anyway |
| contact selection ignored | every fixture contact was selected |
| never-done ordering | nothing compared it against merely-approaching-due |
| the estimate caveat deleted | the assertion was on the word "estimate", which the summary line contains |
| an API permission check removed | the route table refused the viewer on its own |

The common thread: a fixture in which two rules can both refuse, so
deleting either one changes nothing.

## 22. Mutation audit

`tools/mutation_audit.py` removes one safety guard at a time, runs the
tests that should care, restores the file, and reports anything that got
through. Run twice tonight.

The first run - the list as it stood - was **239/239 caught**, and it did
not cover a single line written tonight: the list is fixed, and
`refresh.py`, `revival.py`, `observations.py` and `evidence.py` were not in
it. Every guard added tonight had been mutated by hand and restored, which
proves it once and proves nothing next month.

So entries were added and the audit re-run twice as the work
continued: **266/266**, then **269/269** once the terminal-step guards
described in §24 existed. Thirty new entries in total.

One guard was deliberately left out, and the reason is written where the
list is. Removing the over-long-body drain from the Slack endpoint is
caught about three runs in five - whether the client sees the 413 or a
connection reset depends on socket buffering, and no assertion available
here decides it. An entry that reports MISSED on a working guard two runs
in five is worse than no entry: it teaches whoever reads the tool to skim
past a red line, which is the one thing it cannot afford. The guard is
still covered by `tests.test_slack_route`, which posts four times because
the bug it was written for was intermittent.

## 23. The UX pass, turned into an assertion

`§34` asked for a manual look at the key screens for 500s, tracebacks, raw
reprs and developer-only language. The first three are now swept
automatically for every screen and every role, because a sweep outlasts a
look.

Doing it found the thing the sweep was for, in the sweep itself: the
smoke test's screen list was hand-written, so `/health`, `/refresh` and
`/revival` had silently never joined it. It is derived from the navigation
now and asserted to cover it, which is what the credential sweep already
did and what this file had not.

Nothing leaked. No screen renders a dict, an exception name or an object
repr for any of the five roles. Three planted leaks are caught.

## 24. The last sweep, and what it found

`§35` asks for a TODO audit, a dead-code audit and a computed-but-never-
consumed audit when the feature work is done. All three were run.

**One TODO in the whole of `src/`**, in `lint.py`, saying the cadence
expander must lint the final expanded email and that nothing may enter a
push path unlinted. That work had been done - `cadence.status_for` lints
after expansion and `eligibility` lints again on the exact step a payload
is built from - and the note had stayed. A stale TODO in a safety file is
a small hazard of its own: a reader concludes the guard is missing. It now
says where the guard is.

**Two modules nothing else in `src/` references.** `costsim` is a
command-line tool and is fine. `stepstate` was not: it defines the step
state machine, `DATABASE-MIGRATION.md` names `stepstate.STATES` as the
vocabulary of the status column, and no production code asked it anything.
Both places that need "is this step final" spelled the rule out instead,
as `== "pushed"` - the only terminal state anything currently writes.

That is a latent hole rather than a live one, and it is worth the
distinction. Nothing writes `confirmed` or `cancelled` today. `confirmed`
is what a provider callback would naturally write, and a migration to the
schema that document describes would produce both. Whatever produced the
first one would have found this by sending a message twice.

Both guards now ask `stepstate`. Behaviour is unchanged today, which is
the point: the rule has one home, and the day something writes a third
state the guards are already correct.

## 25. Known product gaps

`PRODUCT-GAPS.md` is the index and was updated tonight with the inbound
Slack row. The gaps that matter most for a first client conversation:
nothing sends, no discovery provider, no CRM connector, no scheduler, and
no volume yet for the learning layer to say anything.

## 26. Exact next human actions

1. Read `LIVE-READINESS.md`. It is the file to read before promising
   anything.
2. Decide whether the first pilot is a preparation pilot or a sending
   pilot. If sending: `LIVE-VALIDATION-PLAN.md` stages 1 to 4, in order,
   each separately authorised.
3. For Slack: set `SLACK_SIGNING_SECRET`, paste
   `https://<host>/slack/interactions` into the Slack app's interactivity
   setting, and press one button. Nothing else proves the endpoint works,
   and without the secret it refuses everything - which is the correct
   direction to fail and is indistinguishable from a wrong secret.
4. Decide what `AGENTS.md` is. It is untracked, it duplicates `CLAUDE.md`,
   and this session did not create it.
5. If the estate is going past ~30,000 records, `DATABASE-MIGRATION.md`.

---

*Nothing in this session sent a message, posted to Slack, called a
provider, spent a credit, or deployed anything.*
