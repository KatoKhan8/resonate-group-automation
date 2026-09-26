#!/usr/bin/env python3
"""xAI (Grok) adapter.  TASK-157, migrated to Responses API in TASK-182.

Responses API against https://api.x.ai/v1/responses, Bearer token auth.
The Chat Completions endpoint (/v1/chat/completions) was DEPRECATED by xAI
and returns HTTP 410 Gone.  Web search now lives on the Responses API with
{"type": "web_search"} as a tool entry.

    https://docs.x.ai/developers/quickstart
    https://docs.x.ai/developers/rest-api-reference/inference/responses
    https://docs.x.ai/developers/tools/overview
    https://docs.x.ai/developers/cost-tracking

The lane is LIVE INTELLIGENCE and mid-to-high reasoning: recent developments,
hiring, launches, partnerships, leadership changes, funding, ambiguous ICP,
evidence challenger, Qwen quality judge.  Grok does NOT replace the crawler.
The evidence order stays: structured data -> cached company evidence -> free
crawler -> Grok only where incremental value is expected.

This module is the adapter only.  It is NOT wired into generate, qualify,
research or any production path.  Claude integrates.

  python -m src.providers.xai --check
"""
import argparse
import time

from . import (MissingKey, ProviderError, key, ok, request, result, failed,
               redact)
from .. import modelrouter

BASE = "https://api.x.ai/v1"
ENV_KEY = "XAI_API_KEY"

# The endpoint this adapter calls.  A test asserts the cassette matches this
# exact path so a provider-side deprecation surfaces as a red test, not a
# silent failure against a fake that faithfully fakes a dead endpoint.
RESPONSES_ENDPOINT = "/responses"

# Model slugs live in config/model_policy.yaml.  The router is the single
# source of truth; this module reads from it.  TASK-360.
MODELS = modelrouter.provider_models("xai")
DEFAULT_MODEL = modelrouter.default_model("xai")

# Bounds.  No agentic loop may run unbounded.
MAX_TOKENS_CAP = 8192
MAX_TOOL_CALLS = 10
MAX_SEARCH_TOOLS = 3
MAX_TEMPERATURE = 2.0
# PER ATTEMPT, SECONDS, AND A CEILING RATHER THAN A DEFAULT - `respond`
# clamps a caller's request down to this, so nothing here can hang however the
# call site is written.
#
# RAISED FROM 60 ON 2026-09-17, and the evidence is that the old value made
# this module unusable for the work it exists to do. `web_search` is the
# capability this lane is FOR, and TASK-166 measured what one such call costs:
# 1,500-4,000 reasoning tokens and 41-65 search URLs per question. None of that
# finishes in a minute.
#
# The tell was already in the repository and was read as a quirk rather than a
# symptom: `docs/GROK-VS-FREE-RESEARCH-2026-09-16.md` records that the
# measurement "calls the Responses API directly" and that this adapter "was not
# used". A ceiling every real caller has to bypass is not a bound, it is a
# module nobody can use - and a bypassed adapter takes its trimming, its usage
# capture and its redaction out of the path with it.
#
# Confirmed again the same day: `scripts/grok_provider_research.py` asked one
# documentation question through this adapter with `timeout=180`, the clamp cut
# it to 60, and the call died on `TimeoutError: The read operation timed out`.
XAI_TIMEOUT = 300
MAX_RETRIES = 2

# https://docs.x.ai/developers/cost-tracking
# 10_000_000_000 ticks = $1 USD.
TICKS_PER_USD = 10_000_000_000

# Tools the model may invoke.  web_search and x_search are OPT-IN per call,
# never defaults.  Running live research for every company automatically is
# the expensive mistake this lane exists to avoid.
OPT_IN_TOOLS = ("web_search", "x_search")


def headers():
    """Bearer auth.  Doc: https://docs.x.ai/developers/quickstart"""
    return {"Authorization": f"Bearer {key(ENV_KEY)}"}


