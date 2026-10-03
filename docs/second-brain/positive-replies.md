# Positive replies — the metric, and the corpus behind it

> **THE METRIC IS THE POSITIVE REPLY. THE FARSEER CADENCE IS THE REFERENCE.**
> Operator, 2026-10-03.

**A positive reply is** an explicit statement of interest, or a request for
more: the classes `positive`, `meeting`, and a question about the offer. **A
referral is not positive. "Send me some information and I will see" is not
positive.** Those are their own class and are counted separately. The goal is a
person who says *"I am interested, let us talk"* — not an acceptance, not a
reply rate, and not meetings nobody can join to a campaign.

**Every rate in this file carries "classifier unaudited" until the operator has
reviewed the sample of replies the classifier called positive — however many
there are** (operator, 2026-10-03: *"uzorak pozitivnih za moj pregled u
copy-review, koliko god ih ima."* The earlier wording of this line asked for
100, which email cannot supply and which would make the gate unsatisfiable;
the instruction supersedes it). Measured
reason: a reply reading "Stop" was classified `positive` at 0.75 confidence
(2026-10-02). The 899-reply email corpus holds **26** positives in total —
measured 2026-10-03: 19 `positive`, 6 `question`, 1 `meeting_intent` — so the
sample cannot be filled from email alone: the real count is the finding, not
something to pad, and the sample goes to copy-review before any rate here is
trusted. **It has: the email half is at
`resonate-ops/copy-review/POSITIVE-SAMPLE-2026-10-03.md`, all 32 flagged rows
with the real text, and 10 of the 26 survive a read against the definition
above.**

**That audit is why the label matters more than the rate.** The classifier's
precision on its own positive bucket is **38.5% (10/26)**, and the failures are
not near-misses. The 14 wrong rows are six plain negatives, three people
selling something to us, two "send me information" replies the rule above
excludes by name, one existing customer sending feature requests, one bare
answer to our own question, and one reading *"What are you even pitching here?
This is one of the weaker cold-mails I've gotten in a while"*. Two of the five
`referral` rows are out-of-office auto-replies that name a covering colleague.
**And `confidence` cannot filter any of it** — it is a per-class constant
across all 899 replies, every `positive` exactly 0.75, zero within-class
variation. The "Stop" reply scored 0.75 because that is what every positive is
given.

---

## What this machine holds about Farseer, measured 2026-10-03

The operator's account of Farseer — **35 meetings in 14 countries, the only
campaign where the channels were coordinated per account** — is not
reconstructible from this machine today, and here is exactly what is and is not
here. Nothing below is inferred from the campaign's name or from memory.

| question | what the machine says | command |
|---|---|---|
| Is Farseer a client config in this repo? | **No.** `config/clients/` holds `productive`, `demo` and `contactout.example` only. | `ls config/clients/` |
| Does the name appear in the repo at all? | **The client's web domain is on `config/suppress.local.txt`** — a suppressed DOMAIN, which is what a client of ours looks like in that file, not a prospect. The domain is deliberately not spelled here: it is also in `FORBIDDEN_DOMAINS` in `tests/test_fixture_hygiene.py`, which scans every tracked `.md`, so writing it makes this file fail the guard. **The first version of this row wrote it, and did fail.** | `grep -ril farseer config/` |
| Is there campaign data for it? | **None.** 0 files under `docs/`, 0 under `src/`, 0 under `scripts/` except one Slack catalogue script. | `grep -ril farseer docs src scripts` |
| Where does the name actually live? | **11 files under `work/slack-history/`** — conversation about the campaign, not the campaign. | `grep -ril farseer work/` |
| Are there call or WhatsApp records? | **No.** Every hit for `whatsapp`, `aircall`, `twilio` or `dialer` outside Slack history is a PROSPECT COMPANY DESCRIPTION: 9 queue rows, with the term in `research` (8) and `company_facts` (1). No call-shaped file exists in `work/`. | the field tally over `work/queue.jsonl` |
| Could such a record exist? | **No. The data model has two channels.** `channels.MODES` is `['multichannel', 'email_only', 'linkedin_only', 'none']`, and no module under `src/` knows `phone`, `call` or `whatsapp`. | `channels.MODES`, `grep` over `channels`/`events`/`store` |

