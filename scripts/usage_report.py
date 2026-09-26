#!/usr/bin/env python3
"""Daily usage and balance report for every provider.

Reads each provider's usage/balance where a programmatic endpoint exists,
writes docs/usage/YYYY-MM-DD.md, and exits. Where no endpoint exists the
row says NEEDS_CONSOLE_READ and names the provider - the foreground operator
reads it from the console.

## The five states, kept apart

    READ_OK              a real number from the provider
    NEEDS_CONSOLE_READ   no programmatic endpoint exists
    AUTH_FAILED          endpoint exists, credentials rejected
    UNREACHABLE          transport failure - NOT the same as AUTH_FAILED
    NOT_CONFIGURED       we hold no credential for this provider

## The rule

A set variable is not an authenticated one, a transport failure is not a bad
key, and an audit that reports clean because it watched nothing is worse than
none. This script NEVER estimates, interpolates, or carries yesterday's number
forward. Where it cannot read, it says so.

## What this script is NOT

- Not a writer. Every call is provably a GET against a status endpoint.
- Not a credential printer. Values are read from the environment and never
  appear in the output, logs, or error messages.
- Not a guesser. A number comes from the provider or it does not appear.

  py -3 scripts/usage_report.py                  writes docs/usage/YYYY-MM-DD.md
  py -3 scripts/usage_report.py --stdout         also prints the report
  py -3 scripts/usage_report.py --dry-run        builds the report, writes nothing
"""
import argparse
import datetime
import json
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src import config                                    # noqa: E402
from src.providers import (                                # noqa: E402
    HttpTimeout, HttpTransportError, MissingKey, ProviderError,
    key, load_env, ok, query, redact, request,
)

# ------------------------------------------------------------------ states

READ_OK = "READ_OK"
NEEDS_CONSOLE_READ = "NEEDS_CONSOLE_READ"
AUTH_FAILED = "AUTH_FAILED"
UNREACHABLE = "UNREACHABLE"
NOT_CONFIGURED = "NOT_CONFIGURED"

ALL_STATES = (READ_OK, NEEDS_CONSOLE_READ, AUTH_FAILED, UNREACHABLE,
              NOT_CONFIGURED)

# --------------------------------------------------------- credential names
#
# From config.VARIABLES via the providers group, never from a hand-written
# list. The same discipline as credential_health.py: a name invented here
# would wrongly report a provider as unconfigured, exactly as CONTACTOUT_KEY
# did on 2026-09-20.

PROVIDER_CREDENTIAL_NAMES = {
    name: name for name, _cls, group, _why in config.VARIABLES
    if group == "providers"
}

