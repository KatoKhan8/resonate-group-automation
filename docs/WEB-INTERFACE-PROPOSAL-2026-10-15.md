# WHAT THE INTERFACE IS FOR — 2026-10-15

**TASK 0020, lane `webapp`.** Six questions worth a page, derived from what the
operator actually had to have measured today, with every proposed field labelled
TRUSTWORTHY, UNKNOWN or MUST NOT RENDER.

    measured on   b1f290c847eb2500b7eb39987ac34f6d6a8d00d2   (= origin/master)
    worktree      Desktop\resonate-trees\wt-webapp-2026-10-15   branch task-webapp-2026-10-15
    builds on     docs/WEB-SURFACE-INVENTORY-2026-10-15.md (TASK 0010, 63a5d7ef3)

**No page was written. No route, no code, no mockup.** No server started, no
listener opened, nothing under `src/` changed, no provider or network call, no
production `work/` read, suite lock untouched.

---

## 1. THE DERIVATION — counted, not remembered

The brief's rule: *a question that appears three times in one day is a page; a
question nobody asked is not.* So I counted rather than recalled. Across the six
lane files written today — **14,762 lines** — `grep -ci`, per file, summed:

| the question, as the lanes had to ask it | pattern counted | lines |
|---|---|---|
| **is master where I think it is?** | `b1f290c84` | **79** |
| **is a suite running, and who holds the lock?** | `suite.lock` / `suitelock` | **62** / **31** |
| **what is the failing-name set here, and against what?** | `name-set`/`name set` | **69** |
| **what can I not determine?** | `UNKNOWN` | **186** |
| **can this reach a provider, and did it?** | `provider write`/`providerwrites` | **132** |
| **has this been certified?** | `CERTIFIED`/`NOT CERTIFIED` | **39** |
| **is anything listening on the console's port?** | `listener`/`Get-NetTCPConnection` | **9** |

(Reported per pattern, never summed across patterns, because two patterns can
share a line.)

And four the operator asked **in chat**, each recorded in `MIDDAY-2026-10-15.md`
with what had to be measured to answer it:

1. **"Which lanes are alive and what are they doing?"** Asked at 21:12. Answered
   **wrong** by the operator session first — it claimed a running task's `.out`
   file grows, and the redirect in fact fills it once at the end, so 0 bytes is
   what seven healthy lanes look like. The honest answer needed two readings of
   per-process CPU time a minute apart, tied to the lane by the task path in a
   `cmd.exe` command line. MIDDAY: *"that is now three separate ways this trap
   has been hit today."*
2. **"Did this task leave a record?"** At least **five** tasks today did correct,
   mutation-proven work and left no usable record. `DONE/` was measured worthless
   as a status source in **four** distinct ways — lanes write their own DONE
   files, `Move-Item` preserves the original mtime, a task can finish with no
   DONE line at all, and a killed task keeps working afterwards.
3. **"What is between here and a first send?"** Restated as a numbered "Yours"
   list four times in one day (14:16, 17:20, 18:05, 18:55) and again as the five
   remaining items in `DECISION-canary-approval-2026-10-15.md`.
4. **"Is this branch pushed, and does the remote agree?"** `glm-c/0100`'s branch
   was **NOT PUSHED** and that was the finding — the work existed and was
   invisible for four hours.

**Two more that are not counts but are the pattern behind the counts.** Three
times today a documented control turned out not to hold on the path it described
(`api.py:3150`, `app.py:1625`, `api.py:3223`), and once a real, consulted, tested
gate turned out to read a field nothing writes (`suppression/0070`). Every one
was found by accident while looking for something else. **The operator has no
surface that would have shown him any of them.**

---

## 2. THE HARD SPLIT, AND IT IS THE HEADLINE

The brief asks for pages built "from what the system already knows and can be
trusted about". So the first honest act is to say which of the day's questions
the product's own data layer can reach at all. Measured against TASK 0010's
inventory, which enumerated every read in `src/web/`:

