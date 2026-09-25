#!/usr/bin/env python3
"""Anthropic (Claude) adapter for prospect-facing copy.  TASK-308.

Operator decision, 2026-09-25: prospect-facing copy runs on Claude Sonnet 5
through the Anthropic API directly - not through OpenRouter - batch mode
where possible, every call ledgered in dollars.

THE DISTINCTION IS LOAD-BEARING.  Routing through `llm.py` / OpenRouter
would silently deliver a different product: a reseller's markup instead of
a dollar-denominated bill, and no batch mode.  This module speaks the
Anthropic Messages API and the Message Batches API directly.

    https://platform.claude.com/docs/en/api/messages
    https://platform.claude.com/docs/en/api/messages/batches/create

Key read through `providers.model_key("anthropic")`, committed at a230771e.
Not a fourth way to read a credential.

## Pricing

Source: https://platform.claude.com/docs/en/about-claude/pricing
Date: 2026-09-25.  Anthropic made Sonnet 5 pricing permanent on 2026-08-10
(the previously scheduled increase to $3/$15 was cancelled).

    Standard:  $2.00 / MTok input,  $10.00 / MTok output
    Batch:     $1.00 / MTok input,   $5.00 / MTok output  (50% discount)
    Cache write (ephemeral 5m, 1.25x input):  $2.50 / MTok
    Cache write (ephemeral 1h, 2x input):     $4.00 / MTok
    Cache read  (0.1x input):                 $0.20 / MTok

Cost comes from the response's own usage block.  An estimated cost
presented as a measured one is worse than no number.

## The spend ledger unit

The spend ledger currently holds credits (integer) and cents (integer).
Dollars are a THIRD unit.  So every row this module writes carries an
explicit `{"unit": "usd"}` and an `amount` field in dollars (float).
The other providers' rows are NOT retrofitted - naming the problem and
not spreading it is the deliverable.

## Batch mode

The Anthropic Message Batches API is the right shape for 50 leads x 6
messages: submit, poll, collect.  Batches are asynchronous and partial
results are normal.  A batch that returns 47 of 50 is not a batch that
failed; it is 47 results and 3 to handle.  Both are reported.

  py -3 -m src.providers.anthropic --check
  py -3 -m src.providers.anthropic --check --live   one real token
"""
import argparse
import json
import time

from . import (MissingKey, ProviderError, key, load_env, model_key,
               ok, redact, request)

BASE = "https://api.anthropic.com"
MESSAGES_ENDPOINT = "/v1/messages"
BATCHES_ENDPOINT = "/v1/messages/batches"

MODEL = "claude-sonnet-5"
MODELS = (MODEL,)

# https://platform.claude.com/docs/en/about-claude/pricing
# Permanent as of 2026-08-10.  Per one million tokens.
PRICING = {
    "standard_input": 2.0,
    "standard_output": 10.0,
    "batch_input": 1.0,
    "batch_output": 5.0,
    "cache_write_5m": 2.5,
    "cache_write_1h": 4.0,
    "cache_read": 0.2,
}
_PRICE_SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing"
_PRICE_DATE = "2026-09-25"

MTOK = 1_000_000

# Bounds.
MAX_TOKENS_DEFAULT = 4096
MAX_TOKENS_CAP = 16384
ANTHROPIC_TIMEOUT = 180
MAX_RETRIES = 2
BACKOFF_BASE = 0.5

# Batch polling.
BATCH_POLL_INTERVAL = 30       # seconds between polls
BATCH_MAX_POLL_TIME = 86400    # 24 hours, matching the API's own expiry

# The version header the Anthropic API requires.
ANTHROPIC_VERSION = "2023-06-01"


# --------------------------------------------------------------- failures

class AnthropicError(ProviderError):
    """An Anthropic call failed.  `.classification` says how."""
    classification = "unknown"


class AnthropicAuthFailed(AnthropicError):
    classification = "auth"


class AnthropicBillingError(AnthropicError):
    classification = "billing"


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


RETRYABLE = (AnthropicRateLimited, AnthropicServerError,
             AnthropicTimeout, AnthropicTransportError)


# --------------------------------------------------------------- headers

