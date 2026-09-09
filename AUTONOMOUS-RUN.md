# Autonomous run state

Resume safety, not a transcript. A session that starts cold should be able
to read this, trust it, and continue at NEXT without redoing anything.

Keep it short. Detail belongs in `PRODUCT-GAPS.md`, the commit messages and
the module docstrings, all of which outlive this file.

## Where things stand

    HEAD                fd54900
    tests               5,244 green
    offline harness     green - nothing reaches off the machine
    live sending        refused in code, not by a flag

## Done in this run

- **Import mapping.** `src/columns.py` maps foreign CSV headers onto
  canonical fields. Personal email and company LinkedIn pages are
  deliberately never mapped; unknown columns are kept as source metadata
  that cannot reach a decision. The upload preview shows how every column
  was read before anything is committed.
- **Scheduler health.** `replywatch.health()` turns the status file into a
  verdict, `/health` lists what is not working, and a failing poller raises
  one CRITICAL notification rather than one per interval.
- **Operator dashboard.** A "Needs attention" section opens the page:
  counts, reasons and links, nothing at zero, severity words shared with
  `notify`.
- **Client dashboard.** A VIEWER gets the funnel in `report.FUNNEL_LABEL`'s
  words rather than the operator's channel-eligibility tiles. Rates carry
  both numbers; `contacted` is confirmed sends only.
- **Work queue.** `src/tasks.py` assembles outstanding work from canonical
  state and stores nothing: a task exists while its condition is true and
  is resolved by fixing the thing. `/tasks` lists it, the dashboard groups
  the same call, and `api._attention` - a second place deciding the same
  question - is gone.
- **Campaign pre-flight.** The campaign page says who the campaign would
  reach and why the rest are held or blocked, in `eligibility.HUMAN`'s
  sentences. The approvals queue carries the same audience, counted with
  the approval gate set aside - "0 of 8" on that screen is circular.
- **Daily digest.** `src/digest.py` assembles what happened in a window
  and what is waiting, and records one notification instead of nineteen.
  Nothing posts; `SLACK_LIVE` still decides that.
- **NOT_NOW.** "Try me in November" is a classification, a date read by
  `ooo`'s grammar with a different cue set, and a task kind of its own
  when due. `oooreturn` reads both dated events rather than gaining a
  twin. Tested after NEGATIVE, so a refusal with a politeness on the end
  stays a refusal.
- **Return-date grammar tightened.** A date with no cue is no longer read
  as a return: "we launched on 3 March" used to resolve.
- **Inbox.** Grouped by what each reply still needs - unmatched,
  unclassified, unread positive - with a tab per canonical category built
  from `replies.CATEGORIES` rather than typed out. Each row carries the
  date its reply left behind.
- **Onboarding.** A super admin can add a client from `/workspaces`: the
  workspace row and a starter config, both or neither. The slug is
  validated before it becomes a filename - `path_for` did none at all.
  The starter carries no ICP and no personas so readiness says they are
  missing.
- **Excel, read without a dependency.** An `.xlsx` is a zip of XML and
  both are standard library, so "save it as CSV first" stops being
  friction on every import. The workbook becomes the bytes a CSV arrives
  as, which is the whole design: the alias table, the formula guard, the
  hygiene screen and the ragged-row report then apply to a spreadsheet
  exactly as they apply to an export, because they are the same code
  reading the same shape. A zip from outside is an attack surface before
  it is a spreadsheet, so a declared unpacked size over the cap, more
  members than an xlsx needs, and a DOCTYPE anywhere in the XML are each
  refused - the last before parsing, because refusing the declaration is
  simpler to be sure of than configuring a parser not to honour it. What
  it gets wrong is written down: the first sheet only, and a date as the
  serial number Excel stores.
- **The five report sections that read keys nothing wrote** are
  assembled - LinkedIn, pipeline, accounts, senders, months - from the
  event log and `account.graph`, reusing the sender report rather than
  counting a reply a fourth way. An acceptance is still never inferred
  from a later message having gone out.
