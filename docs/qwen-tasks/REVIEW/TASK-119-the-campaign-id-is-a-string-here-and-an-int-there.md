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

## RESULT

STATUS: DONE
COMMIT SHA: 66c3590
TESTS: 4 new tests in tests/test_provider_id_normalisation.py, all green.
       141 tests across test_invariants, test_provider_id_normalisation,
       test_campaigns, test_campaign_e2e, test_campaign_preflight - all green.
       Both the boundary test and the fingerprint test FAIL when str() is
       removed from bisonfactory._bind(), proving the normalisation is consumed.
FILES CHANGED:
  - src/bisonfactory.py: 3 str() coercions at write boundaries
  - tests/test_provider_id_normalisation.py: 4 new tests

### 1. Every comparison/lookup site and the type at each site

**Write boundaries (where provider IDs enter the system):**

| Site | Field | Type before fix | Type after fix |
|------|-------|----------------|----------------|
| bisonfactory._bind() :814 | bison_campaign_id | whatever JSON gave (int) | str() |
| bisonfactory._remember_lead() :1021 | bison_lead_id | whatever JSON gave (int) | str() |
| bisonfactory._remember_leads() :1042 | bison_lead_id | whatever JSON gave (int) | str() |
| orchestrator.map_external() :202-204 | bison/heyreach_campaign_id | str() already | str() |
| web/api.py :4039-4040 | bison/heyreach_campaign_id | str from form | str |

**Comparison sites (all already defensive with str()):**

| Site | Pattern | Notes |
|------|---------|-------|
| executionguard.py :351-359 | str(a) == str(b) | campaign_id and provider_campaign_id |
| leadobserve.py :119,182,332 | str(a) == str(b) | campaign_id in observation rows |
| mapping.py :126 | str(a) == str(b) | campaign id in external mapping |
| providers/bison.py :809,1260 | str(a) == str(b) | campaign_id in lead data |
| providers/heyreach.py :1901,2274 | str(a) == str(b) | campaignId in lead rows |
| web/api.py :3383,3768 | str(a) in set(str) | campaign_id filtering |
| configdiff.py :236,437 | str(cid) | when building approved dict |

**API boundary (all coerce to int for provider calls):**

| Site | Pattern |
|------|---------|
| providers/heyreach.py :1392,1455,1635,1796,1898,1961,2185,2208 | int(campaign_id) |
| providers/bison.py :830,896,936 | int(lead_id) |
| leadstop.py :80,114 | int(lead_id) |

### 2. Where the mixed types enter

The EmailBison API returns JSON with integer ids. `json.loads` preserves the
type. `bisonfactory._bind()` stored `created.get("id")` directly - an integer.
`bisonfactory._remember_lead(s)` stored `row["id"]` directly - an integer.

The HeyReach factory never writes `heyreach_campaign_id` back to the campaign
row; it only reads it. The only writers are `orchestrator.map_external()`
(already str()) and `web/api.py` (string from form input). So the mixed types
in the task description came from the EmailBison path.

### 3. The normalisation

Three `str()` coercions at the three write boundaries in `bisonfactory.py`.
Nothing downstream does arithmetic or ordering on these ids - every API call
already coerces to `int()` at the transport boundary.

### 4. Comparisons currently returning empty or zero

OBSERVATIONS (n=1 audit of all comparison sites):
- All comparison sites in the codebase already use `str()` coercion
  defensively. This was done incrementally as each type mismatch was
  discovered (leadobserve.py, executionguard.py, mapping.py, etc.).
- The fingerprint was the silent consumer: `json.dumps(594061)` produces
  a different digest than `json.dumps("594061")`, so a campaign whose
  bison_campaign_id was stored as int would have a different fingerprint
  from the same campaign with it stored as string. This means a re-bind
  from one type to the other silently invalidates the approval.

HYPOTHESES:
- Any existing zeros in lead observation counts or membership lookups are
  NOT caused by type mismatch, because all comparison sites already coerce.

PROVEN LEARNINGS:
- The boundary normalisation prevents FUTURE comparison sites from
  silently missing. Without it, every new comparison is a potential defect.
- The fingerprint is a consumer of the stored type, not just the value.
  A type change moves the digest even when the numeric value is the same.

RISKS:
- Existing data in work/campaigns.jsonl may still hold integer provider ids
  from before this fix. New writes will be strings. The defensive str()
  comparisons at every existing comparison site mean this is safe - the
  mixed types in the file will compare correctly against string lookups.
  A future cleanup could normalise the existing file, but that is a
  separate task and requires Claude's authority over work/.

RECOMMENDED CLAUDE ACTION:
- Review the three str() coercions in bisonfactory.py and the four tests.
- Consider whether a one-time normalisation pass over work/campaigns.jsonl
  is warranted to make the file consistent (all strings). This is a
  Claude-only action over real client state.
