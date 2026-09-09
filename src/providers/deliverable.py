#!/usr/bin/env python3
"""Deliverable: the second opinion in the verification waterfall.

## What is confirmed, and what is not

The transport contract below comes from the provider's own API page
(https://deliverable.co/api), not from guesswork:

    base            https://api.deliverable.co/gateway
    submit          POST /verify/single        {"email": ...}   -> a task id
    poll            POST /verify/single/status {"task_id": ...} -> the answer
    auth            the header  x-api-key: <api key>

Verification is therefore ASYNCHRONOUS: one call submits and a second call
collects. An earlier draft of this module assumed a single synchronous request;
that assumption was wrong and has been removed.

What the documentation does NOT give is the RESPONSE: no field names, no status
values, no error shape. So the normaliser below still reads the spellings
verifiers commonly use, `unmapped_fields()` still reports anything it did not
expect, and an unrecognised answer still degrades to `unknown` rather than to
`valid`. Until one real response has been seen and checked, `verify()` refuses:

    python -m src.validate --provider deliverable --live-validation --max-credits 1

then set DELIVERABLE_RESULT_SHAPE=confirmed. That refusal is the only thing
standing between an unread contract and a credit spent on an answer this code
might not be able to read.

There is no documented account, credit, quota or ping endpoint, so there is no
way to test the key without verifying an address. `check()` reports SKIPPED and
spends nothing.

  python -m src.providers.deliverable --check
  python -m src.providers.deliverable --contract
"""
import argparse
import os
import re
import time

from . import ProviderError, key, ok, query, request, result, failed

# Confirmed from the provider's API documentation. Overridable, not invented.
BASE_DEFAULT = "https://api.deliverable.co/gateway"
VERIFY_DEFAULT = "/verify/single"
STATUS_DEFAULT = "/verify/single/status"
AUTH_DEFAULT = "header"
METHOD_DEFAULT = "POST"
HEADER_NAME = "x-api-key"                # the documented spelling

BASE_VAR = "DELIVERABLE_BASE"
PATH_VAR = "DELIVERABLE_VERIFY"
STATUS_VAR = "DELIVERABLE_STATUS"
AUTH_VAR = "DELIVERABLE_AUTH"
METHOD_VAR = "DELIVERABLE_METHOD"
SHAPE_VAR = "DELIVERABLE_RESULT_SHAPE"   # "confirmed" once a real answer is read
KEY_VAR = "DELIVERABLE_KEY"

AUTH_STYLES = ("header", "bearer", "query")

COST_PER_VERIFY = 1          # one verification credit, like every other verifier
POLL_ATTEMPTS = 6
POLL_INTERVAL = 2.0


class ContractNotVerified(ProviderError):
    """Some part of the contract is unconfirmed, so no call is made."""


def env(name, default):
    value = (os.environ.get(name) or "").strip()
    return value if value else default


def settings():
    """The contract in force: documented defaults unless overridden."""
    return {
        "base": env(BASE_VAR, BASE_DEFAULT).rstrip("/"),
        "path": env(PATH_VAR, VERIFY_DEFAULT),
        "status_path": env(STATUS_VAR, STATUS_DEFAULT),
        "auth": env(AUTH_VAR, AUTH_DEFAULT).lower(),
        "method": env(METHOD_VAR, METHOD_DEFAULT).upper(),
    }


def configure(base=None, path=None, auth=None, method=None, status_path=None,
              result_shape=None):
    """Override the contract. Used by an operator and by the tests."""
    for var, value in ((BASE_VAR, base), (PATH_VAR, path), (AUTH_VAR, auth),
                       (METHOD_VAR, method), (STATUS_VAR, status_path),
                       (SHAPE_VAR, result_shape)):
        if value is not None:
            os.environ[var] = str(value)
    return settings()


def transport_gaps():
    """Anything missing from the request half of the contract."""
    current = settings()
    gaps = []
    if not current["base"]:
        gaps.append(f"{BASE_VAR}: the API base URL")
    if not current["path"]:
        gaps.append(f"{PATH_VAR}: the verification endpoint path")
    if current["auth"] not in AUTH_STYLES:
        gaps.append(f"{AUTH_VAR}: how the key is sent, one of {', '.join(AUTH_STYLES)}")
    if current["method"] not in ("GET", "POST"):
        gaps.append(f"{METHOD_VAR}: GET or POST")
    if current["method"] == "POST" and not current["status_path"]:
        gaps.append(f"{STATUS_VAR}: the path that collects an asynchronous result")
    return gaps


def result_shape_confirmed():
    """Has a real response been seen and the normaliser checked against it?"""
    return env(SHAPE_VAR, "").lower() in ("confirmed", "1", "true", "yes")


