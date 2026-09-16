PRIORITY: P0
DEPENDS:

# TASK-196 - one unparseable response is holding 143 contacts

## WHERE THIS SITS

This is the largest recoverable inventory in the system and it is a parsing
bug, not a policy, a gate or a purchase.

TASK-194 examined the end of the pipe everybody had stopped looking at. Of 207
contacts that were enriched but never verified:

    143   held by "insufficient confirmations" - ContactOut says the address
          is VALID and Deliverable returns errors nobody can parse
     15   MX-blocked (permanent)
     11   catch-all uncleared
     37   no email address at all

**~155 of the 207 are recoverable if Deliverable's response parser is fixed.**
Downstream that is about 38 more records into the verified pool, and TASK-194's
ceiling moves from 66 to roughly 104 campaign-ready records.

Compare that to everything else measured today: free ICP evidence buys 12 of 66
review records, ContactOut company-info buys zero, and Grok is unmeasured. One
parser is worth more than all of it.

## THE QUESTION

1. **Find the parser and the response.** Which module calls Deliverable, what
   does it send, and what comes back. Capture a real response for one of the
   143 - a single read is enough and verification reads are cheap. Record the
   exact shape, status code and body.
2. **Say precisely what "unparseable" means.** There is a real difference
   between an error the provider returns deliberately (rate limit, unknown
   domain, temporary failure), an envelope shape the parser does not expect,
   and a response the parser reads correctly and then classifies as no-answer.
   Which is it? The word "unparseable" in TASK-194's result is a symptom, not
   a diagnosis.
3. **Fix the parser** so each real response shape maps to an explicit
   classification. No silent fallback, no bare `except Exception`, no "unknown"
   standing in for confusion - classify explicitly and fail closed, per
   CLAUDE.md.
4. **Then re-verify the 143** and report: how many become verified, how many
   are genuinely unverifiable, and how many are a THIRD state the old parser
   was collapsing into the second.
5. **The policy question, asked but not answered by you.** TASK-194 says ~155
   are recoverable "IF Deliverable is fixed OR policy relaxed". Establish what
   "insufficient confirmations" requires - how many independent confirmations,
   from which providers - and report what relaxing it would admit. Do not relax
   it. A verified address is the one thing standing between this system and
   sending mail to an address nobody confirmed.

## THE TRAP

CLAUDE.md: "No email is generated for an unverified address." That rule is
load-bearing and this task is the one most likely to erode it by accident. The
goal is a parser that reads the provider's real answer correctly - NOT a parser
that is more willing to call an address verified. If the honest outcome is that
143 contacts remain unverified because Deliverable genuinely cannot confirm
them, that is a complete and successful result, and it still tells us to stop
paying for enrichment ahead of a verification step that cannot clear it.

Second trap, from this repository's own history: a zero and a wrong lookup look
identical from outside. ContactOut saying VALID while Deliverable says nothing
parseable is exactly that shape. Prove which field you are reading and that it
is the right one before you conclude anything about either provider.

## WHAT YOU MAY NOT DO

- No provider WRITES. Verification reads are allowed and are the point; keep
  them bounded and say how many you made.
- Do not relax the confirmation requirement, change the verification threshold,
  or mark an address verified on one provider's word.
- Do not weaken or delete an assertion to make a test pass.
- Do not run enrichment or spend person credits.
- Never commit an email address, a domain or a contact name. Hash them, and
  when you quote a captured response, redact the address inside it.

## FILES ALLOWED

    src/verification.py or whichever module owns the Deliverable call - read
      first and say why the file you changed is the right one
    tests/test_verification_parsing.py   (new)
    docs/DELIVERABLE-PARSER-2026-09-16.md   (new)
    scripts/task196_*.py

## FILES FORBIDDEN

    config/   src/providerwrites.py

## DELIVERABLE

The captured real response shapes with addresses redacted, the diagnosis of
what unparseable actually meant, the parser fixed with an explicit
classification per shape, the re-verification counts across the three states,
and the confirmation policy described but unchanged.
