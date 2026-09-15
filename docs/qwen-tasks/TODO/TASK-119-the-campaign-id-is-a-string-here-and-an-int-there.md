PRIORITY: P3
DEPENDS: 

# TASK-119 - one id, two types, and every comparison that quietly misses

## THE FACT

`work/campaigns.jsonl` holds the HeyReach campaign id as the STRING `"599020"`
on one record and the INTEGER `594061` on another. Both are correct at the
provider. Any comparison that does not normalise silently misses.

This is the same class of defect as TASK-083's approval count, which read 0
because it keyed on `op["contact"]` - the display name - while the cadence is
keyed by slug. **"0 approvals would be revoked" is the most reassuring
possible wrong answer**, and it nearly made a destructive run look free.

## WHAT TO DO

1. Find every place a provider campaign id, lead id, list id or account id is
   compared, looked up or used as a dict key. Report the type at each site.
2. Establish where the mixed types enter - is it the writer, the provider
   response, or a hand edit?
3. Normalise at the boundary rather than at every comparison, and prove the
   normalisation is CONSUMED by a test that fails when it is removed.
4. **Search for comparisons that are currently returning empty or zero** and
   check whether the zero is real. A lookup that never matches reports "none"
   and looks like a clean result.

## WHAT NOT TO DO

- Do not mass-rewrite `work/campaigns.jsonl`. It is real client state, it is
  gitignored, and `src/store.py` is the only sanctioned way to touch it.
- Do not normalise by coercing everything to string without checking that
  nothing downstream does arithmetic or an ordering comparison on the id.

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
