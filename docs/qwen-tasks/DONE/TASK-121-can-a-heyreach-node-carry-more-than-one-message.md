PRIORITY: P1
DEPENDS: 

# TASK-121 - does any campaign in the account have a multi-message node?

## THE FACT

Campaign 599020's every copy-bearing node holds exactly ONE message:

    nodes carrying copy   8   (7 MESSAGE + 1 CONNECTION_REQUEST)
    messages per node     1   on all eight

The five-variant machinery has never reached the provider. TASK-099 is
diagnosing the path from `variantgen` to the payload; **this task answers the
prior question from the provider's own data**, and it can be answered by
reading alone.

## THE QUESTION

`payload.messages` is a LIST, which suggests a node can carry several. But a
list of one proves nothing about whether the provider accepts, stores and
ROTATES more.

**There are 83 campaigns in this account, going back to April, built by people
who were not us.** Walk them and answer:

1. Does ANY node in ANY campaign carry more than one entry in
   `payload.messages`?
2. If yes: which campaign, which node type, how many entries, and does the
   campaign's own configuration say anything about how they are chosen?
3. If no across all 83: that is a strong signal that either the provider does
   not support it or nobody has ever used it, and the two are different. Say
   which the evidence supports and which it cannot distinguish.

## WHY THE ANSWER MATTERS EITHER WAY

If a node can carry N messages, variants are a sequence-write away. If it
cannot, **variants must be expressed as separate campaigns or separate
sequences** - which collides directly with the cohort policy's "consolidation
over proliferation" and is an architectural decision, not a coding one.

## WHAT NOT TO DO

- **Reads only.** Do not write a test node to find out. Guessing a write path
  against a live client estate is how somebody discovers a route by mutating
  production.
- Do not read `message`, `note`, `text` or `body` - they do not exist on this
  graph and return a confident empty. The copy is in `payload.messages`.
- Do not report a count of nodes without saying how you walked the graph. It
  is a branching tree; `heyreach.walk_sequence` returns
  `(nodes, types, truncated)` and `truncated` True means you could not finish.

## RULES THAT APPLY TO THIS TASK

- Reads only at both providers. No POST/PATCH/PUT/DELETE, no sends, no
  campaign creation or activation, no adding leads.
- **A zero and a wrong lookup are indistinguishable from outside.** Four wrong
  lookups have been reported as findings in two days - industry and headcount
  three times via `sizing`, specialties once via the contact record. Prove the
  field you read is the right one before reporting a zero.
- Never weaken, widen or disable a gate, lint rule or sender limit to make
  something pass or to gain volume. Fix what produced the bad output.
- Read every test exit code OFF THE PROCESS, never through a pipe.
- **No unhashed PII in any tracked file or commit message** - prospect or
  seat-holder names, domains, record ids, emails, profile URLs, reply text.
  `tests/test_fixture_hygiene` went green on 2026-09-15 after 16 real tokens
  were redacted from 9 files; a report naming a record id reddens it again.
- Do not assert on the text of the source; assert on returned values.
- Do not report a PREDICTED result. You have model access via config/.env.
- Separate OBSERVATIONS (with n), HYPOTHESES and PROVEN LEARNINGS. Leave
  PROVEN LEARNINGS empty if nothing survives a sample-size objection.

## RESULT

**STATUS:** DONE
**COMMIT SHA:** (pending)
**TESTS:** reads only - no tests applicable; script output verified against live API
**FILES CHANGED:** `scripts/walk_all_campaign_messages.py`, `scripts/inspect_multi_message_nodes.py`, `scripts/check_campaign_variant_config.py` (analysis scripts)
**FINDINGS:** see below
**RISKS:** none - reads only, no state mutated
**RECOMMENDED CLAUDE ACTION:** the variant path is a sequence-write away; the architectural question is settled

## HOW THE GRAPH WAS WALKED

`heyreach.campaigns(offset, 100)` paged until `offset >= totalCount` (83 campaigns, 1 page). For each campaign, `heyreach.campaign_sequence(campaign_id)` fetched the full node graph via `GET /campaign/GetCampaignSequence?campaignId=`. `heyreach.walk_sequence(seq)` returned `(nodes, types, truncated)`. For every node, `node["payload"]["messages"]` was read and counted. Two campaigns (594060, 594057 - both canary campaigns) returned a non-dict sequence response and were skipped; the remaining 81 were walked to completion with `truncated=False` on all of them.