def check(live=False):
    """Configuration readiness by default; one minimal response if live.

    The default spends nothing and makes no request.  A live check sends a
    one-token response to confirm the key is accepted; it costs a fraction
    of a cent.
    """
    if not live:
        try:
            key(ENV_KEY)
        except MissingKey as e:
            return failed("xAI", e)
        return {"provider": "xAI", "ok": None, "status": None, "skipped": True,
                "note": "key configured, no call made (--live-xai to spend)"}
    try:
        body = {"model": DEFAULT_MODEL,
                "input": [{"role": "user",
                           "content": "__xai_check__"}],
                "max_output_tokens": 1}
        status, data = request("POST", f"{BASE}{RESPONSES_ENDPOINT}",
                               headers(), body, XAI_TIMEOUT)
        return result("xAI", status, str(data))
    except (ProviderError, MissingKey) as e:
        return failed("xAI", e)


# Fields returned to a caller.  Nothing else escapes the module.
RESPONSE_FIELDS = ("content", "status", "model", "refusal", "tool_calls",
                   "usage", "search_urls")


def respond(input_messages, model=None, max_tokens=None, temperature=None,
            tools=None, timeout=None, max_attempts=None, sleep=time.sleep):
    """One Responses API call.  Bounded, trimmed, usage captured.

    https://docs.x.ai/developers/rest-api-reference/inference/responses

    Parameters
    ----------
    input_messages : list[dict]
        role/content pairs.  At least one required.  Sent as the ``input``
        field of the request body.
    model : str, optional
        Model name.  Must be in MODELS.  Defaults to DEFAULT_MODEL.
    max_tokens : int, optional
        Output token cap.  Clamped to MAX_TOKENS_CAP.
    temperature : float, optional
        Sampling temperature, 0..MAX_TEMPERATURE.
    tools : list[dict], optional
        OPT-IN.  Server-side tools the model may invoke (web_search, x_search).
        Never included unless the caller passes them.
    timeout : int, optional
        Per-attempt seconds.  Defaults to XAI_TIMEOUT.
    max_attempts : int, optional
        Total attempts including the first.  Defaults to MAX_RETRIES + 1.
    sleep : callable
        Injection point for tests.

    Returns
    -------
    dict
        Trimmed to RESPONSE_FIELDS.  usage carries token counts and cost.

    A Grok answer is a claim with a source, or it is not evidence.  The caller
    must not treat ``content`` as verified fact.
    """
    model = model or DEFAULT_MODEL
    if model not in MODELS:
        raise ValueError(
            f"xai: {model!r} is not in the allowlist.  "
            f"Choose from: {', '.join(MODELS)}")

    if temperature is not None and not (0 <= temperature <= MAX_TEMPERATURE):
        raise ValueError(
            f"xai: temperature {temperature} out of range 0..{MAX_TEMPERATURE}")

    body = {"model": model, "input": list(input_messages)}

    if max_tokens is not None:
        body["max_output_tokens"] = min(max_tokens, MAX_TOKENS_CAP)

    if temperature is not None:
        body["temperature"] = temperature

    # Tools are OPT-IN.  If the caller passes none, the body carries no tools
    # key and the model cannot invoke web_search or x_search.
    if tools:
        if len(tools) > MAX_TOOL_CALLS:
            raise ValueError(
                f"xai: {len(tools)} tools exceeds the cap of {MAX_TOOL_CALLS}")
        body["tools"] = list(tools)

    timeout = min(timeout or XAI_TIMEOUT, XAI_TIMEOUT)
    max_attempts = min(max_attempts or (MAX_RETRIES + 1), MAX_RETRIES + 1)

    status, data = _send_with_retry(body, timeout, max_attempts, sleep)

    if not ok(status):
        raise ProviderError(f"xai respond: {status} {redact(str(data))[:200]}")

    return {
        "content": _content(data),
        "status": (data or {}).get("status"),
        "model": (data or {}).get("model"),
        "refusal": _refusal(data),
        "tool_calls": _tool_calls(data),
        "usage": _usage(data),
        "search_urls": _search_urls(data),
    }