def _headers():
    """x-api-key auth.  The Anthropic API does not use Bearer tokens."""
    api_key, _found_as = model_key("anthropic")
    return {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }


# --------------------------------------------------------------- single message

def complete(system, user, model=None, max_tokens=None, temperature=0,
             timeout=None, max_attempts=None, sleep=time.sleep):
    """One Messages API call.  Return a trimmed dict with usage and cost.

    The key is read through `providers.model_key("anthropic")`, not through
    `os.environ.get`.  That is the whole point of commit a230771e.

    Returns
    -------
    dict
        content          the text the model produced
        model            what answered
        stop_reason      end_turn, max_tokens, etc.
        usage            token counts from the API
        cost_usd         dollars, computed from the usage and PRICING
        seconds          wall time

    Raises
    ------
    AnthropicError (classified)
        On any failure.  Never returns a default or empty dict.
    """
    model = model or MODEL
    if model not in MODELS:
        raise ValueError(
            f"anthropic: {model!r} is not in the allowlist. "
            f"Choose from: {', '.join(MODELS)}")

    body = {
        "model": model,
        "max_tokens": min(int(max_tokens or MAX_TOKENS_DEFAULT),
                          MAX_TOKENS_CAP),
        "messages": [{"role": "user", "content": user}],
    }
    if system:
        body["system"] = system
    if temperature is not None:
        body["temperature"] = temperature

    hdrs = _headers()
    url = f"{BASE}{MESSAGES_ENDPOINT}"
    per_attempt = min(int(timeout or ANTHROPIC_TIMEOUT), ANTHROPIC_TIMEOUT)
    attempts = min(int(max_attempts or MAX_RETRIES + 1), MAX_RETRIES + 1)

    status, data, seconds = _send_with_retry(
        hdrs, url, body, per_attempt, attempts, sleep)

    if not ok(status):
        raise _classify_error(status, data)

    return _trim_response(data, seconds, batch=False)


# --------------------------------------------------------------- batch

def create_batch(requests, model=None):
    """Submit a Message Batch.  Returns the batch object from the API.

    Parameters
    ----------
    requests : list[dict]
        Each dict: {"custom_id": str, "system": str, "user": str,
                     "max_tokens": int (optional)}
        custom_id must be 1-64 chars, alphanumeric/underscore/hyphen.

    Returns
    -------
    dict
        The batch object: id, processing_status, request_counts, etc.
    """
    model = model or MODEL
    if model not in MODELS:
        raise ValueError(
            f"anthropic: {model!r} is not in the allowlist. "
            f"Choose from: {', '.join(MODELS)}")

    batch_requests = []
    for req in requests:
        cid = req["custom_id"]
        entry = {
            "custom_id": cid,
            "params": {
                "model": model,
                "max_tokens": req.get("max_tokens", MAX_TOKENS_DEFAULT),
                "messages": [{"role": "user", "content": req["user"]}],
            },
        }
        if req.get("system"):
            entry["params"]["system"] = req["system"]
        if "temperature" in req:
            entry["params"]["temperature"] = req["temperature"]
        batch_requests.append(entry)

    body = {"requests": batch_requests}
    hdrs = _headers()
    url = f"{BASE}{BATCHES_ENDPOINT}"

    status, data = request("POST", url, hdrs, body, ANTHROPIC_TIMEOUT)
    if not ok(status):
        raise _classify_error(status, data)

    return data


def get_batch(batch_id):
    """Retrieve a batch's current status.  GET /v1/messages/batches/{id}."""
    hdrs = _headers()
    url = f"{BASE}{BATCHES_ENDPOINT}/{batch_id}"
    status, data = request("GET", url, hdrs, None, ANTHROPIC_TIMEOUT)
    if not ok(status):
        raise _classify_error(status, data)
    return data


def get_batch_results(batch_id):
    """Fetch the JSONL results from a completed batch.

    Returns a list of result dicts, each with custom_id and result.
    A result is one of: succeeded (with message + usage), errored,
    canceled, expired.
    """
    batch = get_batch(batch_id)
    results_url = batch.get("results_url")
    if not results_url:
        raise ProviderError(
            f"anthropic: batch {batch_id} has no results_url "
            f"(status: {batch.get('processing_status')})")

    hdrs = _headers()
    status, data = request("GET", results_url, hdrs, None,
                           ANTHROPIC_TIMEOUT)
    if not ok(status):
        raise _classify_error(status, data)

    return _parse_batch_results(data)