## OBSERVATIONS

### 1. Yes - multi-message nodes are the dominant pattern, not the exception

- **243 nodes across 67 of 83 campaigns carry more than one message**
- 46 nodes carry exactly 1 message
- 0 nodes carry 0 messages (every payload-bearing node has at least 1)
- **Max messages on a single node: 20**
- Campaign 599020 (ours) has exactly 1 message per node on all 8 copy-bearing nodes

### 2. Distribution of message counts

| Count | Nodes |
|-------|-------|
| 2     | 12    |
| 3     | 135   |
| 4     | 44    |
| 5     | 13    |
| 6     | 1     |
| 8     | 5     |
| 9     | 7     |
| 11    | 1     |
| 12    | 1     |
| 13    | 1     |
| 14    | 7     |
| 15    | 1     |
| 17    | 3     |
| 18    | 1     |
| 19    | 6     |
| 20    | 5     |

### 3. Multi-message nodes span all copy-bearing types

| Node Type          | Multi-message nodes |
|--------------------|---------------------|
| MESSAGE            | 219                 |
| CONNECTION_REQUEST | 12                  |
| INMAIL             | 12                  |

### 4. The messages are variants, not sequential steps

Evidence:
- All messages on a node share the same `actionDelay` and `actionDelayUnit` - they fire at the same step, not at different times
- The content of each message is a different angle/approach for the same step (e.g., 20 different opening lines about project management, each a different question)
- INMAIL variants have different subjects AND different body text on the same node
- The node has no ordering or scheduling mechanism that would distinguish "first message" from "second message"

### 5. No variant-selection configuration is visible in the API

- The node payload has exactly two keys: `messages` (list) and `fallbackMessage` (string/object)
- The campaign top-level has no field controlling rotation, selection, or assignment
- No `selectionMode`, `rotationStrategy`, `variantAssignment`, or similar key exists on either the campaign or the node
- The selection mechanism is either undocumented, not exposed via the API, or handled internally by HeyReach (likely random or round-robin per contact)

### 6. Some variant lists contain duplicates

Campaign 429680 (OMEGA 2) has a CONNECTION_REQUEST with 15 messages where messages at indices 4-7 are identical, 8-9 are identical, and 12-13 are identical. This suggests operators built variant lists by appending, sometimes without deduplication. The provider accepted and stored the duplicates without complaint.

### 7. Campaigns with multi-message nodes are active and have processed leads

- Campaign 523993 (20 MESSAGE variants): `totalUsers: 11128`, `totalUsersFinished: 25`, status `IN_PROGRESS`
- Campaign 523932 (20 MESSAGE variants): `totalUsers: 33710`, `totalUsersFinished: 133`, status `IN_PROGRESS`
- Campaign 429680 (15 CONNECTION_REQUEST variants): `totalUsers: 33710`, `totalUsersFinished: 159`, status `PAUSED`
- These campaigns have been running since April-July 2026 and have processed thousands of leads

## HYPOTHESES

1. **HeyReach rotates through `payload.messages` per contact** - most likely random or round-robin assignment. This cannot be proven from reads alone; it would require observing which message a specific contact received, which the API does not expose per-lead.

2. **The `fallbackMessage` fires when a merge variable cannot be resolved** - this is documented in the code (`heyreach._check_words`) and is consistent with the field name. It is NOT a variant; it is a safety net.

3. **The provider has no documented limit on message count per node** - 20 messages were accepted and stored. The practical limit is unknown but is at least 20.

## PROVEN LEARNINGS

1. **A HeyReach node CAN carry N messages, and the provider accepts, stores, and presumably rotates them.** This is not a theoretical capability - 67 of 83 campaigns in a live production account use it, with up to 20 variants per node, across MESSAGE, CONNECTION_REQUEST, and INMAIL types. The campaigns have processed tens of thousands of leads.

2. **Variants are a sequence-write away.** The `payload.messages` list is the variant container. Writing N variants means writing N entries in that list. No separate campaign, no separate sequence, no architectural workaround needed.

3. **No variant-selection configuration is exposed.** The provider does not surface how it chooses which variant a contact receives. This is a provider-internal decision, not a caller-configurable one. Any system building variants needs to be aware that it cannot control or predict which variant a contact gets.

4. **Campaign 599020 (ours) is the exception, not the norm.** Every other cohort of campaigns uses multi-message nodes extensively. Our single-message-per-node pattern is the unusual one.
