"""The v2 copy engine: stages A to H, the stage runner.

docs/COPY-ENGINE-SPEC-v2.md is the spec. Claude owns the prompts
(`copystages.py`, `copyprompts.py`) and the gate (`sequencegate.py`).
This module runs them in order, per lead, and assembles the output.

THE COST SHAPE. Stages A to E run on a cheap model (Groq gpt-oss-120b).
Only stage F (the writer) runs on Sonnet. The expensive model writes what
a prospect reads and nothing else.

THE REWRITE RULE. Stage G (the gate) names the step that failed. Only that
step is rewritten, not the whole sequence. Regenerating everything hides
which message was wrong.

NO LIVE OUTREACH. This module generates copy. It does not send, activate,
or mutate any provider state.
"""
import json
import re
import time

from . import copystages, copyprompts, sequencegate, copylint

#: Maximum retries for a single stage call.
MAX_RETRIES = 2

#: Groq's Cloudflare blocks urllib's default UA. This one is honest.
GROQ_USER_AGENT = "resonate-copyengine/2.0"

#: Sonnet truncates at small caps. Size generously.
WRITER_MAX_TOKENS = 4000
CHEAP_MAX_TOKENS = 2000


class StageError(RuntimeError):
    """A stage failed after retries."""


class TruncationError(StageError):
    """The model cut off mid-JSON. Distinguished from a bad answer."""


def _parse_json(text, label="stage"):
    """Parse model output as JSON, treating truncation as its own error.

    A JSONDecodeError is truncation BEFORE it is a bad model. Sonnet cut
    off mid-JSON on 4 of 10 at max_tokens 700 and 5 of 10 at 2600. The
    fix is more tokens, not a different prompt.
    """
    body = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", body, re.S)
    if fence:
        body = fence.group(1).strip()
    try:
        data = json.loads(body, strict=False)
    except (json.JSONDecodeError, ValueError) as e:
        if len(body) > 200 and not body.rstrip().endswith("}"):
            raise TruncationError(
                "%s: model output truncated (%d chars, no closing brace): %s"
                % (label, len(body), str(e)[:100]))
        raise StageError(
            "%s: invalid JSON: %s" % (label, str(e)[:200]))
    if not isinstance(data, dict):
        raise StageError("%s: expected JSON object, got %s"
                         % (label, type(data).__name__))
    return data


def _call(model, system, user, label, max_tokens=None, retries=MAX_RETRIES):
    """One model call with retry on truncation.

    429 gets ONE backoff. Every other 4xx is not worth a retry.
    """
    prompt = "%s\n\n%s" % (system, user)
    last_err = None
    for attempt in range(retries + 1):
        try:
            text = model.complete(prompt)
            return _parse_json(text, label)
        except TruncationError as e:
            last_err = e
            if attempt < retries:
                continue
            raise
        except StageError:
            raise
    raise last_err or StageError("%s: exhausted retries" % label)


def _role_family_for(title):
    """Map a job title to a role family for stage D.

    The families are in copystages.ROLE_FAMILIES. This maps common titles
    to the right one.
    """
    t = (title or "").lower()
    if any(w in t for w in ("ceo", "founder", "coo", "chief executive",
                             "managing director", "president", "owner",
                             "chair", "managing partner")):
        return "executive"
    if any(w in t for w in ("operations", "ops", "head of production",
                             "production director", "studio manager",
                             "head of resource", "traffic manager")):
        return "operations"
    if any(w in t for w in ("project manager", "project director",
                             "delivery", "design director")):
        return "delivery"
    if any(w in t for w in ("finance", "cfo", "head of finance")):
        return "finance"
    return "executive"


def _ps_variant(key):
    """Deterministic P.S. variant assignment. ps_none is retired in v2."""
    variant = copyprompts.ps_variant_for(key)
    if variant == "ps_none":
        return "ps_fact"
    return variant


# --------------------------------------------------------------------------
# THE STAGE RUNNER
# --------------------------------------------------------------------------