- **Two more numbers that could not be told from another.** A delivered
  count of zero now differs from no delivery instrumentation: nothing
  sent is `n/a`, sent and nothing confirmed is `0`, which is a real and
  alarming number. And the held share counted every contact with no
  address at all under an explanation about verification failure.
- **Reporting, walked back to what writes each field.** Five defects,
  four of them the same shape as this codebase's worst precedent - a
  number computed correctly that means something else. The internal
  report's "Invalid" tile counted `verification["status"]`, a key
  `verification.apply` has never written, so it read zero for every
  workspace forever. "Double verified" meant confirmations obtained on
  the dashboard and providers *asked* in the client report, so two
  providers both answering `unknown` were reported to a client as
  verified. The sender report added `reply_received` and
  `reply_classified` together and counted one message twice - a test
  elsewhere says that exact bug was found and fixed in the workspace
  card, and nobody checked here. `report.funnel` counted `verified` from
  the stored `sendable` flag, which `verification.is_sendable` documents
  as the mistake, and it is what `python -m src.report` prints by
  default. And the operator screen printed the only denominator-free
  rate in the build, as an empty cell when nothing had an address. What
  was not fixed is in PRODUCT-GAPS 20 with the reason.
- **Four from the queue.** An Inbox filter for what a reply
  *carries*, beside the tabs rather than among them: a referral inside a
  polite refusal is classified `negative`, so no tab could ever show it,
  and the work-queue row links at `?carries=referral` instead of a tab
  that would open a page without it. One idea of a domain, so
  `mail.acme.test` stops importing as a company of its own while matching
  `acme.test`'s history - the preview was saying "we have contacted this
  company" about a record that had never been contacted. Every column an
  import kept comes back through `/export/contacts.csv`; a canonical
  `phone` column was considered and refused, because nothing in this build
  would read one and a field consumed by nobody is the defect this
  repository keeps finding. And the age of a verification is reported
  where the manual-review question is asked, without a rule being invented
  to go with it - a legacy verdict is undated rather than stamped with the
  moment it was read, which would have called a two-year-old check today's.
- **The import preview says what a file would cost.** How many of its
  addresses are already cleared to write to, how many are here and not,
  how many are new, and how many provider calls verifying the rest would
  take under this workspace's own waterfall. A plan rather than a spend:
  the import path still reaches no provider, and the estimate is one
  `verification.plan` over the policy rather than one per address - with
  a test that says so, because a loop over addresses is the shape that
  turns into a call when somebody changes it. Sendability is recomputed
  from the evidence rather than read from a stored state, and the test
  that proves the difference is a contact carrying `verified` over an
  empty evidence list - which this repository has had, in its own
  fixtures.
- **A referral can become a contact, and skips nothing doing it.**
  A reply saying "email dana@acme.test instead" now records the address
  as well as the fact, because the reply body is not stored and a count
  leaves the decision unmakeable. `/replies/context/...` offers the
  person it named, with the answer worked out at the moment somebody
  looks rather than read from a status recorded when the reply arrived -
  they may have been added or suppressed since. A name is still not an
  identity and cannot be added at all. Somebody suppressed is refused,
  somebody already here is named rather than duplicated, and what
  arrives is unverified, unselected and in front of every gate an
  imported contact faces. The referral edge is written, because that
  edge has always been "written by a person" rather than "never
  written", and a person clicking a button is that person. Two defects
  found while testing it: the edge collapsed to one row when two people
  were added from one reply in the same second, since an event id hashes
  the time and not who was referred; and a "fix" of mine for re-keying
  turned out to be equivalent to the helper it replaced, so it was
  reverted rather than kept with a comment that taught the next reader
  something untrue.
- **A workspace can say who it sells to, from the product.** The
  readiness checklist has always pointed at `/settings` for "ICP
  configured" and `/settings` could not configure it, so a new
  workspace's first batch was blocked on somebody with filesystem
  access. The market rule, both geo lists and the out-of-market answer
  are settings now, and `/settings/personas` covers the other half:
  name, titles, per-company cap and angles, with the whole set refused
  rather than half applied. Everything here narrows or bounds - a
  persona with no titles can never select anybody and is refused, a cap
  is between one and ten, a blank cap is one rather than everybody, and
  qualification, verification, email security, engagement history,
  suppression, pacing and approval all sit after selection and are
  untouched. Proved on what a selection run keeps and on what a
  subprocess writes into canonical state, not on the value coming back
  out of the store.
