"""The extraction step: Groq gpt-oss-120b extracts 3-5 facts from a cleaned pack.

    from src import copyextract
    result = copyextract.extract_one(company, domain, sources, model=model)

Each fact carries a `quote` that MUST appear character-for-character in the
input. A fact whose span is absent is a hallucination and the lead loses
that fact. This is checked HERE, not trusted to the prompt.

## THE MODEL

The operator chose `openai/gpt-oss-120b` on Groq with reasoning effort low.
Groq speaks OpenAI-compatible `/chat/completions`, so `llm.OpenAICompatibleModel`
is the adapter, pointed at Groq's base URL with the Groq key.

## CONCURRENCY AND COST

The task specifies concurrency 50 and every call ledgered. The concurrency
is handled by the caller (the pipeline script). The ledger is
`spendledger.record`, the same path the research pack uses.

## HOLD IS A REAL OUTCOME

A lead with no usable facts is HELD. The extractor returns `usable: false`
and the writer returns `hold: true`. Both are expected paths. The held
count is a headline number, not a failure.
"""
import json
import os
import re
import time

from . import copyprompts

#: The model the operator chose for extraction.
EXTRACT_MODEL = "openai/gpt-oss-120b"

#: Groq's OpenAI-compatible endpoint.
GROQ_BASE = "https://api.groq.com/openai/v1"

#: The env var that carries the Groq key.
GROQ_KEY_VAR = "GROQ_API_KEY"

#: Cost per extraction call, in the ledger's integer cents. Groq charges
#: per token; this is the PLANNED cost for the ledger, same as the Apify
#: actors carry planned costs in `researchpack.actors`.
EXTRACT_COST = 2

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


class ExtractionError(RuntimeError):
    """An extraction that failed for a reason other than 'no facts'."""


class ModelUnavailableError(ExtractionError):
    """The model could not be reached. Retry-able."""


def _parse_json(text):
    """Extract JSON from model output. The prompt asks for strict JSON with
    no prose, but models sometimes wrap it in markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    match = _JSON_RE.search(text)
    if match:
        text = match.group(0)
    return json.loads(text)


def verify_quotes(facts, input_text):
    """Check every fact's `quote` appears verbatim in the input.

    Returns (verified, removed) where `verified` is the list of facts whose
    quote was found and `removed` is the list of facts whose quote was NOT
    found. A fact without a `quote` field is removed - it has no evidence.

    THE PROMPT SAYS IT IS CHECKED, SO THIS CHECKS IT. A fact whose span is
    absent is a hallucination and the lead loses that fact.
    """
    verified, removed = [], []
    normalised = " ".join(input_text.split())
    for fact in (facts or []):
        quote = (fact.get("quote") or "").strip()
        if not quote:
            removed.append({**fact, "_remove_reason": "no quote"})
            continue
        # Normalise both sides for whitespace differences. The model may
        # collapse or expand whitespace; the CONTENT must match.
        norm_quote = " ".join(quote.split())
        if norm_quote in normalised:
            verified.append(fact)
        else:
            removed.append({**fact, "_remove_reason": "quote not in input"})
    return verified, removed


def _build_model(key=None, base=None):
    """Build the Groq adapter. `llm.OpenAICompatibleModel` speaks the
    OpenAI-compatible shape Groq implements."""
    from . import llm
    key = key or os.environ.get(GROQ_KEY_VAR)
    base = base or GROQ_BASE
    if not key:
        raise ExtractionError(
            f"{GROQ_KEY_VAR} is not set; cannot call Groq for extraction")
    return llm.OpenAICompatibleModel(key=key, model=EXTRACT_MODEL, base=base)


def extract_one(company, domain, sources, model=None, input_text=None):
    """Extract facts for one lead.

    `sources` is a list of {label, url, text} already cleaned of chrome.
    `model` is an optional pre-built model; if absent, one is built from env.
    `input_text` is the full text sent to the model, for quote verification.
        If absent, it is reconstructed from sources.

    Returns the parsed extraction result with quotes verified.
    """
    from . import packcleaner

    model = model or _build_model()
    user_prompt = copyprompts.extract_user(company, domain, sources)

    try:
        raw = model.complete(
            f"{copyprompts.EXTRACT_SYSTEM}\n\n{user_prompt}",
            temperature=0)
    except Exception as e:
        if "unavailable" in str(type(e).__name__).lower() \
                or "unavailable" in str(e).lower():
            raise ModelUnavailableError(str(e)) from e
        raise ExtractionError(str(e)) from e

    try:
        result = _parse_json(raw)
    except (json.JSONDecodeError, ValueError) as e:
        raise ExtractionError(f"invalid JSON from extractor: {e}") from e

    # Reconstruct input text for quote verification if not provided
    if input_text is None:
        parts = []
        for s in sources:
            parts.append(s.get("text") or "")
        input_text = "\n".join(parts)

    # VERIFY QUOTES. The prompt says it is checked; this is the check.
    facts = result.get("facts") or []
    verified, removed = verify_quotes(facts, input_text)
    result["facts"] = verified
    result["_removed_facts"] = removed
    result["_quote_verification_run"] = True

    # Enforce fact count bounds
    if len(verified) < copyprompts.MIN_FACTS:
        result["usable"] = False
    if len(verified) > copyprompts.MAX_FACTS:
        result["facts"] = verified[:copyprompts.MAX_FACTS]

    # Validate angle
    angle = result.get("angle")
    if angle is not None and angle not in copyprompts.ANGLES:
        result["angle"] = None
        result["angle_reason"] = (
            f"extracted angle {angle!r} not in allowed list")

    return result


def extract_batch(leads, model=None, concurrency=50, ledger_client=None):
    """Extract facts for a batch of leads.

    `leads` is a list of {id, company, domain, sources} where sources are
    already cleaned.

    Returns a dict mapping lead_id to extraction result.
    The `concurrency` parameter is the max parallel calls.
    Every call is ledgered through `spendledger.record`.
    """
    from . import spendledger

    model = model or _build_model()
    results = {}
    errors = {}

    for lead in leads:
        lead_id = lead.get("id") or lead.get("domain") or "?"
        try:
            spendledger.record(
                ledger_client or "copyextract",
                "groq", "extract", EXTRACT_COST)
            result = extract_one(
                lead.get("company") or lead.get("domain"),
                lead.get("domain") or "",
                lead.get("sources") or [],
                model=model)
            results[lead_id] = result
        except ModelUnavailableError as e:
            errors[lead_id] = {"error": "unavailable", "detail": str(e)}
        except ExtractionError as e:
            errors[lead_id] = {"error": "extraction_failed", "detail": str(e)}

    return {"results": results, "errors": errors,
            "total": len(leads),
            "extracted": len(results),
            "errored": len(errors),
            "held": sum(1 for r in results.values()
                        if not r.get("usable", True))}
