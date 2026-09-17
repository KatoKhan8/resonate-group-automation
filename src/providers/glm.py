#!/usr/bin/env python3
"""Z.AI / GLM worker adapter.  The minimum path that can be given real work.

ONE outward function, `complete(prompt)`.  It sends a bounded prompt to the
Z.AI Coding Plan endpoint and returns a trimmed dict, or raises a CLASSIFIED
failure.  There is no scheduler, router or queue here on purpose: this module
is the seam a worker runs through, not the worker pool.

    ZAI_API_KEY    the credential.  Referred to BY NAME only, never printed,
                   never stored on an object, never placed in an exception.
    ZAI_BASE_URL   the Coding Plan base, e.g. the /api/coding/paas/v4 root.
                   Falls back to BASE_DEFAULT, which is that same documented
                   root - a base URL is configuration, not a credential.
    ZAI_MODEL      the model id to request.  Falls back to DEFAULT_MODEL.

All three are read at CALL time through `providers.load_env`, never at import,
so a key that is absent is a stated failure rather than an import error.

## The endpoint remaps models, and the remap is measured, not assumed

Probed live 2026-09-17 against the Coding Plan base, one token each:

    requested        served            probed
    glm-5.3          glm-5.3          200
    glm-5.2          glm-5.3          200
    glm-5.3-flash    glm-5.3-flash    200
    glm-4.6          glm-5.3-flash    200
    glm-4.5-air      glm-5.3-flash    200
    no-such-model    -                400 {"code":"1211","message":"Unknown Model"}

So `SERVES` below is what the endpoint did, not what a document claims.  A
caller that needs to know what actually answered reads `model` off the result;
`requested_model` carries what was asked for.  Recording only the requested
name would report a flash model as the frontier one.

The endpoint returned NO rate-limit or quota headers on any probe - no
`x-ratelimit-*`, no `retry-after`.  There is therefore nothing to read a
budget from, and `RATE_LIMIT_HEADERS_OBSERVED` records that as a measured
absence rather than leaving a future reader to assume the adapter forgot.

## Failure is classified, never swallowed

Every failure raises a subclass of `GlmError` carrying `.classification`:

    auth                401/403, or no ZAI_API_KEY.       NEVER retried.
    quota               balance or daily allowance gone.  NEVER retried.
    rate_limit          429 that is a pace problem.       Retried.
    invalid_request     4xx about what we sent.           NEVER retried.
    server_error        5xx, retries exhausted.           Retried first.
    timeout             the call did not come back.       Retried.
    transport           DNS, connection, TLS.             Retried.
    malformed_response  2xx whose body is not usable.     NEVER retried.
    unknown             none of the above.                NEVER retried.

There is no `except Exception` returning a default anywhere below.  CLAUDE.md:
an empty dict or an "unknown" standing in for confusion makes an unsafe system
look healthy, so confusion is raised as `unknown` and kept distinguishable
from every failure we do understand.

  py -3 -m src.providers.glm --check          configuration only, no call
  py -3 -m src.providers.glm --check --live   one real token
"""
import argparse
import os
import time

from . import (MissingKey, ProviderError, key, load_env, ok, redact, request)

ENV_KEY = "ZAI_API_KEY"
ENV_BASE = "ZAI_BASE_URL"
ENV_MODEL = "ZAI_MODEL"

# The Coding Plan root.  `ZAI_BASE_URL` overrides it; this is the documented
# default so an adapter with a key and no base is not half-configured.
BASE_DEFAULT = "https://api.z.ai/api/coding/paas/v4"
CHAT_ENDPOINT = "/chat/completions"

DEFAULT_MODEL = "glm-5.3"

# What the endpoint served for each requested id when probed, 2026-09-17.
# An id absent from here is refused before a request is sent: an unknown model
# costs a round trip and comes back as a 400 that reads like our fault, which
# it is.
SERVES = {
    "glm-5.3": "glm-5.3",
    "glm-5.2": "glm-5.3",
    "glm-5.3-flash": "glm-5.3-flash",
    "glm-4.6": "glm-5.3-flash",
    "glm-4.5-air": "glm-5.3-flash",
}
MODELS = tuple(SERVES)

