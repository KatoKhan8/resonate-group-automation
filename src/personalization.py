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

TWO SURFACES LIVE HERE, and they answer different questions. The LADDER above
(`level_for`, `admitted_rows`, `describe`, the `LEVEL_*` constants) answers
"how strongly may this account be personalised". The RESEARCH API below
(`selected_contacts`, `gaps`, `plan`, `decide`, `apply`, `stored`, `settings`
and the done-markers) answers "what should be researched, for whom, and when
to stop", and is what nineteen modules have always called. It was deleted by
accident on 2026-09-30 while the ladder was being written; it holds no policy
of its own and none of its thresholds moved.
"""
import argparse

from . import clients, evidence, events, store

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


# =================================================== the research API
#
# Deciding what to research, for whom, and when to stop.
#
# ## The expensive mistake this exists to prevent
#
# ContactOut hands back twelve people at a company. Personas pick three. If
# person-level research runs before that selection, nine people are researched
# for nothing - and at five thousand domains that is not a rounding error, it
# is the majority of the bill. So the order is fixed and enforced by a test:
#
#     enrich -> select contacts -> research ONLY the selected ones
#
# Company research is worse if repeated: the careers page is the same page for
# every contact at that company, and scraping it once per person is the same
# mistake multiplied. It happens once per domain and is cached on the record.
#
# ## When research is allowed at all
#
# Only when something downstream is actually blocked. `gaps()` names what is
# missing; if it names nothing, no provider is called, whatever budget is
# left. "More context might be nice" is not a reason and is not accepted as
# one.
#
# ## The order of sources
#
# Stored facts, then ContactOut's structured data, then AI Ark only where
# ContactOut genuinely came up short, then Apify on public pages. Each step is
# cheaper or already paid for than the one after it.

# ------------------------------------------------------------------- gaps
#
# Every reason public research is permitted. A call with any other reason is
# refused, so this tuple is the whole permission surface.

MISSING_RECENT_SIGNAL = "missing_recent_signal"
MISSING_PERSON_EVIDENCE = "missing_person_specific_evidence"
MISSING_COMPANY_CHANGE = "missing_company_change_signal"
WEAK_HOOK = "weak_hook"
INSUFFICIENT_ANGLE = "insufficient_angle_evidence"

GAPS = (MISSING_RECENT_SIGNAL, MISSING_PERSON_EVIDENCE, MISSING_COMPANY_CHANGE,
        WEAK_HOOK, INSUFFICIENT_ANGLE)

DEFAULTS = {
    "enabled": False,
    "max_people_per_company": 2,
    "max_posts_per_person": 3,
    "max_sources_per_company": 10,
    "min_relevance_score": evidence.MIN_RELEVANCE,
    "freshness": dict(evidence.DEFAULT_FRESHNESS),
}


def settings(config):
    """The client's research policy, with safe defaults for anything unset.

    Off unless a client asks for it: an existing client must not start
    scraping because this module shipped.
    """
    block = ((config or {}).get("research") or {}).get("recent_signals") or {}
    merged = dict(DEFAULTS)
    for key, value in block.items():
        if key == "freshness" and isinstance(value, dict):
            merged["freshness"] = {**DEFAULTS["freshness"], **value}
        elif key in merged:
            merged[key] = value
    merged["enabled"] = block.get("enabled", False) is True
    for key in ("max_people_per_company", "max_posts_per_person",
                "max_sources_per_company"):
        try:
            merged[key] = max(0, int(merged[key]))
        except (TypeError, ValueError):
            merged[key] = DEFAULTS[key]
    try:
        merged["min_relevance_score"] = float(merged["min_relevance_score"])
    except (TypeError, ValueError):
        merged["min_relevance_score"] = evidence.MIN_RELEVANCE
    return merged


def stored(rec, subject=None, contact_key=None, today=None):
    """Evidence already on the record, re-aged. The first place anything looks.

    Lives under `research`, which is where public evidence has always gone.
    `rec["evidence"]` is the generator's own store of the lines an LLM cited
    and is a different thing with the same name.

    Re-aged here rather than at each caller because this is the single door
    every reader goes through - `gaps`, `decide`, the preview, the dossier,
    the API. `evidence.make` froze a freshness verdict on the day the fact
    was found, and step four of a cadence runs weeks after step one, so
    reading the frozen number answers a question nobody asked today. Only
    what time changed is re-derived; see `evidence.recheck`.
    """
    out = []
    for entry in rec.get("research") or []:
        if subject and entry.get("subject") != subject:
            continue
        if contact_key and entry.get("contact_key") != contact_key:
            continue
        out.append(evidence.recheck(entry, today))
    return out


def company_researched(rec):
    """Has this company's public research already happened?

    Recorded as a flag as well as by evidence, because a company with nothing
    worth keeping must not be re-scraped on every run to rediscover that.
    """
    return bool((rec.get("research_state") or {}).get("company_done"))


def person_researched(rec, contact_key):
    done = (rec.get("research_state") or {}).get("people") or {}
    return contact_key in done


def mark_company_done(rec, note=""):
    state = rec.setdefault("research_state", {})
    state["company_done"] = True
    state["company_at"] = store.now()
    if note:
        state["company_note"] = note
    return state


def mark_person_done(rec, contact_key, note=""):
    state = rec.setdefault("research_state", {})
    people = state.setdefault("people", {})
    people[contact_key] = {"at": store.now(), "note": note}
    return state


# ------------------------------------------------------------- the decision

def selected_contacts(rec, config=None, cap=None):
    """The people this campaign will actually write to, best first.

    This is the gate. Anyone not returned here is never researched, and the
    cap is the client's, not this module's opinion.
    """
    policy = settings(config)
    limit = policy["max_people_per_company"] if cap is None else cap
    contacts = [c for c in rec.get("contacts") or [] if not c.get("excluded")]

    def rank(contact):
        # The buyer track is worth less research than the champion: the
        # champion is who the campaign actually converses with.
        persona = (contact.get("persona") or "").lower()
        return (0 if persona == "champion" else 1,
                0 if contact.get("sendable") else 1,
                contact.get("key") or "")

    return sorted(contacts, key=rank)[:max(0, limit)]


def gaps(rec, contact=None, config=None):
    """What is missing, or an empty list when nothing is.

    Company gaps are asked once per record; person gaps only for a contact that
    survived selection.
    """
    policy = settings(config)
    facts = rec.get("company_facts") or {}
    found = []

    if contact is None:
        company = evidence.usable(stored(rec, subject=evidence.COMPANY))
        recent = [e for e in company
                  if e.get("freshness_bucket") in (evidence.HIGH, evidence.MEDIUM)]
        if rec.get("lane") == "cold" and not rec.get("hook"):
            if not facts.get("notable") and not facts.get("specialties"):
                found.append(WEAK_HOOK)
        if not recent:
            found.append(MISSING_RECENT_SIGNAL)
        if not company and not facts.get("industry") and not facts.get("specialties"):
            found.append(INSUFFICIENT_ANGLE)
        if facts.get("email_domain") and facts["email_domain"] != rec.get("domain"):
            if not facts.get("name"):
                found.append(MISSING_COMPANY_CHANGE)
        return found

    person = evidence.usable(stored(rec, subject=evidence.PERSON,
                                    contact_key=contact.get("key")))
    if not person:
        found.append(MISSING_PERSON_EVIDENCE)
    return found


def plan(rec, config=None, cap=None):
    """Everything a run would do for this record, and why. Calls nothing."""
    policy = settings(config)
    people = selected_contacts(rec, config, cap)
    company_gaps = gaps(rec, None, config)

    company_step = {
        "subject": evidence.COMPANY,
        "planned": bool(company_gaps) and policy["enabled"]
                   and not company_researched(rec),
        "reasons": company_gaps,
        "max_sources": policy["max_sources_per_company"],
    }
    if not policy["enabled"]:
        company_step["why_not"] = "recent-signal research is not enabled"
    elif company_researched(rec):
        company_step["why_not"] = "company research already done for this domain"
    elif not company_gaps:
        company_step["why_not"] = "stored evidence already answers the company"

    person_steps = []
    for contact in people:
        reasons = gaps(rec, contact, config)
        step = {
            "subject": evidence.PERSON,
            "contact_key": contact.get("key"),
            "planned": bool(reasons) and policy["enabled"]
                       and not person_researched(rec, contact.get("key")),
            "reasons": reasons,
            "max_posts": policy["max_posts_per_person"],
        }
        if not policy["enabled"]:
            step["why_not"] = "recent-signal research is not enabled"
        elif person_researched(rec, contact.get("key")):
            step["why_not"] = "already researched"
        elif not reasons:
            step["why_not"] = "stored evidence already answers this person"
        person_steps.append(step)

    excluded = [c.get("key") for c in rec.get("contacts") or []
                if c.get("key") not in {p.get("key") for p in people}]
    return {
        "record": rec.get("id"),
        "enabled": policy["enabled"],
        "selected": [c.get("key") for c in people],
        "not_selected": excluded,
        "company": company_step,
        "people": person_steps,
        "planned_calls": int(company_step["planned"])
                         + sum(1 for s in person_steps if s["planned"]),
    }


# ------------------------------------------------------------- the decision
#
# What the generator is handed. It should never have to work out targeting for
# itself: by the time a prompt is built, the strategy is already decided and
# the evidence already chosen.
#
# The `level` this returns is `evidence`'s ladder (LEVEL_COMPANY .. LEVEL_
# RECENT), which says WHICH KIND OF EVIDENCE was chosen. It is a different
# question from `level_for` above, which says how strongly the account may be
# personalised at all, and the two are deliberately not merged.

def decide(rec, contact, config=None, limit=3):
    """The personalisation decision for one selected contact."""
    policy = settings(config)
    persona = contact.get("persona")
    angle_words = _angle_words(rec, contact, config)

    pool = (stored(rec, subject=evidence.PERSON, contact_key=contact.get("key"))
            + stored(rec, subject=evidence.COMPANY))
    chosen = evidence.select(pool, limit)

    if not chosen:
        return {
            "quality": "none",
            "level": evidence.LEVEL_PERSONA,
            "primary_signal": None,
            "source": None,
            "source_url": None,
            "published_at": None,
            "freshness": evidence.UNKNOWN,
            "persona": persona,
            "angle": contact.get("angle"),
            "reason": "no usable evidence: falling back to a verified company "
                      "fact and persona pain",
            "selected_evidence_ids": [],
        }

    best = chosen[0]
    level = (evidence.LEVEL_RECENT
             if best.get("freshness_bucket") in (evidence.HIGH, evidence.MEDIUM)
             else evidence.LEVEL_PERSON if best.get("subject") == evidence.PERSON
             else evidence.LEVEL_COMPANY)
    return {
        "quality": best.get("quality"),
        "level": level,
        "primary_signal": best.get("fact"),
        "source": best.get("source_type"),
        "source_url": best.get("source_url"),
        "published_at": best.get("published_at"),
        "freshness": best.get("freshness_bucket"),
        "persona": persona,
        "angle": contact.get("angle"),
        "reason": "; ".join(best.get("relevance_reasons") or [])[:200],
        "selected_evidence_ids": [e["evidence_id"] for e in chosen],
    }


def _angle_words(rec, contact, config):
    """The client's own words for this persona's angle. Never invented here."""
    config = config or {}
    persona = contact.get("persona")
    angle = contact.get("angle")
    try:
        angles = clients.angles_for(config, persona) or {}
    except Exception:
        angles = {}
    words = []
    if isinstance(angles, dict):
        if angle and angles.get(angle):
            words.append(str(angles[angle]))
        else:
            words.extend(str(v) for v in angles.values())
    market = (config.get("market") or {}).get("must")
    if market:
        words.append(str(market))
    return words


def apply(rec, config=None, limit=3):
    """Attach a personalisation decision to every selected contact."""
    out = {}
    for contact in selected_contacts(rec, config):
        decision = decide(rec, contact, config, limit)
        contact["personalization"] = decision
        out[contact.get("key")] = decision
        events.record(rec, events.PERSONA_SELECTED,
                      contact_key=contact.get("key"),
                      persona=contact.get("persona"),
                      quality=decision["quality"])
    return out


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.personalization")
    p.add_argument("--plan", action="store_true")
    p.add_argument("--id")
    a = p.parse_args(argv)

    for rec in store.load():
        if a.id and rec["id"] != a.id:
            continue
        try:
            config = clients.load(rec.get("client"))
        except Exception:
            config = {}
        proposal = plan(rec, config)
        print(f"{rec['id']:<20} calls={proposal['planned_calls']} "
              f"selected={len(proposal['selected'])} "
              f"not_selected={len(proposal['not_selected'])}")
        company = proposal["company"]
        mark = "plan" if company["planned"] else "skip"
        print(f"    {mark} company   {company.get('why_not') or ', '.join(company['reasons'])}")
        for step in proposal["people"]:
            mark = "plan" if step["planned"] else "skip"
            print(f"    {mark} {step['contact_key']:<14} "
                  f"{step.get('why_not') or ', '.join(step['reasons'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
