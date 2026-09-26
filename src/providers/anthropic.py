#!/usr/bin/env python3
"""Anthropic (Claude) adapter.  TASK-340.

Messages API against https://api.anthropic.com/v1/messages.  Prompt caching
via `cache_control: {"type": "ephemeral"}` on the stable preamble messages.
Batch submission via `/v1/messages/batches`.

    ANTHROPIC_API_KEY   the credential.  Referred to BY NAME only, never
                        printed, never stored on an object.
    ANTHROPIC_BASE_URL  optional override for the API root.
    ANTHROPIC_MODEL     model id.  Falls back to DEFAULT_MODEL.

This adapter is the seam for Claude models.  The OpenAI-compatible model in
`llm.py` speaks a different shape; this one speaks Anthropic's native format,
which is the only way to express prompt caching and batch submission.

## Prompt caching

Anthropic's prompt caching marks individual messages with
`cache_control: {"type": "ephemeral"}`.  The first call writes the cache
(cache_creation_input_tokens); subsequent calls read it
(cache_read_input_tokens) at 90% less than a normal input.

The stable cohort preamble is the ideal cache candidate: ~1,439 words of
system text retransmitted on every lead.  With caching on, that text is
paid for once (at 1.25x) and then read at 0.1x for every subsequent call.

Caching is OFF by default.  A caller passes `cache=True` to opt in.

## Batch submission

`complete_batch` submits many leads in one request via the Message Batches
API.  The batch is created, polled until done, and results returned in the
same order as the inputs.

## Failure classification

Same hierarchy as every other adapter in this repository.  See `glm.py` for
the full argument; the classifications are identical:

    auth                401/403.        NEVER retried.
    quota               balance gone.   NEVER retried.
    rate_limit          429 pace.       Retried.
    invalid_request     4xx about body. NEVER retried.
    server_error        5xx.            Retried.
    timeout             no answer.      Retried.
    transport           DNS/TLS.        Retried.
    malformed_response  2xx, bad body.  NEVER retried.
    unknown             none of above.  NEVER retried.
"""
import argparse
import os
import time

from . import (MissingKey, ProviderError, key, load_env, ok, redact, request)

ENV_KEY = "ANTHROPIC_API_KEY"
ENV_BASE = "ANTHROPIC_BASE_URL"
ENV_MODEL = "ANTHROPIC_MODEL"

BASE_DEFAULT = "https://api.anthropic.com"
MESSAGES_ENDPOINT = "/v1/messages"
BATCHES_ENDPOINT = "/v1/messages/batches"

DEFAULT_MODEL = "claude-sonnet-4-20250514"
API_VERSION = "2023-06-01"

MODELS = (
    "claude-sonnet-4-20250514",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
)

MAX_TOKENS_CAP = 8192
DEFAULT_MAX_TOKENS = 1024
ANTHROPIC_TIMEOUT = 180
MAX_RETRIES = 2
BACKOFF_BASE = 0.5

RESPONSE_FIELDS = ("content", "model", "requested_model", "stop_reason",
                   "usage", "seconds")


class AnthropicError(ProviderError):
    classification = "unknown"


class AnthropicAuthFailed(AnthropicError):
    classification = "auth"


class AnthropicQuotaExhausted(AnthropicError):
    classification = "quota"


class AnthropicRateLimited(AnthropicError):
    classification = "rate_limit"


class AnthropicInvalidRequest(AnthropicError):
    classification = "invalid_request"


class AnthropicServerError(AnthropicError):
    classification = "server_error"


class AnthropicTimeout(AnthropicError):
    classification = "timeout"


class AnthropicTransportError(AnthropicError):
    classification = "transport"


class AnthropicMalformedResponse(AnthropicError):
    classification = "malformed_response"


class AnthropicUnknownFailure(AnthropicError):
    classification = "unknown"


RETRYABLE = (AnthropicRateLimited, AnthropicServerError,
             AnthropicTimeout, AnthropicTransportError)

QUOTA_WORDS = ("credit", "balance", "quota", "limit exceeded",
               "insufficient", "rate limit")


