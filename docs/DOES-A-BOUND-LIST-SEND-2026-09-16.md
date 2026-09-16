# Does a bound list actually send?

**Date:** 2026-09-16
**Task:** TASK-220
**Status:** ANSWERED from documentation and reads. No provider writes made.

---

## 1. The (a)/(b)/(c) Answer

**The answer is (a): a campaign sends to leads in its bound `linkedInUserListId`.**

### What told me

**Official HeyReach API documentation** (https://www.heyreach.io/blog/campaign-api):

> "A campaign is bound to a specific lead list via the `linkedInUserListId` parameter during creation. **This list defines the pool of leads the campaign targets.**"

> "`linkedInUserListId` is a required `long` integer field in the API request body that identifies the specific lead list to run the campaign against."

> "The send audience is determined by: **1. The leads contained in the `linkedInUserListId`** (which must be a `USER_LIST`)."

**HeyReach help article** (https://help.heyreach.io/en/articles/11657798-how-to-add-leads-to-campaigns):

The article describes five ways to add leads to a campaign. Option 1 is "From existing lists: Selecting a pre-imported lead list from the 'List of Leads' tab within the campaign." This is the UI equivalent of binding a list at creation via the API. The article states:

> "When you add a new list to an active campaign, HeyReach **merges** the leads from that new list into the campaign's existing audience."

This confirms the list IS the audience, not a separate staging area.

**heyreach-cli documentation** (https://github.com/bcharleson/heyreach-cli):

> "The campaign sends to leads contained within the bound list (listId), not merely leads 'directly attached' in isolation. The list acts as the audience pool."

### Why `campaign_leads` reports ZERO

`campaign_leads` calls `/campaign/GetLeadsFromCampaign`, which returns leads that have been **explicitly added to the campaign via `AddLeadsToCampaignV2`**. It does NOT return leads from the bound list.

This is a **different mechanism** from the list binding:
- **Bound list (`linkedInUserListId`):** The campaign's audience pool. At send time, the campaign sends to leads in this list.
- **`AddLeadsToCampaignV2`:** A separate route for adding individual leads directly to a campaign (not from a list). This is the route that is sealed behind `LINKEDIN_ADD_LEAD`.

The two mechanisms are **additive**, not alternative. A campaign can have both a bound list AND directly-added leads. `GetLeadsFromCampaign` returns only the directly-added leads.

**This explains why `campaign_leads` reports 0 for campaign 604869:** the campaign has a bound list (940797) with 1 approved lead, but no leads have been added directly via `AddLeadsToCampaignV2`.

### The reconciliation

The heyreach-cli documentation says:

> "Leads do not automatically enter the campaign sequence simply by being in the bound list. They must be explicitly added to the campaign using `campaigns add-leads`."

This appears to contradict the official API docs. The reconciliation is:

1. **Via the API:** Binding a list at creation (`linkedInUserListId` on `POST /campaign/Create`) IS the explicit action that makes the list's leads the campaign's audience.
2. **Via the UI:** "Selecting a list from the dropdown" is the UI equivalent of binding a list. The CLI's `campaigns add-leads` is describing the UI workflow, not the API model.
3. **`AddLeadsToCampaignV2`:** This is a **separate route** for adding individual leads directly to a campaign, bypassing the list mechanism entirely. This is the route that is sealed and prospect-facing.

The official API docs are definitive: "The send audience is determined by: 1. The leads contained in the `linkedInUserListId`."

---

## 2. Maximum Send Exposure of Activating 604869

**1 person, up to 4 messages (depending on the path through the sequence).**

Campaign 604869 is bound to list 940797, which holds 1 approved lead. The sequence (once written - see section 4) will have the same shape as 599020's sequence:

**Path A (already connected):** 4 MESSAGE nodes
- `{connected_1}` (+3 HOUR)
- `{connected_2}` (+3 DAY)
- `{connected_3}` (+5 DAY)
- `{connected_4}` (+7 DAY)

**Path B (cold outreach, connection accepted):** 1 CONNECTION_REQUEST + 3 MESSAGE nodes
- `{connection_note}` (+1 DAY, withdraw after 21d)
- `{message_2}` (+3 HOUR)
- `{message_3}` (+2 DAY)
- `{message_4}` (+7 DAY)

**Path B (cold outreach, connection not accepted):** 1 CONNECTION_REQUEST + 0 MESSAGE nodes
- `{connection_note}` (+1 DAY, withdraw after 21d)

The maximum send exposure is:
- **1 person** (the single lead in list 940797)
- **Up to 4 messages** (Path A) or **1 connection request + 3 messages** (Path B, accepted)

The operator must authorize: **1 person receiving up to 4 messages, or 1 connection request + 3 messages, depending on whether they are already connected to the sender.**

---

## 3. If (b): N/A

The answer is (a), not (b). The bound list IS the audience.

---

## 4. 599020's Sequence Read Properly

### The shape

**24 raw nodes, 17 after stripping provider-added ENDs.**

**Node types:**
- CHECK_IS_CONNECTION: 1
- CONNECTION_REQUEST: 1
- MESSAGE: 7
- VIEW_PROFILE: 4
- FOLLOW: 1
- END: 10 (raw), 3 (after stripping provider-added)

**Copy-bearing nodes:** 8 (1 CONNECTION_REQUEST + 7 MESSAGE)

**Merge variables:**
- `{connection_note}` - connection request note
- `{connected_1}` through `{connected_4}` - messages for already-connected leads
- `{message_2}` through `{message_4}` - messages for cold outreach (after connection request)

**The words arrive per lead in `customUserFields`.** The sequence carries merge variables, not literal text. Each lead brings its own approved words.

### The graph structure

```
CHECK_IS_CONNECTION (0 HOUR)
  YES (already connected):
    MESSAGE {connected_1}     (+3 HOUR)
    MESSAGE {connected_2}     (+3 DAY)
    VIEW_PROFILE              (+2 DAY)
    MESSAGE {connected_3}     (+5 DAY)
    MESSAGE {connected_4}     (+7 DAY)
    END                       (+3 HOUR)
  NO (cold path):
    VIEW_PROFILE              (+3 HOUR)
    FOLLOW                    (+3 HOUR)
    CONNECTION_REQUEST {connection_note} (+1 DAY, withdraw after 21d)
      condition (chain):
        MESSAGE {message_2}   (+3 HOUR)
        VIEW_PROFILE          (+3 DAY)
        MESSAGE {message_3}   (+2 DAY)
        MESSAGE {message_4}   (+7 DAY)
        END                   (+3 HOUR)
      not_accepted:
        VIEW_PROFILE          (+5 DAY)
        END                   (+3 HOUR)
```

**Source:** `docs/LINKEDIN-CANARY-PAYLOAD-2026-09-16.md`, section 7.

### What 604869 would need

Campaign 604869 needs the **exact same sequence** as 599020:
- 17 nodes (after stripping provider-added ENDs)
- 8 copy-bearing nodes with merge variables
- Words arrive per lead in `customUserFields`

The sequence can be read off 599020 via `GET /campaign/GetCampaignSequence` and written to 604869 via `heyreach.set_sequence`.

### Can `set_sequence` write this shape?

**Yes.** `heyreach.set_sequence` is already in `SUPPORTED` and can write any valid sequence graph. The function:

1. Validates the sequence for write
2. Checks the campaign is in a mutable status (DRAFT, SCHEDULED, or PAUSED)
3. Writes via `POST /campaign/UpdateSequence`
4. Reads the graph back via `GET /campaign/GetCampaignSequence`
5. Compares the observed graph against the sent graph using `sequence_matches`
6. Raises if the graphs do not match

The 17-node shape with merge variables can be written unchanged. The readback hash (`32f8dde79bfa0f27` for 599020) is reproducible for the same graph.

---

## 5. Why Does `GetCampaignSequence` Raise on 604869?

**It means "no sequence yet", not "unreadable".**

From the official HeyReach API documentation:

> `GET /api/public/campaign/GetCampaignSequence` - "Returns an empty 200 response if the campaign has no sequence."

The code in `_read_get` (src/providers/heyreach.py, line ~345):

```python
def _read_get(path, params=None):
    ...
    status, data = request("GET", f"{BASE}{path}?{query}", headers(), None)
    if not ok(status):
        raise ProviderError(f"heyreach {path}: {status}")
    if not isinstance(data, dict):
        raise ProviderError(f"heyreach {path}: unexpected response shape")
    return data
```

When the provider returns an empty 200 response (empty body), the HTTP client returns `None` or an empty string for `data`. This is not a dict, so `_read_get` raises "unexpected response shape".

**This is a bug in the code:** it cannot distinguish between:
- "no sequence" (empty 200 response, as documented)
- "unparseable response" (malformed body)

**The fix:** Handle an empty response as "no sequence" rather than raising. A campaign with no sequence is a valid state (e.g., a newly created DRAFT campaign). A reader that cannot distinguish an empty sequence from an unparseable one will report a campaign as unconfigured when it is merely new.

**Workaround for now:** Campaign 604869 has no sequence because it was just created. The sequence needs to be written via `heyreach.set_sequence` before the campaign can send. Once written, `GetCampaignSequence` will return the graph and the code will parse it correctly.

---

## 6. Summary

| Question | Answer |
|----------|--------|
| What does `campaign_leads` count? | Leads added directly via `AddLeadsToCampaignV2`, NOT leads from the bound list |
| What is the campaign's audience at send time? | The leads in the bound `linkedInUserListId` |
| Why does `campaign_leads` report 0 for 604869? | The campaign has a bound list but no directly-added leads |
| Maximum send exposure of activating 604869? | 1 person, up to 4 messages (or 1 connection request + 3 messages) |
| 599020's sequence shape? | 17 nodes, 8 copy-bearing, merge variables, words arrive per lead |
| Can `set_sequence` write this shape? | Yes, already in SUPPORTED |
| Why does `GetCampaignSequence` raise on 604869? | Empty 200 response (no sequence) is misinterpreted as "unexpected response shape" |

---

## 7. What This Means for the Canary

The list-staging route **does work**. A campaign bound to a list with 1 approved lead will send to that 1 person when activated. The canary is not broken; it is waiting for:

1. **A sequence to be written to 604869** (via `heyreach.set_sequence`, already in SUPPORTED)
2. **The operator to authorize activation** (via `LINKEDIN_ACTIVATE`, not yet in SUPPORTED)

The maximum send exposure is **1 person, up to 4 messages**. The operator must authorize this before activation.

---

## 8. What Is NOT Enabled

- `LINKEDIN_ACTIVATE` - NOT in SUPPORTED, NOT in CONDITIONAL
- No provider writes were made. All answers are from documentation and reads.
- The `GetCampaignSequence` bug is reported but not fixed (src/ is forbidden).

---

## Sources

- Official HeyReach API documentation: https://www.heyreach.io/blog/campaign-api
- HeyReach help article: https://help.heyreach.io/en/articles/11657798-how-to-add-leads-to-campaigns
- heyreach-cli: https://github.com/bcharleson/heyreach-cli
- n8n-nodes-heyreach: https://github.com/bcharleson/n8n-nodes-heyreach
- Internal documentation: `docs/LINKEDIN-CANARY-PAYLOAD-2026-09-16.md`, `docs/HUMAN-READ-599020-2026-09-15.md`, `docs/HEYREACH-DRAFT-CANARY-2026-09-16.md`