def poll_batch(batch_id, poll_interval=None, max_wait=None,
               sleep=time.sleep):
    """Poll a batch until it ends.  Returns (batch_status, results).

    Partial results are normal.  A batch that returns 47 of 50 is not
    a failure; it is 47 results and 3 to handle.  Both are reported.

    Returns
    -------
    tuple[dict, list[dict]]
        (batch_status, parsed_results)
        batch_status carries processing_status, request_counts, etc.
        parsed_results is a list of per-request outcomes.
    """
    interval = poll_interval or BATCH_POLL_INTERVAL
    max_w = max_wait or BATCH_MAX_POLL_TIME
    started = time.monotonic()

    while True:
        batch = get_batch(batch_id)
        status = batch.get("processing_status")
        if status == "ended":
            results = get_batch_results(batch_id)
            return batch, results
        if status in ("canceling",):
            return batch, []
        elapsed = time.monotonic() - started
        if elapsed >= max_w:
            return batch, []
        sleep(interval)


def _parse_batch_results(data):
    """Parse the JSONL body from a batch results download.

    Each line is a JSON object.  The body may arrive as a string (if the
    transport returned text) or as a list (if already parsed).
    """
    if isinstance(data, list):
        return data
    if isinstance(data, str):
        results = []
        for line in data.strip().split("\n"):
            line = line.strip()
            if line:
                try:
                    results.append(json.loads(line))
                except (ValueError, TypeError):
                    continue
        return results
    return []


# --------------------------------------------------------------- retry

def _send_with_retry(headers, url, body, timeout, max_attempts, sleep):
    """POST with bounded retry on transient failures.

    MissingKey is never retried: a credential that is absent now will
    not materialise on the second attempt.
    """
    last_status, last_data = None, None
    started = time.monotonic()
    for attempt in range(max_attempts):
        try:
            last_status, last_data = request(
                "POST", url, headers, body, timeout)
            if ok(last_status):
                seconds = round(time.monotonic() - started, 3)
                return last_status, last_data, seconds
            if 400 <= last_status < 500:
                seconds = round(time.monotonic() - started, 3)
                return last_status, last_data, seconds
        except MissingKey:
            raise
        except ProviderError as e:
            low = redact(str(e)).lower()
            if "timeout" in low or "timed out" in low:
                last_status, last_data = None, None
                if attempt < max_attempts - 1:
                    sleep(BACKOFF_BASE * (2 ** attempt))
                    continue
                raise AnthropicTimeout(
                    f"anthropic: the call did not return: "
                    f"{redact(str(e))[:200]}") from None
            if attempt >= max_attempts - 1:
                raise AnthropicTransportError(
                    f"anthropic: transport failure: "
                    f"{redact(str(e))[:200]}") from None
            sleep(BACKOFF_BASE * (2 ** attempt))
    seconds = round(time.monotonic() - started, 3)
    return last_status, last_data, seconds


# --------------------------------------------------------------- response trim

def _trim_response(data, seconds, batch=False):
    """A 2xx body into a trimmed dict, or a stated malformed failure."""
    if not isinstance(data, dict):
        raise AnthropicMalformedResponse(
            f"anthropic: body is not an object "
            f"({type(data).__name__})")

    content_blocks = data.get("content")
    if not isinstance(content_blocks, list) or not content_blocks:
        raise AnthropicMalformedResponse(
            f"anthropic: no content blocks in response")

    text_parts = []
    for block in content_blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            t = block.get("text")
            if isinstance(t, str) and t.strip():
                text_parts.append(t)

    if not text_parts:
        raise AnthropicMalformedResponse(
            f"anthropic: empty completion "
            f"(stop_reason={data.get('stop_reason')!r})")

    usage = _usage(data)
    cost = cost_from_usage(usage, batch=batch)

    return {
        "content": "\n".join(text_parts),
        "model": data.get("model"),
        "stop_reason": data.get("stop_reason"),
        "usage": usage,
        "cost_usd": cost,
        "seconds": seconds,
    }