### What is missing, and where it should be

1. **A third channel.** A call or a WhatsApp touch has no channel in
   `channels.MODES`, no event kind, and no field on a contact. Farseer's
   coordinated cadence therefore cannot be recorded by this system even if the
   texts were recovered — this is a model change and an operator decision, not
   a patch.
2. **A meeting as a first-class outcome.** "35 meetings" has no home either:
   `meeting_booked` appears in no file under `work/` or `docs/`. The metric the
   operator has just made primary is one the system cannot currently count from
   its own state, only from a reply classification.
3. **The campaigns themselves** are on the providers, under a workspace this
   repo does not configure — so they are reachable only by provider read, which
   is what the two provider lanes are doing now.

**That is the honest position**: Farseer's own record on this machine is a
suppressed domain and eleven Slack conversations. Everything else has to come
from the providers, and anything that cannot be found there is missing rather
than reconstructable.

---

## The corpus

One row per positive reply: recipient **anonymised**, **our own preceding text
in full**, channel, step, day, campaign. Assembled from the two provider lanes
— LinkedIn (`linkedin.md`, all 121 campaigns on the seat) and email
(`email.md`, the 20 OS campaigns and the 899 replies).

**PENDING the LinkedIn lane.** The email half is below, measured 2026-10-03,
and published ahead of LinkedIn's because the audit behind it changes what the
operator does next. It is labelled so nobody ranks a half-corpus by the metric:
**the rows below are email only, the LinkedIn lane is still reading, and no
cross-channel ranking may be drawn from this section until both halves are in.**

### The email half, measured 2026-10-03 (TASK-980)

**Email holds 26 classifier-positives, and 10 survive my read. Do not read
this section as 26 exemplars.** The classifier's precision on its own
positive bucket is **38.5% (10/26)**, or 46.2% (12/26) if explicit interest
with a named later date counts. The full sample, with the real text of every
reply and of our message that earned it, is at
`resonate-ops/copy-review/POSITIVE-SAMPLE-2026-10-03.md` - outside git,
awaiting the operator's ruling. Rows below are the **10 I would keep**, plus
the 2 postponed, listed separately and never mixed in.

Three constraints on every number in this section:

- **The 899-reply corpus is a 47.5% SAMPLE, not a census.**
  `/campaigns/{id}/replies` is an inbox view, not the reply ledger: 899
  readable against **1,894** actually recorded (274 complete, 327 30.7%,
  328 28.7%, 352 82.0%, exhaustive lead walk of 52,661 leads). **Every
  per-step rate is a FLOOR**, and campaign 328's zero positives is
  **UNKNOWN, bounded near 10** - 0 observed in 28.7% coverage - never zero.
- **`confidence` is a per-class constant and cannot triage anything.** Across
  all 899: every `positive` exactly 0.75, every `negative` exactly 0.80,
  every `unsubscribe` exactly 0.95, every `unknown` exactly 0.0. 15 classes,
  7 distinct values, **zero within-class variation**. The "Stop" reply scored
  0.75 because that is what every positive is given.
- **Why the header's count moved from 20 to 26, and the trap behind it.** 20
  was the `positive` class alone; the definition at the top of this file also
  admits a question about the offer. The deeper problem is that **three
  classified artefacts of the same 899 replies exist on disk and no two
  agree** — the pre-fix run gives unknown 324 / negative 205 / unsubscribe 145
  / positive 21; the rules-fixed run gives unknown 292 / negative 197 /
  unsubscribe 201 / positive 19; and the distribution quoted in today's
  briefing matches neither. The rules-fixed run is used throughout because it
  is newest and names its rule hash in its filename. **A count drawn from a
  classification must carry that run's identity with it**, or two lanes quote
  different numbers for the same corpus and both are right.

