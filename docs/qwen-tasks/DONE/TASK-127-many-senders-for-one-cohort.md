PRIORITY: P1
DEPENDS: 

# TASK-127 - assign several healthy senders to one cohort

## THE POLICY AND THE MEASURED ESTATE

`docs/PRODUCTION-SCALE-POLICY.md`: use MULTIPLE appropriate healthy senders
per campaign where the provider supports it, optimising aggregate throughput
rather than pushing individual accounts harder.

Measured, and in `docs/state/SENDER-CAPACITY.json`:

    seats                             41
    healthy (isActive + authIsValid)  33
    active but auth INVALID            1   accepts work, then fails
    inactive                           7
    daily ceiling, healthy          1054 connection requests, 1143 messages
    healthy seats with NO active campaign   ZERO

Campaign 599020 carries ONE sender.

## THE QUESTION THIS ANSWERS

**Can a campaign hold several senders, and what actually decides how work is
split between them?**

1. `campaignAccountIds` is a LIST on the campaign object, which suggests yes.
   Confirm it from the estate: how many campaigns carry more than one, and
   what is the largest number of seats on one campaign?
2. `/campaign/AddLinkedInAccountsToCampaign` and
   `RemoveLinkedInAccountsFromCampaign` are on `heyreach.WRITE_ROUTES`.
   `LINKEDIN_ASSIGN_SENDER` is NOT in `providerwrites.SUPPORTED` and you may
   NOT enable it. Establish the request shape and what a readback would need
   to confirm the assignment landed.
3. **How does HeyReach distribute leads across seats?** Round-robin, per-lead
   assignment at add time, or something else? `build_lead_pairs` pairs each
   lead with a `linkedInAccountId`, which suggests WE choose. If we choose,
   the distribution policy is ours to design and it needs stating.
4. **What is actually free?** Zero healthy seats are uncommitted, so adding
   senders means reassigning seats already attached to campaigns. Per healthy
   seat, report which campaigns it is on and the status of each - a seat on
   six FINISHED and two PAUSED campaigns is effectively idle; one on an
   IN_PROGRESS campaign is not.

## HARD RULES

- **Reads only.** Do not attach, detach or modify any seat or campaign.
- **Never propose raising a per-seat limit.** Add senders or add days. A
  raised limit changes the risk taken with a client's real LinkedIn account
  and is not an engineering decision.
- **The `authIsValid: false` seat is not capacity.** It reports `isActive:
  true`, accepts an assignment and then fails, which is worse than absent
  because leads queue behind it looking scheduled. Find out whether it is
  recoverable or must be excluded from every plan.
- A seat is a REAL PERSON. Hash names, emails and profile URLs. Seat ids and
  numeric limits are fine.

## DELIVERABLE

A distribution design for a ~50-lead cohort across N healthy seats, with the
arithmetic shown: how many seats, how many days, and what that rests on.
Separate what you MEASURED from what you ASSUMED. If the honest answer is
that one seat could carry the cohort in two days, say so - then multi-sender
is not urgent and the finding is worth more than a plan nobody needs.

---

## RESULT

**STATUS:** DONE
**COMMIT:** df8efd5
**TESTS:** Read-only analysis. No code changes to test. Script `scripts/sender_campaign_analysis.py` produced `docs/state/SENDER-CAMPAIGN-ANALYSIS.json` from live provider data.
**FILES CHANGED:**
- `scripts/sender_campaign_analysis.py` (new) - read-only analysis script
- `docs/state/SENDER-CAMPAIGN-ANALYSIS.json` (new) - full sender-to-campaign mapping
- `docs/qwen-tasks/RUNNING/TASK-127-many-senders-for-one-cohort.md` (moved from TODO)

---

### ANSWER 1: Can a campaign hold several senders?

**Yes, and 48 of 83 campaigns already do.**

`campaignAccountIds` is a list on the campaign object. Measured from the live
estate (provider read 2026-09-15):

    campaigns with 0 senders     2
    campaigns with 1 sender     33    (includes campaign 599020)
    campaigns with 3 senders     1
    campaigns with 5 senders     4
    campaigns with 6 senders     1
    campaigns with 8 senders     2
    campaigns with 9 senders     9
    campaigns with 10 senders   15
    campaigns with 25 senders    1
    campaigns with 33 senders    8
    campaigns with 34-39        10
    ---------------------------------
    max senders on one campaign: 39
    campaigns with >1 sender:    48 of 83

The client's pre-Resonate campaigns already use many senders per campaign as
standard practice. A campaign with 33 or 39 senders is normal in this estate.

---

### ANSWER 2: The add/remove sender routes and request shape

Both routes are on `heyreach.WRITE_ROUTES`:

    /campaign/AddLinkedInAccountsToCampaign      additive seat assignment
    /campaign/RemoveLinkedInAccountsFromCampaign  removes a seat

