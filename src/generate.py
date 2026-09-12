#!/usr/bin/env python3
"""The LLM steps. BUILD-SPEC phase 5, prompt contracts in section 8.

Deterministic work happens here; only the reasoning happens in the model. The
context handed to a prompt is assembled from trimmed record fields, never from
a provider payload, and it is small on purpose (section 9, trap 8).

Two of the six cadence emails are generated, day 1 and day 15 (section 7). The
rest are templates the expander fills in phase 7, which is what makes the cost
per lead workable at 500 domains.

A generated draft is linted before it is stored. A draft that breaks a rule is
regenerated, never patched, and never widened away (CLAUDE.md).

  python -m src.generate                    dry run: what would be asked, and of what
  python -m src.generate --live --model ... needs a model; none ships with the repo
"""
import argparse
import os

from . import clients, events, lint, llm, research, store


def cadence_note_words():
    """The cross channel word list, imported late to avoid a cycle."""
    from .cadence import NOTE_MENTIONS_EMAIL
    return NOTE_MENTIONS_EMAIL
from .providers import ProviderError, contactout

PROMPTS = os.path.join(store.ROOT, "prompts")

GENERATED_DAYS = ("day1", "day15")
MAX_DRAFT_ATTEMPTS = 3

# Wording that would make the note reference the email. Section 7.
# The schema in llm.py rejects the obvious cases; this is the fuller list the
# cadence checks with, so the storer is strictly stricter than the contract.
NOTE_MUST_NOT_MENTION = cadence_note_words()

# Cost accounting hook: every model call this module makes, by step.
model_calls = {}


def count_model_call(step, attempts=1):
    model_calls[step] = model_calls.get(step, 0) + int(attempts)
    return model_calls


def reset_model_calls():
    model_calls.clear()


def prompt_text(name):
    with open(os.path.join(PROMPTS, f"{name}.md"), encoding="utf-8") as f:
        return f.read()


# --------------------------------------------------------------- context

def facts_block(rec):
    """The trimmed facts a prompt is allowed to see. No provider payloads.

    FACTS ABOUT THE COMPANY, NEVER FACTS ABOUT OUR OWN PROCESS. `icp_flags`
    and `headcount_signal` were on this list, and the model did exactly what
    it was asked: it wrote about them. The one campaign-ready Productive
    contact's approved-pending day1 email read

        Subject: HSMG geo flag and headcount
        "The specific signal triggering this outreach is the geo outside
         client's stated markets flag."
        "We failed to filter our outreach by geography, and we own that
         failure completely without excuse."
        "Your headcount signal is 23."

    to a stranger, and day15 opened "The ICP flag indicates geographic
    targeting outside stated markets."

    `lint` and `claims` both passed it, and were right to by their own rules:
    every sentence IS grounded in this record's stored evidence. The evidence
    was our qualification verdict about our own targeting, and our provider's
    internal people-count. Grounding checks that a claim is supported; it
    cannot know that the support is a note we wrote to ourselves.

    So the allowlist is the boundary, and it is drawn at what a person at the
    company would recognise as being about their company. `icp_flags` is our
    verdict. `headcount_signal` is our estimate in our vocabulary, and
    `employees` already carries the same number in theirs.
    """
    facts = rec.get("company_facts") or {}
    keep = ("name", "employees", "revenue", "founded", "industry", "offices",
            "specialties", "notable", "email_domain")
    return {k: facts[k] for k in keep if facts.get(k) not in (None, "", [], {})}


def contact_block(contact):
    return {k: contact.get(k) for k in ("name", "title", "persona", "angle")
            if contact.get(k)}