Where the positives sit, by exact step (classifier bucket, n=26, exact
denominators from the lead walk):

| step | positives | sends | per 100 sent |
|---|---|---|---|
| em1 | 14 | 41,077 | 0.0341 |
| em2 | 7 | 37,011 | 0.0189 |
| em3 | 2 | 34,619 | 0.0058 |
| em4 | 1 | 32,108 | 0.0031 |
| em5 | 1 | 30,297 | 0.0033 |
| em6 | 0 | 11,493 | 0.0000 |
| em7 | 1 | 10,606 | 0.0094 |
| em8 | 0 | 9,762 | 0.0000 |

**80.8% of them arrive at em1 or em2 (21 of 26) on 37.7% of the sends.** 24
of 26 (92.3%) come from campaign 352, the one campaign whose email names a
prior LinkedIn touch, on 45.4% of sends - and 352 is also the shortest copy
in the estate, so the two explanations are confounded and this corpus cannot
separate them.

#### The length tension, unresolved on purpose

The step cells that earned a positive run **32-108 own-text words, median 79
(n=7)**; the 22 that earned none run 97-160, **median 129.5 (n=22)**. The em1
contract set today is **90-140, target 120**, from the operator's own 17
exemplars (**114-133, median 120.5, n=17**) - those four figures are as
reported by the lane that set that contract, not measured by this lane.

**These two corpora disagree and neither is adjusted here.** They are
different senders writing to different lists through different mailboxes, and
the earning-cell figure is confounded with naming a prior LinkedIn touch, so
a short email and a channel-coordinated email are the same email in this
data. The exemplar range is what a human writer produced and the operator
endorsed; the 79-word median is what the estate's replies actually came back
to. **Open question, not a contradiction to resolve by picking one.**

The experiment that would settle it, and it is two cells rather than an
argument: send 352's short question-led opener to accounts with **no** prior
LinkedIn touch, and a 120-word exemplar-shaped opener **behind** a LinkedIn
touch, to comparable lists from the same mailboxes in the same window. That
separates length from channel coordination. Until it runs, neither number
licenses changing the other.

#### Rows: the 10 that survive my read

Recipient anonymised. **Our own text is the stored template, in full** -
which is our writing with merge tokens where the prospect's data would go,
and therefore the version a writer should learn from. The rendered send is in
the copy-review file.

##### 1. campaign 327, em7, 2026-05-14

- channel **email** / emailbison, step id 3738 (parent step), persona `champion`, geo `united states`
- classifier `positive` at 0.75; my read **KEEP** - offers a call

**The operative clause** (hand-extracted; verbatim reply in copy-review):

> 'If you want to set up a phone call to chat, we can certainly do that.'

**Our message, as stored** - subject `{wrong person at {COMPANY}?|quick question before I stop reaching out|should I be talking to someone else?}`:

> {% assign title = '{TITLE}' | downcase | strip %}
>
> {Hey|Hi} {FIRST_NAME},
>
> Been reaching out a few times and haven't heard back, which is completely fine, but before I stop I wanted to ask one honest question.
>
> Is project profitability and ops visibility something {COMPANY} is actively looking at right now, or is it not a priority at the moment?
>
> {% if title contains "founder" or title contains "owner" or title contains "ceo" %}
> If it's on your radar but not the right time, I'm happy to check back in a few months. If it's genuinely not something you're thinking about, I'll leave you alone.
> {% elsif title contains "coo" or title contains "operations" %}
> If this sits with someone else at {COMPANY}, finance, ops, whoever owns the tooling, I'm happy to reach out there instead.
>
> Just point me in the right direction.
> {% elsif title contains "cfo" or title contains "finance" %}
> If the ops and delivery side of this sits with someone else at {COMPANY}, I'm happy to reach out to them directly.
> No need for you to pass it on.
> {% else %}
> If this is something that sits with a different person at {COMPANY}, just let me know and I'll reach out to them instead.
> Happy to make it easy.
> {% endif %}
>
> Either way, if you want to try the product before deciding anything, reply {yes|"yes"} and I'll get the trial set up.
>
> That offer stands regardless of timing.
>
> {SENDER_FIRST_NAME}

