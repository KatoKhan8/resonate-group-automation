#!/usr/bin/env python3
"""Groq adapter.  TASK-305.

OpenAI-compatible endpoint at https://api.groq.com/openai/v1.  The primary
reasoning provider for this estate, with OpenRouter as the fallback.

    GROQ_API_KEY     the credential.  Referred to BY NAME only, never printed.
    GROQ_BASE_URL    override for the base.  Falls back to BASE_DEFAULT.
    GROQ_MODEL       override for the model.  Falls back to DEFAULT_MODEL.

One outward function, `complete(prompt)`.  Same shape as `glm.complete`:

    complete(prompt, system=None, model=None, max_tokens=None,
             temperature=0, timeout=None, max_attempts=None,
             sleep=time.sleep)

Every call is ledgered through `spendledger`:

    - `reserve()` BEFORE the provider is reached, so the ceiling check
      happens before any credit is spent.
    - `settle()` after the response, with actual token counts from the
      provider - not an estimate.
    - `release()` on any failure, so the hold does not leak.

A prompt above `MAX_PROMPT_CHARS` is REFUSED, never truncated.
`max_tokens` is always sent so a runaway generation cannot happen.
`model` must be in `MODELS`.

The fallback to OpenRouter is EXPLICIT: if the OpenRouter key is absent,
`fallback_complete()` raises `MissingKey` rather than silently succeeding
with nothing.  A fallback that quietly is not there is the failure class
this repository keeps finding.

  py -3 -m src.providers.groq --check          configuration only
  py -3 -m src.providers.groq --check --live   one real token
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

# What this adapter may ask for.  An id absent from here is refused before a
# request is sent: an unknown model costs a round trip and comes back as a
# 400 that reads like our fault, which it is.
MODELS = (
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
)

# Measured absence: Groq returns standard OpenAI-shaped headers but no
# rate-limit headers were observed on probe.  RATE_LIMIT is None meaning
# UNKNOWN, not a guessed number.
RATE_LIMIT_HEADERS_OBSERVED = ()
RATE_LIMIT = None

# Bounds.  Nothing here may run unbounded.
MAX_PROMPT_CHARS = 60_000
MAX_TOKENS_CAP = 32768
DEFAULT_MAX_TOKENS = 1024
GROQ_TIMEOUT = 180
MAX_RETRIES = 2
BACKOFF_BASE = 0.5

RESPONSE_FIELDS = ("content", "model", "requested_model", "finish_reason",
                   "usage", "seconds", "request_id")


# --------------------------------------------------------------- failures

class GroqError(ProviderError):
    """A Groq call failed.  The subclass says how."""
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
             sleep=time.sleep, ledger_client=None, config=None):
    """Send one bounded prompt.  Return a trimmed dict, or raise a GroqError.

    Parameters match `glm.complete` exactly so callers can swap providers.
    Every call is ledgered: `spendledger.reserve` before, `settle` after.
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
        raise ValueError(
            f"groq: temperature {temperature!r} out of range 0..1")

    messages = ([{"role": "system", "content": system}] if system else [])
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": model,
        "messages": messages,
        "max_tokens": min(int(max_tokens or DEFAULT_MAX_TOKENS),
                          MAX_TOKENS_CAP),
        "temperature": temperature,
        "stream": False,
    }

    # --- spend ledger: reserve BEFORE the call ---
    spend_client = ledger_client or "unattributed"
    if config is None and ledger_client:
        try:
            from .. import clients
            config = clients.load(ledger_client)
        except Exception:                                       # noqa: BLE001
            config = {}
    spend_config = config if config is not None else {}

    from .. import modelprices, spendledger
    est_cost = modelprices.cost_micro_usd(model, {
        "prompt_tokens": len(prompt.split()) * 2,
        "completion_tokens": body["max_tokens"],
    })
    hold = spendledger.reserve(
        spend_client, spend_config, est_cost,
        provider="groq", call=f"complete:{model}",
        unit="microusd")

    try:
        status, data, seconds = _send(
            body,
            timeout=min(int(timeout or GROQ_TIMEOUT), GROQ_TIMEOUT),
            max_attempts=max(1, min(int(max_attempts or MAX_RETRIES + 1),
                                    MAX_RETRIES + 1)),
            sleep=sleep)
    except BaseException:
        spendledger.release(hold)
        raise

    try:
        result = _trim(status, data, seconds, model)
    except BaseException:
        spendledger.release(hold)
        raise

    # Settle with actual cost from the provider's usage block.
    try:
        actual_cost = modelprices.cost_micro_usd(
            model, result.get("usage") or {})
        spendledger.settle(hold, actual_cost=actual_cost)
    except Exception:                                       # noqa: BLE001
        try:
            spendledger.release(hold)
        except Exception:                                   # noqa: BLE001
            pass

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
    return GroqTransportError(
        f"groq: the endpoint was not reached: {text[:200]}")


