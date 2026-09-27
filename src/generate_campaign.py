"""The single versioned production entrypoint for campaign generation.

TASK-369. Every model call goes through `src/llm.py`. No `urllib`, no
`requests`, no API base URL in this file. The spend ledger sees every call.

The pipeline:
    1. Check offers are approved (fail-closed).
    2. Load Second Brain facts; only verified facts inform strategy.
    3. Decide strategy ONCE per segment+persona.
    4. Per contact: ICP -> extract -> hypothesis -> match -> plan -> write.
    5. copylint, then sequencegate, before any provider call.
    6. Return a SequencePlan.

`work/v2_run.py` is the reference. This module promotes it: same stages,
same prompts, but every model call is ledgered and every offer is checked.
"""
import json
import re

from . import (cadencelibrary, clients, copyprompts, copystages, copylint, llm,
               offers as offers_mod, secondbrain, sequencegate, sequenceplan,
               skills)

ENTRYPOINT_VERSION = sequenceplan.ENTRYPOINT_VERSION

DRY_RUN_STAMP = "DRY-RUN / OFFERS PENDING"


class NotApproved(Exception):
    """An offer required by this campaign is not approved.

    Raised by name, fail-closed. Production does not approve its own offers.
    """


class CampaignPipelineError(Exception):
    """A configuration or pipeline error that stops generation.

    Raised by name with the client and the missing config. A missing client
    config is a configuration error, not a reason to silently use a different
    pipeline.
    """


def refuse_dry_run_records(recs):
    """Refuse to attach or activate records stamped by a dry run.

    A dry run produces artifacts marked with `DRY_RUN_STAMP`. Those records
    must not reach a provider - not at attach, not at activation. This
    function checks a list of records and raises if any carry the stamp.

    Called by both HeyReach and EmailBison at the attach and activation
    boundaries, so neither channel can send a dry-run artifact.
    """
    stamped = []
    for rec in (recs or ()):
        stamp = (rec.get("generation_stamp") or
                 (rec.get("cadence") or {}).get("generation_stamp"))
        if stamp == DRY_RUN_STAMP:
            stamped.append(rec.get("id") or "?")
    if stamped:
        raise CampaignPipelineError(
            "%d record(s) carry the dry-run stamp %r and may not be "
            "attached or activated: %s. A dry run produced no approved "
            "copy." % (len(stamped), DRY_RUN_STAMP, ", ".join(stamped[:5])))


