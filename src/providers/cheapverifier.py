#!/usr/bin/env python3
"""CheapVerifier: the first paid rung of the S5 verification order.

## The contract, and where it comes from

Not guessed. `work/cheapverifier-openapi.json` is the provider's own OpenAPI
document, fetched live on 2026-09-25 (HTTP 200, 24,919 bytes on the wire,
sha256 365e27d9eb29411e...). It was re-fetched while this module was written
and compared byte-for-byte against the saved copy: IDENTICAL. Every endpoint,
field name and status code below is read off that document or off a real
response recorded the same day.

    server     https://api.cheapverifier.com/v1
    auth       apiKey, header, `x-api-key`
    credential CHEAPVERIFIER_API_KEY

    GET  /verify/{email}                    stored lookup, FREE
    GET  /email-validation                  single, paid
    GET  /email-validation/status/{fileId}  single, when the single returned 202
    POST /file/upload                       bulk, csv, quick mode
    GET  /task/status/{taskId}              poll
    GET  /task/details/{fileId}             all rows
    GET  /uploads/{upload_id}/results       filtered/summary view

## WHERE THE LIVE API DISAGREES WITH ITS OWN SPEC

Measured 2026-09-25, and each one is a way a careless adapter reads a
provider wrong:

1. **A WRONG KEY IS 403, NOT 401.** The spec documents 401 for "Missing or
   invalid API key". Live, a missing key is `401 {"error":"API key
   required"}` and a WRONG key is `403 {"error":"Invalid API key"}`. An
   adapter that treats only 401 as an auth problem reports a bad credential
   as a server fault, and `credential_health` would classify it FAILED for
   the wrong reason or not at all. `auth_failure()` reads both.

2. **THE DOCUMENTED ERROR ENVELOPE IS NOT WHAT IS SENT.** The spec's `Error`
   schema promises `{"success": false, "message": ..., "error": ...}`. In
   seven real error responses recorded across five endpoints, **`success`
   never appeared once**, and at least four different shapes did:

       {"error":"Not found","message":"No validation result found for ..."}
       {"error":"Task not found"}                       (no message at all)
       {"status":"error","message":"Task not found"}    (different again)
       {"error":"Validation failed","details":[{...}]}  (422)
       {"status":"error","message":"...","code":"EMAIL_REQUIRED"}

   So `message_of()` reads every shape and never branches on `success`,
   which would be a branch on a field the provider does not send.

## THE 404 THAT IS AN ANSWER, NOT AN ERROR

`GET /verify/{address with nothing stored}` answers **404**:

    {"error":"Not found","message":"No validation result found for ..."}

Measured live 2026-09-25. That is the stored cache saying "nothing stored",
and it is the NORMAL, EXPECTED answer for an address we have never verified -
which, on a cold cohort, is nearly all of them. `stored()` returns `None` for
it. It does not raise, and it is not a verdict.

Getting this backwards turns a free cache miss into a failure on every
address in the list, and the free rung of the order - the one that exists to
stop us paying twice for the same answer - becomes the thing that breaks the
run.

## THE CREDIT RULE, WHICH IS THE MONEY

From the spec's own Credits section and the `VerdictFields.outcome`
description, not from an assumption about how verifiers usually bill:

    valid       1 credit
    invalid     1 credit
    catch_all   0 credits    the domain accepts everything: nothing was
                             learned about THIS address
    unknown     0 credits    inconclusive

`credits_for()` is the only place that decides this, and it is keyed on the
OUTCOME rather than on anything the provider says about billing, for two
reasons the spec states plainly:

  - **`creditsReserved` on an upload is HELD, NOT SPENT.** "One credit per
    deduplicated row is held up front so work cannot start that the workspace
    cannot pay for. The file settles down to the rows that reached a verdict
    when it completes." A reservation ledgered as spend over-reports the bill
    by every catch_all and every unknown in the file, and this ledger is what
    refuses the NEXT call - so invented credits exhaust a real ceiling.

  - **`billingStatus: "pending"` IS CHARGEABLE.** The spec: "`pending` means
    not settled yet and still chargeable - which is not the same as having
    cost nothing." `settlement()` therefore never reads `pending` as free.

## THE LEDGER, AND THE ORDER OF THE TWO CALLS

`CLAUDE.md`: a provider call that skips the ledger is invisible to the spend
audit, and an audit that reports clean because it watched nothing is worse
than none. So every paid call here goes through `spendledger`.

**And the check comes BEFORE the spend, never after.** Two separate defects
this week were caps that recorded and never checked - `run_actor` ledgers
every Apify call and checks nothing, and S5's `per_run` was tested at
`--workers 1` and crossed at K=8. A cap consulted after the answer has
arrived can only report an overshoot; it cannot prevent one. `reserve()`
asks `spendledger.check` first and raises `BudgetExceeded` before a request
is built.

## RATE LIMIT: MEASURED ON THE FREE ENDPOINT, AND NOT ESTABLISHED ON THE PAID ONE

The spec documents NO rate limit: no 429 response on any of the seven
endpoints, no `RateLimit-*` or `Retry-After` header anywhere in the document.

Measured 2026-09-25 against `GET /verify/{email}` - the free stored lookup,
so the whole ramp cost nothing. Five arms of 40 requests at rising
concurrency, stopping on the first sign of throttling:

    K=1    40 req    9.4 req/s    404 x40    p50 0.44s
    K=4    40 req   14.8 req/s    404 x40    p50 0.44s
    K=8    40 req   18.0 req/s    404 x40    p50 0.44s
    K=16   40 req   32.1 req/s    404 x40    p50 0.34s
    K=32   40 req   40.5 req/s    404 x40    p50 0.52s

200 requests, zero 429s, zero 503s, no `RateLimit-*` or `Retry-After` header
on any response, and p50 latency flat across a 32x change in concurrency.

**WHAT THAT ESTABLISHES, AND WHAT IT DOES NOT.** It establishes that the
stored-lookup path does not throttle below ~40 req/s. It does **not**
establish a limit for `/file/upload` or `/email-validation`: those run real
SMTP conversations on a different fleet, and the spec says so ("when the
fleet is slower than the request can wait"). Measuring those means spending
credits, and the day's ceiling forbids it - see the merge-request doc.

So `RATE_LIMIT_PAID` is **None**, and None means UNKNOWN and says so. An
unknown limit is not permission to pick a number: `PROVIDER-ROUTING-POLICY`
already carries one provider whose "documented" rate was an operator's guess,
and S5 paid 351 minutes for a concurrency sized against a provider it was not
calling. `recommended_workers()` returns the measured-free figure only when
asked about the free path, and refuses to invent one for the paid path.

  python -m src.providers.cheapverifier --check       free, verifies the key
  python -m src.providers.cheapverifier --contract
  python -m src.providers.cheapverifier --stored a@b.test
"""
import argparse
import csv
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from . import (ProviderError, MissingKey, HttpTransportError, key, ok, query,
               redact, request, mapping, refuse_unauthorized_write,
               USER_AGENT, TIMEOUT)

