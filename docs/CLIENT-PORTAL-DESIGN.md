# Client portal — design, for the operator's review

**STATUS: PROPOSAL. NOTHING HERE IS BUILT, and nothing will be built until
the operator approves it.** The operator's instruction, 2026-09-23:
"`docs/CLIENT-PORTAL-DESIGN.md` for review; build nothing until approved."

This is written to be argued with. Every section that needs a decision says
so and names the alternatives; §9 collects them.

---

## 1. WHAT IT IS, IN ONE PARAGRAPH

A page a client signs in to and sees the state of their own outreach:
which accounts are where, what has actually been sent, what came back, and
what is waiting on them. The same answers the Slack agent gives in their
channel, in a surface they can open on a Monday morning without asking.

**It is a READER.** It answers; it does not act. Approvals are the one place
that argument gets tested, and §6 takes it seriously rather than assuming.

---

## 2. WHY THIS IS MOSTLY ASSEMBLY, NOT NEW SYSTEM

The honest version of this proposal is that **most of it already exists and
is already scoped**, and the portal is a second surface over the same
answers. That is the argument for building it and also the reason to keep it
small.

| what the portal needs | what already answers it |
|---|---|
| a client's own answers, scoped | `slackagenttools.REGISTRY` — 23 client-visible tools |
| the scoping itself | `slackscope.Scope`, `for_scope`, `run`'s refusal |
| a backstop on the way out | `Scope.check_outbound`, `for_client` |
| the account vocabulary | `src/accountstate.py` — the operator's eight states |
| a document | `clientreport.build`, `weeklyreportpdf` |
| a weekly rhythm | `weeklyreportwatch` — Monday 08:00, 07:30 preview |
| authentication and tenancy | `PRODUCTION-AUTH.md`, `src/web/security.py` |

**The portal should add no readback of its own.** If it needs a number the
Slack agent cannot already give in a client channel, that is a new tool with
a scope decision attached — made once, in the registry, where both surfaces
inherit it. Two code paths to one client's data is how they drift, and this
repository has that failure written down three times.

---

## 3. THE SCOPING ARGUMENT, WHICH IS THE WHOLE RISK

A Slack channel is bound to one workspace by policy, and the binding is
resolved per turn. A browser session is bound to a **person**, and a person
can in principle have more than one membership. Those are not the same shape
and the difference is where a leak would come from.

**Proposal: the portal resolves a `Scope` exactly as Slack does, per
request, and every read goes through `slackagenttools.run`.** No direct
store access from a view. That buys three things already paid for:

- an internal-only tool is refused rather than filtered;
- `for_client` corrects the material — timezones into the client's own, and
  internal campaign labels into "email campaign 491";
- `check_outbound` is available as the last pass.

**What must be decided rather than inherited:** Slack's `client_channels()`
drops a channel bound to two workspaces entirely, because an ambiguous
binding is not a binding. The browser equivalent is a person with two
memberships, and **there the answer must be an explicit workspace switcher,
never a merged view.** A single page showing two clients' figures together
is the one thing this system must never render.

---

## 4. WHAT A CLIENT SEES

### 4a. The account picture — settled, do not reopen

The operator's eight states, in order, plus `unanswerable` as its own tile:

    untouched · sequenced · engaged · replied · meeting · won · lost ·
    do_not_contact          + unanswerable

This is decided (2026-09-23) and already implemented in `accountstate`, the
weekly report, the PDF and `working_on`. **The portal inherits it and must
not introduce a ninth word.** `in_flight` is a SUM of four of them and is
never rendered beside the eight.

Two properties that have to survive into a web page, because they are the
reason the vocabulary was rewritten:

- **`unanswerable` renders even at zero.** A tile that appears only when
  non-zero is a tile nobody notices has appeared.
- **`won` and `lost` say why they are zero.** Nothing in this system records
  a deal, and `0 won` read as a measurement is the failure.

### 4b. What has been sent — the provider's counters, never our status

`sends_today` and `activity_this_week` read the provider. A campaign's local
`status` field has said `active` for weeks on a campaign that sent nothing.
**Enrolled is not sent, and the page must show both or neither.**

And where a cap hides campaigns, the page says so — `campaigns_not_read` is
part of the answer, not a footnote to drop in a redesign.

### 4c. What came back