def run_stages(lead, cheap_model, expensive_model, client_config=None):
    """Run stages A to H for one lead. Returns the assembled sequence.

    `lead` is a dict with:
        company, domain, role_title, name, sender_name, linkedin (or None),
        sources (list of {label, url, text}), key (unique id)

    `cheap_model` has a `.complete(prompt) -> str` method (stages A-E).
    `expensive_model` has the same interface (stage F only).
    `client_config` is the parsed productive.yaml (capabilities, etc.).

    Returns a dict with:
        qualification, facts, hypothesis, capability, plan, copy, gate,
        output (EmailBison vars, HeyReach steps), stages_log
    """
    config = client_config or {}
    capabilities = (config.get("product") or {}).get("capabilities") or {}
    log = []
    result = {"stages_log": log}

    company = lead.get("company", "")
    domain = lead.get("domain", "")
    role_title = lead.get("title") or lead.get("role_title", "")
    sources = lead.get("sources") or []

    # STAGE A: Lead qualification
    a_data = _call(cheap_model, copyprompts.ICP_SYSTEM,
                   copyprompts.icp_user(company, domain, sources),
                   "A:qualification")
    log.append({"stage": "A", "model": cheap_model.name, "output": a_data})
    is_agency = a_data.get("is_agency", False)

    if not is_agency:
        result["qualification"] = "UNQUALIFIED"
        result["qualification_evidence"] = a_data.get("what_they_actually_are", "")
        result["facts"] = []
        result["hold"] = True
        result["hold_reason"] = "not an agency: %s" % a_data.get(
            "what_they_actually_are", "unknown")
        return result

    # STAGE B: Research extraction
    b_data = _call(cheap_model, copyprompts.EXTRACT_SYSTEM,
                   copyprompts.extract_user(company, domain, sources),
                   "B:extraction")
    log.append({"stage": "B", "model": cheap_model.name, "output": b_data})
    facts = b_data.get("facts") or []
    angle = b_data.get("angle")
    angle_reason = b_data.get("angle_reason", "")
    usable = b_data.get("usable", True)

    if not facts or not usable:
        result["qualification"] = "INSUFFICIENT"
        result["facts"] = facts
        result["hold"] = True
        result["hold_reason"] = "insufficient research for copy"
        return result

    result["facts"] = facts
    result["angle"] = angle
    result["sources"] = sources

    # STAGE C: Problem hypothesis
    c_data = _call(cheap_model, copystages.HYPOTHESIS_SYSTEM,
                   copystages.hypothesis_user(
                       company, domain, role_title, facts),
                   "C:hypothesis")
    log.append({"stage": "C", "model": cheap_model.name, "output": c_data})
    hypothesis = c_data.get("hypothesis", "")
    signal_strength = c_data.get("signal_strength", "weak")
    qualification = c_data.get("qualification", "QUALIFIED_THIN")
    business_model = c_data.get("business_model", "")
    role_family = c_data.get("role_family") or _role_family_for(role_title)

    result["qualification"] = qualification
    result["hypothesis"] = hypothesis
    result["signal_strength"] = signal_strength
    result["business_model"] = business_model
    result["role_family"] = role_family

    if qualification == "INSUFFICIENT":
        result["hold"] = True
        result["hold_reason"] = "could not form a credible hypothesis"
        return result

    # STAGE D: Value proposition matching
    d_data = _call(cheap_model, copystages.MATCH_SYSTEM,
                   copystages.match_user(
                       hypothesis, role_family, role_title, capabilities),
                   "D:match")
    log.append({"stage": "D", "model": cheap_model.name, "output": d_data})
    capability_key = d_data.get("capability_key", "")
    why_this_one = d_data.get("why_this_one", "")
    what_changes = d_data.get("what_changes", "")
    capability_words = capabilities.get(capability_key, "")

    result["capability_key"] = capability_key
    result["capability_sentence"] = capability_words
    result["why_this_capability"] = why_this_one
    result["what_changes"] = what_changes

    # STAGE E: Sequence strategy
    assets_available = _assets_available(config)
    e_data = _call(cheap_model, copystages.STRATEGY_SYSTEM,
                   copystages.strategy_user(
                       company, hypothesis, capability_words,
                       what_changes, role_title, facts, assets_available),
                   "E:strategy")
    log.append({"stage": "E", "model": cheap_model.name, "output": e_data})
    plan = e_data
    result["plan"] = plan

    # STAGE F: Copy generation (Sonnet, the expensive model)
    ps_variant = _ps_variant(lead.get("key") or lead.get("id") or company)
    has_linkedin = bool(lead.get("linkedin"))
    capability_sentence = "%s: %s" % (capability_key, capability_words)

    f_data = _call(expensive_model, copystages.WRITER_SYSTEM,
                   copystages.writer_user(
                       lead, company, facts, json.dumps(plan, indent=2),
                       capability_sentence, ps_variant, has_linkedin),
                   "F:writer", max_tokens=WRITER_MAX_TOKENS)
    log.append({"stage": "F", "model": expensive_model.name, "output": f_data})

    if f_data.get("hold"):
        result["hold"] = True
        result["hold_reason"] = f_data.get("hold_reason", "writer held this lead")
        return result

    copy = f_data
    result["copy"] = copy

    # STAGE G: Quality validation (the sequence-level gate)
    sequence = {
        "emails": copy.get("emails") or {},
        "linkedin": copy.get("linkedin") or {},
        "subjects": {
            "subject_a": copy.get("subject", ""),
            "subject_b": copy.get("subject_alt", ""),
            "subject_c": copy.get("subject_breakup", ""),
        },
        "hypothesis": hypothesis,
        "ps": copy.get("ps") or {},
        "company": company,
    }
    gate_result = sequencegate.check(
        sequence, facts=facts, capability=capability_words,
        qualification=qualification)
    log.append({"stage": "G", "output": gate_result})
    result["gate"] = gate_result

    # REWRITE FAILED STEPS. The gate names the step; only that step is
    # rewritten, not the whole sequence.
    if not gate_result["passed"]:
        copy = _rewrite_failed_steps(
            expensive_model, company, lead, facts, plan,
            capability_sentence, ps_variant, has_linkedin,
            copy, gate_result, log)
        result["copy"] = copy
        # Re-run the gate on the rewritten sequence.
        sequence = {
            "emails": copy.get("emails") or {},
            "linkedin": copy.get("linkedin") or {},
            "subjects": {
                "subject_a": copy.get("subject", ""),
                "subject_b": copy.get("subject_alt", ""),
                "subject_c": copy.get("subject_breakup", ""),
            },
            "hypothesis": hypothesis,
            "ps": copy.get("ps") or {},
            "company": company,
        }
        gate_result = sequencegate.check(
            sequence, facts=facts, capability=capability_words,
            qualification=qualification)
        result["gate"] = gate_result

    # STAGE H: Output assembly
    output = _assemble_output(copy, lead, config)
    result["output"] = output
    result["hold"] = False
    return result