- **One answer for a workspace's settings.** `/settings` overrides were
  applied only by `repo.config`, and sixty-odd call sites plus every
  `--client` command line read `clients.load` directly - so a workspace
  that had raised `verification.required_confirmations` to three was
  verifying at two from every command line, and nothing said so.
  `clients.load` now applies them itself, which makes it one read path
  rather than two answers. Proved through a subprocess writing a
  different ICP verdict into canonical state, because the helper was
  never the thing that was broken. An estate where two workspaces claim
  one client has no single answer, so `ensure` refuses to create one and
  `load` refuses to guess - they would otherwise share every record and
  campaign while keeping separate audit trails.
- **Import hardening.** Three defects, and the first was a safety one:
  the hygiene check sat after the branch that attaches a colleague, so on
  a list of five people at one account only the first was ever compared
  against previous outreach, replies and the agency suppression index.
  Every person is screened now and the panel names them. A semicolon or
  tab export is read rather than refused - the delimiter is chosen by
  trying each one and keeping whichever yields a column identifying the
  company, not by counting characters, which is what `csv.Sniffer` does
  and what a quoted company name defeats. A row wider or narrower than
  its header is reported rather than silently trimmed.
- **Two structural guards that were only ever claimed.** `repo.py` said
  "the web layer has a test asserting no request handler calls
  `admin_repo()`" and no such test existed; it does now, over the call
  graph rather than over the text. The route-completeness test regexed
  `path == "literal"` and never saw a `path.startswith(...)` branch -
  which is the class of route that carries an id from the address bar.
  `/slack/interactions` is dispatched from a constant and was invisible
  to both; its answer is that Slack's HMAC stands in for a session, and
  that is now written down where somebody will find it.
- **Cross-channel conversation.** `src/conversation.py` puts one
  person's email and LinkedIn history in one column on the contact page,
  with an arrow saying which way each line went: every touch, each reply
  once rather than three times, what the policy did about it, any date
  they named, and any referral. The derived judgement is deliberately
  narrow - a *confirmed* step whose timestamp is later than a reply from
  the same person is flagged, "including on the other channel" when it
  is, and nothing is claimed at all where a clock could not be read. The
  same person on another record is listed and never merged, on an exact
  identifier only and never across a workspace. The messages themselves
  are not stored anywhere in this build, and the screen says so rather
  than showing empty quotes - PRODUCT-GAPS 16.
- **Digest delivery.** `src/digestwatch.py` puts the daily summary on a
  schedule - off, daily or weekdays, at an hour that is UTC and says so.
  No new state: whether a period has already gone out is derived from
  the notification log, because `notify.plan` is idempotent on an id
  that already carries the period's end. Which is why the window is
  anchored to a scheduled boundary rather than to `now()` - anchored to
  the clock, every tick would be a new period and the idempotency would
  be real but useless. A missed day is caught up from where the last
  digest ended rather than dropped, bounded at seven days, and the
  result says which. It rides `replywatch`'s thread through a new
  `after` hook: one thread, two jobs, switched separately, and neither
  can take the other down. Delivery is attempted rather than left at
  `planned` - with no Slack token that records a refusal, which is the
  honest outcome and a recorded one. A period that was scheduled and did
  not happen is a row on `/health` after an hour's grace; being off is
  not, because nobody chose to have one.
- **Referrals.** `src/referral.py` reads what a reply said about somebody
  else and resolves it to one of four answers, where a name is evidence
  and only an address or a canonical profile is identity. Three decisions
  worth keeping: the rule is ranked *last*, because `reply.on_referral`
  holds where `on_negative` stops and a referral winning would have
  softened a refusal into a pause; the mention is therefore recorded from
  the evidence rather than from the winning category, so a polite refusal
  keeps both halves; and a removal request records nothing at all, since
  a queue item naming a colleague inside a company-wide stop is the worst
  thing this could produce. No edge, no contact, nobody activated -
  `REFERRAL_RECORDED` is still only ever written by a person. The task
  clears when the reply is marked handled, which is canonical state the
  Inbox already owns.