##### 2. campaign 352, em1, 2026-09-15

- channel **email** / emailbison, step id 4036 (variant of step 4035), persona `not_a_persona`, geo `absent`
- classifier `positive` at 0.75; my read **KEEP** - offers a call and sends availability

**The operative clause** (hand-extracted; verbatim reply in copy-review):

> 'Growth is always worth a discussion! See my availability below to schedule a time.'

**Our message, as stored** - subject `{me again, {FIRST_NAME}|following up from LinkedIn|trying email this time}`:

> Hey {FIRST_NAME},
>
> {SENDER_FIRST_NAME} here, tried connecting on LinkedIn as well.
>
> curious, as {TITLE} at {COMPANY} do you have a good handle on which projects are actually profitable in real time or is that something you figure out after the fact?
>
> its one of the biggest pain points we hear from {INDUSTRY} agencies and usually comes down to not having projects, budgets and resourcing in one place.
>
> lmk if its worth a conversation.
>
> {SENDER_FIRST_NAME}

##### 3. campaign 352, em1, 2026-07-14

- channel **email** / emailbison, step id 4036 (variant of step 4035), persona `economic_buyer`, geo `canada`
- classifier `meeting_intent` at 0.70; my read **KEEP** - names a slot

**The operative clause** (hand-extracted; verbatim reply in copy-review):

> gives a specific date and a time window with a hard stop. The one row the classifier called meeting_intent, and it is right.

**Our message, as stored** - subject `{me again, {FIRST_NAME}|following up from LinkedIn|trying email this time}`:

> Hey {FIRST_NAME},
>
> {SENDER_FIRST_NAME} here, tried connecting on LinkedIn as well.
>
> curious, as {TITLE} at {COMPANY} do you have a good handle on which projects are actually profitable in real time or is that something you figure out after the fact?
>
> its one of the biggest pain points we hear from {INDUSTRY} agencies and usually comes down to not having projects, budgets and resourcing in one place.
>
> lmk if its worth a conversation.
>
> {SENDER_FIRST_NAME}

##### 4. campaign 352, em1, 2026-07-08

- channel **email** / emailbison, step id 4192 (variant of step 4035), persona `economic_buyer`, geo `austria`
- classifier `question` at 0.75; my read **KEEP** - question about the offer, including price

**The operative clause** (hand-extracted; verbatim reply in copy-review):

> asks for the video AND 'what is the price for that?'. A price question is a question about the offer.

**Our message, as stored** - subject `{me again, {FIRST_NAME}|following up from LinkedIn|trying email this time}`:

