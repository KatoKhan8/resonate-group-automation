# Provider documentation, and which source wins when they disagree

Supplied by the operator 2026-09-14. Recorded here so no future session has
to be told again.

## EMAILBISON

    official    https://docs.emailbison.com/get-started/introduction
    ours        https://send.resonategroup.co/api/reference

Both are authoritative as DOCUMENTATION. Neither is authoritative as
BEHAVIOUR.

## THE HIERARCHY

    1  real authenticated responses from send.resonategroup.co
    2  our actual historical estate
    3  https://send.resonategroup.co/api/reference
    4  https://docs.emailbison.com
    5  src/providers/bison.py
    6  assumptions - NEVER sufficient for a production conclusion

Documentation says what SHOULD exist. An authenticated response says what
DOES exist FOR OUR ACCOUNT, which is the only thing a production decision may
rest on.

**Where they disagree: record the discrepancy, trust the measurement.**

## WHY THE HIERARCHY IS WRITTEN DOWN RATHER THAN ASSUMED

`src/providers/bison.py` already carries a probe log for exactly this. The
endpoint accepts `workspace_id`, and the response for a workspace that does
not exist is BYTE-IDENTICAL to the response for the one that does. Anyone
reading the documentation would believe they had scoped a request to one
client. They would in fact be holding every inbox in the estate.

A documented parameter that silently does nothing is not an edge case here.
It is the failure mode the hierarchy exists to catch.

The same file records three separate occasions on which a route was concluded
not to exist, each by guessing a URL and reading the failure as absence. The
routes were established later against the vendor's own documentation. So the
hierarchy cuts both ways: absence of a working guess is not evidence of
absence, and presence in the documentation is not evidence of function.

## HOW A CAPABILITY EARNS "VERIFIED"

Called against our account, response read, row count recorded. Not "the
documentation says so". `docs/BISON-API-CAPABILITY-MAP-*.md` carries a
VERIFIED column and a documented-but-unverified row is a legitimate entry -
it is a lead for somebody, not a fact.

## THE STANDING PROHIBITION

Cataloguing a write endpoint is not permission to call one. The estate is a
live client's. Document write routes; never exercise them. Every provider
write in this system goes through `providerwrites.perform` and its allowlist,
and that is the only door.
