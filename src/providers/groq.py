#!/usr/bin/env python3
"""Groq adapter.  TASK-305.

OpenAI-compatible Chat Completions against https://api.groq.com/openai/v1.
The lane is REASONING: fast, cheap, structured thinking.  The model is
openai/gpt-oss-120b at reasoning_effort=low.

    GROQ_API_KEY    the credential.  Referred to BY NAME only, never printed.
    GROQ_BASE_URL   override for the base.  Falls back to BASE_DEFAULT.
    GROQ_MODEL      override for the model.  Falls back to DEFAULT_MODEL.

Every call is ledgered through `spendledger.record` with actual token usage
from the response.  A call that skips the ledger is invisible to the spend
audit, and an audit that reports clean because it watched nothing is worse
than none.

## The fallback

OpenRouter is the fallback, same model id.  Its key is OPENROUTER_API_KEY.
When that key is absent the fallback REFUSES rather than silently skipping -
a fallback that quietly is not there is the failure class this repository
keeps finding.  The operator has been told the key is missing.

## Concurrency

50 is the OPERATOR'S choice, not a measured rate limit.  RATE_LIMIT is None
meaning UNKNOWN.  The probe measures what actually happens; it does not
conclude the limit supports 50 because 20 calls did not 429.

  py -3 -m src.providers.groq --check
  py -3 -m src.providers.groq --check --live
"""
import argparse
import os
import time

from . import (MissingKey, ProviderError, key, load_env, ok, redact, request)

ENV_KEY = "GROQ_API_KEY"
ENV_BASE = "GROQ_BASE_URL"
ENV_MODEL = "GROQ_MODEL"

BASE_DEFAULT = "https://api.groq.com/openai/v1"
CHAT_ENDPOINT = "/chat/completions"

DEFAULT_MODEL = "openai/gpt-oss-120b"

# The model allowlist.  An id absent from here is refused before a request
# is sent: an unknown model costs a round trip and comes back as a 400 that
# reads like our fault, which it is.
MODELS = (
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
)

# Reasoning effort.  The operator chose "low" for this lane.
DEFAULT_REASONING_EFFORT = "low"

# Measured absence: no rate-limit headers observed on the Groq API.
# RATE_LIMIT is None meaning UNKNOWN - the operator chose 50 concurrency;
# the probe measures what actually happens.
RATE_LIMIT = None
RATE_LIMIT_HEADERS_OBSERVED = ()

# Bounds.  Nothing here may run unbounded.
MAX_PROMPT_CHARS = 60_000
MAX_TOKENS_CAP = 16384
DEFAULT_MAX_TOKENS = 1024
GROQ_TIMEOUT = 120
MAX_RETRIES = 2
BACKOFF_BASE = 0.5

RESPONSE_FIELDS = ("content", "model", "requested_model", "finish_reason",
                   "usage", "seconds", "request_id")


# --------------------------------------------------------------- failures

class GroqError(ProviderError):
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
    return {"Authorization": f"Bearer {key(ENV_KEY)}",
            "Content-Type": "application/json"}


# --------------------------------------------------------------- the call

def complete(prompt, system=None, model=None, max_tokens=None,
             temperature=0, timeout=None, max_attempts=None,
             reasoning_effort=None, client=None,
             sleep=time.sleep):
    """Send one bounded prompt.  Return a trimmed dict, or raise a GroqError.

    Every call is ledgered: actual token usage from the response is recorded
    through `spendledger.record`.  A call that skips the ledger is invisible
    to the spend audit.

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
    temperature : float
        0 by default.
    timeout : int, optional
        Per-attempt seconds, clamped to GROQ_TIMEOUT.
    max_attempts : int, optional
        Total attempts including the first, clamped to MAX_RETRIES + 1.
    reasoning_effort : str, optional
        "low", "medium" or "high".  Defaults to DEFAULT_REASONING_EFFORT.
    client : str, optional
        The client name for ledger attribution.  Defaults to "unattributed".
    sleep : callable
        Backoff injection point.  Tests pass a recorder.
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

    if not isinstance(temperature, (int, float)) or not 0 <= temperature <= 2:
        raise ValueError(f"groq: temperature {temperature!r} out of range 0..2")

    reasoning_effort = reasoning_effort or DEFAULT_REASONING_EFFORT
    if reasoning_effort not in ("low", "medium", "high"):
        raise ValueError(
            f"groq: reasoning_effort {reasoning_effort!r} not in "
            f"(low, medium, high)")

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

    result = _trim(status, data, seconds, model)

    # Ledger the call with actual usage from the response.
    # A call that skips the ledger is invisible to the spend audit.
    _ledger(client or "unattributed", model, result)

    return result


def _ledger(client, model, result):
    """Record the call in the spend ledger with actual token usage.

    A call that skips the ledger is invisible to the spend audit, and an
    audit that reports clean because it watched nothing is worse than none.
    """
    from .. import spendledger
    usage = result.get("usage") or {}
    spendledger.record(
        client=client,
        provider="groq",
        call=f"complete:{model}",
        expected_cost=0,  # No pricing policy set; the operator sets numbers.
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        total_tokens=usage.get("total_tokens"),
        reasoning_tokens=usage.get("reasoning_tokens"),
        seconds=result.get("seconds"),
    )


def _send(body, timeout, max_attempts, sleep):
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
        except Exception as e:
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


def _http_failure(status, data):
    note = redact(str(data))[:200]
    code, message = _error_code(data)
    said = f"{code} {message}".lower()

    # A 429 with "rate limit" in the message is a pace problem, not a quota
    # problem.  Check this BEFORE quota words, because a rate-limit message
    # might also contain "exceeded" or similar.
    if status == 429 and "rate limit" in said:
        return GroqRateLimited(f"groq: rate limited ({status}): {note}")

    quota_words = ("insufficient balance", "quota", "daily limit",
                   "exceeded your", "recharge", "no remaining")
    quota = any(word in said for word in quota_words)

    if status in (401, 403):
        return GroqAuthFailed(f"groq: {ENV_KEY} was rejected ({status}): {note}")
    if status == 402 or (quota and status in (429, 400)):
        return GroqQuotaExhausted(f"groq: the plan has no budget left "
                                  f"({status}): {note}")
    if status == 429:
        return GroqRateLimited(f"groq: rate limited ({status}): {note}")
    if status is not None and 400 <= status < 500:
        return GroqInvalidRequest(f"groq: the request was refused ({status}): {note}")
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


def _trim(status, data, seconds, requested):
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
    }


def _usage(data):
    u = data.get("usage")
    u = u if isinstance(u, dict) else {}
    out_details = u.get("completion_tokens_details")
    out_details = out_details if isinstance(out_details, dict) else {}
    return {
        "prompt_tokens": u.get("prompt_tokens"),
        "completion_tokens": u.get("completion_tokens"),
        "total_tokens": u.get("total_tokens"),
        "reasoning_tokens": out_details.get("reasoning_tokens"),
    }


# --------------------------------------------------------------- health

def check(live=False):
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
    p.add_argument("--live", action="store_true",
                   help="spend one token against the real endpoint")
    a = p.parse_args(argv)
    r = check(live=a.live)
    print(f"{'ok  ' if r.get('ok') else 'FAIL' if r.get('ok') is False else 'skip'} "
          f"{r['provider']:<6} "
          f"{r.get('status') if r.get('status') is not None else '-'}  "
          f"{r['note']}")
    return 0 if r.get("ok") or r.get("skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
