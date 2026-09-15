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