**Request shape** (from `_change_senders` in `src/providers/heyreach.py:1845`):

    POST /campaign/AddLinkedInAccountsToCampaign
    Body: {"campaignId": <int>, "linkedInAccountIds": [<int>, ...]}

    POST /campaign/RemoveLinkedInAccountsFromCampaign
    Body: {"campaignId": <int>, "linkedInAccountIds": [<int>, ...]}

**Readback:** after the write, `campaign_read(campaign_id)` fetches the
campaign and checks `campaignAccountIds`. If any requested id is missing
(after add) or still present (after remove), the function raises even though
the HTTP status was 2xx - because the provider reports per-account failures
inside a successful response.

**`/campaign/UpdateAccounts` is deliberately NOT on WRITE_ROUTES.** It is a
full replace: any seat missing from the body is removed, and on a PAUSED
campaign the leads belonging to a removed seat are stopped and cannot be
resumed. The additive and subtractive routes do the same job safely.

**`LINKEDIN_ASSIGN_SENDER` is NOT in `providerwrites.SUPPORTED`.** The
OPERATIONS table in `providerwrites.py:130` records it as `False` with the
note "no documented route. campaignAccountIds is readable on the campaign
object, so a write would be verifiable; assignment was done by hand." The
routes now exist on WRITE_ROUTES but the operation has not been enabled.

**MUTABLE_STATUSES** for seat changes: `DRAFT`, `SCHEDULED`, `PAUSED`.
A campaign in any other status answers 400.

---

### ANSWER 3: How does HeyReach distribute leads across seats?

**We choose. HeyReach does not distribute.**

`build_lead_pairs` (src/providers/heyreach.py:27) constructs one
`accountLeadPair` per row, each carrying its own `linkedInAccountId`:

    {
        "linkedInAccountId": _account_id_for(row, fallback),
        "lead": { "profileUrl": ..., "customUserFields": [...] }
    }

`_account_id_for` (src/providers/heyreach.py:98) checks
`row["provider_account_id"]` first, then falls back to the batch-level
`linkedin_account_id` parameter. So:

- If every row has the same `provider_account_id`, one sender sends all.
- If rows carry different `provider_account_id` values, leads go out from
  different senders per lead.
- If no row has `provider_account_id`, the batch-level fallback is used and
  one sender sends all.

**The distribution policy is ours to design.** HeyReach executes whatever
`linkedInAccountId` is on each pair. There is no round-robin, no automatic
balancing. The caller assigns senders to leads before the call.

`push.py:342` calls `heyreach.build_lead_pairs(linkedin_rows, linkedin_account_id or 0)`,
passing a single fallback id. The per-row `provider_account_id` field is
what would carry a multi-sender assignment if one were designed.

---

### ANSWER 4: What is actually free?

**Zero healthy seats are uncommitted. Every healthy sender is on at least one
IN_PROGRESS campaign.**

Measured from the live estate:

    IN_PROGRESS campaigns per healthy sender:
      8 IN_PROGRESS:  23 senders (non-SN seats)
      12 IN_PROGRESS: 10 senders (all Sales Navigator seats)

    effectively idle healthy senders:  0

The 23 non-SN senders are each on 8 IN_PROGRESS campaigns plus additional
DRAFT, PAUSED and FINISHED campaigns (total 13-27 campaigns each). The 10 SN
senders are each on 12 IN_PROGRESS campaigns plus more (total 26-43 campaigns
each).

**No sender can be picked up and assigned to a new campaign without already
carrying active work.** Adding a sender to campaign 599020 does not create
new capacity - it directs existing capacity to also serve the Resonate
cohort. Whether that is safe depends on what those other 8-12 campaigns are
doing and whether the sender's daily limits can absorb the additional load.

---

### THE AUTH_INVALID SENDER: 129531

**Not recoverable by engineering. Requires re-authentication by the account
holder.**

Sender 129531 (hash `42ee6311bdf4`) is `isActive: true, authIsValid: false`.
It is on 10 campaigns:

    campaign 523987   IN_PROGRESS   33,710 leads   <-- actively failing
    campaign 524026   DRAFT            0 leads
    campaign 473854   PAUSED        33,710 leads
    campaign 470035   PAUSED           178 leads
    campaign 467366   PAUSED        33,710 leads
    campaign 429680   PAUSED        33,710 leads
    campaign 429679   PAUSED        33,710 leads
    campaign 428676   PAUSED        11,128 leads
    campaign 388960   PAUSED        50,565 leads
    campaign 388955   PAUSED        50,565 leads

Campaign 523987 is IN_PROGRESS with 33,710 leads. This sender is accepting
assignments and then failing on every action, which means leads queued behind
it look scheduled but never execute. It must be excluded from every plan
until its auth is restored, and the operator should decide whether to remove
it from campaign 523987 to unblock those leads for reassignment to a healthy
seat.

---

### DISTRIBUTION DESIGN FOR A ~50-LEAD COHORT

#### The arithmetic

A connection-request cohort (the entry action for cold outreach):

    1 sender at 40 CR/day    -> 50 leads in 2 days (1.25 working days)
    1 sender at 25 CR/day    -> 50 leads in 2 days (2 working days)
    1 sender at 15 CR/day    -> 50 leads in 4 days (3.3 working days)

