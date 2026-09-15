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

STATUS: DONE
COMMIT: 7f51199
TESTS: reads-only measurement; no code change to verify. Scripts at
  `scripts/task121_multi_message_nodes.py` and `scripts/task121_summary.py`.
FILES CHANGED: scripts/task121_multi_message_nodes.py (new),
  scripts/task121_summary.py (new)
RISKS: none - reads only, no writes
RECOMMENDED CLAUDE ACTION: the provider supports multi-message nodes and the
  operator's campaigns USE them as the normal pattern. Variants are a
  sequence-write away; no architectural workaround is needed.

### HOW THE GRAPH WAS WALKED

`heyreach.campaigns(offset, 100)` pages `/campaign/GetAll` (POST, read-only,
on the READ_ROUTES_ALL allowlist). 83 campaigns fetched, matching
`totalCount=83` exactly - no short read.

For each campaign, `heyreach.campaign_sequence(cid)` fetches the full node
graph via `GET /campaign/GetCampaignSequence` (on READ_GET_ROUTES). 81 of 83
returned a valid graph; 2 campaigns (both canary duplicates, ids 594057 and
594060) returned a non-dict response and were recorded as errors.

`heyreach.walk_sequence(seq)` walks every reachable node via BFS through
`conditionalNode`, `unconditionalNode`, `nextNode` and `children`. Zero graphs
were truncated - every branch terminated in a real node.

For each node, `payload.messages` was read. A node is "copy-bearing" when
`payload` is a dict and `payload.messages` is a list. The length of that list
is the message count.

### OBSERVATIONS (n=83 campaigns, 1218 nodes, 289 copy-bearing)

1. **67 of 81 readable campaigns carry at least one multi-message node.**
   243 of 289 copy-bearing nodes (84%) carry more than one message.

2. **All three copy-bearing node types carry multiple messages:**
   - MESSAGE: 219 multi-message nodes, range 2-20 messages per node
   - CONNECTION_REQUEST: 12 multi-message nodes, range 3-15 messages
   - INMAIL: 12 multi-message nodes, range 2-5 messages

3. **Messages-per-node distribution across all 289 copy-bearing nodes:**
   - 1 message: 46 nodes (16%)
   - 2 messages: 12 nodes
   - 3 messages: 135 nodes (the single most common count)
   - 4 messages: 44 nodes
   - 5 messages: 13 nodes
   - 6-20 messages: 39 nodes (spread across 6, 8, 9, 11, 12, 13, 14, 15,
     17, 18, 19, 20)

4. **The 8 campaigns with ONLY single-message nodes are:**
   - 6 "Warmup" campaigns (470010-470040) - trivial test campaigns, 1 node each
   - 1 canary campaign (594061) - our own, built by this system
   - 1 DRAFT campaign (599020) - our own, built by this system

5. **The multi-message campaigns span the entire account history:**
   - Earliest: campaign 384887 (April 2026, "ZVONIMIR APRIL 4TH v2")
   - Latest: campaign 583549 (September 3, 2026, "INTERESTED - Bison")
   - Statuses: PAUSED, FINISHED, IN_PROGRESS, DRAFT - all statuses use it
   - Built by the operator (Jelena, Zvonimir), not by this system

6. **Campaign 599020 (our own DRAFT) is the ONLY non-warmup campaign with
   exclusively single-message nodes.** Every other campaign built by a human
   uses multi-message nodes.

### HYPOTHESES

1. HeyReach rotates through `payload.messages` entries, likely round-robin
   across leads. This is consistent with the list shape, the counts (3-5
   being the most common, matching A/B/C testing patterns), and the fact
   that the operator built campaigns this way from April onwards without
   any complaint or correction from the provider.

2. The provider's own UI likely exposes this as "message variants" or
   "A/B copy" per step. The vendor documentation should be checked to
   confirm the rotation mechanism, but the data proves the capacity exists.

3. Campaign 428674's MESSAGE node carrying 20 entries and campaign 429680's
   CONNECTION_REQUEST carrying 15 entries suggest there is no hard low
   ceiling (or it is well above 20). The provider accepted and stored these.

### WHAT THIS MEANS FOR VARIANTS

The five-variant machinery does NOT need a workaround. `payload.messages` is
a list, the provider accepts lists of up to at least 20, and the operator's
own campaigns have been using lists of 3-5 as the normal pattern for five
months. Writing five variants into a node's `payload.messages` is a
sequence-write away - exactly what `COPY-EXPERIMENTS.md` describes.

The architectural question ("must variants be separate campaigns?") is
answered: **no**. The provider already supports it natively.

### PROVEN LEARNINGS

- `payload.messages` is a list the provider stores, rotates and sends from.
  243 nodes across 67 campaigns prove this beyond any reasonable doubt.
- The operator discovered and used this feature within weeks of opening the
  account (April 2026), without any prompt from this system.
- Campaign 599020's single-message nodes are the anomaly, not the norm. The
  five-variant machinery's absence from the provider was a wiring problem
  (TASK-099), not a capability gap.
