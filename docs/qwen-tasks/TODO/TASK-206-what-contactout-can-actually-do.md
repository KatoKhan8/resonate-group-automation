PRIORITY: P0
DEPENDS:

# TASK-206 - what ContactOut can actually do, against what we ask it

## WHERE THIS SITS

`PROVIDER-ROUTING-POLICY.md` is new and it is an operator product decision:
**ContactOut is the primary provider, first whenever capable**, regardless of
another provider looking cheaper. It also says, in as many words, do not assume
the current adapter represents the whole ContactOut API.

That instruction exists because of a measurement. TASK-185 called
`contactout/company-information-from-domain` across 50 records and moved **zero
ICP verdicts** and resolved **zero criteria**. The conclusion drawn at the time
was "ContactOut cannot resolve the ICP criteria". The honest conclusion is
narrower: **one endpoint was tested, not ContactOut.**

This task establishes the difference, because every routing decision after it
depends on knowing what ContactOut can be asked.

## THE QUESTION

1. **Enumerate the ContactOut surface we have access to.** Endpoints, their
   inputs, their outputs, their credit cost. Take it from the integration and
   from whatever documentation the repository holds - `src/providers/` and any
   docs naming ContactOut. The account also reaches capabilities the adapter
   may not call: company search, decision-makers, people search, people
   enrich, technology search, email and phone finders, profile lookup from
   email or URL, and job-change signals are all worth checking for
   specifically.
2. **Then enumerate what our code actually calls.** `grep` the codebase.
   Which endpoints appear in `src/`, in `src/waterfall.py`'s stage
   definitions, and in the adapter but with no caller. Produce the diff:
   available but never called.
3. **Map capability to requirement.** For each thing this pipeline needs, say
   whether ContactOut can answer it and with which call. The requirements that
   matter most, because they are what the estate is blocked on:

       geography          an ISO country the ICP criterion accepts
       company_type       a vertical the structural check recognises
       employees          a headcount
       prose evidence     a fact with a source, for check_evidence
       person discovery   contacts at a qualified account
       contact email      and its verification
       job-change signal  a reason to reach out now

   For each: ContactOut call, or NO CONTACTOUT CAPABILITY. Be specific about
   the field name that would carry the answer.
4. **Re-test the ICP question against a DIFFERENT endpoint, bounded.** If item
   3 finds a ContactOut call that could plausibly resolve geography or
   company_type where `company-information-from-domain` did not, try it on
   **FIVE** records from the review pool. Five. Report per record what came
   back and whether the criterion moved. If no other endpoint plausibly
   answers it, run nothing and say so - that is a complete answer.
5. **Say what ContactOut genuinely cannot do**, so the policy's later layers
   have a defensible boundary. A confirmed capability gap is what licenses the
   crawler, then Grok, then anything paid.

## THE TRAP

This task must not become a shopping trip. Five records in item 4, and only if
item 3 identifies a plausible endpoint. Do not call every endpoint once "to see
what it returns" - that is a credit spend with no hypothesis, and this
repository's own rule is that a paid call needs a reason before it is made.

Second trap: an endpoint existing in the API is not a capability we have. Check
whether the plan or key actually permits it, and record "available to us" and
"exists in the documentation" as different columns. A routing layer built on
capabilities the account cannot reach will fail closed at the worst moment.

Third trap: do not conclude from a null that the capability is absent. A zero
and a wrong lookup look identical from outside, and TASK-185's round 1 got
nulls for all 25 domains - which may mean the domains were unknown to
ContactOut, or may mean the call was shaped wrongly. Prove the field you read
is the right one.

## WHAT YOU MAY NOT DO

- Bounded spend only: at most 5 records in item 4, at most one endpoint under
  test. If spend passes 15 credits, stop and report.
- No provider writes. No HeyReach or EmailBison calls at all.
- Do not change `src/waterfall.py`'s stage definitions - TASK-207 and TASK-208
  own the routing changes, and two workers editing that file will collide.
- Do not build a new provider path or adapter. This task reports; it does not
  wire.
- Never commit a key, an email address, a contact name or a domain.

## FILES ALLOWED

    docs/CONTACTOUT-CAPABILITY-2026-09-16.md   (new)
    scripts/task206_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The available surface with inputs, outputs and costs; the diff between
available and called; the capability-to-requirement map with a field name or
an explicit NO CAPABILITY for each of the seven; the bounded five-record
re-test with per-record results, or a stated reason none was warranted; and
the confirmed capability gaps that license the later layers.
