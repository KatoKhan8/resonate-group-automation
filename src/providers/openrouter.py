#!/usr/bin/env python3
"""OpenRouter fallback adapter.  TASK-305.

OpenAI-compatible Chat Completions against https://openrouter.ai/api/v1.
This is the FALLBACK for Groq.  Same model id: openai/gpt-oss-120b.

    OPENROUTER_API_KEY    the credential.  Referred to BY NAME only.

## The absence is explicit

When OPENROUTER_API_KEY is absent, every call REFUSES with a stated reason
rather than silently skipping.  A fallback that quietly is not there is the
failure class this repository keeps finding.  The operator has been told the
key is missing; this module does not pretend otherwise.

  py -3 -m src.providers.openrouter --check
"""
import argparse
import os
import time

from . import (MissingKey, ProviderError, key, load_env, ok, redact, request)

ENV_KEY = "OPENROUTER_API_KEY"
ENV_BASE = "OPENROUTER_BASE_URL"
ENV_MODEL = "OPENROUTER_MODEL"

BASE_DEFAULT = "https://openrouter.ai/api/v1"
CHAT_ENDPOINT = "/chat/completions"

DEFAULT_MODEL = "openai/gpt-oss-120b"

MODELS = (
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
)

DEFAULT_REASONING_EFFORT = "low"

RATE_LIMIT = None
RATE_LIMIT_HEADERS_OBSERVED = ()

MAX_PROMPT_CHARS = 60_000
MAX_TOKENS_CAP = 16384
DEFAULT_MAX_TOKENS = 1024
OPENROUTER_TIMEOUT = 120
MAX_RETRIES = 2
BACKOFF_BASE = 0.5

RESPONSE_FIELDS = ("content", "model", "requested_model", "finish_reason",
                   "usage", "seconds", "request_id")


# --------------------------------------------------------------- failures

class OpenRouterError(ProviderError):
    classification = "unknown"


class OpenRouterAuthFailed(OpenRouterError):
    classification = "auth"


class OpenRouterQuotaExhausted(OpenRouterError):
    classification = "quota"


class OpenRouterRateLimited(OpenRouterError):
    classification = "rate_limit"


class OpenRouterInvalidRequest(OpenRouterError):
    classification = "invalid_request"


class OpenRouterServerError(OpenRouterError):
    classification = "server_error"


class OpenRouterTimeout(OpenRouterError):
    classification = "timeout"


class OpenRouterTransportError(OpenRouterError):
    classification = "transport"


class OpenRouterMalformedResponse(OpenRouterError):
    classification = "malformed_response"


class OpenRouterUnknownFailure(OpenRouterError):
    classification = "unknown"


class OpenRouterNotConfigured(OpenRouterError):
    """The fallback key is absent.  This is NOT a transient failure."""
    classification = "not_configured"


RETRYABLE = (OpenRouterRateLimited, OpenRouterServerError,
             OpenRouterTimeout, OpenRouterTransportError)


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
    """Send one bounded prompt via OpenRouter, or refuse if unconfigured.

    When OPENROUTER_API_KEY is absent, this raises OpenRouterNotConfigured
    BEFORE any network call.  A fallback that silently skips when its key is
    missing reports a failure as a success, which is the failure class this
    repository keeps finding.
    """
    # Check configuration BEFORE anything else.  A missing key cannot
    # materialise on retry, and spending attempts on it would report a
    # configuration problem as an outage.
    try:
        key(ENV_KEY)
    except MissingKey:
        raise OpenRouterNotConfigured(
            f"openrouter: {ENV_KEY} is not configured. The fallback cannot "
            f"operate. The operator has been told; do not wait for it.")

    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("openrouter: prompt must be a non-empty string")
    if system is not None and not isinstance(system, str):
        raise ValueError("openrouter: system must be a string when given")

    size = len(prompt) + len(system or "")
    if size > MAX_PROMPT_CHARS:
        raise ValueError(
            f"openrouter: {size} characters of context exceeds the bound of "
            f"{MAX_PROMPT_CHARS}. Refusing rather than truncating")

    model = model or configured_model()
    if model not in MODELS:
        raise ValueError(
            f"openrouter: {model!r} is not in the allowlist. "
            f"Choose from: {', '.join(MODELS)}")

    if not isinstance(temperature, (int, float)) or not 0 <= temperature <= 2:
        raise ValueError(
            f"openrouter: temperature {temperature!r} out of range 0..2")

    reasoning_effort = reasoning_effort or DEFAULT_REASONING_EFFORT
    if reasoning_effort not in ("low", "medium", "high"):
        raise ValueError(
            f"openrouter: reasoning_effort {reasoning_effort!r} not in "
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
    }

    status, data, seconds = _send(
        body,
        timeout=min(int(timeout or OPENROUTER_TIMEOUT), OPENROUTER_TIMEOUT),
        max_attempts=max(1, min(int(max_attempts or MAX_RETRIES + 1),
                                MAX_RETRIES + 1)),
        sleep=sleep)

    result = _trim(status, data, seconds, model)

    # Ledger the call with actual usage.
    _ledger(client or "unattributed", model, result)

    return result