Earlier runs: reply polling on a timer, the reply cursor fixes, verification
evidence bound to the address it was obtained for, out-of-office reading and
the returns queue with its screen.

- **The import had no second step.** `POST /upload/commit` existed from
  the day the upload page did - it reads the parsed preview, writes the
  records and redirects to the batch - and nothing ever rendered a form
  for it. The preview ended at "Parsed, nothing committed" and stayed
  there, so no lead could be imported through the product at all, while
  the dashboard offered importing leads as the first thing an operator
  does. The acceptance suite posted to the route to prove a viewer could
  not reach it, which is true of a route nobody could reach.
  `tests/test_import_commit.py` drives the real page over HTTP: it reads
  the button out of the returned HTML and posts what the button offers,
  so the test fails if the form disappears again. The button states the
  count it will write rather than the count uploaded, and an import is
  now audited - it was the one durable write with no audit entry.

- **A reviewer could approve and could not refuse.** Everything behind
  the decision was already two-sided: the handler reads `action`,
  `orchestrator.decide` accepts "reject", `roles.REVIEWER` is chosen
  because it carries both, and `campaign.rejected` was already an audit
  action. The page rendered one button. Two further defects fell out of
  fixing it. The guard `state != "approved"` compared `approval.action` -
  whose words are "approve" and "reject" - against a status word it can
  never hold, so it never fired and an approved campaign still offered
  Approve; what is offered now is whichever decision would change
  something. And `stale` was derived as `bool(approval) and not current`,
  while `approval_is_current` answers False for a rejection by
  construction, so every rejected campaign came back stale - tagged as
  such on the approvals page and counted on `/diagnostics` as an
  approval needing a reviewer.

- **An Apify run was invisible to the spend audit.** `research.run` took
  a `budget` parameter, the one caller passed one, and the function never
  read it - so an actor run started with no `PROVIDER_CALL_PLANNED`
  event, no waterfall step and no charge. The parameter is the tell: it
  made the call look bounded at the call site. It goes through `spend()`
  now, and `tests/test_research_spend.py` asserts the recording and
  separately asserts what still does not bound it, because a ledger entry
  looks like a limit and is not one - compute units are not credits and a
  zero charge is affordable at any cap.

- **A provider body of the wrong type crashed the run.** Every module
  read bodies as `(data or {}).get(...)`, which is safe against `None`
  and against `{}` and not against a JSON array. A list body raised
  `AttributeError`, which is not a `ProviderError`, so it went past every
  handler written to contain exactly this, out of `enrich.run`, and past
  the `store.save` at the end of the loop - discarding the enrichment of
  every record already processed, credits included. `providers.mapping`
  classifies it as a `ProviderError` instead, and the batch loop now
  contains anything else per record, marked and reported rather than
  swallowed, so the next unexpected shape costs one record.

- **Three safety defects from the parallel audit**, each with the
  mutation that proves the test measures it. `deliverable` matched its
  vocabulary with `word in label`, so `not_deliverable` read as
  `deliverable` and `token_expired` as `ok` - one of the two vendor
  confirmations that make an address sendable, one authorised action from
  arming. A second unclassified reply inherited the first one's verdict,
  so an escalation after a refusal changed nothing. And the reply outcome
  round-trip was wrong in both directions: reading a classifier's word
  against `OUTCOMES` turned an autoresponder into UNKNOWN, and reading a
  policy word against `CLASSIFIER_OUTCOME` turned `wrong_person` into
  UNKNOWN - which the signals suite caught. Both vocabularies are read
  now, and the outcome is recorded on the event where the translation is
  already being done.