# Measured absence, 2026-09-17: the endpoint answered with Date, Content-Type,
# ga-traceid, X-LOG-ID, X-Request-ID and nothing else.  No budget to read.
RATE_LIMIT_HEADERS_OBSERVED = ()

# Bounds.  Nothing here may run unbounded.
MAX_PROMPT_CHARS = 60_000        # ~15k tokens of context, refused above it
MAX_TOKENS_CAP = 8192
DEFAULT_MAX_TOKENS = 1024
# PER ATTEMPT, SECONDS, AND IT IS A CEILING RATHER THAN A DEFAULT - `complete`
# clamps whatever a caller asks for down to this, so nothing here can hang a
# process indefinitely however the call site is written.
#
# RAISED FROM 60 ON 2026-09-17, on measurement rather than preference. This
# model spends most of its output budget on reasoning tokens: the four calls
# in `docs/GLM-SAFETY-AUDIT-2026-09-17.md` took 20.2s, 43.1s, 47.1s and 56.6s,
# with 917 to 3,041 reasoning tokens each. The last of those cleared 60s by
# three and a half seconds. At 60 the ceiling was inside the model's ordinary
# working range, and `scripts/glm_review.py --target storage` proved it -
# BOTH functions timed out, one on a 5,642-character prompt, and a review that
# times out is a review that silently does not happen.
#
# 180 is three times the longest observed call. It is still a ceiling and
# still bounded; what it stops being is a coin toss.
GLM_TIMEOUT = 180
MAX_RETRIES = 2                  # so three attempts at most
BACKOFF_BASE = 0.5

# Fields returned to a caller.  Nothing else escapes this module.
RESPONSE_FIELDS = ("content", "model", "requested_model", "finish_reason",
                   "usage", "seconds", "request_id")


# --------------------------------------------------------------- failures

class GlmError(ProviderError):
    """A GLM call failed.  The subclass says how, and `.classification` is
    the machine-readable form of that.  Callers switch on the classification,
    never on the message."""

    classification = "unknown"


class GlmAuthFailed(GlmError):
    classification = "auth"


class GlmQuotaExhausted(GlmError):
    classification = "quota"


class GlmRateLimited(GlmError):
    classification = "rate_limit"


class GlmInvalidRequest(GlmError):
    classification = "invalid_request"


class GlmServerError(GlmError):
    classification = "server_error"


class GlmTimeout(GlmError):
    classification = "timeout"


class GlmTransportError(GlmError):
    classification = "transport"


class GlmMalformedResponse(GlmError):
    classification = "malformed_response"


class GlmUnknownFailure(GlmError):
    classification = "unknown"