| the question | its canonical authority | can `src/web/` reach it today? |
|---|---|---|
| is master where I think it is | git refs | **NO.** No module under `src/web/` reads git. Nothing in the repository's web tier runs a `git` subprocess |
| is a suite running / who holds the lock | `work/suite.lock` via `src/suitelock.py` | **NO.** `src/suitelock.py` is imported by `scripts/run_suite.py` only. `src/store.py` names it in two comments and does not import it; nothing under `src/web/` mentions it at all |
| the failing-name set | `run_suite` logs on disk | **NO** |
| has this been certified | the lane files, on the Desktop, **outside the repository** | **NO** |
| which lanes are alive | the OS process table + `logs/watcher-<lane>.log` | **NO** |
| did this task leave a record | the lane files | **NO** |
| **can this reach a provider, and did it** | `work/provider-writes.jsonl` | **NOT TODAY — and it is one import away.** The file exists, every exit from `providerwrites.perform` writes it, and `grep -rn providerwrites src/web/` returns exactly one hit, inside a docstring |
| is a campaign paused, here and at the provider | local: `work/campaigns.jsonl`. provider: EmailBison | **HALF.** The local half is already on `/campaigns`. The provider half is UNKNOWN and nothing says so |
| who is suppressed and why | `work/queue.jsonl` + `work/agency-dnc.jsonl` | **YES** — `/suppression` already does it |
| what failed, and is a retry safe | canonical state, per subsystem | **YES** — `/health` already does it, well |
| what does this workspace still need | config + state | **YES** — `/onboarding` already does it |

**So: of the eleven questions the operator actually had measured today, six
cannot be answered from inside this product at all, one is one import away, one
is half-answerable, and three are already answered by pages that exist.**

That is the finding, and it decides the shape of everything below. **The
interface earns its place on the one column it owns and nobody else is
watching: what this system did to a provider, and what would stop it doing it
again.** The git/suite/lane/certification questions are the operator's *build
machinery*, they live outside the repository, and a console that scraped them
would be inventing a second authority for facts that already have one — which is
the defect this repository keeps finding. **I am not proposing a lane
dashboard.** If the operator wants one it is a different product with a different
authority, and I would say so rather than smuggle it in as a page.

---

## 3. THE SIX PAGES

Per field: **TRUSTWORTHY** (with what makes it so), **UNKNOWN** (with the
measurement that would settle it), or **MUST NOT RENDER** (with why). Every page
is read-only unless the row says otherwise.

---

### PAGE 1 — THE PROVIDER WRITE LOG

> **What has this system actually written to a provider, and what happened?**

Today nothing anywhere can answer that. `/admin` answers the opposite, from the
wrong ledger: *"No provider call has been made. This build does not make one from
any surface"* (`pages.py:4881`), rendered when `api.provider_health`'s list is
empty — and that list walks `waterfall.ledger(rec)`, the **per-record** paid-
enrichment ledger at `rec["waterfall"]`, which could never record a provider
*write*. Writes land in `work/provider-writes.jsonl`.

**Source.** `providerwrites.ledger_path()` (`providerwrites.py:2266-2272`), read
with `store.read_jsonl`. **No new state, no new writer, no new concept** — the
file is already written on every exit from `perform`, and the wrapper exists
precisely so a ninth refusal cannot lose a row.

**Frequency.** One row per attempted provider write. On this estate that is rare:
the measured count of provider writes from this system is **0** to date
(CLAUDE.md), so the honest expectation is an empty page until something writes.

| field | source | label |
|---|---|---|
| `at` | row, UTC, written by `_ledger` | **TRUSTWORTHY.** Stamped by the same function that writes the row |
| `operation` | row — e.g. `bison.pause`, `bison.resume` | **TRUSTWORTHY.** A member of the closed `OPERATIONS` set |
| `outcome` | row — `refused` / `failed` / `unverified` / `accepted` / `drifted` / `unknown` | **TRUSTWORTHY, and the labels must be carried through verbatim.** `accepted` means the transport returned *and* the read-back matched. `drifted` means it acted and the read-back disagreed. **`unknown` means the write happened and nothing verified it** — `_classify` returns it when `expected` is `None` or empty. Rendering `unknown` as anything but UNKNOWN would reproduce the exact defect this page exists to fix |
| `campaign` | row — **our** canonical campaign id | **TRUSTWORTHY** as *our* id |
| **the provider's campaign id** | — | **MUST NOT RENDER: the row does not carry it.** `_ledger` writes `campaign` and `tenant` and never `provider_campaign_id`. So this page can say a `bison.pause` was accepted and **cannot say which EmailBison campaign it hit.** Recommendation §5.1 |
| `tenant` | row | **TRUSTWORTHY**. Also the scoping key, so this page is per-workspace like every other read |
| `by` | row | **TRUSTWORTHY as a record, not as authorisation.** `glm-c/0140` measured that `providerwrites.perform` never consults the actor — `by` is only ledger-recorded. Label the column "recorded as" and not "authorised by" |
| `detail` | row, truncated at 300 chars | **TRUSTWORTHY.** On a refusal this is the guard's own sentence, which is the most useful text on the page |
| `pid`, `argv[:3]` | row | **TRUSTWORTHY.** `argv` is basenames only, so it says "a web request" vs "a script" without leaking a path |
| **"no provider write has happened"** | the file being empty | **MUST NOT RENDER as that sentence.** `_ledger` swallows `OSError`, so a full disk loses a row silently, and `refuse_production_write` returns without writing under test isolation. An empty file means **no row was recorded**, which is a weaker claim. And an **unreadable** file is UNKNOWN, which never becomes zero — invariant 0, verbatim |

