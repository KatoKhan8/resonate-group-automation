# Weekly discovery, client review, and what performance may say

Three modules, one flow, and a rule that runs through all of it: **the
expensive thing happens after a person agrees to it.**

    a source proposes
      -> delta against everything known        (costs nothing)
      -> client reviews                        (costs nothing)
      -> approval gate 1                       (a person)
      -> enrichment                            (costs money)
      -> segmentation, copy, QA
      -> approval gate 2                       (a person)
      -> outreach

---

## 1. Discovery is a subtraction

A run that returns companies the client already knows is worse than one
that returns nothing. Nothing costs nothing; a list padded with their own
customers costs their trust, the first time they read it.

So `discovery.delta()` is a difference, not a search. `known()` builds the
universe once from canonical state and there is no path that returns a
candidate without going through the subtraction.

Seven things are checked:

| | the embarrassment it prevents |
| --- | --- |
| the seed import | "we sent you your own list back" |
| later imports | the same, a month later |
| prior discovery | "you showed me this last week" |
| client review | "I told you they were a client" |
| suppression | a live customer, cold-sequenced |
| campaign history | already being worked |
| the CRM | **not connected** |

### Identity is the domain, exactly

`ingest.norm_domain` and nothing else. No fuzzy company-name matching:
"Acme Ltd" and "ACME Limited" may be one company or two competitors, and
the cost of being wrong is asymmetric. A missed duplicate wastes a row; a
wrong merge sends nothing to somebody who should have heard from us, or
sends to somebody who asked not to.

`norm_domain` normalises and does not judge - `"not a domain"` comes back
unchanged - so validation is `ingest.is_hostname`, shared with the import
path so the two cannot drift into different opinions about what a domain
is.

### Provenance is mandatory

`candidate()` refuses one without a source and evidence a person could
argue with: *"digital agency in Hamburg, 55 staff listed on their team
page"*, not *"matched"*. A candidate nobody can question is a candidate
nobody can reject, which is how a bad list gets approved.

### What could not be checked is named

Two absences travel on every result rather than sitting in a document:

- **`LIVE CRM CONNECTOR REQUIRED`** - a delta computed without the CRM is
  not a smaller delta, it is a wrong one, and it surfaces the client's own
  open opportunities as fresh leads.
- **Agency-wide DNC** is person-level - hashed mailboxes and profile URLs
  - and a candidate is a domain with nobody attached yet. It applies at
  `hygiene`, once contacts exist. Named because "we did not check this"
  and "there was nothing to check" are different sentences.

### It spends nothing

Nothing in `discovery.py` calls a provider, and the result reports
`spent: 0`. Tests assert the whole flow - universe, delta, record - is
free.

---

## 2. The client review roundtrip

The one artefact in this product that leaves the building, is edited by
somebody who is not us, in a spreadsheet, and comes back.

### Canonical columns are echoed and compared

The file carries what we found *and* the three fields the client fills.
The first kind is compared on return. A changed `domain` is not an edit to
accept - it is a file that has been through something, and applying its
decisions would attach a "do not contact" to the wrong company.

A failing row is refused **individually** and named; the rest still
previews. A client who made four hundred decisions should not lose them to
one mangled line.

### The id is the identity

`resonate_candidate_id` = `sha256(workspace | batch | domain)[:16]`.

A file from another workspace matches nothing, because its ids were hashed
with a different workspace. Unknown, missing and duplicated ids are all
refused. Nothing is ever matched on company name.

The batch is *in* the hash, which is why the export must be named for the
run the candidates belong to - a file named for the wrong run produces ids
that fail to match on return, and every row is refused.

### Thirteen statuses, one of which suppresses

| status | effect |
| --- | --- |
| `do_not_contact` | **suppress** |
| `existing_client`, `existing_opportunity`, `active_prospect`, `partner`, `competitor` | exclude from cold outreach |
| `not_relevant`, `bad_fit`, `duplicate` | exclude |
| `review_later` | defer |
| `former_client`, `unknown` | a person decides |
| `approved` | proceed |

Read forgivingly and still from the closed set: "Do Not Contact",
"DO-NOT-CONTACT" and " do_not_contact " are one decision, because a
spreadsheet will produce all three. Anything outside the set is refused
with the list rather than silently becoming "unknown".

### Silence is not a decision

Rows the client did not return are reported as `never_returned`, never
treated as rejections. Otherwise a company is excluded because somebody
closed the file early.

---

## 3. Learning reports; it never acts