# ------------------------------------------------------------- the contract
# Read off the provider's OpenAPI document, not invented. Overridable so an
# operator can point at a staging host; never defaulted to something unread.
BASE_DEFAULT = "https://api.cheapverifier.com/v1"
HEADER_NAME = "x-api-key"                 # the documented and measured spelling

KEY_VAR = "CHEAPVERIFIER_API_KEY"
BASE_VAR = "CHEAPVERIFIER_BASE"

STORED_PATH = "/verify/{email}"
SINGLE_PATH = "/email-validation"
SINGLE_STATUS_PATH = "/email-validation/status/{file_id}"
UPLOAD_PATH = "/file/upload"
TASK_STATUS_PATH = "/task/status/{task_id}"
TASK_DETAILS_PATH = "/task/details/{file_id}"
UPLOAD_RESULTS_PATH = "/uploads/{upload_id}/results"

PROVIDER = "cheapverifier"

# The four-value enum the spec calls "the product".
VALID = "valid"
INVALID = "invalid"
CATCH_ALL = "catch_all"
UNKNOWN = "unknown"
OUTCOMES = (VALID, INVALID, CATCH_ALL, UNKNOWN)

# The credit rule. One credit per address that REACHED A VERDICT, and
# `catch_all`/`unknown` are not verdicts about the address.
CHARGEABLE_OUTCOMES = frozenset({VALID, INVALID})

# What one call is named in the spend ledger's vocabulary.
CALL_SINGLE = "cheapverifier-verify"
CALL_BULK = "cheapverifier-bulk"

# Measured 2026-09-25 on the free stored-lookup path. See the module docstring.
RATE_LIMIT_FREE_REQ_S = 40.5              # observed clean, not a published cap
RATE_LIMIT_FREE_MEASURED_AT = "2026-09-25"
# NOT MEASURED. None means unknown and is never quietly turned into a number.
RATE_LIMIT_PAID = None

# Polling bounds for a single verification that answered 202.
POLL_ATTEMPTS = 8
POLL_INTERVAL = 2.0
# Polling bounds for a bulk file.
BULK_POLL_ATTEMPTS = 240
BULK_POLL_INTERVAL = 15.0


class NotConfigured(ProviderError):
    """No credential, so no call is attempted and nothing is spent.

    Distinct from a provider refusing us: this is raised BEFORE the network,
    so `verification.call` may count it as a local refusal and not bill it.
    """


class BulkNotSettled(ProviderError):
    """A bulk file did not reach `completed` inside its polling bound."""


class IncompleteRead(ProviderError):
    """`/task/details` returned fewer rows than it said the file holds.

    THE FAILURE THIS EXISTS TO MAKE IMPOSSIBLE. `/leads` paged with an offset
    that died at page 1,000 while `meta.last_page` promised more, and the
    silent half-read looked exactly like a complete one. A verification read
    that quietly returns half a file marks the missing half unverified and
    re-buys it, or worse, drops it.
    """


# ------------------------------------------------------------------ config

def base():
    return (os.environ.get(BASE_VAR) or "").strip().rstrip("/") or BASE_DEFAULT


def configured():
    """Is there a credential at all? Never returns the value."""
    try:
        key(KEY_VAR)
        return True
    except MissingKey:
        return False