**Read-only. No write is needed and none should be offered.**

---

### PAGE 2 — WHAT STANDS BETWEEN A CLICK AND A PROVIDER

> **If somebody clicks Pause or Resume on this campaign right now, what refuses?**

This is the question three of today's findings are instances of. The answer is
computable **by asking the real guard functions rather than restating them**,
which is the only form that cannot go stale the way `app.py:1625` did.

**Source.** `providerwrites.classify_campaign`, `providerwrites.is_supported`,
`providerwrites.describe`, `campaigns.validate`, and env-var *presence*. Per
campaign, one row per gate, in the order `_perform` actually applies them.

| field | source | label |
|---|---|---|
| ownership class | `providerwrites.classify_campaign(channel, id)` — called, not reimplemented | **TRUSTWORTHY, and it must render all three states.** `resonate_os`, `resonate_internal`, `unknown` — and **`unknown` renders as do-not-touch, never as a blank or a pass.** It reads `config/internal-campaigns.txt` on every call and is never cached |
| verb supported | `providerwrites.is_supported(op)` | **TRUSTWORTHY.** This is the exact field `api.py:3156` asserts is empty and which holds 16 verbs |
| binding present | `campaign["bison_campaign_id"]` / `heyreach_campaign_id` | **TRUSTWORTHY as a local fact.** Render as "this row names a provider campaign", **not** as "a provider campaign exists" |
| facing / non-facing | `providerwrites.describe(op)` | **TRUSTWORTHY, and this is the field that explains `glm-c/0130`.** `EMAIL_RESUME` is non-facing, so `perform` never reaches `executionguard.revalidate`, the only route to `killswitch.require`. Rendering this column is what makes "the killswitch does not stand here" visible instead of discoverable |
| approval current | `campaigns.approval_is_current(...)` | **TRUSTWORTHY.** The fingerprint covers `bison_campaign_id` (`campaigns.py:292`), so a mapping changed after approval shows here |
| door A state | `RESONATE_PROVIDER_WRITES` **presence** | **TRUSTWORTHY only as presence, and only if labelled "procedure, not code".** `provider_states` already has the right discipline — a variable name and a boolean, never a value. This is the last line of defence on both write paths and it is an environment variable |
| **"three barriers stand"** | — | **MUST NOT RENDER.** False since 2026-09-24 16:53:55 (`6ff9cc945`), measured per barrier by `glm-c/0130`: B1 does not hold, B2 is true as a fact and idle as a barrier, B3 holds for the legacy ten by side effect. **Any page repeating it inherits the lie** |
| **a single green "safe" badge** | — | **MUST NOT RENDER.** The whole failure mode here is an aggregate that is green because one of its inputs was never consulted. Render the ladder, one row per gate, in application order, and let the reader see which rung is doing the work |
| **the killswitch as a global state** | `killswitch.workspace_state` | **MUST NOT RENDER on this page.** It is true and it is **not consulted on this path** — no layer of the resume chain names a workspace. A truthful value in a place that implies it applies is the same defect as a false one |

**Read-only.** It changes when a mapping, an approval or the declaration file
changes — so rarely, and every change is itself auditable.

---

### PAGE 3 — CAMPAIGN STATE, HERE AND THERE

> **What does this system believe about this campaign, and what does the provider
> say — shown as two columns that are allowed to disagree?**

`/campaigns` exists and reports `status`, `paused`, `pause_reason`,
`pause_since` — all from the local row (`api.campaign_rows`, `api.py:2206-2217`).
**Nothing on any screen reports what the provider says.** The three campaigns the
operator cares most about were paused **by hand, in EmailBison, on 2026-09-28**,
and no local field could know that.