# A failure we may try again.  Auth, quota, a validation error and a body we
# could not read are all facts that the next attempt will reproduce exactly.
RETRYABLE = (GlmRateLimited, GlmServerError, GlmTimeout, GlmTransportError)

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
             sleep=time.sleep):
    """Send one bounded prompt.  Return a trimmed dict, or raise a GlmError.

    Parameters
    ----------
    prompt : str
        The user turn.  Refused above MAX_PROMPT_CHARS rather than truncated:
        a silently shortened prompt produces a confident answer to a question
        that was never asked, which is the failure this repository calls a
        silent fallback.
    system : str, optional
        A system turn placed before the prompt.  Counts against the same
        character bound.
    model : str, optional
        Must be in MODELS.  Defaults to ZAI_MODEL, then DEFAULT_MODEL.
    max_tokens : int, optional
        Output cap.  Defaults to DEFAULT_MAX_TOKENS, clamped to
        MAX_TOKENS_CAP.  Always sent, so a runaway generation cannot happen.
    temperature : float
        0 by default.  Deterministic is what engineering work wants.
    timeout : int, optional
        Per-attempt seconds, clamped to GLM_TIMEOUT.
    max_attempts : int, optional
        Total attempts including the first, clamped to MAX_RETRIES + 1.
    sleep : callable
        Backoff injection point.  Tests pass a recorder.

    Returns
    -------
    dict
        Keys exactly RESPONSE_FIELDS.  `model` is what ANSWERED, which is not
        always what was asked for - see SERVES.  `usage` carries the token
        counts the API reported, and a count the API omitted stays None rather
        than becoming zero.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("glm: prompt must be a non-empty string")
    if system is not None and not isinstance(system, str):
        raise ValueError("glm: system must be a string when given")

    size = len(prompt) + len(system or "")
    if size > MAX_PROMPT_CHARS:
        raise ValueError(
            f"glm: {size} characters of context exceeds the bound of "
            f"{MAX_PROMPT_CHARS}. Refusing rather than truncating - a "
            f"shortened prompt answers a different question")

    model = model or configured_model()
    if model not in MODELS:
        raise ValueError(
            f"glm: {model!r} is not in the allowlist. "
            f"Choose from: {', '.join(MODELS)}")

    if not isinstance(temperature, (int, float)) or not 0 <= temperature <= 1:
        raise ValueError(f"glm: temperature {temperature!r} out of range 0..1")

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
        timeout=min(int(timeout or GLM_TIMEOUT), GLM_TIMEOUT),
        max_attempts=max(1, min(int(max_attempts or MAX_RETRIES + 1),
                                MAX_RETRIES + 1)),
        sleep=sleep)

    return _trim(status, data, seconds, model)


def _send(body, timeout, max_attempts, sleep):
    """POST with bounded retry on transient failures only.

    The credential is resolved ONCE, before the loop.  A missing key cannot
    materialise on the second attempt, and spending attempts on it would
    report a configuration problem as an outage.
    """
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
            # Not swallowed and not defaulted: named, redacted and re-raised
            # as `unknown`, which is a classification a caller can act on and
            # an operator can grep for.  The bare clause exists so a surprise
            # cannot escape this module wearing someone else's type.
            raise GlmUnknownFailure(
                f"glm: unexpected {type(e).__name__}: "
                f"{redact(str(e))[:200]}") from None
        else:
            seconds = round(time.monotonic() - started, 3)
            if ok(status):
                return status, data, seconds
            last = _http_failure(status, data)

        if not isinstance(last, RETRYABLE) or attempt >= max_attempts - 1:
            raise last
        sleep(BACKOFF_BASE * (2 ** attempt))

    raise last if last else GlmUnknownFailure(          # pragma: no cover
        "glm: the retry loop ended with no outcome")


def _transport_failure(exc):
    """A failure to reach the endpoint at all, classified.

    `providers._urllib_transport` collapses every network exception into a
    `ProviderError` whose message opens with the original type name, so that
    prefix plus the message body is all there is to read.  A timeout is kept
    apart from the rest because it is the one where the request may well have
    been SERVED - the answer just never came back - and a caller deciding
    whether an action could have happened needs that distinction.
    """
    text = redact(str(exc))
    low = text.lower()
    if "timeout" in low or "timed out" in low:
        return GlmTimeout(f"glm: the call did not return: {text[:200]}")
    return GlmTransportError(f"glm: the endpoint was not reached: {text[:200]}")


# Z.AI answers a business error with {"error": {"code": "...", "message": ...}}.
# Measured: 1211 is an unknown model id, and a bad token is a 401 carrying
# "token expired or incorrect".  The quota codes below are from Z.AI's
# published error table and have NOT been reproduced live - reproducing them
# means exhausting a real plan.  They are therefore a widening of the quota
# class only; anything they do not match still lands on the status code, which
# is never guessed.
QUOTA_CODES = frozenset({"1113", "1112", "1305"})
QUOTA_WORDS = ("insufficient balance", "balance is insufficient", "quota",
               "daily limit", "exceeded your current", "recharge",
               "arrears", "no remaining")


def _http_failure(status, data):
    """A non-2xx answer, classified.  The body is consulted BEFORE the status
    where the status alone cannot tell two different problems apart: a 429 is
    a pace problem when the plan still has budget and a quota problem when it
    does not, and retrying the second one is wasted time by construction.
    """
    note = redact(str(data))[:200]
    code, message = _error_code(data)
    said = f"{code} {message}".lower()

    quota = (code in QUOTA_CODES
             or any(word in said for word in QUOTA_WORDS))

    if status in (401, 403):
        return GlmAuthFailed(
            f"glm: {ENV_KEY} was rejected ({status}): {note}")
    if status == 402 or (quota and status in (429, 400)):
        return GlmQuotaExhausted(f"glm: the plan has no budget left "
                                 f"({status}): {note}")
    if status == 429:
        return GlmRateLimited(f"glm: rate limited ({status}): {note}")
    if status is not None and 400 <= status < 500:
        return GlmInvalidRequest(
            f"glm: the request was refused ({status}): {note}")
    if status is not None and status >= 500:
        return GlmServerError(f"glm: the endpoint faulted ({status}): {note}")
    return GlmUnknownFailure(f"glm: answered {status}: {note}")


def _error_code(data):
    if not isinstance(data, dict):
        return "", ""
    err = data.get("error")
    if not isinstance(err, dict):
        return "", str(data.get("message") or "")
    return str(err.get("code") or ""), str(err.get("message") or "")


def _trim(status, data, seconds, requested):
    """A 2xx body into RESPONSE_FIELDS, or a stated malformed failure.

    Every shape check below has been an outage somewhere: a body that is not
    an object, a `choices` that is not a list, a message with no content. An
    empty completion is refused rather than returned as "", because "" is
    parsed as invalid JSON one layer up, retried, and reported as a schema
    failure - which sends the reader to entirely the wrong problem.
    """
    if not isinstance(data, dict):
        raise GlmMalformedResponse(
            f"glm: answered {status} with a body that is not an object "
            f"({type(data).__name__}), so there is no completion to read")

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise GlmMalformedResponse(
            f"glm: answered {status} with no `choices`, so nothing was "
            f"completed")

    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message")
    message = message if isinstance(message, dict) else {}
    content = message.get("content")
    finish = first.get("finish_reason")

    if not isinstance(content, str) or not content.strip():
        raise GlmMalformedResponse(
            f"glm: answered {status} with an empty completion "
            f"(finish_reason={finish!r}). Refusing rather than returning '', "
            f"which would be read as a bad answer instead of no answer")

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
    """Token counts as the API reported them.

    A count the API omitted stays None.  Zero would be a claim that no tokens
    were spent, and this repository's rule is that missing evidence is never
    positive evidence.
    """
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
    """Configuration readiness by default; one real token if live.

    The default spends nothing and makes no request, matching every other
    adapter here.  `--live` sends a single token so the answer is about the
    endpoint rather than about a file on disk, and reports WHICH MODEL SERVED,
    because the Coding Plan endpoint remaps ids.
    """
    if not live:
        try:
            key(ENV_KEY)
        except MissingKey as e:
            return {"provider": "glm", "ok": False, "status": None,
                    "note": redact(str(e))[:120]}
        return {"provider": "glm", "ok": None, "status": None, "skipped": True,
                "note": f"{ENV_KEY} configured, model {configured_model()}, "
                        f"no call made (--live to spend a token)"}
    try:
        status, data, seconds = _send(
            {"model": configured_model(),
             "messages": [{"role": "user", "content": "ping"}],
             "max_tokens": 1, "temperature": 0, "stream": False},
            timeout=GLM_TIMEOUT, max_attempts=MAX_RETRIES + 1,
            sleep=time.sleep)
    except GlmError as e:
        return {"provider": "glm", "ok": False, "status": None,
                "classification": e.classification,
                "note": redact(str(e))[:120]}
    except MissingKey as e:
        return {"provider": "glm", "ok": False, "status": None,
                "classification": "auth", "note": redact(str(e))[:120]}
    served = data.get("model") if isinstance(data, dict) else None
    return {"provider": "glm", "ok": ok(status), "status": status,
            "classification": None,
            "note": f"requested {configured_model()}, served {served}, "
                    f"{int(seconds * 1000)}ms"}


def main(argv=None):
    p = argparse.ArgumentParser(prog="py -3 -m src.providers.glm")
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
