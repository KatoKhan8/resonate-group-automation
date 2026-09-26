#!/usr/bin/env python3
"""Groq adapter.  TASK-305.

OpenAI-compatible chat completions against https://api.groq.com/openai/v1.
The primary reasoning provider, with OpenRouter as the fallback.

    GROQ_API_KEY     the credential.  Referred to BY NAME only, never printed,
                     never stored on an object, never placed in an exception.
    GROQ_BASE_URL    override the base.  Falls back to BASE_DEFAULT.
    GROQ_MODEL       override the model.  Falls back to DEFAULT_MODEL.

Every call is ledgered through `spendledger`.  Model calls were unledgered
across the whole system before this adapter; `glm.py` has zero spendledger
references.  The ledger row carries actual token usage from the response,
not an estimate.

## The model

`openai/gpt-oss-120b` is an open-weight model hosted on Groq.  It supports
the `reasoning_effort` parameter (low, medium, high) which controls how many
reasoning tokens the model generates before answering.

## Concurrency

The task specifies concurrency 50.  Groq's rate limits are not publicly
documented for this model, so `RATE_LIMIT` is `None` (unknown, measured
absence) rather than a guessed number.  The probe measures what actually
happens at 50 concurrent calls.

## Failure classification

Same shape as `glm.py`: every failure raises a subclass of `GroqError`
carrying `.classification`.  Callers switch on the classification, never
on the message.

  py -3 -m src.providers.groq --check          configuration only, no call
  py -3 -m src.providers.groq --check --live   one real token
"""
import argparse
import os
import time

from . import (MissingKey, ProviderError, key, load_env, ok, redact, request)
from .. import spendledger

ENV_KEY = "GROQ_API_KEY"
ENV_BASE = "GROQ_BASE_URL"
ENV_MODEL = "GROQ_MODEL"

BASE_DEFAULT = "https://api.groq.com/openai/v1"
CHAT_ENDPOINT = "/chat/completions"

DEFAULT_MODEL = "openai/gpt-oss-120b"

# What the endpoint serves for each requested id.  Groq has not been probed
# live yet (GROQ_API_KEY is not in config/.env as of 2026-09-25), so this is
# the requested model only.  A live probe would fill this in; for now, the
# allowlist is the one model the task specifies.
SERVES = {
    "openai/gpt-oss-120b": "openai/gpt-oss-120b",
}
MODELS = tuple(SERVES)

# No rate-limit headers have been observed; the endpoint has not been reached.
RATE_LIMIT_HEADERS_OBSERVED = ()

# Rate limit: UNKNOWN, not guessed.  The task says "measure the rate limit,
# never guess it, and record the measured value.  RATE_LIMIT = None meaning
# unknown is an acceptable answer; a guessed number is not."
RATE_LIMIT = None

# Bounds.
MAX_PROMPT_CHARS = 60_000
MAX_TOKENS_CAP = 32768
DEFAULT_MAX_TOKENS = 1024
GROQ_TIMEOUT = 180
MAX_RETRIES = 2
BACKOFF_BASE = 0.5

# Reasoning effort: low, medium, or high.  Default is low per the task.
REASONING_EFFORTS = ("low", "medium", "high")
DEFAULT_REASONING_EFFORT = "low"

# Fields returned to a caller.
RESPONSE_FIELDS = ("content", "model", "requested_model", "finish_reason",
                   "usage", "seconds", "request_id", "reasoning_effort")

# The client used for ledger rows when no client context is supplied.
# Model calls are often made outside a client context (system-level review,
# probe, etc.); this default keeps them ledgered rather than refused.
DEFAULT_LEDGER_CLIENT = "system"


# --------------------------------------------------------------- failures

class GroqError(ProviderError):
    """A Groq call failed.  The subclass says how, and `.classification` is
    the machine-readable form of that."""
    classification = "unknown"


class GroqAuthFailed(GroqError):
    classification = "auth"