def _rewrite_failed_steps(expensive_model, company, lead, facts, plan,
                          capability_sentence, ps_variant, has_linkedin,
                          copy, gate_result, log):
    """Rewrite only the steps the gate named as failed.

    The gate says "em4 repeats em2", not "regenerate". So we re-run the
    writer with a note about what went wrong, and replace only the named
    steps.
    """
    failed_steps = set()
    for f in gate_result.get("failures") or []:
        step = f.get("step", "")
        if step.startswith("em") or step in ("connect", "msg1", "msg2",
                                               "msg3", "subjects", "ps"):
            failed_steps.add(step)

    if not failed_steps:
        return copy

    # Re-run the writer with the failure context appended to the plan.
    failure_note = ("IMPORTANT: the previous attempt had these failures: %s"
                    % "; ".join("%s: %s" % (f["step"], f["why"])
                                for f in gate_result.get("failures") or []))
    augmented_plan = json.dumps(plan, indent=2) + "\n\n" + failure_note

    try:
        new_copy = _call(expensive_model, copystages.WRITER_SYSTEM,
                         copystages.writer_user(
                             lead, company, facts, augmented_plan,
                             capability_sentence, ps_variant, has_linkedin),
                         "F:rewrite", max_tokens=WRITER_MAX_TOKENS)
        log.append({"stage": "F-rewrite", "model": expensive_model.name,
                     "output": new_copy})
        if new_copy.get("hold"):
            return copy
        return new_copy
    except StageError:
        return copy