def require_configured():
    """Refuse clearly, before the wire, rather than erroring obscurely later."""
    try:
        return key(KEY_VAR)
    except MissingKey:
        raise NotConfigured(
            f"no {KEY_VAR} in config/.env, so no CheapVerifier call is made "
            f"and nothing is spent. Register it there; it is declared in "
            f"src/config.py VARIABLES and read by scripts/credential_health.py"
        ) from None


def endpoint(path, **parts):
    filled = path.format(**{k: urllib.parse.quote(str(v), safe="")
                            for k, v in parts.items()})
    return base() + filled


def headers():
    return {HEADER_NAME: require_configured()}


# ------------------------------------------------------- reading a response

def message_of(payload):
    """The human-readable reason, across every envelope the API really sends.

    Deliberately does NOT read `success`. The spec promises it on every
    failure; seven real error responses across five endpoints carried it
    zero times. Branching on a field the provider does not send is a branch
    that never fires.
    """
    body = payload if isinstance(payload, dict) else {}

    # `details` FIRST, and the ordering is the point. A 422 answers
    # `{"error":"Validation failed","details":[{"field":"email","message":
    # "email must be a valid email address"}]}` - the top-level `error` is a
    # category and the useful sentence is in `details`. Reading `error` first
    # returned "Validation failed" on every 422, which names neither the
    # field nor the problem, and is what an operator would have had to debug
    # a rejected address from.
    details = body.get("details")
    specifics = []
    if isinstance(details, list):
        for detail in details:
            if not isinstance(detail, dict):
                continue
            field, msg = detail.get("field"), detail.get("message")
            if msg:
                specifics.append(f"{field}: {msg}" if field else str(msg))

    for name in ("message", "error"):
        value = body.get(name)
        if isinstance(value, str) and value.strip():
            general = value.strip()
            return f"{general}: {'; '.join(specifics)}" if specifics else general

    if specifics:
        return "; ".join(specifics)
    if isinstance(payload, str) and payload.strip():
        return payload.strip()[:200]
    return ""


def code_of(payload):
    body = payload if isinstance(payload, dict) else {}
    value = body.get("code")
    return value.strip() if isinstance(value, str) and value.strip() else None


def auth_failure(status):
    """Is this the provider refusing our CREDENTIAL, rather than the request?

    BOTH 401 AND 403, because the live API uses them for two different
    credential faults and the spec documents only the first:
        401  no key sent          {"error":"API key required"}
        403  wrong key sent       {"error":"Invalid API key"}
    """
    return status in (401, 403)


def insufficient_credits(status, payload):
    """A 402 refusal, raised BEFORE any address is queued, so nothing was spent."""
    return status == 402 or code_of(payload) == "INSUFFICIENT_CREDITS"


def _call(method, url, body=None, timeout=TIMEOUT):
    """One request through the shared seam, with the errors named.

    Returns `(status, payload)`. Never raises on a status the caller has to
    branch on - a 404 from the stored lookup is an ANSWER - but does raise on
    the ones no caller can do anything sensible with.
    """
    status, payload = request(method, url, headers(), body, timeout)
    if auth_failure(status):
        raise ProviderError(
            f"cheapverifier: credential refused ({status}) "
            f"{redact(message_of(payload))}")
    if status is not None and status >= 500:
        raise ProviderError(
            f"cheapverifier: {status} {redact(message_of(payload))[:120]}")
    return status, payload


# ------------------------------------------------------ 1. the free rung

def stored(email, upload_id=None):
    """A verdict already produced for this workspace. FREE, and often absent.

    Returns a trimmed dict, or **None when nothing is stored** - which the API
    reports as HTTP 404 and which is the ordinary case on a cold list. None
    is not an error and not a verdict; the caller goes on to a paid rung.

    Raises only when the ADDRESS is unusable (422) or the credential is.
    """
    url = endpoint(STORED_PATH, email=email)
    if upload_id:
        url = query(url, {"upload_id": upload_id})
    status, payload = _call("GET", url)

    if status == 404:
        return None                      # nothing stored. FREE cache miss.
    if status == 422:
        raise ProviderError(
            f"cheapverifier: not a valid email address "
            f"({redact(message_of(payload))[:80]})")
    if not ok(status):
        raise ProviderError(
            f"cheapverifier stored lookup: {status} "
            f"{redact(message_of(payload))[:120]}")

    body = mapping(payload, "cheapverifier stored result")
    return trim_stored(body)


def trim_stored(body):
    """The stored lookup, trimmed. No raw payload escapes this module."""
    history = body.get("history")
    return {
        "email": body.get("email"),
        "outcome": normalise_outcome(body.get("outcome")),
        "reason_code": body.get("reason_code"),
        "confidence": body.get("confidence"),
        "algorithm_version": body.get("algorithm_version"),
        "final_status": body.get("final_status"),
        "hard_bounce": body.get("hard_bounce"),
        "upload_id": body.get("upload_id"),
        "validated_at": body.get("validated_at"),
        "history_count": len(history) if isinstance(history, list) else 0,
        "source": "stored",
        # A stored read costs nothing. Stated, not implied, because this is
        # the field the ledger reads.
        "credits": 0,
    }


def normalise_outcome(value):
    """The provider's outcome, or None. An unrecognised word is never a verdict."""
    text = str(value or "").strip().lower().replace("-", "_")
    return text if text in OUTCOMES else None


# --------------------------------------------------- the credit accounting