def context_for(step, rec, contact=None, client=None):
    """Assemble the smallest context that can answer the question."""
    block = {"company": rec.get("company"), "domain": rec.get("domain"),
             "lane": rec.get("lane"), "facts": facts_block(rec)}
    public = research.for_prompt(rec)
    if public:
        # Attributed and trimmed. The fence in llm.py marks it as data.
        block["public_evidence"] = public
    if step == "diagnose":
        block["thread"] = rec.get("context") or ""
    elif step == "hook":
        block["signal"] = rec.get("signal") or ""
    elif step == "persona_angle":
        block["contact"] = contact_block(contact or {})
        block["angles"] = (client or {}).get("angles")
    elif step == "linkedin_note":
        block["contact"] = contact_block(contact or {})
        block["angle"] = (contact or {}).get("angle")
        block["angle_wording"] = ((client or {}).get("personas") or {}).get(
            (contact or {}).get("persona") or "", {}).get("angles")
        block["tone"] = ((client or {}).get("tone") or {}).get("linkedin")
    elif step == "draft":
        block["contact"] = contact_block(contact or {})
        block["angle"] = (contact or {}).get("angle")
        block["evidence"] = (rec.get("evidence") or {}).get(
            lint.contact_key(contact or {}), [])
        block["tone"] = (client or {}).get("tone")
        if rec.get("lane") == "revive":
            block["diagnosis"] = rec.get("diagnosis")
        if rec.get("lane") == "cold":
            block["hook"] = rec.get("hook")
        if rec.get("sizing"):
            block["sizing"] = rec["sizing"]
    return block


def render_prompt(step, rec, contact=None, client=None):
    """Contract first, then the record fenced as untrusted data.

    A CRM thread can say anything, including "ignore your instructions". The
    contract is stated before the fence and the fence says the contents are
    data, so a thread cannot promote itself to an instruction.
    """
    import json
    context = json.dumps(context_for(step, rec, contact, client), indent=2,
                         ensure_ascii=False)
    return f"{prompt_text(step)}\n\n{llm.fence(context)}"


# ----------------------------------------------------------------- steps

def note_mode(rec, client=None):
    """template or llm, from the client config. Template unless asked."""
    if client is None:
        try:
            client = clients.load(rec.get("client"))
        except clients.ConfigError:
            return "template"
    return clients.linkedin_note_mode(client)


def plan(rec, client=None):
    """What this record needs from a model, and why. No call without a reason."""
    ops = []
    if rec.get("state") in ("dropped", "pushed"):
        return ops
    # Through the resolver, not off a stored flag. src/verification.py is the
    # only module allowed to conclude an address may be written to, and a
    # contact whose evidence says verified must not be skipped merely because
    # nobody copied a boolean onto it.
    sendable = [c for c in rec.get("contacts") or [] if lint.sendable(c)]
    # THE LINKEDIN LANE WAS GATED ON EMAIL VERIFICATION, AND IT IS A DIFFERENT
    # CHANNEL. The early return below said "nothing is drafted for an
    # unverified address", which is exactly right for an email draft and wrong
    # for everything else in this function: the connection note twenty lines
    # down needs a LinkedIn profile and no address at all, and it sat inside
    # the same gate.
    #
    # Measured on the Productive cohort 2026-09-12: of the contacts on
    # qualified companies, ALL carry a usable LinkedIn profile and fewer than
    # a third are email-sendable - the rest are catch-all domains reoon will
    # not clear, or MX gateways the client's own policy closes. Every one of
    # those people was reachable on LinkedIn and got no copy written for them,
    # so `campaign_ready` stood at 1 of 24 while the channel that could
    # actually reach 24 of them was never drafted for.
    #
    # `channels.linkedin_verdict` is the authority and is asked rather than
    # re-implemented: it refuses an unsubscribed or suppressed person, a
    # duplicate, a missing profile, and a URL that is a company page or a
    # search link. What it does not require is an email, because LinkedIn does
    # not.
    from . import channels
    on_linkedin = [c for c in rec.get("contacts") or ()
                   if channels.linkedin_verdict(rec, c, client)[0]]
    keys = {id(c) for c in sendable}
    workable = sendable + [c for c in on_linkedin if id(c) not in keys]
    if not workable:
        return ops
    if rec.get("lane") == "revive" and not (rec.get("diagnosis") or {}).get("died_because"):
        ops.append({"step": "diagnose", "why": "revive record with no diagnosis"})
    if rec.get("lane") == "cold" and not rec.get("hook"):
        ops.append({"step": "hook", "why": "cold record with no hook"})
    for c in workable:
        if rec.get("lane") == "domains" and not c.get("angle"):
            ops.append({"step": "persona_angle", "why": f"{c['name']} has no angle",
                        "contact": c.get("name")})
        if note_mode(rec, client) == "llm" and c in on_linkedin:
            stored_note = (rec.get("cadence") or {}).get(
                lint.contact_key(c), {}).get("day3") or {}
            if not (stored_note.get("generated") and stored_note.get("note")):
                ops.append({"step": "linkedin_note",
                            "why": f"{c['name']} has no written connection note",
                            "contact": c.get("name"), "day": "day3"})
        # EMAIL DRAFTS STAY BEHIND EMAIL VERIFICATION. CLAUDE.md: no email is
        # generated for an unverified address, and that rule is untouched -
        # only the LinkedIn note moved out from behind it.
        if c not in sendable:
            continue
        for day in GENERATED_DAYS:
            step = (rec.get("cadence") or {}).get(lint.contact_key(c), {}).get(day)
            if not (step or {}).get("body"):
                ops.append({"step": "draft", "why": f"{c['name']} has no {day} email",
                            "contact": c.get("name"), "day": day})
    return ops