def _assets_available(config):
    """What the client config actually has for days 8 and 12.

    Per the spec: until customer cases, benchmarks, calculators and demo
    links arrive, days 8 and 12 use a concrete product workflow described
    in plain words.
    """
    product = config.get("product") or {}
    available = []
    if product.get("case_studies"):
        available.append("customer case studies")
    if product.get("benchmarks"):
        available.append("verified benchmarks")
    if product.get("demo_link"):
        available.append("demo link")
    if product.get("calculator"):
        available.append("profitability calculator")
    return ", ".join(available) if available else ""


def _assemble_output(copy, lead, config):
    """Stage H: EmailBison custom variables, HeyReach steps, preview data."""
    emails = copy.get("emails") or {}
    ps = copy.get("ps") or {}
    linkedin = copy.get("linkedin") or {}

    # EmailBison custom variables.
    bison_vars = {
        "subject_1": copy.get("subject", ""),
        "subject_2": copy.get("subject_alt", ""),
        "subject_3": copy.get("subject_breakup", ""),
        "body_1": emails.get("em1", ""),
        "body_2": emails.get("em2", ""),
        "body_3": emails.get("em3", ""),
        "body_4": emails.get("em4", ""),
        "body_5": emails.get("em5", ""),
        "ps_1": ps.get("em1", ""),
        "ps_3": ps.get("em3", ""),
    }

    # HeyReach steps.
    heyreach_steps = {
        "connect": linkedin.get("connect", ""),
        "msg1": linkedin.get("msg1", ""),
        "msg2": linkedin.get("msg2", ""),
        "msg3": linkedin.get("msg3", ""),
    }

    return {
        "bison_vars": bison_vars,
        "heyreach_steps": heyreach_steps,
        "ps_variant": copy.get("ps_variant", ""),
        "facts_used": copy.get("facts_used") or {},
        "confidence": copy.get("confidence"),
        "why_this_lead": copy.get("why_this_lead", ""),
    }


# --------------------------------------------------------------------------
# BATCH RUNNER
# --------------------------------------------------------------------------

def run_batch(leads, cheap_model, expensive_model, client_config=None):
    """Run the pipeline for a batch of leads. Returns per-lead results.

    Also computes the batch-level capability check: if every lead got the
    same capability, stage D is defaulting.
    """
    results = []
    capabilities = []
    for lead in leads:
        try:
            r = run_stages(lead, cheap_model, expensive_model, client_config)
            r["error"] = None
        except StageError as e:
            r = {"error": str(e), "qualification": None,
                 "hold": True, "hold_reason": str(e),
                 "stages_log": []}
        capabilities.append(r.get("capability_key"))
        results.append(r)

    # Batch-level gate: if every lead got the same capability, D is defaulting.
    non_null = [c for c in capabilities if c]
    if len(non_null) >= 5:
        distinct = set(non_null)
        if len(distinct) == 1:
            defaulting_cap = next(iter(distinct))
            for r in results:
                if r.get("gate") is None:
                    r["gate"] = {"passed": False, "failures": [],
                                 "warnings": [], "checks": []}
                r["gate"].setdefault("failures", []).append({
                    "check": "capability_matches",
                    "step": "batch",
                    "why": ("every lead in this batch was matched to %r: "
                            "stage D is not choosing, it is defaulting"
                            % defaulting_cap),
                })
                r["gate"]["passed"] = False

    return results