def _usage(data):
    """Token counts as the API reported them.  Missing stays None."""
    u = data.get("usage")
    u = u if isinstance(u, dict) else {}
    return {
        "input_tokens": u.get("input_tokens"),
        "output_tokens": u.get("output_tokens"),
        "cache_creation_input_tokens": u.get("cache_creation_input_tokens"),
        "cache_read_input_tokens": u.get("cache_read_input_tokens"),
    }


# --------------------------------------------------------------- cost

def cost_from_usage(usage, batch=False):
    """Compute dollars from a usage dict, using PRICING.

    The price table source and date are recorded in `_PRICE_SOURCE` and
    `_PRICE_DATE`.  An estimated cost presented as a measured one is
    worse than no number, because it reconciles against nothing - this
    function uses the response's own token counts, not estimates.

    Cache tokens:
    - cache_creation_input_tokens are priced at the 5m write rate by
      default.  The API does not distinguish 5m vs 1h in the standard
      usage block; the 1h rate is available where the response carries
      cache_creation.ephemeral_1h_input_tokens.
    - cache_read_input_tokens are priced at the read rate (0.1x input).
    - input_tokens are the non-cached input tokens.
    """
    if not isinstance(usage, dict):
        return 0.0

    in_price = PRICING["batch_input"] if batch else PRICING["standard_input"]
    out_price = (PRICING["batch_output"] if batch
                 else PRICING["standard_output"])

    input_t = usage.get("input_tokens") or 0
    output_t = usage.get("output_tokens") or 0
    cache_write_t = usage.get("cache_creation_input_tokens") or 0
    cache_read_t = usage.get("cache_read_input_tokens") or 0

    cost = 0.0
    cost += (input_t / MTOK) * in_price
    cost += (output_t / MTOK) * out_price
    cost += (cache_write_t / MTOK) * PRICING["cache_write_5m"]
    cost += (cache_read_t / MTOK) * PRICING["cache_read"]
    return round(cost, 8)


# --------------------------------------------------------------- error classify

def _classify_error(status, data):
    """A non-2xx response into a classified AnthropicError."""
    note = redact(str(data))[:200]
    err_type = ""
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            err_type = (error.get("type") or "").strip()

    if status in (401, 403):
        return AnthropicAuthFailed(
            f"anthropic: key rejected ({status}): {note}")
    if err_type == "billing_error" or status == 402:
        return AnthropicBillingError(
            f"anthropic: billing error ({status}): {note}")
    if status == 429 or err_type == "rate_limit_error":
        return AnthropicRateLimited(
            f"anthropic: rate limited ({status}): {note}")
    if status == 400 or err_type == "invalid_request_error":
        return AnthropicInvalidRequest(
            f"anthropic: invalid request ({status}): {note}")
    if status is not None and status >= 500:
        return AnthropicServerError(
            f"anthropic: server error ({status}): {note}")
    return AnthropicError(f"anthropic: {status}: {note}")


# --------------------------------------------------------------- health

def check(live=False):
    """Configuration readiness by default; one real token if live."""
    if not live:
        try:
            model_key("anthropic")
        except MissingKey as e:
            return {"provider": "anthropic", "ok": False, "status": None,
                    "note": redact(str(e))[:120]}
        return {"provider": "anthropic", "ok": None, "status": None,
                "skipped": True,
                "note": f"ANTHROPIC_API_KEY configured, model {MODEL}, "
                        f"no call made (--live to spend a token)"}
    try:
        started = time.monotonic()
        hdrs = _headers()
        body = {
            "model": MODEL,
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "ping"}],
        }
        status, data = request(
            "POST", f"{BASE}{MESSAGES_ENDPOINT}", hdrs, body,
            ANTHROPIC_TIMEOUT)
        seconds = round(time.monotonic() - started, 3)
    except (ProviderError, MissingKey) as e:
        return {"provider": "anthropic", "ok": False, "status": None,
                "note": redact(str(e))[:120]}
    return {"provider": "anthropic", "ok": ok(status), "status": status,
            "note": f"model {MODEL}, {int(seconds * 1000)}ms"}


# --------------------------------------------------------------- copy pipeline

