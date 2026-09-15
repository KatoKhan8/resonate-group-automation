#!/usr/bin/env python3
"""HTML. Rendering only.

Every function here takes data that `api.py` already assembled and turns it
into markup. Nothing in this module decides anything: there is no call to
`icp`, `verification`, `channels`, `lint`, `qa` or `push` anywhere in it, and
`tests/test_web_invariants.py` asserts that by walking the call graph.

Two rules the whole file is built to:

**Every interpolation goes through `esc`.** Company names, prospect names and
scraped evidence are attacker-controlled text that arrived from a provider or a
crawl. A test renders a record whose name is a script tag and asserts it comes
out inert.

**An absence is stated, never blank.** `unavailable()` prints why a cell is
empty. A blank cell reads as a broken page, and "we did not look" and "we
looked and found nothing" are different facts an operator needs to tell apart.
"""
import json
from urllib.parse import urlencode

from .assets import CSS_VERSION, JS_VERSION, LOGO_VERSION
from .security import attr, esc, safe_url

# (href, label, permission). An entry with no href is a section heading, and
# a heading whose entries are all hidden disappears with them. The permission
# is what the *handler* enforces; hiding the link as well is a courtesy, not
# the control. A menu full of refusals is a bad tool, and a menu that is the
# only check is a vulnerability.
# ------------------------------------------------------------------ navigation
#
# Six sections, and the point is what a person sees *at rest*: the section
# they are in, expanded, and five closed labels. The previous shape put
# forty links on the screen at once under five headings, which is not a
# menu but an index, and an index is what you reach for when you already
# know the name of the thing you want.
#
# Disclosure is server-rendered `<details>`, open when the current path is
# inside the section. No script, keyboard-usable, and stable across a
# refresh because it is derived from the URL rather than remembered.
#
# GLOBAL stays apart from the workspace sections deliberately. Everything
# under it aggregates across workspaces; everything under the others is
# scoped to the one you are inside, and a reader should never have to
# guess which they are looking at.
#
# None of this is authorization. Every href is checked against the
# permission table before the handler runs, and there is an invariant
# asserting a visible link never leads somewhere the role is refused.

SECTIONS = (
    ("global", "Global", None, (
        ("/global", "Overview", "workspace.view"),
        ("/workspaces", "Workspaces", None),
        ("/search", "Search", "workspace.view"),
        ("/global/reporting", "Global reporting", "reporting.view"),
        ("/admin", "Admin", "__super_admin__"),
        ("/admin/slack", "Slack operations", "__super_admin__"),
        ("/admin/health", "System health", "__super_admin__"),
    )),
    ("overview", "Overview", "/", (
        ("/", "Dashboard", "workspace.view"),
        ("/tasks", "Work queue", "operations.view"),
        ("/onboarding", "Workspace setup", "workspace.view"),
    )),
    ("audience", "Audience", None, (
        # First, and named the way somebody with a spreadsheet would say
        # it. This screen had no navigation entry at all: the only way to
        # reach it was to know the URL.
        ("/audience", "Overview", "contacts.view"),
        ("/upload", "Import leads", "batch.create"),
        ("/batches", "Imports and batches", "operations.view"),
        ("/companies", "Companies", "contacts.view"),
        ("/contacts", "Contacts", "contacts.view"),
        ("/segments", "Segments", "contacts.view"),
        ("/icp", "ICP review", "contacts.view"),
        ("/discovery", "Discovery", "operations.view"),
        ("/signals", "Account intelligence", "contacts.view"),
    )),
    ("outreach", "Outreach", None, (
        ("/campaigns", "Campaigns", "operations.view"),
        ("/campaigns/new", "Campaign builder", "campaign.create"),
        ("/campaigns/experiments", "Copy experiments", "operations.view"),
        ("/outreach/accounts", "Account outreach", "operations.view"),
        ("/revival", "Revival", "operations.view"),
        ("/outreach/cadence", "Cadence", "operations.view"),
        ("/outreach", "Outreach preview", "operations.view"),
        ("/senders", "Senders", "operations.view"),
        ("/approvals", "Approvals", "approvals.review"),
    )),
    ("inbox", "Inbox", None, (
        ("/replies", "Inbox", "replies.view"),
        ("/replies/returns", "Out-of-office returns", "operations.view"),
        ("/replies/policy", "Reply policy", "operations.view"),
        ("/notifications", "Notifications", "operations.view"),
    )),
    ("reporting", "Reporting", None, (
        ("/reporting", "Analytics", "reporting.view"),
        ("/compare", "Compare", "reporting.view"),
        ("/reporting/senders", "By sender", "reporting.view"),
        ("/reporting/cohorts", "Cohort performance", "operations.view"),
        ("/reporting/client", "Client reports", "reporting.view"),
        ("/reporting/editor", "Report editor", "reporting.view"),
    )),
    # Split out of Settings, which had quietly become the drawer everything
    # operational went into. "Where do I see what is failing" and "what is
    # this workspace's angle" are not the same question, and a section a
    # person cannot scan is the sidebar problem wearing a disclosure
    # triangle.
    ("operations", "Operations", None, (
        ("/health", "Operational health", "operations.view"),
        ("/refresh", "Refresh plan", "operations.view"),
        ("/jobs", "Batch processing", "operations.view"),
        ("/audit", "Audit log", "operations.view"),
        ("/diagnostics", "Diagnostics", "operations.view"),
        ("/simulator", "Scale simulator", "operations.view"),
    )),
    ("settings", "Settings", None, (
        ("/settings", "Workspace", "operations.view"),
        ("/settings/personas", "Personas", "workspace.manage"),
        ("/strategy", "Strategy", "operations.view"),
        # A policy list rather than an audience view: it says who
        # may never be written to, which is a setting.
        ("/suppression", "Suppression", "contacts.view"),
        ("/users", "Users", "users.manage"),
        ("/timezones", "Timezones", "operations.view"),
    )),
)

# The flat view, derived rather than maintained. Every invariant that
# walks the navigation reads this, so the two cannot disagree.
NAV = tuple(
    item
    for _, label, _, children in SECTIONS
    for item in (("", label, None),) + tuple(children))

# Status word -> visual kind. One table, so a status renders the same colour on
# every screen it appears on.
KIND = {
    "eligible": "pass", "pushed": "pass", "pass": "pass", "verified": "pass",
    "approved": "pass", "qualified": "pass", "completed": "pass",
    "multichannel": "pass", "valid": "pass", "ok": "pass",
    "unapproved": "warn", "waiting": "warn", "review": "warn", "held": "warn",
    "awaiting_approval": "warn", "unknown": "warn", "running": "warn",
    "queued": "warn", "email_only": "warn", "linkedin_only": "warn",
    "completed_with_holds": "warn", "warn": "warn",
    "blocked": "block", "skipped": "block", "rejected": "block",
    "invalid": "block", "failed": "block", "block": "block", "none": "block",
    "not_planned": "block", "accept_all_uncleared": "block",
    "paused": "pause", "cancelled": "pause",
}


# What a client-facing role may be told this system cannot measure. The two
# entries deliberately missing from it explain themselves by naming a supplier,
# and a reporting page is not where a vendor list gets published.
CLIENT_SAFE_UNAVAILABLE = ("meetings_booked", "opens",
                           "email_and_linkedin_eligibility")


def kind(status):
    return KIND.get(str(status or "").lower(), "")


def tag(text, k=None):
    return f'<span class="tag {k if k is not None else kind(text)}">{esc(text)}</span>'


def stat(label, value, k="", raw=False):
    # A `warn` or `block` tile showing zero is an alarm about nothing, and a
    # screen that raises one teaches an operator to stop reading the colour.
    # "0 held records" in amber, "0 failed jobs" in red and "0 review" in
    # amber were all on screens at once. Zero is neutral; the count decides,
    # not the call site, so fifteen call sites do not each have to remember.
    if k in ("warn", "block") and value in (0, "0", None):
        k = ""
    # `raw` for the one thing a tile has to be able to say instead of a
    # number: that nothing observes it. See `_meetings`.
    body = value if raw else esc(value)
    return (f'<div class="stat {k}"><div class="n">{body}</div>'
            f'<div class="k">{esc(label)}</div></div>')


def stats(pairs):
    return f'<div class="stats">{"".join(stat(*p) for p in pairs)}</div>'


def unavailable(why):
    return f'<span class="absent">not available &mdash; {esc(why)}</span>'


def row(label, value, raw=False):
    body = value if raw else esc(value)
    return f"<tr><th>{esc(label)}</th><td>{body}</td></tr>"


def kv(rows):
    return f'<table class="kv">{"".join(rows)}</table>'


def panel(title, body):
    head = f"<h3>{esc(title)}</h3>" if title else ""
    return f'<div class="panel">{head}{body}</div>'


def section(title, body, open_=False):
    return (f'<details{" open" if open_ else ""}><summary>{esc(title)}</summary>'
            f'<div class="secbody">{body}</div></details>')


def empty(title, detail):
    return (f'<div class="empty"><b>{esc(title)}</b>'
            f'<div class="small">{esc(detail)}</div></div>')


def link(href, text):
    return f'<a href="{attr(href)}">{esc(text)}</a>'


def external(url):
    """A source URL from the public web. Rendered as text unless it is http(s).

    Evidence carries URLs that came off a crawl, so a `javascript:` scheme here
    is a real possibility rather than a hypothetical one.
    """
    safe = safe_url(url)
    if not safe:
        return f'<span class="absent">{esc(url) or "no URL"}</span>'
    return (f'<a href="{attr(safe)}" rel="nofollow noopener noreferrer" '
            f'target="_blank">{esc(safe)}</a>')


def table(headers, rows_html, table_id=None, filterable=False):
    ident = f' id="{attr(table_id)}"' if table_id else ""
    head = "".join(f'<th scope="col">{esc(h)}</th>' for h in headers)
    controls = ""
    if filterable and table_id:
        controls = (f'<div class="filters">'
                    f'<label class="sr-only" for="{attr(table_id)}-filter">'
                    f'Filter loaded {esc(table_id)} rows</label>'
                    f'<input id="{attr(table_id)}-filter" type="search" '
                    f'placeholder="Filter rows on this page"'
                    f' aria-controls="{attr(table_id)}" data-filter="{attr(table_id)}">'
                    f'<span id="{attr(table_id)}-count" class="filter-count" '
                    f'role="status" data-count="{attr(table_id)}">'
                    f"</span></div>")
    return (f'{controls}<div class="scroll"><table{ident}><thead><tr>{head}</tr>'
            f"</thead><tbody>{rows_html}</tbody></table></div>")


def pager(page, base, query=None):
    """The controls, and the sentence that says what is on screen.

    The sentence comes first and is not optional. A reader who cannot see
    "1-100 of 30,000" has no way to know the list is a window.
    """
    if not page or not page["total"]:
        return ""

    def link_to(number):
        parts = dict(query or {})
        parts["page"] = number
        return attr(base + "?" + urlencode(
            {k: v for k, v in parts.items() if v not in (None, "")}))

    if not page["truncated"]:
        return ('<p class="small muted">' + esc(page["total"])
                + " row(s).</p>")

    controls = ""
    if page["has_previous"]:
        controls += ('<a class="btn" href="' + link_to(page["page"] - 1)
                     + '">Previous</a> ')
    if page["has_next"]:
        controls += ('<a class="btn" href="' + link_to(page["page"] + 1)
                     + '">Next</a>')

    return ('<div class="filters"><span class="small muted">Showing '
            + esc(page["first"]) + "&ndash;" + esc(page["last"]) + " of "
            + esc(page["total"]) + " &middot; page " + esc(page["page"])
            + " of " + esc(page["pages"]) + "</span> " + controls
            + "</div>")


def json_block(value):
    return f'<pre class="json">{esc(json.dumps(value, indent=2, default=str))}</pre>'


def progress(fraction):
    pct = max(0, min(100, round((fraction or 0) * 100)))
    return (f'<progress value="{pct}" max="100" '
            f'aria-label="Progress: {pct}%">{pct}%</progress>')


def error_state(title, detail, path="/", retry=False):
    """A failed read can be retried. A failed write never claims no change."""
    action = (link(path, "Reload this page") if retry
              else link("/", "Return to dashboard"))
    return ('<section class="empty error-state" role="alert">'
            f'<p class="eyebrow">Request could not be completed</p>'
            f'<h1>{esc(title)}</h1><p class="small">{esc(detail)}</p>'
            f'<p class="small">{action}</p></section>')


def brand():
    return (f'<div class="brand"><img class="brand-logo" '
            f'src="/assets/resonate-logo.png?v={attr(LOGO_VERSION)}" '
            'width="54" height="54" alt="Resonate Group logo">'
            '<div><b>RESONATE OS</b><span>Control center</span></div></div>')


# ------------------------------------------------------------------ shell

def _current_nav(path, hrefs):
    """Which nav entry this path belongs to: the longest one that contains it.

    A sub-page still lights its section - /outreach/contact/x is "Outreach
    preview" - but a section that has its own entry claims its own pages, so
    /replies/policy is "Reply policy" and nothing else.
    """
    best = None
    for href in hrefs:
        if href == "/":
            if path == "/":
                return "/"
            continue
        if path == href or path.startswith(href.rstrip("/") + "/"):
            if best is None or len(href) > len(best):
                best = href
    return best


def shell(body, session, ctx, path="/", title="Control Center"):
    """The frame every page renders inside."""
    granted = set(ctx.get("permissions") or ())
    if ctx.get("super_admin"):
        granted.add("__super_admin__")
    # Every href this role may see, so "which entry is current" is decided
    # against what is actually reachable.
    allowed = [(href, label)
               for _, _, _, children in SECTIONS
               for href, label, permission in children
               if not permission or permission in granted]

    # Exactly one item is current, and it is the most specific one that
    # matches. Any-prefix-wins lit two at once - "Replies" and "Reply policy"
    # both, and "Outreach preview" alongside "Accounts" - which tells a
    # reader they are in two places.
    current_href = _current_nav(path, [h for h, _ in allowed if h])

    nav = ""
    for key, label, own, children in SECTIONS:
        entries = [(href, child_label)
                   for href, child_label, permission in children
                   if not permission or permission in granted]
        if not entries:
            # A section this role cannot enter is not shown closed, it is
            # not shown. An empty disclosure is a promise of nothing.
            continue
        here = any(href == current_href for href, _ in entries)
        inner = ""
        for href, child_label in entries:
            on = "on" if href == current_href else ""
            active = ' aria-current="page"' if on else ''
            inner += (f'<a class="{on}" href="{attr(href)}"{active}>'
                      f'{esc(child_label)}</a>')
        # Open where you are. Derived from the path rather than remembered,
        # so a refresh or a pasted deep link lands in the same place - and
        # /outreach/account/acme expands Outreach without anybody storing
        # that it should.
        nav += (f'<details class="navsec"{" open" if here else ""}>'
                f'<summary>{esc(label)}</summary>'
                f'<div class="navkids">{inner}</div></details>')

    spaces = ctx.get("workspaces") or []
    options = "".join(
        f'<option value="{attr(w["slug"])}"'
        f'{" selected" if w["slug"] == ctx.get("workspace") else ""}>'
        f'{esc(w["name"])}</option>' for w in spaces)
    picker = ""
    if spaces:
        # The name of the workspace, not only a dropdown. On a screen that can
        # show one client's prospects to somebody who also has access to
        # another's, "which workspace am I in" has to be readable at a glance
        # rather than inferred from a select box.
        current = next((w["name"] for w in spaces
                        if w["slug"] == ctx.get("workspace")), None)
        label = (f'<span class="wsname">{esc(current)}</span>' if current
                 else '<span class="wsname none">no workspace</span>')
        picker = (
            f'<div class="scope-picker">{label}'
            f'<form method="post" action="/select-workspace">'
            f'<input type="hidden" name="csrf" value="{attr(ctx.get("csrf"))}">'
            '<label class="sr-only" for="workspace-picker">Switch workspace</label>'
            f'<select id="workspace-picker" name="workspace" data-autosubmit>{options}</select>'
            '<noscript><button type="submit">Switch</button></noscript>'
            '</form></div>')

    demo = ctx.get("demo")
    env = "DEMO" if demo else str(ctx.get("mode") or "LOCAL").upper()
    safety = (
        f'<div class="safety"><span class="dot off"></span>'
        f"<span>Live sending <b>disabled</b></span></div>"
        f'<div class="safety environment"><span class="dot {"demo" if demo else "off"}">'
        f"</span><span>{esc(env)}</span></div>")

    who = ""
    if session:
        badge = tag(ctx.get("role") or "no role",
                    "pass" if ctx.get("super_admin") else "info")
        who = (f'<span class="small muted user-email">{esc(ctx.get("email"))}</span>'
               f"{badge}"
               f'<a class="small" href="/logout">Sign out</a>')

    search = ''
    if session and 'workspace.view' in granted:
        search = (f'<form action="/search" method="get" class="workspace-search">'
                  '<label for="workspace-search" class="sr-only">Search current workspace</label>'
                  f'<input type="hidden" name="workspace" value="{attr(ctx.get("workspace"))}">'
                  '<input id="workspace-search" name="q" type="search" '
                  'placeholder="Search workspace…" maxlength="160">'
                  '<button type="submit" aria-label="Search workspace">Find</button></form>')

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} &middot; Resonate</title>
<link rel="icon" type="image/png" href="/assets/resonate-logo.png?v={attr(LOGO_VERSION)}">
<link rel="stylesheet" href="/assets/app.css?v={attr(CSS_VERSION)}">
</head><body>
<a class="skip-link" href="#main-content">Skip to content</a>
<div class="loading-line" aria-hidden="true"></div>
<div class="loading-skeleton" aria-hidden="true"><div class="skel"></div><div class="skel"></div><div class="skel"></div></div>
<div id="page-status" class="page-status" role="status" aria-live="polite"></div>
<button type="button" class="nav-overlay" data-nav-close aria-label="Close navigation"></button>
<div class="shell">
  <aside class="side" id="sidebar" aria-label="Application navigation">
    {brand()}
    <button type="button" class="nav-close" data-nav-close>Close menu</button>
    <nav class="nav" aria-label="Workspace sections">{nav}</nav>
  </aside>
  <div class="main">
    <header class="top"><button type="button" id="nav-toggle" class="nav-toggle" data-nav-toggle aria-controls="sidebar" aria-expanded="false">Menu</button>{picker}{search}<div class="spacer"></div>{safety}{who}</header>
    <main class="wrap" id="main-content" tabindex="-1">{body}</main>
  </div>
</div>
<script src="/assets/app.js?v={attr(JS_VERSION)}"></script>
</body></html>"""


def provider_login_page(error=None):
    """Sign in through the identity provider. One button and nothing else.

    What is *absent* here is the point. The demo page renders every known
    user in a dropdown, which is right for a fictional estate and is an
    enumeration of the agency's staff and its clients anywhere else. This
    page names no address, no workspace and no provider account, so a
    stranger who finds the URL learns that Resonate exists and stops there.

    The error text is deliberately one sentence for every failure. Which
    check refused - state, nonce, audience, expiry, domain - is useful to
    somebody probing and useless to somebody who should try again.
    """
    warn = f'<div class="banner stop">{esc(error)}</div>' if error else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sign in &middot; Resonate</title>
<link rel="stylesheet" href="/assets/app.css?v={attr(CSS_VERSION)}">
</head><body>
<div class="login">
  {brand()}
  <h1>Sign in to Resonate OS</h1>
  <p class="muted small">Control Center</p>
  {warn}
  <p><a class="btn primary" href="/auth/start">Sign in</a></p>
  <p class="note small">Sign-in is handled by your organisation's identity
  provider. Resonate never sees your password. What you may do once you are
  in comes from the membership table on this server, resolved on every
  request &mdash; so a revoked role stops working immediately rather than at
  your next sign-in.</p>
</div>
</body></html>"""


def login_page(users, error=None):
    """Sign in as a known user. No password, and that is stated on the page.

    Demo sign-in is for local fictional data. Production uses the separate
    OIDC sign-in page and the existing server-side authentication policy. What it *does* have is authorisation: which
    workspaces this person is in and what their role there carries, resolved on
    the server on every request.
    """
    options = "".join(
        f'<option value="{attr(u["email"])}">{esc(u["name"])} '
        f'&mdash; {esc(u["email"])}{" (super admin)" if u.get("super_admin") else ""}'
        f"</option>" for u in users)
    warn = f'<div class="banner stop">{esc(error)}</div>' if error else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sign in &middot; Resonate</title>
<link rel="stylesheet" href="/assets/app.css?v={attr(CSS_VERSION)}">
</head><body>
<div class="login">
  {brand()}
  <h1>Sign in to Resonate OS</h1>
  <p class="muted small">Control Center. Live sending is disabled in this
  build.</p>
  {warn}
  <form method="post" action="/login">
    <label for="email">Sign in as</label>
    <select id="email" name="email">{options}</select>
    <button class="btn primary" type="submit">Sign in</button>
  </form>
  <p class="note small">Demo sign-in does not verify identity, and no role is
  taken from this form. Which workspaces you can enter and what you may do in
  them is resolved from the membership table on the server, on every request
  &mdash; so a revoked role stops working immediately rather than at your next
  sign-in.</p>
</div>
</body></html>"""


# -------------------------------------------------------------- dashboard

def _active_of(metrics, key, one, many):
    """"18 of 22 inboxes" - never a bare count next to a different one.

    The health line beside this row reports the *active* figure. A row
    reporting the total with the same word left a reader to work out which
    of two numbers on one card meant what.
    """
    total = metrics.get(key) or 0
    active = metrics.get(key + "_active")
    word = one if total == 1 else many
    if active is None or active == total:
        return f"{esc(total)} {esc(word)}"
    return f"{esc(active)} of {esc(total)} {esc(word)}"


def _health_tag(health):
    kind_ = {"ok": "pass", "warn": "warn", "none": "block"}.get(
        health.get("state"), "")
    return (tag(health.get("state"), kind_)
            + f'<div class="small muted">{esc(health.get("why"))}</div>')


def global_overview(data, csrf=None):
    """Every workspace this person may enter, and the totals across them.

    The scope line is not decoration. A dashboard that aggregates "everything"
    means something different to a super admin and to somebody who is a member
    of one workspace, and a reader who cannot tell which they are looking at
    will read the second as the first.
    """
    totals = data["totals"]
    cards = ""
    for card in data["workspaces"]:
        m = card["metrics"]
        cards += f"""
<div class="wscard">
  <h3>{link("/select-workspace?to=" + card["slug"], card["name"])}
    {tag(card["role"] or "no role", "info")}</h3>
  <div class="small muted"><code>{esc(card["slug"])}</code></div>
  {stats([("companies", m["companies"]),
          ("contacts", m["contacts"]),
          ("campaigns", m["campaigns"]),
          ("replies", m["replies"], "pass" if m["replies"] else ""),
          ("positive", m["positive_replies"],
           "pass" if m["positive_replies"] else ""),
          ("awaiting approval", m["pending_approvals"],
           "warn" if m["pending_approvals"] else "")])}
  <table class="kv">
    {f'''<tr><th>Sender infrastructure</th>
      <td>{_health_tag(card["sender_health"])}</td></tr>'''
     if card.get("can_see_operations") else ""}
    <tr><th>Campaigns</th><td>{_health_tag(card["campaign_health"])}</td></tr>
    <tr><th>Confirmed touches</th><td>{esc(m["confirmed_email_touches"])} email
      &middot; {esc(m["confirmed_linkedin_touches"])} LinkedIn</td></tr>
    {f'''<tr><th>Senders</th>
      <td>{_active_of(m, "senders", "person", "people")}
      &middot; {_active_of(m, "email_accounts", "inbox", "inboxes")}
      &middot; {_active_of(m, "linkedin_accounts", "profile", "profiles")}
      <div class="small muted">active of total</div></td></tr>'''
     if card.get("can_see_operations") else ""}
    <tr><th>Held / paused</th><td>{esc(m["held"])} held &middot;
      {esc(m["paused"])} paused</td></tr>
  </table>
  <p><a class="btn primary" href="/select-workspace?to={attr(card["slug"])}">
    Enter {esc(card["name"])}</a></p>
</div>"""

    sources = "".join(
        f'<tr><td><code>{esc(name)}</code></td>'
        f'<td class="small muted">{esc(why)}</td></tr>'
        for name, why in sorted(data["sources"].items()))

    return f"""
<h1>All workspaces</h1>
<div class="crumb">Aggregating {esc(data["scope"])}.</div>
{stats([("workspaces", totals["workspaces"]),
        ("campaigns", totals["campaigns"]),
        ("companies", totals["companies"]),
        ("ICP qualified", totals["qualified"], "pass"),
        ("contacts", totals["contacts"]),
        ("contactable", totals["contactable"], "pass"),
        ("email touches", totals["confirmed_email_touches"]),
        ("linkedin touches", totals["confirmed_linkedin_touches"]),
        ("replies", totals["replies"]),
        ("positive", totals["positive_replies"], "pass"),
        ("meetings", _meetings(totals["meetings"]), "", True),
        ("held", totals["held"], "block" if totals["held"] else ""),
        ("paused", totals["paused"], "pause" if totals["paused"] else ""),
        ("awaiting approval", totals["pending_approvals"],
         "warn" if totals["pending_approvals"] else ""),
        ]
       + ([("failed jobs", totals["failed_jobs"],
            "block" if totals["failed_jobs"] else "pass"),
           ("credits", totals["credits"])]
          if data.get("operations_visible") else []))}
<div class="wsgrid">{cards}</div>
{section("Where each number comes from",
         table(["metric", "source"], sources)
         + '<p class="note">Every tile above is counted from stored state. '
           'A number this system cannot know - a send, a delivery, a meeting - '
           'is counted from the events that would establish it and comes back '
           'zero, rather than being estimated from what was planned. '
           '<b>Nothing here has been sent</b>, so the touch counts are the '
           'ones the demo estate planted.</p>')}
"""


def global_comparison(data):
    """Workspaces side by side. Every rate carries the pair it came from."""
    rows = ""
    for row in data["rows"]:
        rows += (
            f'<tr><td>{link("/select-workspace?to=" + row["slug"], row["name"])}'
            f'</td><td>{esc(row["contacts"])}</td>'
            f'<td>{esc(row["contactable"])}</td>'
            f'<td>{esc(row["confirmed_touches"])}</td>'
            f'<td>{esc(row["replies"])} {_rate(row["reply_rate"])}</td>'
            f'<td>{esc(row["positive_replies"])} {_rate(row["positive_rate"])}</td>'
            f'<td>{_meetings(row["meetings"])}</td></tr>')
    return f"""
<h1>Global reporting</h1>
<div class="crumb">Aggregating {esc(data["scope"])}.</div>
{table(["workspace", "contacts", "contactable", "confirmed touches",
        "replies", "positive", "meetings"], rows)
 if rows else empty("Nothing to compare",
                    "You are a member of no workspace with any data.")}
<p class="note">Every rate is printed with its own numerator and denominator,
and the denominator is <b>contactable contacts</b> rather than everyone
loaded. Sample sizes here are small; a difference between two workspaces at
these numbers is a thing to look into, not a result.</p>
<p class="note stop">A workspace you are not a member of is not in this table
and is not in the totals. The aggregate is built from one scoped read per
authorised workspace, so there is no view here that a membership did not
grant.</p>
"""


def quick_actions(can):
    """The handful of things somebody opens this product to do.

    First is importing an audience, because that is what a new workspace
    needs and because it was the hardest thing here to find: the screen
    had no navigation entry and nothing linked to it, so the only way in
    was to already know the URL.

    `can` is a set of permissions. An action a role cannot perform is not
    shown disabled, it is not shown - a button that refuses is worse than
    no button, and hiding it is a courtesy rather than a control. The
    permission is checked again at the handler.
    """
    actions = [
        ("/upload", "Import leads",
         "Upload a CSV of company domains", "batch.create", True),
        ("/campaigns/new", "Create campaign",
         "Build one from a segment", "campaign.create", False),
        ("/senders", "Senders",
         "Who sends, on which channel", "operations.view", False),
        ("/reporting/client", "Client report",
         "Generate this month's report", "reporting.view", False),
    ]
    out = ""
    for href, label, why, permission, primary in actions:
        if permission not in can:
            continue
        out += (f'<a class="quick{" primary" if primary else ""}" '
                f'href="{attr(href)}"><b>{esc(label)}</b>'
                f'<span>{esc(why)}</span></a>')
    if not out:
        return ""
    return f'<div class="quickrow">{out}</div>'



# notify's severities, in this stylesheet's vocabulary. Critical reads red,
# everything actionable reads amber; the count decides whether a row exists
# at all, so nothing here is ever a coloured zero.
SEVERITY_CLASS = {"critical": "block", "action_required": "warn",
                  "warning": "warn", "info": ""}

SEVERITY_WORD = {"critical": "Critical", "action_required": "Action required",
                 "warning": "Warning", "info": "For information"}



def client_funnel(funnel):
    """What has happened, in the words the client report already uses.

    The client cut used to borrow the operator's tiles, which say
    "multichannel", "email only" and "held" - internal channel eligibility -
    beside "review" and "rejected", which are this system's private opinion
    of somebody's company. All true, none of it addressed to the reader.

    The labels arrive already chosen, from `report.FUNNEL_LABEL`, so the
    screen and the client PDF describe one number one way.
    """
    if not funnel or not funnel.get("stages"):
        return empty("Nothing yet",
                     "Once accounts are researched and contacts are found, "
                     "the progress of the work appears here.")
    tiles = [(row["label"], row["count"],
              "pass" if row["stage"] in ("positive", "meeting") and row["count"]
              else "")
             for row in funnel["stages"]]
    reached = funnel.get("contacted") or 0
    replied = funnel.get("replied") or 0
    if reached:
        # Every rate carries both of its numbers. A percentage on its own is
        # a claim the reader has no way to check.
        #
        # Sends rather than people, and it has to say so: the funnel counts
        # `push_marked` events, so thirteen sends can have reached twelve
        # people. This said "13 people" until a digest cross-check caught
        # it, which is the kind of claim a client would have believed.
        note = (f'<p class="note">{esc(replied)} replies from '
                f'{esc(reached)} confirmed sends.</p>')
    else:
        note = ('<p class="note">Nothing has been sent from this system yet, '
                "so nobody has been contacted and no reply can have arrived. "
                "Everything above is research and preparation.</p>")
    return stats(tiles) + note


def task_queue(data):
    """The work list, one row per thing to do.

    Ordered by severity and then by what is due soonest, so it reads top
    down and can be stopped at the first thing that matters. A population
    row - eleven addresses waiting for a second verifier - says how many
    rather than pretending to be one clickable item, because nobody works
    through ten thousand contacts one at a time.
    """
    rows = data.get("tasks") or []
    if not rows:
        return ('<h1>Work queue</h1><div class="crumb">Everything waiting in '
                + esc(data.get("workspace") or "") + "</div>"
                + empty("Nothing outstanding",
                        "No approvals waiting, nobody due back from leave, "
                        "no failed jobs, and reply protection is running."))

    body = ""
    for row in rows:
        css = SEVERITY_CLASS.get(row["severity"], "")
        what = (esc(row["title"]) if row["object_type"] != "population"
                else esc(f'{row["count"]} records'))
        due = esc(row["due"]) if row.get("due") else ""
        body += (
            "<tr>"
            f'<td>{tag(SEVERITY_WORD.get(row["severity"], row["severity"]), css)}</td>'
            f'<td class="small muted">{esc(row.get("kind_label") or row["kind"])}</td>'
            f"<td><b>{what}</b>"
            f'<div class="small muted">{esc(row["why"])}</div></td>'
            f'<td class="small">{due}</td>'
            f'<td><a class="btn" href="{esc(row["where"])}">Open</a></td>'
            "</tr>")

    return ('<h1>Work queue</h1><div class="crumb">'
            + esc(len(rows)) + " thing(s) waiting in "
            + esc(data.get("workspace") or "") + "</div>"
            + attention_panel(data.get("summary") or [])
            + panel("Everything, in order",
                    table(["", "Kind", "What", "Due", ""], body))
            + '<p class="note">This list is assembled from canonical state '
              "every time it is opened. Nothing here is ticked off: a row "
              "disappears when the thing it describes is actually done.</p>")


def attention_panel(rows):
    """What to do, before what we have.

    The dashboard used to open with how many companies are in the
    workspace, which is not a question anybody starts the day with. This
    is: every row is a count, a sentence saying why it matters, and a link
    to the screen where it can be dealt with.

    Nothing renders at zero. A list that always shows nine rows, six of
    them empty, is a list people learn to skim past - and then miss the
    one that mattered.
    """
    if not rows:
        return panel(
            "Needs attention",
            '<p class="note">Nothing is waiting. No approvals pending, no '
            "follow-ups due or failed jobs in this workspace. "
            "See runtime status below for reply protection.</p>")

    body = ""
    for row in rows:
        css = SEVERITY_CLASS.get(row["severity"], "")
        body += (
            '<tr>'
            f'<td>{tag(SEVERITY_WORD.get(row["severity"], row["severity"]), css)}</td>'
            f'<td class="n"><b>{esc(row["count"])}</b></td>'
            f'<td><b>{esc(row["label"])}</b>'
            f'<div class="small muted">{esc(row["why"])}</div></td>'
            f'<td><a class="btn" href="{esc(row["where"])}">Open</a></td>'
            "</tr>")
    return panel("Needs attention",
                 table(["", "", "What", ""], body))


def operator_pipeline(can):
    stages = (
        ("Import", "Normalize, deduplicate, suppress", "/upload", "batch.create"),
        ("Qualify", "Evidence and human review", "/icp", "contacts.view"),
        ("Segment", "Region, vertical and size", "/segments", "contacts.view"),
        ("Verify", "Consensus and channel eligibility", "/contacts", "contacts.view"),
        ("Review", "Cadence, copy and QA", "/campaigns", "operations.view"),
        ("Approve", "Exact campaign fingerprint", "/approvals", "approvals.review"),
    )
    return '<div class="pipeline-strip">' + ''.join(
        f'<a class="pipeline-stage" href="{attr(href)}"><b>{esc(label)}</b>'
        f'<span>{esc(detail)}</span></a>'
        for label, detail, href, permission in stages if permission in can) + '</div>'


def control_center(data):
    if not data:
        return ''
    runtime = [row("Live sending", tag("disabled", "warn"), raw=True),
               row("Sign-in", tag(data["auth"], "info"), raw=True),
               row("Cadence scheduler", data["cadence_scheduler"])]
    for poll in data["polling"]:
        state = "pass" if poll["state"] == "working" else "warn"
        runtime.append(row(f'{poll["provider"]} reply reconciliation',
                           tag(poll["label"], state), raw=True))
    activity = ''.join(
        f'<li><b>{esc(entry["action"])}</b> '
        f'<span class="small muted">{esc(entry["resource_id"] or "")}</span>'
        f'<time>{esc(entry["at"])} · {esc(entry["actor"] or "system")}</time></li>'
        for entry in data["audit"])
    return ('<div class="grid2">' + panel("Safety & runtime", kv(runtime))
            + panel("Recent workspace activity", '<ul class="audit-preview">'
                    + activity + '</ul>' if activity else empty(
                        "No audit events yet", "Workspace changes appear here when recorded."))
            + '</div>')


def distribution_chart(counts, title):
    """An accessible distribution of actual counts, never a completion rate."""
    total = sum(counts.values())
    if not total:
        return empty("No data yet", "Import a batch to see the qualification distribution.")
    bars = ''.join(
        f'<div class="metric-bar"><span>{esc(name.replace("_", " "))}</span>'
        f'<progress value="{attr(count)}" max="{attr(total)}" '
        f'aria-label="{attr(name)}: {attr(count)} of {attr(total)}">'
        f'{esc(count)} of {esc(total)}</progress><strong>{esc(count)}</strong></div>'
        for name, count in counts.items())
    return (f'<div class="metric-bars" role="group" aria-label="{attr(title)}">'
            + bars + f'</div><p class="small muted">{esc(total)} companies with a recorded verdict.</p>')


def dashboard(data, simple=False, slack=None):
    """The operator's first screen, or the client-facing cut of it.

    `simple=True` is what a VIEWER sees. It keeps the outcome - how many
    companies, how many qualified, how many contacts are reachable, what came
    back - and drops the machinery: which email-security vendors were found,
    what enrichment costs, what the job queue is doing, and every link to a
    screen this role would be refused from anyway. A client-facing role should
    not learn the vendor stack from a dashboard, and a nav full of links that
    return 403 is a worse product than one that does not offer them.
    """
    q = data["qualification"]
    modes = data["modes"]
    ver = data["verification"]
    cost = data["cost"]
    needs = attention_panel(data.get("attention") or [])

    head = stats([
        ("companies", data["records"]),
        ("qualified", q["by_status"].get("qualified", 0), "pass"),
        ("review", q["by_status"].get("review", 0), "warn"),
        ("rejected", q["by_status"].get("rejected", 0), "block"),
        ("contacts", data["contacts"]),
        ("multichannel", modes.get("multichannel", 0), "pass"),
        ("email only", modes.get("email_only", 0)),
        ("linkedin only", modes.get("linkedin_only", 0)),
        ("held", modes.get("none", 0), "block" if modes.get("none") else ""),
    ])

    # Two versions of the same six facts. The operator's names the escalation
    # verifier; the client-facing one says what happened without naming the
    # supplier who did it, because a dashboard is not where a client learns
    # which vendors are in the stack. Same number, one fewer disclosure.
    verification_common = [
        ("double verified", ver["double"], "pass"),
        ("held for a 2nd", ver["single"], "warn" if ver["single"] else ""),
        ("invalid", ver["invalid"], "block" if ver["invalid"] else ""),
        ("catch-all", ver["catch_all"]),
        ("disagreements", ver["disagreement"],
         "block" if ver["disagreement"] else ""),
    ]
    verification = stats(verification_common
                         + [("reoon escalations", ver["reoon_escalations"])])
    client_verification = stats(
        verification_common
        + [("sent to a third check", ver["reoon_escalations"])])

    mx_rows = "".join(
        f"<tr><td>{esc(name)}</td><td>{esc(count)}</td></tr>"
        for name, count in (data["mx"] or {}).items())

    campaigns = "".join(
        f"<tr><td>{tag(k)}</td><td>{esc(v)}</td></tr>"
        for k, v in (data["campaigns"]["by_status"] or {}).items())

    replies = data["replies"]
    reply_stats = stats([
        ("positive", replies.get("positive", 0), "pass"),
        ("neutral", replies.get("neutral", 0)),
        ("negative", replies.get("negative", 0), "block"),
        ("unknown", replies.get("unknown", 0), "warn"),
    ])

    cost_rows = kv([
        row("Expected credits", cost["expected_credits"]),
        row("Maximum exposure", cost["maximum_credits"]),
        row("Fallback exposure", cost["fallback_exposure"]),
        row("Companies costing nothing", cost["companies_costing_nothing"]),
        row("Verification operations",
            ", ".join(f"{k}: {v}" for k, v in
                      (cost["verification_operations"] or {}).items()) or "none"),
        row("Actual spend", unavailable(cost["actual_note"] or "not reported"),
            raw=True),
    ])

    batches = "".join(
        f'<tr><td>{link("/batches/" + b, b)}</td><td>{esc(n)}</td></tr>'
        for b, n in (data["batches"] or {}).items())

    jobs_ = data["jobs"]
    # A client-facing role is told which room its replies land in and nothing
    # about the operations channel. Knowing that a positive reply reaches your
    # own Slack is part of the service; knowing where provider credit warnings
    # are discussed is not.
    slack_panel = ("" if slack is None
                   else slack_status_panel(slack, show_ops=not simple,
                                           link_history=not simple))
    if simple:
        return f"""
<h1>Your outbound</h1>
<div class="crumb">{esc(data['records'])} accounts researched so far</div>
{client_funnel(data.get('funnel'))}
<div class="grid2">
  <div class="panel"><h3>Campaigns</h3>
    {table(["status", "count"], campaigns) if campaigns
      else empty("No campaigns yet",
                 "Your campaigns appear here once they are built.")}
  </div>
  <div class="panel"><h3>Replies</h3>{reply_stats}
    <p class="note">Any reply pauses both channels for the whole company, so
    nobody on your list is contacted again after somebody answers.</p>
  </div>
</div>
{slack_panel}
<h2>Email quality</h2>
{client_verification}
<p class="note">No address is used on the strength of a single provider. Where
two disagreed, the contact is held for a person to look at rather than sent to
on a guess. Nothing has been sent from this system.</p>
"""

    return f"""
<p class="eyebrow">Resonate Group · Operator core</p>
<h1>Dashboard</h1>
<div class="crumb">Client <b>{esc(data['client'])}</b> &middot;
{esc(data['records'])} companies across {esc(len(data['batches']))} batch(es)</div>
{quick_actions(set(data.get('permissions') or ()))}
{head}
<h2>Operator pipeline</h2>
{operator_pipeline(set(data.get('permissions') or ()))}
<div class="dashboard-layout">
{needs}
{panel("Qualification distribution", distribution_chart(q["by_status"], "Company qualification"))}
</div>
{control_center(data.get('control_center'))}
{slack_panel}
<div class="grid2">
  <div class="panel"><h3>Batches</h3>
    {table(["batch", "companies"], batches) if batches
      else empty("No batches yet",
                 "Import a CSV of company domains to create one.")}
  </div>
  <div class="panel"><h3>Campaigns</h3>
    {table(["status", "count"], campaigns) if campaigns
      else empty("No campaigns", "Create one from a segment.")}
  </div>
</div>
<h2>Email verification</h2>
{verification}
<div class="grid2">
  <div class="panel"><h3>MX and email security</h3>
    {table(["provider", "contacts"], mx_rows) if mx_rows
      else empty("No MX results", "Screening runs before any verifier credit.")}
    <p class="note">A blocked gateway closes the <b>email</b> channel only.
    LinkedIn is untouched and the contact keeps its place.</p>
  </div>
  <div class="panel"><h3>Replies</h3>{reply_stats}
    <p class="note">Any reply pauses both channels for the whole company.</p>
  </div>
</div>
<div class="grid2">
  <div class="panel"><h3>Cost</h3>{cost_rows}</div>
  <div class="panel"><h3>Jobs</h3>
    {kv([row("Total", jobs_["jobs"]), row("Active", jobs_["active"]),
         row("Failed", jobs_["failed"]),
         row("Completed with holds", jobs_["with_holds"])])}
    <p class="small muted">{link("/diagnostics", "Operator diagnostics")}</p>
  </div>
</div>
"""


# --------------------------------------------------------------- batches

def batch_list(rows):
    if not rows:
        return ("<h1>Batches</h1>"
                + empty("No batches yet",
                        "Upload a CSV of domains to create one."))
    body = ""
    for entry in rows:
        q = entry["qualification"]["by_status"]
        body += (
            f'<tr><td>{link("/batches/" + entry["batch"], entry["batch"])}</td>'
            f'<td>{esc(entry["records"])}</td>'
            f'<td>{esc(q.get("qualified", 0))}</td>'
            f'<td>{esc(q.get("review", 0))}</td>'
            f'<td>{esc(q.get("rejected", 0))}</td>'
            f'<td>{esc(entry["qualification"]["dropped_at_ingest"])}</td></tr>')
    return ("<h1>Batches</h1>"
            + table(["batch", "companies", "qualified", "review", "rejected",
                     "dropped"], body))


def batch_detail(data, preflight_data):
    q = data["qualification"]
    dist = data["distribution"]
    cost = data["cost"]

    head = stats([
        ("companies", data["records"]),
        ("qualified", q["by_status"].get("qualified", 0), "pass"),
        ("review", q["by_status"].get("review", 0), "warn"),
        ("rejected", q["by_status"].get("rejected", 0), "block"),
        ("needs review", q["needs_manual_review"], "warn"),
        ("dropped at ingest", q["dropped_at_ingest"]),
        ("planned contacts", data["decision_makers"]["planned_contacts"]),
        ("segments", data["segments"]["segments"]),
    ])

    def dist_table(name):
        rows = "".join(f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>"
                       for k, v in (dist.get(name) or {}).items())
        return table([name.replace("_", " "), "companies"], rows)

    dropped = "".join(
        f'<tr><td>{esc(d["company"])}</td><td><code>{esc(d["domain"])}</code></td>'
        f'<td>{esc(d["reason"])}</td></tr>' for d in data["dropped"])

    free_rows = "".join(
        f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{tag(c, 'pass')}</td></tr>"
        for a, b, c in preflight_data["free"])

    plan = preflight_data.get("plan") or {}
    plan_rows = kv([
        row("Companies needing enrichment",
            plan.get("companies_requiring_enrichment", 0)),
        row("Companies costing nothing", plan.get("companies_skipped", 0)),
        row("Planned decision-maker searches", plan.get("planned_dm_searches", 0)),
        row("Maximum contacts", plan.get("maximum_contacts", 0)),
        row("Expected credits", plan.get("expected_credits", 0)),
        row("Maximum exposure", plan.get("maximum_credits", 0)),
        row("Fallback exposure", plan.get("fallback_exposure", 0)),
        row("Actual spend",
            unavailable("no provider reports per-call spend"), raw=True),
    ])
    policy = preflight_data["verification_policy"]
    job_data = data.get("jobs") or {}
    job_lines = ''.join(
        f'<tr><td>{esc(j["type"])}</td><td>{tag(j["status"])}</td>'
        f'<td>{progress(j["progress"])}<span class="small muted">'
        f'{esc(j["processed"])} / {esc(j["total"])}</span></td>'
        f'<td>{esc(j["cursor"] or "not started")}</td>'
        f'<td>{esc(j["failed"])}</td><td>{esc(j["held"])}</td></tr>'
        for j in job_data.get("rows", []))
    jobs_panel = panel("Batch execution", (
        table(["Stage", "State", "Progress", "Cursor", "Failures", "Holds"], job_lines)
        if job_lines else empty("No processing jobs yet", "The intake is stored. Start a free processing stage to continue."))
        + f'<p>{link("/jobs?" + urlencode({"batch": data["batch"]}), "Open batch processing")}</p>')

    return f"""
<h1>Batch {esc(data['batch'])}</h1>
<div class="crumb">{link("/batches", "Batches")} / {esc(data['batch'])}</div>
{head}
{jobs_panel}
<div class="panel"><h3>Pre-flight: what the engine intends to do</h3>
  <h4>Free and cheap, runs on everything</h4>
  {table(["step", "scope", "cost"], free_rows)}
  <h4>Provider plan</h4>
  {plan_rows}
  <p class="note"><b>Expected</b> is what this costs if it goes normally.
  <b>Maximum exposure</b> is what it costs if every conditional call fires, and
  it is the number a cap is set against, because it is the one that can arrive
  on an invoice. Email verification requires
  <b>{esc(policy['required_confirmations'])}</b> independent confirmations:
  {esc(policy['primary'])} first, then {esc(policy['secondary'])}, escalating
  to {esc(policy['catch_all'])}.</p>
</div>
<div class="grid3">
  <div class="panel">{dist_table("vertical")}</div>
  <div class="panel">{dist_table("region")}</div>
  <div class="panel">{dist_table("employee_band")}</div>
</div>
<div class="panel"><h3>Excluded, with reasons</h3>
  {table(["company", "domain", "reason"], dropped) if dropped
    else '<p class="note">Nothing was dropped from this batch.</p>'}
  <p class="small muted">Nothing disappears. Every excluded row keeps its
  record and its reason.</p>
</div>
"""


# ------------------------------------------------------------- companies

# --------------------------------------------------------------- senders

HEALTH_KIND = {"ok": "pass", "warming": "warn", "paused": "pause",
               "blocked": "block", "unknown": ""}


def _limit(value):
    """A configured daily limit, or the honest absence of one.

    `unavailable` rather than a dash or a zero: an inbox with no known limit
    is not an inbox that may send nothing, and it is not an inbox that may
    send fifty. It is one nobody has told us about.
    """
    return esc(value) if value is not None else unavailable(
        "no daily limit has been configured for this account")


def _capacity_panel(capacity):
    rows = ""
    for channel, cap in capacity.items():
        total = (esc(cap["known_daily_capacity"]) if cap["complete"]
                 else f'{esc(cap["known_daily_capacity"])} '
                      f'<span class="small muted">from '
                      f'{esc(cap["accounts_with_a_known_limit"])} of '
                      f'{esc(cap["accounts"])} accounts</span>')
        rows += (f'<tr><td>{esc(channel)}</td>'
                 f'<td>{esc(cap["accounts"])}</td>'
                 f'<td>{total}</td>'
                 f'<td>{esc(cap["accounts_with_no_known_limit"])}</td></tr>')
    return (table(["channel", "active accounts", "known daily capacity",
                   "accounts with no known limit"], rows)
            + '<p class="note">The capacity column is the sum of the limits '
              'somebody configured, and it is not the capacity unless the '
              'last column is zero. A guessed sending limit looks like a '
              'control and is not one, so an account nobody has told us about '
              'contributes nothing rather than a default.</p>')


def senders_page(data, csrf=None, can_manage=False, tab="overview"):
    """Who can send here, on which accounts, paired with whom.

    Four tabs over one read of the roster. The overview is the one that
    answers the question the model exists for - which humans, and how does the
    email roster differ from the LinkedIn one - so it leads.
    """
    counts = data["counts"]
    tabs = ""
    for key, label in (("overview", "Overview"), ("email", "Email"),
                       ("linkedin", "LinkedIn"), ("pairings", "Pairings"),
                       ("capacity", "Capacity")):
        on = " primary" if key == tab else ""
        tabs += (f'<a class="btn{on}" href="/senders?tab={attr(key)}">'
                 f"{esc(label)}</a> ")

    body = ""
    if tab == "overview":
        rows = ""
        for person in data["senders"]:
            pairing = person.get("pairing") or {}
            rows += (
                f'<tr><td><b>{esc(person["display_name"])}</b>'
                f'<div class="small muted">{esc(person.get("title") or "")}'
                f'{" &middot; " + esc(person["team"]) if person.get("team") else ""}'
                f'</div></td>'
                f'<td>{tag("active", "pass") if person["active"] else tag("inactive", "block")}</td>'
                f'<td>{esc(person["active_email_accounts"])} of '
                f'{esc(person["email_account_count"])}</td>'
                f'<td>{esc(person["active_linkedin_accounts"])} of '
                f'{esc(person["linkedin_account_count"])}</td>'
                f'<td class="small muted">'
                f'{esc(pairing.get("linkedin_display_name") or pairing.get("linkedin_sender_id") or "")}'
                f'</td></tr>')
        orphans = "".join(
            f'<tr><td>{esc(a["channel"])}</td>'
            f'<td><code>{esc(a["account_id"])}</code></td>'
            f'<td class="small muted">{esc(a["sender_id"])}</td></tr>'
            for a in data["orphan_accounts"])
        body = f"""
{table(["sender", "state", "inboxes", "LinkedIn profiles",
        "paired LinkedIn sender"], rows)
 if rows else empty("No senders", "This workspace has no sender identity yet.")}
<p class="note">An inbox is not a person and a LinkedIn profile is not a
person. One human here may own twenty inboxes; the email roster and the
LinkedIn roster overlap only where somebody genuinely sends on both.</p>
{section("Accounts with no owner", table(["channel", "account", "claims owner"],
                                         orphans))
 if orphans else ''}"""
    elif tab in ("email", "linkedin"):
        accounts = data["email_accounts"] if tab == "email" \
            else data["linkedin_accounts"]
        by_id = {p["sender_id"]: p for p in data["senders"]}
        rows = ""
        for account in accounts:
            owner = by_id.get(account["sender_id"])
            rows += (
                f'<tr><td><code>{esc(account["account_id"])}</code></td>'
                f'<td>{esc((owner or {}).get("display_name") or account["sender_id"])}'
                f'{"" if owner else tag("unknown owner", "block")}</td>'
                f'<td class="small">'
                f'{esc(account.get("email_address") or account.get("profile_url"))}'
                f'</td>'
                f'<td class="small muted">{esc(account.get("provider"))}'
                + (f'<div><code>{esc(account["provider_account_id"])}</code>'
                   "</div>" if account.get("provider_account_id") else "")
                + '</td>'
                f'<td>{_limit(account.get("daily_limit"))}</td>'
                f'<td>{tag(account.get("health"), HEALTH_KIND.get(account.get("health"), ""))}</td>'
                f'<td>{tag("active", "pass") if account["active"] else tag("off", "block")}</td>'
                f"</tr>")
        body = (table(["account", "owner", "address", "provider", "daily limit",
                       "health", "state"], rows, table_id=f"senders-{tab}",
                      filterable=True)
                if rows else empty("No accounts",
                                   f"No {tab} account in this workspace."))
        body += ('<p class="note">The provider column shows the identifier '
                 'that provider uses for the account. It is not a credential '
                 'and no credential is stored on these rows.</p>')
    elif tab == "pairings":
        by_id = {p["sender_id"]: p for p in data["senders"]}
        rows = "".join(
            f'<tr><td>{esc((by_id.get(p["email_sender_id"]) or {}).get("display_name") or p["email_sender_id"])}</td>'
            f'<td>{esc((by_id.get(p["linkedin_sender_id"]) or {}).get("display_name") or p["linkedin_sender_id"])}</td>'
            f'<td>{esc(p.get("campaign_id") or "every campaign")}</td>'
            f'<td class="small muted">{esc(p.get("note") or "")}</td></tr>'
            for p in data["pairings"])
        body = (table(["email sender", "LinkedIn sender", "scope", "note"],
                      rows)
                if rows else empty("No pairings",
                                   "Without a pairing the LinkedIn sender is "
                                   "allocated from the pool, and then sticks."))
        body += ('<p class="note">A pairing is a preference, not a guarantee: '
                 'if the paired human owns no active LinkedIn account the '
                 'allocation falls back to the pool. Once a contact has been '
                 'allocated either way, the pair sticks to them.</p>')
    else:
        body = _capacity_panel(data["capacity"])

    return f"""
<h1>Senders</h1>
<div class="crumb">{esc(counts["senders"])} people &middot;
{esc(counts["email_accounts"])} inbox(es) across
{esc(counts["email_senders"])} email sender(s) &middot;
{esc(counts["linkedin_accounts"])} profile(s) across
{esc(counts["linkedin_senders"])} LinkedIn sender(s)</div>
<div class="filters">{tabs}</div>
{body}
"""


def sender_assignments(data):
    """Who is carrying which contacts, and which pairs exist in practice."""
    rows = "".join(
        f'<tr><td>{esc(r["channel"])}</td>'
        f'<td>{esc(r["display_name"] or r["sender_id"])}</td>'
        f'<td>{esc(r["contacts"])}</td>'
        f'<td>{esc(r["account_count"])}</td></tr>'
        for r in data["by_sender"])
    labels = data.get("pair_labels") or {}
    pairs = "".join(
        f'<tr><td>{esc(labels.get(pair) or pair)}</td>'
        f'<td>{esc(count)}</td></tr>'
        for pair, count in data["by_pair"].items())
    return f"""
<div class="grid2">
  <div class="panel"><h3>Contacts per sender</h3>
    {table(["channel", "sender", "contacts", "accounts"], rows)
     if rows else '<p class="note">Nothing is assigned yet.</p>'}
  </div>
  <div class="panel"><h3>Sender pairs in use</h3>
    {table(["email + LinkedIn", "contacts"], pairs)
     if pairs else '<p class="note">No pair is in use yet.</p>'}
    <p class="note">A pair is how a prospect experiences this: one human in
    their inbox, one on LinkedIn. Reporting groups by the pair because that is
    the unit whose performance differs.</p>
  </div>
</div>
<p class="small muted">Unassigned:
{esc(data["unassigned"].get("email", 0))} email,
{esc(data["unassigned"].get("linkedin", 0))} LinkedIn.</p>
"""


# ------------------------------------------------------------------ jobs

def jobs_page(data, csrf):
    """Batch processing: turn the handle, watch the number, read the reasons.

    The list of steps this screen will *not* run is on the page and not hidden
    behind a disabled button, because "there is no button" and "there is a
    button that would spend money" are not the same thing to look at, and an
    operator wondering where enrichment went deserves the sentence rather than
    the silence.
    """
    rows = ""
    for j in data["rows"]:
        fails = ""
        if j["failures"]:
            fails = "".join(
                f'<div class="small block-text"><code>{esc(f.get("id"))}</code> '
                f'{esc(f.get("error"))}</div>' for f in j["failures"][:3])
        budget = (f'{esc(j["spent"])} / {esc(j["budget"])}' if j["spends"]
                  else '<span class="small muted">free</span>')
        stop = ""
        if data["can_run"] and j["status"] in ("queued", "running"):
            stop = (
                f'<form method="post" action="/jobs/cancel" '
                f'class="inline-form">'
                f'<input type="hidden" name="csrf" value="{attr(csrf)}">'
                f'<input type="hidden" name="job_id" value="{attr(j["id"])}">'
                f'<button class="btn">Stop</button></form>')
            stop += (
                f'<form method="post" action="/jobs/run" '
                f'class="inline-form">'
                f'<input type="hidden" name="csrf" value="{attr(csrf)}">'
                f'<input type="hidden" name="job_id" value="{attr(j["id"])}">'
                f'<input type="hidden" name="job_type" value="{attr(j["type"])}">'
                f'<input type="hidden" name="batch" value="{attr(j["batch"])}">'
                f'<button class="btn primary">Next slice</button></form>')
        rows += (
            f'<tr><td><code>{esc(j["id"])}</code>'
            f'<div class="small muted">{esc(j["created_at"])} &middot; '
            f'{esc(j["created_by"])}</div></td>'
            f'<td>{esc(j["type"])}</td>'
            f'<td>{esc(j["batch"])}</td>'
            f'<td>{tag(j["status"])}</td>'
            f'<td>{progress(j["progress"])}'
            f'<div class="small muted">{esc(j["processed"])} of '
            f'{esc(j["total"])} &middot; {esc(j["slices"])} slice(s)</div></td>'
            f'<td>{esc(j["failed"])}{fails}</td>'
            f'<td>{esc(j["held"])}</td>'
            f'<td>{budget}</td>'
            f'<td class="small muted"><code>{esc(j["cursor"] or "not started")}'
            f'</code></td>'
            f'<td>{stop}</td></tr>')

    batches = "".join(f'<option value="{attr(b)}">{esc(b)}</option>'
                      for b in data["batches"])
    types = "".join(
        f'<option value="{attr(r["type"])}">{esc(r["label"])}</option>'
        for r in data["runnable"])
    start = '<p class="note">Your role can read the job list but not run '\
            'anything.</p>'
    if data["can_run"] and batches:
        start = f"""
<form method="post" action="/jobs/run" class="filters">
  <input type="hidden" name="csrf" value="{attr(csrf)}">
  <span class="small muted">Run</span>
  <select name="job_type">{types}</select>
  <span class="small muted">over batch</span>
  <select name="batch">{batches}</select>
  <button class="btn primary" type="submit">Run one slice</button>
</form>"""
    elif data["can_run"]:
        start = ('<p class="note">There is no batch in this workspace yet. '
                 'Upload a CSV first.</p>')

    safe = "".join(
        f'<tr><td>{esc(r["label"])}</td><td><code>{esc(r["type"])}</code></td>'
        f'<td class="small muted">{esc(r["why_safe"])}</td></tr>'
        for r in data["runnable"])
    refused = "".join(
        f'<tr><td><code>{esc(r["type"])}</code></td>'
        f'<td class="small muted">{esc(r["why"])}</td></tr>'
        for r in data["unrunnable"])

    summary = data["summary"]
    return f"""
<h1>Batch processing</h1>
<div class="crumb">One slice of {esc(data["slice_size"])} records per request.
A crash loses a slice, never a batch.</div>
{stats([("jobs", summary["jobs"]),
        ("active", summary["active"], "warn" if summary["active"] else ""),
        ("failed", summary["failed"],
         "block" if summary["failed"] else "pass"),
        ("finished with holds", summary["with_holds"],
         "warn" if summary["with_holds"] else "")])}
<div class="panel"><h3>Start or advance a job</h3>{start}
  <p class="note">A web request never runs a batch to completion &mdash; it
  does one slice and returns, so the browser gets a progress number rather
  than a timeout. The cursor is what makes the next click continue instead of
  starting over, and it is matched by record identity, so a batch that grew
  between slices does not shift the resume point.</p>
</div>
{table(["job", "type", "batch", "status", "progress", "failed", "held",
        "budget", "cursor", ""], rows, table_id="jobs", filterable=True)
 if rows else empty("No jobs yet", "Nothing has been run in this workspace.")}
<div class="grid2">
  <div class="panel"><h3>What this screen runs</h3>
    {table(["step", "type", "why it is safe here"], safe)}
  </div>
  <div class="panel"><h3>What it will not run, and why</h3>
    {table(["type", "reason"], refused)}
    <p class="note stop">The four steps that can spend &mdash;
    <code>enrich</code>, <code>verify</code>, <code>research</code> and
    <code>personalize</code> &mdash; are refused here by a table, not by the
    absence of a button. This build makes no paid provider call from any
    surface, and the CLI requires an explicit budget for each of them even
    when that changes.</p>
  </div>
</div>
"""


def company_list(rows, batch=None, filters=None, page=None, query=None):
    filters = filters or {}
    body = ""
    for r in rows:
        reasons = "; ".join(r["reasons"][:2])
        body += (
            f'<tr><td>{link("/companies/" + r["id"], r["company"] or r["id"])}'
            f'<div class="small muted"><code>{esc(r["domain"])}</code></div></td>'
            f'<td>{tag(r["icp_status"])}</td>'
            f'<td>{tag("tier " + str(r["icp_tier"]), "info")}</td>'
            f'<td>{esc(r["icp_score"])}</td>'
            f'<td>{tag(r["icp_confidence"])}</td>'
            f'<td>{esc(r["vertical"])}</td>'
            f'<td>{esc(r["employee_band"])}</td>'
            f'<td>{esc(r["country"])}</td>'
            f'<td>{esc(r["timezone"]) or unavailable("spans zones")}</td>'
            f'<td class="small muted">{esc(reasons)}</td></tr>')
    crumb = f"Batch {esc(batch)}" if batch else "All batches"
    # The window before the rows. A reader who cannot see "1-100 of
    # 30,000" has no way to know the list is a window rather than the
    # list.
    active = {"batch": batch, "q": query, **filters}
    controls = pager(page, "/companies", active)
    hidden = ''.join(f'<input type="hidden" name="{attr(k)}" value="{attr(v)}">'
                     for k, v in active.items()
                     if k not in ("q", "icp_status") and v)
    statuses = ''.join(
        f'<option value="{attr(value)}"'
        f'{" selected" if filters.get("icp_status", "") == value else ""}>'
        f'{esc(value.title() if value else "Every ICP verdict")}</option>'
        for value in ("", "qualified", "review", "rejected", "unknown"))
    search = (f'<form class="filters" action="/companies" method="get">{hidden}'
              '<label class="sr-only" for="company-search">Search companies in this workspace</label>'
              f'<input id="company-search" type="search" name="q" value="{attr(query)}" '
              'maxlength="160" placeholder="Search company, domain or segment…">'
              '<label class="sr-only" for="company-status">ICP verdict</label>'
              f'<select id="company-status" name="icp_status">{statuses}</select>'
              '<button type="submit">Search</button>'
              '<a class="btn" href="/companies">Clear filters</a></form>')
    return f"""
<h1>Companies</h1>
<div class="crumb">{crumb} &middot; {esc((page or {}).get("total", len(rows)))}
company(s)</div>
{search}
{controls}
{table(["company", "ICP", "tier", "score", "confidence", "vertical", "band",
        "country", "timezone", "why"], body, table_id="companies",
       filterable=True) if rows else empty("No companies match", "Clear the filters or import a batch to add companies to this workspace.")}
{controls}
"""


# ------------------------------------------------------------ ICP review

def _review_badge(row):
    """What a human already decided about this company, if anything."""
    review = row.get("review")
    if review:
        word = "accepted" if review["decision"] == "accept" else "rejected"
        return (tag(word, "pass" if word == "accepted" else "block")
                + f'<div class="small muted">{esc(review.get("by"))} '
                  f'&middot; {esc(review.get("at"))}</div>')
    stale = row.get("stale_review")
    if stale:
        return (tag("outdated", "warn")
                + '<div class="small muted">reviewed, then the facts '
                  'changed</div>')
    return '<span class="small muted">not yet</span>'


def _review_form(row, csrf, can_decide, allowed_by_policy):
    if not can_decide:
        return '<span class="small muted">your role cannot decide</span>'
    if row.get("review"):
        return '<span class="small muted">decided</span>'
    common = (f'<input type="hidden" name="csrf" value="{attr(csrf)}">'
              f'<input type="hidden" name="record_id" '
              f'value="{attr(row["record_id"])}">'
              f'<input type="hidden" name="fingerprint" '
              f'value="{attr(row.get("fingerprint"))}">')
    accept_title = ("records the decision and, because this client has enabled "
                    "enrichment after review, allows this company to be "
                    "enriched" if allowed_by_policy else
                    "records the decision. This client has not enabled "
                    "dm_plan.allow_review_enrichment, so nothing is unlocked "
                    "by it")
    return (
        f'<form method="post" action="/icp/decide" class="inline-form">'
        f'{common}<input type="hidden" name="note" value="">'
        f'<button class="btn primary" name="decision" value="accept" '
        f'title="{attr(accept_title)}">Accept</button> '
        f'<button class="btn" name="decision" value="reject" '
        f'title="records a refusal. No person enrichment for this company, '
        f'whatever the score says">Reject</button></form>')


def icp_review(data, csrf):
    """The queue of companies the engine would not call either way.

    Two things are on the page that a shorter version would leave off. The
    *gate reason* is printed per row, because "accepted" and "will be enriched"
    are different facts and an operator who confuses them will be surprised by
    an invoice or by its absence. And `missing_evidence` is printed beside the
    score, because a low score on no evidence is a task and a low score on good
    evidence is a rejection - PLAYBOOK section 2 - and the two must never look
    the same.
    """
    counts = data["counts"]
    rows = ""
    for r in data["rows"]:
        gaps = "; ".join(r["missing_evidence"][:4])
        clashes = "".join(f'<div class="small block-text">{esc(c)}</div>'
                          for c in r["contradictions"][:2])
        gate = ("pass" if r["enrichment_allowed"] else "block")
        rows += (
            f'<tr><td>{link("/companies/" + r["record_id"], r["company"] or r["domain"])}'
            f'<div class="small muted"><code>{esc(r["domain"])}</code></div></td>'
            f'<td>{tag(r["status"])}<div class="small muted">'
            f'{esc(r["tier"])}</div></td>'
            f'<td>{esc(r["score"])}</td>'
            f'<td>{tag(r["confidence"])}</td>'
            f'<td class="small muted">{esc(r["vertical"])}'
            f'<div>{esc(r["employee_band"])} &middot; {esc(r["country"])}</div></td>'
            f'<td class="small muted">{esc(gaps) if gaps else "none"}{clashes}</td>'
            f'<td class="small">{esc(r["planned_contacts"])} contacts'
            f'<div class="muted">up to {esc(r["maximum_credits"])} credits</div></td>'
            f'<td>{_review_badge(r)}</td>'
            f'<td>{tag("would enrich" if r["enrichment_allowed"] else "blocked", gate)}'
            f'<div class="small muted">{esc(r["enrichment_reason"])}</div></td>'
            f'<td>{_review_form(r, csrf, data["can_decide"], data["review_enrichment_allowed"])}</td>'
            f"</tr>")

    policy = (
        '<p class="note ok">This client has <code>dm_plan.'
        'allow_review_enrichment</code> enabled, so accepting a company here '
        'lets it be enriched once the batch cost plan is approved.</p>'
        if data["review_enrichment_allowed"] else
        '<p class="note">This client has <b>not</b> enabled <code>dm_plan.'
        'allow_review_enrichment</code>. A decision is recorded either way, '
        'and a rejection still blocks enrichment permanently &mdash; but '
        'accepting will not by itself let a company that did not qualify on '
        'evidence be enriched. Widening that is a change to the client config, '
        'not a click on this page.</p>')

    def chip(href, label, count=None, on=False):
        n = f' <span class="small muted">{esc(count)}</span>' if count is not None else ""
        cls = "btn primary" if on else "btn"
        return f'<a class="{cls}" href="{attr(href)}">{esc(label)}{n}</a> '

    here = data.get("status")
    awaiting_count = sum(counts.get(s, 0) for s in data["awaiting_statuses"])
    filters = chip("/icp", "Awaiting a decision", awaiting_count,
                   on=here == "awaiting")
    filters += chip("/icp?status=all", "All companies",
                    sum(counts.values()), on=here == "all")
    for word in data["statuses"]:
        filters += chip(f"/icp?status={word}", word, counts.get(word, 0),
                        on=here == word)
    filters += chip("/icp?decided=no", "Not yet decided",
                    on=data.get("decided_filter") == "no")
    filters += chip("/icp?decided=yes", "Already decided", data["reviewed"],
                    on=data.get("decided_filter") == "yes")

    return f"""
<h1>ICP review</h1>
<div class="crumb">{esc(data["awaiting"])} awaiting a decision &middot;
{esc(data["reviewed"])} decided</div>
{stats([("qualified", counts.get("qualified", 0), "pass"),
        ("review", counts.get("review", 0), "warn"),
        ("unknown", counts.get("unknown", 0), "warn"),
        ("rejected", counts.get("rejected", 0), "block"),
        ("decided by a human", data["reviewed"], "info")])}
<div class="filters">{filters}</div>
{policy}
{table(["company", "ICP", "score", "confidence", "segment", "what is missing",
        "planned spend", "human review", "enrichment gate", ""], rows,
       table_id="icp", filterable=True)
 if rows else empty(
     "Nothing awaiting a decision" if here == "awaiting" else "Nothing here",
     "Every company in this workspace reached a verdict the engine was "
     "willing to call. Nothing is waiting on a person."
     if here == "awaiting" else "No company matches this filter.")}
<p class="note">A score and a confidence answer different questions. A low
score on good evidence is a rejection; a low score on <i>no</i> evidence is a
task, and the &ldquo;what is missing&rdquo; column is which of the two this
is. Deciding here spends nothing: it records what a person concluded.</p>
"""


def _segment_strategy(found):
    """What we would say to this segment, and how much of it is a guess.

    The confidence line comes first and is words rather than a score. A
    reader needs to know whether they are looking at a brief or at a
    starting point, and a number invites somebody to optimise it.
    """
    if not found or not found.get("exists"):
        return ""

    level = found["confidence"]["level"]
    primary = found.get("primary")
    body = (
        stats([("companies", found["companies"]),
               ("reachable", found["reachable"], "pass"),
               ("evidence", level,
                {"evidenced": "pass", "mixed": "warn",
                 "thin": "warn", "none": "block"}.get(level, ""))])
        + '<p class="note">' + esc(found["confidence"]["why"]) + ".</p>")

    if primary:
        secondary = "; ".join(row["describes"] for row in found["secondary"])
        body += section(
            "What we would lead with",
            "<p><b>" + esc(primary["describes"]) + "</b>"
            + '<span class="small muted"> &middot; '
            + esc(primary["companies"]) + " of "
            + esc(found["companies"]) + " companies</span></p>"
            + ('<p class="small muted">Then: ' + esc(secondary) + "</p>"
               if secondary else ""),
            open_=True)

    if found.get("hypotheses"):
        names = ", ".join(row["describes"] for row in found["hypotheses"])
        body += ('<p class="note">Typical for the vertical and supported by '
                 "no company here: " + esc(names) + ". Copy that leads with "
                 "one of these is leading with a guess.</p>")

    if found.get("personas"):
        rows_ = "".join(
            "<tr><td>" + esc(row["persona"]) + "</td><td>"
            + esc(row["contacts"]) + "</td></tr>"
            for row in found["personas"])
        body += section("Who we would write to",
                        table(["Persona", "Contacts"], rows_))

    if found.get("playbooks"):
        rows_ = ""
        for row in found["playbooks"]:
            rows_ += ("<tr><td><b>" + esc(row["name"]) + "</b>"
                      + '<div class="small muted">' + esc(row["when"])
                      + "</div></td><td>" + esc(row["accounts"]) + "</td>"
                      + '<td class="small muted">' + esc(row["cta"])
                      + "</td></tr>")
        body += section(
            "Approaches these accounts fit",
            table(["Playbook", "Accounts", "Asks for"], rows_)
            + ('<p class="small muted">Counted across '
               + esc(found["scanned"]) + " of " + esc(found["companies"])
               + " companies.</p>" if found["capped"] else ""))

    body += '<p class="note">' + esc(found["note"]) + "</p>"
    return panel("Strategy for " + found["segment_key"], body)


def _split_axes(by_segment):
    """How each oversized cohort could be divided, and what it would cost.

    Proposals with their numbers, and no control that applies one. Which
    axis to split on decides whether the resulting copy is right, so the
    screen shows what each division would produce and leaves the decision
    where it belongs.
    """
    if not by_segment:
        return ""

    out = ""
    for key, found in sorted(by_segment.items()):
        if not found.get("axes") and not found.get("rejected"):
            continue
        rows_ = ""
        for axis in found["axes"]:
            children = ", ".join(
                f"{c['value']} ({c['companies']})"
                + ("" if c["viable"] else " - too small to campaign")
                for c in axis["children"][:5])
            rows_ += (
                "<tr><td><b>" + esc(axis["label"]) + "</b>"
                + '<div class="small muted">' + esc(axis["why"])
                + "</div></td>"
                + "<td>" + esc(f"{axis['known_share']:.0%}") + "</td>"
                + "<td>" + esc(axis["viable_children"]) + " of "
                + esc(axis["distinct"]) + "</td>"
                + '<td class="small">' + esc(children) + "</td></tr>")

        skipped = ""
        for axis in found.get("rejected") or []:
            skipped += ("<li><b>" + esc(axis["label"]) + "</b> "
                        + '<span class="small muted">' + esc(axis["why_not"])
                        + "</span></li>")

        out += section(
            "Ways to divide " + key,
            (table(["Axis", "Known", "Viable children", "Would produce"],
                   rows_) if rows_ else
             '<p class="note">No dimension divides this cohort usefully.</p>')
            + ('<p class="small muted">Not offered: <ul>' + skipped
               + "</ul></p>" if skipped else "")
            + '<p class="note">' + esc(found["note"]) + "</p>")
    return out


def segment_health(data):
    """Segments outside the size a campaign can be written for.

    Two directions and they are not symmetrical. The ladder merges a small
    segment upward on its own, because a message written for a broader
    group is duller and that is survivable. Splitting a broad one is a
    strategy decision - split on the wrong axis and the message is wrong,
    not merely dull - so this names the cohort and leaves the choice to a
    person.
    """
    if not data["segments"]:
        return ""

    def rows(entries, kind):
        out = ""
        for entry in entries:
            examples = ", ".join(entry["examples"])
            out += (
                "<tr><td><code>" + esc(entry["segment_key"]) + "</code>"
                + '<div class="small muted">' + esc(entry["reason"])
                + "</div></td>"
                + "<td>" + tag(entry["companies"], kind) + "</td>"
                + '<td class="small muted">' + esc(examples)
                + ("&hellip;" if entry["companies"] > 4 else "")
                + "</td></tr>")
        return out

    body = stats([
        ("segments", data["segments"]),
        ("companies", data["segmented_companies"]),
        ("too small", len(data["too_small"]),
         "warn" if data["too_small"] else "pass"),
        ("too broad", len(data["too_broad"]),
         "warn" if data["too_broad"] else "pass"),
    ])

    if data["healthy"]:
        body += ('<p class="note">Every segment is between '
                 + esc(data["minimum"]) + " and " + esc(data["maximum"])
                 + " companies.</p>")

    if data["too_broad"]:
        body += section(
            "Broad enough to be worth splitting",
            table(["Segment", "Companies", "For example"],
                  rows(data["too_broad"], "warn"))
            + _split_axes(data.get("axes") or {})
            + "".join(_segment_strategy(row) for row
                      in (data.get("strategies") or {}).values())
            + '<p class="note">Above ' + esc(data["maximum"])
            + " companies, one message is unlikely to be right for all of "
              "them. Splitting is not automatic: which dimension to split "
              "on - size, country, a signal - is a strategy decision, and "
              "a cohort split on the wrong axis produces copy that is "
              "wrong rather than merely broad.</p>",
            open_=True)

    if data["too_small"]:
        body += section(
            "Below the minimum, with nothing left to merge into",
            table(["Segment", "Companies", "For example"],
                  rows(data["too_small"], "warn"))
            + '<p class="note">' + esc(data["note"]) + "</p>")

    return panel("Segment health", body)


def segment_explorer(tree, total, health=None):
    if not tree:
        return ("<h1>Segments</h1>"
                + empty("No segments yet",
                        "Segments are assigned when a batch is qualified."))
    # Health first: which cohorts are outside the size a campaign can be
    # written for is the question somebody opens this screen with, and the
    # tree below answers a different one.
    banner = segment_health(health) if health else ""
    body = ""
    for region, verticals in sorted(tree.items()):
        count = sum(b["companies"] for v in verticals.values()
                    for b in v.values())
        body += (f'<li><span class="node">{esc(region)}</span> '
                 f'{tag(str(count) + " companies", "info")}<ul class="tree">')
        for vertical, bands in sorted(verticals.items()):
            vcount = sum(b["companies"] for b in bands.values())
            body += (f'<li><span class="node">{esc(vertical)}</span> '
                     f'<span class="small muted">{esc(vcount)}</span>'
                     f'<ul class="tree">')
            for band, bucket in sorted(bands.items()):
                keys = ", ".join(bucket["segment_keys"]) or "no segment key"
                href = f"/companies?region={region}&vertical={vertical}"
                body += (f'<li>{link(href, band)} '
                         f'<span class="small muted">{esc(bucket["companies"])}'
                         f' &middot; {esc(keys)}</span></li>')
            body += "</ul></li>"
        body += "</ul></li>"
    return f"""
<h1>Segment explorer</h1>
<div class="crumb">{esc(total)} companies &middot; region &rarr; vertical &rarr;
employee band</div>
{banner}
<div class="panel"><ul class="tree">{body}</ul></div>
<p class="note">A segment key is a promise that everything inside it can
receive the same message. Segments are built at full specificity and merged
upward until each is worth writing for.</p>
"""


# -------------------------------------------------------------- contacts

MODE_WORDS = {"multichannel": "MULTICHANNEL", "email_only": "EMAIL ONLY",
              "linkedin_only": "LINKEDIN ONLY", "none": "HELD"}


def mode_tag(mode):
    return (f'<span class="tag mode {kind(mode)}">'
            f'{esc(MODE_WORDS.get(mode, mode))}</span>')


def contact_list(rows, mode=None, flag=None, page=None, batch=None, query=None):
    body = ""
    for r in rows:
        conf = ""
        if r.get("required"):
            k = "pass" if (r["confirmations"] or 0) >= r["required"] else "warn"
            conf = tag(f"{r['confirmations']}/{r['required']}", k)
            if r["disagreement"]:
                conf += tag("DISAGREE", "block")
        href = f"/contacts/{r['record_id']}/{r['contact_key']}"
        body += (
            f'<tr><td>{link(href, r["name"] or r["contact_key"])}'
            f'<div class="small muted">{esc(r["title"])}</div></td>'
            f'<td>{esc(r["company"])}</td>'
            f'<td>{mode_tag(r["mode"])}</td>'
            f'<td>{conf}</td>'
            f'<td>{esc(r["mx_provider"]) or unavailable("not checked")}</td>'
            f'<td class="small">{esc(r["email_reason"] or "eligible")}</td>'
            f'<td class="small">{esc(r["linkedin_reason"] or "eligible")}</td>'
            f"</tr>")

    def opt(name, value, current):
        sel = " selected" if value == current else ""
        return f'<option value="{attr(value)}"{sel}>{esc(name)}</option>'

    modes = "".join(opt(n, v, mode) for n, v in
                    [("Every mode", ""), ("Multichannel", "multichannel"),
                     ("Email only", "email_only"),
                     ("LinkedIn only", "linkedin_only"), ("Held", "none")])
    flags = "".join(opt(n, v, flag) for n, v in
                    [("No flag filter", ""), ("Held", "held"),
                     ("MX blocked", "mx_blocked"),
                     ("Verifier disagreement", "disagreement"),
                     ("Awaiting a 2nd confirmation", "single_verified"),
                     ("No email", "no_email"), ("No LinkedIn", "no_linkedin")])
    # The filters travel with the page number, so paging does not
    # silently drop the filter somebody is looking through.
    controls = pager(page, "/contacts", {"mode": mode, "flag": flag,
                                         "batch": batch, "q": query})
    batch_field = (f'<input type="hidden" name="batch" value="{attr(batch)}">'
                   if batch else '')
    return f"""
<h1>Contacts</h1>
<div class="crumb">{esc((page or {}).get("total", len(rows)))} contact(s)</div>
<form class="filters" method="get" action="/contacts">
  {batch_field}
  <label class="sr-only" for="contact-search">Search contacts in this workspace</label>
  <input id="contact-search" type="search" name="q" value="{attr(query)}" maxlength="160" placeholder="Search name, title or company…">
  <label class="sr-only" for="contact-mode">Channel eligibility</label>
  <select id="contact-mode" name="mode">{modes}</select>
  <label class="sr-only" for="contact-flag">Contact hold reason</label>
  <select id="contact-flag" name="flag">{flags}</select>
  <button class="btn primary" type="submit">Filter</button>
  <a class="btn" href="/contacts">Clear filters</a>
</form>
{controls}
{table(["contact", "company", "channel", "confirmations", "MX",
        "email reason", "linkedin reason"], body, table_id="contacts",
       filterable=True) if rows else empty("No contacts match", "Clear the filters to see the workspace contact list. Imported people appear after a batch is committed.")}
{controls}
"""


# -------------------------------------------------- verification and MX

VERIFIERS = ("contactout", "deliverable", "reoon")


def _evidence_age(age):
    """How old the evidence is, or why that cannot be said.

    There is no rule about how old is too old - nobody has chosen one, and
    choosing costs re-verification credits. This is here so the question
    can be answered by looking rather than guessed at:
    `MANUAL-REVIEW.md` 9b.
    """
    if not age:
        return unavailable("nothing has been asked about this address")
    if age["oldest_days"] is None:
        return unavailable(
            "undated. A verdict carried over from before this build "
            "recorded when it was obtained, and stamping it with today "
            "would be a confident wrong answer")
    days = age["oldest_days"]
    also = (f' &middot; {age["undated"]} undated'
            if age["undated"] else "")
    return (f'{esc(days)} day(s) old{also}'
            '<div class="small muted">There is no expiry rule in this '
            "build. This is the number a person needs to decide whether "
            "there should be.</div>")


def verification_block(email):
    """The double-verification panel. Every verifier, including the unasked."""
    count = email.get("confirmations")
    required = email.get("required")
    enough = (count or 0) >= (required or 1)

    rows = ""
    results = email.get("results") or {}
    for provider in VERIFIERS:
        answer = results.get(provider)
        if answer:
            verdict = str(answer.get("verdict") or "unknown")
            cell = tag(verdict.upper(), kind(verdict))
            when = esc(answer.get("checked_at") or "")
            detail = answer.get("reason") or ""
            if answer.get("is_safe_to_send") is not None:
                detail = (f"safe_to_send={answer['is_safe_to_send']} "
                          f"catch_all={answer.get('is_catch_all')} {detail}")
        elif enough:
            cell, when, detail = (tag("NOT REQUIRED", "info"), "",
                                  "the pair was already complete")
        else:
            cell, when, detail = (tag("NOT RUN", "warn"), "",
                                  "this provider was never asked")
        rows += (f"<tr><td>{esc(provider)}</td><td>{cell}</td>"
                 f"<td class='small muted'>{when}</td>"
                 f"<td class='small'>{esc(detail)}</td></tr>")

    final = ("PASS" if enough and email.get("sendable")
             else "BLOCKED" if email.get("state") == "invalid" else "HELD")
    summary = kv([
        row("Confirmations",
            tag(f"{count} / {required}", "pass" if enough else "warn")
            + (tag("DISAGREEMENT", "block") if email.get("disagreement") else ""),
            raw=True),
        row("Final verification", tag(final, kind(final.lower())), raw=True),
        row("Why", email.get("why") or unavailable("nothing has been asked"),
            raw=not email.get("why")),
        row("Confirmed by", ", ".join(email.get("confirmed_by") or [])
            or unavailable("no provider has confirmed this address"),
            raw=not (email.get("confirmed_by") or [])),
        row("Oldest evidence", _evidence_age(email.get("age")), raw=True),
    ])

    note = ""
    if email.get("disagreement"):
        note = ('<p class="note"><b>The verifiers disagree.</b> Two independent '
                "providers reached different conclusions about this address, so "
                "nothing is sent on the optimistic one. Email closes; LinkedIn "
                "is untouched.</p>")
    elif not enough and email.get("address"):
        note = (f'<p class="note"><b>Double verification incomplete.</b> '
                f"{esc(count)} of {esc(required)} independent confirmations. "
                "Held rather than blocked: one more verifier call would settle "
                "it.</p>")
    return (summary
            + table(["verifier", "verdict", "checked at", "detail"], rows)
            + note)


def mx_block(mx_data):
    provider = mx_data.get("provider")
    allowed = mx_data.get("allows_email")
    return kv([
        row("MX provider", esc(provider) if provider
            else unavailable("no MX evidence identifies the operator"),
            raw=not provider),
        row("Classification", mx_data.get("category")
            or unavailable("not classified"), raw=not mx_data.get("category")),
        row("Lookup status", mx_data.get("status")),
        row("MX hostnames", ", ".join(mx_data.get("hosts") or [])
            or unavailable("no lookup recorded"),
            raw=not (mx_data.get("hosts") or [])),
        row("Email policy",
            tag("ALLOWED" if allowed else "EMAIL BLOCKED BY POLICY",
                "pass" if allowed else "block"), raw=True),
        row("Reason", mx_data.get("reason") or "no gateway blocks this domain"),
    ])


def evidence_block(evidence_data):
    def rows(items):
        if not items:
            return None
        out = ""
        for item in items:
            out += (
                f'<div class="step"><div>{esc(item.get("fact"))}</div>'
                f'<div class="small muted space-above">'
                f'{tag(item.get("provider") or "unknown provider", "info")}'
                f'{tag(item.get("source_type") or "unknown source")}'
                f'{tag((item.get("quality") or "unrated") + " quality")}'
                f'{tag((item.get("freshness") or "undated") + " freshness")}'
                f"</div>"
                f'<div class="small muted">published '
                f'{esc(item.get("published_at") or "unknown")} &middot; '
                f'retrieved {esc(item.get("retrieved_at") or "unknown")} '
                f'&middot; relevance {esc(item.get("relevance"))}</div>'
                f'<div class="small">{external(item.get("source_url"))}</div>'
                f"</div>")
        return out

    company = rows(evidence_data.get("company"))
    person = rows(evidence_data.get("person"))
    caution = ('<p class="note">Evidence is scraped, untrusted text. It is '
               "stored as a dated, attributed fact with a relevance score and "
               "never as prose, so a page telling the reader to ignore previous "
               "instructions arrives here as data with a score rather than as a "
               "line in a prompt.</p>")
    return (
        "<h4>Company evidence</h4>"
        + (company or f'<p>{unavailable("no company evidence was retained")}</p>')
        + "<h4>Person evidence</h4>"
        + (person or f'<p class="note">{esc(evidence_data.get("person_note"))}</p>')
        + caution)


def personalization_block(p):
    comps = p.get("components") or {}
    bars = ""
    for name, value in comps.items():
        if not isinstance(value, (int, float)):
            continue
        bars += (f'<div class="small component-score">'
                 f'<span class="muted">{esc(name.replace("_", " "))}</span> '
                 f"<b>{esc(round(float(value), 2))}</b>{progress(float(value))}"
                 f"</div>")
    caution = ('<p class="note">These five components are arithmetic over '
               "stored evidence. Nothing specific about the company caps the "
               "band at <b>low</b> however good everything else is, which is "
               "what stops anyone inventing a recent post to fill the gap.</p>")
    return (kv([
        row("Persona", p.get("persona")),
        row("Angle", p.get("angle")),
        row("Personalisation band",
            tag(str(p.get("band")),
                "pass" if p.get("band") == "high"
                else "warn" if p.get("band") == "medium" else "block"),
            raw=True),
        row("Meets the campaign minimum",
            tag("yes" if p.get("meets_minimum") else "no",
                "pass" if p.get("meets_minimum") else "block"), raw=True),
        row("Evidence pieces considered", p.get("evidence_count")),
        row("Why", p.get("why")),
    ]) + bars + caution)


# ------------------------------------------------- company and contact detail

def company_dossier(d):
    icp = d["icp"]
    seg = d["segment"]
    facts = (d.get("evidence") or {}).get("company_facts") or {}

    overview = kv([
        row("Company", d.get("company")),
        row("Domain", f"<code>{esc(d.get('domain'))}</code>", raw=True),
        row("ICP", tag(icp.get("status")) + tag("tier " + str(icp.get("tier")),
                                                "info")
            + tag(f"score {icp.get('score')}", "info")
            + tag(f"{icp.get('confidence')} confidence"), raw=True),
        row("Vertical", seg.get("vertical")),
        row("Subvertical", seg.get("subvertical")),
        row("Industry", facts.get("industry")),
        row("Employees", f"{seg.get('employees')} ({seg.get('employee_band')})"),
        row("Country", (seg.get("country") or "").title()),
        row("Region", seg.get("region")),
        row("Timezone", seg.get("timezone")
            or unavailable("the country spans several zones and nothing "
                           "narrows it"), raw=not seg.get("timezone")),
        row("Schedulable", tag("yes" if seg.get("schedulable") else "no",
                               "pass" if seg.get("schedulable") else "warn"),
            raw=True),
        row("Segment", d.get("campaign", {}).get("segment_key")
            or unavailable("not segmented")),
    ])

    def bullets(items, cls=""):
        if not items:
            return ""
        rows_ = "".join(f"<li>{esc(i)}</li>" for i in items)
        return f'<ul class="{cls}">{rows_}</ul>'

    signals = ""
    if icp.get("positive_signals"):
        signals += "<h4>Positive signals</h4><ul>" + "".join(
            f'<li><b>{esc(s["dimension"])}</b> +{esc(s["weight"])} '
            f'&mdash; {esc(s["why"])}</li>'
            for s in icp["positive_signals"][:8]) + "</ul>"
    if icp.get("negative_signals"):
        signals += "<h4>Negative signals</h4><ul>" + "".join(
            f'<li><b>{esc(s["dimension"])}</b> {esc(s["weight"])} '
            f'&mdash; {esc(s["why"])}</li>'
            for s in icp["negative_signals"][:8]) + "</ul>"
    if icp.get("missing_evidence"):
        signals += ("<h4>What we do not know</h4>"
                    '<p class="note">Missing information never counts as a '
                    "positive signal. It costs confidence.</p>"
                    + bullets(icp["missing_evidence"][:8]))
    if icp.get("contradictions"):
        signals += "<h4>Contradictory evidence</h4><ul>" + "".join(
            f'<li>{esc(c.get("kind"))} &mdash; {esc(c.get("why"))}</li>'
            for c in icp["contradictions"]) + "</ul>"

    contacts = ""
    for c in d.get("contacts") or []:
        if not c:
            continue
        href = f"/contacts/{c['record_id']}/{c['contact_key']}"
        contacts += (
            f'<tr><td>{link(href, c.get("name"))}</td>'
            f'<td>{esc(c.get("title"))}</td>'
            f'<td>{esc(c.get("persona"))}</td>'
            f'<td>{mode_tag(c.get("mode"))}</td>'
            f'<td>{esc((c.get("email") or {}).get("confirmations"))}/'
            f'{esc((c.get("email") or {}).get("required"))}</td></tr>')

    excluded = "".join(
        f'<tr><td>{esc(e.get("name"))}</td><td>{esc(e.get("title"))}</td>'
        f'<td>{esc(e.get("why"))}</td></tr>' for e in d.get("excluded") or [])

    events_ = "".join(
        f'<tr><td class="small muted">{esc(e.get("at"))}</td>'
        f'<td>{esc(e.get("type"))}</td>'
        f'<td class="small">{esc(e.get("contact") or "")}</td></tr>'
        for e in (d.get("events") or [])[-25:])

    persona = d.get("persona_plan") or {}
    plan = kv([
        row("Strategy", persona.get("strategy")),
        row("Why", persona.get("strategy_reason")),
        row("Priority personas", ", ".join(persona.get("priority_personas") or [])),
        row("Target titles", ", ".join((persona.get("target_titles") or [])[:8])),
        row("Contacts to enrich", persona.get("max_contacts")),
        row("Cap reason", persona.get("reason")),
    ])

    return f"""
<h1>{esc(d.get('company'))}</h1>
<div class="crumb">{link("/companies", "Companies")} /
<code>{esc(d.get('domain'))}</code></div>
<div class="grid2">
  <div class="panel"><h3>Overview</h3>{overview}</div>
  <div class="panel"><h3>Why this company</h3>
    <ul>{"".join(f"<li>{esc(r)}</li>" for r in icp.get("reasons") or [])}</ul>
    {signals}
  </div>
</div>
<div class="panel"><h3>Who we would approach</h3>{plan}
  {table(["contact", "title", "persona", "channel", "confirmations"], contacts)
   if contacts else empty("No contacts", "Decision-maker enrichment has not run.")}
  {("<h4>Considered and not selected</h4>"
    + table(["name", "title", "why not"], excluded)) if excluded else ""}
</div>
<div class="panel"><h3>Events</h3>
  {table(["at", "event", "contact"], events_) if events_
   else '<p class="note">No events recorded for this record.</p>'}
</div>
"""


ARROW = {"out": "&rarr;", "in": "&larr;"}

# What each kind of entry is, for somebody who has never read the event log.
ENTRY_WORDS = {
    "touch": "we contacted them",
    "reply": "they replied",
    "connection": "they accepted",
    "decision": "what we did about it",
    "intent": "a date they named",
    "referral": "a referral",
    "account": "the account",
}


def conversation_block(thread, also=()):
    """One person, both channels, in order.

    The arrow column is the point of it: an operator scanning a
    multichannel cadence needs to see which way each line went before
    reading any of them.
    """
    if thread is None:
        return empty("No conversation", "this contact is not on the record")

    summary = thread["summary"]
    head = kv([
        row("Where they stand", tag(summary["state"], "pass"), raw=True),
        row("Channels we used", ", ".join(summary["channels_used"])
            or unavailable("nothing confirmed has gone to them"),
            raw=not summary["channels_used"]),
        row("Channels they answered on",
            ", ".join(summary["channels_replied"])
            or unavailable("they have not replied"),
            raw=not summary["channels_replied"]),
        row("Confirmed touches", summary["confirmed_touches"]),
        row("Replies", summary["replies"]),
        row("Waiting until", summary["return_date"]
            or unavailable("no date was named"),
            raw=not summary["return_date"]),
    ])

    flags = "".join(
        f'<p class="note stop">{esc(flag)}</p>' for flag in summary["flags"])

    rows_html = ""
    for entry in thread["entries"]:
        arrow = ARROW.get(entry["direction"], "")
        # The one row an operator has to look twice at: a confirmed step
        # that went out after this person had already answered.
        mark = ' class="flagged"' if entry.get("after_a_reply") else ""
        rows_html += (
            f"<tr{mark}><td>{esc(entry.get('at') or 'undated')}</td>"
            f"<td>{arrow}</td>"
            f"<td>{esc(ENTRY_WORDS.get(entry['kind'], entry['kind']))}</td>"
            f"<td>{esc(entry.get('channel') or '')}</td>"
            f"<td>{esc(entry['summary'])}</td></tr>")
    body = (table(["When", "", "What", "Channel", "Detail"], rows_html)
            if rows_html else
            empty("Nothing yet", "no touch, reply or decision is recorded "
                                 "for this person"))

    elsewhere = ""
    if also:
        cells = "".join(
            f"<tr><td>{link(row_['where'], row_['name'])}</td>"
            f"<td>{esc(row_['company'])}</td>"
            f"<td>{esc(', '.join(row_['matched_on']))}</td>"
            f"<td>{row_['events']}</td></tr>" for row_ in also)
        elsewhere = (
            '<p class="small muted">The same person appears on another '
            "record in this workspace, matched on an exact identifier. "
            "Listed rather than merged: one company's history under "
            "another company's heading would be a claim nobody "
            "reviewed.</p>"
            + table(["Contact", "Company", "Matched on", "Events"], cells))

    return (f'<div class="panel">{head}</div>{flags}{body}{elsewhere}'
            f'<p class="small muted">{esc(thread["text_note"])}.</p>')


def contact_detail(view, outreach_data):
    # The sender panel and the real history lead, because "who is writing to
    # this person and what have they already received" is the first question
    # anybody opening a contact is asking.
    email = view["email"]
    linkedin = view["linkedin"]

    head = kv([
        row("Company", link("/companies/" + view["record_id"], view["company"]),
            raw=True),
        row("Title", view.get("title")),
        row("Persona", view.get("persona")),
        row("Angle", view.get("angle")),
        row("Final channel decision", mode_tag(view["mode"]), raw=True),
    ])

    email_rows = kv([
        row("Address", email.get("address")
            or unavailable("no address was found"),
            raw=not email.get("address")),
        row("Sendable", tag("yes" if email.get("sendable") else "no",
                            "pass" if email.get("sendable") else "block"),
            raw=True),
        row("Email eligible", tag("YES" if email["eligible"] else "NO",
                                  "pass" if email["eligible"] else "block"),
            raw=True),
        row("Reason", email.get("reason") or "eligible"),
        row("In plain words", email.get("reason_text")
            or "this address may be written to"),
    ])
    linkedin_rows = kv([
        row("Profile", f"<code>{esc(linkedin.get('url'))}</code>"
            if linkedin.get("url")
            else unavailable("no profile was found for this person"), raw=True),
        row("LinkedIn eligible", tag("YES" if linkedin["eligible"] else "NO",
                                     "pass" if linkedin["eligible"] else "block"),
            raw=True),
        row("Reason", linkedin.get("reason") or "eligible"),
        row("In plain words", linkedin.get("reason_text")
            or "this profile may be approached"),
    ])

    return f"""
<h1>{esc(view.get('name'))}</h1>
<div class="crumb">{link("/contacts", "Contacts")} / {esc(view.get('company'))}
</div>
<div class="panel">{head}</div>
{section("Conversation", conversation_block(view.get("conversation"),
                                            view.get("also_known") or []),
         open_=True)}
{section("Email verification", verification_block(email), open_=True)}
{section("MX and email security", mx_block(view["mx"]), open_=True)}
{section("Email eligibility", email_rows)}
{section("LinkedIn eligibility", linkedin_rows)}
{section("Research and evidence", evidence_block(view["evidence"]))}
{section("Personalisation", personalization_block(view["personalization"]))}
{section("Full outreach", outreach_block(outreach_data), open_=True)
 if outreach_data else ""}
"""


# --------------------------------------------------------------- outreach

STEP_WORDS = {"eligible": "will send", "pushed": "already sent",
              "unapproved": "needs approval",
              "waiting": "waiting on a connection", "blocked": "blocked",
              "skipped": "skipped", "paused": "paused",
              "not_planned": "not planned"}


def _cross_channel_block(cross):
    """Whether this step may refer to the other channel, and why.

    Always rendered when a context exists, including - especially - when the
    answer is no. A preview that only showed the allowed case would leave a
    reviewer unable to tell "there was nothing to reference" from "there was
    something and we refused it", which are the two states QA has to
    distinguish.
    """
    if not cross:
        return ""
    allowed = cross.get("may_reference")
    reference = cross.get("reference") or {}
    head = (tag("cross-channel reference ALLOWED", "pass") if allowed
            else tag("cross-channel reference NOT ALLOWED", "warn"))
    detail = ""
    if allowed and reference:
        detail = (f'<div class="small">Previous confirmed touch: '
                  f'<b>{esc(reference.get("display_name"))}</b> on '
                  f'{esc(reference.get("channel"))}, day '
                  f'{esc(reference.get("day"))} &middot; '
                  f'{esc(reference.get("state"))}</div>')
    applied = ""
    if cross.get("applied"):
        applied = tag(cross["applied"].replace("_", " "), "info")
    return (f'<div class="xchan {"ok" if allowed else "no"}">{head}{applied}'
            f'{detail}<div class="small muted">{esc(cross.get("reason"))}</div>'
            f"</div>")


def contact_timeline(history):
    """What actually happened to this contact, in order.

    The states are deliberately not collapsed into "sent". "planned",
    "payload built" and "confirmed sent" look the same from the outside and
    mean entirely different things to anybody deciding what a later message
    may claim.
    """
    if not history or not history.get("steps"):
        return ""
    rows = ""
    for step in history["steps"]:
        cls = "confirmed" if step["confirmed"] else "refused"
        who = step.get("sender_id") or ""
        rows += (
            f'<li class="{cls}"><b>Day {esc(step["day"])}</b> '
            f'{tag(step["channel"] or "?", "info")} '
            f'{tag(step["state"], "pass" if step["confirmed"] else kind(step["state"]))}'
            f'{" &middot; " + esc(who) if who else ""}'
            f'<div class="small muted">{esc(step["state_words"])}'
            f'{" &middot; " + esc(step["at"]) if step.get("at") else ""}'
            f'{"" if step.get("in_current_cadence", True) else " &middot; not in the current cadence"}'
            f"</div></li>")
    return f"""
<div class="panel"><h3>What has actually happened</h3>
  <ul class="timeline">{rows}</ul>
  <p class="note">Confirmed means an event established it:
  <code>push_marked</code>, <code>email_delivered</code> or
  <code>linkedin_connected</code>. A built payload is not a send, an approved
  draft is not a send, and only a confirmed touch may be referred to in a
  later message.</p>
</div>"""


def sender_panel(senders, stale=False):
    """The two humans on this contact, and how they got there."""
    if not senders:
        return ""
    rows = ""
    for channel in ("email", "linkedin"):
        row = senders.get(channel)
        if not row:
            rows += (f'<tr><th>{esc(channel)}</th><td>'
                     f'{unavailable("no sender assigned on this channel")}'
                     f"</td></tr>")
            continue
        rows += (f'<tr><th>{esc(channel)}</th><td><b>'
                 f'{esc(row.get("display_name") or row.get("sender_id"))}</b> '
                 f'<span class="small muted">{esc(row.get("account_id"))}'
                 f'{" &middot; " + esc(row.get("address")) if row.get("address") else ""}'
                 f' &middot; via {esc(row.get("via"))}</span></td></tr>')
    history = ""
    if senders.get("history"):
        history = "".join(
            f'<li class="small">{esc(h.get("at"))} &middot; {esc(h.get("channel"))}: '
            f'{esc((h.get("from") or {}).get("sender_id"))} &rarr; '
            f'{esc((h.get("to") or {}).get("sender_id"))} '
            f'by {esc(h.get("by"))} &mdash; {esc(h.get("reason"))}</li>'
            for h in senders["history"])
        history = f"<h4>Reassignments</h4><ul>{history}</ul>"
    warn = ('<p class="note">The sender pool has changed since this contact '
            'was assigned. The assignment has deliberately not moved: a '
            'changed pool is a reason for a person to look, not for the '
            'software to move a prospect between humans.</p>') if stale else ""
    return f"""
<div class="panel"><h3>Who owns this prospect</h3>
  <table class="kv">{rows}</table>
  {history}{warn}
  <p class="note">The email human and the LinkedIn human are separate
  relationships and may be different people. Once assigned they stick, so a
  prospect is never handed between humans mid-cadence by accident.</p>
</div>"""


def outreach_block(data):
    if not data:
        return ""
    steps = ""
    for s in data["steps"]:
        k = kind(s["status"])
        reasons = ""
        if not s["lint_ok"]:
            reasons += (f'<div class="small text-block">Lint: '
                        f'{esc(", ".join(s["lint"]))}</div>')
        if s["eligibility_reasons"]:
            reasons += (f'<div class="small muted">Eligibility: '
                        f'{esc(", ".join(s["eligibility_reasons"]))}</div>')
        if s.get("blocked_by"):
            blocked = s["blocked_by"]
            blocked = ", ".join(blocked) if isinstance(blocked, list) else str(blocked)
            reasons += (f'<div class="small text-block">'
                        f"Blocked by: {esc(blocked)}</div>")
        if s.get("requires"):
            reasons += (f'<div class="small muted">Requires '
                        f"{esc(s['requires'])} &mdash; no connection-accepted "
                        "state is assumed, so this waits rather than firing"
                        "</div>")

        body = ""
        if s["channel"] == "email":
            if s.get("subject"):
                body += (f'<div class="message-subject">'
                         f'Subject: {esc(s["subject"])}</div>')
            body += f'<pre class="copy">{esc(s.get("text"))}</pre>'
            body += (f'<div class="small muted">{esc(s["words"])} words '
                     f"&middot; angle {esc(s.get('angle'))} &middot; "
                     f"{'generated' if s.get('generated') else 'template ' + esc(s.get('template') or '')}"
                     f"</div>")
        elif s.get("text"):
            body += f'<pre class="copy">{esc(s.get("text"))}</pre>'
            body += (f'<div class="small muted">{esc(s["characters"])} '
                     f"characters &middot; template "
                     f"{esc(s.get('template') or 'none')}</div>")
        else:
            body += (f'<p>{unavailable("this activity carries no text: it is a "
                                       "connection request, or it has not been "
                                       "expanded")}</p>')

        sender = s.get("sender") or {}
        who = ""
        if sender.get("display_name"):
            who = (f'<div class="small">From <b>{esc(sender["display_name"])}</b>'
                   f' <span class="muted">via {esc(s["provider"])} / '
                   f'{esc(sender.get("account_id"))}'
                   f'{" &middot; " + esc(sender.get("address")) if sender.get("address") else ""}'
                   f'</span></div>')
        elif s.get("sender") is None:
            who = (f'<div class="small">{unavailable("no sender is assigned "
                   "to this contact on this channel")}</div>')

        steps += (
            f'<div class="step {k}"><div class="stephead">'
            f'<span class="day">DAY {esc(s["day"])}</span>'
            f'{tag(s["provider"], "info")}'
            f'{tag(STEP_WORDS.get(s["status"], s["status"]), k)}'
            f'<span class="small muted push-end">'
            f'{esc(s["step"])}</span></div>{who}'
            f'{_cross_channel_block(s.get("cross_channel"))}'
            f'{body}{reasons}</div>')

    lead = (sender_panel(data.get("senders"), data.get("assignment_stale"))
            + contact_timeline(data.get("history")))
    coherence = data["coherence"]
    findings = ""
    if coherence["findings"]:
        findings = "<ul>" + "".join(
            f'<li>{tag(f["severity"], kind(f["severity"]))} '
            f'<b>{esc(f["kind"])}</b> &mdash; {esc(f["message"])}</li>'
            for f in coherence["findings"]) + "</ul>"
    else:
        findings = ('<p class="note">The email and LinkedIn steps read as one '
                    "conversation: nothing repeats, nothing contradicts, and no "
                    "step references the other channel.</p>")

    sched = data.get("schedule") or {}
    when = ""
    if sched.get("schedulable"):
        rows_ = "".join(
            f'<tr><td>{esc(x["step"])}</td><td>{esc(x["channel"])}</td>'
            f'<td>{esc(x.get("local_at"))}</td><td>{esc(x.get("utc_at"))}</td>'
            f'</tr>' for x in sched.get("steps") or [])
        when = table(["step", "channel", "local", "UTC"], rows_)
    else:
        when = f'<p>{unavailable(sched.get("why") or "not schedulable")}</p>'

    paused = ""
    if data.get("paused"):
        paused = (f'<div class="banner">{tag("PAUSED", "pause")} '
                  f'{esc(data.get("pause_reason") or "this company replied")}. '
                  "The pause is company-wide and covers both channels. Nothing "
                  "is deleted: every step keeps its place and its reason.</div>")

    return f"""
{paused}
{lead}
<p class="small muted">One conversation, both channels, in the order the
prospect experiences it.</p>
{steps}
<h4>Cross-channel coherence &mdash; {tag(coherence["verdict"],
                                         kind(coherence["verdict"]))}</h4>
{findings}
<h4>When each step would fire, in the prospect's own time</h4>
{when}
"""


# -------------------------------------------------------------- campaigns

# -------------------------------------------------- full outreach preview

def full_outreach(data):
    """One campaign, everything that would go out, and what would not.

    Built out of `outreach_block` - the same renderer the contact screen uses -
    so a step reads identically wherever it is shown. A second renderer for the
    same object is a second chance to describe it differently.
    """
    picker = "".join(
        f'<option value="{attr(c["campaign_id"])}"'
        f'{" selected" if c["campaign_id"] == data.get("chosen") else ""}>'
        f'{esc(c["name"] or c["campaign_id"])} &middot; {esc(c["status"])}'
        f"</option>" for c in data["campaigns"])
    chooser = (
        f'<form method="get" action="/outreach" class="filters">'
        f'<span class="small muted">Campaign</span>'
        f'<select name="campaign" data-autosubmit>{picker}</select>'
        f'<noscript><button class="btn" type="submit">Show</button></noscript>'
        f"</form>") if picker else ""

    campaign = data.get("campaign")
    if not campaign:
        return ("<h1>Full outreach preview</h1>" + chooser
                + empty("Nothing to preview",
                        "This workspace has no campaign yet. Build one from a "
                        "segment first."))

    t = data["totals"]
    blocked = "".join(
        f'<tr><td>{esc(row_["reason"])}</td><td>{esc(row_["steps"])}</td>'
        f'<td class="small muted">{esc(row_["means"])}</td></tr>'
        for row_ in data["blocked_reasons"])
    schedule = "".join(
        f'<tr><td>Day {esc(day)}</td><td>{esc(count)}</td></tr>'
        for day, count in data["days"].items())

    cards = "".join(
        f'<div class="panel"><h3>{esc(view["name"] or view["contact_key"])}'
        f' <span class="small muted">{esc(view["company"])}</span> '
        f'{mode_tag(view["mode"])}'
        f'{tag("paused", "pause") if view["paused"] else ""}</h3>'
        f'{outreach_block(view)}</div>'
        for view in data["cards"])

    omitted = ""
    if data["omitted"]:
        omitted = (f'<p class="note">Showing {esc(data["shown"])} of '
                   f'{esc(t["contacts"])} contacts. The other '
                   f'{esc(data["omitted"])} are counted in every number above '
                   f'but not drawn &mdash; a full card is several kilobytes, '
                   f'and a page nobody opens is not a preview. Open a contact '
                   f'to read one that is not here.</p>')

    return f"""
<h1>Full outreach preview</h1>
<div class="crumb">{link("/campaigns/" + campaign["campaign_id"],
                         campaign["name"] or campaign["campaign_id"])}
&middot; {esc(campaign["status"])} &middot; {esc(campaign["companies"])}
companies</div>
{chooser}
<div class="banner stop"><b>Nothing here is sent.</b> This is what the
providers would receive if sending were enabled. It is not, at four levels:
there is no route that sends, no role below super admin carries
<code>campaign.launch</code>, <code>push.run(live=True)</code> raises, and
every payload below carries <code>delivered: false</code> and the reason.</div>
{stats([("contacts", t["contacts"]),
        ("steps", t["steps"]),
        ("would run", t["will_run"], "pass"),
        ("would not", t["blocked"], "block"),
        ("email steps", t["email_steps"]),
        ("linkedin steps", t["linkedin_steps"]),
        ("lint failures", t["lint_failures"],
         "block" if t["lint_failures"] else "pass"),
        ("paused contacts", t["paused_contacts"],
         "pause" if t["paused_contacts"] else "")])}
<div class="grid2">
  <div class="panel"><h3>Why a step would not run</h3>
    {table(["reason", "steps", "what it means"], blocked) if blocked
     else '<p class="note ok">Every step in this campaign is eligible.</p>'}
  </div>
  <div class="panel"><h3>When it would land</h3>
    {table(["day", "steps"], schedule) if schedule
     else '<p class="note">No step is eligible, so nothing is scheduled.</p>'}
    <p class="small muted">Days are cadence days from the campaign start, not
    calendar dates. The send window per contact is their local business
    morning &mdash; see {link("/timezones", "Timezones")}.</p>
  </div>
</div>
{section("QA report", qa_block(data["qa"]))}
{section("Provider payloads that would be submitted",
         provider_previews(data["payloads"]))}
<h2>Every contact, every step</h2>
{omitted}
{cards if cards else empty("No contacts",
                           "This campaign has no selected contact.")}
"""


def _pause_control(row, csrf, can_pause):
    """Stop, or start again. Never launch - there is no such button anywhere.

    Pausing is offered from reviewer upward while launching is offered to
    nobody, and the asymmetry is the point: the person who can see something
    is wrong should be able to stop it without finding somebody more senior
    first, and nobody at all should be able to start it from a browser.
    """
    if not can_pause:
        return '<span class="small muted">your role cannot pause</span>'
    common = (f'<input type="hidden" name="csrf" value="{attr(csrf)}">'
              f'<input type="hidden" name="campaign_id" '
              f'value="{attr(row["campaign_id"])}">')
    if row.get("paused"):
        return (f'<form method="post" action="/campaigns/resume" '
                f'class="inline-form">{common}'
                f'<button class="btn">Resume</button></form>'
                f'<div class="small muted">Resuming re-runs every check.</div>')
    return (f'<form method="post" action="/campaigns/pause" '
            f'class="inline-form">{common}'
            f'<input name="why" placeholder="why" maxlength="200">'
            f'<button class="btn">Pause</button></form>')


def campaign_list(rows, csrf=None, can_pause=False):
    if not rows:
        return ("<h1>Campaigns</h1>"
                + empty("No campaigns",
                        "Create one from a segment in the campaign builder."))
    body = ""
    for r in rows:
        mapping = ("both mapped" if r["bison_campaign_id"] and r["heyreach_campaign_id"]
                   else "partly mapped" if (r["bison_campaign_id"]
                                            or r["heyreach_campaign_id"])
                   else "not mapped")
        paused = ""
        if r.get("paused"):
            paused = (f'{tag("paused", "pause")}<div class="small muted">'
                      f'{esc(r.get("pause_reason"))}</div>')
        body += (
            f'<tr><td>{link("/campaigns/" + r["campaign_id"], r["name"])}</td>'
            f'<td>{tag(r["status"])}{paused}</td>'
            f'<td>{esc(r["records"])}</td>'
            f'<td>{tag(r["approval"] or "none", kind(r["approval"]))}</td>'
            f'<td class="small muted">{esc(mapping)}</td>'
            f'<td>{tag(r["launch"] or "not_launched", "pause")}</td>'
            f'<td>{_pause_control(r, csrf, can_pause)}</td></tr>')
    return ("<h1>Campaigns</h1>"
            + '<div class="crumb">Nothing here launches. There is no launch '
              'control on this screen or any other, and '
              '<code>push.run(live=True)</code> raises.</div>'
            + table(["campaign", "status", "companies", "approval", "provider "
                     "mapping", "launch", ""], body))


# ------------------------------------------------------ campaign builder

def _mix(counter, total=None):
    """A distribution, printed as counts rather than as a bar chart.

    Percentages of eleven companies are how a demo starts sounding like a
    study. The denominator is printed beside the numbers so the reader can
    make whatever ratio they actually want.
    """
    if not counter:
        return unavailable("nothing selected yet")
    ordered = sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0])))
    out = " ".join(f'{tag(str(k), "info")}<span class="small muted">'
                   f"{esc(v)}</span>" for k, v in ordered[:6])
    if total:
        out += f'<div class="small muted">of {esc(total)}</div>'
    return out


def sender_strategy_panel(data):
    """Who would send this campaign, and whether the two channels can carry it.

    The asymmetry is the point: a hundred inboxes and six LinkedIn profiles is
    not one capacity, and a screen that added them together would be planning
    against a number that does not exist.
    """
    if not data:
        return ""
    planned, capacity = data["planned"], data["capacity"]
    warnings = "".join(
        f'<li>{esc(w)}</li>' for w in data["warnings"])
    people = "".join(
        f'<tr><td>{esc(p["display_name"])}</td>'
        f'<td>{esc(p["email_accounts"])}</td>'
        f'<td>{esc(p["linkedin_accounts"])}</td></tr>'
        for p in data["senders"])
    pairs = "".join(
        f'<tr><td>{esc(p["email_sender_id"])}</td>'
        f'<td>{esc(p["linkedin_sender_id"])}</td>'
        f'<td>{esc(p.get("campaign_id") or "every campaign")}</td></tr>'
        for p in data["pairings"])

    def cap_cell(channel):
        cap = capacity[channel]
        if not cap["accounts"]:
            return unavailable(f"no active {channel} account")
        if cap["complete"]:
            return f'{esc(cap["known_daily_capacity"])} a day'
        return (f'{esc(cap["known_daily_capacity"])} a day '
                f'<span class="small muted">from '
                f'{esc(cap["accounts_with_a_known_limit"])} of '
                f'{esc(cap["accounts"])} accounts &mdash; the rest have no '
                f'configured limit</span>')

    options = data["options"]
    return f"""
<div class="panel"><h3>Sender strategy</h3>
  {stats([("email accounts", capacity["email"]["accounts"]),
          ("linkedin accounts", capacity["linkedin"]["accounts"]),
          ("planned contacts", planned["contacts"]),
          ("planned email touches", planned["email_touches"]),
          ("planned linkedin touches", planned["linkedin_touches"])])}
  <table class="kv">
    <tr><th>Email capacity</th><td>{cap_cell("email")}</td></tr>
    <tr><th>LinkedIn capacity</th><td>{cap_cell("linkedin")}</td></tr>
    <tr><th>Allocation</th><td>Explicit pairing where one exists, otherwise
      from the eligible pool. Either way it sticks to the contact.</td></tr>
    <tr><th>Team-handoff language</th><td>
      {tag("on", "pass") if options["colleague_language"] else tag("off", "warn")}
      <span class="small muted">from
      <code>sender_policy.colleague_language</code> in the client config</span>
      </td></tr>
    <tr><th>Same-sender continuity</th><td>{tag("on", "pass")}
      <span class="small muted">no permission needed: the same person on both
      channels makes no claim about anybody else</span></td></tr>
  </table>
  {f'<ul class="note">{warnings}</ul>' if warnings else
   '<p class="note ok">Both channels have an active account and a known '
   'capacity.</p>'}
  <div class="grid2">
    <div>{table(["sender", "inboxes", "LinkedIn"], people)}</div>
    <div>{table(["email sender", "LinkedIn sender", "scope"], pairs)
          if pairs else '<p class="note">No explicit pairing; the LinkedIn '
                        'sender is allocated from the pool.</p>'}</div>
  </div>
  <p class="note stop">None of these settings can override the touch history.
  A message may only refer to a previous cross-channel touch that actually
  happened, whatever is switched on here.</p>
</div>
"""


def campaign_builder(data, csrf):
    """Pick a segment; see exactly what a campaign off it would contain.

    The page has no field that changes who is in the segment. That is not an
    omission: `campaignseg.assign` decided the grouping and
    `campaignseg.why_together` explains it, and a builder that let an operator
    hand-pick a population would be a second answer to a question that already
    has one.
    """
    rows = ""
    for seg in data["segments"]:
        state = (tag("ready", "pass") if seg["buildable"]
                 else tag("all in campaigns", "muted"))
        where = ", ".join(f"{k} ({v})" for k, v in
                          sorted(seg["already_in"].items())) or "none"
        rows += (
            f'<tr><td>{link("/campaigns/new?segment=" + seg["segment_key"], seg["segment_key"])}'
            f'<div class="small muted">{esc(seg["reason"] or "")}</div></td>'
            f'<td>{tag(seg["rung"] or "full", "info")}</td>'
            f'<td>{esc(seg["companies"])}<div class="small muted">'
            f'{esc(seg["unassigned"])} free</div></td>'
            f'<td>{esc(seg["contacts"])}</td>'
            f'<td>{_mix(seg["personas"])}</td>'
            f'<td>{_mix(seg["modes"])}</td>'
            f'<td class="small muted">{esc(where)}</td>'
            f"<td>{state}</td></tr>")

    chosen = data.get("chosen")
    detail = ""
    if chosen:
        companies = "".join(
            f'<tr><td>{link("/companies/" + c["record_id"], c["company"] or c["domain"])}'
            f'<div class="small muted"><code>{esc(c["domain"])}</code></div></td>'
            f'<td>{tag("tier " + str(c["tier"]), "info")}</td>'
            f'<td>{esc(c["score"])}</td>'
            f'<td>{esc(c["country"])}</td>'
            f'<td>{esc(c["timezone"]) or unavailable("spans zones")}</td>'
            f'<td>{esc(c["contacts"])}</td>'
            f'<td class="small muted">{esc(", ".join(c["personas"]))}</td>'
            f'<td>{tag(c["in_campaign"], "block") if c["in_campaign"] else ""}</td>'
            f"</tr>"
            for c in chosen["company_rows"])

        why = chosen.get("why_together") or {}
        together = (f'<p class="note">{esc(why.get("why"))}</p>'
                    if why.get("why") else
                    f'<p class="note">{unavailable("this segment holds one "
                    "company, so there is no pair to explain")}</p>')

        form = '<p class="note">Your role can read this screen but not create '\
               'a campaign from it.</p>'
        if data["can_create"] and chosen["unassigned"] > 0:
            form = f"""
<form method="post" action="/campaigns/create" class="stack">
  <input type="hidden" name="csrf" value="{attr(csrf)}">
  <input type="hidden" name="segment_key" value="{attr(chosen["segment_key"])}">
  <label>Campaign name
    <input name="name" value="{attr(chosen["suggested_name"])}" maxlength="120"
           required></label>
  <label>Campaign id
    <input name="campaign_id" value="{attr(chosen["suggested_id"])}"
           pattern="[a-z0-9][a-z0-9_-]{{0,63}}"></label>
  <button class="btn primary" type="submit">Create draft campaign</button>
  <p class="note">Creates a <b>draft</b>. Nothing is sent, no provider
  campaign is created, and the copy still has to pass lint and QA and be
  approved by a human before anything is even push-eligible.</p>
</form>"""
        elif data["can_create"]:
            form = ('<p class="note">Every company in this segment is already '
                    'in a campaign. A record in two campaigns is one person '
                    'written to twice.</p>')

        detail = f"""
<div class="panel"><h3>{esc(chosen["segment_key"])}</h3>
  {stats([("companies", chosen["company_count"]),
          ("not yet in a campaign", chosen["unassigned"], "pass"),
          ("contacts selected", chosen["contacts"]),
          ("merge rung", chosen["rung"] or "full"),
          ("expected credits", chosen["expected_credits"]),
          ("at most", chosen["maximum_credits"], "warn")])}
  {together}
  <div class="grid3">
    {panel("Personas", _mix(chosen["personas"], chosen["contacts"]))}
    {panel("Angles", _mix(chosen["angles"], chosen["contacts"]))}
    {panel("Channel strategy", _mix(chosen["modes"], chosen["contacts"]))}
    {panel("Countries", _mix(chosen["countries"], chosen["company_count"]))}
    {panel("Timezones", _mix(chosen["timezones"], chosen["company_count"]))}
    {panel("Verticals", _mix(chosen["verticals"], chosen["company_count"]))}
  </div>
</div>
<div class="panel"><h3>Who would be in it</h3>
  {table(["company", "tier", "score", "country", "timezone", "contacts",
          "personas", "already in"], companies, table_id="builder-companies",
         filterable=True)}
  <p class="small muted">Showing {esc(chosen["shown"])} of
  {esc(chosen["company_count"])}.</p>
</div>
<div class="panel"><h3>Create</h3>{form}</div>
"""
        detail += sender_strategy_panel(data.get("sender_strategy"))

    return f"""
<h1>Campaign builder</h1>
<div class="crumb">A campaign is a segment plus a name. Everything else was
decided upstream.</div>
{table(["segment", "rung", "companies", "contacts", "personas",
        "channel strategy", "already in", ""], rows, table_id="segments",
       filterable=True)
 if rows else empty("No segments yet",
                    "Segments are assigned when a batch is qualified. "
                    "Qualify a batch first.")}
{detail}
<p class="note">Segments are built at full specificity and merged upward until
each one is worth writing for &mdash; the minimum is
{esc(data["min_segment_size"])} companies. A segment key is a promise that
everyone inside it can receive the same message, which is why the population
is not editable here.</p>
"""


def qa_block(qa_):
    """The QA report, rendered once and used wherever it is shown.

    A second renderer for the same report is a second chance to describe it
    differently, and the difference is the thing nobody notices.
    """
    if not qa_:
        return unavailable("no QA report was produced")
    issues = "".join(
        f'<tr><td>{tag(i.get("severity"), kind(i.get("severity")))}</td>'
        f'<td>{esc(i.get("dimension"))}</td>'
        f'<td class="small">{esc(i.get("record_id"))}</td>'
        f'<td class="small">{esc(i.get("message"))}</td></tr>'
        for i in (qa_.get("issues") or [])[:60])
    verdict = tag(qa_.get("verdict"), kind(str(qa_.get("verdict")).lower()))
    body = (table(["severity", "dimension", "record", "issue"], issues)
            if issues else '<p class="note ok">No QA issues.</p>')
    return f'<div class="crumb">Verdict {verdict}</div>{body}'


def _context_pack(pack):
    """Why these companies, why now, and what may actually be said.

    The order is the argument. Grouping first, because a campaign that is
    four segments wearing one name is a different problem from anything
    below it. Then attention *with* what cannot be worked, in one block,
    because those two numbers are one sentence. Then what is happening,
    quoted rather than characterised. Then the angles, split, because a
    supported pain and a plausible one are not the same kind of thing.
    Then what a message may say, which is the shortest block and the one
    that decides the most.
    """
    if not pack:
        return ""

    grouping = pack["why_these"]
    segments = ""
    for entry in grouping["segments"]:
        segments += (
            "<tr><td>" + (esc(entry["segment_key"]) if entry["segment_key"]
                          else unavailable("no ICP verdict yet"))
            + "</td><td>" + esc(entry["companies"]) + "</td>"
            + '<td class="small muted">' + esc(entry["reason"] or "")
            + "</td></tr>")

    attention = pack["attention"]
    top = ""
    for row_ in attention["top"]:
        top += (
            "<tr><td>"
            + link("/outreach/account/" + str(row_["record_id"]),
                   row_["company"] or row_["record_id"])
            + "</td><td>" + esc(f"{row_['score']:g}") + "</td><td>"
            + tag(row_["tier"], {"high": "pass", "medium": "warn"}.get(
                row_["tier"], ""))
            + "</td><td>"
            + (tag("eligible", "pass") if row_["eligible"]
               else tag(row_["blocked"] or "not eligible", "block"))
            + '</td><td class="small muted">' + esc(row_["why_now"])
            + "</td></tr>")

    signals = pack["signals"]

    def signal_rows(entries):
        out = ""
        for entry in entries:
            quotes = "".join(
                '<div class="small muted">' + esc(q["company"]) + ": "
                + esc(q["evidence"]) + "</div>"
                for q in entry["evidence"])
            out += ("<tr><td><b>" + esc(entry["label"]) + "</b></td><td>"
                    + esc(entry["accounts"]) + "</td><td>" + quotes
                    + "</td></tr>")
        return out

    angles = pack["angles"]

    def angle_rows(rows):
        out = ""
        for entry in rows:
            out += ("<tr><td>" + esc(entry["describes"]) + "</td><td>"
                    + esc(entry["companies"]) + "</td>"
                    + '<td class="small muted">'
                    + esc(f"{entry['share']:.0%} of the campaign")
                    + "</td></tr>")
        return out

    claims = pack["claims"]
    claim_rows = ""
    for entry in claims["claims"]:
        claim_rows += (
            "<tr><td>" + esc(entry["claim"].replace("_", " ")) + "</td><td>"
            + (tag("allowed", "pass") if entry["allowed"]
               else tag("off", ""))
            + '</td><td class="small muted">' + esc(entry["why"])
            + "</td></tr>")

    past = pack.get("history") or {"accounts": [], "shown": 0,
                                   "with_history": 0, "cold": 0,
                                   "planned_not_sent": 0, "note": ""}
    history_rows = ""
    for entry in past["accounts"]:
        heard = "; ".join(
            f"{channel}: " + ", ".join(people)
            for channel, people in sorted(entry["heard_from"].items()))
        history_rows += (
            "<tr><td>" + esc(entry["account"] or entry["record_id"])
            + "</td>"
            + '<td class="small">'
            + (esc(heard) if heard
               else unavailable("no sender recorded on the event"))
            + "</td>"
            + '<td class="small">' + esc(", ".join(entry["channels"]))
            + "</td>"
            + "<td>" + esc(entry["contacts_reached"]) + "</td>"
            + "<td>" + esc(entry["confirmed_total"])
            + ('<div class="small muted">'
               + esc(entry["planned_not_sent"]) + " planned, not sent</div>"
               if entry["planned_not_sent"] else "")
            + "</td></tr>")

    checks = ""
    for entry in pack["check"]:
        checks += ("<li><b>" + esc(entry["what"]) + "</b> &mdash; "
                   + '<span class="small muted">' + esc(entry["why"])
                   + "</span></li>")

    body = (
        stats([("companies", pack["companies"]),
               ("can be worked", attention["workable"], "pass"),
               ("cannot", attention["blocked_count"],
                "block" if attention["blocked_count"] else ""),
               ("signals at them", signals["external_live"]),
               ("evidenced angles",
                angles["companies_with_supported_angle"])])

        + ('<p class="note stop">'
           + esc(attention["blocked_count"])
           + " of these accounts cannot be written to. They are in the "
             "campaign and nothing will go to them; a high priority does "
             "not override that.</p>"
           if attention["blocked_count"] else "")

        + (('<p class="note">This campaign spans '
            + esc(len([s for s in grouping["segments"] if s["segment_key"]]))
            + " segments. One campaign means one story.</p>")
           if not grouping["one_segment"] else "")

        + section("Why these companies are one group",
                  table(["Segment", "Companies", "Why"], segments))

        + section("Worth attention first",
                  table(["Account", "Score", "Tier", "Outreach", "Why now"],
                        top)
                  + '<p class="small muted">Showing '
                  + esc(attention["shown"]) + " of "
                  + esc(attention["accounts"])
                  + ". Priority says worth attention; the outreach column "
                    "says whether anything may be sent, and it is not part "
                    "of the score.</p>",
                  open_=True)

        + section("What is happening at them",
                  (table(["Signal", "Accounts", "What was seen"],
                         signal_rows(signals["external"]))
                   if signals["external"] else
                   '<p class="note">Nothing observed at these companies. '
                   "This build has no external signal sources, so the only "
                   "way one gets here is somebody entering it.</p>")
                  + '<p class="note">' + esc(signals["note"]) + "</p>"
                  + ('<p class="small muted">'
                     + esc(signals["stale"])
                     + " stale signal(s) excluded: still true, no longer a "
                       "reason to act today.</p>"
                     if signals["stale"] else ""))

        + section("Where we already stand with them",
                  (table(["", "Accounts", "What happened"],
                         signal_rows(signals["engagement"]))
                   + '<p class="small muted">Our own history, derived from '
                     "the event log. It belongs in the priority and not in "
                     "the paragraph above: having written to somebody is "
                     "not evidence that they were worth writing to.</p>")
                  if signals["engagement"] else
                  '<p class="note">No prior contact with these accounts.</p>')


        + section("What these accounts have already heard",
                  (table(["Account", "Who they heard from", "Channels",
                          "People reached", "Touches"], history_rows)
                   + '<p class="small muted">Showing '
                   + esc(past["shown"]) + " of " + esc(past["with_history"])
                   + " account(s) with any confirmed history. "
                   + esc(past["cold"])
                   + " have never been written to.</p>"
                   if history_rows else
                   '<p class="note">None of these accounts has been '
                   "written to. Every step in this campaign would be a "
                   "first touch.</p>")
                  + ('<p class="note stop">'
                     + esc(past["planned_not_sent"])
                     + " step(s) across these accounts are prepared and "
                       "have not been sent. They are not history and "
                       "nothing may describe them as contact that "
                       "happened.</p>"
                     if past["planned_not_sent"] else "")
                  + '<p class="small muted">' + esc(past["note"]) + "</p>")

        + section("What the evidence supports",
                  (table(["Angle", "Companies", "Reach"],
                         angle_rows(angles["supported"]))
                   if angles["supported"] else
                   '<p class="note stop">No company here has an angle its own '
                   "evidence supports. Everything available is a "
                   "hypothesis.</p>")
                  + '<p class="small muted">' + esc(angles["why"])
                  + "</p>")

        + section("Plausible, and evidenced by nobody here",
                  (table(["Angle", "Companies", "Reach"],
                         angle_rows(angles["unsupported_anywhere"]))
                   + '<p class="note">Typical for the vertical and supported '
                     "by no company in this campaign. Copy that leads with "
                     "one of these is leading with a guess.</p>")
                  if angles["unsupported_anywhere"] else
                  '<p class="note">Every typical angle is supported by at '
                  "least one company here.</p>")

        + section("What a message may say",
                  table(["Claim", "Policy", "Why"], claim_rows)
                  + '<p class="note">' + esc(claims["not_a_claim_type"])
                  + "</p>")

        + (section("What a person still has to check",
                   "<ul>" + checks + "</ul>", open_=True)
           if checks else
           '<p class="note">Nothing here needs a second pair of eyes.</p>'))

    return panel("Why this campaign", body)


def preflight_panel(pre):
    """Who could actually receive something, and what is stopping the rest.

    The campaign page has always listed the seventeen checks about the
    campaign itself. This is the other half: the audience. A reviewer
    approving a campaign where eighteen of forty contacts are held for
    verification is approving something other than what they think, and
    "campaign cannot run" is not a sentence anybody can act on.

    The sentences are `eligibility.HUMAN`, which is where they already
    live. Blocked and held are shown apart on purpose - they are different
    jobs. A block needs a different contact; a hold needs one more thing to
    happen.
    """
    if not pre:
        return ""
    eligible = pre.get("eligible") or 0
    contacts = pre.get("contacts") or 0
    head = stats([
        ("accounts", pre.get("accounts") or 0),
        ("contacts", contacts),
        ("could receive their next step", eligible,
         "pass" if eligible else "block"),
        ("held", pre["verdicts"].get("held", 0),
         "warn" if pre["verdicts"].get("held") else ""),
        ("blocked", pre["verdicts"].get("blocked", 0),
         "block" if pre["verdicts"].get("blocked") else ""),
    ])

    rows = ""
    for reason in pre.get("reasons") or []:
        css = "block" if reason["kind"] == "blocked" else "warn"
        rows += (f'<tr><td class="n"><b>{esc(reason["count"])}</b></td>'
                 f'<td>{tag(reason["kind"], css)}</td>'
                 f'<td class="small">{esc(reason["human"])}</td></tr>')

    if rows:
        body = table(["", "", "Why"], rows)
    elif contacts:
        body = ('<p class="note">Every contact in this audience could '
                "receive its next step.</p>")
    else:
        body = ('<p class="note">This campaign has no contacts in its '
                "audience yet.</p>")

    return panel("Before you approve: the audience",
                 head + body
                 + '<p class="note">Counted by asking the eligibility gate '
                   "about each contact's next unsent step, now. Approving "
                   "does not change any of it - the same gate runs again at "
                   "the moment anything would be sent.</p>")


def campaign_detail(d, previews):
    campaign = d["campaign"]
    qa_ = d["qa"]
    modes = d["modes"]

    checks = "".join(
        f'<tr><td>{esc(c["name"])}</td>'
        f'<td>{tag("pass" if c["ok"] else "fail", "pass" if c["ok"] else "block")}'
        f'</td><td class="small">{esc(c["detail"])}</td></tr>'
        for c in d["validate"])

    contacts = "".join(
        f'<tr><td>{link("/contacts/" + c["record_id"] + "/" + c["contact_key"], c["name"] or c["contact_key"])}</td>'
        f'<td>{esc(c["company"])}</td><td>{mode_tag(c["mode"])}</td>'
        f'<td class="small">{esc(c["email_reason"] or "eligible")}</td></tr>'
        for c in d["contacts"])

    mapping = d["mapping"]
    mapping_rows = kv([
        row("Internal campaign", f"<code>{esc(campaign.get('campaign_id'))}</code>",
            raw=True),
        row("EmailBison campaign", mapping.get("bison_campaign_id")
            or unavailable("no EmailBison campaign has been created"),
            raw=not mapping.get("bison_campaign_id")),
        row("HeyReach campaign", mapping.get("heyreach_campaign_id")
            or unavailable("no HeyReach campaign has been created"),
            raw=not mapping.get("heyreach_campaign_id")),
        row("Mapping status", mapping.get("status")),
    ])

    return f"""
<h1>{esc(campaign.get('name'))}</h1>
<div class="crumb">{link("/campaigns", "Campaigns")} /
<code>{esc(campaign.get('campaign_id'))}</code></div>
{stats([("companies", d["records"]),
        ("contacts", len(d["contacts"])),
        ("multichannel", modes.get("multichannel", 0), "pass"),
        ("email only", modes.get("email_only", 0)),
        ("linkedin only", modes.get("linkedin_only", 0)),
        ("held", modes.get("none", 0), "block" if modes.get("none") else ""),
        ("QA", qa_.get("verdict"), kind(str(qa_.get("verdict")).lower())),
        ("would send", d["would_send"], "pass")])}
{_context_pack(d.get('context'))}
<div class="panel"><h3>One campaign, two providers</h3>{mapping_rows}
  <p class="note">One internal Resonate campaign maps to one EmailBison
  campaign and one HeyReach campaign, and the three together are a single
  multichannel campaign. Creating those provider campaigns is a mutation this
  build does not perform.</p>
</div>
{preflight_panel(d.get("preflight"))}
<div class="panel"><h3>Launch checklist</h3>
  {table(["check", "result", "detail"], checks)}
</div>
<div class="panel"><h3>Campaign QA</h3>{qa_block(qa_)}</div>
<div class="panel"><h3>Contacts</h3>
  {table(["contact", "company", "channel", "email reason"], contacts,
         table_id="campaign-contacts", filterable=True)}
</div>
{previews}
"""


def provider_previews(preview):
    if not preview:
        return ""
    bison = preview["payloads"]["emailbison"]
    heyreach = preview["payloads"]["heyreach"]
    banner = (f'<div class="banner stop"><b>{esc(preview["banner"])}</b> '
              "These are the exact request bodies the sender would post, built "
              "by the production payload builder. Nothing is submitted: "
              "<code>push.run(live=True)</code> raises "
              "<code>LiveSendNotEnabled</code>.</div>")

    skipped = "".join(
        f'<tr><td>{esc(s.get("id"))}</td><td>{esc(s.get("contact") or "")}</td>'
        f'<td>{esc(s.get("step") or "")}</td>'
        f'<td class="small">{esc(s.get("why"))}</td></tr>'
        for s in preview["skipped"][:40])

    return f"""
<div class="panel"><h3>Provider payload preview</h3>
{banner}
{stats([("EmailBison rows", bison["count"]),
        ("HeyReach lead pairs", heyreach["count"]),
        ("would send", preview["would_send"], "pass")])}
{section("EmailBison payload",
         f'<p>{esc(bison["method"])} <code>{esc(bison["endpoint"])}</code></p>'
         + json_block(bison["body"]))}
{section("HeyReach payload",
         f'<p>{esc(heyreach["method"])} <code>{esc(heyreach["endpoint"])}</code></p>'
         + json_block(heyreach["body"])
         + '<p class="note">Identity travels in <code>customUserFields</code>: '
           "<code>record_id</code> and <code>contact_key</code> are ours, and "
           "the canonical profile URL is what a reply is actually matched on. "
           "There is no name or company matching anywhere in that path.</p>")}
{section("Excluded from the executable payload, with reasons",
         table(["record", "contact", "step", "why"], skipped) if skipped
         else '<p class="note">Nothing was skipped.</p>')}
</div>
"""


# -------------------------------------------------------------- approvals

def approvals(data, csrf, can_approve):
    campaigns = ""
    for c in data["campaigns"]:
        state = ("stale" if c["stale"] else
                 (c["approval"] or {}).get("action") or "pending")
        # Both halves of the decision. `_approve_campaign` has always taken
        # `action`, `orchestrator.decide` has always accepted "reject", and
        # the audit log has always had a `campaign.rejected` entry to write -
        # and this page offered one button, so the only decision a reviewer
        # could record was yes. Approval that cannot be withheld is not
        # approval.
        #
        # What is offered is what would change something. `state` above
        # reads `approval.action`, whose words are "approve" and "reject" -
        # never "approved" - so the old `state != "approved"` guard could
        # not fire and an already-approved campaign still offered Approve.
        # A stale approval offers both again, because the plan it was given
        # for is not the plan on the screen.
        decided = "" if c["stale"] else state
        offered = [a for a in ("approve", "reject") if a != decided]
        button = ""
        if can_approve and offered:
            button = (
                f'<form method="post" action="/approvals/campaign" '
                f'class="inline-form">'
                f'<input type="hidden" name="csrf" value="{attr(csrf)}">'
                f'<input type="hidden" name="campaign_id" '
                f'value="{attr(c["campaign_id"])}">'
                f'<input type="hidden" name="fingerprint" '
                f'value="{attr(c["fingerprint"])}">'
                + " ".join(
                    f'<button class="btn primary" name="action" '
                    f'value="approve">Approve</button>' if a == "approve"
                    else f'<button class="btn" name="action" '
                         f'value="reject">Reject</button>'
                    for a in offered)
                + "</form>")
        elif not can_approve:
            button = '<span class="small muted">your role cannot approve</span>'
        plan = link("/approvals/plan?campaign=" + str(c["campaign_id"]),
                    "Plan review")
        audience = c.get("audience")
        if not audience:
            reach = unavailable("audience not computed")
        elif not audience["contacts"]:
            reach = '<span class="small muted">no contacts yet</span>'
        else:
            # Counted with the approval gate set aside, because on this
            # screen "nobody can receive it, it is not approved" is the
            # reader telling themselves what they already know.
            ready = audience.get("eligible_if_approved", 0)
            css = "pass" if ready else "block"
            label = (f'{ready} of {audience["contacts"]}'
                     " once approved")
            reach = tag(label, css)
            stopped = audience["contacts"] - ready
            if stopped:
                reach += ('<div class="small muted">'
                          + esc(f"{stopped} stopped by something else")
                          + "</div>")

        campaigns += (
            f'<tr><td>{link("/campaigns/" + c["campaign_id"], c["name"])}'
            f'<div class="small">{plan}</div></td>'
            f'<td>{tag(c["status"])}</td>'
            f'<td>{tag(state, "block" if c["stale"] else kind(state))}</td>'
            f"<td>{reach}</td>"
            f'<td class="small muted">'
            + (f'<code>{esc(c["fingerprint"])}</code>' if c["fingerprint"]
               else unavailable("not computed yet"))
            + f"</td><td>{button}</td></tr>")

    waiting = "".join(
        f'<tr><td>{esc(w.get("id"))}</td>'
        f'<td>{esc(w.get("name") or w.get("contact"))}</td>'
        f'<td>{esc(w.get("step"))}</td><td>{esc(w.get("channel"))}</td>'
        f'<td class="small">{esc(w.get("subject") or "")}</td></tr>'
        for w in (data["steps"].get("waiting") or [])[:60])

    blocked = "".join(
        f'<tr><td>{esc(b.get("id"))}</td>'
        f'<td>{esc(b.get("name") or b.get("contact"))}</td>'
        f'<td>{esc(b.get("step"))}</td>'
        f'<td class="small">{esc(b.get("why"))}</td></tr>'
        for b in (data["steps"].get("blocked") or [])[:60])

    return f"""
<h1>Approvals</h1>
<div class="crumb">Nothing is push-eligible until a human says so.</div>
<div class="panel"><h3>Campaigns</h3>
  {table(["campaign", "status", "approval", "who it reaches", "fingerprint", ""], campaigns)
   if campaigns else empty("No campaigns", "Nothing to approve.")}
  <p class="note">The fingerprint is what makes &ldquo;approve&rdquo; mean
  &ldquo;approve <b>this</b>&rdquo;. If the copy or the population moves, the
  approval goes stale and says so rather than looking current.</p>
</div>
<div class="panel"><h3>Steps waiting on a human</h3>
  {table(["record", "contact", "step", "channel", "subject"], waiting)
   if waiting else '<p class="note">Nothing is waiting.</p>'}
</div>
<div class="panel"><h3>Steps that cannot be approved, and why</h3>
  {table(["record", "contact", "step", "why"], blocked) if blocked
   else '<p class="note">Nothing is blocked.</p>'}
</div>
"""


# ---------------------------------------------------------------- replies

def _reply_handled(r, csrf, can_manage):
    """Whether a person has read this one, or a button to say so.

    Marking a reply handled does not un-pause anything, and the note beside
    the control says so. A reply pauses both channels for the whole company,
    and that pause is lifted by looking at the company - not by ticking the
    reply off a list. Letting a checkbox undo it would turn a safety property
    into a piece of admin.
    """
    handled = r.get("handled")
    if handled:
        return (tag("handled", "pass")
                + f'<div class="small muted">{esc(handled.get("by"))} '
                  f'&middot; {esc(handled.get("at"))}</div>'
                + (f'<div class="small muted">{esc(handled.get("note"))}</div>'
                   if handled.get("note") else ""))
    if not can_manage:
        return '<span class="small muted">not yet</span>'
    return (
        f'<form method="post" action="/replies/handle" class="inline-form">'
        f'<input type="hidden" name="csrf" value="{attr(csrf)}">'
        f'<input type="hidden" name="record_id" value="{attr(r["record_id"])}">'
        f'<input type="hidden" name="contact_key" '
        f'value="{attr(r["contact_key"])}">'
        f'<input type="hidden" name="at" value="{attr(r["at"])}">'
        f'<input name="note" placeholder="what you did" maxlength="300">'
        f'<button class="btn">Mark handled</button></form>')


# What a classification is called in front of a person. The codes are
# vocabulary; these are the words, kept here for the same reason
# `eligibility.HUMAN` keeps its own.
REPLY_LABEL = {
    "positive": "Positive",
    "neutral": "Neutral",
    "negative": "Negative",
    "unsubscribe": "Unsubscribed",
    "account_do_not_contact": "Company asked us to stop",
    "out_of_office": "Out of office",
    "not_now": "Not now",
    "not_relevant": "Wrong person or not a fit",
    "unknown": "Needs classifying",
}




def _reply_label(classification):
    """The classification in the words a person uses for it."""
    return tag(REPLY_LABEL.get(classification, classification),
               kind(classification))


def _follow_up_cell(follow_up):
    """The date this reply left behind, if it left one.

    An out-of-office and a "come back in November" both name a day. Saying
    so here is what connects a message somebody read last week to the row
    that will be due next month.
    """
    if not follow_up:
        return ""
    if follow_up.get("return_date"):
        return esc(follow_up["return_date"])
    status = follow_up.get("status") or ""
    return ('<span class="muted">' + esc("they gave no readable date")
            + "</span>") if status else ""


def _referral_cell(found):
    """Who a reply pointed at, beside the date it named.

    Both are things the message left behind that its classification does
    not carry, and an operator scanning the list wants them in the same
    column rather than one screen away.
    """
    if not found:
        return ""
    who = found.get("named") or found.get("email") or "somebody"
    mark = tag("needs a person", "warn") if found["needs_a_person"] else ""
    return f'<div class="small">&rarr; {esc(who)} {mark}</div>'


def carries_referral_chip(count, on=False, kind=None):
    """A filter beside the tabs, not one of them.

    The tabs ask what a reply was read as. This asks what it contains, and
    the two give different answers on the same message: a referral inside
    a polite refusal is classified `negative`, so its tab would never show
    it. Rendering it as a tab would say it is a tenth classification.
    """
    if not count and not on:
        return ""
    where = "/replies?carries=referral"
    if kind:
        where += "&kind=" + attr(kind)
    if on:
        where = "/replies" + (f"?kind={attr(kind)}" if kind else "")
        return (f'<a class="btn primary" href="{where}">'
                f"Carries a referral ({esc(count)}) &times;</a> ")
    return (f'<a class="btn" href="{where}">'
            f"Carries a referral ({esc(count)})</a> ")


def reply_tabs(categories, current):
    """One tab per canonical category, with its count.

    Built from the list rather than typed out. The five that were typed out
    left `out_of_office` and `not_now` with nowhere to appear, so a reply
    that named a date was only visible under All.
    """
    tabs = ('<a class="btn' + ("" if current else " primary")
            + '" href="/replies">All</a> ')
    for entry in categories:
        name = entry["kind"]
        on = " primary" if name == current else ""
        label = REPLY_LABEL.get(name, name)
        count = f' ({entry["count"]})' if entry["count"] else ""
        tabs += (f'<a class="btn{on}" href="/replies?kind={attr(name)}">'
                 f"{esc(label)}{esc(count)}</a> ")
    return tabs


def _reply_who(row):
    """The person, linked to the reply in its account context.

    That page is the only place a referral can be turned into a contact, so
    a reply row that does not link to it leaves `REVIEW_REFERRAL` telling an
    operator to do something the product gives them no control for.

    Only when the reply is matched. `/replies/context/` resolves the contact
    and 404s when it cannot, so an unmatched reply - whose whole problem is
    that nobody knows who it is - stays text rather than a dead link.
    """
    who = row["name"] or row["contact_key"] or ""
    if not row["matched"]:
        return esc(who)
    return link(f'/replies/context/{row["record_id"]}/{row["contact_key"]}',
                who)


def attention_replies(rows, csrf=None, can_manage=False):
    """The ones that are still somebody's job, above the list.

    Three reasons, and they are different jobs: nobody knows who this is,
    nobody has said what it means, somebody said yes and nobody has looked.
    A single "unread" flag would flatten all three.
    """
    if not rows:
        return panel("Needs attention",
                     '<p class="note">Every reply has been matched to a '
                     "person, classified, and read.</p>")
    body = ""
    for row in rows[:50]:
        body += (
            f'<tr><td class="small muted">{esc(row["at"])}</td>'
            f'<td>{link("/companies/" + row["record_id"], row["company"])}'
            f'<div class="small muted">{_reply_who(row)}</div></td>'
            f'<td>{esc(row["channel"])}</td>'
            f'<td class="small">{esc(row["needs"])}</td>'
            f'<td>{_reply_handled(row, csrf, can_manage)}</td></tr>')
    return panel("Needs attention",
                 table(["when", "who", "channel", "what it needs", ""], body))


def replies(rows, kind_filter=None, slack=None, csrf=None, can_manage=False,
            data=None):
    body = "".join(
        f'<tr><td class="small muted">{esc(r["at"])}</td>'
        f'<td>{link("/companies/" + r["record_id"], r["company"])}</td>'
        f'<td>{_reply_who(r)}</td>'
        f'<td>{esc(r["channel"])}</td>'
        f'<td>{_reply_label(r["classification"])}</td>'
        f'<td class="small">{_follow_up_cell(r.get("follow_up"))}'
        f'{_referral_cell(r.get("referral"))}</td>'
        f'<td>{tag("paused", "pause") if r["paused"] else ""}</td>'
        f'<td>{tag("matched", "pass") if r["matched"] else tag("unmatched", "warn")}'
        f'</td><td>{_reply_handled(r, csrf, can_manage)}</td></tr>'
        for r in rows)

    data = data or {}
    tabs = reply_tabs(data.get("categories") or [], kind_filter or None)
    chip = carries_referral_chip(data.get("referrals") or 0,
                                 on=data.get("carries") == "referral",
                                 kind=kind_filter or None)
    waiting = attention_replies(data.get("attention") or [], csrf, can_manage)

    slack_block = ""
    if slack:
        items = ""
        for preview in slack:
            payload = preview.get("payload")
            items += section(
                preview.get("kind", "slack message"),
                (json_block(payload) if payload
                 else f'<p>{unavailable(preview.get("error") or "not built")}</p>')
                + '<p class="note">Not posted. This is the payload that '
                  "<i>would</i> be posted, with <code>delivered: false</code> "
                  "travelling beside it.</p>")
        slack_block = f'<div class="panel"><h3>Slack, previewed</h3>{items}</div>'

    return f"""
<h1>Inbox</h1>
<div class="crumb">Any reply pauses both channels for the whole company.</div>
{waiting}
<div class="filters">{tabs}</div>
<div class="filters">{chip}</div>
{table(["at", "company", "contact", "channel", "classification",
        "follow-up", "pause", "match", "handled"], body) if body
 else empty("No replies here",
            "Nothing in this group yet. The tabs above cover every "
            "classification a reply can be given.")}
<p class="note">A reply pauses the <b>company</b>, not just the person, and it
pauses email and LinkedIn together. Nothing is deleted: every later step keeps
its place in the timeline with its reason.</p>
<p class="note stop">Marking a reply handled records that somebody read it. It
does <b>not</b> un-pause anything, and there is no control here that does: the
pause is lifted by looking at the company, on the company&rsquo;s own screen.
A checkbox that lifted it would turn a safety property into a piece of
admin.</p>
{slack_block}
"""


# -------------------------------------------------------------- reporting

def reporting(data, simple=False):
    """The operator's report, or the client-facing cut of it.

    `simple=True` is what a VIEWER sees. It drops provider names, credit
    counts, cost notes and the operational machinery, and keeps the funnel and
    the outcome. That is not a UI preference: a client-facing role is not
    supposed to learn which vendors are in the stack or what they cost, and the
    page it gets should not contain that in the markup either.
    """
    funnel = data["funnel"]
    conf = data["confirmation"]
    dm = data["decision_makers"]

    labels = data.get("funnel_labels") or {}
    funnel_rows = "".join(
        f"<tr><td>{esc(_funnel_label(labels, k))}</td>"
        f"<td>{_funnel_count(k, v)}</td></tr>"
        for k, v in funnel.items() if isinstance(v, (int, float)))

    conf_rows = kv([
        row("Required confirmations", conf["required_confirmations"]),
        row("Contacts with an address", conf["contacts_with_an_address"]),
        row("Double confirmed", conf["double_confirmed"]),
        row("Held awaiting confirmation", conf["held_awaiting_confirmation"]),
        row("Disagreements", conf["disagreements"]),
        row("Invalid", conf["invalid"]),
        row("Catch-all", conf["catch_all"]),
        row("Reoon escalations", conf["reoon_escalations"]),
        # A pair, like every other rate in this build. It was a bare
        # rounded float - the only denominator-free number on any surface -
        # and an empty cell when no contact had an address, because
        # `report` returns None there and `esc(None)` is "". The
        # client-facing branch below has always rendered the same two
        # numbers correctly.
        row("Pass rate", _rate((conf["double_confirmed"],
                                conf["contacts_with_an_address"])), raw=True),
    ])

    ops = "".join(f"<tr><td>{esc(k)}</td><td>{esc(v)}</td>"
                  f"<td>{esc((conf['credits'] or {}).get(k))}</td></tr>"
                  for k, v in (conf["operations"] or {}).items())

    dm_rows = kv([
        row("Planned contacts", dm["planned_contacts"]),
        row("Planned DM searches", dm["planned_dm_searches"]),
        row("Companies costing nothing", dm["companies_with_no_planned_spend"]),
        row("Contacts found", dm["found_contacts"]),
        row("Enrichment has run", dm["enrichment_has_run"]),
    ])

    absent = "".join(f"<tr><td>{esc(k)}</td><td class='small'>{esc(v)}</td></tr>"
                     for k, v in (data["unavailable"] or {}).items())

    if simple:
        # An allowlist, not a denylist. Two of the entries in
        # `report.unavailable()` explain themselves by naming a supplier -
        # "ContactOut reports usage per account" - and a client-facing page is
        # not where the vendor stack gets published. Listing what may appear
        # means a new entry is invisible here until somebody decides it is
        # safe, which is the right way round.
        safe = {k: v for k, v in (data["unavailable"] or {}).items()
                if k in CLIENT_SAFE_UNAVAILABLE}
        absent = "".join(
            f"<tr><td>{esc(k)}</td><td class='small'>{esc(v)}</td></tr>"
            for k, v in safe.items())
        with_address = conf["contacts_with_an_address"]
        return f"""
<h1>Reporting</h1>
<div class="crumb">Your campaign, in the numbers we can actually stand
behind.</div>
{stats([("companies", data["records"]),
        ("contacts with an address", with_address),
        ("confirmed by two providers", conf["double_confirmed"]),
        ("held for a human", conf["held_awaiting_confirmation"],
         "warn" if conf["held_awaiting_confirmation"] else "")])}
<div class="grid2">
  <div class="panel"><h3>Funnel</h3>
    {table(["stage", "count"], funnel_rows)}</div>
  <div class="panel"><h3>Email quality</h3>
    {kv([row("Contacts with an address", conf["contacts_with_an_address"]),
         row("Confirmed by two independent providers",
             conf["double_confirmed"]),
         row("Held until a second provider confirms",
             conf["held_awaiting_confirmation"]),
         row("Rejected as invalid", conf["invalid"]),
         row("Confirmed and usable",
             _rate((conf["double_confirmed"], with_address)), raw=True)])}
    <p class="note">No address is used on the strength of one provider. Where
    two disagreed, the contact is held rather than guessed at.</p>
  </div>
</div>
<div class="panel"><h3>What this cannot tell you</h3>
  {table(["metric", "why"], absent)}
  <p class="note">Nothing has been sent from this system, so there are no open
  rates, no bounce rates and no deliverability figures. Those numbers exist
  only in the sending platform once a campaign is live.</p>
</div>
"""

    return f"""
<h1>Reporting</h1>
<div class="crumb">Planned, actual and unavailable are kept apart.</div>
<div class="grid2">
  <div class="panel"><h3>Funnel</h3>
    {table(["stage", "count"], funnel_rows)}</div>
  <div class="panel"><h3>Email verification</h3>{conf_rows}</div>
</div>
<div class="grid2">
  <div class="panel"><h3>Decision makers</h3>{dm_rows}
    <p class="note">Planned and found are different numbers. On a qualified
    batch that has not been enriched, found is legitimately 0 &mdash; because
    nobody has been looked up, not because nobody is there.</p>
  </div>
  <div class="panel"><h3>Provider operations</h3>
    {table(["provider", "operations", "credits"], ops) if ops
     else '<p class="note">No verification operations recorded.</p>'}
    <p class="note">{esc(conf.get("cost_note"))}</p>
  </div>
</div>
<div class="panel"><h3>What this system cannot know</h3>
  {table(["metric", "why"], absent)}
</div>
"""


# -------------------------------------------------------------- simulator

def simulator(result, size):
    if not result:
        return f"""
<h1>5,000-domain simulation</h1>
<div class="crumb">Offline. No provider, model or network is touched.</div>
<div class="panel">
  <form method="get" action="/simulator">
    <div class="filters">
      <select name="size">
        <option value="500">500 companies</option>
        <option value="1000">1,000 companies</option>
        <option value="5000" selected>5,000 companies</option>
      </select>
      <button class="btn primary" type="submit">Run the simulation</button>
    </div>
  </form>
  <p class="note">Runs the whole company-first path &mdash; normalise, classify,
  score, segment, resolve timezone, route personas, plan the spend &mdash; over
  a deterministic synthetic upload. It spends nothing and calls nobody.</p>
</div>"""

    icp_ = result.get("status") or {}
    tiers = result.get("tier") or {}
    return f"""
<h1>5,000-domain simulation</h1>
<div class="crumb">{esc(size)} companies &middot;
{esc(result.get("seconds"))}s &middot; peak memory
{esc(result.get("peak_mb"))} MB &middot; offline</div>
{stats([("companies", size),
        ("qualified", icp_.get("qualified", 0), "pass"),
        ("review", icp_.get("review", 0), "warn"),
        ("rejected", icp_.get("rejected", 0), "block"),
        ("unknown", icp_.get("unknown", 0), "warn"),
        ("tier A", tiers.get("A", 0)),
        ("tier B", tiers.get("B", 0)),
        ("tier C", tiers.get("C", 0))])}
{stats([("needs review", result.get("needs_manual_review", 0), "warn"),
        ("schedulable", result.get("schedulable", 0), "pass"),
        ("no timezone", result.get("not_schedulable", 0), "warn"),
        ("segments", result.get("segments", 0)),
        ("DM searches", result.get("planned_dm_searches", 0)),
        ("max contacts", result.get("maximum_contacts", 0)),
        ("expected credits", result.get("expected_credits", 0)),
        ("maximum exposure", result.get("maximum_credits", 0), "warn")])}
<div class="panel"><h3>What this proves</h3>
  <p>Every phase is linear in batch size, checked per phase rather than in
  total &mdash; one quadratic phase inside an otherwise linear run is exactly
  what a single total hides. A rejected or review company consumes
  <b>zero</b> person credits, which is where most of the bill goes on a
  5,000-domain upload.</p>
  <p class="note">No provider, model or network was touched.</p>
</div>
"""


# -------------------------------------------------------------- timezones

def timezones(result):
    span = result.get("first_step_utc_span")
    rows = ""
    for row_ in result.get("rows") or []:
        first = next((s for s in row_["steps"] if s.get("utc_at")), None)
        rows += (f'<tr><td>{esc(row_["domain"])}</td>'
                 f'<td>{esc(row_["timezone"])}</td>'
                 f'<td>{esc((first or {}).get("local_at"))}</td>'
                 f'<td>{esc((first or {}).get("utc_at"))}</td>'
                 f'<td>{esc((first or {}).get("utc_offset_hours"))}</td>'
                 f'<td>{tag("DST", "info") if (first or {}).get("is_dst") else ""}'
                 f"</td></tr>")
    for row_ in result.get("held_rows") or []:
        rows += (f'<tr><td>{esc(row_["domain"])}</td>'
                 f'<td colspan="5">{unavailable(row_["why"])}</td></tr>')

    detail = ""
    for row_ in result.get("rows") or []:
        steps = "".join(
            f'<tr><td>{esc(s["step"])}</td><td>{esc(s["day"])}</td>'
            f'<td>{esc(s["channel"])}</td><td>{esc(s.get("local_at"))}</td>'
            f'<td>{esc(s.get("utc_at"))}</td>'
            f'<td class="small muted">{esc(s.get("why"))}</td></tr>'
            for s in row_["steps"])
        detail += section(
            f'{row_["timezone"]} - {row_["domain"]}',
            table(["step", "day", "channel", "local", "UTC", "note"], steps))

    return f"""
<h1>Local-time scheduling</h1>
<div class="crumb">The same campaign, four cities, DST-safe.</div>
{('<p>Day 1 spans <b>' + esc(span["hours"]) + ' hours</b> of UTC, because every '
  'send is placed in the prospect&rsquo;s own working morning.</p>')
 if span and span.get("hours") else
 '<p>Every prospect here shares one UTC offset, so day 1 fires at a single '
 'instant. The times are still computed through each IANA zone rather than '
 'assumed, which is what makes them move correctly across a daylight-saving '
 'change.</p>'}
<div class="panel">
  {table(["domain", "timezone", "day 1 local", "day 1 UTC", "offset", ""], rows)}
</div>
<div class="panel"><h3>Every step, per city</h3>{detail}</div>
<p class="note">Timezones are stored as IANA names, never as offsets: an offset
is right for half the year, and the wrong half is the one nobody checks. Where
a country spans zones and nothing narrows it, scheduling is <b>held</b> &mdash;
a guessed timezone sends confidently at the wrong hour, where a missing one
stops the send.</p>
"""


# ------------------------------------------------------------ diagnostics

def diagnostics(data):
    creds = "".join(
        f'<tr><td><code>{esc(name)}</code></td>'
        f'<td>{tag("configured", "pass") if present else tag("not set", "warn")}'
        f"</td></tr>" for name, present in (data["credentials"] or {}).items())

    stale = "".join(
        f'<tr><td>{link("/campaigns/" + c["campaign_id"], c["name"])}</td>'
        f'<td>{tag("stale", "block")}</td></tr>' for c in data["stale_approvals"])

    unmatched = "".join(
        f'<tr><td>{esc(r["company"])}</td><td>{esc(r["channel"])}</td>'
        f'<td class="small muted">{esc(r["at"])}</td></tr>'
        for r in data["unmatched_replies"])

    held = "".join(f'<tr><td>{link("/companies/" + h["id"], h["company"])}</td>'
                   f"</tr>" for h in data["held_records"])

    unmapped = "".join(
        f'<tr><td>{link("/campaigns/" + c["campaign_id"], c["name"])}</td>'
        f'<td class="small">{esc(c["status"])}</td></tr>'
        for c in data["unmapped_campaigns"])

    jobs_ = data["jobs"]
    return f"""
<h1>Diagnostics</h1>
<div class="crumb">What an operator needs to look at, and nothing sensitive.</div>
{stats([("jobs", jobs_["jobs"]), ("active", jobs_["active"]),
        ("failed jobs", jobs_["failed"], "block" if jobs_["failed"] else ""),
        ("with holds", jobs_["with_holds"], "warn"),
        ("stale approvals", len(data["stale_approvals"]),
         "block" if data["stale_approvals"] else ""),
        ("unmatched replies", len(data["unmatched_replies"]),
         "warn" if data["unmatched_replies"] else ""),
        ("held records", len(data["held_records"]), "warn"),
        ("unmapped campaigns", len(data["unmapped_campaigns"]))])}
<div class="grid2">
  <div class="panel"><h3>Provider credentials</h3>
    {table(["variable", "state"], creds)}
    <p class="note">Presence only. No value from the environment is ever sent
    to a browser, and a test asserts that by planting a known value into every
    credential variable and grepping every rendered byte for it.</p>
  </div>
  <div class="panel"><h3>Sending</h3>
    {kv([row("Live sending", tag("DISABLED", "pass"), raw=True),
         row("EmailBison", tag("preview only", "pass"), raw=True),
         row("HeyReach", tag("preview only", "pass"), raw=True),
         row("Slack posting",
             tag("LIVE", "block") if data.get("slack_posting")
             else tag("preview only", "pass"), raw=True),
         row("Paid enrichment", tag("no web job spends", "pass"),
             raw=True)])}
    <p class="note"><code>push.run(live=True)</code> raises
    <code>LiveSendNotEnabled</code>. There is no flag on this surface that
    changes that.</p>
  </div>
</div>
<div class="grid2">
  <div class="panel"><h3>Stale approvals</h3>
    {table(["campaign", "state"], stale) if stale
     else '<p class="note">No approval has gone stale.</p>'}</div>
  <div class="panel"><h3>Unmatched replies</h3>
    {table(["company", "channel", "at"], unmatched) if unmatched
     else '<p class="note">Every reply matched a contact.</p>'}</div>
</div>
<div class="grid2">
  <div class="panel"><h3>Held records</h3>
    {table(["company"], held) if held
     else '<p class="note">Nothing is held.</p>'}</div>
  <div class="panel"><h3>Campaigns without a provider mapping</h3>
    {table(["campaign", "status"], unmapped) if unmapped
     else '<p class="note">Every campaign is mapped.</p>'}</div>
</div>
"""


# ------------------------------------------------------------- csv upload

def _verification_panel(result):
    """How much of this file could be written to, and what the rest costs.

    The number an operator wants before committing anything is not "how
    many rows" - it is "how many of these can I actually email, and what
    does finding out about the others cost". Both are here, and the second
    is a plan rather than a spend.
    """
    found = (result or {}).get("verification")
    if not found:
        return ""

    rows = kv([
        row("Already cleared to write to", found["sendable"]),
        row("Here already, not cleared", found["known"]),
        row("New to this workspace", found["new"]),
        row("No address at all", found["no_address"]),
    ])
    if found["needs_verification"]:
        cost = (f'<p class="note">{esc(found["needs_verification"])} '
                f"address(es) would need verifying: about "
                f'{esc(found["planned_calls"])} provider calls, at most '
                f'{esc(found["max_calls"])}. {esc(found["note"])}</p>')
    else:
        cost = ('<p class="note ok">Nothing here needs verifying.</p>'
                if found["with_address"] else
                '<p class="note">No addresses in this file.</p>')
    return ('<div class="panel"><h3>What could be written to</h3>'
            + rows + cost + "</div>")


def _hygiene_panel(result):
    """What this list looks like against everything we have already done.

    The point of the panel is the middle of the table, not the ends. A row
    that is suppressed is easy; a row held because somebody else at the same
    company is mid-conversation is the one an operator would otherwise post
    a cold email to.
    """
    summary = (result or {}).get("hygiene")
    if not summary:
        return ""

    counts = "".join(
        f'<tr><td><b>{esc(row["label"])}</b></td>'
        f'<td>{esc(row["count"])}</td>'
        f'<td>{tag(row["action_label"], row["kind"])}</td></tr>'
        for row in summary["rows"])

    # Every *person* who is not cold-eligible, with the evidence. Read from
    # `screened` rather than from the company rows: five people at one
    # account are five answers, and walking the company rows showed the
    # first one and silently dropped the rest.
    #
    # Capped for the page, and the cap is stated rather than silently
    # applied.
    held, shown = [], 0
    for row in (result.get("screened") or []):
        verdict = row.get("verdict") or {}
        if not verdict or verdict["action"] == "eligible":
            continue
        shown += 1
        if shown > 100:
            continue
        held.append(
            "<tr><td>" + esc(row.get("who") or row["domain"])
            + '<div class="small muted">' + esc(row["company"]) + "</div>"
            + "</td><td>" + tag(verdict["action_label"], verdict["kind"])
            + "</td><td>" + esc(verdict["label"])
            + '<div class="small muted">' + esc(verdict["why"]) + "</div>"
            + "</td></tr>")

    more = (f'<p class="small muted">{shown - 100} more not listed.</p>'
            if shown > 100 else "")
    return (
        '<div class="panel"><h3>Checked against everything we have already '
        "done</h3>"
        + f'<p class="small muted">{esc(summary["eligible"])} of '
        + f'{esc(summary["total"])} people are cold-eligible. The rest are '
        + "classified below, not deleted.</p>"
        + table(["What we already know", "Rows", "What happens"], counts)
        + (table(["Row", "", "Why"], "".join(held)) + more if held else "")
        + '<p class="note">Previously engaged is not the same as permanently '
        "excluded. A removal request suppresses; a conversation in progress "
        "holds; &ldquo;not right now&rdquo; routes to follow-up. Every row "
        "keeps its place here with the reason that put it there.</p></div>")


def upload_form(csrf, workspace, error=None, result=None):
    """The new-batch form.

    There is no client picker on this page, and that is the point: a batch
    belongs to the workspace the operator is currently in. Offering a choice
    would be offering a way to file somebody else's data in the wrong tenant -
    and the repository would refuse it anyway, so the control would be a lie.
    """
    warn = f'<div class="banner stop">{esc(error)}</div>' if error else ""
    summary = ""
    if result:
        excluded = result["excluded"]
        rows = "".join(
            f'<tr><td>{esc(r["row"])}</td><td>{esc(r["domain"])}</td>'
            f'<td class="small">{esc(r["reason"])}</td></tr>'
            for r in excluded[:100])
        # The table is capped and the sentence under it promises every
        # excluded row is listed. On a big file those two disagree
        # silently, so the cap is stated with the number it hides.
        excluded_more = (
            f'<p class="small muted">Showing the first 100 of '
            f'{esc(len(excluded))} excluded rows.</p>'
            if len(excluded) > 100 else "")

        # People who joined a company another row introduced. Reported
        # apart from the exclusions on purpose: "4 rows were dropped" and
        # "4 more people joined this account" are opposite outcomes, and
        # this used to report the second as the first.
        attached = result.get("attached") or []
        joined = ""
        if attached:
            by_domain = {}
            for entry in attached:
                by_domain[entry["domain"]] = by_domain.get(
                    entry["domain"], 0) + 1
            listed = "".join(
                f"<tr><td>{esc(domain)}</td><td>{esc(count + 1)}</td></tr>"
                for domain, count in sorted(by_domain.items(),
                                            key=lambda kv: -kv[1])[:40])
            joined = (
                '<div class="panel"><h3>More than one person at a '
                "company</h3>"
                + table(["Company", "People in this file"], listed)
                + '<p class="note">A domain is a company and a row is a '
                "person at it. These rows are not duplicates; they are "
                "colleagues, and they import as contacts on one "
                "account.</p></div>")
        # How the file's own column names were read. Shown before the
        # counts, because every number below depends on it: an operator who
        # cannot see that "Work Email" became the address we would write to
        # cannot tell a right mapping from a plausible one.
        notes = result.get("mapping_notes") or []
        unmapped = result.get("unmapped_columns") or []
        ambiguous = (result.get("mapping") or {}).get("ambiguous") or []
        mapped = ""
        if notes or unmapped or ambiguous:
            read = "".join(
                f'<tr><td class="small">{esc(line)}</td></tr>'
                for line in notes)
            kept = ""
            if unmapped:
                kept = ('<p class="note">Kept with the rows but not used for '
                        "any decision: "
                        + esc(", ".join(str(c) for c in unmapped[:20]))
                        + ("…" if len(unmapped) > 20 else "") + ".</p>")
            unsettled = ""
            if ambiguous:
                # Actionable, because the answer is not in the product.
                # Picking one of two identical headers is a coin flip over
                # whose values are real, and a screen that offered the
                # choice would be asking a question only the file can
                # answer. Saying which columns and what to do about them
                # is the whole fix.
                names = esc(", ".join(ambiguous))
                copies = esc(", ".join(result["mapping"]["duplicates"]))
                unsettled = (
                    '<p class="note stop">This file has more than one column '
                    f"called {copies}, so nothing was read for "
                    f"{names}. Which copy is the real one is a question "
                    "only the file can answer - delete or rename the "
                    "duplicate and upload it again. Every other column was "
                    "read normally, and nothing has been committed.</p>")
            mapped = ('<div class="panel"><h3>How the columns were read</h3>'
                      + (table(["Column"], read) if read else "")
                      + kept + unsettled
                      + '<p class="note">Columns are matched by name, never '
                        "guessed. Anything not recognised is kept as source "
                        "detail and can never make somebody contactable."
                        "</p></div>")

        # Which sheet was read. Only a workbook has one, and saying it is
        # the only way somebody notices that their leads were on the
        # second tab.
        sheet_note = ""
        if result.get("sheet"):
            sheet_note = ('<p class="note">Read from the sheet <b>'
                          + esc(result["sheet"]) + "</b>, the first in the "
                          "workbook. Nothing on any other sheet was "
                          "read.</p>")

        # The second step. `POST /upload/commit` has always existed and
        # nothing ever rendered a form for it, so the preview was a dead
        # end and no lead could be imported through the product at all -
        # while the dashboard offered importing leads as its first action.
        #
        # The button says what it will write, because "Commit" alone does
        # not tell an operator whether the number they are agreeing to is
        # the one at the top of the page or the one left after exclusions.
        # It is `result["rows"]`, which is exactly what `upload.commit`
        # iterates.
        if result["rows"]:
            commit = (
                '<form method="post" action="/upload/commit">'
                f'<input type="hidden" name="csrf" value="{attr(csrf)}">'
                '<button class="btn primary" type="submit">Import '
                f'{esc(len(result["rows"]))} companies and '
                f'{esc(result.get("contacts", 0))} people</button>'
                '</form><p class="note">Importing writes them to the queue. '
                "Everything excluded above stays excluded, and nothing is "
                "contacted by being imported.</p>")
        elif not result["uploaded"]:
            commit = '<p class="note">This file had no rows to read.</p>'
        else:
            commit = ('<p class="note">Nothing here can be imported: every '
                      "row was excluded for the reason beside it.</p>")

        summary = f"""
{mapped}
<div class="panel"><h3>Parsed, nothing committed</h3>
{sheet_note}
{stats([("rows uploaded", result["uploaded"]),
        ("companies", result["unique"], "pass"),
        ("people", result.get("contacts", 0),
         "pass" if result.get("contacts") else ""),
        ("invalid", result["invalid"], "block" if result["invalid"] else ""),
        ("repeated rows", result["duplicates"],
         "warn" if result["duplicates"] else ""),
        ("same person twice", result.get("duplicate_contacts", 0),
         "warn" if result.get("duplicate_contacts") else ""),
        ("suppressed", result["suppressed"], "warn" if result["suppressed"] else ""),
        ("already exist", result["existing"], "warn" if result["existing"] else "")])}
{joined}
{table(["row", "domain", "why excluded"], rows) + excluded_more if rows
 else '<p class="note">Every row is usable.</p>'}
<p class="note">Nothing disappears. Every excluded row is listed with its
reason, and none of this has been written to the queue yet.</p>
{commit}
</div>{_verification_panel(result)}{_hygiene_panel(result)}"""

    return f"""
<p class="eyebrow">Operator core · Intake</p>
<h1>New batch</h1>
<div class="crumb">Upload a CSV of domains into
<b>{esc(workspace)}</b>. Parsing happens before anything is written.</div>
<p class="note">Before leads become campaign-eligible, Resonate checks them
against existing outreach, replies, engagement and suppression history.
Previously engaged leads are not deleted &mdash; they are classified and
routed according to workspace policy.</p>
{warn}
<div class="panel">
  <form method="post" action="/upload" enctype="multipart/form-data">
    <input type="hidden" name="csrf" value="{attr(csrf)}">
    <div class="upload-fields">
      <label for="batch-name">Batch name
        <input id="batch-name" name="batch" placeholder="uk-agencies" required>
      </label>
      <label for="batch-notes">Notes (optional)
        <input id="batch-notes" name="notes" placeholder="Describe this audience">
      </label>
    </div>
    <div class="upload-dropzone" data-dropzone>
      <strong>Drop your audience file here</strong>
      <p>CSV or Excel · parse first, review exclusions, then commit.</p>
      <label for="batch-file"><span id="upload-filename" class="file-name">Choose a CSV or Excel file</span></label>
      <input id="batch-file" type="file" name="csv" data-upload aria-describedby="upload-help"
             accept=".csv,text/csv,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" required>
    </div>
    <details><summary>File format and column mapping</summary>
    <p id="upload-help" class="small muted">CSV or Excel. A workbook's first sheet is
    read, and the preview says which sheet that was &mdash; leads on a
    second tab will not be the ones imported. Column names do not need
    changing: <code>Company
    Website</code>, <code>Organization</code>, <code>Work Email</code>,
    <code>LinkedIn URL</code> and <code>Job Title</code> are all understood.
    Something identifying the company is the one requirement. Email and
    LinkedIn identify a person, so several rows sharing a company import as
    several contacts on one account. Columns we do not recognise are kept
    with the rows and never used to decide anything &mdash; the preview
    shows exactly how each one was read before anything is saved.</p></details>
    <div class="form-actions">
      <button class="btn primary" type="submit">Parse and preview</button>
      <span class="small muted">No provider spend. No records written at this step.</span>
    </div>
  </form>
  <p class="note">The suppression list is checked here, at ingest, before
  anything is spent. Sending a live customer a cold sequence is the single most
  expensive mistake in this motion.</p>
</div>
{summary}
"""


# ------------------------------------------------------------- workspaces

def workspace_list(spaces, current, memberships_by_space, can_manage, csrf,
                   super_admin=False, error=None):
    body = ""
    for w in spaces:
        people = memberships_by_space.get(w["slug"]) or []
        members = ", ".join(f'{m["email"]} ({m["role"]})' for m in people[:6])
        here = " &middot; current" if w["slug"] == current else ""
        switch = (f'<form method="post" action="/select-workspace" '
                  f'class="inline-form">'
                  f'<input type="hidden" name="csrf" value="{attr(csrf)}">'
                  f'<input type="hidden" name="workspace" '
                  f'value="{attr(w["slug"])}">'
                  f'<button class="btn" type="submit">Open</button></form>')
        body += (f'<tr><td><b>{esc(w["name"])}</b>{here}'
                 f'<div class="small muted"><code>{esc(w["slug"])}</code></div>'
                 f"</td>"
                 f'<td class="small">{esc(len(people))}</td>'
                 f'<td class="small muted">{esc(members)}</td>'
                 f"<td>{switch}</td></tr>")
    note = ("<p class=\"note\">A workspace is a hard tenancy boundary, not a "
            "filter. Every batch, company, contact, campaign, approval, reply "
            "and job belongs to exactly one, and a repository built for one "
            "workspace has no call that can return another's rows.</p>")
    if super_admin:
        note += ('<p class="note">You are a <b>super admin</b>, so you can '
                 "enter every workspace. Each crossing is recorded in the "
                 "audit log as <code>super_admin</code> rather than as an "
                 "ordinary membership.</p>")
    warn = f'<div class="banner stop">{esc(error)}</div>' if error else ""
    add = ""
    if super_admin:
        add = panel(
            "Add a client",
            f'<form method="post" action="/workspaces/create">'
            f'<input type="hidden" name="csrf" value="{attr(csrf)}">'
            '<div class="filters">'
            '<input name="slug" placeholder="acme-security" required '
            'pattern="[a-z0-9][a-z0-9-]{1,39}" maxlength="40">'
            '<input name="name" placeholder="Acme Security" required '
            'maxlength="80">'
            '<input name="domain" placeholder="acme-security.com" '
            'maxlength="80">'
            '<input name="booking_link" placeholder="https://... (optional)" '
            'maxlength="120" class="input-wide">'
            '<button class="btn primary" type="submit">Create</button>'
            "</div></form>"
            '<p class="note">Creates the workspace and a starter '
            "configuration together. It deliberately carries no ICP and no "
            "personas: workspace setup will list those as missing, and a "
            "placeholder ICP is one that gets used to choose real people."
            "</p>")

    return f"""
<h1>Workspaces</h1>
<div class="crumb">{esc(len(spaces))} workspace(s) you may enter</div>
{warn}
{table(["workspace", "members", "who", ""], body) if body
 else empty("No workspaces", "You are not a member of any workspace.")}
{add}
{note}
"""


def workspace_personas(data, csrf, error=None):
    """Who counts as a decision maker here, and how many of each.

    The one screen in settings that changes who gets *selected*, so it says
    what still holds after it rather than leaving that to be assumed.
    """
    rows = ""
    for row in data["personas"]:
        angles = "".join(
            f'<div class="small"><b>{esc(name)}</b> &mdash; {esc(phrase)}</div>'
            for name, phrase in sorted(row["angles"].items()))
        remove = ""
        if data["can_manage"]:
            remove = (
                f'<form method="post" action="/settings/personas/remove">'
                f'<input type="hidden" name="csrf" value="{attr(csrf)}">'
                f'<input type="hidden" name="name" value="{attr(row["name"])}">'
                f'<button class="btn">Remove</button></form>')
        rows += (
            f"<tr><td><b>{esc(row['name'])}</b></td>"
            f"<td>{esc(', '.join(row['titles']))}</td>"
            f"<td>{esc(row['cap_per_domain'])}</td>"
            + "<td>" + (angles or unavailable(
                "no angle, so a message here falls back to general wording"))
            + f"</td><td>{remove}</td></tr>")

    table_html = (table(["Persona", "Titles", "Per company", "Angles", ""],
                        rows) if rows else
                  empty("No personas",
                        "nobody is a decision maker here yet, so a batch "
                        "would select nobody"))

    form = ""
    if data["can_manage"]:
        limits = data["limits"]
        form = f"""
<div class="panel"><h3>Add or replace a persona</h3>
  <form method="post" action="/settings/personas/save">
    <input type="hidden" name="csrf" value="{attr(csrf)}">
    <label>Name<input name="name" placeholder="champion" required>
      <span class="small muted">Lower case, no spaces. Replacing an
      existing name replaces that persona.</span></label>
    <label>Titles<input name="titles" required
      placeholder="Operations Manager, Head of Operations">
      <span class="small muted">Comma separated, up to
      {limits['titles']}. A contact is this persona when their title
      matches one.</span></label>
    <label>How many at one company<input type="number" name="cap"
      value="1" min="1" max="{limits['cap']}">
      <span class="small muted">The cap on how many people at a single
      company this persona may put into a sequence.</span></label>
    <label>Angles<textarea name="angles" rows="4"
      placeholder="ops: utilisation, capacity planning
finance: margin per project, month end"></textarea>
      <span class="small muted">One per line, <code>name: what it
      says</code>. Optional - without one, messages fall back to general
      wording rather than failing.</span></label>
    <button class="btn primary" type="submit">Save persona</button>
  </form>
</div>"""

    problem = f'<p class="note stop">{esc(error)}</p>' if error else ""
    return f"""
<h1>Personas</h1>
<div class="crumb">{link("/settings", "Settings")} / Personas</div>
<p class="note">In force from <b>{esc(data['source'])}</b>. Editing here
replaces the whole set for this workspace rather than merging with the
client file, so what this page shows is what a batch will use.</p>
{problem}
{table_html}
{form}
<p class="note">Selecting somebody is not contacting them. A company
reaches this step only with an ICP verdict, the cap bounds how many people
at each one, and verification, email security, engagement history,
suppression, pacing and approval all sit after it and are unchanged by
anything on this page.</p>
"""


def _policy_field(field):
    """One editable setting, with its range and the reason it has one."""
    name = attr("policy:" + field["key"])
    if field["kind"] == "list":
        # Rendered the way it is typed and the way the client file writes
        # it. A multi-select would need the full set of possible values,
        # and nobody has the full set of places a client sells into.
        value = ", ".join(str(v) for v in (field["value"] or []))
    elif field["kind"] == "bool":
        value = (field["choices"][0] if field["value"] is not False
                 else field["choices"][1])
    else:
        value = "" if field["value"] is None else str(field["value"])
    if field["kind"] in ("choice", "bool"):
        options = "".join(
            f'<option value="{attr(c)}"'
            f'{" selected" if c == value else ""}>{esc(c)}</option>'
            for c in field["choices"])
        control = f'<select name="{name}">{options}</select>'
    elif field["kind"] == "int":
        blank = " placeholder=\"no cap\"" if field["blank_is_none"] else ""
        control = (f'<input type="number" name="{name}" '
                   f'value="{attr(value)}" min="{attr(field["min"])}" '
                   f'max="{attr(field["max"])}"{blank}>')
    elif field["kind"] == "list":
        control = (f'<input name="{name}" value="{attr(value)}" '
                   f'placeholder="United Kingdom, Ireland, Germany" '
                   f'maxlength="900">')
    else:
        control = (f'<input name="{name}" value="{attr(value)}" '
                   f'maxlength="{attr(field.get("max_length") or 80)}">')
    mark = tag("overridden", "warn") if field["overridden"] else ""
    return (f'<label>{esc(field["label"])} {mark}{control}'
            f'<span class="small muted">{esc(field["why"])}</span></label>')


# Policy areas, in the order somebody configuring a workspace works through
# them. Thirty-six settings in one flat column is a wall nobody reads; the
# same thirty-six under six headings is a form.
#
# The prefix decides the group, so a new key lands in the right place without
# a second list to maintain. Anything unmatched falls into "Workspace", which
# is where it would have been anyway.
POLICY_GROUPS = (
    ("market.", "Who this client sells to",
     "The ICP. Everything here narrows: a company outside it is flagged or "
     "dropped, and nothing on this screen can make somebody contactable "
     "who was not already."),
    ("outreach.claim_", "Account-aware messaging",
     "Whether a message may refer to outreach that has already happened. "
     "Every reference is checked against recorded events; these decide "
     "whether it is offered at all."),
    ("reply.on_", "Reply policy",
     "What a reply from one decision maker does to the others at the same "
     "company."),
    ("fatigue.contact.", "Contact pacing",
     "How often one person may hear from us, counting every sender and both "
     "channels."),
    ("fatigue.account.", "Account pacing",
     "How often one company may hear from us, across every decision maker."),
    ("slack.", "Slack",
     "Where this workspace's notifications go."),
    ("reporting.", "Reporting",
     "What a client report defaults to."),
)


def _grouped_policy_fields(editable):
    """Every policy field, under the heading it belongs to."""
    remaining = list(editable)
    out = ""
    for prefix, title, why in POLICY_GROUPS:
        mine = [f for f in remaining if f["key"].startswith(prefix)]
        if not mine:
            continue
        remaining = [f for f in remaining if f not in mine]
        out += (f"<h4>{esc(title)}</h4>"
                f'<p class="small muted">{esc(why)}</p>'
                + "".join(_policy_field(f) for f in mine))
    if remaining:
        out += ("<h4>Workspace</h4>"
                + "".join(_policy_field(f) for f in remaining))
    return out


def workspace_settings(data, can_see_providers, csrf=None):
    """This workspace's own rules.

    `can_see_providers` gates the provider mapping specifically, rather than
    the page. A reviewer may legitimately want to know what the ICP rules and
    the verification policy are; which EmailBison campaign this workspace
    points at is a different question, and `provider_settings.view` is the
    permission that answers it. The note at the foot of this page makes that
    claim, so the page has to be true to it.
    """
    config = data["config"]

    def block(title, rows_):
        return f"<h4>{esc(title)}</h4>" + kv(rows_)

    verification = config.get("verification") or {}
    mx_policy = ((config.get("email_security") or {}).get("mx_filter") or {})
    market = config.get("market") or {}
    personas_ = config.get("personas") or {}
    slack_ = config.get("slack") or {}

    personas_rows = "".join(
        f'<tr><td>{esc(name)}</td>'
        f'<td class="small">{esc(", ".join((spec or {}).get("titles") or [])[:200])}</td>'
        f'<td>{esc((spec or {}).get("cap_per_domain"))}</td></tr>'
        for name, spec in personas_.items())

    fields = _grouped_policy_fields(data["editable"])
    policy_form = (
        '<div class="panel"><h3>Policy</h3><p class="note">Your role can read '
        'these but not change them.</p></div>') if not data["can_manage"] else f"""
<div class="panel"><h3>Policy</h3>
  <form method="post" action="/settings/policy" class="stack">
    <input type="hidden" name="csrf" value="{attr(csrf)}">
    {fields}
    <button class="btn primary" type="submit">Save policy</button>
  </form>
  <p class="note">These are stored as <b>overrides beside the workspace</b>,
  not written back into the client config file. That file is hand-written,
  has comments in it, and is read by a parser whose own docstring says a
  misparsed geo is a live customer getting cold sequenced &mdash; a web form
  is not allowed to rewrite it.</p>
  <p class="note stop">Three things are deliberately not on this form.
  <b>Double verification cannot be switched off</b>: the confirmation count
  has a floor of two, because that is a property of this build rather than a
  setting. <b>MX filtering cannot be disabled</b>: the unknown-gateway policy
  moves either way, but turning the filter off entirely is how a Proofpoint
  tenant gets cold emailed. And <b><code>allow_review_enrichment</code></b> is
  absent, because it lets a company that did not qualify on evidence be
  enriched anyway, and {link("/icp", "the ICP review screen")} says in words
  that widening it is a change to the client config rather than a click on a
  page.</p>
</div>"""

    mapping_form = ""
    if data["can_manage_providers"]:
        rows_ = ""
        for c in data["mappable"]:
            rows_ += f"""
<tr><td>{link("/campaigns/" + c["campaign_id"], c["name"] or c["campaign_id"])}
<div class="small muted">Name it in the provider:</div>
<div class="small"><code>{esc(c["suggested_names"]["names"]["email"])}</code></div>
<div class="small"><code>{esc(c["suggested_names"]["names"]["linkedin"])}</code></div>
</td><td>
  <form method="post" action="/settings/mapping" class="filters">
    <input type="hidden" name="csrf" value="{attr(csrf)}">
    <input type="hidden" name="campaign_id" value="{attr(c["campaign_id"])}">
    <input name="bison" value="{attr(c["bison"] or "")}"
           placeholder="EmailBison campaign id" maxlength="80">
    <input name="heyreach" value="{attr(c["heyreach"] or "")}"
           placeholder="HeyReach campaign id" maxlength="80">
    <button class="btn" type="submit">Save</button>
  </form>
</td></tr>"""
        mapping_form = f"""
<div class="panel"><h3>Provider mapping</h3>
  {table(["campaign", "EmailBison / HeyReach"], rows_) if rows_
   else '<p class="note">No campaign to map yet.</p>'}
  <p class="note stop">This records a <b>pointer</b>. It creates nothing at
  EmailBison or HeyReach and changes nothing there: creating a provider
  campaign is a mutation this build does not perform, and a form that claimed
  to have made one would be the most dangerous sentence on this screen.
  Changing a mapping after approval is logged on the campaign, because the
  campaign somebody approved would now be submitted somewhere else.</p>
  <p class="note">The names above are what to call those campaigns inside
  the provider, so somebody opening EmailBison can tell which of them
  Resonate is filling. They are <b>labels</b>: nothing here matches a
  campaign by name, and renaming one in the provider breaks nothing,
  because the mapping is the provider's own campaign id.</p>
</div>"""

    return f"""
<h1>Workspace settings</h1>
<div class="crumb">{esc(data["workspace"]["name"])} &middot;
<code>{esc(data["workspace"]["slug"])}</code></div>
<div class="grid2">
 <div class="panel">
  {block("Market", [
      row("Must be", market.get("must")),
      row("Minimum employees", market.get("size_min_employees")),
      row("Geographies", ", ".join(market.get("geos") or [])),
      row("Excluded geographies", ", ".join(market.get("exclude_geos") or [])),
  ])}
  {block("Email verification", [
      row("Required confirmations",
          verification.get("required_confirmations", 2)),
      row("Primary", verification.get("primary", "contactout")),
      row("Secondary", verification.get("secondary", "deliverable")),
      row("Escalation", verification.get("catch_all", "reoon")),
      row("On disagreement", verification.get("disagreement", "hold")),
  ])}
  {block("Email security (MX)", [
      row("Filtering", tag("on" if mx_policy.get("enabled", True) else "off",
                           "pass" if mx_policy.get("enabled", True) else "warn"),
          raw=True),
      row("Blocked providers", ", ".join(mx_policy.get("blocked_providers")
                                         or ["barracuda", "mimecast",
                                             "proofpoint"])),
      row("Unknown provider policy",
          mx_policy.get("unknown_provider_policy", "allow")),
  ])}
 </div>
 <div class="panel">
  {block("Provider mapping", [
      row("EmailBison campaign", data["mapping"].get("bison")
          or unavailable("no EmailBison campaign has been created"),
          raw=not data["mapping"].get("bison")),
      row("HeyReach campaign", data["mapping"].get("heyreach")
          or unavailable("no HeyReach campaign has been created"),
          raw=not data["mapping"].get("heyreach")),
  ]) if can_see_providers else
   "<h4>Provider mapping</h4>" + kv([
      row("EmailBison campaign",
          unavailable("your role does not carry provider_settings.view"),
          raw=True),
      row("HeyReach campaign",
          unavailable("your role does not carry provider_settings.view"),
          raw=True)])}
  {block("Approval and Slack routing", [
      row("Approvals channel", slack_.get("approvals_channel")
          or unavailable("not configured"),
          raw=not slack_.get("approvals_channel")),
      row("Named approvers", ", ".join(slack_.get("allowed_approvers") or [])
          or unavailable("nobody is named in the Slack block"),
          raw=not (slack_.get("allowed_approvers") or [])),
      row("Slack posting", tag("preview only", "pass"), raw=True),
  ])}
  <h4>Personas</h4>
  {table(["persona", "titles", "cap per domain"], personas_rows) if personas_rows
   else '<p class="note">No personas configured for this workspace.</p>'}
 </div>
</div>
<p class="note">Everything on this page comes from this workspace's own client
config, which is what makes ICP rules, personas, geographies, timezone policy,
the verification waterfall, MX policy, research policy, campaign defaults and
provider mapping independent per workspace. Provider <b>secrets</b> are not
here and never reach a browser: only whether one is configured, and only for a
role that carries <code>provider_settings.view</code>.</p>
{policy_form}
{mapping_form}
"""


# What each outcome of the invite form says. A fixed map, so the query
# parameter that selects one can only ever choose among these sentences -
# it names a result, it does not carry one.
USER_RESULTS = {
    "invited": ("ok", "Invitation pending. They get access the first time "
                      "they sign in with that Google address."),
    "already_pending": ("info", "That invitation was already pending."),
    "pending_role_changed": ("ok", "Pending invitation updated to the new "
                                   "role."),
    "added": ("ok", "Added to this workspace."),
    "role_changed": ("ok", "Role updated."),
    "already_member": ("info", "Already a member with that role."),
    "revoked": ("ok", "Invitation revoked."),
    "nothing_to_revoke": ("info", "There was no pending invitation to "
                                  "revoke."),
    "error": ("stop", "That could not be done. Check the address and the "
                      "role."),
}


def workspace_users(data, csrf, can_manage, result=None):
    banner = ""
    kind, words = USER_RESULTS.get(str(result or ""), (None, None))
    if words:
        banner = f'<div class="banner {kind}">{esc(words)}</div>'

    body = ""
    for m in data["memberships"]:
        actions = ""
        if can_manage:
            options = "".join(
                f'<option value="{attr(r)}"'
                f'{" selected" if r == m["role"] else ""}>{esc(r)}</option>'
                for r in data["roles"])
            actions = (
                f'<form method="post" action="/users/role" class="inline-form">'
                f'<input type="hidden" name="csrf" value="{attr(csrf)}">'
                f'<input type="hidden" name="email" value="{attr(m["email"])}">'
                f'<select name="role">{options}</select> '
                f'<button class="btn" type="submit">Save</button></form>')
        else:
            actions = '<span class="small muted">read only</span>'
        body += (f'<tr><td>{esc(m["email"])}</td>'
                 f'<td>{tag(m["role"], "info")}</td>'
                 f"<td>{actions}</td></tr>")

    pending = ""
    for entry in data.get("invitations") or []:
        actions = '<span class="small muted">waiting</span>'
        if can_manage:
            actions = (
                f'<form method="post" action="/users/revoke" '
                f'class="inline-form">'
                f'<input type="hidden" name="csrf" value="{attr(csrf)}">'
                f'<input type="hidden" name="email" '
                f'value="{attr(entry["email"])}">'
                f'<button class="btn" type="submit">Revoke</button></form>')
        pending += (f'<tr><td>{esc(entry["email"])}</td>'
                    f'<td>{tag(entry["role"], "info")}</td>'
                    f'<td class="small muted">{esc(entry.get("invited_by"))}'
                    f'</td>'
                    f'<td class="small muted">'
                    f'{esc((entry.get("created_at") or "")[:10])}</td>'
                    f"<td>{actions}</td></tr>")

    invited_panel = ""
    if pending:
        invited_panel = f"""
<div class="panel"><h3>Pending invitations</h3>
  {table(["address", "role", "invited by", "offered", ""], pending)}
  <p class="note">These grant nothing yet. An invitation becomes membership
  the first time the identity provider proves that exact address &mdash; not a
  similar one, not another address at the same domain &mdash; and only for
  this workspace.</p>
</div>"""

    matrix = ""
    for role in data["roles"]:
        granted = data["permissions"].get(role) or []
        matrix += (f'<tr><td>{tag(role, "info")}</td>'
                   f'<td class="small muted">{esc(", ".join(granted))}</td></tr>')

    invite = ""
    if can_manage:
        roles_ = "".join(f'<option value="{attr(r)}">{esc(r)}</option>'
                         for r in data["roles"])
        invite = f"""
<form method="post" action="/users/add" class="filters">
  <input type="hidden" name="csrf" value="{attr(csrf)}">
  <input name="email" type="email" placeholder="someone@example.com" required
         class="input-wide">
  <select name="role">{roles_}</select>
  <button class="btn primary" type="submit">Add to this workspace</button>
</form>
<p class="note">An address, not a list. Offering every account that exists
would let an admin in one workspace read off the staff of every other one, and
to add somebody you already know who they are. Somebody who has never signed
in is invited rather than refused: the address is pre-authorised, and it grants
nothing until Google proves it.</p>"""

    return f"""
<h1>Users</h1>
<div class="crumb">{esc(data["workspace"]["name"])}</div>
{banner}
<div class="panel"><h3>Members</h3>
  {table(["user", "role", ""], body) if body
   else empty("No members", "Nobody is assigned to this workspace.")}
  {invite}
</div>
{invited_panel}
<div class="panel"><h3>What each role carries</h3>
  {table(["role", "permissions"], matrix)}
  <p class="note">Permissions are checked at the service boundary, never in a
  page. A handler that forgets to check still cannot read another workspace's
  rows, because the repository it was handed has no call that returns them.</p>
</div>
"""


# ------------------------------------------------------------- audit log

def _audit_value(value):
    """One side of a change, as words.

    A dict reaching `esc()` renders as its Python repr - the log showed
    `{'slack.workspace_channel': None}` where a person needed to read what
    the setting used to be. An audit log is read during an incident, which
    is the worst moment to be decoding a repr.
    """
    if value is None:
        return "not set"
    if isinstance(value, dict):
        return ("; ".join(f"{key}: {_audit_value(inner)}"
                          for key, inner in sorted(value.items()))
                or "nothing")
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value) or "nothing"
    return str(value)


def _audit_change(before, after):
    """"channel: not set -> #client-productive-replies".

    When both sides are dicts, the key is said once and the two values are
    put either side of the arrow, rather than printing the whole mapping
    twice and leaving a reader to diff it by eye.
    """
    if isinstance(before, dict) and isinstance(after, dict):
        keys = sorted(set(before) | set(after))
        if keys:
            return "; ".join(
                f"{key}: {_audit_value(before.get(key))}"
                f" \u2192 {_audit_value(after.get(key))}" for key in keys)
    return f"{_audit_value(before)} \u2192 {_audit_value(after)}"


def audit_log(entries, workspace=None, may_widen=False, total=None):
    """The durable log for one workspace, or for all of them.

    `may_widen` only controls whether the link is offered. Whether it works is
    decided on the server, which is why the handler re-checks rather than
    trusting that this link was the only way to arrive.
    """
    widen = ""
    if may_widen:
        widen = ('<p class="small">'
                 + (link("/audit", "This workspace only") if workspace is None
                    else link("/audit?scope=all", "Every workspace"))
                 + "</p>")
    body = ""
    for e in entries:
        change = ""
        if e.get("before") is not None or e.get("after") is not None:
            change = esc(_audit_change(e.get("before"), e.get("after")))
        body += (f'<tr><td class="small muted">{esc(e.get("at"))}</td>'
                 f'<td>{esc(e.get("actor"))}</td>'
                 f'<td class="small">{esc(e.get("workspace"))}</td>'
                 f'<td>{esc(e.get("action"))}</td>'
                 f'<td class="small">{esc(e.get("resource_type") or "")} '
                 f'{esc(e.get("resource_id") or "")}</td>'
                 f"<td class='small muted'>{change}</td></tr>")
    # "300 entries" was the truncation reporting itself as the answer:
    # `audit_entries` caps at 300 and this printed the length of what came
    # back, so a workspace with four thousand writes read exactly the same
    # as one with three hundred. A durable log whose stated job is
    # answering "what happened" must not present its own page size as the
    # total.
    shown = f"{esc(len(entries))} entries"
    if total is not None and total > len(entries):
        shown = f"showing the newest {esc(len(entries))} of {esc(total)}"

    return f"""
<h1>Audit log</h1>
<div class="crumb">{esc(workspace or "every workspace")} &middot;
{shown}, newest first</div>
{widen}
{table(["at", "who", "workspace", "action", "resource", "change"], body,
       table_id="audit", filterable=True) if body
 else empty("Nothing recorded yet", "Actions appear here as they happen.")}
<p class="note">Durable and human-readable. No entry carries a credential, a
raw provider payload or message content &mdash; identifiers, counts and status
words only.</p>
"""


# ------------------------------------------------------------ super admin

def _flag_state(state):
    """On, off, or decided per process. Three states, not two.

    `None` is not "off": demo mode is set by a command-line argument at
    startup, and rendering that as off would be a page claiming to know
    something it was not told.
    """
    if state is None:
        return tag("per process", "info")
    return tag("on", "warn") if state else tag("off", "pass")


def admin(data):
    spaces = "".join(
        f'<tr><td><b>{esc(w["name"])}</b>'
        f'<div class="small muted"><code>{esc(w["slug"])}</code></div></td>'
        f'<td>{esc(w["members"])}</td><td>{esc(w["records"])}</td>'
        f'<td>{esc(w["campaigns"])}</td><td>{esc(w["contacts"])}</td></tr>'
        for w in data["workspaces"])

    people = "".join(
        f'<tr><td>{esc(u["email"])}</td><td>{esc(u["name"])}</td>'
        f'<td>{tag("super admin", "pass") if u.get("super_admin") else ""}</td>'
        f'<td class="small muted">{esc(", ".join(u["workspaces"]))}</td></tr>'
        for u in data["users"])

    creds = "".join(
        f'<tr><td><code>{esc(name)}</code></td>'
        f'<td>{tag("configured", "pass") if present else tag("not set", "warn")}'
        f"</td></tr>" for name, present in (data["credentials"] or {}).items())

    roles = "".join(
        f'<tr><td>{tag(r["role"], "pass" if r["role"] == "super_admin" else "info")}'
        f'</td><td>{esc(r["count"])}</td>'
        f'<td class="small muted">{esc(", ".join(r["permissions"]))}</td></tr>'
        for r in data["roles"]["roles"])

    providers = "".join(
        f'<tr><td>{esc(p["provider"])}</td><td>{esc(p["calls"])}</td>'
        f'<td>{esc(p["credits"])}</td>'
        f'<td class="small muted">'
        f'{esc(", ".join(f"{k} {v}" for k, v in sorted(p["outcomes"].items())))}'
        f'</td></tr>'
        for p in data["providers"]["providers"])

    costs = data["costs"]
    cost_rows = "".join(
        f'<tr><td><code>{esc(c["call"])}</code></td><td>{esc(c["calls"])}</td>'
        f'<td>{esc(c["credits"])}</td></tr>' for c in costs["by_call"])

    failed = "".join(
        f'<tr><td><code>{esc(j["id"])}</code></td><td>{esc(j["type"])}</td>'
        f'<td>{esc(j["client"])}</td><td>{esc(j["batch"])}</td>'
        f'<td class="small block-text">{esc(j["error"])}</td></tr>'
        for j in data["failed_jobs"])

    unmatched = data["unmatched"]
    suppression = data["suppression"]
    events_ = data["security_events"]
    refusals = "".join(
        f'<tr><td class="small muted">{esc(e.get("at"))}</td>'
        f'<td>{esc(e.get("actor"))}</td>'
        f'<td>{esc(e.get("workspace") or "&mdash;")}</td>'
        f'<td>{tag((e.get("metadata") or {}).get("kind"), "block")}</td>'
        f'<td class="small"><code>{esc(e.get("resource_id"))}</code></td></tr>'
        for e in events_["recent"][:40])

    flags = "".join(
        f'<tr><td><code>{esc(f["flag"])}</code></td>'
        f'<td>{_flag_state(f["state"])}</td>'
        f'<td class="small muted">{esc(f["why"])}</td>'
        f'<td class="small muted"><code>{esc(f["controlled_by"])}</code></td>'
        f'</tr>' for f in data["flags"])

    status = data["status"]
    files = "".join(
        f'<tr><td>{esc(name)}</td><td class="small muted">'
        f'<code>{esc(info["path"])}</code></td>'
        f'<td>{tag("present", "pass") if info["exists"] else tag("absent", "warn")}'
        f'</td><td>{esc(info["bytes"])}</td></tr>'
        for name, info in status["files"].items())

    jobs_ = data["jobs"]
    return f"""
<h1>Admin</h1>
<div class="crumb">Every workspace. This view exists for a super admin and is
recorded as such.</div>
{stats([("workspaces", len(data["workspaces"])),
        ("users", len(data["users"])),
        ("records", data["totals"]["records"]),
        ("contacts", data["totals"]["contacts"]),
        ("campaigns", data["totals"]["campaigns"]),
        ("jobs", jobs_["jobs"]),
        ("failed jobs", jobs_["failed"], "block" if jobs_["failed"] else ""),
        ("audit entries", data["audit_entries"])])}
<div class="panel"><h3>Workspaces</h3>
  {table(["workspace", "members", "companies", "campaigns", "contacts"], spaces)}
</div>
<div class="panel"><h3>Users</h3>
  {table(["email", "name", "", "workspaces"], people)}
</div>
<div class="grid2">
  <div class="panel"><h3>Provider credentials</h3>
    {table(["variable", "state"], creds)}
    <p class="note">Presence only. No value from the environment reaches a
    browser, and a test plants a known value into every credential variable
    then greps every rendered byte for it.</p>
  </div>
  <div class="panel"><h3>System status</h3>
    {kv([row("Live sending", tag("DISABLED", "pass"), raw=True),
         row("EmailBison", tag("preview only", "pass"), raw=True),
         row("HeyReach", tag("preview only", "pass"), raw=True),
         row("Slack posting", tag("preview only", "pass"), raw=True),
         row("Paid enrichment", tag("not run", "pass"), raw=True),
         row("Demo mode", tag("on" if data["demo"] else "off",
                              "warn" if data["demo"] else "pass"), raw=True)])}
  </div>
</div>
<div class="panel"><h3>Roles and what each one carries</h3>
  {table(["role", "permissions", "which"], roles)}
  <p class="note">Read from <code>src/workspaces.py</code>, not written out
  here. A table typed into an admin page is a second statement of the
  permission model, and the second one is the one that goes stale.</p>
</div>
<div class="grid2">
  <div class="panel"><h3>Provider usage</h3>
    {table(["provider", "calls", "credits", "outcomes"], providers)
     if providers else
     '<p class="note ok">No provider call has been made. This build does not '
     'make one from any surface.</p>'}
    <p class="note">{esc(data["providers"]["note"])}</p>
  </div>
  <div class="panel"><h3>Credits, by call</h3>
    {stats([("credits", costs["total_credits"]),
            ("reported cost",
             costs["reported_cost"] if costs["reported_cost"] is not None
             else "not reported")])}
    {table(["call", "calls", "credits"], cost_rows) if cost_rows
     else '<p class="note ok">Nothing has been charged.</p>'}
    <p class="note">{esc(costs["note"])}</p>
  </div>
</div>
<div class="panel"><h3>Failed jobs</h3>
  {table(["job", "type", "workspace", "batch", "why it stopped"], failed)
   if failed else '<p class="note ok">No job has failed.</p>'}
  <p class="note">A job stops when the failures stop looking like bad records
  and start looking like a bad run &mdash; twenty failures and more than a
  quarter of what it touched. Continuing through 5,000 of those is how a
  mistake becomes an invoice.</p>
</div>
<div class="grid2">
  <div class="panel"><h3>Unmatched provider events</h3>
    {kv([row("Events naming nothing we hold", unmatched["unknown_events"]),
         row("Rejected webhooks", unmatched["rejected_webhooks"]),
         row("Duplicates ignored", unmatched["duplicates"])])}
    <p class="note">An event that cannot be matched is left unmatched rather
    than attached to the closest guess: a guess here pauses the wrong company.
    They belong to no workspace, which is why they are only here.</p>
    <p class="small muted">{esc(unmatched["note"])}</p>
  </div>
  <div class="panel"><h3>Global suppression</h3>
    {stats([("domains", suppression["count"])])}
    <p class="small muted"><code>{esc(suppression["path"])}</code></p>
    <p class="note">{esc(suppression["note"])}</p>
    {f'<p class="small muted">{esc(", ".join(suppression["sample"]))}</p>'
     if suppression["sample"] else ''}
  </div>
</div>
<div class="panel"><h3>Security events &mdash; {esc(events_["total"])}
  refusal(s)</h3>
  {stats([(kind_, count, "block")
          for kind_, count in list(events_["by_kind"].items())[:6]])
   if events_["by_kind"] else ''}
  {table(["when", "who", "workspace", "kind", "request"], refusals)
   if refusals else '<p class="note ok">Nothing has been refused.</p>'}
  <p class="note">Who, when, which workspace, which path and which class of
  refusal. Not the query string, not the form, not the id that was reached
  for &mdash; an attacker who can choose what goes in your log has been handed
  a second tool.</p>
</div>
<div class="panel"><h3>Feature flags</h3>
  {table(["flag", "state", "what it means", "controlled by"], flags)}
  <p class="note">Read from the code that decides each one. A flag page that
  keeps its own copy of the answer is a flag page that can be wrong about it.
  </p>
</div>
<div class="panel"><h3>Where the state lives</h3>
  {table(["file", "path", "state", "bytes"], files)}
  {kv([row("Records", status["counts"]["records"]),
       row("Campaigns", status["counts"]["campaigns"]),
       row("Jobs", status["counts"]["jobs"]),
       row("Workspaces", status["counts"]["workspaces"]),
       row("Users", status["counts"]["users"]),
       row("Python", status["python"])])}
  <p class="note">{esc(status["note"])}</p>
</div>
<p class="small muted">{link("/audit", "Full audit log")} &middot;
{link("/diagnostics", "Operator diagnostics")}</p>
"""


# ------------------------------------------------------ advanced reporting

def _funnel_label(labels, key):
    return (labels or {}).get(key) or str(key).replace("_", " ")


def _funnel_count(key, value):
    """A zero for something nothing observes is named, never printed.

    Nothing in this build marks a meeting, so a `meeting` row reading 0 is
    an absence of instrumentation rather than an absence of meetings - and a
    dashboard that shows zero for the first teaches people to read it as the
    second. The client report already says this in its appendix.
    """
    if key == "meeting" and not value:
        return unavailable("needs a calendar or CRM integration, or "
                           "someone marking it in Slack")
    return esc(value)


def _meetings(value):
    """The same refusal, for the two global screens.

    They printed a bare `0` under a source table three lines down saying
    "absent until somebody marks one" - the exact thing `_funnel_count`
    exists to prevent, on the two screens a super admin opens first.
    """
    if not value:
        return unavailable("not tracked")
    return esc(value)


def _rate(pair):
    """A percentage with both halves of it visible.

    Never a bare number. "38%" of what, out of how many, is the question every
    reporting screen gets asked second, and a page that cannot answer it has
    made a claim it cannot support.
    """
    num, den = pair
    if not den:
        return f'<span class="absent">&mdash; <span class="small">0 of 0</span></span>'
    pct = round(100.0 * num / den)
    return (f'<b>{esc(pct)}%</b> '
            f'<span class="small muted">{esc(num)} of {esc(den)}</span>')


def analytics(data, csrf=None, can_export=False, base="/reporting"):
    dim = data["dimension"]
    picker = "".join(
        f'<option value="{attr(field)}"'
        f'{" selected" if field == dim else ""}>{esc(label)}</option>'
        for field, label in data["dimensions"])

    filter_fields = ""
    for field, label in data["dimensions"]:
        current = (data["filters"] or {}).get(field) or ""
        options = "".join(
            f'<option value="{attr(v)}"{" selected" if v == current else ""}>'
            f"{esc(v)}</option>"
            for v in (data["choices"].get(field) or []))
        filter_fields += (
            f'<label class="small">{esc(label)}'
            f'<select name="{attr(field)}"><option value="">any</option>'
            f"{options}</select></label>")

    body = ""
    for entry in data["breakdown"]:
        body += (f'<tr><td><b>{esc(entry["value"])}</b></td>'
                 f'<td>{esc(entry["companies"])}</td>'
                 f'<td>{esc(entry["contacts"])}</td>'
                 f'<td>{_rate(entry["rates"]["sendable"])}</td>'
                 f'<td>{_rate(entry["rates"]["email_eligible"])}</td>'
                 f'<td>{_rate(entry["rates"]["linkedin_eligible"])}</td>'
                 f'<td>{_rate(entry["rates"]["double_verified"])}</td>'
                 f'<td>{esc(entry["held"])}</td>'
                 f'<td>{esc(entry["replies"])}</td></tr>')

    totals = data["totals"]
    export_link = ""
    if can_export:
        query = "&".join(
            f"{k}={attr(v)}" for k, v in
            list(data["filters"].items()) + [("dimension", dim)])
        export_link = ('<p class="small">'
                       + link(f"/export/analytics.csv?{query}",
                              "Download this breakdown as CSV")
                       + "</p>")

    return f"""
<h2>Breakdown</h2>
{stats([("companies", totals["companies"]),
        ("contacts", totals["contacts"]),
        ("sendable", totals["sendable"]),
        ("email eligible", totals["email_eligible"]),
        ("linkedin eligible", totals["linkedin_eligible"]),
        ("double verified", totals["double_verified"]),
        ("held", totals["held"], "warn" if totals["held"] else ""),
        ("replies", totals["replies"])])}
<form method="get" action="{attr(base)}" class="filters">
  <label class="small">Group by
    <select name="dimension" data-autosubmit>{picker}</select></label>
  {filter_fields}
  <button class="btn" type="submit">Apply</button>
  {link(base, "Clear")}
</form>
{table([data["dimension_label"], "companies", "contacts", "sendable",
        "email eligible", "linkedin eligible", "double verified", "held",
        "replies"], body, table_id="analytics", filterable=True) if body
 else empty("Nothing to break down", "No records match these filters.")}
{export_link}
<p class="note">Every percentage above is printed with its own numerator and
denominator, because the denominator is where a reporting screen usually
lies. Reply rate is counted against <b>sendable contacts</b>, not against
everyone loaded, and nothing has been sent from this build &mdash; so a reply
here came from a rehearsal, not from a mailbox.</p>
"""


def sender_report(data):
    """Outcomes grouped by who sent them, with the denominator on every row."""
    rows = ""
    for row in data["rows"]:
        rows += (
            f'<tr><td><code>{esc(row["key"])}</code></td>'
            f'<td>{esc(row["contacts"])}</td>'
            f'<td>{esc(row["contactable"])} {_rate(row["contactable_rate"])}</td>'
            f'<td>{esc(row["confirmed_email"])}</td>'
            f'<td>{esc(row["confirmed_linkedin"])}</td>'
            f'<td>{esc(row["reached"])}</td>'
            f'<td>{esc(row["replies"])} {_rate(row["reply_rate"])}</td>'
            f'<td>{esc(row["positive"])} {_rate(row["positive_rate"])}</td>'
            f"</tr>")
    tabs = ""
    for key, label in data["dimensions"]:
        on = " primary" if key == data["dimension"] else ""
        tabs += (f'<a class="btn{on}" href="/reporting/senders?dimension='
                 f'{attr(key)}">{esc(label)}</a> ')
    return f"""
<h1>Reporting by sender</h1>
<div class="crumb">Grouped by {esc(dict(data["dimensions"]).get(data["dimension"]))}.</div>
<div class="filters">{tabs}</div>
{table(["group", "contacts assigned", "contactable", "confirmed email",
        "confirmed linkedin", "reached", "replies", "positive"], rows,
       table_id="sender-report", filterable=True)
 if rows else empty("Nothing assigned",
                    "No contact in this workspace has a sender yet.")}
<p class="note">Reply rate is counted against contacts actually
<b>reached</b> - confirmed touches - rather than against everyone assigned,
because a sender who was given twenty prospects and reached none of them has
not had a reply rate of zero. Both numbers are printed.</p>
<p class="note stop">{esc(data["note"])}</p>
"""


def comparison(data):
    left, right = data["left"], data["right"]
    values = "".join(f'<option value="{attr(v)}">{esc(v)}</option>'
                     for v in data["values"])

    def side(entry):
        warn = ""
        if entry["small_sample"]:
            warn = (f'<div class="banner warn">Small sample: '
                    f'{esc(entry["contacts"])} contacts, below the '
                    f'{esc(data["small_sample_threshold"])} this build will '
                    f"call a difference on.</div>")
        return f"""
<div class="panel">
  <h3>{esc(entry["value"])}</h3>
  {warn}
  {kv([row("Companies", entry["companies"]),
       row("Contacts", entry["contacts"]),
       row("Sendable", _rate(entry["rates"]["sendable"]), raw=True),
       row("Email eligible", _rate(entry["rates"]["email_eligible"]), raw=True),
       row("LinkedIn eligible", _rate(entry["rates"]["linkedin_eligible"]),
           raw=True),
       row("Double verified", _rate(entry["rates"]["double_verified"]),
           raw=True),
       row("Held", entry["held"]),
       row("Replies", _rate(entry["rates"]["reply"]), raw=True),
       row("Positive", _rate(entry["rates"]["positive"]), raw=True)])}
</div>"""

    dims = "".join(
        f'<option value="{attr(field)}"'
        f'{" selected" if field == data["dimension"] else ""}>{esc(label)}'
        f"</option>" for field, label in data["dimensions"])

    return f"""
<h1>Compare</h1>
<div class="crumb">Two slices of the same workspace, side by side</div>
<form method="get" action="/compare" class="filters">
  <label class="small">Compare by
    <select name="dimension" data-autosubmit>{dims}</select></label>
  <label class="small">Left
    <select name="left">{values.replace(f'value="{attr(left["value"])}"',
                                        f'value="{attr(left["value"])}" selected')}
    </select></label>
  <label class="small">Right
    <select name="right">{values.replace(f'value="{attr(right["value"])}"',
                                         f'value="{attr(right["value"])}" selected')}
    </select></label>
  <button class="btn" type="submit">Compare</button>
</form>
<div class="grid2">{side(left)}{side(right)}</div>
<p class="note">Both sample sizes are on the page on purpose. A difference
between two slices of a few dozen contacts is not a finding, and this screen
says so rather than letting the bigger percentage win the argument. Nothing
here has been sent, so these are eligibility and rehearsal numbers, not
deliverability ones.</p>
"""


# ------------------------------------------------------------------- Slack
#
# Three screens, and the split between them is the architecture rather than a
# layout: `slack_admin` is the global operations channel and the routing table
# for every workspace, `slack_notifications` is the log, and
# `slack_status_panel` is the one block a workspace sees about itself.

DASH = "—"
RSQUO = "’"


def _severity_tag(severity):
    return tag(str(severity or "").replace("_", " "),
               {"critical": "block", "warning": "warn",
                "action_required": "warn", "info": "info"}.get(severity, ""))


def _destination_tag(destination):
    return tag(destination, {"global": "info", "workspace": "pass",
                             "nowhere": "block"}.get(destination, ""))


def _notify_status_tag(status):
    return tag(status, {"sent": "pass", "planned": "info", "failed": "block",
                        "retrying": "warn", "suppressed": "block",
                        "unconfigured": "warn"}.get(status, ""))


def slack_admin(data):
    """The global operations channel, and where every workspace's alerts go.

    The column worth reading is "channel". Blank means this workspace's
    positive replies reach nobody - not that they fall back to the operations
    channel, and not that they go to whichever room is closest in name. The
    router has no fallback, and this page says so in words rather than leaving
    a reader to infer it from an empty cell.
    """
    live = data["live"]
    head = kv([
        row("Global operations channel",
            "<code>" + esc(data["ops_channel"]) + "</code>"
            if data["ops_configured"] else unavailable(
                esc(data["ops_channel_var"]) + " is not set, so operational "
                "alerts have nowhere to post"), raw=True),
        row("Configured by",
            "<code>" + esc(data["ops_channel_var"]) + "</code>", raw=True),
        row("Slack posting",
            tag("LIVE", "block") if live
            else tag("disabled", "pass") + ' <span class="small muted">'
                 "notifications are recorded and rendered, never posted"
                 "</span>",
            raw=True),
    ])

    rows_html = ""
    for space in data["workspaces"]:
        toggles = " ".join(
            tag(t["event"].replace("_", " "),
                "pass" if t["allowed"] else "block")
            for t in space["toggles"])
        channel = ("<code>" + esc(space["channel"]) + "</code>"
                   if space["configured"]
                   else unavailable("no channel mapped; nothing is routed "
                                    "here"))
        rows_html += (
            "<tr><td><b>" + esc(space["name"]) + "</b>"
            '<div class="small muted"><code>' + esc(space["slug"])
            + "</code></div></td><td>" + channel + "</td><td>" + toggles
            + "</td><td>" + esc(space["notifications"]) + "</td>"
            '<td class="small muted">' + esc(space["last"] or "never")
            + "</td></tr>")

    warnings = ""
    if data["unconfigured"]:
        warnings += panel(
            "Workspaces with no channel",
            "<p>" + esc(", ".join(data["unconfigured"])) + "</p>"
            '<p class="small muted">A positive reply in one of these is '
            "recorded with status <code>unconfigured</code> and posted "
            "nowhere. It is never redirected to another workspace" + RSQUO
            + "s channel, and never to the operations channel.</p>")
    if data["collisions"]:
        shared = "".join(
            "<tr><td><code>" + esc(channel) + "</code></td><td>"
            + esc(", ".join(slugs)) + "</td></tr>"
            for channel, slugs in data["collisions"].items())
        warnings += panel(
            "One channel, more than one workspace",
            table(["Channel", "Workspaces"], shared)
            + '<p class="small muted">Reported, not resolved. This may be '
              "deliberate; it is also what a copied setting looks like.</p>")

    routes = "".join(
        "<tr><td><code>" + esc(r["event"]) + "</code></td><td>"
        + _destination_tag(r["destination"]) + "</td><td>"
        + _severity_tag(r["severity"]) + "</td></tr>"
        for r in data["routes"])

    recent = "".join(
        '<tr><td class="small muted">' + esc(n.get("at")) + "</td><td>"
        + esc(n.get("workspace") or DASH) + "</td><td><code>"
        + esc(n.get("type")) + "</code></td><td>"
        + _destination_tag(n.get("destination")) + "</td><td>"
        + _notify_status_tag(n.get("status")) + "</td></tr>"
        for n in data["recent"])

    return (
        "<h2>Slack operations</h2>"
        + panel("Global channel", head)
        + warnings
        + panel("Per-workspace channels",
                # "Alert kinds", not "Enabled for": the column lists every
                # kind and colours each on or off, so a header promising the
                # enabled ones reads as a list of five enabled kinds.
                table(["Workspace", "Channel", "Alert kinds", "Alerts",
                       "Last"], rows_html, "slack-workspaces", True)
                + '<p class="small muted">Set with the <code>'
                + esc(data["channel_key"]) + "</code> policy on each "
                "workspace" + RSQUO + "s settings page. It is never inferred "
                "from the workspace name.</p>")
        + section("Routing table",
                  table(["Event", "Destination", "Severity"], routes))
        + panel("Recent notifications",
                table(["When", "Workspace", "Event", "Destination", "Status"],
                      recent)
                + link("/notifications?scope=all",
                       "Full notification history")))


def slack_demo(data):
    """Eight fictional alerts, and which channel each would go to.

    Every one of them is `planned` and none is posted. The value of the
    screen is the three columns read together: the same event type reaches a
    different room in a different workspace, and one of them reaches no room
    at all.
    """
    cards = ""
    for scenario in data["scenarios"]:
        where = ("<code>" + esc(scenario["channel"]) + "</code>"
                 if scenario["channel"]
                 else unavailable("no channel; recorded and posted nowhere"))
        body = kv([
            row("Level", _destination_tag(scenario["destination"])
                + (" &middot; global operations channel"
                   if scenario["destination"] == "global"
                   else " &middot; this workspace only"
                   if scenario["destination"] == "workspace"
                   else " &middot; Web App only"), raw=True),
            row("Workspace", esc(scenario["workspace"] or "none - this is "
                                 "about the machine, not a campaign"),
                raw=True),
            row("Channel", where, raw=True),
            row("Severity", _severity_tag(scenario["severity"]), raw=True),
            row("Status", _notify_status_tag(scenario["status"]), raw=True),
            row("Why", esc(scenario["why"]), raw=True),
        ])
        message = ("<pre class=\"json\">" + esc(scenario["text"]) + "</pre>"
                   if scenario["text"] else
                   empty("Nothing would be posted",
                         "This scenario routes nowhere."))
        cards += panel(
            scenario["title"],
            body + "<h4>What would be posted</h4>" + message
            + '<p class="small muted">' + esc(scenario["note"]) + "</p>")

    return (
        "<h2>Slack scenarios</h2>"
        '<p class="small muted">Fictional companies, fictional people, '
        "fictional quotations. Nothing on this page has been posted and "
        "nothing on it will be: these are routing decisions, taken by the "
        "same function the live path calls.</p>"
        + stats([("scenarios", len(data["scenarios"])),
                 ("to the operations channel", data["to_global"], "info"),
                 ("to a client channel", data["to_workspace"], "pass"),
                 ("nowhere to go", data["nowhere"],
                  "warn" if data["nowhere"] else ""),
                 ("workspaces", len(data["workspaces"]))])
        + ("" if data["live"] else
           '<p class="small muted">Slack posting is disabled. Posts made: 0.'
           "</p>")
        + cards)


def slack_notifications(data, may_widen=False, demo=None):
    """The log. Every notification, what it was, and where it went.

    A row with destination `nowhere` is not a failure and is not hidden: a
    neutral reply is *supposed* to stay in the Web App, and this log is where
    somebody checks that it did.
    """
    scope = data["scope"]
    rows_html = ""
    for n in data["rows"]:
        detail = ('<div class="small muted">' + esc(n["why"]) + "</div>"
                  if n["why"] else "")
        error = ('<div class="small block">' + esc(n["last_error"]) + "</div>"
                 if n["last_error"] else "")
        channel = ("<code>" + esc(n["channel"]) + "</code>" if n["channel"]
                   else unavailable("no channel"))
        rows_html += (
            '<tr><td class="small muted">' + esc(n["at"]) + "</td><td>"
            + esc(n["workspace"] or DASH) + "</td><td><code>"
            + esc(n["type"]) + "</code>" + detail + "</td><td>"
            + _destination_tag(n["destination"]) + "</td><td>"
            + _severity_tag(n["severity"]) + "</td><td>"
            + _notify_status_tag(n["status"]) + error + "</td><td>"
            + channel + "</td></tr>")
    if not rows_html:
        rows_html = ('<tr><td colspan="7">'
                     + empty("No notifications yet",
                             "Nothing has been routed in this scope.")
                     + "</td></tr>")

    summary = data["summary"]
    counts = stats(
        [("Total", summary["total"])]
        + [(k.replace("_", " "), v)
           for k, v in summary["by_destination"].items()]
        + [(k, v) for k, v in summary["by_status"].items()])

    where = ("Workspace <code>" + esc(scope) + "</code>" if scope
             else "Every workspace")
    widen = ""
    if may_widen:
        widen = (" &middot; " + link("/notifications?scope=all",
                                     "all workspaces") if scope
                 else " &middot; " + link("/notifications", "this workspace"))

    filters = (
        '<form method="get" action="/notifications" class="filters">'
        + ('<input type="hidden" name="scope" value="all">'
           if not scope else "")
        + _select("type", data["filters"]["type"], data["event_types"])
        + _select("status", data["filters"]["status"], data["statuses"])
        + '<button type="submit">Filter</button></form>')

    live = ("" if data["live"] else
            '<p class="small muted">Slack posting is disabled in this build. '
            "Notifications are routed, recorded and rendered; none is posted."
            "</p>")

    demo_block = ("" if demo is None else
                  section("Demo scenarios: which channel each alert would go "
                          "to", slack_demo(demo)))

    return (
        "<h2>Notification history</h2>"
        '<p class="small muted">' + where + widen + "</p>"
        + counts + live + filters
        + table(["Timestamp", "Workspace", "Event", "Destination", "Severity",
                 "Status", "Channel"], rows_html, "notifications", True)
        + demo_block)


def _select(name, current, choices):
    options = '<option value="">any ' + esc(name) + "</option>"
    for choice in choices:
        selected = " selected" if choice == current else ""
        options += ('<option value="' + attr(choice) + '"' + selected + ">"
                    + esc(choice) + "</option>")
    return '<select name="' + attr(name) + '">' + options + "</select>"


def slack_status_panel(data, show_ops=False, link_history=True):
    """What a workspace is told about its own Slack routing.

    `show_ops` is the operator's cut. A client-facing role is not shown the
    global operations channel: the existence and the name of the room where
    provider health and credit exposure are discussed are not part of what
    this workspace bought.
    """
    rows = [
        row("Channel",
            "<code>" + esc(data["channel"]) + "</code>" if data["configured"]
            else unavailable("no channel mapped for this workspace"),
            raw=True),
    ]
    for toggle in data["toggles"]:
        rows.append(row(
            toggle["label"],
            tag("on", "pass") if toggle["allowed"] else tag("off", "block"),
            raw=True))
    last = data["last_alert"]
    rows.append(row(
        "Last alert",
        (esc(last.get("at")) + " &middot; <code>" + esc(last.get("type"))
         + "</code>") if last
        else unavailable("nothing has been routed here yet"),
        raw=True))
    if show_ops:
        rows.append(row("Slack posting",
                        tag("LIVE", "block") if data["live"]
                        else tag("disabled", "pass"), raw=True))
    body = kv(rows)
    if not data["configured"]:
        body += ('<p class="small muted">Alerts for this workspace are '
                 "recorded and go nowhere. They are never sent to another "
                 "workspace" + RSQUO + "s channel.</p>")
    if link_history:
        body += link("/notifications", "Notification history")
    return panel("Slack", body)


# ----------------------------------------------------------- client reports
#
# One screen: what can be built, the controls that shape it, and what has been
# built before. The history is on the same page deliberately - "generate" and
# "what did we send them last month" are the same question asked twice.


def client_reports(data, csrf, generated=None):
    """The Client Reports screen.

    The template list comes from the API already filtered by permission, so
    a client-facing role does not see the internal operations report offered
    and refused - it is simply not there. Rendering a control that always
    fails teaches people the product is broken.
    """
    if not data["templates"]:
        return ("<h2>Client reports</h2>"
                + empty("No report template available",
                        "This role cannot generate reports for this "
                        "workspace."))

    banner = ""
    if generated:
        if generated.get("status") == "failed":
            banner = panel(
                "Report not generated",
                "<p>" + esc(generated.get("error") or "unknown error")
                + "</p><p class=\"small muted\">Nothing was sent and nothing "
                  "was changed. The attempt is in the history below.</p>")
        else:
            banner = panel(
                "Report ready",
                "<p>" + esc(generated.get("id")) + " &middot; "
                + esc(generated.get("bytes") or 0) + " bytes</p>"
                + link("/reporting/client/download?id="
                       + str(generated.get("id")), "Download PDF"))

    blocks = ""
    for template in data["templates"]:
        checked = data["defaults"]["sections"] \
            if template["key"] == data["defaults"]["template"] else \
            [s["key"] for s in template["sections"]]
        boxes = ""
        for section in template["sections"]:
            mark = " checked" if section["key"] in checked else ""
            flag = ("" if section["client_safe"]
                    else ' <span class="tag block">operator only</span>')
            boxes += (
                '<label class="check"><input type="checkbox" name="sections" '
                'value="' + attr(section["key"]) + '"' + mark + "> "
                + esc(section["label"]) + flag + "</label>")

        campaigns = '<option value="">All campaigns</option>'
        for campaign in data["campaigns"]:
            campaigns += ('<option value="' + attr(campaign["campaign_id"])
                          + '">' + esc(campaign["name"]) + "</option>")

        blocks += section_block(
            template["label"],
            '<p class="small muted">' + esc(template["blurb"]) + "</p>"
            '<form method="post" action="/reporting/client/generate">'
            '<input type="hidden" name="csrf" value="' + attr(csrf) + '">'
            '<input type="hidden" name="template" value="'
            + attr(template["key"]) + '">'
            '<div class="grid2">'
            '<label>From<input type="date" name="since"></label>'
            '<label>To<input type="date" name="until"></label>'
            "</div>"
            '<label>Campaigns<select name="campaigns" multiple size="4">'
            + campaigns + "</select></label>"
            '<div class="checks">' + boxes + "</div>"
            '<button type="submit"' + ("" if data["can_generate"]
                                       else " disabled") + ">Generate PDF"
            "</button>"
            + ("" if data["can_generate"] else
               '<p class="small muted">This role may read reports but not '
               "generate them.</p>")
            + "</form>",
            open_=template["key"] == data["defaults"]["template"])

    rows = ""
    for row in data["history"]:
        status = tag(row["status"],
                     {"generated": "pass", "downloaded": "pass",
                      "failed": "block"}.get(row["status"], "warn"))
        action = (link("/reporting/client/download?id=" + str(row["id"]),
                       "Download")
                  if row["status"] in ("generated", "downloaded") else "")
        rows += (
            '<tr><td class="small muted">' + esc(row["at"]) + "</td><td>"
            + esc(row["template"]) + "</td><td>" + esc(row["period"])
            + "</td><td>" + esc(len(row["sections"] or [])) + "</td><td>"
            + esc(row["by"]) + "</td><td>" + status + "</td><td>"
            + action + "</td></tr>")
    if not rows:
        rows = ('<tr><td colspan="7">'
                + empty("No reports generated yet",
                        "Generate one above; every generation is recorded "
                        "here with who ran it and over what period.")
                + "</td></tr>")

    return (
        "<h2>Client reports</h2>"
        '<p class="small muted">Every figure in a report is counted from the '
        "same functions the screens read. A figure this system cannot observe "
        "is named in the report's appendix rather than printed as zero.</p>"
        + banner
        + blocks
        + panel("Report history",
                table(["Generated", "Template", "Period", "Sections", "By",
                       "Status", ""], rows, "report-history", True)))


def section_block(title, body, open_=False):
    return section(title, body, open_)


# ------------------------------------------------------------- onboarding
#
# The one screen that answers "what is left". Every row is checked against
# stored state, so it cannot say "senders configured" about a workspace with
# none - and none of it costs a provider call.


def audience_overview(data):
    """The shape of a market universe.

    An empty workspace gets the next action rather than a wall of zeroes -
    a chart of nothing teaches nothing, and the person looking at it has
    exactly one thing they need to do.
    """
    if data["empty"]:
        return ("<h1>Audience</h1>"
                + empty("Nothing here yet",
                        "Import a CSV of company domains and Resonate will "
                        "normalise it, check it against everything already "
                        "known, and show you what the market looks like.")
                + '<div class="quickrow">'
                  '<a class="quick primary" href="/upload"><b>Import leads'
                  "</b><span>Upload a CSV of company domains</span></a>"
                  "</div>")

    ladder = ""
    for stage in data["stages"]:
        share = ("" if stage["share"] is None
                 else f"{stage['share']:.0%} of {stage['of']}")
        ladder += (
            "<tr><td><b>" + esc(stage["label"]) + "</b>"
            + '<div class="small muted">' + esc(stage["why"]) + "</div></td>"
            + "<td>" + esc(stage["count"]) + "</td>"
            + '<td class="small muted">' + esc(share) + "</td></tr>")

    def distribution(title, counts):
        if not counts:
            return ""
        rows = "".join(
            "<tr><td>" + esc(name) + "</td><td>" + esc(count) + "</td></tr>"
            for name, count in sorted(counts.items(),
                                      key=lambda kv: -kv[1])[:12])
        return section(title, table(["", "Companies"], rows))

    dist = data["distribution"]
    body = (
        stats([("companies", data["total"]),
               ("a fit", data["stages"][2]["count"], "pass"),
               ("reachable", data["stages"][4]["count"], "pass"),
               ("cannot be worked", data["not_workable"],
                "block" if data["not_workable"] else "")])

        + table(["Stage", "Companies", "Share"], ladder)

        + ('<p class="note stop">' + esc(data["not_workable"])
           + " account(s) cannot be written to - suppressed, or held while "
             "a conversation is live. They are in the audience and nothing "
             "will go to them.</p>"
           if data["not_workable"] else "")

        + distribution("By vertical", dist.get("vertical"))
        + distribution("By region", dist.get("region"))
        + distribution("By size", dist.get("employee_band"))
        + distribution("By country", dist.get("country"))

        + '<p class="note">Counted from stored state. Nothing here '
          "classifies, scores or spends: the verdicts were decided when "
          "the companies were qualified, and this counts them.</p>")

    return ('<h1>Audience</h1><div class="crumb">'
            + esc(data["batch"] or "All batches")
            + " &middot; what this market universe looks like</div>"
            + panel("Shape", body))


def discovery_view(data):
    """What a source proposed, and what was already known.

    The excluded rows are the point of the screen, not an appendix. A run
    that returned six companies and kept three has done its job; a screen
    that showed only the three would be hiding the work.
    """
    new_rows = ""
    for row in data["new"]:
        new_rows += (
            "<tr><td><b>" + esc(row.get("company") or row["domain"])
            + '</b><div class="small muted">' + esc(row["domain"])
            + "</div></td>"
            + '<td class="small">' + esc(row["evidence"]) + "</td>"
            + '<td class="small muted">' + esc(row["source"]) + "</td></tr>")

    known_rows = ""
    for row in data["excluded"]:
        known_rows += (
            "<tr><td>" + esc(row.get("company") or row["domain"]) + "</td>"
            + "<td>" + tag(row["verdict"].replace("_", " "),
                           "block" if row["verdict"] == "suppressed"
                           else "warn") + "</td>"
            + '<td class="small muted">' + esc(row["why"]) + "</td></tr>")

    gaps = ""
    for row in data["unavailable"]:
        gaps += ("<li><b>" + esc(row["source"].replace("_", " ")) + "</b> "
                 + '<span class="small muted">' + esc(row["why"])
                 + "</span>"
                 + (' <code>' + esc(row["marker"]) + "</code>"
                    if row.get("marker") else "") + "</li>")

    counts = data["counts"]
    body = (
        stats([("proposed", counts["proposed"]),
               ("new", counts["new"], "pass" if counts["new"] else ""),
               ("already known", counts["already_known"],
                "warn" if counts["already_known"] else ""),
               ("credits spent", data["spent"], "pass")])

        + '<p class="note">Nothing here has been enriched or contacted. '
        "Discovery proposes; the spend happens after somebody approves.</p>"

        + (table(["Company", "Why it was proposed", "Source"], new_rows)
           if new_rows else
           '<p class="note">Nothing new this run. That is a result, not a '
           "failure - it means the market this ICP describes is already "
           "in the workspace.</p>")

        # Parenthesised deliberately. Without the brackets the ternary
        # binds the whole expression above it, so an empty excluded list
        # silently swallowed the counts and the "nothing new" note - the
        # screen rendered, and left out its own result.
        + (section("Proposed and already known",
                   table(["Company", "Why not new", "Detail"], known_rows)
                   + '<p class="note">These are the rows a client would '
                     "otherwise have been asked to look at twice. Showing "
                     "them is how the delta can be checked rather than "
                     "trusted.</p>",
                   open_=True)
           if known_rows else "")

        + section("What could not be checked",
                  "<ul>" + gaps + "</ul>"
                  + '<p class="note">A delta computed without these is not '
                    "a smaller delta. It is a wrong one, and it surfaces "
                    "the client's own open opportunities as fresh "
                    "leads.</p>")

        + ('<p class="note">' + esc(data["review_rows"])
           + " candidate(s) would go to the client for review. "
           + ('<a class="btn primary" href="/discovery/review.csv">'
              "Download review CSV</a>" if data["can_export"] else
              "Your role cannot export it.") + "</p>"))

    return ('<h1>Discovery</h1><div class="crumb">What a source proposed '
            "this week, and what was already known</div>"
            + panel("This run", body))


def revival_view(data):
    """What is worth looking at again, and what would be new about it.

    The second table is the one that earns its place: accounts that are
    quiet, past their cooling period, and have nothing new behind them. A
    screen that showed only the ready ones would make that queue invisible,
    and an invisible queue is where a repeat campaign comes from.
    """
    summary = data["summary"]
    head = stats([(row["label"], row["count"],
                   "pass" if row["verdict"] == "ready" else "")
                  for row in data["verdicts"]])

    rows = ""
    for row in data["ready"]:
        cases = "".join(
            '<div class="small"><b>' + esc(case["label"]) + "</b> "
            + '<span class="muted">' + esc(case["detail"] or "") + "</span>"
            + "</div>"
            for case in row["cases"])
        rows += ("<tr><td><b>" + esc(row["company"] or row["record_id"])
                 + "</b>"
                 + '<div class="small muted">' + esc(row["domain"] or "")
                 + "</div></td>"
                 + '<td class="small">'
                 + esc(f'{row.get("days_since")} days quiet') + "</td>"
                 + "<td>" + cases + "</td></tr>")

    body = head + (
        table(["Account", "Quiet for", "What would be new"], rows) if rows
        else '<p class="note">No account here has anything new behind it '
             "yet.</p>")

    quiet = ""
    for row in data["quiet_with_nothing_new"]:
        quiet += ("<tr><td>" + esc(row["company"] or row["record_id"])
                  + "</td>"
                  + '<td class="small">'
                  + esc(f'{row.get("days_since")} days') + "</td>"
                  + '<td class="small muted">' + esc(row["why"])
                  + "</td></tr>")
    waiting = section(
        "Quiet, and nothing new to say",
        (table(["Account", "Quiet for", "Why not"], quiet) if quiet else
         '<p class="note">Nothing is waiting in this state.</p>')
        + '<p class="note">Reviving one of these with the angle that '
          "already failed is not a revival. It is the same campaign with a "
          "later date on it, and the recipient reads it that way.</p>")

    return ('<h1>Revival</h1><div class="crumb">'
            "Accounts that went quiet, and whether anything has changed"
            "</div>"
            + panel("Worth looking at again", body)
            + panel("Waiting", waiting)
            + '<p class="note">' + esc(data["note"]) + "</p>")


def returns_view(data):
    """Who said they would be back, and whether today is the day.

    Three tables, and the middle one is why this is a screen rather than a
    number. An absence with no readable return date is not a parsing
    failure to hide: it is a person somebody has to look at by hand, and a
    page showing only the due ones would bury that queue for ever.

    Nothing here is a button. `DUE` means a person may now look at this
    contact; the stop their out-of-office wrote is still on them, and
    lifting it is a human action taken somewhere else.
    """
    head = stats([(row["label"], row["count"],
                   "pass" if row["verdict"] == "due" else "")
                  for row in data["verdicts"]])

    def who(row):
        return ("<td><b>" + esc(row.get("name") or row["contact"]) + "</b>"
                + '<div class="small muted">'
                + esc(row.get("company") or row["record_id"])
                + "</div></td>")

    due = ""
    for row in data["due"]:
        late = row.get("days_since_return") or 0
        due += ("<tr>" + who(row)
                + '<td class="small">' + esc(str(row.get("return_date") or ""))
                + "</td>"
                + '<td class="small muted">'
                + esc("back today" if late == 0 else f"{late} days ago")
                + "</td></tr>")
    back = panel(
        "Back now",
        (table(["Who", "They said", "Since"], due) if due else
         '<p class="note">Nobody is due back today.</p>')
        + '<p class="note">A date is a reason to look, not permission to '
          "write. Their cadence is still stopped, and it stays stopped "
          "until a person decides otherwise.</p>")

    unknown = ""
    for row in data["needs_a_person"]:
        unknown += ("<tr>" + who(row)
                    + '<td class="small muted">'
                    + esc(row.get("return_status") or "") + "</td></tr>")
    asked = panel(
        "They did not say when",
        (table(["Who", "What they said instead"], unknown) if unknown else
         '<p class="note">Every recorded absence carried a date we could '
         "read.</p>")
        + '<p class="note">A guessed return date is worse than a missing '
          "one: it schedules a follow-up into somebody's leave, which is "
          "what their message was warning about. These are read by "
          "hand.</p>")

    later = ""
    for row in data["waiting"]:
        when = row.get("days_until")
        later += ("<tr>" + who(row)
                  + '<td class="small">'
                  + esc(str(row.get("return_date") or "")) + "</td>"
                  + '<td class="small muted">'
                  + esc(f"in {when} days" if when is not None
                        else (row.get("why") or "")) + "</td></tr>")
    waiting = panel(
        "Not yet",
        table(["Who", "They said", "Why not"], later) if later else
        '<p class="note">Nothing is waiting.</p>')

    return ('<h1>Out-of-office returns</h1><div class="crumb">'
            "People who said they would be back, as of "
            + esc(data["as_of"]) + "</div>"
            + head + back + asked + waiting)


def refresh_plan(data):
    """What is worth spending on again, and everything that is not.

    The two numbers a reader needs first are what this would cost and what
    it left out. A plan that showed only its selection would read as the
    whole answer.
    """
    estimate = data["estimate"]
    head = stats([
        ("accounts", data["considered"]),
        ("due for something", data["due"]),
        ("selected", len(data["selected"]), "pass"),
        ("below the line", data["below_the_line"],
         "warn" if data["below_the_line"] else ""),
        ("estimated credits", estimate["credits"]),
    ])

    rows = ""
    for row in data["selected"]:
        kinds = "".join(
            f'<div class="small">{esc(k["label"])}'
            + (f' <span class="muted">{k["credits"]} credit(s)</span>'
               if k["credits"] else ' <span class="muted">free</span>')
            + (' <span class="muted">never done</span>' if k["never"] else "")
            + "</div>"
            for k in row["due"])
        rows += (
            "<tr><td><b>" + esc(row["company"] or row["record_id"]) + "</b>"
            + '<div class="small muted">' + esc(row["domain"] or "")
            + "</div></td>"
            + '<td class="small">' + esc(str(row["priority"]))
            + '<div class="muted">' + esc(row["why_now"] or "") + "</div></td>"
            + '<td class="small">' + esc(f'{row["urgency"]}x') + "</td>"
            + "<td>" + kinds
            + ('<div class="small">'
               + tag("free work only", "warn") + "</div>"
               if row.get("floor_limited") else "")
            + "</td>"
            + '<td class="small">' + esc(str(row.get("credits", 0)))
            + "</td></tr>")

    body = head + (
        table(["Account", "Priority", "Overdue by", "What would be done",
               "Credits"], rows)
        if rows else
        '<p class="note">Nothing is due for a refresh in this workspace.</p>')

    if data["capped_scan"]:
        body += ('<p class="note">Priority was assessed for the stalest '
                 + esc(str(data["scanned"])) + " of "
                 + esc(str(data["due"])) + " accounts that are due. The rest "
                 "were not scanned, which is not the same as not needing "
                 "anything.</p>")

    excluded = "".join(
        "<li><b>" + esc(str(row["count"])) + "</b> " + esc(row["label"])
        + "</li>"
        for row in data["excluded"])
    left_out = section(
        "Not refreshed", ("<ul>" + excluded + "</ul>") if excluded else
        '<p class="note">Nothing was excluded.</p>')

    cost = "".join(
        "<li><b>" + esc(str(call["credits"])) + "</b> credit(s) across "
        + esc(str(call["calls"])) + " " + esc(call["call"]) + " call(s)</li>"
        for call in estimate["by_call"] if call["credits"])
    spend = section(
        "What it would cost",
        ("<ul>" + cost + "</ul>" if cost else
         '<p class="note">Nothing here costs a credit.</p>')
        + '<p class="note">' + esc(estimate["note"]) + "</p>")

    return ('<h1>Refresh plan</h1><div class="crumb">'
            "Which accounts we already know are worth spending on again"
            "</div>"
            + panel("This week", body)
            + panel("Left out", left_out + spend)
            + '<p class="note">' + esc(data["note"])
            + " There is no scheduler: &ldquo;weekly&rdquo; describes the "
              "intended cadence, and a run happens when somebody asks for "
              "one.</p>")


def operational_health(data):
    """What is failing, what still worked, and whether to retry.

    "It failed" without "and the reply was still recorded" is the sentence
    that makes somebody re-run a thing that already happened, so every row
    carries both.
    """
    if data["clean"]:
        body = ('<p class="note">Nothing is failing or owed in this '
                "workspace.</p>")
    else:
        rows = ""
        for row in data["rows"]:
            rows += (
                "<tr><td><b>" + esc(row["area"]) + "</b>"
                + '<div class="small muted">' + esc(row["what"])
                + "</div></td>"
                + "<td>" + tag(row["state"],
                               "block" if not row["retry_safe"] else "warn")
                + "</td>"
                + '<td class="small">'
                + (esc(f"{row['succeeded']} succeeded first")
                   if row["succeeded"] else "")
                + "</td>"
                + '<td class="small muted">' + esc(row["detail"] or "")
                + "</td>"
                + "<td>" + (tag("retry is safe", "pass") if row["retry_safe"]
                            else tag("needs a person", "block"))
                + '<div class="small muted">' + esc(row["why_safe"])
                + "</div></td></tr>")
        body = (stats([("areas", data["counts"]["areas"]),
                       ("rows", data["counts"]["rows"]),
                       ("retryable", data["counts"]["retryable"], "pass"),
                       ("need a person",
                        data["counts"]["needs_a_person"],
                        "block" if data["counts"]["needs_a_person"] else "")])
                + table(["Area", "State", "Progress", "Detail", "Retry"],
                        rows))

    watched = "".join(
        "<li><b>" + esc(row["area"]) + "</b> "
        + '<span class="small muted">' + esc(row["why"]) + "</span></li>"
        for row in data["unwatched"])
    body += section("Not watched here", "<ul>" + watched + "</ul>"
                    + '<p class="note">A health screen that looks clean '
                      "because it was not watching is worse than none.</p>")

    return ('<h1>Operational health</h1><div class="crumb">'
            "What is failing, and whether anything was lost</div>"
            + panel("Failures", body))


def cohort_performance(data):
    """What the cohorts have done, and how much of it is worth believing.

    The state column is the whole screen. A rate without it invites the
    reader to compare 15% against 5% and act; with it, they can see that
    one of those rests on six replies and the other on two hundred.
    """
    rows = ""
    for cohort in data["cohorts"]:
        enough = cohort["state"] != "insufficient_data"
        rows += (
            "<tr><td><b>" + esc(cohort["cohort"]) + "</b></td>"
            + "<td>" + esc(cohort["contacted"]) + "</td>"
            + "<td>" + esc(cohort["outcomes"]) + "</td>"
            + "<td>" + (esc(f"{cohort['rate']:.1%}") if enough
                        else unavailable("not enough yet")) + "</td>"
            + "<td>" + tag(cohort["state_label"],
                           {"high_confidence": "pass", "promising": "warn",
                            "declining": "block"}.get(cohort["state"], ""))
            + "</td>"
            + '<td class="small muted">' + esc(cohort["why"]) + "</td></tr>")

    picks = ""
    for entry in data["recommendations"]["recommendations"]:
        picks += ("<li><b>" + esc(entry["what"]) + "</b>"
                  + '<div class="small muted">' + esc(entry["why"])
                  + "</div></li>")

    switches = ""
    for entry in data["available_dimensions"]:
        switches += (
            '<a class="btn' + (" primary" if entry["chosen"] else "")
            + '" href="/reporting/cohorts?dimension='
            + attr(entry["key"]) + '">' + esc(entry["key"].replace("_", " "))
            + "</a> ")

    body = (
        stats([("accounts", data["accounts"]),
               ("contacted", data["contacted"], "pass"),
               ("cohorts", len(data["cohorts"])),
               ("enough to judge", data["cohorts_with_enough_data"],
                "pass" if data["cohorts_with_enough_data"] else "warn")])
        + '<p class="note">' + esc(data["baseline"]["why"])
        + ". Every cohort below is measured against that, not against an "
        "industry benchmark - what this workspace does is the only fair "
        "comparison.</p>"
        + '<div class="filters">' + switches + "</div>"
        + (table(["Cohort", "Contacted", "Outcomes", "Rate", "Evidence",
                  "Why"], rows) if rows else
           '<p class="note">No cohort has enough accounts on these '
           "dimensions yet.</p>")
        + ('<p class="note stop">Nothing here has enough evidence to act '
           "on. That is the honest answer at this volume, and it is a "
           "better one than a winner picked from a handful of "
           "replies.</p>"
           if not data["cohorts_with_enough_data"] else "")
        + (section("Worth considering", "<ul>" + picks + "</ul>"
                   + '<p class="note">'
                   + esc(data["recommendations"]["note"]) + "</p>",
                   open_=True) if picks else "")
        + '<p class="note">' + esc(data["note"]) + "</p>")

    return ('<h1>Cohort performance</h1>'
            '<div class="crumb">Observed rates by cohort, and how much of '
            "it is worth believing</div>" + panel("Cohorts", body))


def strategy_centre(data, csrf=None):
    """What was decided, what it rested on, and what has no reason recorded.

    The basis column is the one worth reading. "Measured in this workspace"
    and "judgement, nothing measured" are both legitimate, and only the
    first can be re-examined by looking at data - the second has to be
    argued again from scratch. Showing them in one column, in the same
    words the person chose, is the whole point.
    """
    rows = ""
    for block in data["areas"]:
        if not block["decisions"]:
            continue
        rows += ('<tr><td colspan="4"><b>' + esc(block["label"])
                 + "</b></td></tr>")
        for entry in block["decisions"]:
            checkable = entry["basis"] in ("measured", "research")
            rows += (
                "<tr><td>" + esc(entry["decided"])
                + '<div class="small muted">' + esc(entry["why"]) + "</div>"
                + ('<div class="small muted">Evidence: '
                   + esc(entry["evidence"]) + "</div>"
                   if entry.get("evidence") else "")
                + "</td><td>"
                + tag(_basis_label(entry["basis"]),
                      "pass" if checkable else "warn")
                + "</td><td>"
                + (('<code>' + esc(entry["policy_key"]) + "</code>")
                   if entry.get("policy_key") else
                   unavailable("no setting"))
                + '</td><td class="small muted">'
                + esc((entry.get("at") or "")[:10]) + "<br>"
                + esc(entry.get("decided_by") or "") + "</td></tr>")

    unexplained = ""
    for entry in data.get("unexplained_detail") or []:
        unexplained += ("<tr><td>" + esc(entry["label"])
                        + "</td><td><code>" + esc(entry["key"])
                        + "</code></td><td>" + esc(entry["value"])
                        + "</td></tr>")

    superseded = ""
    for entry in data.get("history") or []:
        if not entry.get("superseded_by"):
            continue
        superseded += (
            "<tr><td>" + esc(entry["decided"])
            + '<div class="small muted">' + esc(entry["why"]) + "</div>"
            + "</td><td>" + tag(_basis_label(entry["basis"]), "")
            + '</td><td class="small muted">'
            + esc((entry.get("at") or "")[:10])
            + "</td></tr>")

    body = (
        # A refusal nobody can see looks like nothing happening. The form
        # below reopens itself on an error for the same reason.
        (('<p class="note stop">' + esc(data["error"]) + "</p>")
         if data.get("error") else "")
        + stats([("decisions", data["decisions"]),
               ("checkable against data", data["checkable"], "pass"),
               ("judgement", data["judgement"],
                "warn" if data["judgement"] else ""),
               ("superseded", data["superseded"]),
               ("settings with no reason", len(data["unexplained"]),
                "warn" if data["unexplained"] else "")])

        + '<p class="note">This page decides nothing. It records what '
          "somebody believed and what that rested on; the settings screen "
          "is the only thing that changes what the machine does.</p>"

        + (table(["What was decided", "Rests on", "Setting", "When"], rows)
           if rows else
           '<p class="note">No decisions recorded yet. Every setting in '
           "this workspace is currently in force for a reason nobody "
           "wrote down.</p>")

        + (section("Settings changed with no reason recorded",
                   table(["Setting", "Key", "Value"], unexplained)
                   + '<p class="note">Not a fault - most changes are '
                     "obvious at the time. They stop being obvious about "
                     "six months later, which is when somebody asks "
                     "whether the reason still holds.</p>",
                   open_=True)
           if unexplained else "")

        + (section("Superseded",
                   table(["What was decided", "Rested on", "When"],
                         superseded)
                   + '<p class="small muted">Kept rather than deleted. '
                     '"We believed this, then we learned otherwise" is '
                     "the part of a decision log worth having.</p>")
           if superseded else "")

        + (_decision_form(data, csrf) if data.get("can_record") else
           '<p class="note">Your role can read these decisions but not '
           "record one.</p>"))

    return ('<h1>Strategy</h1><div class="crumb">Why this workspace is '
            "worked the way it is</div>" + panel("Decisions", body))


def _basis_label(basis):
    return {"measured": "measured here", "client": "client asked",
            "research": "desk research",
            "judgement": "judgement only"}.get(basis, basis)


def _decision_form(data, csrf):
    areas = "".join('<option value="' + attr(a["area"]) + '">'
                    + esc(a["label"]) + "</option>"
                    for a in data.get("areas_available") or [])
    bases = "".join('<option value="' + attr(b["basis"]) + '">'
                    + esc(b["label"]) + "</option>"
                    for b in data.get("bases_available") or [])
    keys = '<option value="">No particular setting</option>'
    keys += "".join('<option value="' + attr(k) + '">' + esc(k) + "</option>"
                    for k in data.get("policy_keys") or [])
    return section(
        "Record a decision",
        '<form method="post" action="/strategy" class="stack">'
        + '<input type="hidden" name="csrf" value="' + attr(csrf) + '">'
        + "<label>What is this about"
        + '<select name="area" required>' + areas + "</select></label>"
        + "<label>What was decided"
        + '<textarea name="decided" rows="2" maxlength="600" required '
        + 'placeholder="Stop targeting agencies under 20 people">'
        + "</textarea></label>"
        + "<label>Why"
        + '<textarea name="why" rows="2" maxlength="600" required '
        + 'placeholder="Eleven of them replied and none had a budget '
        + 'holder">' + "</textarea></label>"
        + "<label>What it rests on"
        + '<select name="basis">' + bases + "</select></label>"
        + "<label>The evidence, if it was measured or researched"
        + '<textarea name="evidence" rows="2" maxlength="600" '
        + 'placeholder="40 replies across Q2, 0 meetings booked under 20 '
        + 'employees"></textarea></label>'
        + "<label>Which setting this explains, if any"
        + '<select name="policy_key">' + keys + "</select></label>"
        + '<button class="btn primary" type="submit">Record decision</button>'
        + '<p class="note">This changes no setting. If the decision needs '
          "one changed, change it on the settings screen as well - and "
          "this page will then show the two beside each other.</p>"
        + "</form>",
        open_=bool(data.get("error")) or not data["decisions"])


def onboarding(data):
    steps = ""
    for step in data["steps"]:
        if step["done"]:
            mark, kind = "done", "pass"
        elif step["blocked_by"]:
            mark, kind = "waiting", "warn"
        elif step["optional"]:
            mark, kind = "optional", ""
        else:
            mark, kind = "to do", "block"
        blocked = ""
        if step["blocked_by"] and not step["done"]:
            blocked = ('<div class="small muted">after '
                       + esc(step["blocked_by"]) + "</div>")
        why = ('<div class="small muted">' + esc(step["why"]) + "</div>"
               if step["why"] else "")
        action = ("" if step["done"]
                  else link(step["where"], "Open") if step["where"] else "")
        steps += (
            '<tr><td>' + tag(mark, kind) + "</td><td><b>"
            + esc(step["label"]) + "</b>" + why + "</td><td>"
            + esc(step["detail"]) + blocked + "</td><td>" + action
            + "</td></tr>")

    nxt = data["next"]
    head = panel(
        "Progress",
        stats([("done", str(data["done"]) + " of " + str(data["total"])),
               ("status", "ready" if data["complete"] else "in progress",
                "pass" if data["complete"] else "warn")])
        + progress(data["done"] / float(data["total"] or 1))
        + ('<p class="note">Next: <b>' + esc(nxt["label"]) + "</b> &middot; "
           + link(nxt["where"], "go there") + "</p>" if nxt else
           '<p class="note ok">Every required step is done. This workspace '
           "can build and review a campaign.</p>"))

    return (
        "<h2>Workspace setup</h2>"
        '<p class="small muted">' + esc(data["workspace_name"])
        + "</p>" + head
        + panel("Checklist",
                table(["", "Step", "State", ""], steps))
        + '<p class="note stop">' + esc(data["note"]) + "</p>")


# ----------------------------------------------------------- system health
#
# Five states, and the two that are not green carry more information than the
# one that is. Nothing here claims a provider is healthy: nothing in this
# build calls one, so the honest word is "configured, not called".


def _component_tag(state):
    return tag(state, {"healthy": "pass",
                       "configured, not called": "info",
                       "live validation required": "warn",
                       "unconfigured": "warn",
                       "degraded": "warn",
                       "failed": "block"}.get(state, ""))


def system_health(data):
    components = ""
    for item in data["components"]:
        components += (
            "<tr><td><b>" + esc(item["name"]) + "</b></td><td>"
            + _component_tag(item["state"]) + "</td><td>" + esc(item["detail"])
            + '<div class="small muted">' + esc(item["why"])
            + "</div></td></tr>")

    providers = ""
    for item in data["providers"]:
        offline = tag("yes", "pass") if item["offline_contract"] \
            else tag("no", "block")
        live = tag("validated", "pass") if item["live_contract"] \
            else tag("never", "warn")
        providers += (
            "<tr><td><b>" + esc(item["name"]) + "</b>"
            '<div class="small muted"><code>' + esc(item["variable"])
            + "</code></div></td><td>"
            + (tag("configured", "pass") if item["configured"]
               else tag("not set", "warn"))
            + "</td><td>" + offline + "</td><td>" + live + "</td><td>"
            + _component_tag(item["state"])
            + '<div class="small muted">' + esc(item["note"])
            + "</div></td></tr>")

    configuration = ""
    for row in data["configuration"]["variables"]:
        configuration += (
            "<tr><td><code>" + esc(row["name"]) + "</code></td><td>"
            + esc(row["group"]) + "</td><td>" + esc(row["classification"])
            + "</td><td>"
            + (tag("set", "pass") if row["configured"]
               else tag("blocking", "block") if row["blocking"]
               else tag("not set", ""))
            + '</td><td class="small muted">' + esc(row["why"])
            + "</td></tr>")

    blockers = ""
    if data["configuration"]["blockers"]:
        blockers = panel(
            "Would not start in production mode",
            "<p>" + esc(", ".join(data["configuration"]["blockers"]))
            + '</p><p class="small muted">Demo mode needs none of these. '
              "Production fails closed rather than starting without them.</p>")

    return (
        "<h2>System health</h2>"
        '<p class="small muted">Overall: ' + _component_tag(data["worst"])
        + " &middot; nothing on this page calls a provider, so nothing on it "
          "claims a provider is healthy.</p>"
        + blockers
        + panel("Components", table(["Component", "State", "Detail"],
                                    components))
        + panel("Providers",
                table(["Provider", "Credentials", "Offline contract",
                       "Live contract", "State"], providers)
                + '<p class="small muted">A validated offline contract means '
                  "the suite exercises a recorded response. It does not mean "
                  "anybody has spoken to the wire. See "
                  "LIVE-VALIDATION-PLAN.md.</p>")
        + section("Configuration",
                  table(["Variable", "Group", "Needed", "State", "Why"],
                        configuration)))


# ------------------------------------------------------------- suppression


def suppression(data):
    rows = ""
    for row in data["rows"]:
        kind = tag(row["kind"], {"unsubscribe": "block", "global": "block",
                                 "dropped": "warn",
                                 "reply": "pause"}.get(row["kind"], ""))
        who = link("/companies/" + str(row["record_id"]),
                   row["company"] or row["record_id"])
        if row["contact"]:
            who += ('<div class="small muted">' + esc(row["contact"])
                    + "</div>")
        rows += (
            "<tr><td>" + kind + "</td><td>" + who + "</td><td>"
            + esc(row["domain"] or "") + "</td><td>" + esc(row["scope"])
            + "</td><td>" + esc(row["why"] or "") + '</td><td class="small '
            'muted">' + esc(row["since"] or "") + "</td></tr>")
    if not rows:
        rows = ('<tr><td colspan="6">'
                + empty("Nobody is suppressed in this workspace",
                        "Replies, unsubscribes, dropped records and the "
                        "global do-not-contact list all appear here.")
                + "</td></tr>")

    counts = stats(
        [("total", data["total"])]
        + [(k, v, {"unsubscribe": "block", "global": "block",
                   "dropped": "warn", "reply": "pause"}.get(k, ""))
           for k, v in sorted(data["counts"].items())]
        + [("global list", data["global_count"])])

    return (
        "<h2>Suppression</h2>"
        '<p class="small muted">Who is stopped in this workspace, and what '
        "stopped them.</p>"
        + counts
        + '<p class="note">' + esc(data["note"]) + "</p>"
        + table(["Reason", "Company", "Domain", "Scope", "Why", "Since"],
                rows, "suppression", True))


# ------------------------------------------------------------------ search


def search(data):
    if data["why"]:
        return ("<h2>Search</h2>" + empty("Nothing searched", data["why"]))

    groups = {}
    for hit in data["results"]:
        groups.setdefault(hit["kind"], []).append(hit)

    body = ""
    for kind in ("workspace", "campaign", "company", "contact"):
        hits = groups.get(kind) or []
        if not hits:
            continue
        rows = ""
        for hit in hits:
            rows += (
                "<tr><td>" + link(hit["where"], hit["label"] or hit["id"])
                + "</td><td>" + esc(hit["detail"] or "")
                + '</td><td><span class="wsname">' + esc(hit["workspace"])
                + "</span></td></tr>")
        note = ("Showing the first " + str(len(hits)) + "; there are more."
                if data["truncated"].get(kind) else None)
        body += panel(
            kind.capitalize() + "s",
            table([kind.capitalize(), "", "Workspace"], rows)
            + ('<p class="small muted">' + esc(note) + "</p>" if note else ""))

    if not body:
        body = empty("No matches",
                     "Nothing in the workspaces you can enter matches "
                     + repr(data["query"]) + ".")

    return ("<h2>Search</h2>"
            '<p class="small muted">' + esc(len(data["results"]))
            + " match(es) across " + esc(len(data.get("workspaces") or []))
            + " workspace(s) you are a member of.</p>" + body)


# ---------------------------------------------------- account orchestration
#
# The three screens the outreach rebuild is about. The old `/outreach` was a
# flat list of contacts with their steps; it could not show that four humans
# are working three people at one company, which is the thing an operator most
# needs to see before approving anything.
#
# Account view  - one company, every decision maker, one timeline
# Contact view  - one person, their cadence, what may be claimed and why
# Cadence view  - the graph, with its branches visible


CHANNEL_DOT = {"email": "email", "linkedin": "linkedin"}

STATE_KIND = {
    "sent": "pass", "delivered": "pass", "replied": "pass",
    "positive_reply": "pass", "planned": "", "approved": "warn",
    "payload_ready": "warn", "paused": "pause", "held": "warn",
    "blocked": "block", "failed": "block", "skipped": "block",
    "active": "pass", "engaged": "pass", "not_started": "",
    "suppressed": "block", "referral": "info",
    # `cadence.status_for`'s vocabulary, which reaches `_state` through the
    # contact outreach page. `eligible` is deliberately not "pass": green
    # reads as done, and eligible means only that nothing refused it.
    "stopped": "block", "waiting": "", "unapproved": "warn", "eligible": "",
}


def _state(value):
    return tag(str(value or "").replace("_", " "),
               STATE_KIND.get(value, ""))


def _channel(value):
    if not value:
        return ""
    css = CHANNEL_DOT.get(value, "")
    return ('<span class="chan ' + css + '"></span>' + esc(value)) if css \
        else esc(value)


CHANNEL_NAME = {"email": "Email", "linkedin": "LinkedIn"}


def _channel_label(value):
    """The channel as a heading. `.title()` produces "Linkedin"."""
    return CHANNEL_NAME.get(value, (value or "").title())


def _channel_dot(value):
    """The colour chip alone, where the label already names the channel."""
    css = CHANNEL_DOT.get(value, "")
    return '<span class="chan ' + css + '"></span>' if css else ""


def account_list(rows, batch=None):
    """Every account, ordered by how alive it is."""
    body = ""
    for row in rows:
        team = " ".join(tag(t, "info") for t in row["team"][:4])
        channels = " ".join(_channel(c) for c in row["channels"])
        body += (
            "<tr><td>" + link("/outreach/account/" + str(row["record_id"]),
                              row["company"] or row["record_id"])
            + '<div class="small muted">' + esc(row["domain"] or "")
            + "</div></td><td>" + esc(row["decision_makers"]) + "</td><td>"
            + esc(row["contacted"]) + "</td><td>" + esc(row["touches"])
            + "</td><td>" + esc(row["engaged"]) + "</td><td>"
            + (tag(row["positive"], "pass") if row["positive"]
               else esc(0)) + "</td><td>"
            + (tag(row["referrals"], "info") if row["referrals"] else "")
            + "</td><td>" + channels + "</td><td>" + team + "</td><td>"
            + (tag("paused", "pause") if row["paused"] else "")
            + "</td></tr>")
    if not body:
        body = ('<tr><td colspan="10">'
                + empty("No accounts yet",
                        "Upload a batch and qualify it; accounts appear here "
                        "with every decision maker being worked.")
                + "</td></tr>")
    return table(["Account", "DMs", "Contacted", "Touches", "Engaged",
                  "Positive", "Referrals", "Channels", "Team", ""],
                 body, "accounts", True)


def account_view(data):
    """One company as an orchestration map. The flagship screen."""
    counts = data["counts"]
    head = stats([
        ("decision makers", counts["decision_makers"]),
        ("contacted", counts["contacted"], "pass" if counts["contacted"]
         else ""),
        ("confirmed touches", counts["touches"]),
        ("planned", counts["planned"], "warn" if counts["planned"] else ""),
        ("engaged", counts["engaged"], "pass" if counts["engaged"] else ""),
        ("positive", counts["positive"], "pass" if counts["positive"] else ""),
        ("referrals", counts["referrals"], "info" if counts["referrals"]
         else ""),
    ])

    banner = ""
    if data["paused"]:
        banner = ('<div class="banner">This account is paused: '
                  + esc((data["paused"] or {}).get("reason") or "")
                  + ". Any reply pauses every channel for every contact "
                    "here, not only the person who answered.</div>")

    pacing = data["account_fatigue"]
    if pacing["findings"]:
        rows = "".join('<li>' + tag(f["level"], "block" if f["level"] == "block"
                                    else "warn") + " " + esc(f["why"])
                       + "</li>" for f in pacing["findings"])
        banner += panel("Account pacing", "<ul class=\"tree\">" + rows
                        + "</ul>")

    # -- the people
    #
    # Four different facts about senders, kept apart. A single "Assigned"
    # line was the old one-sender-per-channel model showing through, and it
    # answered none of the questions an operator actually has: who is next,
    # who has this person already heard from, and who is even allowed here.
    people = ""
    for contact in data["contacts"]:
        senders = contact.get("senders") or {}
        assigned = []
        for channel in ("email", "linkedin"):
            entry = senders.get(channel) or {}
            if entry.get("sender_id"):
                assigned.append(
                    _channel(channel) + " "
                    + esc(entry.get("display_name") or entry["sender_id"])
                    + (' <span class="small muted">via '
                       + esc(entry["account_id"]) + "</span>"
                       if entry.get("account_id") else ""))
        touched = " ".join(tag(n, "info") for n in contact["sender_names"])
        referred = ""
        if contact.get("referred_by"):
            referred = ('<div class="small">' + tag("referred", "info")
                        + " by " + esc(contact["referred_by"]["from_contact"])
                        + "</div>")

        # Sentences, not claim types. The reasoning is one disclosure away.
        allowed = [c for c in contact["claims"] if c["allowed"] and
                   c.get("phrase")]
        claims = ""
        for claim in allowed:
            claims += ('<div class="xchan ok"><b>&ldquo;'
                       + esc(claim["phrase"]) + '&rdquo;</b>'
                       '<div class="small muted">' + esc(claim["why"])
                       + "</div></div>")
        if not claims:
            claims = ('<p class="small muted">Nothing may be referenced for '
                      "this contact yet. A message here stands on its own.")
            claims += "</p>"

        steps = ""
        for touch in contact["touches"]:
            steps += (
                '<li>' + _state(touch["state"]) + " "
                + (("day " + str(touch["day"])) if touch["day"] else "")
                + " " + _channel(touch["channel"]) + " &middot; "
                + esc(touch["sender_id"] or "no sender recorded")
                + '<span class="small muted"> ' + esc(touch["at"] or "")
                + "</span></li>")

        pacing_note = ""
        if contact["fatigue"]["findings"]:
            pacing_note = ('<div class="small muted">'
                           + esc("; ".join(f["why"] for f in
                                           contact["fatigue"]["findings"]))
                           + "</div>")

        people += panel(
            (contact["name"] or contact["key"]),
            kv([
                row("Role", esc(contact["title"] or "") + " &middot; "
                    + tag(contact["priority"], "info"), raw=True),
                row("State", _state(contact["state"]) + pacing_note, raw=True),
                row("Next sender", " &nbsp; ".join(assigned)
                    or unavailable("no sender assigned for either channel"),
                    raw=True),
                row("Has heard from", touched
                    or unavailable("nobody yet - nothing confirmed sent"),
                    raw=True),
                row("Referral", referred or unavailable("none recorded"),
                    raw=True),
            ])
            + ("<h4>Touches</h4><ul class=\"tree\">" + steps + "</ul>"
               if steps else
               '<p class="small muted">No touch recorded for this person.</p>')
            + "<h4>What a message here may say</h4>" + claims
            + '<p class="small muted">'
            + link("/outreach/contact/" + str(data["record_id"]) + "/"
                   + str(contact["key"]),
                   "Open " + (contact["name"] or contact["key"]))
            + "</p>")

    # -- the timeline
    feed = ""
    for entry in data["timeline"]:
        feed += (
            '<li class="' + ("confirmed" if entry["confirmed"] else "")
            + '"><span class="day">' + esc((entry["at"] or "")[:10])
            + "</span> " + _state(entry["state"]) + " "
            + _channel(entry["channel"]) + " " + esc(entry["summary"])
            + "</li>")
    timeline = ("<ul class=\"timeline\">" + feed + "</ul>" if feed
                else empty("Nothing has happened here yet",
                           "Touches, replies and referrals appear on this "
                           "timeline as they are recorded."))

    team = data["team"]
    team_block = unavailable("no outreach team is configured for this "
                             "campaign")
    if team:
        team_block = kv([
            row("Team", esc(team["name"]) + " (" + esc(team["scope"]) + ")",
                raw=True),
            row("Email", ", ".join(m["name"] for m in team["email"])
                or "none"),
            row("LinkedIn", ", ".join(m["name"] for m in team["linkedin"])
                or "none"),
        ])

    # -- account strategy: who is primary, who was activated and why
    strategy = ""
    for contact in sorted(data["contacts"],
                          key=lambda c: ("primary", "secondary", "tertiary",
                                         "referral").index(c["priority"])
                          if c["priority"] in ("primary", "secondary",
                                               "tertiary", "referral") else 9):
        because = []
        if contact.get("referred_by"):
            because.append("referred by "
                           + str(contact["referred_by"].get("from_name")
                                 or contact["referred_by"]["from_contact"]))
        if contact["positive"]:
            because.append("replied positively")
        elif contact["replies"]:
            because.append("replied")
        strategy += (
            "<tr><td>" + tag(contact["priority"], "info") + "</td><td>"
            + link("/outreach/contact/" + str(data["record_id"]) + "/"
                   + str(contact["key"]), contact["name"] or contact["key"])
            + '<div class="small muted">' + esc(contact["title"] or "")
            + "</div></td><td>" + _state(contact["state"]) + "</td><td>"
            + esc(len(contact["confirmed_touches"])) + "</td><td>"
            + '<span class="small muted">' + esc(", ".join(because))
            + "</span></td></tr>")

    return (
        "<h1>" + esc(data["company"] or data["record_id"]) + "</h1>"
        '<div class="crumb">' + esc(data["domain"] or "") + " &middot; "
        + link("/companies/" + str(data["record_id"]), "company dossier")
        + (" &middot; " + esc((data["campaign"] or {}).get("name") or "")
           if data["campaign"] else "") + "</div>"
        + banner + head
        + _priority_panel(data.get("priority"))
        + _playbook_panel(data.get("playbooks"))
        + _signal_form(data.get("signal_form"), data.get("csrf"),
                       data.get("signal_error"),
                       data.get("contacts") or [])
        + '<div class="grid2">'
        + panel("Account timeline", timeline)
        + panel("Outreach team", team_block
                + "<h4>Has actually touched this account</h4>"
                + kv([row(_channel_label(channel),
                          _channel_dot(channel) + esc(", ".join(names)),
                          raw=True)
                      for channel, names in
                      sorted((data["touched_by"] or {}).items())])
                if data["touched_by"] else team_block)
        + "</div>"
        + panel("Account strategy",
                table(["Priority", "Decision maker", "State", "Touches",
                       "Why"], strategy)
                + '<p class="small muted">Priority is campaign strategy. '
                  "A contact activated by a referral says so here rather "
                  "than only in the event log.</p>")
        + "<h2>Decision makers</h2>" + people)


def cadence_view(data):
    """The graph, with branches visible and nothing rendered as JSON."""
    if data is None:
        return empty("No cadence to show",
                     "Build a campaign, or pick a template.")

    summary = data["summary"]
    head = stats([
        ("nodes", summary["nodes"]),
        ("touches", summary["touches"]),
        ("branches", summary["branches"], "info" if summary["branches"]
         else ""),
        ("senders", len(summary["senders"])),
        ("channels", len(summary["channels"])),
        ("longest wait", str(summary["longest_wait"]) + "d"),
    ])

    problems = ""
    for finding in data["findings"]:
        problems += ('<li>' + tag(finding["level"],
                                  "block" if finding["level"] == "block"
                                  else "warn")
                     + " " + esc(finding["why"])
                     + (' <code>' + esc(finding["node"]) + "</code>"
                        if finding["node"] else "") + "</li>")
    problems = ("<ul class=\"tree\">" + problems + "</ul>" if problems
                else '<p class="note ok">Nothing structurally wrong with '
                     "this cadence.</p>")

    steps = _cadence_phases(data)
    picker = _cadence_picker(data)
    return (
        "<h2>Cadence</h2>"
        '<p class="small muted">'
        + ("This campaign's own cadence." if data["source"] == "campaign"
           else "A reusable shape, built from this workspace's senders. A "
                "template carries no client copy.")
        + "</p>" + picker + head
        + panel("Validation", problems)
        + steps)


def _cadence_phases(data):
    """One collapsible block per phase, the first one open.

    A long cadence is read phase by phase - "what happens after the
    connection request" is a question about a phase, not about node 14.
    """
    out = ""
    for index, group in enumerate(data.get("phases") or []):
        body = _cadence_steps(group["nodes"])
        summary = (esc(group["phase"] or "Steps")
                   + '  <span class="small muted">'
                   + esc(len(group["nodes"])) + " nodes &middot; "
                   + esc(group["touches"]) + " touches"
                   + (" &middot; " + esc(", ".join(group["senders"]))
                      if group["senders"] else "") + "</span>")
        out += section(group["phase"] or "Steps", body, open_=index == 0)
        # `section` escapes its title, so the counts go inside the body.
        out = out.replace("<div class=\"secbody\">" + body,
                          "<div class=\"secbody\">"
                          '<p class="small muted">' + esc(len(group["nodes"]))
                          + " nodes &middot; " + esc(group["touches"])
                          + " touches"
                          + (" &middot; " + esc(", ".join(group["senders"]))
                             if group["senders"] else "") + "</p>" + body, 1)
    return out or empty("No steps", "This cadence has no nodes.")


def _cadence_steps(nodes):
    steps = ""
    for node in nodes:
        kind = ("block" if not node["validated"]
                else "pass" if node["contacts"] else "")
        branches = ""
        for branch in node["branches"]:
            branches += ('<div class="small">' + tag(branch["on"],
                                                     "pass" if branch["on"]
                                                     == "yes" else "warn")
                         + " &rarr; " + esc(branch["target_label"]
                                            or branch["target"] or "end")
                         + "</div>")
        detail = []
        if node["day"]:
            detail.append("day " + str(node["day"]))
        if node["wait_days"]:
            detail.append(str(node["wait_days"]) + " days")
        if node["sender"]:
            detail.append("by " + str(node["sender"]))
        if node["role"]:
            detail.append("to the " + str(node["role"]) + " contact")
        if node["condition"]:
            detail.append("if " + str(node["condition_why"]
                                      or node["condition"]))

        steps += (
            '<div class="step ' + kind + ("" if not node["off_path"]
                                          else " warn") + '">'
            '<div class="stephead">'
            + ('<span class="day">' + esc(node["key"]) + "</span> ")
            + "<b>" + esc(node["label"]) + "</b> "
            + _channel(node["channel"])
            + (" " + tag("not on the default path", "warn")
               if node["off_path"] else "")
            + (" " + tag("provider capability unvalidated", "block")
               if not node["validated"] else "")
            + "</div>"
            + '<div class="small muted">' + esc(" &middot; ".join(detail))
            .replace("&amp;middot;", "&middot;") + "</div>"
            + branches + "</div>")

    return steps


def _cadence_picker(data):
    picker = ('<form method="get" action="/outreach/cadence" class="filters">'
              '<select name="template" data-autosubmit>')
    for template in data["templates"]:
        selected = " selected" if template["key"] == data["template"] else ""
        picker += ('<option value="' + attr(template["key"]) + '"' + selected
                   + ">" + esc(template["name"]) + "</option>")
    picker += "</select></form>"
    return picker


# --------------------------------------------------------- the report editor
#
# Three columns: which draft, the blocks a person writes, and the numbers they
# have to agree with. The numbers are rendered as text with no input beside
# them, because there is no field in a draft to put an edited one in - see
# `src/reportdraft.py`.


def report_editor(data, csrf):
    if data is None:
        return empty("No such draft",
                     "It may belong to another workspace.")

    picker = ('<form method="post" action="/reporting/editor/new" '
              'class="filters"><input type="hidden" name="csrf" value="'
              + attr(csrf) + '">')
    picker += "<select name=\"template\">"
    for template in data["templates"]:
        picker += ('<option value="' + attr(template["key"]) + '">'
                   + esc(template["label"]) + "</option>")
    picker += ("</select>"
               # Wide enough for its own placeholder. A field that truncates
               # the example it offers reads as broken before it is used.
               '<input type="text" name="period" size="24" '
               'placeholder="2026-07-01 to 2026-07-31" '
               'aria-label="Reporting period">'
               '<button type="submit">New draft</button></form>')

    listed = ""
    # `entry`, not `row` - `row()` is the key/value helper this function calls
    # a dozen lines further down, and shadowing it turned every later call
    # into "'dict' object is not callable".
    for entry in data["drafts"]:
        current = data["draft"] and entry["id"] == data["draft"]["id"]
        listed += (
            '<tr class="' + ("on" if current else "") + '"><td>'
            + link("/reporting/editor?draft=" + str(entry["id"]),
                   entry.get("narrative", {}).get("title") or entry["id"])
            + '<div class="small muted">' + esc(entry["template"])
            + " &middot; " + esc(entry["period"]) + "</div></td><td>"
            + tag("v" + str(entry.get("version") or 1), "info") + " "
            + tag(entry["status"],
                  "pass" if entry["status"] == "final" else "")
            + '</td><td class="small muted">' + esc(entry["updated_by"] or "")
            + "<br>" + esc((entry.get("updated_at") or "")[:16])
            + "</td></tr>")
    if not listed:
        listed = ('<tr><td colspan="3">'
                  + empty("No drafts yet",
                          "Create one above. A draft holds the words; the "
                          "numbers are counted every time it renders.")
                  + "</td></tr>")

    if data["draft"] is None:
        return ("<h2>Report editor</h2>" + picker
                + panel("Drafts", table(["Draft", "Version", "Updated"],
                                        listed)))

    draft = data["draft"]
    readonly = "" if data["can_edit"] else " disabled"

    blocks = ""
    for block in data["blocks"]:
        suggestion = ""
        if block["suggested"] and not block["edited"]:
            suggestion = ('<div class="note small">Suggested: '
                          + esc(block["suggested"]) + "</div>")
        blocks += (
            "<label><b>" + esc(block["label"]) + "</b>"
            + (" " + tag("edited", "pass") if block["edited"] else "")
            + '<div class="small muted">' + esc(block["why"]) + "</div>"
            + '<textarea name="n:' + attr(block["key"]) + '" rows="'
            + ("5" if block["key"] in ("summary", "takeaways", "learned")
               else "3") + '"' + readonly + ">"
            + esc(block["value"]) + "</textarea>" + suggestion + "</label>")

    sections = ""
    # `block`, not `section` - `section()` is the disclosure helper used a few
    # lines below. This is the second time a loop variable has shadowed a
    # helper in this file, so `test_no_page_shadows_a_helper` now fails the
    # build for it rather than leaving it to a 500.
    for block in data["sections"]:
        sections += (
            '<label class="check"><input type="checkbox" name="sections" '
            'value="' + attr(block["key"]) + '"'
            + (" checked" if block["on"] else "") + readonly + "> "
            + esc(block["label"]) + "</label>")

    recommendations = ""
    for kind in data["recommendation_kinds"]:
        existing = [r["text"] for r in data["recommendations"]
                    if r["kind"] == kind["key"]]
        recommendations += (
            "<label><b>" + esc(kind["label"]) + "</b>"
            '<textarea name="r:' + attr(kind["key"]) + '" rows="2"'
            + readonly + ">" + esc("\n".join(existing)) + "</textarea></label>")

    metrics = ""
    for label, value in data["metrics"]:
        metrics += row(label, _n_or_unknown(value), raw=True)

    versions = ""
    for past in data["versions"][:8]:
        versions += ("<li>" + tag("v" + str(past.get("version")), "info")
                     + " " + esc(past.get("updated_by") or "")
                     + '<span class="small muted"> '
                     + esc((past.get("updated_at") or "")[:16])
                     + "</span></li>")
    versions = ("<ul class=\"tree\">" + versions + "</ul>" if versions
                else '<p class="small muted">This is version 1.</p>')

    status = tag(draft["status"],
                 "pass" if draft["status"] == "final" else "")
    actions = ""
    if data["can_edit"]:
        actions = ('<button type="submit">Save as v'
                   + esc((draft.get("version") or 1) + 1) + "</button>")
    elif draft["status"] == "final":
        actions = ('<p class="small muted">This report is marked final. '
                   "Reopen it to make a new version.</p>")

    editor = (
        '<form method="post" action="/reporting/editor/save">'
        '<input type="hidden" name="csrf" value="' + attr(csrf) + '">'
        '<input type="hidden" name="draft" value="' + attr(draft["id"]) + '">'
        '<div class="stack">' + blocks + "</div>"
        + section("Sections", '<div class="checks">' + sections + "</div>",
                  open_=True)
        + section("Next month",
                  '<p class="small muted">Written by a person, and editable '
                  "until the report is final. One recommendation per line."
                  "</p><div class=\"stack\">" + recommendations + "</div>")
        + actions + "</form>")

    side = (
        panel("Counted", kv([row("Template", draft.get("template_label")
                                 or draft["template"]),
                             row("Period", draft["period"]),
                             row("Version", "v" + str(draft.get("version")
                                                      or 1)),
                             row("Status", status, raw=True)])
              + "<h4>Figures in this report</h4>" + kv([metrics])
              + '<p class="small muted">Read-only. These are recounted every '
                "time the report renders, so an edit above cannot change "
                "one.</p>")
        + panel("Versions", versions)
        + panel("Export",
                link("/reporting/editor/preview?draft=" + str(draft["id"]),
                     "Preview") + " &middot; "
                + link("/reporting/editor/export?draft=" + str(draft["id"]),
                       "Export PDF")
                + ('<form method="post" action="/reporting/editor/finalise">'
                   '<input type="hidden" name="csrf" value="' + attr(csrf)
                   + '"><input type="hidden" name="draft" value="'
                   + attr(draft["id"]) + '">'
                   '<button type="submit" class="ghost">'
                   + ("Reopen" if draft["status"] == "final"
                      else "Mark final") + "</button></form>"
                   if data["can_finalise"] else "")))

    return (
        "<h2>Report editor</h2>" + picker
        + '<div class="grid2">'
        + panel("Drafts", table(["Draft", "Version", "Updated"], listed))
        + side + "</div>"
        + panel("Narrative", editor))


def _n_or_unknown(value):
    if value is None:
        return unavailable("not tracked")
    try:
        return esc(f"{int(value):,}")
    except (TypeError, ValueError):
        return esc(value)


def report_preview(data, html):
    """The draft as the client will read it, before it becomes a PDF."""
    return ("<h2>Preview</h2>"
            '<p class="small muted">What the PDF will contain. Numbers are '
            "recounted for this render; the words are the draft's.</p>"
            + html)


# ------------------------------------------------------ contact orchestration
#
# The contact half of the pair. Leads with what a message may safely say and
# what happens next; the claim-by-claim reasoning is behind a disclosure,
# because "which of seven claim types resolved and why" is a debugging
# question and this screen is where somebody decides whether to send.


def _priority_panel(assessment):
    """Why this account, why now, and whether anything may go out.

    Two facts side by side on purpose. Priority says *worth attention*;
    eligibility says *may we send*. A screen that showed the first without
    the second would invite somebody to write to a suppressed account, so
    the two are rendered together and the second is never derived from the
    first.
    """
    if not assessment:
        return ""

    eligible = assessment["eligibility"]["eligible"]
    head = stats([
        ("priority", f"{assessment['score']:g}",
         {"high": "pass", "medium": "warn"}.get(assessment["tier"], "")),
        ("", assessment["tier_label"]),
        ("cold outreach",
         "eligible" if eligible else "not eligible",
         "pass" if eligible else "block"),
    ])

    # The working. A number nobody can decompose is an assertion.
    rows = ""
    for part in assessment["components"]:
        rows += (
            "<tr><td>" + esc(part["label"]) + "</td>"
            + "<td>" + esc(f"+{part['points']:.0f}") + "</td>"
            + '<td class="small muted">' + esc(part["why"]) + "</td></tr>")

    signals = ""
    for entry in assessment["signals"][:12]:
        signals += (
            "<tr><td><b>" + esc(entry["label"]) + "</b>"
            + '<div class="small muted">' + esc(entry["evidence"])
            + "</div></td>"
            + "<td>" + tag(entry["freshness"],
                           {"fresh": "pass", "ageing": "warn",
                            "stale": "", "permanent": "info"}.get(
                               entry["freshness"], ""))
            + "</td>"
            + '<td class="small muted">' + esc(entry["source_label"])
            + "</td></tr>")

    body = (head
            + '<p class="note">' + esc(assessment["why_now"]) + "</p>"
            + (('<p class="note stop">Not eligible for cold outreach: '
                + esc(assessment["eligibility"]["blocked"]) + ". A high "
                "priority does not override this.</p>")
               if not eligible else "")
            + (table(["Signal", "Freshness", "Source"], signals)
               if signals else
               '<p class="small muted">No signals recorded for this '
               "account yet.</p>")
            + section("How this priority was reached",
                      table(["Component", "Points", "Why"], rows)
                      + '<p class="small muted">Components are weighted per '
                        "workspace. Eligibility is not one of them: it is "
                        "reported beside the score and outranks it.</p>"))
    return panel("Why this account", body)


def _playbook_panel(found):
    """Which approach fits, why, and what it would still be guessing at.

    The conditions that did *not* hold are shown beside the ones that did,
    split into "we asked and the answer was no" and "we never established
    this". A recommendation whose weak points are hidden is one nobody can
    disagree with, which makes it an instruction.
    """
    if not found:
        return ""

    def conditions(row):
        out = ""
        for entry in row["met"]:
            out += ('<div class="small"><b>' + esc(entry["label"])
                    + ":</b> " + esc(entry["why"]) + "</div>")
        for entry in row["missed"]:
            out += ('<div class="small muted">' + esc(entry["label"])
                    + ": " + esc(entry["why"]) + "</div>")
        for entry in row["unknown"]:
            out += ('<div class="small muted">' + esc(entry["label"])
                    + ": " + esc(entry["why"]) + " (not asked)</div>")
        return out

    rows = ""
    for row in found["recommended"]:
        rows += (
            "<tr><td><b>" + esc(row["name"]) + "</b>"
            + '<div class="small muted">' + esc(row["when"]) + "</div>"
            + "</td><td>" + conditions(row) + "</td>"
            + '<td class="small">' + esc(row["lead_pain_words"] or "")
            + '<div class="muted">' + esc(row["cta"]) + "</div></td>"
            + '<td class="small muted">' + esc(row["cadence"])
            + "</td></tr>")

    fallback = found["fallback"]
    body = (
        '<p class="note">' + esc(found["why"]) + ".</p>"
        + (table(["Approach", "Why it fits", "Leads with", "Cadence"], rows)
           if rows else "")
        + section(
            "If none of those are used" if rows else "The segment approach",
            "<b>" + esc(fallback["name"]) + "</b>"
            + '<div class="small muted">' + esc(fallback["when"])
            + "</div><div class=\"small\">Leads with "
            + esc(fallback["lead_pain_words"] or "") + "; "
            + esc(fallback["cta"]) + ".</div>",
            open_=not rows)
        + '<p class="note">' + esc(found["note"]) + "</p>")
    return panel("How to approach this account", body)


def _signal_form(form, csrf, error=None, contacts=()):
    """Write down something observed. The field labels carry the rule.

    "What did you see" rather than "evidence", because the second reads as
    a box to fill and the first asks a question. The placeholder is a real
    example for the same reason: the difference between a signal and a
    rumour is whether it can be quoted back, and one quotable sentence
    teaches that faster than a paragraph explaining it.

    Engagement types are not offered, and their absence is stated. A person
    who came here to record "they replied" should be told where that
    actually lives rather than left hunting for it.
    """
    if not form:
        return ""
    if not form["may_record"]:
        return panel(
            "Record a signal",
            '<p class="note">Your role can read the signals on this account '
            "but not add one.</p>")

    options = ""
    scope_now = None
    for entry in form["types"]:
        if entry["scope"] != scope_now:
            if scope_now is not None:
                options += "</optgroup>"
            scope_now = entry["scope"]
            options += ('<optgroup label="'
                        + attr("About the company" if scope_now == "account"
                               else "About a person") + '">')
        options += ('<option value="' + attr(entry["type"]) + '">'
                    + esc(entry["label"]) + "</option>")
    if scope_now is not None:
        options += "</optgroup>"

    people = '<option value="">The company as a whole</option>'
    for contact in contacts:
        people += ('<option value="' + attr(contact["key"]) + '">'
                   + esc(contact["name"] or contact["key"]) + "</option>")

    confidence = ""
    for level in form["confidence"]:
        confidence += ('<option value="' + attr(level) + '"'
                       + (" selected" if level == "medium" else "") + ">"
                       + esc(level) + "</option>")

    body = (
        (('<p class="note stop">' + esc(error) + "</p>") if error else "")
        + '<form method="post" action="/signals" class="stack">'
        + '<input type="hidden" name="csrf" value="' + attr(csrf) + '">'
        + '<input type="hidden" name="record_id" value="'
        + attr(form["record_id"]) + '">'
        + "<label>What kind of signal"
        + '<select name="type" required>' + options + "</select></label>"
        + "<label>What did you see"
        + '<textarea name="evidence" rows="2" maxlength="400" required'
        + ' minlength="' + attr(form["minimum_evidence"]) + '"'
        + ' placeholder="7 open delivery roles listed on the careers page">'
        + "</textarea></label>"
        + "<label>About"
        + '<select name="contact_key">' + people + "</select></label>"
        + "<label>When it happened"
        + '<input type="date" name="observed_at"></label>'
        + "<label>How sure are you"
        + '<select name="confidence">' + confidence + "</select></label>"
        + "<label>Where you saw it (optional)"
        + '<input name="source_ref" maxlength="300"'
        + ' placeholder="link or source"></label>'
        + '<button class="btn primary" type="submit">Record signal</button>'
        + '<p class="note">Recorded as observed by you, and every screen '
        "will say so. A signal raises the priority of this account. It does "
        "not permit anything to be sent, and it is not permission to put "
        "the observation in an email - that stays with the claim rules.</p>"
        + '<p class="small muted">Replies, referrals and meetings are not in '
        "this list. Those are read from the event log as they happen, and a "
        "handwritten copy would be the one that goes stale.</p>"
        + "</form>")
    # Folded away unless something went wrong. This screen exists to show
    # an account; entering a signal is an occasional act, and a form
    # standing permanently open between the priority and the timeline
    # takes a screen's worth of room to say "you could type here". An
    # error reopens it, because a refusal nobody can see is a refusal
    # that looks like nothing happening.
    return panel("Record a signal",
                 section("Write down something you observed", body,
                         open_=bool(error)))


def _engagement_panel(engagement):
    """Where this person stands, and whether anything may go out to them.

    The second question is the one an operator actually needs and the one
    easiest to get wrong by reading the first: "replied positively" and "may
    be contacted" are different facts, and a screen showing only the first
    invites somebody to assume the second.
    """
    if not engagement:
        return ""

    eligible = engagement["cold_eligible"]
    rows = [
        row("Engagement", engagement["outcome_label"] or "None recorded"),
        row("Cold outreach",
            tag("eligible", "pass") if eligible
            else tag("not eligible", "block"), raw=True),
    ]
    if not eligible and engagement.get("blocked_why"):
        rows.append(row("Because", engagement["blocked_why"]))
    if engagement.get("last_reply_at"):
        rows.append(row("Last reply", engagement["last_reply_at"][:10]))
    if engagement.get("active_conversation"):
        rows.append(row("Conversation", tag("in progress", "warn"), raw=True))

    provider_rows = ""
    for provider, state in sorted((engagement.get("provider_sync")
                                   or {}).items()):
        if state is None:
            body = unavailable("nothing queued")
        elif state["status"] == "blocked":
            body = unavailable(state["why"] or "no authoritative identity")
        else:
            body = (tag(state["status"],
                        {"sent": "pass", "failed": "block",
                         "pending": "warn"}.get(state["status"], ""))
                    + ' <span class="small muted">'
                    + esc(state["stage"]) + "</span>")
        provider_rows += row(provider, body, raw=True)

    body = kv(rows)
    if provider_rows:
        body += ("<h4>Provider tags</h4>" + kv([provider_rows])
                 + '<p class="small muted">What the providers should be told. '
                   "Resonate is authoritative; a tag is a copy, and no tag "
                   "endpoint has been validated against a live contract "
                   "yet.</p>")
    return panel("Engagement", body)


def _safe_context(context, suggested, heading="What this message may say"):
    """The operator-facing view of the claim engine.

    Sentences and their evidence. No claim types, no policy keys - those are
    in the diagnostics block, which is the same data asked a different way.
    """
    if not suggested:
        body = empty("Nothing may be referenced yet",
                     "No confirmed touch, reply or referral supports a "
                     "reference. The message stands on its own, which is "
                     "the safe default.")
    else:
        body = ""
        for item in suggested:
            body += (
                '<div class="xchan ok"><b>&ldquo;' + esc(item["say"])
                + '&rdquo;</b><div class="small muted">' + esc(item["because"])
                + "</div></div>")
        body += ('<p class="small muted">' + tag("suggested", "info")
                 + " Context a message may draw on, built from recorded "
                 "events. Not approved copy.</p>")

    facts = ""
    for item in context.get("account_activity") or []:
        facts += (
            "<li>" + _channel(item["channel"]) + " "
            + esc(item["sender"] or "unknown sender") + " &rarr; "
            + esc(item["contact"]) + '<span class="small muted"> '
            + esc((item["at"] or "")[:10]) + "</span>"
            + (" " + tag("replied", "pass") if item["replied"] else "")
            + (" " + tag("positive", "pass") if item["positive"] else "")
            + "</li>")
    if facts:
        body += ("<h4>Elsewhere at this account</h4><ul class=\"tree\">"
                 + facts + "</ul>"
                 '<p class="small muted">Facts, whether or not a message '
                 "mentions them.</p>")
    return panel(heading, body)


def _claim_diagnostics(claims):
    """Every claim type, allowed or refused, with its reason.

    Deliberately behind a disclosure. It is the right screen for somebody
    asking why a reference is unavailable and the wrong one for somebody
    approving a message.
    """
    body = ""
    for claim in claims:
        body += (
            "<tr><td>" + (tag("allowed", "pass") if claim["allowed"]
                          else tag("refused", "block"))
            + "</td><td><b>" + esc(claim["label"]) + "</b>"
            + '<div class="small muted"><i>'
            + esc(claim["phrase"] or claim["template"]) + "</i></div>"
            + "</td><td>" + esc(claim["why"]) + "</td><td>"
            + '<span class="small muted">' + esc(claim["minimum"])
            + "</span></td></tr>")
    return section("Claim diagnostics",
                   table(["", "Claim", "Reason", "Needs"], body)
                   + '<p class="small muted">Every claim type this system '
                     "knows, whether it resolves for this contact, and what "
                     "it would take. A refused claim shows the shape of the "
                     "sentence with roles rather than names, because there "
                     "is nobody to name.</p>")


def _fatigue_band(verdict):
    """Safe / near limit / blocked, so nobody has to do the arithmetic."""
    state = verdict.get("state")
    label, kind = {"ok": ("Safe", "pass"), "warn": ("Near limit", "warn"),
                   "block": ("Blocked", "block")}.get(state, (state, ""))
    body = tag(label, kind)
    findings = verdict.get("findings") or []
    if findings:
        body += "<ul class=\"tree\">"
        for finding in findings:
            body += ("<li>" + tag(finding["level"],
                                  "block" if finding["level"] == "block"
                                  else "warn")
                     + " " + esc(finding["why"]) + "</li>")
        body += "</ul>"
    else:
        body += ('<div class="small muted">Within every configured limit.'
                 "</div>")
    return body


def contact_outreach(data):
    """One decision maker, and what the next message may say."""
    head = kv([
        row("Role", esc(data["title"] or "") + " &middot; "
            + tag(data["priority"], "info"), raw=True),
        row("Company", link("/outreach/account/" + str(data["record_id"]),
                            data["company"] or data["record_id"]), raw=True),
        row("State", _state(data["state"]), raw=True),
        row("Campaign", esc((data["campaign"] or {}).get("name") or "")
            or unavailable("not in a campaign"), raw=True),
    ])

    # Four sender facts, never one "assigned" line.
    email = data["next_sender"]["email"] or {}
    linkedin = data["next_sender"]["linkedin"] or {}
    next_up = ""
    for channel, entry in (("email", email), ("linkedin", linkedin)):
        if entry.get("sender_id"):
            next_up += (
                "<li>" + _channel(channel) + " <b>"
                + esc(entry.get("display_name") or entry["sender_id"])
                + "</b>"
                + ('<span class="small muted"> via '
                   + esc(entry.get("account_id") or "") + "</span>"
                   if entry.get("account_id") else "")
                + "</li>")
    senders_block = kv([
        row("Next sender", ("<ul class=\"tree\">" + next_up + "</ul>")
            if next_up else unavailable("no sender assigned"), raw=True),
        row("Has heard from",
            " ".join(tag(n, "info") for n in data["heard_from"])
            or unavailable("nobody yet - nothing confirmed sent"), raw=True),
        row("Outreach team", esc((data["team"] or {}).get("name") or "")
            or unavailable("no team configured"), raw=True),
    ])

    # What happened, and what is planned, kept apart on purpose.
    history = ""
    for item in data["history"]:
        history += (
            '<li class="confirmed"><span class="day">'
            + esc((item.get("at") or "")[:10]) + "</span> "
            + _state(item.get("state")) + " " + _channel(item.get("channel"))
            + " " + esc(item.get("sender") or item.get("sender_id") or "")
            + (' <span class="small muted">via '
               + esc(item.get("account_id") or "") + "</span>"
               if item.get("account_id") else "") + "</li>")
    for reply in data["replies"]:
        history += (
            '<li class="confirmed"><span class="day">'
            + esc((reply.get("at") or "")[:10]) + "</span> "
            + _state("positive_reply" if reply.get("positive") else "replied")
            + " " + esc(data["contact"]) + " replied</li>")
    history = ("<ul class=\"timeline\">" + history + "</ul>" if history
               else empty("Nothing confirmed sent yet",
                          "Confirmed touches and replies appear here."))

    planned = ""
    for step in data["planned"]:
        planned += (
            '<div class="step ' + ("block" if step.get("would_send") is False
                                   else "") + '">'
            '<div class="stephead"><span class="day">day '
            + esc(step.get("day") or "?") + "</span> "
            + _channel(step.get("channel")) + " "
            + esc(step.get("sender") or "no sender") + " "
            + _state(step.get("state") or "planned") + "</div>"
            + ('<div class="small muted">' + esc(step.get("why") or "")
               + "</div>" if step.get("why") else "")
            + ("<pre class=\"copy\">" + esc(step.get("copy") or "")
               + "</pre>" if step.get("copy") else "")
            + "</div>")
    planned = planned or empty("No cadence planned",
                               "Build a campaign to plan one.")

    others = ""
    for other in data["account"]["contacts"]:
        if other["key"] == data["contact_key"]:
            continue
        others += (
            "<li>" + link("/outreach/contact/" + str(data["record_id"]) + "/"
                          + str(other["key"]), other["name"] or other["key"])
            + '<span class="small muted"> ' + esc(other["title"] or "")
            + "</span> " + _state(other["state"])
            + (" " + tag("positive", "pass") if other["positive"] else "")
            + "</li>")

    return (
        "<h1>" + esc(data["contact"]) + "</h1>"
        '<div class="crumb">'
        + link("/outreach/account/" + str(data["record_id"]),
               data["company"] or "account")
        + " &middot; " + esc(data["title"] or "") + "</div>"
        + '<div class="grid2">' + panel("Contact", head)
        + panel("Senders", senders_block) + "</div>"
        + _safe_context(data["context"], data["suggested"])
        + '<div class="grid2">'
        + panel("What happened", history)
        + panel("Pacing", _fatigue_band(data["fatigue"])
                + ("<h4>Others at this account</h4><ul class=\"tree\">"
                   + others + "</ul>" if others else ""))
        + "</div>"
        + panel("Planned cadence",
                '<p class="small muted">Planned, not sent. Nothing here is '
                "evidence for anything a message may claim.</p>" + planned)
        + _claim_diagnostics(data["context"]["claims"]))


# ------------------------------------------------ reply, in account context


def _referred_panel(data, csrf):
    """Who this reply pointed at, and whether they can be added.

    The verdict beside each one is context rather than an objection. A
    referral almost always comes from somebody who has replied, so "this
    account has engaged before" is the normal case here and saying it as a
    warning would train an operator to ignore the row that matters.
    """
    rows = ""
    for entry in data.get("referred") or []:
        who = entry.get("named") or entry.get("email") or "somebody"
        # EVERY IDENTIFIER THE REPLY CARRIED, which is one or several and
        # never a choice between them. This used to read `email or linkedin`,
        # so a row with both showed the address and silently hid the profile -
        # and a reply naming two people could put one person's mailbox and
        # another's profile on one contact with nothing on screen to reveal
        # it. `promotable` now refuses to pair them, which leaves a promotable
        # row with exactly one identifier and puts all the others here, on the
        # refused row - where `email` and `linkedin` are both None by
        # construction. Without them the operator reads "this reply names more
        # than one person" beside a blank cell and has nowhere to go: this
        # page does not render the reply body. Listing them is not pairing
        # them; they are shown as what was said, for a person to resolve.
        listed = entry.get("candidates") or {}
        several = (listed.get("emails") or []) + (listed.get("profiles") or [])
        identifier = (", ".join(several) if several
                      else entry.get("email") or entry.get("linkedin") or "")
        if entry["promotable"] and csrf:
            action = (
                '<form method="post" action="/replies/referral/add">'
                f'<input type="hidden" name="csrf" value="{attr(csrf)}">'
                f'<input type="hidden" name="record_id" '
                f'value="{attr(data["record_id"])}">'
                f'<input type="hidden" name="contact_key" '
                f'value="{attr(data["contact_key"])}">'
                f'<input type="hidden" name="event_id" '
                f'value="{attr(entry["event_id"])}">'
                "<button class=\"btn\">Add to this account</button></form>")
        else:
            action = f'<span class="small muted">{esc(entry["why"])}</span>'
        note = ""
        if entry.get("hygiene") and entry["hygiene"]["action"] != "eligible":
            note = ('<div class="small muted">Already known here: '
                    + esc(entry["hygiene"]["label"]) + "</div>")
        rows += ("<tr><td><b>" + esc(who) + "</b>"
                 + f'<div class="small muted">{esc(identifier)}</div>' + note
                 + "</td><td>" + esc(entry.get("status") or "") + "</td><td>"
                 + action + "</td></tr>")
    if not rows:
        return ""
    return panel(
        "Who they pointed us at",
        table(["Person", "What we could prove", ""], rows)
        + '<p class="note">Adding somebody is not contacting them. They '
        "arrive unverified and unselected, and every check an imported "
        "contact passes is still in front of them. A name with no address "
        "is not an identity and cannot be added at all.</p>")


def reply_context(data, csrf=None):
    """What arrived, and what it means for everybody else at that company."""
    effect = data["effect"]
    decision = effect["decision"]

    head = kv([
        row("Contact", esc(data["contact"] or "") + " &middot; "
            + esc(data["title"] or ""), raw=True),
        row("Company", link("/outreach/account/" + str(data["record_id"]),
                            data["company"] or data["record_id"]), raw=True),
        row("Campaign", esc((data["campaign"] or {}).get("name") or "")
            or unavailable("not in a campaign"), raw=True),
        row("Channel", _channel(data["channel"]), raw=True),
        row("Sender", esc(data["sender"] or "")
            or unavailable("no sender recorded"), raw=True),
        row("Outcome", tag(data["outcome_label"],
                           "pass" if data["positive"] else ""), raw=True),
    ])

    people = ""
    for entry in effect["contacts"]:
        people += (
            "<tr><td>" + link("/outreach/contact/" + str(data["record_id"])
                              + "/" + str(entry["contact_key"]),
                              entry["contact"] or entry["contact_key"])
            + (" " + tag("replied", "pass") if entry["replier"] else "")
            + "</td><td>" + _state(entry["state"]) + "</td><td>"
            + tag(entry["action"],
                  {"stop": "block", "hold": "warn", "review": "warn",
                   "continue": "pass"}.get(entry["action"], ""))
            + '</td><td class="small muted">' + esc(entry["why"])
            + "</td><td>" + (esc(entry["planned"]) + " planned"
                             if entry["planned"] else "") + "</td></tr>")

    return (
        "<h1>" + esc(data["contact"] or "Reply") + "</h1>"
        '<div class="crumb">' + esc(data["company"] or "") + "</div>"
        + '<div class="grid2">' + panel("The reply", head)
        + panel("What this does",
                "<p><b>" + esc(decision["why"]) + "</b></p>"
                + '<p class="small muted">Scope: ' + esc(decision["scope"])
                + ". "
                + ("Configured for this workspace."
                   if decision["configured"]
                   else "Using the safe default; nobody has configured it.")
                + "</p>"
                + '<p class="note stop">' + esc(effect["current_behaviour"])
                + "</p>")
        + "</div>"
        + _referred_panel(data, csrf)
        + panel("Everybody at this account",
                table(["Decision maker", "State", "Action", "Why", ""],
                      people)))


def reply_policies(data):
    """The eight policies, what each defaults to, and why."""
    body = ""
    for entry in data["policies"]:
        body += (
            "<tr><td><b>" + esc(entry["title"]) + "</b>"
            '<div class="small muted">' + esc(entry["why"]) + "</div>"
            "</td><td>" + tag(entry["scope"], "info") + "</td><td>"
            + tag(entry["action"],
                  {"stop": "block", "hold": "warn", "review": "warn",
                   "continue": "pass"}.get(entry["action"], ""))
            + "</td><td>"
            + (tag("configured", "pass") if entry["configured"]
               else '<span class="small muted">default</span>')
            + "</td></tr>")
    return (
        "<h2>Reply policy</h2>"
        '<p class="small muted">What a reply from one decision maker does to '
        "the others at the same company. The defaults lean towards holding: "
        "a hold somebody lifts costs a day, and a message sent into a "
        "conversation that had already started cannot be recalled.</p>"
        + '<p class="note">' + esc(data["current_behaviour"]) + "</p>"
        + table(["When", "Scope", "Action", "Set by"], body)
        + panel("What each reply does", _reply_effects(data)))


def _reply_effects(data):
    """The consequence of every outcome, resolved through the policies above.

    Worth a table of its own: a reader looking at "hold / account" has to
    do two translations before they know whether Sarah gets her Thursday
    email. This says so.
    """
    labels = data.get("effect_label") or {}
    body = ""
    for row_ in data.get("outcomes") or []:
        extra = []
        if row_.get("review"):
            extra.append("a person must look")
        if row_.get("activate_referred"):
            extra.append("the referred contact is activated")
        body += (
            "<tr><td><b>" + esc(row_["label"]) + "</b>"
            + ('<div class="small muted">' + esc(", ".join(extra)) + "</div>"
               if extra else "")
            + "</td><td>" + esc(labels.get(row_["replier"], row_["replier"]))
            + "</td><td>" + esc(labels.get(row_["account"], row_["account"]))
            + "</td></tr>")
    return (table(["Outcome", "The person who replied",
                   "Everybody else there"], body)
            + '<p class="small muted">Somebody who answered is never left to '
              "carry on, whatever they said - the mildest thing that can "
              "happen to them is that their own sequence ends. Only an "
              "explicit removal request suppresses anybody permanently.</p>")


def campaign_plan_qa(data):
    """Plan-level QA, grouped so a reviewer knows what to do about each."""
    if data is None:
        return empty("No such campaign", "")

    state = data["state"]
    head = stats([
        ("state", state, {"block": "block", "warn": "warn",
                          "ok": "pass"}.get(state, "")),
        ("blocking", len(data["blocking"]),
         "block" if data["blocking"] else "pass"),
        ("findings", len(data["findings"])),
        ("companies", data["records"]),
        ("cadence nodes", (data["graph"] or {}).get("nodes", 0)),
        ("outreach team", (data["team"] or {}).get("size", 0)),
    ])

    groups = ""
    for group in ("structure", "safety", "pacing", "claims"):
        rows = data["by_group"].get(group) or []
        if not rows:
            continue
        body = ""
        for finding in rows:
            body += (
                "<tr><td>" + tag(finding["level"],
                                 "block" if finding["level"] == "block"
                                 else "warn")
                + "</td><td>" + esc(finding["why"])
                + ('<div class="small muted">' + esc(finding["fix"]) + "</div>"
                   if finding["fix"] else "")
                # An empty <code> renders as a small grey box, which reads as
                # a rendering fault rather than as "this finding is about the
                # plan, not about one step".
                + "</td><td>"
                + ("<code>" + esc(finding["where"]) + "</code>"
                   if finding["where"] else "")
                + "</td></tr>")
        groups += panel(_QA_GROUP_LABEL.get(group, group),
                        table(["", "Finding", "Step"], body))

    if not groups:
        groups = panel("Nothing to raise",
                       '<p class="note ok">This plan has no structural, '
                       "safety, pacing or claim problems.</p>")

    return ("<h2>Plan review</h2>"
            '<p class="small muted">The cadence, the senders, the decision '
            "makers, the pacing and what messages may claim. Draft-level "
            "lint is separate and unchanged.</p>" + head + groups)


_QA_GROUP_LABEL = {
    "structure": "Cadence structure",
    "safety": "Outreach safety",
    "pacing": "Contact and account pacing",
    "claims": "What messages may claim",
}


def campaign_experiments(data):
    """Copy experiments, one panel per message step.

    The header on each panel is the *state*, not the leader, because the
    honest answer is usually "not yet" and a screen that led with a winner
    would be teaching people to read noise as a result.
    """
    if data is None:
        return empty("No such campaign", "")
    if data.get("no_cadence_graph"):
        # Distinct from "no message steps": one is a cadence that carries no
        # copy, the other is no cadence at all. Collapsing them would tell an
        # operator their experiment found nothing when it was never asked.
        return ("<h2>Copy experiments</h2>"
                + empty("No cadence graph on this campaign",
                        "Copy experiments are evaluated against a campaign's "
                        "own cadence graph, and this campaign has none. "
                        "Nothing writes one yet - see PRODUCT-GAPS.md. Run "
                        "the application with --demo to see the screen "
                        "against a fictional estate."))
    if not data["steps"]:
        return ("<h2>Copy experiments</h2>"
                + empty("No message steps",
                        "This cadence has no step that carries copy."))

    note = ""
    if data.get("planted"):
        note = ('<p class="note">This campaign has no cadence of its own, so '
                "the demo cadence is shown. Its totals are fictional. Every "
                "verdict, threshold and traffic share below is computed from "
                "them by the same code a real campaign uses.</p>")

    panels = ""
    for step in data["steps"]:
        rows = ""
        for entry in step["variants"]:
            result = entry.get("result") or {}
            exposures = result.get("exposures") or 0
            outcomes = result.get("outcomes") or 0
            leading = entry["variant_id"] == step.get("leader")
            rows += (
                "<tr><td><b>" + esc(entry.get("style_name")
                                    or entry.get("style") or "") + "</b>"
                + (" " + tag("leading", "pass") if leading else "")
                + '<div class="small muted">'
                + esc(entry.get("style_label") or "") + "</div></td>"
                + "<td>" + esc(f"{(entry.get('share') or 0) * 100:.0f}%")
                + "</td>"
                + "<td>" + esc(exposures) + "</td>"
                + "<td>" + esc(outcomes) + "</td>"
                # Always the pair. A percentage on its own is a sentence
                # somebody has to trust rather than one they can check.
                #
                # And below the experiment's own minimum, no percentage at
                # all: "0.0%" from three sends is a number two variants can
                # be compared on when the difference between them is noise.
                # The evaluator already refuses to call a winner at this
                # volume; the screen should not quietly offer one.
                + "<td>" + (unavailable("nothing sent yet")
                            if result.get("rate") is None
                            else (esc(f"{result['rate'] * 100:.1f}%")
                                  + ' <span class="small muted">'
                                  + esc(f"{outcomes}/{exposures}")
                                  + "</span>")
                            if exposures >= data.get("minimum_per_variant", 0)
                            else ('<span class="small muted">'
                                  + esc(f"{outcomes}/{exposures}")
                                  + ", too few to rate</span>"))
                + "</td></tr>")

        head = stats([
            ("state", step["state_label"],
             _EXPERIMENT_KIND.get(step["state"], "")),
            ("variants", len(step["variants"])),
            ("progress", (f"{step['progress']:.0%}"
                          if step.get("progress") is not None else "n/a")),
            ("optimising for", step["objective_label"]),
        ])
        channel = step["channel"] or ""
        title = step["label"]
        if channel and channel.lower() not in title.lower():
            title += " · " + channel
        if step.get("day"):
            title += f" · day {step['day']}"
        panels += panel(
            title,
            head
            + '<p class="small muted">' + esc(step["verdict"]["why"]) + "</p>"
            + table(["Style", "Traffic", "Sent", step["objective_label"],
                     "Rate"], rows)
            + ('<p class="note">Traffic has been shifted toward the winner. '
               "The other variants keep a share, because a variant that "
               "stops being served stops being measured.</p>"
               if step.get("shifted") else ""))

    return ("<h2>Copy experiments</h2>"
            '<p class="small muted">One experiment per message step. A '
            "winner on day 1 says nothing about day 6, so each is evaluated "
            "on its own.</p>"
            + note + panels
            + '<p class="note">Outcomes are credited to the last confirmed '
              "touch before them. That is a reporting convention, not a "
              "claim about cause: a contact who saw three variants is "
              "counted once, against the last one they were sent.</p>")


_EXPERIMENT_KIND = {
    "winner": "pass", "leading": "warn", "exploring": "",
    "insufficient_data": "", "no_clear_winner": "", "paused": "pause",
    "completed": "pass",
}


def signal_dashboard(data):
    """Which accounts are worth attention, why, and which may be worked.

    Sorted by priority, and every row says whether outreach is allowed -
    because the two most useful facts here are "this one matters" and
    "this one is suppressed", and a list showing only the first is a list
    somebody works down without checking.
    """
    if not data["total"]:
        return ("<h2>Account intelligence</h2>"
                + empty("No accounts yet",
                        "Import a batch, and this becomes the list of who "
                        "is worth attention and why."))

    head = stats([
        ("accounts", data["counts"]["accounts"]),
        ("with signals", data["counts"]["with_signals"]),
        ("fresh signals", data["counts"]["with_fresh"],
         "pass" if data["counts"]["with_fresh"] else ""),
        ("not eligible", data["counts"]["not_eligible"],
         "block" if data["counts"]["not_eligible"] else ""),
    ])

    # The same tab idiom the senders screen uses: `link()` renders a plain
    # anchor, so a styled one is written out here rather than by widening
    # the helper for one caller.
    on = "" if data["filtered"] else " primary"
    filters = ('<div class="filters">'
               f'<a class="btn{on}" href="/signals">All tiers</a>')
    for entry in data["tiers"]:
        on = " primary" if data["tier"] == entry["key"] else ""
        filters += (f'<a class="btn{on}" '
                    f'href="/signals?tier={attr(entry["key"])}">'
                    + esc(entry["label"]) + " ("
                    + esc(entry["count"]) + ")</a>")
    filters += "</div>"

    rows = ""
    for row in data["accounts"]:
        rows += (
            "<tr><td>"
            + link("/outreach/account/" + str(row["record_id"]),
                   row["company"] or row["record_id"])
            + '<div class="small muted">' + esc(row["domain"] or "")
            + "</div></td>"
            + "<td><b>" + esc(row["score"]) + "</b> "
            + tag(row["tier_label"],
                  {"high": "pass", "medium": "warn"}.get(row["tier"], ""))
            + "</td>"
            + '<td class="small">' + esc(row["why_now"]) + "</td>"
            + "<td>" + (esc(row["fresh"]) if row["fresh"]
                        else '<span class="small muted">none</span>')
            + "</td>"
            + "<td>" + (tag("eligible", "pass") if row["eligible"]
                        else tag("not eligible", "block")
                        + '<div class="small muted">'
                        + esc(row["blocked"] or "") + "</div>")
            + "</td></tr>")

    types = "".join(
        "<tr><td>" + esc(entry["label"]) + "</td><td>" + esc(entry["count"])
        + "</td><td>" + esc(entry["accounts"]) + "</td></tr>"
        for entry in data["signal_types"])

    more = ""
    if data["shown"] < data["total"] and not data["filtered"]:
        more = ('<p class="small muted">Showing the top '
                + esc(data["shown"]) + " of " + esc(data["total"])
                + " accounts by priority.</p>")

    return ("<h2>Account intelligence</h2>"
            '<p class="small muted">Which accounts are worth attention, and '
            "why. A high priority is not permission to write: every row says "
            "separately whether outreach is allowed.</p>"
            + head + filters
            + table(["Account", "Priority", "Why now", "Fresh signals",
                     "Cold outreach"], rows)
            + more
            + panel("Live signals by type",
                    table(["Signal", "Observations", "Accounts"], types)
                    if types else
                    '<p class="small muted">Nothing is being observed yet. '
                    "First-party signals appear as touches and replies are "
                    "recorded; no external source is connected.</p>"))