def _send_with_retry(body, timeout, max_attempts, sleep):
    """POST with bounded retry on 5xx and network errors.

    MissingKey is never retried: a credential that is absent now will not
    materialise on the second attempt.
    """
    # Resolve the credential once before the loop.  A missing key raises
    # immediately rather than consuming attempts on a failure that cannot
    # self-heal.
    hdrs = headers()

    last_status, last_data = None, None
    for attempt in range(max_attempts):
        try:
            last_status, last_data = request(
                "POST", f"{BASE}{RESPONSES_ENDPOINT}", hdrs, body, timeout)
            if ok(last_status):
                return last_status, last_data
            # 4xx is a client error; retrying won't help.
            if 400 <= last_status < 500:
                return last_status, last_data
        except MissingKey:
            raise
        except ProviderError:
            if attempt >= max_attempts - 1:
                raise
        if attempt < max_attempts - 1:
            sleep(0.5 * (2 ** attempt))
    return last_status, last_data


def _content(data):
    """Extract text content from the output array.

    The Responses API returns output as an array of typed items.  Text content
    lives in items with type="message", under content[].text.
    """
    output = (data or {}).get("output") or []
    parts = []
    for item in output:
        if item.get("type") == "message":
            for c in item.get("content") or []:
                if c.get("type") == "output_text":
                    text = c.get("text")
                    if text:
                        parts.append(text)
    return "\n".join(parts) if parts else None


def _refusal(data):
    """Extract refusal from the output array, if present."""
    output = (data or {}).get("output") or []
    for item in output:
        if item.get("type") == "message":
            for c in item.get("content") or []:
                if c.get("type") == "refusal":
                    return c.get("text")
    return None


def _tool_calls(data):
    """Tool calls from the output array, trimmed to id/name/type."""
    output = (data or {}).get("output") or []
    calls = []
    for item in output:
        if item.get("type") in ("web_search_call", "x_search_call",
                                "function_call"):
            calls.append({
                "id": item.get("id"),
                "type": item.get("type"),
                "status": item.get("status"),
            })
    return calls if calls else None


def _search_urls(data):
    """URLs from web_search_call items in the output array."""
    output = (data or {}).get("output") or []
    urls = []
    for item in output:
        if item.get("type") == "web_search_call":
            action = item.get("action") or {}
            for src in action.get("sources") or []:
                if src.get("type") == "url":
                    url = src.get("url", "")
                    if url:
                        urls.append(url)
    return urls


def _usage(data):
    """Usage and cost from the response.

    https://docs.x.ai/developers/cost-tracking
    cost_in_usd_ticks: 10_000_000_000 ticks = $1 USD.  The field covers all
    model decodes and every tool invocation within the agentic loop.

    The Responses API uses different field names than Chat Completions:
        input_tokens  (was prompt_tokens)
        output_tokens (was completion_tokens)
        input_tokens_details.cached_tokens  (was prompt_tokens_details.cached_tokens)
        output_tokens_details.reasoning_tokens (was completion_tokens_details.reasoning_tokens)

    The normalised return dict keeps the descriptive names.
    """
    u = (data or {}).get("usage") or {}
    input_details = u.get("input_tokens_details") or {}
    output_details = u.get("output_tokens_details") or {}
    out = {
        "prompt_tokens": u.get("input_tokens"),
        "completion_tokens": u.get("output_tokens"),
        "total_tokens": u.get("total_tokens"),
        "cached_tokens": input_details.get("cached_tokens"),
        "reasoning_tokens": output_details.get("reasoning_tokens"),
        "cost_in_usd_ticks": u.get("cost_in_usd_ticks"),
        "num_sources_used": u.get("num_sources_used"),
    }
    # num_server_side_tools_used is a count on the Responses API, replacing
    # the per-tool breakdown that server_side_tool_usage carried on Chat
    # Completions.  Only included when non-zero, matching the old pattern.
    nsstu = u.get("num_server_side_tools_used")
    if nsstu:
        out["num_server_side_tools_used"] = nsstu
    return out


def ticks_to_usd(ticks):
    """Convert cost_in_usd_ticks to a float USD amount.

    https://docs.x.ai/developers/cost-tracking
    """
    if ticks is None or ticks < 0:
        return None
    return ticks / TICKS_PER_USD


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.providers.xai")
    p.add_argument("--check", action="store_true")
    p.add_argument("--live", action="store_true",
                   help="spend a fraction of a cent on a real response")
    a = p.parse_args(argv)
    r = check(live=a.live)
    print(f"{'ok  ' if r.get('ok') else 'FAIL'} {r['provider']:<12} "
          f"{r.get('status') if r.get('status') is not None else '-'}"
          f"  {r['note']}")
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