class GroqQuotaExhausted(GroqError):
    classification = "quota"


class GroqRateLimited(GroqError):
    classification = "rate_limit"


class GroqInvalidRequest(GroqError):
    classification = "invalid_request"


class GroqServerError(GroqError):
    classification = "server_error"


class GroqTimeout(GroqError):
    classification = "timeout"


class GroqTransportError(GroqError):
    classification = "transport"


class GroqMalformedResponse(GroqError):
    classification = "malformed_response"


class GroqUnknownFailure(GroqError):
    classification = "unknown"


RETRYABLE = (GroqRateLimited, GroqServerError, GroqTimeout, GroqTransportError)

CLASSIFICATIONS = ("auth", "quota", "rate_limit", "invalid_request",
                   "server_error", "timeout", "transport",
                   "malformed_response", "unknown")


# --------------------------------------------------------------- config

def base_url():
    load_env()
    return (os.environ.get(ENV_BASE) or BASE_DEFAULT).strip().rstrip("/")


def configured_model():
    load_env()
    return (os.environ.get(ENV_MODEL) or "").strip() or DEFAULT_MODEL


def headers():
    """Bearer auth.  The value is built here and never held anywhere else."""
    return {"Authorization": f"Bearer {key(ENV_KEY)}",
            "Content-Type": "application/json"}


# --------------------------------------------------------------- the call