def contract_gaps():
    """Everything still unconfirmed, request half and response half alike."""
    gaps = transport_gaps()
    if not result_shape_confirmed():
        gaps.append(
            f"{SHAPE_VAR}: the response shape is undocumented and has not been "
            "read from a real answer")
    return gaps


def contract_verified():
    return not contract_gaps()


def require_transport():
    gaps = transport_gaps()
    if gaps:
        raise ContractNotVerified(
            "the Deliverable request contract is incomplete. Missing: "
            + "; ".join(gaps))


def require_contract():
    require_transport()
    if not result_shape_confirmed():
        raise ContractNotVerified(
            "Deliverable's response shape is undocumented and has not been read "
            "from a real answer, so a credit spent now might buy an answer this "
            "adapter cannot interpret. Read one first with "
            "python -m src.validate --provider deliverable --live-validation "
            f"--max-credits 1, then set {SHAPE_VAR}=confirmed")


# ------------------------------------------------------------ the request

def authorise(url, headers, api_key):
    """Put the key where the contract says it travels."""
    style = settings()["auth"]
    if style == "header":
        headers[HEADER_NAME] = api_key
    elif style == "bearer":
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        url = query(url, {"api_key": api_key})
    return url


def endpoint(path):
    current = settings()
    return f"{current['base']}{path if path.startswith('/') else '/' + path}"


def build_request(email):
    """The exact submit request that would be sent. Built without sending it."""
    require_transport()
    current = settings()
    api_key = key(KEY_VAR)
    url = endpoint(current["path"])
    headers, body = {}, None

    if current["method"] == "GET":
        url = query(url, {"email": email})
    else:
        body = {"email": email}
    url = authorise(url, headers, api_key)
    return {"method": current["method"], "url": url, "headers": headers, "body": body}


def build_status_request(handle):
    """The poll that collects an asynchronous answer."""
    require_transport()
    api_key = key(KEY_VAR)
    url = endpoint(settings()["status_path"])
    headers = {}
    url = authorise(url, headers, api_key)
    return {"method": "POST", "url": url, "headers": headers,
            "body": {"task_id": handle}}


# --------------------------------------------------------- normalisation

TRUE_WORDS = ("true", "yes", "y", "1")
# "ok" and "good" are gone, and their absence is the point.
#
# `classify` reads this vocabulary off the unwrapped body, and `unwrap`
# only descends into `data` or `result` - so any other envelope leaves the
# *transport* status at the top level, where "ok" is a whole word. A body
# of `{"status": "ok"}`, which is what an API says about the request it
# just accepted, classified as `valid`: a deliverability verdict about the
# mailbox. That is one of the two independent vendor confirmations that
# make an address sendable, and `words_of` already records that "ok" was
# the vehicle the last time this went wrong. The substring bug was fixed
# and the word was left in the list.
#
# Every word here has to be something a verifier says about a *mailbox*.
# "ok" and "good" are what a gateway says about a call. Losing a genuine
# vendor whose positive word is "ok" costs an `unknown`, which holds the
# address and asks; keeping it cost a false confirmation.
VALID_WORDS = ("valid", "deliverable", "safe", "verified")
INVALID_WORDS = ("invalid", "undeliverable", "bad", "bounced", "rejected", "failed")
CATCH_ALL_WORDS = ("catch_all", "catch-all", "catchall", "accept_all", "accept-all")
DISPOSABLE_WORDS = ("disposable", "temporary", "throwaway")
UNKNOWN_WORDS = ("unknown", "risky", "uncertain", "inconclusive", "timeout")
PENDING_WORDS = ("pending", "processing", "queued", "in_progress", "in-progress",
                 "running", "waiting", "started", "accepted")


def flag(payload, *names):
    """A boolean, whatever the provider chose to call it or how it spelled it."""
    for name in names:
        if name in payload:
            value = payload[name]
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in TRUE_WORDS
            if isinstance(value, (int, float)):
                return bool(value)
    return None


def text(payload, *names):
    for name in names:
        value = payload.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def unwrap(payload):
    payload = payload if isinstance(payload, dict) else {}
    for envelope in ("data", "result"):
        inner = payload.get(envelope)
        if isinstance(inner, dict):
            return inner
    return payload


def task_id(payload):
    """The handle the submit call hands back, under any of its spellings."""
    body = unwrap(payload)
    for name in ("task_id", "taskId", "taskID", "id", "task"):
        value = body.get(name)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            if str(value).strip():
                return str(value).strip()
    return None