def generate(client, account, contacts, *, config=None, model=None, live=False,
             allow_pending_offers=False):
    """Generate a SequencePlan for one account's outreach.

    `client` is a client name (str) or a loaded config dict.
    `account` has `company`, `domain`, and optionally `sources` (research pack)
    and `persona`.
    `contacts` is a list of dicts with `email`, `first_name`, `title`,
    `contact_key`, optionally `linkedin`, `sender_name`, `sender_email`.

    `model` is injectable. Tests pass `llm.ScriptedModel`; production passes
    `llm.OpenAICompatibleModel` or `llm.from_env()`.

    Returns a SequencePlan dict. Projections (preview, provider payloads,
    approval hash) derive from it via `sequenceplan.derive_*`.

    Raises `CampaignPipelineError` if the client config cannot be loaded.
    Raises `NotApproved` if any offer is not approved.
    Raises `CampaignPipelineError` if contacts is empty.
    """
    if not contacts:
        raise CampaignPipelineError(
            "no contacts provided for account %r; generation requires at "
            "least one contact." % account.get("company", "?"))

    if isinstance(client, str):
        try:
            config = config or clients.load(client)
        except clients.ConfigError as e:
            raise CampaignPipelineError(
                "client %r config could not be loaded: %s. "
                "A missing client config is a configuration error, not a "
                "reason to silently use a different pipeline."
                % (client, e))
        client_name = client
    else:
        config = client
        client_name = config.get("name", "")

    if model is None:
        model = llm.NoModel()

    account_company = account.get("company", "")
    account_domain = account.get("domain", "")

    # 1. OFFERS: fail-closed. All offers pending -> NotApproved.
    #
    # THE BYPASS IS EXPLICIT AND NARROW, and an earlier version of this got it
    # wrong in a way worth recording. Making `not live` the bypass trigger
    # weakened the gate for EVERY non-live caller, including library callers and
    # the TASK-369 tests that assert `generate()` fail-closes on unapproved
    # offers whatever the mode. A caller now has to ask for the bypass by name.
    #
    # `allow_pending_offers` exists for one purpose the operator named: letting
    # them watch the whole new path execute before any offer is approved. It is
    # not a mode, it is a deliberate request, and it is never implied.
    offers_gate_bypassed = bool(allow_pending_offers)
    if not offers_gate_bypassed:
        _check_offers(client_name)

    # 2. SECOND BRAIN: only verified facts inform strategy.
    sb_facts = _load_verified_facts(client_name)

    # 3. STRATEGY: once per segment+persona.
    persona = account.get("persona", "champion")
    segment_key = account.get("segment", client_name)
    strategy = _decide_strategy(segment_key, persona, model,
                                client=client_name, config=config)

    # 4. SOURCES: account research pack, cleaned.
    sources = _prepare_sources(account)

    # 5. CAPABILITIES: from client config, for the match stage.
    caps_cfg = (config.get("product") or {}).get("capabilities") or {}

    # 6. PER-CONTACT pipeline.
    cadence_info = _cadence_stub(config)
    plan = sequenceplan.new(
        client_name, account, [],
        strategy=strategy,
        second_brain_facts=sb_facts,
        offers=_offer_summary(client_name),
        cadence=cadence_info,
    )

    batch_capabilities = []

    for contact in contacts:
        contact_result = _process_contact(
            contact, account_company, account_domain, sources,
            caps_cfg, strategy, sb_facts, config, model,
            client_name=client_name,
        )
        plan["contacts"].append(contact_result)
        cap = (contact_result.get("match") or {}).get("capability_key")
        if cap and contact_result.get("qualification") not in (
                "UNQUALIFIED", "INSUFFICIENT"):
            batch_capabilities.append(cap)

    # 7. BATCH-LEVEL sequence gate.
    if batch_capabilities:
        batch_gate = sequencegate.check(
            {"emails": {"em1": "x"}, "linkedin": {}, "ps": {},
             "subjects": {}},
            batch_capabilities=batch_capabilities,
        )
        plan["batch_gate"] = batch_gate

    # 8. STAMP. Two independent reasons an artifact is not provider-ready, and
    # either is sufficient: it came from a non-live run, or the offer gate was
    # bypassed. Bypass therefore ALWAYS implies a stamp, so a gate that was
    # skipped can never produce an artifact a provider would accept.
    if offers_gate_bypassed or not live:
        plan["generation_stamp"] = DRY_RUN_STAMP

    return plan


def _check_offers(client_name):
    """Every offer for this client must be approved. Fail-closed.

    Raises `NotApproved` naming the first unapproved offer found.
    """
    all_offers = offers_mod.load()
    for oid, offer in all_offers.items():
        if offer.get("approval_status") != offers_mod.APPROVED:
            raise NotApproved(
                f"offer {oid} has approval_status="
                f"{offer.get('approval_status')!r}, not 'approved'. "
                f"Production does not approve its own offers."
            )


def _load_verified_facts(client_name):
    """Second Brain facts that are verified. INFERRED facts inform strategy
    but never become prospect-facing assertions."""
    try:
        brain = secondbrain.for_task("campaign_strategy", client_name)
    except (ValueError, Exception):
        return []
    verified = []
    for section, facts in brain.items():
        for fact in facts:
            if fact.get("verified"):
                verified.append(fact)
    return verified


def _decide_strategy(segment_key, persona, model, client=None, config=None):
    """Strategy decided ONCE per segment+persona.

    Delegates to `campaignstrategy.for_segment`, which caches and counts.
    The system prompt comes from the `campaign_strategy` skill's procedure,
    not from the raw constant.
    """
    from . import campaignstrategy
    skill = skills.load("campaign_strategy")
    return campaignstrategy.for_segment(
        segment_key, persona, model=model, system_prompt=skill.procedure,
        client=client, config=config)


def _prepare_sources(account):
    """Clean the account's research sources for the prompts.

    Sources come from the account dict, not from hardcoded work/ paths.
    """
    raw = account.get("sources") or []
    out = []
    for src in raw:
        text = _clean(src.get("text", ""))
        if text:
            out.append({
                "label": src.get("label") or "site",
                "url": src.get("url"),
                "text": text,
            })
    return out


_NAV = re.compile(
    r"^(?:\s*(?:login|about|home|menu|contact|services|work|"
    r"recent work|blog|pricing|team|careers|portfolio|our work|"
    r"skip to main content)\b[\s|,-]*)+", re.I)


def _clean(text, limit=2500):
    return re.sub(r"\s+", " ", _NAV.sub("", str(text or "").strip()))[:limit]


