#!/usr/bin/env python3
"""xAI (Grok) adapter.  TASK-157.

Chat completions against https://api.x.ai/v1, Bearer token auth.
OpenAI-compatible request/response shape.

    https://docs.x.ai/developers/quickstart
    https://docs.x.ai/developers/rest-api-reference/inference/chat-completions
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

BASE = "https://api.x.ai/v1"
ENV_KEY = "XAI_API_KEY"

# https://docs.x.ai/developers/models
MODELS = (
    "grok-4.6",
    "grok-4.5",
    "grok-4.3",
    "grok-4.20-0309-reasoning",
    "grok-4.20-0309-non-reasoning",
    "grok-build-0.1",
    "grok-4.20-multi-agent-0309",
)
DEFAULT_MODEL = "grok-4.6"

# Bounds.  No agentic loop may run unbounded.
MAX_TOKENS_CAP = 8192
MAX_TOOL_CALLS = 10
MAX_SEARCH_TOOLS = 3
MAX_TEMPERATURE = 2.0
XAI_TIMEOUT = 60
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
    """Configuration readiness by default; one minimal chat completion if live.

    The default spends nothing and makes no request.  A live check sends a
    one-token completion to confirm the key is accepted; it costs a fraction
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
                "messages": [{"role": "user",
                              "content": "__xai_check__"}],
                "max_completion_tokens": 1}
        status, data = request("POST", f"{BASE}/chat/completions",
                               headers(), body, XAI_TIMEOUT)
        return result("xAI", status, str(data))
    except (ProviderError, MissingKey) as e:
        return failed("xAI", e)


# Fields returned to a caller.  Nothing else escapes the module.
CHAT_FIELDS = ("content", "finish_reason", "model", "refusal", "tool_calls",
               "usage")


def chat(messages, model=None, max_tokens=None, temperature=None,
         tools=None, timeout=None, max_attempts=None, sleep=time.sleep):
    """One chat completion.  Bounded, trimmed, usage captured.

    https://docs.x.ai/developers/rest-api-reference/inference/chat-completions

    Parameters
    ----------
    messages : list[dict]
        role/content pairs.  At least one required.
    model : str, optional
        Model name.  Must be in MODELS.  Defaults to DEFAULT_MODEL.
    max_tokens : int, optional
        Output token cap.  Clamped to MAX_TOKENS_CAP.
    temperature : float, optional
        Sampling temperature, 0..MAX_TEMPERATURE.
    tools : list[dict], optional
        OPT-IN.  Server-side tools the model may invoke (web_search, x_search,
        code_interpreter).  Never included unless the caller passes them.
    timeout : int, optional
        Per-attempt seconds.  Defaults to XAI_TIMEOUT.
    max_attempts : int, optional
        Total attempts including the first.  Defaults to MAX_RETRIES + 1.
    sleep : callable
        Injection point for tests.

    Returns
    -------
    dict
        Trimmed to CHAT_FIELDS.  usage carries token counts and cost.

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

    body = {"model": model, "messages": list(messages)}

    if max_tokens is not None:
        body["max_completion_tokens"] = min(max_tokens, MAX_TOKENS_CAP)

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
        raise ProviderError(f"xai chat: {status} {redact(str(data))[:200]}")

    choice = _choice(data)
    msg = choice.get("message") or {}

    return {
        "content": msg.get("content"),
        "finish_reason": choice.get("finish_reason"),
        "model": (data or {}).get("model"),
        "refusal": msg.get("refusal"),
        "tool_calls": _tool_calls(msg),
        "usage": _usage(data),
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
                "POST", f"{BASE}/chat/completions", hdrs, body, timeout)
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


def _choice(data):
    """The first choice from the response, or {} if absent."""
    choices = (data or {}).get("choices") or []
    return choices[0] if choices else {}


def _tool_calls(message):
    """Tool calls from the message, trimmed to id/name/arguments."""
    raw = message.get("tool_calls")
    if not raw:
        return None
    return [{"id": tc.get("id"),
             "type": tc.get("type"),
             "name": (tc.get("function") or {}).get("name"),
             "arguments": (tc.get("function") or {}).get("arguments")}
            for tc in raw if isinstance(tc, dict)]


def _usage(data):
    """Usage and cost from the response.

    https://docs.x.ai/developers/cost-tracking
    cost_in_usd_ticks: 10_000_000_000 ticks = $1 USD.  The field covers all
    model decodes and every tool invocation within the agentic loop.
    """
    u = (data or {}).get("usage") or {}
    pd = u.get("prompt_tokens_details") or {}
    cd = u.get("completion_tokens_details") or {}
    out = {
        "prompt_tokens": u.get("prompt_tokens"),
        "completion_tokens": u.get("completion_tokens"),
        "total_tokens": u.get("total_tokens"),
        "cached_tokens": pd.get("cached_tokens"),
        "reasoning_tokens": (cd or {}).get("reasoning_tokens"),
        "cost_in_usd_ticks": u.get("cost_in_usd_ticks"),
        "num_sources_used": u.get("num_sources_used"),
    }
    sstu = (data or {}).get("server_side_tool_usage")
    if sstu:
        out["server_side_tool_usage"] = sstu
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
                   help="spend a fraction of a cent on a real completion")
    a = p.parse_args(argv)
    r = check(live=a.live)
    print(f"{'ok  ' if r.get('ok') else 'FAIL'} {r['provider']:<12} "
          f"{r.get('status') if r.get('status') is not None else '-'}"
          f"  {r['note']}")
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
