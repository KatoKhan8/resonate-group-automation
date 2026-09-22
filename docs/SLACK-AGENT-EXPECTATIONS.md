# What will be asked next — expectations for the week of 2026-09-22

From the last ten days of Slack: **351 messages, 53 promise-shaped, 21
threads opened with a question.** Same redaction rules as the question
catalogue — no names, no clients, no amounts.

The point of this file is that the agent and the 07:15 briefing should
already hold the answer when the question arrives, rather than reading for
it while somebody waits.

---

## 1. THE OPEN PROMISE THAT IS ALREADY LATE

**A client asked for the list of sending domains on 2026-09-22 at 09:18.**
The reply was "we'll send the latest list today or tomorrow". At 11:17 a
194KB CSV of every *sender* was attached — which is not what was asked for
— and the next message was a question about one unfamiliar domain.

    STATUS      answered with the wrong artefact, one follow-up outstanding
    EXPECT      "what is <domain>", and a repeat of the original ask
    READY       `sending_domains` answers both, with the list built in code
    BLOCKED ON  the operator's "go"; the Croatian reply is drafted and unsent

This is the single most likely question of the week and it is already
drafted.

## 2. RECURRING, BY THE CALENDAR

| When | What is asked | Ready? |
| --- | --- | --- |
| Monday morning | *jesu puštene kampanje?* — did the campaigns go out | ✓ `sends_today`, `activity_this_week` |
| Monday/Tuesday | weekly numbers: connections, replies, meetings | **partly** — meetings booked is MISSING |
| Mid-week | *kakav nam je status s ovim leadom?* | ✓ `lead_lookup` |
| Mid-week | bounce and domain health after a push | ✓ `sender_roster`, `sending_domains` |
| Month end | the monthly outbound report | **MISSING** — `clientreport.py` unwired |
| Any day | *jel ICP?* on a specific account | ✓ `account_lookup` |

The weekly update is a **habit with a shape**: connections accepted,
replies by channel, new interested leads as a bulleted list. Three of those
four numbers are answerable now.

## 3. WHAT THIS WEEK SPECIFICALLY WILL RAISE

**Campaigns 491-498 went active this morning**, first sends 13:02-14:13Z,
after sitting paused with 151 enrolled leads. Expect, within a day:

- *is it actually sending?* — ✓ answerable, and the distinction between
  enrolled and sent is already in every answer.
- *how many went out?* — ✓
- *what is the bounce rate looking like?* — ✓ per sender, against the 2%
  stop.
- *why did it take so long?* — the honest answer names an activation grant
  and is **internal**. A client channel gets the state, not the reason.

**LinkedIn.** 33 campaigns are in progress with connection requests still
at 0. Expect *jel krenuo LinkedIn?* Answerable as state; the seat count is
now resolvable but seat *ownership* is not attributed, so the agent gives a
workspace total and no names.

**Sender changes.** Six of the last ten days' sender questions are about
adding, pausing or swapping a domain. These are change requests and the
ticket flow takes them — but every one so far came from an internal person,
who will be surprised that the agent raises a ticket rather than doing it.
Worth saying once in `#resonate-os`.

## 4. WHAT THE 07:15 BRIEFING SHOULD LEAD WITH THIS WEEK

1. Whether 491-498 actually sent, with the provider's counter beside the
   enrolled figure.
2. Any sender over 1.5% bounce — early enough to matter, not at 2%.
3. Open change requests awaiting the operator, by id.
4. Anything promised to a client in the last 48 hours and not delivered —
   **this file's own reason for existing**, and not yet automated. The
   promise-shaped scan is in the history script; nothing consumes it.

## 5. THE GAP THIS EXERCISE FOUND

Fifty-three promise-shaped messages in ten days, and **no system anywhere
tracks whether any of them was kept.** The domain-list promise on Monday
was kept in 119 minutes with the wrong artefact, and the only reason
anybody knows is that the client replied.

A `promises` readback — messages containing a commitment, with whether a
matching delivery followed — is the highest-value thing this history
suggests building, and it is not on the tool list yet because it needs a
decision about what counts as delivery.