- **A parallel audit, and the six defects it found on the sending path.**
  A transport acknowledgement was read as a deliverability verdict, so
  `{"status": "ok"}` supplied one of the two confirmations that make an
  address sendable. A vendor's explicit refusal was outvoted: Reoon's
  `is_safe_to_send: false` was recorded and never read, and a valid
  primary returned VERIFIED before the catch-all branch that would have
  declined it could run. Re-importing a list rebuilt the record and
  erased a do-not-contact. A tenancy refusal printed the reason on the
  page, which made record ids - a deterministic function of the domain -
  an oracle for whether a company was on another client's list. The
  HeyReach poller checkpointed an offset into an inbox with no documented
  ordering. And a missing collection was read as "no replies".

- **Two stop buttons that did not stop anything.** Pausing a campaign set
  `status` and `eligibility._campaign` never read it, so a campaign
  paused because somebody replied still passed the gate that decides
  whether a payload is built. And an unattributable removal request -
  a reply from an alias, a forward, a phone - wrote nothing at all,
  because every replier branch was guarded on a contact key we did not
  have. It widens to the account now, which is what "uncertainty never
  narrows" means when we cannot name the person.

- **`/search` answered questions the pages refuse.** Gated on
  `WORKSPACE_VIEW` and reasoned about entirely in terms of tenancy, which
  is the wrong question: a client-facing viewer, refused `/contacts`,
  `/companies` and `/campaigns`, could read names, titles, addresses,
  domains and campaign ids through it, and matching on `email` made it an
  address-confirmation oracle.

- **The third orphaned path, and the largest.** `orchestrator.prepare` is
  the only setter of `ready_for_review` and the only caller of
  `assign_cadence_arms`, and it had no web caller - so no campaign built
  in the product ever reached the two statuses `/tasks` reports on, and
  the work queue silently omitted its most consequential row. After the
  import's missing Commit button and the approval's missing Reject, this
  one was not a control nobody rendered but a lifecycle step nobody
  called.

- **A test-suite trap, found three times in one day and now guarded.**
  `tests/test_audit.py` reloads `src.providers` to prove no module reads a
  credential at import, and a reload mints a fresh exception class - so a
  test that binds `ProviderError` at module scope passes alone and errors
  under `discover`. It cost two new test files and one existing one.
  `tests/test_invariants.py` now refuses a module-scope import of a
  provider exception, on the import graph rather than on the text.

## Next

The reporting items are done and XLSX turned out not to need a
dependency - an `.xlsx` is a zip of XML and both are standard library.
What is left came out of auditing the web routes against the pages that
reach them, which is the sweep that found the missing Commit and Reject
buttons. None of it is blocked.

1. **`/senders` has no controls.** The page reads sender state and
   renders it; nothing on it changes anything. Whether that is a gap or a
   deliberate read-only view needs settling before it is built, because
   the answer decides whether the missing thing is a form or a sentence.
2. **27 mutating POST routes with no confirmation step.** Not all of them
   want one - the destructive ones do, and the list has never been
   triaged into the two groups.
3. **The audit log truncates at 300 and reports the count as a total.**
   `workspaces.audit` takes a limit and the page prints the length of
   what came back, so a workspace past the limit is told a number that is
   not the answer. Either page it or say which it is.
4. **`data["by_region"]` is a sixth report key nothing writes.** The five
   named above were assembled; this one was found afterwards and is the
   same defect.
5. **An operator override for column mapping**, for a file carrying the
   same header twice. `PRODUCT-GAPS.md` 18.

## Blocked, and why

- **HeyReach reply path** - never live-validated. Needs a real read.
- **Deliverable** - response contract unread; stays UNPROVEN.
- **Slack** - no token, so posting and interactive approval are
  fixture-proven only.
- **Micro-pilot** - blocked on the two above plus the credential rotation
  in `HUMAN-ACTIONS-REQUIRED.md`.

## Standing rules for this run

- A green test is not evidence. Break the behaviour, watch the intended
  test fail for the intended reason, restore, re-run. Eight of nineteen
  mutations survived their first attempt in one earlier batch, and every
  one was a test that measured nothing.
- Never stage while a mutation is applied. Verify restoration with `diff`
  against the pre-mutation copy.
- Stage exact paths. `work/` is real client data and is never committed.