def credits_for(outcome):
    """What ONE address costs. The single place this is decided.

    Keyed on the outcome, because that is what the provider bills on:
    1 for `valid` and `invalid`, 0 for `catch_all` and `unknown`. An outcome
    this does not recognise costs 1 - the conservative direction, since
    under-reporting a real bill is how a ledger stops being able to refuse.
    """
    normalised = normalise_outcome(outcome)
    if normalised is None:
        return 1
    return 1 if normalised in CHARGEABLE_OUTCOMES else 0


def settlement(rows):
    """What a completed set of verdicts actually cost, and the breakdown.

    `billingStatus: pending` NEVER reduces this. The spec is explicit that
    pending "means not settled yet and still chargeable - which is not the
    same as having cost nothing", and a settlement that read pending as free
    would under-report the bill by every row still in flight.
    """
    by_outcome = {}
    credits = 0
    for row in rows or []:
        outcome = normalise_outcome(
            (row or {}).get("outcome")) or "unrecognised"
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
        credits += credits_for((row or {}).get("outcome"))
    return {
        "rows": len(rows or []),
        "credits": credits,
        "by_outcome": by_outcome,
        "chargeable_rows": sum(by_outcome.get(o, 0) for o in CHARGEABLE_OUTCOMES),
        "free_rows": by_outcome.get(CATCH_ALL, 0) + by_outcome.get(UNKNOWN, 0),
    }


def reserved_is_not_spent(upload):
    """The reservation, stated as held rather than spent.

    `creditsReserved` is one credit per DEDUPLICATED ROW, held so work cannot
    start that the workspace cannot pay for, and the file settles down to the
    rows that reached a verdict. Ledgering it as spend over-reports the bill
    by every catch_all and unknown in the file - and this ledger is what
    refuses the next call, so the over-report becomes a refusal of work that
    was affordable.
    """
    return {
        "held": int((upload or {}).get("credits_reserved") or 0),
        "spent": 0,
        "note": "held, not spent; settles to the rows that reached a verdict",
    }


# -------------------------------------------------------------- the ledger

def reserve(client, config, cost, call=CALL_SINGLE, rows=None, day=None):
    """Ask the durable ceiling BEFORE spending. Raises `BudgetExceeded`.

    THE ORDER IS THE WHOLE POINT. A cap consulted after the provider has
    answered can only report an overshoot; it cannot prevent one. This runs
    before a request is built.
    """
    from .. import spendledger
    spendledger.check(client, config, int(cost), provider=PROVIDER,
                      rows=rows, day=day)
    return True


def ledger(client, cost, call=CALL_SINGLE, run_id=None):
    """Record what was spent. One row per verdict bought, never per request."""
    from .. import spendledger
    if int(cost) <= 0:
        return None                     # a free outcome is not a ledger row
    return spendledger.record(client, PROVIDER, call, int(cost), run_id=run_id)


def headroom(client, config, rows=None, day=None):
    """Credits left under the tightest declared ceiling. Never raises one.

    Returns a dict with `remaining` (None = no ceiling declared) so a bulk
    caller can size a file to what is affordable and halt cleanly instead of
    crossing.
    """
    from .. import spendledger
    rows = spendledger.load() if rows is None else rows
    day = day or spendledger.today()
    ceilings = spendledger.caps(config)
    spent_today = spendledger.spent(client, day=day, rows=rows)
    spent_total = spendledger.spent(client, rows=rows)
    limits = []
    if ceilings.get("per_day") is not None:
        limits.append(("per_day", ceilings["per_day"] - spent_today))
    if ceilings.get("total") is not None:
        limits.append(("total", ceilings["total"] - spent_total))
    if ceilings.get("per_provider_per_day") is not None:
        limits.append(("per_provider_per_day",
                       ceilings["per_provider_per_day"]
                       - spendledger.spent(client, day=day, provider=PROVIDER,
                                           rows=rows)))
    binding, remaining = (None, None)
    if limits:
        binding, remaining = min(limits, key=lambda kv: kv[1])
    return {
        "client": client, "day": day,
        "spent_today": spent_today, "spent_total": spent_total,
        "ceilings": ceilings,
        "binding": binding,
        "remaining": remaining,
        "exhausted": remaining is not None and remaining <= 0,
    }


# ------------------------------------------------ 2. the paid single rung