def write_copy_batch(leads, sender_name, model=None, sleep=time.sleep):
    """Submit a batch of copy-writing requests for a set of leads.

    This is the pipeline function that unblocks TASK-306's writing step.
    Each lead carries pre-extracted facts (from the extractor step, which
    runs on Groq).  This function builds the writer prompts from
    `copyprompts`, submits them as a batch, and returns the results.

    Parameters
    ----------
    leads : list[dict]
        Each: {lead_id, lead: {name, title, domain}, company, facts,
               angle, angle_reason}
    sender_name : str
        The named sender at Productive.
    model : str, optional
        Defaults to MODEL (claude-sonnet-5).
    sleep : callable
        Backoff/poll injection point for tests.

    Returns
    -------
    dict
        batch_id       the API's batch id
        total          how many were submitted
        results        list of {custom_id, status, content, usage, cost_usd}
        counts         {succeeded, errored, canceled, expired}
    """
    from . import copyprompts

    batch_requests = []
    for lead_data in leads:
        user_prompt = copyprompts.write_user(
            lead=lead_data["lead"],
            company=lead_data["company"],
            facts=lead_data["facts"],
            angle=lead_data["angle"],
            angle_reason=lead_data["angle_reason"],
            sender_name=sender_name,
        )
        batch_requests.append({
            "custom_id": lead_data["lead_id"],
            "system": copyprompts.WRITE_SYSTEM,
            "user": user_prompt,
        })

    batch_obj = create_batch(batch_requests, model=model)
    batch_id = batch_obj.get("id")
    if not batch_id:
        raise AnthropicMalformedResponse(
            "anthropic: batch creation returned no id")

    batch_status, raw_results = poll_batch(batch_id, sleep=sleep)

    results = []
    for r in raw_results:
        cid = r.get("custom_id")
        result = r.get("result", {})
        rtype = result.get("type")
        entry = {"custom_id": cid, "status": rtype}
        if rtype == "succeeded":
            message = result.get("message", {})
            content_blocks = message.get("content", [])
            text_parts = []
            for block in content_blocks:
                if isinstance(block, dict) and block.get("type") == "text":
                    t = block.get("text")
                    if t:
                        text_parts.append(t)
            entry["content"] = "\n".join(text_parts)
            usage = _usage(message)
            entry["usage"] = usage
            entry["cost_usd"] = cost_from_usage(usage, batch=True)
        elif rtype == "errored":
            error = result.get("error", {})
            inner = error.get("error", {})
            entry["error"] = inner.get("message", str(error))
        results.append(entry)

    counts = batch_status.get("request_counts", {})
    return {
        "batch_id": batch_id,
        "total": len(leads),
        "results": results,
        "counts": {
            "succeeded": counts.get("succeeded", 0),
            "errored": counts.get("errored", 0),
            "canceled": counts.get("canceled", 0),
            "expired": counts.get("expired", 0),
        },
    }


def record_spend(client, run_id, cost_usd, call="complete"):
    """Write one spend ledger row in dollars.

    The row carries `amount` (float dollars) and `unit` ("usd") alongside
    the standard fields.  The existing `expected_cost` column is set to 0
    because dollars and credits are different units and must not be summed.
    """
    from .. import spendledger, store

    row = {
        "at": store.now(),
        "day": spendledger.today(),
        "client": client,
        "provider": "anthropic",
        "call": call,
        "expected_cost": 0,
        "amount": cost_usd,
        "unit": "usd",
        "run_id": run_id,
    }
    spendledger._append_row(row)
    return row


def main(argv=None):
    p = argparse.ArgumentParser(prog="py -3 -m src.providers.anthropic")
    p.add_argument("--check", action="store_true")
    p.add_argument("--live", action="store_true",
                   help="spend one token against the real endpoint")
    a = p.parse_args(argv)
    r = check(live=a.live)
    status = r.get("status")
    note = r.get("note", "")
    if r.get("ok") is True:
        tag = "ok  "
    elif r.get("ok") is False:
        tag = "FAIL"
    else:
        tag = "skip"
    print(f"{tag} anthropic  "
          f"{status if status is not None else '-'}  {note}")
    return 0 if r.get("ok") or r.get("skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
