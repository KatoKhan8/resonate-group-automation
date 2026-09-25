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
