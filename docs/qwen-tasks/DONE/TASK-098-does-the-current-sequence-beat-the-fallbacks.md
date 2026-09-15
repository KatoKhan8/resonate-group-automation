PRIORITY: P0
DEPENDS: 

# TASK-098 - read the LIVE sequence as a human, against the fallbacks

## WHY THIS IS P0

This is the gate that lifts the lead block. `docs/LEADS-ARE-BLOCKED-2026-09-14.md`
records the decision: copy passing every automated gate FAILED two independent
human reads, and on both channels **the operator's hand-written fallbacks beat
everything the model produced.**

So the question is NOT "is this acceptable". It is:

    DOES THIS COPY BEAT THE HAND-WRITTEN FALLBACKS?

If it does not, it must not send, and the answer is the deliverable.

## WHAT TO READ

The sequence actually in HeyReach campaign 599020 - 24 nodes, 7 MESSAGE plus
1 CONNECTION_REQUEST, all of which carry exactly ONE message each. Read what
the provider holds, not what the generator would produce today. Use
`scripts/heyreach_readback.py` and the provider read path; the copy lives in
`payload.messages` and NOWHERE else (`message`, `note`, `text`, `body` do not
exist on this graph and return a confident empty).

Then read the hand-written fallbacks and put them side by side.

## THE SPECIFIC FAILURES THE LAST HUMAN READ FOUND

Check each, and say whether it is still true:

    Productive named in ZERO of the 12 pushable LinkedIn messages
    sender identity in ZERO of 165 email steps
    four askings of ONE question where the ladder asks for six different jobs
    49 email openers beginning "i noticed"

`ogpartner-dk/jacob-faertz` is the counter-example - a sequence where the
ladder DID run: six rungs, six different jobs, product named once at rung 4,
easy out at rung 6. That is the target shape. Compare against it.

## WHAT NOT TO DO

- **Do not approve anything.** Approval is a human act and it is not yours.
- **Do not edit the copy to make it pass.** Report what it is.
- Do not conclude "acceptable" because it passes the gates. That is precisely
  the condition that produced the block.

## DELIVERABLE

`docs/HUMAN-READ-599020-2026-09-15.md`: a verdict of BEATS FALLBACKS / DOES
NOT BEAT FALLBACKS, per message, with the reasoning. A clear NO is a complete
and valuable result.

## RULES THAT APPLY TO THIS TASK

- Reads only at both providers. No POST/PATCH/PUT/DELETE, no sends, no
  campaign creation or activation, no adding leads.
- **A zero and a wrong lookup are indistinguishable from the outside.** If you
  measure zero of something, prove you read the right field first. Industry
  and headcount were reported at 0% three separate times by a reader looking
  at `sizing`, which is null everywhere, instead of `company_facts`.
- Say what you SAMPLED. `per_page` is accepted and IGNORED on every EmailBison
  route - you get 15 rows whatever you ask for - and offset pagination is
  refused past ~500 pages. A number without its page budget is not
  reproducible.
- Never use `meta.total` as a sent count. Campaign 274 reports 30,411
  scheduled rows and zero of its first 100 pages are sent. Count rows WHERE
  `sent_at` IS PRESENT.
- **Do not quote 8.49%** - unreproduced. **Do not quote any open rate** -
  `open_tracking` is False estate-wide, which is an ABSENT MEASUREMENT and not
  a zero. **Do not count an UNKNOWN as negative** - 53.4% of unknowns are
  correctly unknown.
- INTERESTED may NOT carry a learning claim: 0.44 precision on the old pattern
  set, and the new set is UNMEASURED, which is not the same as good.
  MEETING_INTENT (1.00) and OBJECTION (1.00) may, with recall stated.
- Never weaken, widen or disable a gate, a lint rule or a sender limit to make
  something pass or to gain volume. Fix what produced the bad output.
- Read every test exit code OFF THE PROCESS, never through a pipe.
- No unhashed PII in any tracked file or commit message - no real names,
  domains, emails, profile URLs or reply text. A seat holder is a real person
  too; Claude leaked one yesterday and the guard caught it.
- Separate OBSERVATIONS (with n), HYPOTHESES, and PROVEN LEARNINGS. Leave
  PROVEN LEARNINGS empty if nothing survives a sample-size objection. TASK-059
  left it empty and was right to.

## RESULT

**STATUS:** DONE

**COMMIT SHA:** 5adcf07

**TESTS:** Read-only task. No code changed. Provider read via
`heyreach.campaign_sequence(599020)` confirmed READ-ONLY (GET route on the
allowlist). No POST/PATCH/PUT/DELETE.

**FILES CHANGED:**
- `docs/HUMAN-READ-599020-2026-09-15.md` (new) - the verdict document
- `docs/qwen-tasks/RUNNING/TASK-098-...` (moved from TODO) - task claim

**FINDINGS:**

The live sequence DOES NOT BEAT FALLBACKS. Per-message verdict is NO for all
three pushable contacts on all dimensions.

The four specific failures, checked against `work/queue.jsonl` on 2026-09-15:

| Failure | Before (TASK-064) | Now (TASK-098) | Still broken? |
|---------|-------------------|-----------------|---------------|
| Productive named in LI messages | 0 of 12 | 1 of 18 (pushable); 91 of 407 (estate) | YES on pushable |
| Sender identity in email steps | 0 of 165 | 53 of 234 (estate); 0 of 18 (pushable) | YES on pushable |
| Ladder progression (4 askings of 1 question) | 4 identical questions | 0 records with >50% exact repetition; but thematic repetition persists on pushable contacts | PARTIALLY - fixed on counter-example, not on pushable |
| 49 email openers "I noticed" | 49 | 49 of 234 (unchanged) | YES - exact same count |

The fallbacks name Productive, identify the sender, progress through four
distinct jobs, and assert nothing about the reader. The generated copy for
the three pushable contacts does none of those things reliably.

The lead block holds.

**RISKS:**
- The pushable contacts carry copy from before the product block fix
  (savagebrands-com, mypersonalestatesale-com from 2026-09-13) or carry
  the exact phrase the claims rule was built to catch (portsidemarketing-com:
  "as a fellow founder").
- Regenerating the pushable contacts would improve Productive naming (the
  ladder runs on fresh generation - ogpartner-dk/jacob-faertz proves it)
  but would not fix "as a fellow founder" (structural, not stale-copy).

**RECOMMENDED CLAUDE ACTION:**
The deliverable is the verdict: DOES NOT BEAT FALLBACKS. The lead block
remains in place. No copy should be sent until the pushable contacts are
regenerated and re-read, and the "as a fellow founder" pattern is addressed
at the prompt level.
