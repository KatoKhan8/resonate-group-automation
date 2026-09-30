#!/usr/bin/env python3
"""How strongly this account can be personalised, as a LADDER not a gate.

OPERATOR DECISION, Zvonimir, 2026-09-30:

    Lack of deep account-specific personalization is NOT, by itself, a reason
    to HELD an otherwise qualified prospect. Personalization quality is a
    ladder. It is NOT a binary send / don't-send gate.

    NO PERSONALIZATION FACT != NO SAFE COPY.

WHAT THIS IS NOT. It is not a second personalization engine and it holds no
evidence rules of its own. Every level is READ from an authority that already
exists - `evidence.select` for what reaches a prompt, `company_facts` for
structured context, the contact's persona, and the record's ICP verdict. If
one of those changes its mind, this changes with it.

THE ONE THING IT DOES NOT DO IS RELAX A CLAIM. A level is an instruction
about WHICH TRUTHFUL ANGLE to reach for, never a licence to assert anything.
`claims`, `copylint` and `sequencegate` decide whether the resulting copy may
ship, exactly as before, and a level 4 draft that invents a prospect fact is
refused precisely as a level 1 draft would be. What changed is that the
absence of a fact now selects a different angle instead of discarding an
account.
"""

#: Deep account personalization: enough ADMITTED prospect evidence to open on
#: something they said. `research.MIN_COPY_EVIDENCE_ROWS` is the same floor
#: the research path uses, read from there rather than repeated.
LEVEL_ACCOUNT_FACT = 1

#: Account-context angle: some admitted evidence or structured context, so
#: the ANGLE can be chosen for their operating model without asserting a
#: problem they may not have.
LEVEL_ACCOUNT_CONTEXT = 2

#: Persona + Second Brain: no usable account context, but we know who we are
#: writing to, so the approved Productive angle for that persona is chosen.
LEVEL_PERSONA = 3

#: ICP + Second Brain: the account is genuinely qualified and nothing more is
#: known. The strongest relevant approved Productive angle, as a question.
LEVEL_ICP = 4

#: Nothing above applies. This is the ONLY value that means "do not write",
#: and it is reached when the account is not qualified at all - which is an
#: eligibility failure, not a personalization one.
LEVEL_NONE = None

NAMES = {
    LEVEL_ACCOUNT_FACT: "account fact",
    LEVEL_ACCOUNT_CONTEXT: "account context",
    LEVEL_PERSONA: "persona + second brain",
    LEVEL_ICP: "icp + second brain",
}

#: The structured fields that count as "we understand their operating model".
#: Exactly `research.structured_evidence`'s vocabulary, minus `name`, which
#: every record has and which says nothing about how they operate.
CONTEXT_FIELDS = ("industry", "specialties", "notable", "employees",
                  "revenue", "offices", "stack", "founded")


def admitted_rows(rec):
    """How many research rows actually reach a prompt. Asked of the filter."""
    from . import evidence as ev

    rows = (rec or {}).get("research") or []
    if not rows:
        return 0
    try:
        return len(list(ev.select(rows) or ()))
    except Exception:                                         # noqa: BLE001
        # A shape the filter cannot read is not evidence that evidence
        # exists. Fail towards the weaker level, never towards a claim.
        return 0


def _icp_qualified(rec):
    verdict = ((rec or {}).get("qualification") or {}).get("verdict") or {}
    status = str(verdict.get("icp_status") or "").lower()
    if status in ("rejected", "review", "unknown", ""):
        return status == ""  # unqualified-but-unscored is decided by callers
    return status in ("qualified", "dm_enrichment_approved")


def level_for(rec, contact=None):
    """The strongest truthful angle available for this account and person.

    Returns one of the LEVEL_* constants, or `LEVEL_NONE` when the account
    should not be written to at all. Absence of personalization NEVER returns
    `LEVEL_NONE` on its own - that is the whole point of the decision this
    implements.
    """
    from . import research

    if ((rec or {}).get("qualification") or {}).get(
            "verdict", {}).get("icp_status") == "rejected":
        return LEVEL_NONE

    admitted = admitted_rows(rec)
    if admitted >= research.MIN_COPY_EVIDENCE_ROWS:
        return LEVEL_ACCOUNT_FACT

    facts = (rec or {}).get("company_facts") or {}
    has_context = any(facts.get(f) not in (None, "", [], {})
                      for f in CONTEXT_FIELDS)
    if admitted >= 1 or has_context:
        return LEVEL_ACCOUNT_CONTEXT

    persona = (contact or {}).get("persona") or (rec or {}).get("persona")
    if isinstance(persona, dict):
        persona = persona.get("key")
    if persona:
        return LEVEL_PERSONA

    if _icp_qualified(rec):
        return LEVEL_ICP

    return LEVEL_NONE


def describe(level):
    """What the writer is told it is working with."""
    if level == LEVEL_ACCOUNT_FACT:
        return ("LEVEL 1, account fact. Open on something the numbered facts "
                "actually say about them.")
    if level == LEVEL_ACCOUNT_CONTEXT:
        return ("LEVEL 2, account context. You know roughly how they operate "
                "but have no fact worth opening on. Choose the angle for "
                "that operating model and open with a relevant QUESTION. Do "
                "NOT manufacture an icebreaker.")
    if level == LEVEL_PERSONA:
        return ("LEVEL 3, persona angle. You know who they are, not what "
                "they do. Use the approved Productive angle for this persona "
                "and open with a relevant QUESTION. Do NOT pretend to know "
                "anything about their company.")
    if level == LEVEL_ICP:
        return ("LEVEL 4, ICP angle. You know only that this account fits. "
                "Ask the strongest relevant question and describe one "
                "licensed Productive capability. Do NOT pretend to know "
                "anything about them at all.")
    return "no level: this account should not be written to."
