#!/usr/bin/env python3
"""OpenRouter adapter.  TASK-305.

OpenAI-compatible endpoint at https://openrouter.ai/api/v1.  The FALLBACK
reasoning provider for this estate; Groq is the primary.

    OPENROUTER_API_KEY   the credential.  Referred to BY NAME only.
    LLM_API_KEY          legacy spelling, still read as a fallback.
    LLM_BASE_URL         legacy base override.
    OPENROUTER_BASE_URL  canonical base override.  Falls back to BASE_DEFAULT.

Same contract as `groq.complete` and `glm.complete`:

    complete(prompt, system=None, model=None, max_tokens=None,
             temperature=0, timeout=None, max_attempts=None,
             sleep=time.sleep)

## THE KEY IS NOT SET, measured 2026-09-27

`OPENROUTER_API_KEY` is NOT SET in `config/.env` under any spelling.
`LLM_API_KEY` is also NOT SET.  This adapter CANNOT make a call today.

A fallback that quietly is not there is the failure class this repository
keeps finding.  So `complete()` raises `MissingKey` with a clear message
when no credential is configured, rather than returning a default or
silently succeeding.  The operator has been told; do not fake it.

  py -3 -m src.providers.openrouter --check          configuration only
  py -3 -m src.providers.openrouter --check --live   one real token
"""
import argparse
import os
import time

from . import (MissingKey, ProviderError, key, load_env, ok, redact, request,
               model_key)

ENV_BASE = "OPENROUTER_BASE_URL"
LEGACY_BASE = "LLM_BASE_URL"

BASE_DEFAULT = "https://openrouter.ai/api/v1"
CHAT_ENDPOINT = "/chat/completions"

DEFAULT_MODEL = "openai/gpt-oss-120b"

MODELS = (
    "openai/gpt-oss-120b",
)

# Bounds.  Nothing here may run unbounded.
MAX_PROMPT_CHARS = 60_000
MAX_TOKENS_CAP = 32768
DEFAULT_MAX_TOKENS = 1024
OPENROUTER_TIMEOUT = 180
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


RETRYABLE = (OpenRouterRateLimited, OpenRouterServerError,
             OpenRouterTimeout, OpenRouterTransportError)


# --------------------------------------------------------------- config

def base_url():
    load_env()
    return (os.environ.get(ENV_BASE)
            or os.environ.get(LEGACY_BASE)
            or BASE_DEFAULT).strip().rstrip("/")


def configured_model():
    return DEFAULT_MODEL


def headers():
    """Bearer auth.  Reads through `model_key` which checks both spellings."""
    value, _name = model_key("openrouter")
    return {"Authorization": f"Bearer {value}",
            "Content-Type": "application/json"}


# --------------------------------------------------------------- the call

def complete(prompt, system=None, model=None, max_tokens=None,
             temperature=0, timeout=None, max_attempts=None,
             sleep=time.sleep, ledger_client=None, config=None):
    """Send one bounded prompt.  Return a trimmed dict, or raise.

    Raises `MissingKey` when no credential is configured.  This is NOT a
    silent skip: a fallback that quietly is not there is the failure class
    this repository keeps finding.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("openrouter: prompt must be a non-empty string")
    if system is not None and not isinstance(system, str):
        raise ValueError("openrouter: system must be a string when given")

    size = len(prompt) + len(system or "")
    if size > MAX_PROMPT_CHARS:
        raise ValueError(
            f"openrouter: {size} characters exceeds the bound of "
            f"{MAX_PROMPT_CHARS}. Refusing rather than truncating")

    model = model or configured_model()
    if model not in MODELS:
        raise ValueError(
            f"openrouter: {model!r} is not in the allowlist. "
            f"Choose from: {', '.join(MODELS)}")

    if not isinstance(temperature, (int, float)) or not 0 <= temperature <= 1:
        raise ValueError(
            f"openrouter: temperature {temperature!r} out of range 0..1")

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
        provider="openrouter", call=f"complete:{model}",
        unit="microusd")

    try:
        status, data, seconds = _send(
            body,
            timeout=min(int(timeout or OPENROUTER_TIMEOUT),
                        OPENROUTER_TIMEOUT),
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


QUOTA_WORDS = ("insufficient balance", "balance is insufficient", "quota",
               "daily limit", "exceeded your current", "recharge",
               "no remaining", "credits")


def _http_failure(status, data):
    note = redact(str(data))[:200]
    code, message = _error_code(data)
    said = f"{code} {message}".lower()

    quota = any(word in said for word in QUOTA_WORDS)

    if status in (401, 403):
        return OpenRouterAuthFailed(
            f"openrouter: credential was rejected ({status}): {note}")
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
    return OpenRouterUnknownFailure(
        f"openrouter: answered {status}: {note}")


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
            f"openrouter: answered {status} with a body that is not an "
            f"object ({type(data).__name__})")

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
    u = data.get("usage")
    u = u if isinstance(u, dict) else {}
    return {
        "prompt_tokens": u.get("prompt_tokens"),
        "completion_tokens": u.get("completion_tokens"),
        "total_tokens": u.get("total_tokens"),
    }


# --------------------------------------------------------------- health

def check(live=False):
    """Configuration readiness by default; one real token if live."""
    if not live:
        try:
            model_key("openrouter")
        except MissingKey as e:
            return {"provider": "openrouter", "ok": False, "status": None,
                    "note": redact(str(e))[:120]}
        return {"provider": "openrouter", "ok": None, "status": None,
                "skipped": True,
                "note": f"OpenRouter configured, model {configured_model()}, "
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
          f"{r['provider']:<10} "
          f"{r.get('status') if r.get('status') is not None else '-'}  "
          f"{r['note']}")
    return 0 if r.get("ok") or r.get("skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