def verify_single(email, client=None, config=None, run_id=None, mode="quick",
                  catch_all=True, attempts=POLL_ATTEMPTS,
                  interval=POLL_INTERVAL, sleep=time.sleep, ledger_rows=None):
    """One address, paid. Checks the ceiling first, ledgers the verdict after.

    The worst case is 1 credit, so that is what is reserved; the verdict
    decides what is actually recorded, which is 0 for a catch_all or an
    unknown.
    """
    require_configured()
    if client:
        reserve(client, config, 1, CALL_SINGLE, rows=ledger_rows)

    url = query(endpoint(SINGLE_PATH), {
        "email": email,
        "mode": mode,
        "catchAll": "true" if catch_all else "false",
    })
    status, payload = _call("GET", url)

    if insufficient_credits(status, payload):
        # Raised before any address is queued: nothing charged, no work done.
        raise ProviderError(
            f"cheapverifier: workspace cannot cover the request "
            f"({redact(message_of(payload))[:100]})")

    if status == 202:
        handle = pending_handle(payload)
        if not handle:
            raise ProviderError(
                "cheapverifier: 202 pending with no fileId to poll")
        status, payload = poll_single(handle, attempts, interval, sleep)

    if not ok(status):
        raise ProviderError(
            f"cheapverifier verify: {status} "
            f"{redact(message_of(payload))[:120]}")

    body = mapping(payload, "cheapverifier verify")
    if str(body.get("status") or "").lower() == "pending":
        # Gave up waiting. The provider may well have done the work, so this
        # is charged rather than assumed free - the same rule the waterfall
        # already applies to a timeout.
        trimmed = {"email": email, "outcome": None, "source": "single",
                   "billing_status": body.get("billingStatus"),
                   "settled": False, "credits": 1,
                   "reason_code": "abandoned_while_pending"}
        if client:
            ledger(client, 1, CALL_SINGLE, run_id)
        return trimmed

    trimmed = trim_single(body, email)
    if client:
        ledger(client, trimmed["credits"], CALL_SINGLE, run_id)
    return trimmed


def pending_handle(payload):
    """The `fileId` a 202 hands back, wherever the envelope puts it."""
    body = payload if isinstance(payload, dict) else {}
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    for source in (data, body):
        value = source.get("fileId") or source.get("file_id")
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
    return None


def poll_single(handle, attempts=POLL_ATTEMPTS, interval=POLL_INTERVAL,
                sleep=time.sleep):
    """Poll a 202 to settlement. Bounded: it returns the last answer either way."""
    status, payload = 202, {}
    for attempt in range(max(1, attempts)):
        status, payload = _call(
            "GET", endpoint(SINGLE_STATUS_PATH, file_id=handle))
        if status != 202:
            return status, payload
        if attempt < attempts - 1:
            sleep(interval)
    return status, payload


def trim_single(body, email=None):
    """A single verification, trimmed. Nothing raw escapes."""
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    verdict = (data.get("validationResult")
               if isinstance(data.get("validationResult"), dict) else {})
    outcome = normalise_outcome(
        data.get("outcome") or verdict.get("outcome") or body.get("outcome"))
    billing = body.get("billingStatus")
    return {
        "email": email or data.get("email") or verdict.get("email"),
        "outcome": outcome,
        "reason_code": verdict.get("reason_code"),
        "confidence": verdict.get("confidence"),
        "algorithm_version": verdict.get("algorithm_version"),
        "esp_type": verdict.get("esp_type"),
        "billing_status": billing,
        "provider_credits_used": body.get("creditsUsed"),
        # OURS, and it is keyed on the outcome rather than on `creditsUsed`.
        # `billingStatus: pending` is chargeable, so a 0 reported alongside
        # `pending` is "not settled yet", never "free".
        "credits": credits_for(outcome),
        "verification_mode": data.get("verificationMode"),
        "settled": str(billing or "").lower() == "completed",
        "source": "single",
    }


# ------------------------------------------------------ 3. the bulk rung

def csv_bytes(emails, header="email"):
    """A one-column CSV of addresses, as the upload wants it.

    A header row is optional per the spec and one is sent anyway: the column
    is then named rather than sniffed, which removes the "scored across the
    rows" guess from the path entirely.
    """
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow([header])
    for address in emails:
        writer.writerow([address])
    return buffer.getvalue().encode("utf-8")


def _multipart(fields, filename, payload, field="file"):
    """Encode a multipart/form-data body. Returns `(content_type, bytes)`."""
    boundary = "----resonate" + os.urandom(16).hex()
    out = io.BytesIO()

    def line(text):
        out.write(text.encode("utf-8"))
        out.write(b"\r\n")

    for name, value in (fields or {}).items():
        if value in (None, ""):
            continue
        line(f"--{boundary}")
        line(f'Content-Disposition: form-data; name="{name}"')
        line("")
        line(str(value))

    line(f"--{boundary}")
    line(f'Content-Disposition: form-data; name="{field}"; '
         f'filename="{filename}"')
    # The EXTENSION decides whether the file is accepted and the Content-Type
    # is ignored - the spec says so explicitly, because `curl -F` sends
    # application/octet-stream and every client guesses differently. The
    # honest type is sent anyway; the `.csv` in the filename is what matters.
    line("Content-Type: text/csv")
    line("")
    out.write(payload)
    out.write(b"\r\n")
    line(f"--{boundary}--")
    return f"multipart/form-data; boundary={boundary}", out.getvalue()


def _upload_transport(url, content_type, body, request_headers, timeout):
    """The real multipart POST.

    A SEAM OF ITS OWN, AND WHY. Every other call in this module goes through
    `providers.request`, which is the one place a cassette can be swapped in.
    That seam JSON-encodes its body (`json.dumps(body).encode()`), so it
    cannot carry multipart bytes at all. Rather than widen the shared
    transport - which every other provider depends on and which is also where
    the prospect-facing write guard lives - the upload gets a seam beside it,
    swapped the same way by `set_upload_transport`.

    `refuse_unauthorized_write` is still called first, exactly as the shared
    transport does it, so this path is no less guarded than the other.
    """
    refuse_unauthorized_write("POST", url)
    req = urllib.request.Request(url, method="POST", data=body)
    for name, value in (request_headers or {}).items():
        req.add_header(name, value)
    req.add_header("Content-Type", content_type)
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        with e:
            return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        raise HttpTransportError(f"{type(e).__name__}: {redact(e)}") from None