def _ledger(client, model, result):
    from .. import spendledger
    usage = result.get("usage") or {}
    spendledger.record(
        client=client,
        provider="openrouter",
        call=f"complete:{model}",
        expected_cost=0,
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        total_tokens=usage.get("total_tokens"),
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
            raise OpenRouterUnknownFailure(
                f"openrouter: unexpected {type(e).__name__}: "
                f"{redact(str(e))[:200]}") from None
        else:
            seconds = round(time.monotonic() - started, 3)
            if ok(status):
                return status, data, seconds
            last = _http_failure(status, data)

        if not isinstance(last, RETRYABLE) or attempt >= max_attempts - 1:
            raise last
        sleep(BACKOFF_BASE * (2 ** attempt))

    raise last if last else OpenRouterUnknownFailure(
        "openrouter: the retry loop ended with no outcome")


def _transport_failure(exc):
    text = redact(str(exc))
    low = text.lower()
    if "timeout" in low or "timed out" in low:
        return OpenRouterTimeout(
            f"openrouter: the call did not return: {text[:200]}")
    return OpenRouterTransportError(
        f"openrouter: the endpoint was not reached: {text[:200]}")


def _http_failure(status, data):
    note = redact(str(data))[:200]
    code, message = _error_code(data)
    said = f"{code} {message}".lower()

    quota_words = ("insufficient balance", "quota", "daily limit",
                   "exceeded", "recharge", "no remaining")
    quota = any(word in said for word in quota_words)

    if status in (401, 403):
        return OpenRouterAuthFailed(
            f"openrouter: {ENV_KEY} was rejected ({status}): {note}")
    if status == 402 or (quota and status in (429, 400)):
        return OpenRouterQuotaExhausted(
            f"openrouter: the plan has no budget left ({status}): {note}")
    if status == 429:
        return OpenRouterRateLimited(
            f"openrouter: rate limited ({status}): {note}")
    if status is not None and 400 <= status < 500:
        return OpenRouterInvalidRequest(
            f"openrouter: the request was refused ({status}): {note}")
    if status is not None and status >= 500:
        return OpenRouterServerError(
            f"openrouter: the endpoint faulted ({status}): {note}")
    return OpenRouterUnknownFailure(f"openrouter: answered {status}: {note}")


def _error_code(data):
    if not isinstance(data, dict):
        return "", ""
    err = data.get("error")
    if not isinstance(err, dict):
        return "", str(data.get("message") or "")
    return str(err.get("code") or ""), str(err.get("message") or "")


def _trim(status, data, seconds, requested):
    if not isinstance(data, dict):
        raise OpenRouterMalformedResponse(
            f"openrouter: answered {status} with a body that is not an object "
            f"({type(data).__name__})")

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenRouterMalformedResponse(
            f"openrouter: answered {status} with no `choices`")

    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message")
    message = message if isinstance(message, dict) else {}
    content = message.get("content")
    finish = first.get("finish_reason")

    if not isinstance(content, str) or not content.strip():
        raise OpenRouterMalformedResponse(
            f"openrouter: answered {status} with an empty completion "
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
    return {
        "prompt_tokens": u.get("prompt_tokens"),
        "completion_tokens": u.get("completion_tokens"),
        "total_tokens": u.get("total_tokens"),
    }


# --------------------------------------------------------------- health

def check(live=False):
    if not live:
        try:
            key(ENV_KEY)
        except MissingKey as e:
            return {"provider": "openrouter", "ok": False, "status": None,
                    "classification": "not_configured",
                    "note": redact(str(e))[:120]}
        return {"provider": "openrouter", "ok": None, "status": None,
                "skipped": True,
                "note": f"{ENV_KEY} configured, model {configured_model()}, "
                        f"no call made (--live to spend a token)"}
    try:
        status, data, seconds = _send(
            {"model": configured_model(),
             "messages": [{"role": "user", "content": "ping"}],
             "max_tokens": 1, "temperature": 0, "stream": False},
            timeout=OPENROUTER_TIMEOUT, max_attempts=MAX_RETRIES + 1,
            sleep=time.sleep)
    except OpenRouterError as e:
        return {"provider": "openrouter", "ok": False, "status": None,
                "classification": e.classification,
                "note": redact(str(e))[:120]}
    except MissingKey as e:
        return {"provider": "openrouter", "ok": False, "status": None,
                "classification": "auth", "note": redact(str(e))[:120]}
    served = data.get("model") if isinstance(data, dict) else None
    return {"provider": "openrouter", "ok": ok(status), "status": status,
            "classification": None,
            "note": f"requested {configured_model()}, served {served}, "
                    f"{int(seconds * 1000)}ms"}


def main(argv=None):
    p = argparse.ArgumentParser(prog="py -3 -m src.providers.openrouter")
    p.add_argument("--check", action="store_true")
    p.add_argument("--live", action="store_true",
                   help="spend one token against the real endpoint")
    a = p.parse_args(argv)
    r = check(live=a.live)
    print(f"{'ok  ' if r.get('ok') else 'FAIL' if r.get('ok') is False else 'skip'} "
          f"{r['provider']:<12} "
          f"{r.get('status') if r.get('status') is not None else '-'}  "
          f"{r['note']}")
    return 0 if r.get("ok") or r.get("skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