`learning.py` measures cohorts against the **workspace's own baseline**,
not an industry benchmark - the copy, the senders and the ICP are roughly
constant within a workspace, and that is the only fair comparison.

### Below the floor, nothing is said

40 contacted and 6 outcomes. Below either, a cohort gets no state, no
lift, no recommendation and no boost. Not cautious ones - none. A number
with a caveat beside it is still a number somebody will quote.

Confidence uses the Wilson lower bound rather than the raw rate: 6 of 40
against a 10.2% baseline has a raw rate well above it and a lower bound
below it, and only the second reading is honest about what six replies
support.

### It is observational

Every account in a cohort was chosen, worked and written to by somebody.
"These accounts replied more often" is supportable; "being a German agency
causes replies" is not, and only the second invites a decision the
evidence cannot carry. There is no `cause` field and no recommendation
phrased as an instruction.

A declining cohort is never told to stop. It may be the cohort, the copy,
the senders or the timing, and the number does not say which.

### What it may never do

- **Move the ICP.** There is no code path from here to `qualify`, and a
  test asserts the module contains nothing that writes.
- **Override a refusal.** The priority boost is capped at 0.10 and only a
  clearly-ahead cohort earns one. `hygiene` and `eligibility` do not
  mention learning at all, and a test asserts that.
- **Cross a workspace.** Rows are assembled from `repo.records()`, which
  has already narrowed to one tenant.

Rows count an account as contacted only on a **confirmed** touch. Planned
and approved steps are not outreach that happened.

---

## 4. Refresh is the other half

Discovery asks who else is out there. `src/refresh.py` asks the other
half of the same question: of the companies already in the estate, which
have gone stale enough that what we hold no longer supports a message,
and of those, which are worth a credit this week.

Both halves are needed and they are different work. Rediscovering a
company we already have is waste. Refreshing all thirty thousand of them
every week is a larger waste with a tidier name.

**Staleness is per kind, never one number.** Company evidence, person
evidence, the contacts we hold and the verification on their mailboxes
age at different rates and cost different amounts to renew. A single
"days since last touched" would put a re-verification costing one credit
in the same queue as a decision-maker search costing ten.

| kind | threshold | call | credits |
| --- | --- | --- | --- |
| Company evidence | 90 days | `apify-research` | 0 |
| Person evidence | 60 days | `apify-research` | 0 |
| Decision makers | 120 days | `decision-makers` | 10 |
| Mailbox re-verification | 120 days | `email-verifier` | 1 per mailbox |

Costs are read from `enrich.COSTS` - the table the spend ledger charges
against - rather than from a second list that could drift from it.

**Never researched is not stale.** A record with no company evidence has
not aged; it has not happened. It is marked `never`, counted separately,
and sorted as though it were just past its threshold: due, ahead of
anything merely approaching due, and behind something years overdue.

**Four accounts are excluded before anything is ranked.** Dropped
records, suppressed domains, a company that asked us to stop, and a
company already in a live conversation. The cheapest credit is the one
not spent on an account that may never be written to.

**Person credits wait for a verdict.** PLAYBOOK says no paid
person-level call happens before a company reaches an explicit ICP
verdict, and that rejected, review and unknown all mean zero person
credits. A company without one is offered company research - which is
free - and nothing else.

**The priority floor reduces rather than drops.** An account below it
keeps the work that costs nothing and loses the work that costs credits.
A company scores low partly because nothing is known about it, and free
research is how that stops being true; a floor that refused free
research would hold an account below the floor permanently and call the
result thrift.

**Nothing is refreshed.** `plan()` returns what a run would do, with an
estimate that says it is one. No provider is called to produce it, no
state is written, and the cap is applied before the fan-out rather than
after - with what fell below the line counted rather than dropped
silently.

---

## 5. What is not here

- **No discovery provider.** Every candidate is a fixture or a manual
  entry and says so. `LIVE DISCOVERY PROVIDER REQUIRED`.
- **No CRM connector.** `LIVE CRM CONNECTOR REQUIRED`.
- **No scheduler.** "Weekly" describes the intended cadence; nothing runs
  on a timer. A run happens when somebody asks for one. That is true of
  refresh as well as discovery, and it is the reason both modules say so
  in their own docstrings rather than leaving the word "weekly" to imply
  a timer that does not exist.
- **No volume to learn from.** The demo estate has 11 contacted accounts
  across 6 cohorts, so every cohort is `INSUFFICIENT_DATA` and the screen
  says so. That is the honest answer at this size.
- **No second approval gate wiring.** Gate 2 is the existing campaign
  approval; discovery does not yet hand off to it automatically.