# Model providers use the MODEL_KEY_NAMES registry.
MODEL_PROVIDER_KEYS = {
    "openrouter": ("OPENROUTER_API_KEY", "LLM_API_KEY"),
    "groq": ("GROQ_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
}

# --------------------------------------------------------- one row builder


def _row(provider, metric, value=None, limit=None, percent=None,
          state=READ_OK, source="api", read_at=None, detail=""):
    """One row of the report. value/limit/percent are None unless READ_OK."""
    return {
        "provider": provider,
        "metric": metric,
        "value": value,
        "limit": limit,
        "percent": percent,
        "state": state,
        "source": source,
        "read_at": read_at or _now_iso(),
        "detail": detail,
    }


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _today():
    return datetime.date.today().isoformat()


def _is_configured(name):
    """Whether a credential env var is set. Never reads the value."""
    return bool((os.environ.get(name) or "").strip())


def _model_key_configured(provider):
    """Whether any of the model provider's key names is set."""
    for name in MODEL_PROVIDER_KEYS.get(provider, ()):
        if _is_configured(name):
            return True
    return False


def _classify_error(exc):
    """Map an exception to one of the failure states.

    A transport failure is NOT a bad credential. Classifying them alike is
    how an outage gets diagnosed as an auth problem.
    """
    if isinstance(exc, MissingKey):
        return NOT_CONFIGURED
    if isinstance(exc, (HttpTimeout, HttpTransportError)):
        return UNREACHABLE
    if isinstance(exc, ProviderError):
        text = str(exc).lower()
        if any(w in text for w in ("401", "403", "unauthor", "forbidden",
                                    "authentication", "credential")):
            return AUTH_FAILED
        if any(w in text for w in ("timeout", "timed out", "connection",
                                    "dns", "unreachable", "refused",
                                    "network", "transport")):
            return UNREACHABLE
    return UNREACHABLE


def _safe_read(fn):
    """Call fn() and return (row_dict | None, error_state | None).

    fn() returns a row dict on success. On exception, returns None and the
    classified state.
    """
    try:
        return fn(), None
    except Exception as exc:
        return None, _classify_error(exc)


# --------------------------------------------------------- provider readers
#
# Each reader returns a list of row dicts. A reader that cannot read returns
# a row with the appropriate non-READ_OK state. Every reader is READ-ONLY:
# GET against a status endpoint, or a documented free check.


def _read_contactout():
    """ContactOut: GET /v1/stats - free usage stats."""
    if not _is_configured("CONTACTOUT_TOKEN"):
        return [_row("ContactOut", "credits", state=NOT_CONFIGURED,
                      detail="CONTACTOUT_TOKEN not set")]
    try:
        from src.providers.contactout import headers
        status, data = request("GET",
                               "https://api.contactout.com/v1/stats",
                               headers())
        if status in (401, 403):
            return [_row("ContactOut", "credits", state=AUTH_FAILED,
                          detail=f"HTTP {status}")]
        if not ok(status):
            return [_row("ContactOut", "credits", state=UNREACHABLE,
                          detail=f"HTTP {status}")]
        data = data or {}
        # ContactOut returns:
        #   {"status_code": 200, "period": {...},
        #    "usage": {"count": N, "quota": N,
        #              "search_count": N, "search_quota": N,
        #              "phone_count": N, "phone_quota": N}}
        usage = data.get("usage", data) if isinstance(data, dict) else {}
        if not isinstance(usage, dict):
            usage = {}
        rows = []
        read_at = _now_iso()
        period = data.get("period") if isinstance(data, dict) else None
        for metric_key, label in [
            ("count", "api_calls_used"),
            ("quota", "api_calls_quota"),
            ("search_count", "search_credits_used"),
            ("search_quota", "search_credits_quota"),
            ("phone_count", "phone_credits_used"),
            ("phone_quota", "phone_credits_quota"),
        ]:
            val = usage.get(metric_key)
            if val is not None:
                rows.append(_row("ContactOut", label, value=val,
                                  state=READ_OK, source="api",
                                  read_at=read_at))
        if period and isinstance(period, dict):
            rows.append(_row("ContactOut", "period",
                              value=f"{period.get('start', '?')} to "
                                    f"{period.get('end', '?')}",
                              state=READ_OK, source="api",
                              read_at=read_at))
        if not rows:
            rows.append(_row("ContactOut", "credits", state=READ_OK,
                              source="api", read_at=read_at,
                              detail=str(data)[:200]))
        return rows
    except (HttpTimeout, HttpTransportError) as exc:
        return [_row("ContactOut", "credits", state=UNREACHABLE,
                      detail=redact(str(exc))[:120])]
    except ProviderError as exc:
        state = _classify_error(exc)
        return [_row("ContactOut", "credits", state=state,
                      detail=redact(str(exc))[:120])]


def _read_blitz():
    """Blitz: GET /v2/account/key-info - free, 0 records."""
    if not _is_configured("BLITZ_API_KEY"):
        return [_row("Blitz", "records", state=NOT_CONFIGURED,
                      detail="BLITZ_API_KEY not set")]
    try:
        from src.providers.blitz import key_info
        info = key_info()
        read_at = _now_iso()
        rows = []
        remaining = info.get("records_remaining")
        if remaining is not None:
            rows.append(_row("Blitz", "records_remaining", value=remaining,
                              state=READ_OK, source="api", read_at=read_at))
        plan = info.get("plan")
        if plan:
            rows.append(_row("Blitz", "plan", value=str(plan),
                              state=READ_OK, source="api", read_at=read_at))
        if not rows:
            rows.append(_row("Blitz", "records", state=READ_OK,
                              source="api", read_at=read_at,
                              detail=json.dumps(info)[:200]))
        return rows
    except (HttpTimeout, HttpTransportError) as exc:
        return [_row("Blitz", "records", state=UNREACHABLE,
                      detail=redact(str(exc))[:120])]
    except ProviderError as exc:
        state = _classify_error(exc)
        return [_row("Blitz", "records", state=state,
                      detail=redact(str(exc))[:120])]


def _read_apify():
    """Apify: GET /v2/users/me - account info.

    NOTE: this endpoint returns plan and username but NOT balance or usage.
    The balance is only available through the Apify console. We report what
    the API gives us and mark balance as NEEDS_CONSOLE_READ.
    """
    if not _is_configured("APIFY_TOKEN"):
        return [_row("Apify", "balance", state=NOT_CONFIGURED,
                      detail="APIFY_TOKEN not set")]
    try:
        token = key("APIFY_TOKEN")
        status, data = request(
            "GET", query("https://api.apify.com/v2/users/me",
                         {"token": token}))
        if status in (401, 403):
            return [_row("Apify", "balance", state=AUTH_FAILED,
                          detail=f"HTTP {status}")]
        if not ok(status):
            return [_row("Apify", "balance", state=UNREACHABLE,
                          detail=f"HTTP {status}")]
        data = (data or {})
        user_data = data.get("data", data) if isinstance(data, dict) else {}
        read_at = _now_iso()
        rows = []
        username = user_data.get("username") if isinstance(user_data, dict) else None
        if username:
            rows.append(_row("Apify", "username", value=username,
                              state=READ_OK, source="api",
                              read_at=read_at))
        plan = user_data.get("plan") if isinstance(user_data, dict) else {}
        if isinstance(plan, dict):
            tier = plan.get("tier")
            if tier:
                rows.append(_row("Apify", "plan_tier", value=tier,
                                  state=READ_OK, source="api",
                                  read_at=read_at))
            price = plan.get("monthlyBasePriceUsd")
            if price is not None:
                rows.append(_row("Apify", "monthly_price_usd",
                                  value=price, state=READ_OK,
                                  source="api", read_at=read_at))
        # Balance is NOT on this endpoint.
        rows.append(_row("Apify", "balance_usd",
                          state=NEEDS_CONSOLE_READ, source="console",
                          detail="no balance field on /v2/users/me; "
                                 "read console at console.apify.com"))
        return rows
    except (HttpTimeout, HttpTransportError) as exc:
        return [_row("Apify", "balance", state=UNREACHABLE,
                      detail=redact(str(exc))[:120])]
    except ProviderError as exc:
        state = _classify_error(exc)
        return [_row("Apify", "balance", state=state,
                      detail=redact(str(exc))[:120])]


def _read_openrouter():
    """OpenRouter: GET /api/v1/credits - remaining credits.

    NOTE: requires an admin/management key. A standard inference key returns
    401. We try it and classify the failure honestly.
    """
    key_name = None
    for name in MODEL_PROVIDER_KEYS["openrouter"]:
        if _is_configured(name):
            key_name = name
            break
    if not key_name:
        return [_row("OpenRouter", "credits", state=NOT_CONFIGURED,
                      detail="no OpenRouter key configured")]
    try:
        token = key(key_name)
        hdrs = {"Authorization": f"Bearer {token}"}
        status, data = request(
            "GET", "https://openrouter.ai/api/v1/credits", hdrs)
        if status in (401, 403):
            return [_row("OpenRouter", "credits", state=NEEDS_CONSOLE_READ,
                          source="api",
                          detail="key is not an admin key; "
                                 "GET /api/v1/credits requires one")]
        if not ok(status):
            return [_row("OpenRouter", "credits", state=UNREACHABLE,
                          detail=f"HTTP {status}")]
        data = data or {}
        inner = data.get("data", data) if isinstance(data, dict) else {}
        read_at = _now_iso()
        rows = []
        total = inner.get("total_credits")
        used = inner.get("total_usage")
        if total is not None:
            rows.append(_row("OpenRouter", "total_credits", value=total,
                              state=READ_OK, source="api", read_at=read_at))
        if used is not None:
            rows.append(_row("OpenRouter", "total_usage", value=used,
                              state=READ_OK, source="api", read_at=read_at))
        if total is not None and used is not None:
            remaining = round(total - used, 4)
            rows.append(_row("OpenRouter", "remaining_credits",
                              value=remaining, state=READ_OK, source="api",
                              read_at=read_at))
        if not rows:
            rows.append(_row("OpenRouter", "credits", state=READ_OK,
                              source="api", read_at=read_at,
                              detail=str(data)[:200]))
        return rows
    except (HttpTimeout, HttpTransportError) as exc:
        return [_row("OpenRouter", "credits", state=UNREACHABLE,
                      detail=redact(str(exc))[:120])]
    except ProviderError as exc:
        state = _classify_error(exc)
        return [_row("OpenRouter", "credits", state=state,
                      detail=redact(str(exc))[:120])]


def _console_only(provider, metric, reason):
    """A provider with no programmatic usage/balance endpoint."""
    return [_row(provider, metric, state=NEEDS_CONSOLE_READ,
                  source="console", detail=reason)]


# --------------------------------------------------------- the full reader

def read_all():
    """Every provider, in the order the operator named them.

    Returns a list of row dicts. Each reader is independent: one failure
    does not stop the others.
    """
    rows = []

    # Claude / Anthropic API
    if not _model_key_configured("anthropic"):
        rows.append(_row("Claude (Anthropic API)", "dollars",
                          state=NOT_CONFIGURED,
                          detail="ANTHROPIC_API_KEY not set"))
    else:
        rows.extend(_console_only(
            "Claude (Anthropic API)", "dollars",
            "no balance endpoint; read console at console.anthropic.com"))

    # GLM / Z.ai
    if not _is_configured("ZAI_API_KEY"):
        rows.append(_row("GLM (Z.ai)", "quota",
                          state=NOT_CONFIGURED,
                          detail="ZAI_API_KEY not set"))
    else:
        rows.extend(_console_only(
            "GLM (Z.ai)", "quota",
            "no quota headers on the Coding Plan endpoint "
            "(measured absence 2026-09-17); read console at open.bigmodel.cn"))

    # Qwen (local pool)
    rows.extend(_console_only(
        "Qwen", "pool_utilisation",
        "local pool; no Alibaba API credits endpoint known"))

    # Grok / xAI
    if not _is_configured("XAI_API_KEY"):
        rows.append(_row("Grok (xAI)", "credits",
                          state=NOT_CONFIGURED,
                          detail="XAI_API_KEY not set"))
    else:
        rows.extend(_console_only(
            "Grok (xAI)", "credits",
            "no documented balance endpoint; read console at console.x.ai"))

    # Groq
    if not _model_key_configured("groq"):
        rows.append(_row("Groq", "usage",
                          state=NOT_CONFIGURED,
                          detail="GROQ_API_KEY not set"))
    else:
        rows.extend(_console_only(
            "Groq", "usage",
            "no documented balance endpoint; read console at console.groq.com"))

    # OpenRouter
    rows.extend(_read_openrouter())

    # Anthropic API (already covered as Claude above)

    # CheapVerifier - mapped to Reoon in this codebase
    rows.extend(_read_reoon())

    # ContactOut
    rows.extend(_read_contactout())

    # AI-ARK
    if not _is_configured("AIARK_KEY"):
        rows.append(_row("AI-ARK", "credits",
                          state=NOT_CONFIGURED,
                          detail="AIARK_KEY not set"))
    else:
        rows.extend(_console_only(
            "AI-ARK", "credits",
            "no documented balance endpoint; read console at ai-ark.com"))

    # Apify
    rows.extend(_read_apify())

    # Reoon (already covered as CheapVerifier above, but listed separately
    # per the operator's naming)
    # We skip the duplicate since _read_reoon already covers it.

    # Deliverable
    if not _is_configured("DELIVERABLE_KEY"):
        rows.append(_row("Deliverable", "credits",
                          state=NOT_CONFIGURED,
                          detail="DELIVERABLE_KEY not set"))
    else:
        rows.extend(_console_only(
            "Deliverable", "credits",
            "no documented account/credit endpoint; "
            "read console at deliverable.co"))

    # Blitz
    rows.extend(_read_blitz())

    return rows


def _read_reoon():
    """Reoon / CheapVerifier: no usage endpoint."""
    if not _is_configured("REOON_KEY"):
        return [_row("Reoon (CheapVerifier)", "credits",
                      state=NOT_CONFIGURED,
                      detail="REOON_KEY not set")]
    return _console_only(
        "Reoon (CheapVerifier)", "credits",
        "no documented balance endpoint; "
        "read console at emailverifier.reoon.com")


# --------------------------------------------------------- report formatting

def format_markdown(rows, date=None):
    """The daily report as markdown. One section per provider."""
    date = date or _today()
    lines = [
        f"# Daily Usage Report - {date}",
        "",
        f"Generated at {_now_iso()} by `scripts/usage_report.py`.",
        "",
        "## Summary",
        "",
    ]

    # Group by provider
    by_provider = {}
    for r in rows:
        by_provider.setdefault(r["provider"], []).append(r)

    # Summary table
    lines.append("| Provider | Metric | Value | Limit | % | State | Source |")
    lines.append("|----------|--------|-------|-------|---|-------|--------|")
    for r in rows:
        val = _fmt_value(r["value"])
        lim = _fmt_value(r["limit"])
        pct = _fmt_percent(r["percent"])
        lines.append(
            f"| {r['provider']} | {r['metric']} | {val} | {lim} | "
            f"{pct} | **{r['state']}** | {r['source']} |")

    lines.append("")

    # Providers needing console read
    console_needed = [r for r in rows
                       if r["state"] == NEEDS_CONSOLE_READ]
    if console_needed:
        lines.append("## NEEDS_CONSOLE_READ")
        lines.append("")
        lines.append("The following providers have no programmatic endpoint. "
                      "Read from the console:")
        lines.append("")
        seen = set()
        for r in console_needed:
            if r["provider"] not in seen:
                seen.add(r["provider"])
                lines.append(f"- **{r['provider']}**: {r['detail']}")
        lines.append("")

    # Delegation section
    lines.append("## Delegation Rules")
    lines.append("")
    lines.append("- **Allowances that RESET are consumed to the maximum "
                  "before anything billed per token.**")
    lines.append("- **If a resetting allowance will expire under 70% used, "
                  "the operator names the tasks that should have been "
                  "routed to it.**")
    lines.append("- **If a paid provider is on pace to exceed its ceiling, "
                  "the router downgrades.**")
    lines.append("- **Claude's weekly limit is protected.** Claude does "
                  "orchestration, merges and prospect-facing copy only.")
    lines.append("")

    # Credential states
    not_configured = [r for r in rows if r["state"] == NOT_CONFIGURED]
    if not_configured:
        lines.append("## NOT_CONFIGURED")
        lines.append("")
        for r in not_configured:
            lines.append(f"- {r['provider']}: {r['detail']}")
        lines.append("")

    return "\n".join(lines)


def _fmt_value(v):
    if v is None:
        return "-"
    return str(v)


def _fmt_percent(p):
    if p is None:
        return "-"
    return f"{p:.1f}%"


# --------------------------------------------------------- output

def write_report(rows, output_dir=None, date=None, dry_run=False):
    """Write the markdown report to docs/usage/YYYY-MM-DD.md.

    Returns the path written (or would-be path if dry_run).
    """
    date = date or _today()
    output_dir = output_dir or os.path.join(_ROOT, "docs", "usage")
    path = os.path.join(output_dir, f"{date}.md")
    content = format_markdown(rows, date)
    if not dry_run:
        os.makedirs(output_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    return path, content


# --------------------------------------------------------- credential safety

def verify_no_credential_leak(content):
    """Assert that no configured credential value appears in the content.

    Reads every credential value from the environment and searches for it.
    Returns a list of variable names whose values were found (should be empty).
    """
    leaks = []
    for name, _cls, group, _why in config.VARIABLES:
        value = (os.environ.get(name) or "").strip()
        if len(value) >= 4 and value in content:
            leaks.append(name)
    return leaks


# --------------------------------------------------------- main

def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0])
    parser.add_argument("--stdout", action="store_true",
                        help="print the report to stdout as well")
    parser.add_argument("--dry-run", action="store_true",
                        help="build the report but write nothing")
    parser.add_argument("--date",
                        help="override the date (YYYY-MM-DD)")
    parser.add_argument("--output-dir",
                        help="override the output directory")
    args = parser.parse_args(argv)

    load_env(os.path.join(_ROOT, "config", ".env"))

    rows = read_all()
    date = args.date or _today()
    path, content = write_report(
        rows, output_dir=args.output_dir, date=date, dry_run=args.dry_run)

    leaks = verify_no_credential_leak(content)
    if leaks:
        print(f"CRITICAL: credential values found in report: "
              f"{', '.join(leaks)}", file=sys.stderr)
        return 2

    if args.stdout or args.dry_run:
        print(content)

    if not args.dry_run:
        print(f"Report written to {path}")
    else:
        print("(dry run - nothing written)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