> {Hey|Hi} {FIRST_NAME},
>
> {saw your profile and noticed|came across your profile, saw} you're {TITLE} at {COMPANY}. {reached out on LinkedIn too but figured email might be easier|tried you on LinkedIn as well but email felt like the safer bet}.
>
> {quick question|honest question}, how are you guys {currently managing|handling} projects, resourcing and finances, {is it all in one place or spread across a bunch of different tools|one platform or stitched together across a few tools}?
>
> {asking because|reason I ask is} I'm with Productive, {we built one platform|it's a single platform} for exactly that, projects, resourcing, budgets and invoicing {together|in one place}, so {INDUSTRY} agencies {can actually see project profitability in real time|stop losing visibility on which projects actually make money}. most teams we talk to are {juggling 3-4 tools|running 3-4 separate tools} before they switch.
>
> {worth a quick chat|open to a short call} to see if it'd {fit how {COMPANY} works|make sense for {COMPANY}}?
>
> {SENDER_FIRST_NAME}
>
> P.S. {if a call feels like too much, happy to just send a 2 minute overview instead|no pressure on the call, I can also just send a short video of how it works|if now's not the time, just tell me when to circle back and I will}

##### 5. campaign 352, em1, 2026-07-02

- channel **email** / emailbison, step id 4192 (variant of step 4035), persona `champion`, geo `ireland`
- classifier `positive` at 0.75; my read **KEEP** - explicit interest and asks to talk

**The operative clause** (hand-extracted; verbatim reply in copy-review):

> 'We are interested in more information about what you do and how you do it as this is the spot on on our key pain point. When would be a good time to talk?'

**Our message, as stored** - subject `{me again, {FIRST_NAME}|following up from LinkedIn|trying email this time}`:

> {Hey|Hi} {FIRST_NAME},
>
> {saw your profile and noticed|came across your profile, saw} you're {TITLE} at {COMPANY}. {reached out on LinkedIn too but figured email might be easier|tried you on LinkedIn as well but email felt like the safer bet}.
>
> {quick question|honest question}, how are you guys {currently managing|handling} projects, resourcing and finances, {is it all in one place or spread across a bunch of different tools|one platform or stitched together across a few tools}?
>
> {asking because|reason I ask is} I'm with Productive, {we built one platform|it's a single platform} for exactly that, projects, resourcing, budgets and invoicing {together|in one place}, so {INDUSTRY} agencies {can actually see project profitability in real time|stop losing visibility on which projects actually make money}. most teams we talk to are {juggling 3-4 tools|running 3-4 separate tools} before they switch.
>
> {worth a quick chat|open to a short call} to see if it'd {fit how {COMPANY} works|make sense for {COMPANY}}?
>
> {SENDER_FIRST_NAME}
>
> P.S. {if a call feels like too much, happy to just send a 2 minute overview instead|no pressure on the call, I can also just send a short video of how it works|if now's not the time, just tell me when to circle back and I will}

##### 6. campaign 352, em1, 2026-06-12

- channel **email** / emailbison, step id 4035 (parent step), persona `not_a_persona`, geo `absent`
- classifier `question` at 0.75; my read **KEEP** - question about the offer

**The operative clause** (hand-extracted; verbatim reply in copy-review):

> 'Is this for a CRM system?' - asks what the offer actually is.

**Our message, as stored** - subject `{me again, {FIRST_NAME}|following up from LinkedIn|trying email this time}`:

> Hey {FIRST_NAME},
>
> saw your profile and noticed you're {TITLE} at {COMPANY}, reached out on LinkedIn too but figured email might be easier.
>
> quick question, how are you guys currently managing projects, resourcing and finances, is it all in one place or spread across a bunch of different tools?
>
> most {INDUSTRY} agencies we talk to are juggling 3-4 tools and losing visibility on project profitability because of it.
>
> worth a quick chat?
>
> {SENDER_FIRST_NAME}

##### 7. campaign 352, em1, 2026-06-01

- channel **email** / emailbison, step id 4035 (parent step), persona `champion`, geo `canada`
- classifier `question` at 0.75; my read **KEEP** - open, and asks what the offer is

**The operative clause** (hand-extracted; verbatim reply in copy-review):

> 'open to considering other options. What is the all in one solution you're proposing?'

**Our message, as stored** - subject `{me again, {FIRST_NAME}|following up from LinkedIn|trying email this time}`:

> Hey {FIRST_NAME},
>
> saw your profile and noticed you're {TITLE} at {COMPANY}, reached out on LinkedIn too but figured email might be easier.
>
> quick question, how are you guys currently managing projects, resourcing and finances, is it all in one place or spread across a bunch of different tools?
>
> most {INDUSTRY} agencies we talk to are juggling 3-4 tools and losing visibility on project profitability because of it.
>
> worth a quick chat?
>
> {SENDER_FIRST_NAME}

##### 8. campaign 352, em2, 2026-06-15

- channel **email** / emailbison, step id 4204 (variant of step 4037), persona `economic_buyer`, geo `united states`
- classifier `positive` at 0.75; my read **KEEP** - asks for a demo and proposes timing

**The operative clause** (hand-extracted; verbatim reply in copy-review):

> 'I'm interested in seeing a demo. Let me know if you think we could set something up towards the end of the week.' The strongest row in the set.

**Our message, as stored** - subject `Re: {me again, {FIRST_NAME}|following up from LinkedIn|trying email this time}`:

> {Hey|Hi} {FIRST_NAME},
>
> {my message is somewhere between your unread Slack threads and that tab you've had open since March|pretty sure my last email is in witness protection somewhere in your inbox}.
>
> {the question stands though|still curious though}: {profitability and resourcing at {COMPANY}, solved or duct-taped|is {COMPANY} running projects and finances in one place or four}?
>
> {quick reply and I'll either book you a short demo or leave you in peace|one line back decides whether I'm useful or just noise}.
>
> {SENDER_FIRST_NAME}

##### 9. campaign 352, em4, 2026-07-01

- channel **email** / emailbison, step id 4217 (variant of step 4043), persona `not_a_persona`, geo `absent`
- classifier `positive` at 0.75; my read **KEEP** - question about the offer, conditional interest

**The operative clause** (hand-extracted; verbatim reply in copy-review):

> 'It is unclear what you are trying to sell. I assume a project management software? I could be interested but need better information before I waste time on demos.'

**Our message, as stored** - subject `Re: what we see with {INDUSTRY} agencies`:

> {Hey {FIRST_NAME}|{FIRST_NAME}|Hi {FIRST_NAME}},
>
> {going to close this thread out|wrapping this up on my end|last nudge from me} {unless you say otherwise|unless I hear back|if I don't hear back}.
>
> {before I do|one last time though|so, final ask}: {project ops and profitability at {COMPANY}, solid or improvable|is the {COMPANY} setup for projects and margins where you want it|happy with how project profitability gets tracked over there}?
>
> {if solid, congrats, genuinely|"we're good" is a perfectly good answer|a quick "all good" closes this}. {if improvable, the demo is 20 minutes and tailored|if not, 20 tailored minutes might fix it|if there's room, that's literally my job}.
>
> {SENDER_FIRST_NAME}

##### 10. campaign 352, em5, 2026-06-28

- channel **email** / emailbison, step id 4220 (variant of step 4045), persona `economic_buyer`, geo `united states`
- classifier `question` at 0.75; my read **KEEP** - intrigued, asks what it is

**The operative clause** (hand-extracted; verbatim reply in copy-review):

> 'Ok I'm intrigued...what is this and how can it help my agency?'

**Our message, as stored** - subject `{last one from me|closing the file on {COMPANY}|signing off, {FIRST_NAME}}`:

> {Hey {FIRST_NAME}|{FIRST_NAME}|Hi {FIRST_NAME}},
>
> {last one from me, I promise|this is the last email, promise|final one, scout's honor}.
>
> {I've reached out a few times now|a few messages in,} {and totally get it if the timing's off|I fully get it if now's not the moment} {or it's just not relevant for {COMPANY} right now|or this just isn't a {COMPANY} problem at the moment}.
>
> {if things change|if that ever shifts|whenever the timing's right} and you {want to see how other {INDUSTRY} agencies run projects, resourcing and finances in one place|feel like looking at the one-platform setup other {INDUSTRY} agencies use}, {just reply to this email and I'll pick it up|a one line reply revives this thread anytime|hit reply, even months from now, and I'm here}.
>
> {SENDER_FIRST_NAME}

#### The 2 that are interest, postponed - counted separately

Both say they are interested and both name a later date. If the operator
rules them positive the email count is 12; if `not_now`, it stays 10. They
are listed here so the ruling has the text in front of it, and they are **not**
included in the 10 above.

##### D1. campaign 327, em2, 2026-07-13

- channel **email** / emailbison, step id 3733, persona `champion`
- classifier `positive` at 0.75; my read **DEFER** - explicit interest, explicitly postponed

**The operative clause** (hand-extracted; verbatim reply in copy-review):

> states 'I am interested' and asks to touch base at the start of August. The interest is real; it is not 'let us talk' now.

**Our message, as stored** - subject `Re: {how {COMPANY} tracks margin today|the ops stack at {COMPANY}|project profitability at {COMPANY}}`:

> {% assign title = '{TITLE}' | downcase | strip %}{% assign loc = '{LOCATION}' | strip | default: 'your market' %}{Hey|Hi} {FIRST_NAME}, {% if title contains "founder" or title contains "owner" or title contains "ceo" %}
>
> Dropped you a note last week about the ops stack at {COMPANY}.
>
> Most founders we work with say the tipping point was realising they were paying for 4 or 5 tools that still left them guessing on margins.{% elsif title contains "coo" or title contains "operations" %}Sent you something last week. Quick add: the ops leaders who get the most out of Productive are usually the ones who've already tried fixing this with integrations or spreadsheet workarounds, and hit the ceiling on what that can actually do.{% elsif title contains "cfo" or title contains "finance" %}Following up from last week.
>
> One thing worth adding: the finance teams that get the most value aren't replacing their accounting tool, they're finally connecting time data to budget actuals in real time, no manual step in between.{% else %} Sent you a note last week.
>
> Wanted to follow up with a bit more context on why {COMPANY} came up on my radar.{% endif %} Productive replaces the handoff between your delivery and finance layer;  so when a project runs over hours, the budget number moves immediately, not at month-end when someone reconciles it.
>
> That's the gap most {INDUSTRY} agencies are still patching with exports and spreadsheets.If it sounds familiar, just reply {yes|"yes"} and I'll get you a free trial, no call required.
>
> You can poke around with your own data first.
>
> {SENDER_FIRST_NAME}

##### D2. campaign 352, em2, 2026-05-19

- channel **email** / emailbison, step id 4039, persona `not_a_persona`
- classifier `positive` at 0.75; my read **DEFER** - explicit interest, explicitly postponed

**The operative clause** (hand-extracted; verbatim reply in copy-review):

> 'We are currently scaling our operations. Let's connect in the fall. I would be interested in knowing what you intend to offer.'

**Our message, as stored** - subject `Re: {me again, {FIRST_NAME}|following up from LinkedIn|trying email this time}`:

> Hey {FIRST_NAME},
>
> just checking if this landed. no pitch, genuinely curious how {COMPANY} handles the ops side right now.
>
> if its not relevant just lmk and ill leave you alone, if it is would love to show you what we do.
>
> {SENDER_FIRST_NAME}

#### What the 18 wrong rows say the classifier fix is

Grouped by why they are wrong, because the grouping is the fix signal. Text
for each is in the copy-review file.

| group | n | the fix it implies |
|---|---|---|
| plain negative | 7 | negation handling, before any positive match - most contain "interested" inside a negation |
| inbound pitch TO US | 4 | a class that does not exist: somebody selling to us is neither positive nor negative about our offer |
| send-info (excluded by the operator's rule) | 2 | a pattern the operator's rule already names and the classifier does not implement |
| out-of-office read as a referral | 2 | ordering - `out_of_office` must be decided before `referral` |
| existing customer / internal redirect | 1 | a class that does not exist, plus a suppression question |
| answers the question, no interest | 1 | answering our question is not interest |
| objection | 1 | ordering - hostile objections are being absorbed by `question` |

**Not one of the 18 is a threshold problem**, which matters because
`confidence` carries no information to set a threshold against. 7 of 18 are
negations, 4 are inbound pitches to us, 5 are pattern or ordering faults the
operator's own rules already describe, and 2 need a class that does not
exist. The `referral`/`send_info` bucket is worse in kind: 4 of its 6 rows
are wrong and 2 of those are plain out-of-office auto-replies that name a
covering colleague.

#### LinkedIn half

**PENDING** - the LinkedIn lane is still reading. The email rows above are
shaped to concatenate with it: `channel`, `provider`, `campaign_id`,
`step_order`, `sequence_step_id`, `date_received`, `persona`, `geo`, our
subject and body, and the anonymised reply.