| field | source | label |
|---|---|---|
| local `status`, `paused`, `pause_reason`, `pause_since` | `work/campaigns.jsonl` | **TRUSTWORTHY, under a heading that says whose belief it is.** Column header "this system believes", not "state" |
| provider status | EmailBison / HeyReach | **UNKNOWN.** The measurement that would settle it is a live provider read — `scripts/provider_truth.py`, which writes `docs/state/PROVIDER-CAMPAIGNS.json`. Render the column with the age of that file beside it, or render UNKNOWN. **Never infer it from the local column** |
| the two disagreeing | both | **TRUSTWORTHY once the provider column has a real value, and it is the most valuable cell on this page** — "RUNNING here, paused there" is exactly the divergence `6ff9cc945`'s own comment says went unrecorded for two weeks |
| **"not mapped: no provider campaign has been created"** | `api._mapping_status` (`api.py:2874`) | **MUST NOT RENDER as written.** It derives a claim about the provider from a local absence. Absence of a binding is not evidence that nothing exists there — the 40 EmailBison campaigns are the counter-example. The honest text is "this row names no provider campaign" |
| campaign **owner** from `PROVIDER-CAMPAIGNS.json` | that file's `owner` field | **MUST NOT RENDER.** It is the two-state boolean CLAUDE.md withdrew on 2026-10-01 — `provider_truth.owned_by_resonate` "wrote 'not provably ours' down as the client's". The file in this tree still labels **327, 328, 352 and 418** `client_or_other`, which is the claim that was corrected. Ownership has three states and the authority is `classify_campaign` |
| `generated_at` of the provider file | the file | **TRUSTWORTHY and mandatory wherever a provider column appears.** This tree's copy reads `2026-09-30T20:40:42+00:00` — which does not match the `2026-09-28T12:51:44Z` CLAUDE.md cites, so **a reader of either prose has the wrong date.** A rendered age is the fix |

**Read-only, and deliberately so.** `/campaigns` already carries the Pause and
Resume buttons and those are two of today's three findings. This page should
**not** add a third control; it should make visible what the existing two do.

---

### PAGE 4 — WHY THIS PERSON WILL NOT BE CONTACTED

> **For one person, every gate that would refuse them, and — for each gate — what
> feeds it and when that feed last wrote.**

`/suppression` exists and answers the first half well, scoped per workspace.
The second half is the part `suppression/0070` proves is missing, and it is the
brief's own worked example.

| field | source | label |
|---|---|---|
| suppression reasons | `eligibility.must_not_contact` via `api.suppression` — called, not re-derived | **TRUSTWORTHY.** Six person-level reasons, and the function is the same one the engine asks |
| agency DNC membership | `work/agency-dnc.jsonl` | **TRUSTWORTHY.** 105 fingerprints, verified by name-set in both directions on 2026-10-15 by `suppression/0055` |
| the bounce gate's **verdict** | `channels._bounced` reading `events.EMAIL_BOUNCED` | **TRUSTWORTHY as the gate's answer, and worthless as protection.** It returns `(True, None)` — SENDABLE, no reason — for all three addresses EmailBison has already bounced |
| **"bounce protection: active"** | — | **MUST NOT RENDER.** The brief's own example, and it is exact: the gate is real, consulted on every send, before MX and before verification (`eligibility.py:806-807`), and the only writer of the event it reads, `leadobserve.confirm_email_touches` (`leadobserve.py:579`), has **zero production callers** — its only caller is its own CLI `main()` plus four tests. A page rendering that badge converts an unknown into a confident answer, which is the thing worth refusing |
| **the feed column** | per gate: the writer module, its production caller count, the last row's timestamp | **This is the proposal.** TRUSTWORTHY where a writer exists and has written; **UNKNOWN, rendered as UNKNOWN, where the feed has never written.** A bounce gate whose feed row reads "no production writer — last wrote: never" is honest and useful. The same gate with a green tick is the defect |
| **"this person is safe to contact"** | — | **MUST NOT RENDER in any form.** Every gate on this page can only say *no*. None of them can say *yes*, because `must_not_contact` returning empty means "no reason was found", and CLAUDE.md's rule 2 makes UNKNOWN a block. The page answers "why not", never "why yes" |

**Read-only.** The feed column is the whole idea and it needs no new state — the
caller count is a static fact about the code and the last-write time is one
`read_jsonl` tail.

---

### PAGE 5 — WHAT THIS SYSTEM CANNOT SEE

> **The blind spots, named, on the same screen as the health it reports.**

