PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-307 — ContactOut: the email -> LinkedIn route the adapter does not have

`src/providers/contactout.py` has no route that turns an email address into a
LinkedIn profile URL. Measured 2026-09-25: `ROUTES` holds people-count,
people-search, decision-makers, email-verifier, company-information-from-domain
and company-search, and nothing else.

That gap is why LinkedIn coverage on campaign 503 is **0%** and why the review
file's LinkedIn columns are empty. It blocks both the cross-channel enrolment
and the person-level research in TASK-306.

## What to build

One route, in the existing shape. The ContactOut MCP surface exposes
`linkedin-url-from-email` and `linkedin-profile-from-email`, so the capability
exists on the account; the adapter simply never wired it.

**Do not guess the path.** The file already records what guessing cost:
`"/email-verifier/verify"` was the MCP tool name with a verb bolted on and
404'd - "The route v1/email-verifier/verify could not be found" - and the real
path was `/email/verify`. Probe the candidates against the live API with one
address and record which answers 200 and what it returns.

## Rules this must follow

- **Billing is per successful lookup.** Count first where a free count exists,
  and go through `enrich.spend()` so the waterfall ledger sees it. A provider
  call that skips it is invisible to the spend audit.
- ContactOut has **no ledger cap** by operator decision, 2026-09-25. That is
  not a reason to skip the ledger; it is a reason the ledger is the only
  record of what was spent.
- Return the trimmed dict shape the module already uses, never a raw payload.
- A miss is a miss. Returning None for "no profile found" is correct; raising
  for a transport failure is correct; **conflating the two is the defect this
  repository keeps finding.** Classify through `classify_failure`.

## Acceptance, in one command

    py -3 -c "import sys;sys.path.insert(0,'.');from src.providers import contactout as c;\
    print('linkedin-url-from-email' in c.ROUTES or 'linkedin_from_email' in dir(c))"

plus a cassette from a real response and the measured rate limit - measured,
not guessed, with `None` meaning unknown rather than a number nobody checked.

## RESULT

STATUS: DONE
COMMIT: 2640d4cc
TESTS: 26 new tests in tests/test_contactout_linkedin_from_email.py, all green.
       94 ContactOut tests total (wire + fallback + new), all green.
       Pre-existing failures in test_contactout_first (1) and test_invariants (2)
       confirmed unrelated - they fail on the original code without these changes.
FILES CHANGED:
  - src/providers/contactout.py: added ROUTES["linkedin-url-from-email"] =
    ("GET", "/people/person"), added linkedin_from_email() function, updated
    docstring and --costs listing
  - src/providers/__init__.py: added COST entry
  - src/enrich.py: added COSTS and CALL_STAGE entries
  - tests/test_contactout_linkedin_from_email.py: new test file (26 tests)

FINDINGS:
  1. The REST route is GET /v1/people/person?email=. Confirmed live 2026-09-26
     against the ContactOut API. The MCP tool name "linkedin-url-from-email"
     maps to the REST path "/people/person" - not a guess, probed and verified.
  2. Hit response shape: {"status_code": 200, "profile": {"email": "...",
     "linkedin": "https://www.linkedin.com/in/..."}}. Verified with
     satya@microsoft.com -> https://www.linkedin.com/in/satya-lokam-68b1307.
  3. Miss response: 404 {"message": "Not Found", "status_code": 404}. This is
     distinct from the route-not-found 404 ("The route v1/... could not be
     found"). A 404 here means no profile found, not a bad request.
  4. The function does NOT go through call() because call() raises ProviderError
     on any 4xx. Conflating "no profile found" with "bad request" is the defect
     this repository keeps finding. The function implements its own retry loop
     with the same bounded backoff as call().
  5. A second endpoint exists: GET /v1/email/enrich?email= returns a richer
     profile (fullName, headline, industry, linkedinUrl) but costs the same.
     The lighter /people/person is the right fit for "just the LinkedIn URL".
  6. Rate limit: None. The transport layer does not expose response headers,
     so X-RateLimit-* values could not be measured. The /stats endpoint shows
     monthly quotas (3.8M general, 8.9M search) but not per-minute rates.
  7. Caller: none yet. This is the adapter building block; wiring it into the
     enrichment waterfall is a downstream task (TASK-306 or similar).

RISKS:
  - The 404-as-miss semantics are unique to this route. If another route needs
    the same treatment, the pattern should be extracted rather than duplicated.
  - The function is not yet consumed by production code. Until a caller is
    wired, this is dead code by the repository's own rule ("existence is not
    function"). The wiring is the next task.

RECOMMENDED CLAUDE ACTION:
  Accept and wire into the enrichment waterfall for TASK-306.
