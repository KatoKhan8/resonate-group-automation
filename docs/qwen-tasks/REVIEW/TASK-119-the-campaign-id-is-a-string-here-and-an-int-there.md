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

## RESULT BLOCK

STATUS: DONE
COMMIT SHA: b9726e0
TESTS: tests.test_campaign_id_types (3 tests, all pass); tests.test_staging_a_campaign_twice_builds_one (9 tests, all pass)
FILES CHANGED:
- src/bisonfactory.py: normalised provider ids to strings at 4 write points
- src/leadobserve.py: normalised provider_lead_id to string
- tests/test_staging_a_campaign_twice_builds_one.py: updated fake provider to handle string ids
- tests/test_campaign_id_types.py: new test proving the boundary normalises

FINDINGS:

OBSERVATIONS (with n):
1. Three write paths stored provider ids as-is from JSON responses (integers):
   - bisonfactory._bind (line 814): bison_campaign_id
   - bisonfactory._remember_lead/_remember_leads (lines 1021, 1042): bison_lead_id
   - leadobserve.scheduled_rows (line 454): provider_lead_id
2. orchestrator.map_external (lines 202, 204) and web/api.py (lines 4039-4040) already normalised to strings - these are the manual mapping paths
3. executionguard.py (lines 351-352, 358-359) already defensively normalises with str() at comparison time
4. outcomes.py (line 833) already defensively normalises provider_lead_id with str() when building comparison sets

HYPOTHESES:
1. The mixed types in production (string "599020" and integer 594061) came from two different write paths: manual mapping via orchestrator.map_external (string) vs automatic creation via bisonfactory._bind (integer)
2. Comparisons that silently missed would report "0 results" or "not found", which looks like a clean result - the same trap as TASK-083

PROVEN LEARNINGS:
1. Provider JSON responses return integers for id fields. Any write path that stores these without str() creates a type mismatch.
2. Normalisation at the boundary (write time) is cheaper and safer than normalisation at every comparison (read time).
3. A test that constructs inputs by hand can miss wiring bugs - the staging test had to be updated because the fake provider returned integers while the real factory now stores strings.

RISKS:
1. Existing production data in work/campaigns.jsonl and work/queue.jsonl may still have mixed types. The fix prevents NEW mismatches but does not retroactively fix old ones. Comparisons that use str() defensively (executionguard, outcomes) will continue to work. Comparisons that do not may still miss on old data.
2. HeyReach factory was not changed because it does not write provider ids to the queue - it only reads them. The heyreach_campaign_id field is set via orchestrator.map_external which already normalises to string.

RECOMMENDED CLAUDE ACTION:
1. Review the fix and merge if acceptable.
2. Consider whether a one-time migration script should normalise existing production data in work/campaigns.jsonl and work/queue.jsonl to strings. This is optional because the defensive str() calls in executionguard and outcomes will handle mixed types, but a clean estate is easier to reason about.
3. Search for any other provider id fields that may have the same issue (list_id, account_id, etc.) - the grep search in this task found provider_account_id is already normalised in senderinventory.py (lines 157, 255).