def pending(payload):
    """Is this the provider saying 'not finished yet' rather than an answer?"""
    body = unwrap(payload)
    # `processing_status` is this provider's word for it: `pending` until the
    # task settles, then `completed`. Without it `pending()` answered False on
    # a body that said pending, so `collect()` returned on the first poll with
    # no verdict and no address on it.
    label = (text(body, "processing_status", "status", "state", "task_status",
                  "result") or "")
    label = label.lower().replace(" ", "_")
    if not label:
        return False
    # Negated the same way `classify` is. "not pending" means finished, and
    # reading it as still running would poll a settled task until the loop
    # gave up - which ends in `unknown`, so it is safe, and it is still
    # wrong about what the provider said.
    if words_of(label) & set(NEGATIONS):
        return False
    return _says(label, PENDING_WORDS)


# A label is a small number of words, and a word is what has to match.
# `_` and `-` are how providers join them; `.` and `/` show up in a few.
WORD_BREAK = re.compile(r"[^a-z0-9]+")


def words_of(label):
    """The label as a set of whole words. Never a substring.

    This function is the whole of a verification defect. `classify` used
    `word in label`, so a provider answering `not_deliverable` matched
    `deliverable` and was read as **valid** - the one word that means "do
    not send", turned into a confirmation. `token_expired`, `revoked`,
    `broken` and `not ok` all matched `ok` for the same reason, each of
    them an error being counted as one of the two independent vendor
    confirmations that make an address sendable.

    Nothing reached it: `require_contract` refuses every call until
    somebody sets `DELIVERABLE_RESULT_SHAPE`, and nobody has. But
    `HUMAN-ACTIONS-REQUIRED.md` asks a person to set exactly that, so this
    was one authorised action away from arming.
    """
    return {w for w in WORD_BREAK.split(str(label or "").lower()) if w}


def _says(label, vocabulary):
    """Whether the label uses any of these words, as words."""
    said = words_of(label)
    for phrase in vocabulary:
        wanted = words_of(phrase)
        if wanted and wanted <= said:
            return True
    return False


# A negation anywhere in the label disqualifies a positive reading. "not
# deliverable" is two words and would otherwise pass the whole-word test
# on its second one.
NEGATIONS = ("not", "non", "no", "never", "un")


def classify(payload):
    """The provider's own words, mapped onto our normalised status.

    Matched on whole words, and never positively when the label negates.
    An answer this does not recognise is `unknown` - which holds the
    address - and that is the direction this is allowed to fail in.
    """
    # `email_status` first, because it is the field this provider actually
    # answers in. Read live 2026-09-07: the verdict arrives as
    # `data.email_status` with the vocabulary
    # `deliverable | undeliverable | risky | unknown`, and none of the five
    # names below appear in the body at all - so every real answer classified
    # as `unknown`. Fail-closed, and useless: a credit per address for a
    # verdict this adapter could not read.
    label = (text(payload, "email_status", "status", "result", "state",
                  "verdict", "deliverability") or "").lower().replace(" ", "_")
    negated = bool(words_of(label) & set(NEGATIONS))

    if flag(payload, "disposable", "is_disposable", "temporary") is True:
        return "disposable"
    if _says(label, DISPOSABLE_WORDS):
        return "disposable"
    if flag(payload, "catch_all", "is_catch_all", "catchall", "accept_all") is True:
        return "accept_all"
    if _says(label, CATCH_ALL_WORDS):
        return "accept_all"
    if _says(label, INVALID_WORDS):
        return "invalid"
    if flag(payload, "deliverable", "is_deliverable", "valid", "is_valid") is False:
        return "invalid"
    # A negated label is never read as valid. "not deliverable" says the
    # opposite of the word it contains.
    if _says(label, VALID_WORDS):
        return "unknown" if negated else "valid"
    if flag(payload, "deliverable", "is_deliverable", "valid", "is_valid") is True:
        return "valid"
    if _says(label, UNKNOWN_WORDS):
        return "unknown"
    return "unknown"


def normalise(payload, email=None):
    """Provider payload to this project's verification model. Nothing raw escapes.

    The field names below are the ones verifiers commonly use, because this
    provider documents none. `unmapped_fields()` reports whatever the real
    answer carries that this does not read, so the gap is visible instead of
    silent, and an unrecognised answer becomes `unknown`, never `valid`.
    """
    from .. import verification

    payload = unwrap(payload)
    score = payload.get("score", payload.get("quality_score", payload.get("confidence")))
    return verification.result(
        "deliverable",
        classify(payload),
        email or text(payload, "email", "address"),
        deliverable=flag(payload, "deliverable", "is_deliverable", "valid", "is_valid"),
        safe_to_send=flag(payload, "safe_to_send", "is_safe_to_send", "safe"),
        catch_all=flag(payload, "catch_all", "is_catch_all", "catchall", "accept_all"),
        disposable=flag(payload, "disposable", "is_disposable", "temporary"),
        role_account=flag(payload, "role", "role_account", "is_role_account",
                          "is_role"),
        score=score if isinstance(score, (int, float)) else None,
        reason=text(payload, "reason", "message", "detail", "sub_status"),
    )