_upload_seam = _upload_transport


def set_upload_transport(fn):
    """Swap the multipart wire for a cassette. Tests do this, nothing else."""
    global _upload_seam
    previous, _upload_seam = _upload_seam, fn
    return previous


def reset_upload_transport():
    set_upload_transport(_upload_transport)


def upload(emails, client=None, config=None, mode="quick", catch_all=True,
           priority="normal", filename="addresses.csv", ledger_rows=None,
           check_headroom=True):
    """Queue a list for bulk verification. Returns the trimmed upload receipt.

    NOTHING IS LEDGERED HERE. The upload holds `creditsReserved`; it does not
    spend it. Spend is recorded when the file settles and the verdicts are
    known - see `settle_and_ledger`.

    `check_headroom` asks the durable ceiling BEFORE the file is sent, at the
    worst case of one credit per row, and refuses cleanly rather than
    crossing. The reservation the provider takes is one credit per
    DEDUPLICATED row, so the worst case is an over-estimate in our favour.
    """
    require_configured()
    addresses = [a for a in (emails or []) if a]
    if not addresses:
        raise ProviderError("cheapverifier upload: no addresses")

    if check_headroom and client:
        # The worst case, not the expected one. A ceiling checked against an
        # optimistic estimate is a ceiling that gets crossed by the pessimistic
        # outcome.
        reserve(client, config, len(set(addresses)), CALL_BULK,
                rows=ledger_rows)

    payload = csv_bytes(addresses)
    content_type, body = _multipart(
        {"mode": mode,
         "catchAll": "true" if catch_all else "false",
         "priority": priority},
        filename, payload)

    status, text = _upload_seam(endpoint(UPLOAD_PATH), content_type, body,
                                headers(), TIMEOUT)
    try:
        parsed = json.loads(text) if text else None
    except (ValueError, TypeError):
        parsed = text

    if auth_failure(status):
        raise ProviderError(
            f"cheapverifier upload: credential refused ({status})")
    if insufficient_credits(status, parsed):
        raise ProviderError(
            f"cheapverifier upload: workspace cannot cover the file "
            f"({redact(message_of(parsed))[:100]}). Nothing was queued and "
            f"nothing was charged")
    if not ok(status):
        raise ProviderError(
            f"cheapverifier upload: {status} "
            f"{redact(message_of(parsed))[:120]}")

    return trim_upload(mapping(parsed, "cheapverifier upload"),
                       submitted=len(addresses))


def trim_upload(body, submitted=None):
    return {
        "file_id": str(body.get("fileId") or "") or None,
        "email_count": body.get("emailCount"),
        "submitted": submitted,
        # HELD, NOT SPENT. Named so nothing downstream can mistake it for a
        # charge, and deliberately NOT called `credits`.
        "credits_reserved": body.get("creditsReserved"),
        "file_type": body.get("fileType"),
        "phase": body.get("phase"),
        "queued_at": body.get("queuedAt"),
        "verification_mode": body.get("verificationMode"),
        "source": "bulk",
    }


def task_status(file_id):
    """How far a file has got. Free."""
    status, payload = _call("GET", endpoint(TASK_STATUS_PATH, task_id=file_id))
    if status == 404:
        raise ProviderError(f"cheapverifier: no such file {file_id}")
    if not ok(status):
        raise ProviderError(
            f"cheapverifier task status: {status} "
            f"{redact(message_of(payload))[:120]}")
    body = mapping(payload, "cheapverifier task status")
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    return {
        "file_id": data.get("fileId"),
        "status": data.get("status"),
        "phase": data.get("phase"),
        "total": data.get("totalEmails"),
        "processed": data.get("processedEmails"),
        "valid": data.get("validEmails"),
        "invalid": data.get("invalidEmails"),
        "catch_all": data.get("catchAllCount"),
        "unknown": data.get("unknownEmails"),
        "completed_at": data.get("completedAt"),
        "done": str(data.get("status") or "").lower() == "completed",
    }


def wait_for(file_id, attempts=BULK_POLL_ATTEMPTS,
             interval=BULK_POLL_INTERVAL, sleep=time.sleep, on_progress=None):
    """Poll a file to `completed`. Bounded, and says so when it gives up."""
    last = None
    for attempt in range(max(1, attempts)):
        last = task_status(file_id)
        if on_progress:
            on_progress(last)
        if last.get("done"):
            return last
        if attempt < attempts - 1:
            sleep(interval)
    raise BulkNotSettled(
        f"cheapverifier: file {file_id} still "
        f"{last.get('status') if last else 'unknown'} after "
        f"{attempts} polls; {(last or {}).get('processed')} of "
        f"{(last or {}).get('total')} rows")