`/health` (`api.operational_health`) is the best-built screen on this surface and
it already has the right instinct: an `unwatched` list, because *"a health screen
that looks clean because it was not watching is worse than none."* **Its
`unwatched` list has two entries and both of today's biggest blind spots are
missing from it.** This is not a new page so much as the one existing page worth
finishing — and I would ship it as part of Page 1 rather than alone.

| field | source | label |
|---|---|---|
| existing rows: reply polling, digest, failed jobs, failed notifications, owed tags | `api.operational_health` | **TRUSTWORTHY.** Every row reads canonical state, is scoped to the workspace, and says whether a retry is safe and why — which is the sentence that stops somebody re-running a thing that already happened |
| the job row's label | `job.get('kind')` at `api.py:1580` | **A FIELD WITH NO WRITER, measured.** `jobs.py` contains the string `"kind"` **zero** times; `jobs.new` writes `"type"` (`jobs.py:135`). So every job row on the health screen renders `job <id>` and the job type is never shown. Smallest instance of today's pattern, on a health screen, and a two-character fix |
| `unwatched`: "no provider is called in this build, so there are no enrichment failures to report" | `api.py:1677` | **HALF TRUE AND IT MUST BE SPLIT.** The enrichment half is true — no web surface runs a spending job type, structurally. The "no provider is called" half is false since 2026-09-13 |
| **missing from `unwatched`: provider writes** | — | Should be a row: *this screen cannot see what was written to a provider; that is `work/provider-writes.jsonl` and nothing here reads it* |
| **missing from `unwatched`: the bounce feed** | — | Should be a row: *no production code writes `EMAIL_BOUNCED`, so a bounce at the provider is invisible here* |
| **missing from `unwatched`: provider campaign state** | — | Should be a row: *this screen reports what this system believes; a campaign paused by hand at the provider is invisible* |

**Read-only.** Every addition is a sentence, not a subsystem.

---

### PAGE 6 — WHAT IS BETWEEN HERE AND THE NEXT SEND

> **The gate list, with each item's authority named and its state read from that
> authority rather than typed.**

The question the operator restated four times in one day. **I am proposing this
one with an explicit warning**, because it is the most tempting page on this list
and the easiest to build wrong: most of its rows have authorities outside the
product, and a row whose state is typed rather than read is a checklist that
drifts — which is how `docs/state/LEDGER.json` earned its "derived, never
hand-edited, because a ledger somebody has to remember to update is a ledger that
drifts" rule.

| row | authority | label |
|---|---|---|
| copy approved | `canary/APPROVAL-SHEET-2026-10-15.md` + `DECISION-canary-approval-2026-10-15.md`, **outside the repository** | **UNKNOWN from inside the product.** Settled by reading the sheet, which is on the Desktop. Either the sheet moves into the repo or this row is not rendered |
| per-row approval still valid | the 48 per-row sha256 digests in the sheet | **TRUSTWORTHY *if* the sheet is reachable, and it is the best-designed row here** — the operator chose a mechanism where a re-render to different bytes makes the approval stale by construction rather than by anyone noticing. A page recomputing those 48 digests is a real check |
| the 90 suppressions applied | `work/agency-dnc.jsonl` | **TRUSTWORTHY.** 105 rows, name-set verified both directions |
| the three bounced addresses | `work/agency-dnc.jsonl` | **TRUSTWORTHY once applied; today it renders NOT APPLIED**, which is correct — the disposition is recommended and not applied |
| halt fix certified | `pilotcaps/0130`'s lane entry, **outside the repository** | **UNKNOWN from inside the product** |
| sender pool / Flag B | `canary/sender-estate-export-2026-10-15b.csv` + the fixture | **UNKNOWN, and flagged as contradictory**: the fixture says Ivan Mamic owns 0 mailboxes, the export says 12. Both cannot be true, and `glm-c/0150` is reconciling them |
| company-name derivation | undecided | **UNKNOWN — and this row must say that three sources disagree**: `company_facts.name`, `record.company`, and the supplier CSV under production `work/`. It decides one body's word count and one row's safety |
| word contract on the composed body | `lint.countable_words` | **TRUSTWORTHY and it is the row with a measurement**: the composed text at the binding shape is 91 against a hard ceiling of 90, and `countable_words` has exactly one caller in the repository, handed the bare body. A gate that is not run on the text that ships |
| freeze / `sending.live` / killswitch | code + operator order | **MUST NOT RENDER as a single "sending: blocked" state.** The freeze is an operator order, not code on the pause or resume path; `sending.live` is read by nothing on those paths. Render the per-path ladder from Page 2 instead |