def base_url():
    load_env()
    return (os.environ.get(ENV_BASE) or BASE_DEFAULT).strip().rstrip("/")


def configured_model():
    load_env()
    return (os.environ.get(ENV_MODEL) or "").strip() or DEFAULT_MODEL


def headers():
    """x-api-key auth, per Anthropic's spec."""
    return {"x-api-key": key(ENV_KEY),
            "anthropic-version": API_VERSION,
            "Content-Type": "application/json"}


def complete(prompt, system=None, model=None, max_tokens=None,
             temperature=0, timeout=None, max_attempts=None,
             sleep=time.sleep, ledger_client=None, cache=False):
    """One Messages API call.  Return a trimmed dict, or raise.

    Parameters
    ----------
    cache : bool
        OFF by default.  When True, the system message (or, lacking one, the
        first user message) carries `cache_control: {"type": "ephemeral"}`.
        The stable cohort preamble is the ideal cache candidate: it is the
        same text on every lead, and caching reduces its per-lead cost by
        ~90% after the first write.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("anthropic: prompt must be a non-empty string")
    if system is not None and not isinstance(system, str):
        raise ValueError("anthropic: system must be a string when given")

    model = model or configured_model()
    if model not in MODELS:
        raise ValueError(
            f"anthropic: {model!r} is not in the allowlist. "
            f"Choose from: {', '.join(MODELS)}")

    if not isinstance(temperature, (int, float)) or not 0 <= temperature <= 1:
        raise ValueError(
            f"anthropic: temperature {temperature!r} out of range 0..1")

    messages = [{"role": "user", "content": prompt}]
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": min(int(max_tokens or DEFAULT_MAX_TOKENS),
                          MAX_TOKENS_CAP),
        "temperature": temperature,
    }
    if system:
        body["system"] = _system_with_cache(system, cache)
    elif cache:
        messages[0]["cache_control"] = {"type": "ephemeral"}

    status, data, seconds = _send(
        body,
        timeout=min(int(timeout or ANTHROPIC_TIMEOUT), ANTHROPIC_TIMEOUT),
        max_attempts=max(1, min(int(max_attempts or MAX_RETRIES + 1),
                                MAX_RETRIES + 1)),
        sleep=sleep)

    result = _trim(status, data, seconds, model)
    _record_spend(model, result.get("usage") or {}, ledger_client)
    return result


def _system_with_cache(system_text, cache):
    """Build the system field.  With cache=True, it carries cache_control.

    Anthropic's system field accepts two shapes:
      - a plain string (no caching)
      - a list of blocks, each with `type`, `text`, and optional `cache_control`

    When caching is requested, we emit the list form with one block carrying
    `cache_control: {"type": "ephemeral"}`.
    """
    if not cache:
        return system_text
    return [{"type": "text", "text": system_text,
             "cache_control": {"type": "ephemeral"}}]


def _send(body, timeout, max_attempts, sleep):
    """POST with bounded retry on transient failures only."""
    hdrs = headers()
    url = f"{base_url()}{MESSAGES_ENDPOINT}"

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
            raise AnthropicUnknownFailure(
                f"anthropic: unexpected {type(e).__name__}: "
                f"{redact(str(e))[:200]}") from None
        else:
            seconds = round(time.monotonic() - started, 3)
            if ok(status):
                return status, data, seconds
            last = _http_failure(status, data)

        if not isinstance(last, RETRYABLE) or attempt >= max_attempts - 1:
            raise last
        sleep(BACKOFF_BASE * (2 ** attempt))

    raise last if last else AnthropicUnknownFailure(
        "anthropic: the retry loop ended with no outcome")


def _transport_failure(exc):
    text = redact(str(exc))
    low = text.lower()
    if "timeout" in low or "timed out" in low:
        return AnthropicTimeout(
            f"anthropic: the call did not return: {text[:200]}")
    return AnthropicTransportError(
        f"anthropic: the endpoint was not reached: {text[:200]}")


def _http_failure(status, data):
    note = redact(str(data))[:200]
    said = (note or "").lower()

    if status in (401, 403):
        return AnthropicAuthFailed(
            f"anthropic: auth rejected ({status}): {note}")
    if status == 429 and any(w in said for w in QUOTA_WORDS):
        return AnthropicQuotaExhausted(
            f"anthropic: no budget left ({status}): {note}")
    if status == 429:
        return AnthropicRateLimited(
            f"anthropic: rate limited ({status}): {note}")
    if status is not None and 400 <= status < 500:
        return AnthropicInvalidRequest(
            f"anthropic: refused ({status}): {note}")
    if status is not None and status >= 500:
        return AnthropicServerError(
            f"anthropic: endpoint faulted ({status}): {note}")
    return AnthropicUnknownFailure(f"anthropic: answered {status}: {note}")


def _trim(status, data, seconds, requested):
    """A 2xx body into RESPONSE_FIELDS, or a stated malformed failure."""
    if not isinstance(data, dict):
        raise AnthropicMalformedResponse(
            f"anthropic: answered {status} with a body that is not an object "
            f"({type(data).__name__})")

    content_blocks = data.get("content")
    if not isinstance(content_blocks, list) or not content_blocks:
        raise AnthropicMalformedResponse(
            f"anthropic: answered {status} with no `content` blocks")

    first = content_blocks[0] if isinstance(content_blocks[0], dict) else {}
    text = first.get("text")
    if not isinstance(text, str) or not text.strip():
        raise AnthropicMalformedResponse(
            f"anthropic: answered {status} with an empty completion")

    return {
        "content": text,
        "model": data.get("model"),
        "requested_model": requested,
        "stop_reason": data.get("stop_reason"),
        "usage": _usage(data),
        "seconds": seconds,
    }


def _usage(data):
    """Token counts as the API reported them.

    Includes cache-specific counts when present: `cache_creation_input_tokens`
    (the first write) and `cache_read_input_tokens` (subsequent reads).
    """
    u = data.get("usage")
    u = u if isinstance(u, dict) else {}
    return {
        "prompt_tokens": u.get("input_tokens"),
        "completion_tokens": u.get("output_tokens"),
        "total_tokens": ((u.get("input_tokens") or 0)
                         + (u.get("output_tokens") or 0)),
        "cache_creation_input_tokens": u.get("cache_creation_input_tokens"),
        "cache_read_input_tokens": u.get("cache_read_input_tokens"),
    }


def _record_spend(model, usage, ledger_client):
    """Write one ledger row for this call.  TASK-323.

    Cost comes from `modelprices.cost_micro_usd`.  Cache tokens are not
    separately priced in model-prices.yaml yet; the row carries them in
    `rows` so a future pricer can account for them.
    """
    try:
        from .. import modelprices, spendledger
        cost = modelprices.cost_micro_usd(model, usage)
        spendledger.record(
            ledger_client or "_model", "anthropic",
            f"complete:{model}",
            cost,
            unit="microusd",
            rows=usage,
        )
    except Exception:                                       # noqa: BLE001
        pass


# --------------------------------------------------------------- batch

def complete_batch(items, model=None, max_tokens=None, temperature=0,
                   timeout=None, sleep=time.sleep, ledger_client=None,
                   cache=False, poll_interval=10, max_polls=60):
    """Submit N leads in one batch request.

    Parameters
    ----------
    items : list[dict]
        Each dict has `prompt` (required) and `system` (optional).
    cache : bool
        OFF by default.  When True, each item's system message carries
        `cache_control: {"type": "ephemeral"}`.
    poll_interval : int
        Seconds between poll attempts.
    max_polls : int
        Maximum poll attempts before giving up.

    Returns
    -------
    list[dict]
        One result per input item, in the same order.  Each has the same
        shape as `complete()`'s return value, plus `custom_id`.
    """
    if not items:
        raise ValueError("anthropic: items must be non-empty")

    model = model or configured_model()
    if model not in MODELS:
        raise ValueError(
            f"anthropic: {model!r} is not in the allowlist. "
            f"Choose from: {', '.join(MODELS)}")

    requests_list = []
    for i, item in enumerate(items):
        prompt = item.get("prompt") or item.get("content")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(
                f"anthropic: item {i} has no valid prompt")
        system = item.get("system")
        entry = {
            "custom_id": f"item-{i}",
            "params": {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": min(int(max_tokens or DEFAULT_MAX_TOKENS),
                                  MAX_TOKENS_CAP),
                "temperature": temperature,
            }
        }
        if system:
            entry["params"]["system"] = _system_with_cache(system, cache)
        elif cache:
            entry["params"]["messages"][0]["cache_control"] = {
                "type": "ephemeral"}
        requests_list.append(entry)

    body = {"requests": requests_list}
    hdrs = headers()
    url = f"{base_url()}{BATCHES_ENDPOINT}"

    status, data = request("POST", url, hdrs, body,
                           min(timeout or ANTHROPIC_TIMEOUT,
                               ANTHROPIC_TIMEOUT))
    if not ok(status):
        raise _http_failure(status, data)

    batch_id = (data or {}).get("id")
    if not batch_id:
        raise AnthropicMalformedResponse(
            "anthropic: batch create returned no id")

    results = _poll_batch(batch_id, hdrs, poll_interval, max_polls, sleep)
    return _trim_batch_results(results, model)


def _poll_batch(batch_id, hdrs, interval, max_polls, sleep):
    """Poll the batch until it is done or we exhaust attempts."""
    url = f"{base_url()}{BATCHES_ENDPOINT}/{batch_id}"
    for _ in range(max_polls):
        sleep(interval)
        status, data = request("GET", url, hdrs, None, ANTHROPIC_TIMEOUT)
        if not ok(status):
            raise _http_failure(status, data)
        processing = (data or {}).get("processing_status")
        if processing == "ended":
            return (data or {}).get("results") or []
        if processing in ("failed", "cancelled"):
            raise AnthropicServerError(
                f"anthropic: batch {processing}")
    raise AnthropicServerError(
        f"anthropic: batch {batch_id} did not complete in {max_polls} polls")


def _trim_batch_results(results, requested):
    """Map batch results back to per-item trimmed dicts."""
    out = []
    for entry in results:
        if not isinstance(entry, dict):
            continue
        result_data = entry.get("result")
        if not isinstance(result_data, dict):
            error = entry.get("error")
            out.append({"content": None, "model": None,
                        "requested_model": requested,
                        "stop_reason": None, "usage": {},
                        "seconds": 0,
                        "custom_id": entry.get("custom_id"),
                        "error": str(error) if error else "no result"})
            continue
        trimmed = _trim(200, result_data, 0, requested)
        trimmed["custom_id"] = entry.get("custom_id")
        out.append(trimmed)
    return out


# --------------------------------------------------------------- health

def check(live=False):
    if not live:
        try:
            key(ENV_KEY)
        except MissingKey as e:
            return {"provider": "anthropic", "ok": False, "status": None,
                    "note": redact(str(e))[:120]}
        return {"provider": "anthropic", "ok": None, "status": None,
                "skipped": True,
                "note": f"{ENV_KEY} configured, model {configured_model()}, "
                        f"no call made (--live to spend)"}
    try:
        body = {"model": configured_model(),
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1, "temperature": 0}
        status, data, seconds = _send(
            body, timeout=ANTHROPIC_TIMEOUT,
            max_attempts=MAX_RETRIES + 1, sleep=time.sleep)
    except AnthropicError as e:
        return {"provider": "anthropic", "ok": False, "status": None,
                "classification": e.classification,
                "note": redact(str(e))[:120]}
    except MissingKey as e:
        return {"provider": "anthropic", "ok": False, "status": None,
                "classification": "auth",
                "note": redact(str(e))[:120]}
    served = data.get("model") if isinstance(data, dict) else None
    return {"provider": "anthropic", "ok": ok(status), "status": status,
            "classification": None,
            "note": f"requested {configured_model()}, served {served}, "
                    f"{int(seconds * 1000)}ms"}


def main(argv=None):
    p = argparse.ArgumentParser(prog="py -3 -m src.providers.anthropic")
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