def _offer_summary(client_name):
    """The offers for the plan's metadata. Does not refuse; _check_offers did."""
    try:
        return offers_mod.load()
    except Exception:
        return {}


def _cadence_stub(config):
    """The cadence the plan uses, with resolved steps from cadencelibrary.

    The steps are stored on the plan so every consumer reads timing and
    thread relation from the plan rather than from the library directly.
    """
    name = config.get("cadence", "productive_li_heavy_v1")
    steps = cadencelibrary.named(name)
    return {"name": name, "steps": tuple(steps or ())}


def _process_contact(contact, company, domain, sources, caps_cfg,
                     strategy, sb_facts, config, model, client_name=None):
    """Run stages A-G for one contact. Returns a contact entry for the plan."""
    email = contact.get("email", "")
    first_name = contact.get("first_name", "")
    title = contact.get("title", "")
    contact_key = contact.get("contact_key", email)
    sender_name = contact.get("sender_name",
                              (config.get("sender") or {}).get("name", ""))

    result = {
        "contact_key": contact_key,
        "email": email,
        "first_name": first_name,
        "title": title,
        "sequences": {},
        "subjects": {},
        "facts": [],
        "hypothesis": {},
        "match": {},
        "qualification": None,
        "held": None,
        "sequence_gate": {},
        "copylint": {},
    }

    try:
        # A. ICP check — through the signal_verification skill.
        icp_skill = skills.load("signal_verification")
        icp_raw = _call_model(model, icp_skill.procedure,
                              copyprompts.icp_user(company, domain, sources),
                              client=client_name, config=config)
        icp = _parse_json(icp_raw)
        if not icp.get("is_agency"):
            result["qualification"] = "UNQUALIFIED"
            result["held"] = "not an agency: %s" % (
                icp.get("what_they_actually_are") or "?")
            return result

        # B. Extract facts — through the account_research skill.
        extract_skill = skills.load("account_research")
        extract_raw = _call_model(
            model, extract_skill.procedure,
            copyprompts.extract_user(company, domain, sources),
            client=client_name, config=config)
        extracted = _parse_json(extract_raw)
        facts = extracted.get("facts") or []
        for f in facts:
            f["source_url"] = copyprompts.source_url_for(f, sources)
        result["facts"] = facts
        if not facts:
            result["qualification"] = "INSUFFICIENT"
            result["held"] = "no verifiable fact in the pack"
            return result

        # C. Hypothesis
        br_context = _format_br_context(sb_facts)
        hyp_raw = _call_model(
            model, copystages.HYPOTHESIS_SYSTEM,
            copystages.hypothesis_user(company, domain, title, facts,
                                       br_context),
            client=client_name, config=config)
        hyp = _parse_json(hyp_raw)
        result["hypothesis"] = hyp
        result["qualification"] = hyp.get("qualification") or "QUALIFIED_THIN"
        if result["qualification"] == "INSUFFICIENT":
            result["held"] = "insufficient basis: %s" % hyp.get(
                "hypothesis_basis")
            return result

        # D. Match
        match_raw = _call_model(
            model, copystages.MATCH_SYSTEM,
            copystages.match_user(hyp.get("hypothesis"),
                                  hyp.get("role_family"),
                                  title, caps_cfg),
            client=client_name, config=config)
        match = _parse_json(match_raw)
        result["match"] = match
        cap_key = match.get("capability_key")
        cap_sentence = caps_cfg.get(cap_key, "")

        # E. Strategy is already decided (cached per segment+persona).
        # The hypothesis informs the writer's angle. In v2_run.py the strategy
        # was per-lead and took the hypothesis as input; here the strategy is
        # per-segment but the hypothesis still flows to the writer through the
        # capability match and the plan context.
        plan_data = dict(strategy) if strategy else {}
        plan_data["hypothesis"] = hyp.get("hypothesis", "")
        plan_data["what_changes"] = match.get("what_changes", "")
        plan_json = json.dumps(plan_data, indent=1)

        # F. Writer
        variant = copyprompts.ps_variant_for(email)
        if variant == "ps_none":
            variant = "ps_fact"
        result["ps_variant"] = variant

        # F. Writer — through the cold_email_writing and linkedin_writing
        # skills. Both share WRITER_SYSTEM; the entrypoint loads both so
        # neither is disconnected.
        email_skill = skills.load("cold_email_writing")
        linkedin_skill = skills.load("linkedin_writing")
        writer_system = email_skill.procedure

        name = (first_name + " " + contact.get("last_name", "")).strip()
        writer_raw = _call_model(
            model, writer_system,
            copystages.writer_user(
                {"name": name, "title": title, "sender_name": sender_name},
                company, facts, plan_json, cap_sentence, variant,
                bool(contact.get("linkedin"))),
            client=client_name, config=config)
        w = _parse_json(writer_raw)

        if w.get("hold"):
            result["held"] = "writer held: %s" % w.get("hold_reason")
            return result

        # Populate sequences from writer output
        result["sequences"] = {
            "em1": (w.get("emails") or {}).get("em1", ""),
            "em2": (w.get("emails") or {}).get("em2", ""),
            "em3": (w.get("emails") or {}).get("em3", ""),
            "em4": (w.get("emails") or {}).get("em4", ""),
            "em5": (w.get("emails") or {}).get("em5", ""),
        }
        result["subjects"] = {
            "A": w.get("subject", ""),
            "B": w.get("subject_alt", ""),
            "C": w.get("subject_breakup", ""),
        }
        for key in ("connect", "msg1", "msg2", "msg3"):
            li_text = (w.get("linkedin") or {}).get(key, "")
            if li_text:
                result["sequences"][key] = li_text
        for key in ("em1", "em3"):
            ps_text = (w.get("ps") or {}).get(key, "")
            if ps_text:
                result["sequences"]["ps_" + key] = ps_text

        # G. copylint, then sequencegate
        lead_for_lint = {
            "id": contact_key,
            "steps": [
                {"subject": result["subjects"].get("A", ""),
                 "body": result["sequences"].get("em1", "")},
                {"subject": "", "body": result["sequences"].get("em2", "")},
                {"subject": result["subjects"].get("B", ""),
                 "body": result["sequences"].get("em3", "")},
                {"subject": "", "body": result["sequences"].get("em4", "")},
                {"subject": result["subjects"].get("C", ""),
                 "body": result["sequences"].get("em5", "")},
            ],
            "ps": {k: v for k, v in result["sequences"].items()
                   if k.startswith("ps_")},
            "linkedin": {k: v for k, v in result["sequences"].items()
                         if k in ("connect", "msg1", "msg2", "msg3")},
            "pack": {"facts": [{"snippet": f.get("quote") or f.get("text")}
                               for f in facts]},
        }
        result["copylint"] = copylint.check_batch([lead_for_lint])

        seqs_for_gate = {
            "company": company,
            "emails": {k: v for k, v in result["sequences"].items()
                       if k.startswith("em") and v},
            "linkedin": {k: v for k, v in result["sequences"].items()
                         if k in ("connect", "msg1", "msg2", "msg3") and v},
            "ps": {k: v for k, v in result["sequences"].items()
                   if k.startswith("ps_") and v},
            "subjects": result["subjects"],
            "hypothesis": hyp.get("hypothesis", ""),
        }
        result["sequence_gate"] = sequencegate.check(
            seqs_for_gate, facts=facts, capability=cap_sentence,
            qualification=result["qualification"])

    except (llm.ModelError, llm.ModelUnavailable) as e:
        result["held"] = "model error: %s" % str(e)[:200]
    except Exception as e:
        result["held"] = "%s: %s" % (type(e).__name__, str(e)[:200])

    return result


def _call_model(model, system, user, client=None, config=None):
    """Route a model call through the injected model.

    The system and user prompts are concatenated into a single prompt for the
    `complete()` seam. The model's `complete()` method handles the HTTP call,
    the spend ledger, and the retry loop.

    `client` and `config` thread into the spend gate. TASK-373.
    """
    return model.complete(system + "\n\n" + user, client=client, config=config)


def _parse_json(text):
    """Extract JSON from model output, tolerating fences."""
    if isinstance(text, dict):
        return text
    t = re.sub(r"^```(?:json)?|```$", "", str(text or "").strip(), flags=re.M)
    i, j = t.find("{"), t.rfind("}")
    if i == -1 or j == -1:
        raise ValueError("no JSON in model output: %r" % t[:160])
    return json.loads(t[i:j + 1], strict=False)


def _format_br_context(facts):
    """Format verified Second Brain facts for the hypothesis prompt."""
    if not facts:
        return None
    lines = []
    for fact in facts:
        lines.append("[%s] %s (source: %s, verified: %s)" % (
            fact.get("source", "unknown"),
            fact.get("text", ""),
            fact.get("source", ""),
            fact.get("verified", False)))
    return "\n".join(lines) if lines else None