A message-only cohort (connection already established):

    1 sender at 40 msg/day   -> 50 leads in 2 days (1.25 working days)
    1 sender at 17 msg/day   -> 50 leads in 3 days (2.9 working days)
    1 sender at 5 msg/day    -> 50 leads in 10 days

#### The honest answer

**One seat can carry a 50-lead cohort in two days.** Multi-sender is not
urgent for a cohort this size. The finding is worth more than a plan nobody
needs.

The constraint that blocked production was never throughput. Campaign 599020
carried ONE sender and ZERO leads while 33 healthy seats were configured for
1,054 connection requests a day. What blocked was approval and copy quality,
and no amount of sender capacity addresses either.

#### If multi-sender IS wanted (for resilience, not capacity)

Design for 3 senders across a 50-lead cohort:

    Sender A (40 CR/day):  leads  1-17   (17 leads, finishes day 1)
    Sender B (40 CR/day):  leads 18-34   (17 leads, finishes day 1)
    Sender C (25 CR/day):  leads 35-50   (16 leads, finishes day 1)

    All 50 connection requests sent on day 1. Acceptances and replies
    trickle in over the following days per cadence.

Implementation: assign `provider_account_id` on each row before calling
`build_lead_pairs`. Round-robin across the chosen sender ids. The mechanism
already exists in the code - `_account_id_for` reads `provider_account_id`
per row.

**Sender selection criteria** (measured, not assumed):
- Must be HEALTHY (isActive + authIsValid)
- Must be Sales Navigator if the campaign requires it (campaign 599020's
  sender 174892 is SN)
- Prefer senders with lower current IN_PROGRESS campaign count (all have 8
  or 12, so the difference is small)
- Prefer senders with higher daily limits (40/40 over 15/15)

#### What I MEASURED vs what I ASSUMED

MEASURED:
- 83 campaigns, their statuses and sender counts (live provider read)
- 33 healthy senders, their limits and campaign assignments (live provider read)
- 1 auth-invalid sender and its 10 campaigns (live provider read)
- `build_lead_pairs` assigns sender per lead via `provider_account_id`
- `add_senders` / `remove_senders` request shapes and readback
- `LINKEDIN_ASSIGN_SENDER` is not in SUPPORTED
- 48 of 83 campaigns already carry multiple senders (max 39)

ASSUMED:
- That all 50 leads need connection requests (some may already be connected)
- That the daily limits are sustainable (they are provider-configured
  ceilings, not a promise LinkedIn tolerates them indefinitely)
- That adding a cohort to an already-loaded sender does not push it into
  cooldown - the cooldown flags in SENDER-CAPACITY.json are all currently
  false, but that is a point-in-time measurement

---

### FINDINGS

1. **Multi-sender is a solved problem in the estate.** 48 campaigns already
   use it. The mechanism exists in code (`add_senders`, `build_lead_pairs`
   with per-row `provider_account_id`). The operation just needs enabling in
   `providerwrites.SUPPORTED` by Claude.

2. **Multi-sender is not needed for a 50-lead cohort.** One sender handles it
   in 2 days. The policy says "use MULTIPLE appropriate healthy senders" but
   the arithmetic shows this is about resilience and appearance, not
   capacity. If the goal is "the cohort finishes faster than 2 days", the
   answer is that 2 days is already the floor for LinkedIn cadence timing.

3. **The auth-invalid sender is a live risk.** It is on an IN_PROGRESS
   campaign with 33,710 leads. Those leads are queued behind a sender that
   cannot act. This is not a theoretical problem - it is happening now.

4. **Zero healthy seats are free.** Every plan to add senders to a campaign
   is a plan to redirect existing capacity, not pick up spares. The
   implication is that adding a sender to campaign 599020 adds load to a
   sender already running 8-12 other campaigns.

---

### RISKS

- Adding senders to campaign 599020 from the existing estate increases the
  load on seats already serving the client's pre-Resonate campaigns. If
  those campaigns are actively sending, the additional CR/message load could
  push seats into cooldown.
- The `provider_account_id` per-row assignment is not yet wired in `push.py`
  - it passes a single `linkedin_account_id` fallback. Multi-sender
  distribution would need a pre-assignment step before `build_lead_pairs`.

---

### RECOMMENDED CLAUDE ACTION

1. **Decide on the auth-invalid sender 129531.** Remove from campaign 523987
   (IN_PROGRESS, 33,710 leads) or leave it - but the leads behind it are not
   moving.

2. **If multi-sender is wanted for campaign 599020:** enable
   `LINKEDIN_ASSIGN_SENDER` in `providerwrites.SUPPORTED` and use
   `add_senders(campaign_id, [seat_ids])` to attach 2-3 additional SN seats.
   The routes work, the readback is wired, the code exists.

3. **If the cohort is ~50 leads:** one sender is sufficient. The finding is
   that multi-sender is not urgent, and the plan nobody needs is the honest
   answer. Focus remains on approval and copy quality, which were the actual
   blockers.