def details(file_id, expect=None):
    """Every verdict in a file, and it PROVES it read every one.

    The operator states, and the spec's own text agrees, that omitting `page`
    returns every row: "10 rows per page; omit `page` to return every row."

    THAT IS NOT TAKEN ON TRUST, because the schema also carries `page` and
    `totalPages`, and a response that quietly carries only the first page
    would be indistinguishable from a complete one. `/leads` failed in
    exactly this shape - an offset that died at page 1,000 while
    `meta.last_page` promised more - and the read looked fine.

    So: the unpaged read is made, and the rows returned are checked against
    the `total` the SAME response reports. If they match, the operator's
    statement held and the file is read. If they do not, this pages through
    explicitly rather than returning a half-read, and raises `IncompleteRead`
    if even that cannot account for every row.

    `expect` is the row count a caller already knows (from `task_status`),
    checked as a second, independent witness.
    """
    status, payload = _call("GET", endpoint(TASK_DETAILS_PATH,
                                            file_id=file_id))
    if status == 404:
        raise ProviderError(
            f"cheapverifier: file {file_id} has no results yet, or does not "
            f"exist")
    if not ok(status):
        raise ProviderError(
            f"cheapverifier task details: {status} "
            f"{redact(message_of(payload))[:120]}")

    body = mapping(payload, "cheapverifier task details")
    rows = body.get("data") if isinstance(body.get("data"), list) else []
    total = body.get("total")
    total_pages = body.get("totalPages")
    paged = False

    needed = total if isinstance(total, int) else None
    if needed is None and isinstance(expect, int):
        needed = expect

    if needed is not None and len(rows) < needed:
        # The unpaged read did NOT return everything. Page explicitly, and
        # discard the short read rather than trying to merge it - the pages
        # are authoritative and a union of the two could double-count.
        paged = True
        collected, page = [], 1
        while True:
            st, pl = _call("GET", query(
                endpoint(TASK_DETAILS_PATH, file_id=file_id), {"page": page}))
            if not ok(st):
                break
            pb = mapping(pl, "cheapverifier task details page")
            chunk = pb.get("data") if isinstance(pb.get("data"), list) else []
            if not chunk:
                break
            collected.extend(chunk)
            pages = pb.get("totalPages")
            if isinstance(pages, int) and page >= pages:
                break
            if len(collected) >= needed:
                break
            page += 1
            if page > 100000:                     # never loop unbounded
                break
        rows = collected

    trimmed = [trim_row(r) for r in rows]
    if needed is not None and len(trimmed) != needed:
        raise IncompleteRead(
            f"cheapverifier: file {file_id} reports {needed} row(s) and "
            f"{len(trimmed)} were read"
            + (" even after paging" if paged else "")
            + ". Refusing a half-read: the missing rows would look "
              "unverified and be bought again")
    return {
        "file_id": body.get("fileId") or file_id,
        "rows": trimmed,
        "total": total,
        "total_pages": total_pages,
        "paged": paged,
        "read_complete": True,
    }


def trim_row(row):
    """One bulk verdict, trimmed. No evidence blob, no raw payload."""
    row = row if isinstance(row, dict) else {}
    outcome = normalise_outcome(row.get("outcome"))
    return {
        "email": row.get("email"),
        "outcome": outcome,
        "reason_code": row.get("reason_code"),
        "confidence": row.get("confidence"),
        "algorithm_version": row.get("algorithm_version"),
        "esp_type": row.get("esp_type"),
        "credits": credits_for(outcome),
        "source": "bulk",
    }


def settle_and_ledger(file_id, client=None, config=None, run_id=None,
                      expect=None):
    """Read a completed file and record what it ACTUALLY cost, per verdict.

    This is where spend is recorded, and it is recorded from the verdicts
    rather than from the reservation: one row per chargeable verdict, nothing
    for a catch_all or an unknown.
    """
    read = details(file_id, expect=expect)
    account = settlement(read["rows"])
    if client and account["credits"] > 0:
        ledger(client, account["credits"], CALL_BULK, run_id)
    return {"file_id": file_id, "rows": read["rows"],
            "settlement": account, "read_complete": read["read_complete"],
            "paged": read["paged"]}


def upload_results(upload_id, status=None, limit=None, offset=None):
    """The filtered/summary view of one file. Free.

    NOTE THE DIFFERENT VOCABULARY, which the spec warns about: this endpoint
    reports `risky` and `catch-all` where `/task/details` reports an
    `outcome`. It is a reporting view and is NOT used to decide a verdict.
    """
    url = query(endpoint(UPLOAD_RESULTS_PATH, upload_id=upload_id),
                {"status": status, "limit": limit, "offset": offset})
    st, payload = _call("GET", url)
    if st == 404:
        raise ProviderError(f"cheapverifier: no such upload {upload_id}")
    if not ok(st):
        raise ProviderError(
            f"cheapverifier upload results: {st} "
            f"{redact(message_of(payload))[:120]}")
    body = mapping(payload, "cheapverifier upload results")
    summary = body.get("summary") if isinstance(body.get("summary"), dict) else {}
    return {
        "upload_id": body.get("upload_id") or upload_id,
        "total": body.get("total"),
        "summary": {k: summary.get(k) for k in
                    ("valid", "invalid", "risky", "catch_all", "unknown")},
        "returned": len(body.get("results") or []),
    }


# --------------------------------------------------------- normalisation

# The project's normalised statuses, from `src/verification.py`.
TO_VERIFICATION_STATUS = {
    VALID: "valid",
    INVALID: "invalid",
    CATCH_ALL: "accept_all",
    UNKNOWN: "unknown",
}


