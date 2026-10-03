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
reviewed a sample of 100 replies the classifier called positive.** Measured
reason: a reply reading "Stop" was classified `positive` at 0.75 confidence
(2026-10-02). The 899-reply email corpus holds **20** positives in total, so the
sample cannot be filled from email alone — the real count is the finding, not
something to pad, and the sample goes to copy-review before any rate here is
trusted.

---

## What this machine holds about Farseer, measured 2026-10-03

The operator's account of Farseer — **35 meetings in 14 countries, the only
campaign where the channels were coordinated per account** — is not
reconstructible from this machine today, and here is exactly what is and is not
here. Nothing below is inferred from the campaign's name or from memory.

| question | what the machine says | command |
|---|---|---|
| Is Farseer a client config in this repo? | **No.** `config/clients/` holds `productive`, `demo` and `contactout.example` only. | `ls config/clients/` |
| Does the name appear in the repo at all? | **`farseer.io` is on `config/suppress.local.txt`** — a suppressed DOMAIN, which is what a client of ours looks like in this file, not a prospect. | `grep -ril farseer config/` |
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

**PENDING both lanes.** This section is deliberately empty rather than
partially filled: a corpus assembled from one channel while the other is still
being read would be ranked by the metric and read as complete.

**These positives are an exemplar corpus for the writer only AFTER the
operator's review.** Nothing from here goes into `prompts/exemplars/` or
`WRITER_SYSTEM` before that.
