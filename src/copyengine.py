"""The v2 copy engine pipeline. Orchestrates stages A through F.

This module is the PRODUCTION CALLER for the v2 prompt layer. Before this
module existed, copyprompts, copystages (except STRATEGY_SYSTEM via
campaignstrategy), secondbrain and the user-builder functions had zero
non-test callers in src/.

THE ORDER IS FIXED: A -> B -> C -> D -> E -> F.

    A   ICP qualification       copyprompts.ICP_SYSTEM + icp_user
    B   Fact extraction         copyprompts.EXTRACT_SYSTEM + extract_user
    C   Problem hypothesis      copystages.HYPOTHESIS_SYSTEM + hypothesis_user
    D   Value match             copystages.MATCH_SYSTEM + match_user
    E   Sequence strategy       campaignstrategy.for_segment (stage E)
    F   Writer                  copystages.WRITER_SYSTEM + writer_user

Stage E is delegated to campaignstrategy, which caches per segment+persona
and calls copystages.STRATEGY_SYSTEM internally.

WHAT THIS MODULE DOES NOT DO.

- It does not call any provider. No send, no stage, no activate.
- It does not approve anything. Approval is a separate gate.
- It does not weaken copylint or sequencegate. If they refuse, the refusal
  propagates.

The model call is injectable so tests never spend. Production passes a real
model; tests pass llm.ScriptedModel.
"""
import json

from . import copyprompts, copystages, campaignstrategy


def _call_model(system_prompt, user_prompt, model):
    """Make one model call. Returns the parsed JSON dict.

    The model is injectable. NoModel raises, which is the correct behaviour
    for production-without-a-model and for tests that forget to pass one.
    """
    full_prompt = system_prompt + "\n\n" + user_prompt
    raw = model.complete(full_prompt)
    return json.loads(raw) if isinstance(raw, str) else raw


# ---------------------------------------------------------------- stage A

def stage_a_icp(company, domain, sources, model):
    """Stage A: is this company a services agency that runs client projects?

    Returns the parsed ICP decision dict. Uses copyprompts.ICP_SYSTEM.
    """
    user_prompt = copyprompts.icp_user(company, domain, sources)
    return _call_model(copyprompts.ICP_SYSTEM, user_prompt, model)


# ---------------------------------------------------------------- stage B

def stage_b_extract(company, domain, sources, model):
    """Stage B: extract verifiable facts from source material.

    Returns the parsed extraction dict with facts, angle, company_hook.
    Uses copyprompts.EXTRACT_SYSTEM.
    """
    user_prompt = copyprompts.extract_user(company, domain, sources)
    return _call_model(copyprompts.EXTRACT_SYSTEM, user_prompt, model)


# ---------------------------------------------------------------- stage C

def stage_c_hypothesis(company, domain, role_title, facts, client, model):
    """Stage C: propose one operational problem the agency plausibly has.

    Returns the parsed hypothesis dict. Uses copystages.HYPOTHESIS_SYSTEM.
    Calls copystages.business_context_for, which reaches secondbrain.for_task
    transitively - this is how secondbrain enters the production path.
    """
    business_context = copystages.business_context_for(
        "cold_email_writing", client)
    user_prompt = copystages.hypothesis_user(
        company, domain, role_title, facts,
        business_context=business_context)
    return _call_model(copystages.HYPOTHESIS_SYSTEM, user_prompt, model)


# ---------------------------------------------------------------- stage D

def stage_d_match(hypothesis, role_family, role_title, capabilities, model):
    """Stage D: choose one Productive capability that answers the problem.

    Returns the parsed match dict with capability_key, why_this_one,
    what_changes. Uses copystages.MATCH_SYSTEM.
    """
    user_prompt = copystages.match_user(
        hypothesis, role_family, role_title, capabilities)
    return _call_model(copystages.MATCH_SYSTEM, user_prompt, model)


# ---------------------------------------------------------------- stage E

def stage_e_strategy(segment_key, persona, model=None):
    """Stage E: plan the nine-message sequence BEFORE any copy is written.

    Delegates to campaignstrategy.for_segment, which caches per segment+persona
    and calls copystages.STRATEGY_SYSTEM internally. Returns the strategy dict.
    """
    return campaignstrategy.for_segment(segment_key, persona, model=model)


# ---------------------------------------------------------------- stage F

def stage_f_writer(lead, company, facts, plan, capability_sentence,
                   ps_variant, has_linkedin, model):
    """Stage F: write the actual copy. The only stage a prospect's words come from.

    Returns the parsed writer output dict with subjects, emails, linkedin, ps.
    Uses copystages.WRITER_SYSTEM.
    """
    user_prompt = copystages.writer_user(
        lead, company, facts, plan, capability_sentence, ps_variant,
        has_linkedin)
    return _call_model(copystages.WRITER_SYSTEM, user_prompt, model)


# --------------------------------------------------------- full pipeline

def run_pipeline(company, domain, sources, role_title, client,
                 role_family, capabilities, segment_key, persona,
                 lead, ps_variant, has_linkedin, model):
    """Run the full A->B->C->D->E->F pipeline for one lead.

    Returns a dict with each stage's output keyed by stage letter.
    The model is shared across all stages; tests pass ScriptedModel.

    This function exists to prove the wiring: every stage function above
    is called, and the chain from copyprompts through copystages through
    campaignstrategy through secondbrain is traversed in a single call.
    """
    result = {}

    result["A"] = stage_a_icp(company, domain, sources, model)
    if not result["A"].get("is_agency"):
        return result

    result["B"] = stage_b_extract(company, domain, sources, model)
    if not result["B"].get("usable"):
        return result

    facts = result["B"].get("facts") or []
    result["C"] = stage_c_hypothesis(
        company, domain, role_title, facts, client, model)

    hypothesis = result["C"].get("hypothesis") or ""
    result["D"] = stage_d_match(
        hypothesis, role_family, role_title, capabilities, model)

    capability = result["D"].get("capability_key") or ""
    what_changes = result["D"].get("what_changes") or ""
    result["E"] = stage_e_strategy(segment_key, persona, model=model)

    plan = json.dumps(result["E"], indent=2) if result["E"] else "{}"
    capability_sentence = f"{capability}: {what_changes}"
    result["F"] = stage_f_writer(
        lead, company, facts, plan, capability_sentence,
        ps_variant, has_linkedin, model)

    return result