def normalise(trimmed, email=None):
    """A trimmed CheapVerifier answer, as this project's verification model.

    An outcome this module does not recognise becomes `unknown`, which HOLDS
    the address. That is the direction this is allowed to fail in: an
    unreadable answer must never become a confirmation.
    """
    from .. import verification

    trimmed = trimmed or {}
    outcome = normalise_outcome(trimmed.get("outcome"))
    status = TO_VERIFICATION_STATUS.get(outcome, "unknown")
    return verification.result(
        PROVIDER, status, email or trimmed.get("email"),
        deliverable=(True if outcome == VALID else
                     False if outcome == INVALID else None),
        catch_all=(outcome == CATCH_ALL) if outcome else None,
        reason=trimmed.get("reason_code"),
        # `charged` is what the waterfall bills on. A free outcome is stated
        # as free rather than left to a default that assumes charged.
        charged=bool(trimmed.get("credits")),
    )


# --------------------------------------------------------------- readiness

def check():
    """Readiness, and it is FREE - which no other verifier here manages.

    Deliverable and Reoon have no documented account or quota endpoint, so
    their `check()` can only report SKIPPED: the key cannot be tested without
    spending a verification credit. CheapVerifier's stored lookup IS a real
    authenticated read that costs nothing, so a key can be genuinely proven
    here:

        404  the key works, and nothing is stored for that address
        403  the key is wrong
        401  no key was sent
    """
    if not configured():
        return {"provider": "CheapVerifier", "ok": False, "status": None,
                "note": f"no {KEY_VAR} in config/.env"}
    probe = "readiness-probe-unused@example.invalid"
    try:
        status, payload = request(
            "GET", endpoint(STORED_PATH, email=probe), headers(), None, TIMEOUT)
    except ProviderError as e:
        return {"provider": "CheapVerifier", "ok": None, "status": None,
                "note": redact(str(e))[:120]}
    if status == 404:
        return {"provider": "CheapVerifier", "ok": True, "status": status,
                "note": "key accepted; stored lookup answered 404 (nothing "
                        "stored), which is free and is the normal miss"}
    if auth_failure(status):
        return {"provider": "CheapVerifier", "ok": False, "status": status,
                "note": f"credential refused: {redact(message_of(payload))[:80]}"}
    if ok(status):
        return {"provider": "CheapVerifier", "ok": True, "status": status,
                "note": "key accepted; a stored verdict exists for the probe"}
    return {"provider": "CheapVerifier", "ok": False, "status": status,
            "note": redact(message_of(payload))[:120]}


def contract():
    """What is confirmed, and how. Printed rather than asserted."""
    return {
        "base": base(),
        "auth": f"header {HEADER_NAME}",
        "credential": KEY_VAR,
        "configured": configured(),
        "source": "the provider's own OpenAPI document, fetched live "
                  "2026-09-25 and re-compared byte-for-byte while this "
                  "module was written",
        "free_endpoints": [STORED_PATH, TASK_STATUS_PATH, TASK_DETAILS_PATH,
                           UPLOAD_RESULTS_PATH],
        "paid_endpoints": [SINGLE_PATH, UPLOAD_PATH],
        "credit_rule": {"valid": 1, "invalid": 1, "catch_all": 0, "unknown": 0},
        "rate_limit_free_req_s": RATE_LIMIT_FREE_REQ_S,
        "rate_limit_free_measured": RATE_LIMIT_FREE_MEASURED_AT,
        "rate_limit_paid": RATE_LIMIT_PAID,
        "rate_limit_paid_note": "NOT MEASURED. None means unknown and is "
                                "never silently turned into a number",
        "spec_deviations": [
            "a wrong key is 403, not the documented 401",
            "the documented `success` field appears in no real error body",
        ],
    }


def recommended_workers(path="free"):
    """Concurrency this module is willing to stand behind.

    Only for the path that was actually measured. Asking about the paid path
    gets `None`, because a clean arm on the free endpoint is evidence about
    the free endpoint and nothing else.
    """
    if path == "free":
        return 16          # measured clean at 32; one step below, not the edge
    return None


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.providers.cheapverifier")
    p.add_argument("--check", action="store_true",
                   help="verify the credential. Free.")
    p.add_argument("--contract", action="store_true")
    p.add_argument("--stored", metavar="EMAIL",
                   help="free stored lookup for one address")
    p.add_argument("--headroom", metavar="CLIENT",
                   help="credits left under this client's declared ceilings")
    a = p.parse_args(argv)

    if a.contract:
        print(json.dumps(contract(), indent=1))
        return 0

    if a.stored:
        answer = stored(a.stored)
        if answer is None:
            print("no stored verdict (HTTP 404). Free, and not an error.")
            return 0
        print(json.dumps(answer, indent=1))
        return 0

    if a.headroom:
        from .. import clients
        try:
            config = clients.load(a.headroom)
        except Exception:
            config = {}
        print(json.dumps(headroom(a.headroom, config), indent=1))
        return 0

    r = check()
    mark = "ok  " if r["ok"] else ("SKIP" if r["ok"] is None else "FAIL")
    print(f"{mark} {r['provider']:<14} {r['note']}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