def diagnose(rec, model):
    data, attempts, errors = llm.ask(model, "diagnose", render_prompt("diagnose", rec))
    rec["diagnosis"] = {"died_on": data.get("died_on"),
                        "died_because": data["died_because"],
                        "failure_mode": data["failure_mode"],
                        "last_position": data.get("last_position"),
                        "what_changed": data.get("what_changed")}
    store.log(rec, "diagnose", f"{data['failure_mode']} on {data.get('died_on')}",
              attempts=attempts, rejected=errors)
    return rec["diagnosis"]


def hook(rec, model):
    data, attempts, errors = llm.ask(model, "hook", render_prompt("hook", rec), rec=rec)
    rec["hook"] = data["hook"]
    store.log(rec, "hook", data["hook"][:80], attempts=attempts, rejected=errors)
    return rec["hook"]


def persona_angle(rec, contact, model, client=None):
    """The angle plus its evidence. Evidence that is not traceable is rejected."""
    data, attempts, errors = llm.ask(
        model, "persona_angle", render_prompt("persona_angle", rec, contact, client),
        rec=rec)
    contact["angle"] = data["angle"]
    rec.setdefault("evidence", {})[lint.contact_key(contact)] = data["evidence"]
    store.log(rec, "angle", f"{contact.get('name')}: {data['angle']}",
              attempts=attempts, rejected=errors, evidence=data["evidence"])
    return data


def linkedin_note(rec, contact, model, client=None):
    """The day 3 note, written rather than templated. Short, and no crossover.

    Cost accounting: every model call is counted here through
    `model_calls`, and the attempts are on the record's log, so the price of
    llm mode is visible before it is turned on for 500 domains.
    """
    key = lint.contact_key(contact)
    data, attempts, errors = llm.ask(
        model, "linkedin_note", render_prompt("linkedin_note", rec, contact, client))
    note = data["note"].strip()
    step = {"channel": "linkedin", "generated": True, "note": note}
    leaks = [w for w in NOTE_MUST_NOT_MENTION if w in note.lower()]
    if leaks:
        store.log(rec, "linkedin_note", f"rejected, mentions {leaks[0]}")
        return None
    rec.setdefault("cadence", {}).setdefault(key, {})["day3"] = step
    count_model_call("linkedin_note", attempts)
    store.log(rec, "linkedin_note", note[:80], attempts=attempts, rejected=errors)
    events.record(rec, events.DRAFT_GENERATED, contact_key=key,
                  channel="linkedin", step="day3", generated=True)
    return step


def draft(rec, contact, day, model, client=None):
    """Generate, lint, regenerate. Never patch, never widen a rule."""
    key = lint.contact_key(contact)
    rejected = []
    for attempt in range(1, MAX_DRAFT_ATTEMPTS + 1):
        prompt = render_prompt("draft", rec, contact, client)
        if rejected:
            prompt += ("\n## Your previous draft failed lint\n\n"
                       f"{'; '.join(rejected[-1])}\n\nWrite a new one. Do not patch the old one.\n")
        data, _, schema_errors = llm.ask(model, "draft", prompt)
        candidate = {"channel": "email", "generated": True,
                     "subject": data["subject"], "body": data["body"]}
        # Lint the candidate against a copy: a failing draft is never stored.
        trial = dict(rec)
        trial["cadence"] = {**(rec.get("cadence") or {}),
                            key: {**((rec.get("cadence") or {}).get(key) or {}),
                                  day: candidate}}
        failures = lint.check(trial, key, candidate)
        content_failures = [f for f in failures if f not in lint.HELD_CODES]
        if not content_failures:
            rec.setdefault("cadence", {}).setdefault(key, {})[day] = candidate
            store.log(rec, "draft", f"{contact.get('name')} {day}: {data['subject']}",
                      attempts=attempt, rejected=rejected)
            count_model_call("draft", attempt)
            events.record(rec, events.DRAFT_GENERATED, contact_key=key,
                          channel="email", step=day, generated=True)
            return candidate
        rejected.append(content_failures)
        events.record(rec, events.LINT_FAILED, contact_key=key, channel="email",
                      step=day, failures=content_failures, attempt=attempt)
    store.log(rec, "draft",
              f"{contact.get('name')} {day}: no draft passed lint, nothing stored",
              attempts=MAX_DRAFT_ATTEMPTS, rejected=rejected)
    return None