def complete(prompt, system=None, model=None, max_tokens=None,
             temperature=0, timeout=None, max_attempts=None,
             sleep=time.sleep, reasoning_effort=None,
             client=None):
    """Send one bounded prompt.  Return a trimmed dict, or raise a GroqError.

    Every successful call is ledgered through `spendledger` with actual token
    usage from the response.  A call that skips the ledger is invisible to
    the spend audit.

    Parameters
    ----------
    prompt : str
        The user turn.  Refused above MAX_PROMPT_CHARS rather than truncated.
    system : str, optional
        A system turn placed before the prompt.
    model : str, optional
        Must be in MODELS.  Defaults to GROQ_MODEL, then DEFAULT_MODEL.
    max_tokens : int, optional
        Output cap.  Defaults to DEFAULT_MAX_TOKENS, clamped to MAX_TOKENS_CAP.
        Always sent, so a runaway generation cannot happen.
    temperature : float
        0 by default.
    timeout : int, optional
        Per-attempt seconds, clamped to GROQ_TIMEOUT.
    max_attempts : int, optional
        Total attempts including the first, clamped to MAX_RETRIES + 1.
    sleep : callable
        Backoff injection point.
    reasoning_effort : str, optional
        "low", "medium", or "high".  Defaults to DEFAULT_REASONING_EFFORT.
    client : str, optional
        The client for ledger rows.  Defaults to DEFAULT_LEDGER_CLIENT.

    Returns
    -------
    dict
        Keys exactly RESPONSE_FIELDS.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("groq: prompt must be a non-empty string")
    if system is not None and not isinstance(system, str):
        raise ValueError("groq: system must be a string when given")

    size = len(prompt) + len(system or "")
    if size > MAX_PROMPT_CHARS:
        raise ValueError(
            f"groq: {size} characters of context exceeds the bound of "
            f"{MAX_PROMPT_CHARS}. Refusing rather than truncating")

    model = model or configured_model()
    if model not in MODELS:
        raise ValueError(
            f"groq: {model!r} is not in the allowlist. "
            f"Choose from: {', '.join(MODELS)}")

    if not isinstance(temperature, (int, float)) or not 0 <= temperature <= 1:
        raise ValueError(f"groq: temperature {temperature!r} out of range 0..1")

    reasoning_effort = reasoning_effort or DEFAULT_REASONING_EFFORT
    if reasoning_effort not in REASONING_EFFORTS:
        raise ValueError(
            f"groq: reasoning_effort {reasoning_effort!r} not in "
            f"{REASONING_EFFORTS}")

    client = client or DEFAULT_LEDGER_CLIENT

    # BUDGET CHECK BEFORE THE CALL.  An ungoverned client ({}) means no
    # ceilings apply; the call is still ledgered.
    try:
        spendledger.check(client, {}, 0, provider="groq")
    except spendledger.BudgetExceeded:
        raise

    messages = ([{"role": "system", "content": system}] if system else [])
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": model,
        "messages": messages,
        "max_tokens": min(int(max_tokens or DEFAULT_MAX_TOKENS),
                          MAX_TOKENS_CAP),
        "temperature": temperature,
        "stream": False,
        "reasoning_effort": reasoning_effort,
    }

    status, data, seconds = _send(
        body,
        timeout=min(int(timeout or GROQ_TIMEOUT), GROQ_TIMEOUT),
        max_attempts=max(1, min(int(max_attempts or MAX_RETRIES + 1),
                                MAX_RETRIES + 1)),
        sleep=sleep)

    result = _trim(status, data, seconds, model, reasoning_effort)

    # LEDGER THE CALL with actual usage from the response.  A call that
    # skips the ledger is invisible to the spend audit.
    usage = result.get("usage") or {}
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    metadata = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": usage.get("total_tokens"),
        "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
        "served_model": result.get("model"),
        "reasoning_effort": reasoning_effort,
        "latency_seconds": seconds,
    }
    # expected_cost is 0 because Groq pricing for this model is not yet
    # known.  The token counts are recorded in metadata for later costing.
    # An invented cost is worse than an absent one.
    spendledger.record(client, "groq", "complete", 0, unit="microusd",
                       metadata=metadata)

    return result


def _send(body, timeout, max_attempts, sleep):
    """POST with bounded retry on transient failures only."""
    hdrs = headers()
    url = f"{base_url()}{CHAT_ENDPOINT}"

    last = None
    for attempt in range(max_attempts):
        started = time.monotonic()
        try:
            status, data = request("POST", url, hdrs, body, timeout)
        except MissingKey:
            raise
        except ProviderError as e:
            last = _transport_failure(e)
        except Exception as e:                                   # noqa: BLE001
            raise GroqUnknownFailure(
                f"groq: unexpected {type(e).__name__}: "
                f"{redact(str(e))[:200]}") from None
        else:
            seconds = round(time.monotonic() - started, 3)
            if ok(status):
                return status, data, seconds
            last = _http_failure(status, data)

        if not isinstance(last, RETRYABLE) or attempt >= max_attempts - 1:
            raise last
        sleep(BACKOFF_BASE * (2 ** attempt))

    raise last if last else GroqUnknownFailure(
        "groq: the retry loop ended with no outcome")


def _transport_failure(exc):
    text = redact(str(exc))
    low = text.lower()
    if "timeout" in low or "timed out" in low:
        return GroqTimeout(f"groq: the call did not return: {text[:200]}")
    return GroqTransportError(f"groq: the endpoint was not reached: {text[:200]}")


QUOTA_WORDS = ("insufficient balance", "balance is insufficient", "quota",
               "daily limit", "exceeded your current", "recharge",
               "arrears", "no remaining", "rate limit exceeded")


def _http_failure(status, data):
    note = redact(str(data))[:200]
    code, message = _error_code(data)
    said = f"{code} {message}".lower()

    quota = any(word in said for word in QUOTA_WORDS)

    if status in (401, 403):
        return GroqAuthFailed(
            f"groq: {ENV_KEY} was rejected ({status}): {note}")
    if status == 402 or (quota and status in (429, 400)):
        return GroqQuotaExhausted(f"groq: the plan has no budget left "
                                  f"({status}): {note}")
    if status == 429:
        return GroqRateLimited(f"groq: rate limited ({status}): {note}")
    if status is not None and 400 <= status < 500:
        return GroqInvalidRequest(
            f"groq: the request was refused ({status}): {note}")
    if status is not None and status >= 500:
        return GroqServerError(f"groq: the endpoint faulted ({status}): {note}")
    return GroqUnknownFailure(f"groq: answered {status}: {note}")


def _error_code(data):
    if not isinstance(data, dict):
        return "", ""
    err = data.get("error")
    if not isinstance(err, dict):
        return "", str(data.get("message") or "")
    return str(err.get("code") or ""), str(err.get("message") or "")


def _trim(status, data, seconds, requested, reasoning_effort):
    if not isinstance(data, dict):
        raise GroqMalformedResponse(
            f"groq: answered {status} with a body that is not an object "
            f"({type(data).__name__})")

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise GroqMalformedResponse(
            f"groq: answered {status} with no `choices`")

    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message")
    message = message if isinstance(message, dict) else {}
    content = message.get("content")
    finish = first.get("finish_reason")

    if not isinstance(content, str) or not content.strip():
        raise GroqMalformedResponse(
            f"groq: answered {status} with an empty completion "
            f"(finish_reason={finish!r})")

    return {
        "content": content,
        "model": data.get("model"),
        "requested_model": requested,
        "finish_reason": finish,
        "usage": _usage(data),
        "seconds": seconds,
        "request_id": data.get("request_id") or data.get("id"),
        "reasoning_effort": reasoning_effort,
    }


def _usage(data):
    u = data.get("usage")
    u = u if isinstance(u, dict) else {}
    prompt_details = u.get("prompt_tokens_details")
    prompt_details = prompt_details if isinstance(prompt_details, dict) else {}
    out_details = u.get("completion_tokens_details")
    out_details = out_details if isinstance(out_details, dict) else {}
    return {
        "prompt_tokens": u.get("prompt_tokens"),
        "completion_tokens": u.get("completion_tokens"),
        "total_tokens": u.get("total_tokens"),
        "reasoning_tokens": out_details.get("reasoning_tokens"),
        "cached_tokens": prompt_details.get("cached_tokens"),
    }


# --------------------------------------------------------------- health

def check(live=False):
    """Configuration readiness by default; one real token if live."""
    if not live:
        try:
            key(ENV_KEY)
        except MissingKey as e:
            return {"provider": "groq", "ok": False, "status": None,
                    "note": redact(str(e))[:120]}
        return {"provider": "groq", "ok": None, "status": None, "skipped": True,
                "note": f"{ENV_KEY} configured, model {configured_model()}, "
                        f"no call made (--live to spend a token)"}
    try:
        status, data, seconds = _send(
            {"model": configured_model(),
             "messages": [{"role": "user", "content": "ping"}],
             "max_tokens": 1, "temperature": 0, "stream": False,
             "reasoning_effort": DEFAULT_REASONING_EFFORT},
            timeout=GROQ_TIMEOUT, max_attempts=MAX_RETRIES + 1,
            sleep=time.sleep)
    except GroqError as e:
        return {"provider": "groq", "ok": False, "status": None,
                "classification": e.classification,
                "note": redact(str(e))[:120]}
    except MissingKey as e:
        return {"provider": "groq", "ok": False, "status": None,
                "classification": "auth", "note": redact(str(e))[:120]}
    served = data.get("model") if isinstance(data, dict) else None
    return {"provider": "groq", "ok": ok(status), "status": status,
            "classification": None,
            "note": f"requested {configured_model()}, served {served}, "
                    f"{int(seconds * 1000)}ms"}


def main(argv=None):
    p = argparse.ArgumentParser(prog="py -3 -m src.providers.groq")
    p.add_argument("--check", action="store_true")
    p.add_argument("--live", action="store_true")
    a = p.parse_args(argv)
    r = check(live=a.live)
    print(f"{'ok  ' if r.get('ok') else 'FAIL' if r.get('ok') is False else 'skip'} "
          f"{r['provider']:<6} "
          f"{r.get('status') if r.get('status') is not None else '-'}  "
          f"{r['note']}")
    return 0 if r.get("ok") or r.get("skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