KNOWN_FIELDS = {
    "email", "address", "status", "result", "state", "verdict", "deliverability",
    "deliverable", "is_deliverable", "valid", "is_valid", "safe_to_send",
    "is_safe_to_send", "safe", "catch_all", "is_catch_all", "catchall",
    "accept_all", "disposable", "is_disposable", "temporary", "role",
    "role_account", "is_role_account", "is_role", "score", "quality_score",
    "confidence", "reason", "message", "detail", "sub_status", "data",
    # Read from a live answer rather than from documentation.
    "email_status", "processing_status", "provider", "task_id", "status_code",
    "task_id", "taskId", "taskID", "id", "task", "task_status",
}


def unmapped_fields(payload):
    """Fields the real response carries that this normaliser ignores."""
    return sorted(set(unwrap(payload)) - KNOWN_FIELDS)


# --------------------------------------------------------------- the call

def submit(email):
    """Hand the address over. Returns the task id the answer will arrive under."""
    plan = build_request(email)
    status, data = request(plan["method"], plan["url"], plan["headers"], plan["body"])
    if not ok(status):
        raise ProviderError(f"deliverable submit: {status}")
    handle = task_id(data)
    if handle is not None:
        return handle, data
    # It may have answered inline. Only accept that if it really is an answer.
    if pending(data) or classify(unwrap(data)) == "unknown":
        raise ProviderError(
            "deliverable submit: no task id in the response and no answer either")
    return None, data


def collect(handle, attempts=POLL_ATTEMPTS, interval=POLL_INTERVAL,
            sleep=time.sleep):
    """Poll for the answer. Bounded: a provider that never settles is `unknown`."""
    last = {}
    for attempt in range(max(1, attempts)):
        plan = build_status_request(handle)
        status, data = request(plan["method"], plan["url"], plan["headers"],
                               plan["body"])
        if not ok(status):
            raise ProviderError(f"deliverable status: {status}")
        last = data
        if not pending(data):
            return data
        if attempt < attempts - 1:
            sleep(interval)
    return last


def verify(email, attempts=POLL_ATTEMPTS, interval=POLL_INTERVAL, sleep=time.sleep,
           unread_contract=False):
    """One address, submit then collect. Costs one credit.

    `unread_contract=True` is how the validation harness reads the first real
    answer. Nothing else may set it: everywhere else, an unread response shape
    is a refusal rather than a spend.
    """
    if unread_contract:
        require_transport()
    else:
        require_contract()

    handle, submitted = submit(email)
    if handle is None:
        return normalise(submitted, email)
    return normalise(collect(handle, attempts, interval, sleep), email)


def check():
    """Readiness only. No address is verified to make a provider look green."""
    try:
        key(KEY_VAR)
    except ProviderError as e:
        return failed("Deliverable", e)

    gaps = transport_gaps()
    if gaps:
        return {"provider": "Deliverable", "ok": None, "status": None,
                "skipped": True,
                "note": "key configured, request contract incomplete: "
                        + "; ".join(g.split(":")[0] for g in gaps)}
    note = ("endpoints and auth confirmed from the provider's documentation; "
            "no account or quota endpoint is documented, so the key cannot be "
            "tested without spending a verification credit")
    if not result_shape_confirmed():
        note += "; response shape still unread"
    return {"provider": "Deliverable", "ok": None, "status": None, "skipped": True,
            "note": note}


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.providers.deliverable")
    p.add_argument("--check", action="store_true")
    p.add_argument("--contract", action="store_true",
                   help="show what is confirmed and what still is not")
    a = p.parse_args(argv)

    if a.contract:
        current = settings()
        print("Deliverable contract")
        print(f"  submit   {current['method']} {current['base']}{current['path']}")
        print(f"  collect  POST {current['base']}{current['status_path']}")
        print(f"  auth     {current['auth']}"
              + (f" ({HEADER_NAME})" if current["auth"] == "header" else ""))
        print("  source   the provider's own API documentation")
        gaps = contract_gaps()
        print("\nresponse:", "read and confirmed" if result_shape_confirmed()
              else "UNDOCUMENTED and unread - verify() refuses")
        for gap in gaps:
            print(f"  missing  {gap}")
        print("\nnormalised fields this adapter produces:")
        print("  email, status, deliverable, safe_to_send, catch_all, disposable,")
        print("  role_account, score, reason, provider")
        return 0 if not gaps else 1

    r = check()
    mark = "SKIP" if r.get("skipped") else ("ok  " if r["ok"] else "FAIL")
    print(f"{mark} {r['provider']:<12} {r['note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
