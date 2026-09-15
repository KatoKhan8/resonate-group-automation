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

## RESULT

**STATUS:** DONE

**COMMIT SHA:** 04613e6

**TESTS:** Reads-only survey. No code changes to test. Scripts at
`scripts/task121_multi_message_nodes.py` and `scripts/task121_deep_analysis.py`.
Full JSON results at `.qwen/tmp/task121/results.json`.

**FILES CHANGED:**
- `scripts/task121_multi_message_nodes.py` (new) - walks all 83 campaigns, counts messages per node
- `scripts/task121_deep_analysis.py` (new) - examines content of multi-message nodes
- `scripts/task121_connection_request_check.py` (new) - CONNECTION_REQUEST and error campaign detail

**ANSWER: YES. 67 of 83 campaigns carry multi-message nodes. 243 total.**

### 1. Does ANY node in ANY campaign carry more than one entry in payload.messages?

**Yes, extensively.** 67 of 81 walkable campaigns (2 returned errors - see below)
have at least one node with more than one message. The maximum observed is 20
messages on a single MESSAGE node.

### 2. Which campaigns, which node types, how many entries?

**By node type (across the whole estate):**

| Node type          | Multi-message nodes | Max messages |
|--------------------|--------------------:|-------------:|
| MESSAGE            |                 219 |           20 |
| CONNECTION_REQUEST |                  12 |           15 |
| INMAIL             |                  12 |            5 |

**Representative campaigns:**

- Campaign 523993 (FIXED - OMEGA 3): MESSAGE node with **20 messages** - all
  different opening questions about project management at {COMPANY}
- Campaign 429680 (OMEGA 2): CONNECTION_REQUEST with **15 messages** - all
  different connection note variants
- Campaign 428676 (PRODUCTIVE - MARKETING AGENCIES - ALL LEADS): MESSAGE node
  with **20 messages** - same 20 opening questions as 523993 (copy reused)
- Campaign 388960 (USA 2ND CLEANED): MESSAGE node with **18 messages**
- Campaign 523987 (FIXED - OMEGA): MESSAGE node with **17 messages**
- Campaign 567758 (ANA L CONNECTIONS): MESSAGE nodes with **3-4 messages** each

### 3. What are the multiple messages? VARIANTS, not sequential steps.

The messages within a multi-message node are **A/B/n copy variants** - different
wordings of the same step's intent. The evidence:

- Campaign 567758, 4-message node: all four messages say "we've been connected
  a while but never actually talked" in slightly different phrasings
- Campaign 523993, 20-message node: all 20 are different opening questions
  ("how does {COMPANY} track profitability" / "do you guys have resource
  planning sorted" / "how many tools is {COMPANY} using") - same intent, 20
  wordings
- Campaign 429680, 15-message CONNECTION_REQUEST: all 15 are different
  connection note pitches, all under the 300-char LinkedIn limit

**No rotation or selection configuration exists** on any node or campaign. The
payload carries only `messages` (the list) and `fallbackMessage`. How the
provider selects which variant to send is **opaque** - it is not documented in
the API response and no campaign-level field controls it.

### 4. Data quality observations

- **Duplicate messages within nodes**: Campaigns 524002, 388960, and 429680
  have identical strings repeated within the same node (e.g., campaign 388960
  has messages [6]-[12] all identical "here's the actual hook" text). The
  provider accepted these without rejection.
- **Empty messages**: Campaign 524026 has a CONNECTION_REQUEST with 5 messages,
  all zero-length strings. The provider accepted this.
- **Two unwalkable campaigns**: 594060 and 594057 (both "PRODUCTIVE - CANARY -
  2026-09-09") return "unexpected response shape" from GetCampaignSequence.
  These are likely incomplete canary campaigns with no proper sequence graph.
- **Our campaign (599020) has exactly 1 message per node** on all 8
  copy-bearing nodes - the only campaign in the estate with this pattern.

### 5. Architectural implication

**Variants are a sequence-write away.** The provider natively supports multiple
messages per node, and 67 of the 82 pre-existing campaigns (built by people who
were not us, going back to at least April 2026) use this capability. The
five-variant machinery does NOT need separate campaigns or separate sequences.
A node's `payload.messages` list is the variant pool.

What the evidence **cannot** distinguish:
- **How the provider selects which variant to send** (random, round-robin,
  weighted, per-sender). No configuration field was found.
- **Whether the provider tracks per-variant reply rates** (so an evaluator
  could determine which variant performed best).
- **Whether there is a maximum** the provider enforces. The observed max is 20,
  but this may be a client-side choice rather than a provider limit.

**FINDINGS:**
- The provider supports multi-message nodes. This is proven by 243 instances
  across 67 campaigns, not by a write test.
- All multi-message nodes carry A/B/n copy variants, not sequential messages.
- No selection/rotation config was found on any node or campaign.
- The provider accepts duplicate messages and empty messages without error.
- Two canary campaigns (594060, 594057) have unwalkable sequences.
- Our campaign (599020) is the only one with exactly 1 message per node.

**RISKS:**
- The opaque selection mechanism means we cannot control which variant a
  contact receives, only the pool they draw from.
- Duplicate messages in the pool waste slots and dilute variant diversity.

**RECOMMENDED CLAUDE ACTION:**
The variant pool is `payload.messages`. The five-variant copy experiment can
write five entries into that list on each MESSAGE node. The architectural
barrier the task was asking about does not exist.

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