def size(rec, live=False):
    """Free: put the prospect's own market in the email instead of ours."""
    if not live or rec.get("sizing"):
        return rec.get("sizing")
    try:
        count = contactout.people_count(domain=rec["domain"])
    except ProviderError as e:
        store.log(rec, "sizing", f"people-count failed: {e}")
        return None
    rec["sizing"] = {"query": count.get("query") or rec["domain"],
                     "profiles": count.get("profiles"), "mobiles": count.get("mobiles")}
    store.log(rec, "sizing", f"{rec['sizing']['profiles']} profiles (free)")
    return rec["sizing"]


# ---------------------------------------------------------------- runner

def generate_record(rec, model, client=None):
    """Every step this record needs, in order, stopping at the first that fails."""
    done = []
    for op in plan(rec):
        contact = next((c for c in rec.get("contacts") or []
                        if c.get("name") == op.get("contact")), None)
        try:
            if op["step"] == "diagnose":
                diagnose(rec, model)
            elif op["step"] == "hook":
                hook(rec, model)
            elif op["step"] == "persona_angle" and contact:
                persona_angle(rec, contact, model, client)
            elif op["step"] == "linkedin_note" and contact:
                if not linkedin_note(rec, contact, model, client):
                    continue
            elif op["step"] == "draft" and contact:
                if not draft(rec, contact, op["day"], model, client):
                    continue
            done.append(op)
        except llm.ModelError as e:
            store.log(rec, op["step"], f"held: {e}")
            if rec.get("state") not in ("dropped", "pushed"):
                rec["state"] = "held"
            break
    if done and any((rec.get("cadence") or {}).get(lint.contact_key(c), {}).get("day1")
                    for c in rec.get("contacts") or []):
        if rec.get("state") not in ("dropped", "pushed", "held"):
            rec["state"] = "drafted"
    return done


def run(model=None, live=False, ids=None, limit=None, client=None):
    """Dry by default: reports what would be asked without asking anything."""
    recs = store.load()
    model = model or llm.NoModel()
    targets = [r for r in recs if ids is None or r["id"] in ids]
    if limit:
        targets = targets[:limit]

    report = []
    for rec in targets:
        ops = generate_record(rec, model, client) if live else plan(rec)
        report.append({"id": rec["id"], "lane": rec.get("lane"),
                       "state": rec.get("state"), "ops": ops})
    if live:
        store.save(recs)
    return {"live": live, "model": getattr(model, "name", "unknown"), "records": report}


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.generate")
    p.add_argument("--live", action="store_true",
                   help="actually call the model (none is configured by default)")
    p.add_argument("--id", action="append", dest="ids")
    p.add_argument("--limit", type=int)
    a = p.parse_args(argv)

    result = run(live=a.live, ids=a.ids, limit=a.limit)
    head = "GENERATED" if a.live else "DRY RUN, no model called"
    print(f"{head}: {len(result['records'])} record(s), model={result['model']}")
    for r in result["records"]:
        print(f"\n  {r['id']} ({r['lane']}) state={r['state']}")
        for o in r["ops"]:
            detail = f" [{o['contact']}{' ' + o['day'] if o.get('day') else ''}]" \
                if o.get("contact") else ""
            print(f"    {o['step']:<14}{detail:<28} {o['why']}")
        if not r["ops"]:
            print("    nothing to generate")
    if not a.live:
        print("\nno model ships with this repo: pass one to run(model=...).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