`replies`, with the same rule the Slack answers use: human excludes
out-of-office, automated acknowledgements and assistant redirects.

**`positive` is not shown yet.** `replyverdict.positive_confirmed` is 0
until a verdict can be proved to come from the current rule set, and a
portal tile reading "3 positive replies" that turns out to be an
autoresponder is worse in a browser than in a chat message, because a page
looks like a record.

### 4d. What is waiting on them

`working_on`'s `waiting_on_you`. **Our own backlog is a count, not a list**,
for the reason that tool already documents.

---

## 5. WHAT IT MUST NEVER DO

1. **Never show another client's anything.** Enforced by the scope, asserted
   by the same registry-enumerated tests that cover Slack.
2. **Never merge two workspaces into one view** — §3.
3. **Never state a number that is not in a readback.** The Slack path has
   `unsupported_numbers` because a model rounded 878 to "about 900". A
   portal computing a percentage client-side is the same class of defect
   with no guard in front of it. **Rates come from the readback or are not
   rendered.**
4. **Never name a person at Resonate, a provider, a worker, or an
   experiment arm.** `CLIENT_FORBIDDEN_TERMS` already enumerates these.
5. **Never act.** See §6.

---

## 6. APPROVALS — THE ONE PLACE "READ ONLY" IS UNDER REAL PRESSURE

`working_on` reports accounts awaiting the client's approval. The obvious
next question is "let them approve it here", and it is a genuinely good
product idea. **It is also the thing that turns a reader into a writer**,
and this system's entire safety argument is that the client-facing surface
cannot act.

Three options, and the recommendation is the middle one:

1. **Read-only.** The portal shows what is pending and the client replies in
   Slack or by email. Safe, and mildly insulting to the client.
2. **RECOMMENDED — the portal raises a TICKET, exactly as the Slack agent
   does.** A click records an intent; a person at Resonate executes it
   through the existing gates. The client gets a button and the system gets
   no new write path. `slackrequests` already has the shape.
3. **Direct approval through `clientapproval.record`.** Only if the operator
   decides the approval record is genuinely the client's to write. It is a
   real write to a file that gates spend, and it would need its own
   authorization argument in `PRODUCTION-AUTH.md` terms.

**This is decision 1 for the operator.**

---

## 7. AUTHENTICATION — READ `PRODUCTION-AUTH.md`, DO NOT RE-DERIVE IT

Its rule is already the right one: an identity provider proves the
*address*; the membership table decides what that address may *do*; and
neither is allowed to learn the other's job. No row or no membership is a
403 with no session.

**Nothing here proposes changing that.** The portal is a consumer of it. The
only new question is §3's: what a person with two memberships sees.

Note `RELEASE-CANDIDATE.md`'s finding, which applies directly: signing in
proving nothing about *who somebody is* is why the demonstration could go
online and the product could not. A client portal is the product.

---

## 8. WHAT I WOULD BUILD FIRST, IF APPROVED

Smallest thing that is genuinely useful and proves the scoping:

**One page. One workspace. Four blocks: the eight account tiles, what was
sent this week, what came back, what is waiting on you.** Every number from
`slackagenttools.run`. No approvals, no export, no second workspace, no
charts.

Then, in order: the workspace switcher (§3), the weekly PDF as a download
(it already exists), approvals as tickets (§6).

**What I would not build early:** anything that computes. The first
client-side percentage is the first number nothing guards.

---

## 9. THE DECISIONS THIS NEEDS FROM THE OPERATOR

1. **Approvals: read-only, ticket, or direct write?** §6. Recommendation:
   ticket.
2. **A person with two memberships: switcher, or one membership per
   login?** §3. Recommendation: explicit switcher, never merged.
3. **Is `positive` shown once rules-4 lands, or does it stay out of the
   client surface entirely?** §4c.
4. **Does the portal replace the Monday Slack post, sit beside it, or is the
   post reduced to a link?** The weekly report and its 07:30 stop already
   exist; a portal makes the post redundant or makes it an announcement.
5. **Who is the user?** One named contact per client, or anyone at the
   client's domain? This decides the membership model and it is a
   commercial question, not a technical one.

---

## 10. WHAT THIS DOCUMENT IS NOT

It is not a schedule, it is not a commitment, and it does not describe
anything that exists. **No code has been written for it.** The next action
is the operator's review, and the five questions in §9 are the review.