QUOTA_WORDS = ("insufficient balance", "balance is insufficient", "quota",
               "daily limit", "exceeded your current", "recharge",
               "no remaining")


def _http_failure(status, data):
    note = redact(str(data))[:200]
    code, message = _error_code(data)
    said = f"{code} {message}".lower()

    quota = any(word in said for word in QUOTA_WORDS)

    if status in (401, 403):
        return GroqAuthFailed(
            f"groq: {ENV_KEY} was rejected ({status}): {note}")
    if status == 402 or (quota and status in (429, 400)):
        return GroqQuotaExhausted(
            f"groq: the plan has no budget left ({status}): {note}")
    if status == 429:
        return GroqRateLimited(f"groq: rate limited ({status}): {note}")
    if status is not None and 400 <= status < 500:
        return GroqInvalidRequest(
            f"groq: the request was refused ({status}): {note}")
    if status is not None and status >= 500:
        return GroqServerError(
            f"groq: the endpoint faulted ({status}): {note}")
    return GroqUnknownFailure(f"groq: answered {status}: {note}")


def _error_code(data):
    if not isinstance(data, dict):
        return "", ""
    err = data.get("error")
    if not isinstance(err, dict):
        return "", str(data.get("message") or "")
    return str(err.get("code") or ""), str(err.get("message") or "")


def _trim(status, data, seconds, requested):
    """A 2xx body into RESPONSE_FIELDS, or a stated malformed failure."""
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
            f"(finish_reason={finish!r}). Refusing rather than returning ''")

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
    """Token counts as the API reported them.  None where omitted."""
    u = data.get("usage")
    u = u if isinstance(u, dict) else {}
    return {
        "prompt_tokens": u.get("prompt_tokens"),
        "completion_tokens": u.get("completion_tokens"),
        "total_tokens": u.get("total_tokens"),
    }


# --------------------------------------------------------------- fallback

def fallback_complete(prompt, **kwargs):
    """Try Groq first; if it fails with MissingKey, try OpenRouter.

    The OpenRouter fallback REFUSES explicitly when the key is absent.
    A fallback that quietly is not there is the failure class this
    repository keeps finding.
    """
    try:
        return complete(prompt, **kwargs)
    except MissingKey:
        pass

    from . import openrouter as _openrouter
    return _openrouter.complete(prompt, **kwargs)


# --------------------------------------------------------------- health

def check(live=False):
    """Configuration readiness by default; one real token if live."""
    if not live:
        try:
            key(ENV_KEY)
        except MissingKey as e:
            return {"provider": "groq", "ok": False, "status": None,
                    "note": redact(str(e))[:120]}
        return {"provider": "groq", "ok": None, "status": None,
                "skipped": True,
                "note": f"{ENV_KEY} configured, model {configured_model()}, "
                        f"no call made (--live to spend a token)"}
    try:
        status, data, seconds = _send(
            {"model": configured_model(),
             "messages": [{"role": "user", "content": "ping"}],
             "max_tokens": 1, "temperature": 0, "stream": False},
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