**Read-only, and this is the page I would build LAST**, if at all. Half its rows
would render UNKNOWN today, which is the honest answer and also an argument that
the page is premature.

---

## 4. WHAT I WOULD BUILD FIRST, AND WHY — one paragraph

**Page 1, the provider write log, and I would build nothing else until it
exists.** It is the only page on this list where the writer and the reader are
the same module's own ledger, so every field is trustworthy by construction and
nothing has to be derived, inferred or kept in sync; it needs no new state, no
new writer, no new concept and no migration — `providerwrites.perform` has
written `work/provider-writes.jsonl` on every exit since 2026-09-24, and the only
reason nobody can see it is that no module under `src/web/` imports
`providerwrites`. It is read-only, so it cannot reproduce any of the three
defects TASK 0010 found, all of which were on write routes. It is small enough to
be correct: one `read_jsonl`, one scope filter on `tenant`, nine columns, and the
three sentences that must not be rendered are already written down above. And it
is the only one that **pays back immediately on a question nobody can currently
answer** — today the console tells a super admin "No provider call has been made.
This build does not make one from any surface" while the two routes that *can*
write to EmailBison sit two clicks away on the Campaigns page, and the sentence is
derived from a ledger that could never have recorded one. Page 1 does not fix
that sentence; it does something better, which is to make it **falsifiable from
inside the product** — the first time a row appears, the claim is visibly wrong,
and the next person to find a false control sentence finds it on a screen instead
of by accident while looking for something else. Page 2 is the natural second
because it answers the same question prospectively rather than retrospectively,
and because it is computed by *calling* the guards rather than restating them,
which is the one construction that cannot go stale the way `app.py:1625` did.

---

## 5. WHAT THESE PAGES WOULD NEED THAT DOES NOT EXIST

Three, each small, each named rather than assumed.

1. **`_ledger` does not record the provider campaign id.** `providerwrites.py:2338-2349`
   writes `campaign` (ours) and `tenant`, never `provider_campaign_id` — which
   `_perform` already has in hand. So the log can say a `bison.pause` was
   accepted and cannot say which EmailBison campaign it hit. **One key in one
   dict**, and it is the difference between an audit trail and an anecdote.
2. **Nothing in `src/web/` imports `providerwrites`.** Page 1 and Page 2 both need
   it. It is a read-only import of a module with no provider dependency at
   import time — `_perform_pause` imports `providers.bison` lazily inside the
   function — so the web tier would gain no provider import.
3. **The approval sheet and the lane files live outside the repository.** Page 6
   cannot read them and should not try. That is the operator's call about where
   the canary's approval record belongs, not an interface decision.

---

## 6. PAGES I CONSIDERED AND REJECTED

The brief's rule cuts both ways: a question nobody asked is not a page.

- **A lane / watcher dashboard.** It is the day's loudest question (23 processes,
  six live, two silently dead, `.out` at 0 bytes, `DONE/` worthless four ways) and
  I am not proposing it. Its authority is the OS process table and
  `logs/watcher-<lane>.log`, both outside the repository and outside `work/`. A
  console that scraped them would be a second answer to a question that already
  has one, and §2 is the reason to refuse it rather than a reason to build it.
- **A suite / merge-gate page.** Same objection, and worse: the name-set
  reference is regime-dependent — `qwen/0060` measured thirteen names that flip
  between a CRLF and an LF checkout at the same SHA, and `git status` calls both
  trees clean. A page rendering a failing-name count would render a number whose
  meaning depends on which git looked at the tree last. **MUST NOT RENDER**, as a
  whole page.
- **A "send readiness" traffic light.** The aggregate is the defect. Page 2's
  ladder is the same information in the one shape that cannot be green for the
  wrong reason.
- **Anything about open rates, deliverability or reach.** TASK 0010 §3.6: five
  hardcoded "nothing has been sent" sites, two on client-facing cuts, false since
  no later than 2026-09-23, and the one conditional site reads `push_marked`
  touches — 912 provider-confirmed sends against one recorded touch in 1,582
  records. There is no trustworthy sending number on this estate today.

---

## 7. WHAT THIS PROPOSAL DOES NOT DECIDE

It designs nothing and builds nothing. It does not decide whether the approval
sheet moves into the repository, whether `_ledger` gains a key, whether the
console should ever read anything outside `work/`, or which of the six gets
built — only which one I would build first and the reason. Every MUST NOT RENDER
above is a constraint on a page that does not exist yet, written down now
because the cheapest moment to refuse a field is before anybody renders it.
