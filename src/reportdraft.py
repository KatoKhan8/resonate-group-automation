#!/usr/bin/env python3
"""Report drafts: the words a person writes, kept apart from the numbers.

## Why "generate PDF" was the wrong product

The previous flow was one button: press it, get an immutable PDF. That is a
report *generator*, and a client report is not a generated artefact. It is a
document somebody writes, using numbers the system counted.

The flow is now:

    CREATE  →  GENERATE DRAFT  →  EDIT  →  PREVIEW  →  EXPORT

## The one guarantee this module exists to make

**A draft stores narrative. It never stores a metric.**

There is no field here for a funnel count, a reply rate or a contact total.
Not "they are not stored by convention" - there is nowhere to put one. Every
number is recomputed from `src/report.py` at render time, through the same
functions the dashboards read.

That is what makes "manual edits cannot rewrite canonical metrics" a
structural property rather than a rule somebody has to remember. An editor
that could type over a number would eventually be used to, and the resulting
document would look exactly like every other report this system produces.

What a person may edit: the title, the summary, the takeaways, the
observations, the recommendations, which sections appear, what order they
appear in, and any custom notes. All of it is prose.

## Versions, not overwrites

Editing creates a new version. `v1`, `v2`, ... and one may be marked final.
A client report is a thing that was sent; "what did we tell them in July"
must be answerable, and an editor that overwrote its own history could not
answer it.

Versions are append-only. `edit()` appends; nothing rewrites a stored version.

## Client-safe by construction

Custom sections hold text, and `render_text` escapes. There is no HTML
passthrough, no template language and no way to inject markup into a client
document - see `src/web/pages.py` for the same discipline on screen.
"""
import os
import uuid

from . import clientreport, store

ENV = "REPORT_DRAFTS"

DRAFT = "draft"
FINAL = "final"
STATUSES = (DRAFT, FINAL)

# Every narrative block a person may write, and what it is for. These are the
# only editable fields; everything else in a report is counted.
NARRATIVE = (
    ("title", "Report title",
     "Defaults to the workspace and period. Change it for a client who calls "
     "it something else."),
    ("summary", "Executive summary",
     "Two or three sentences a busy reader will actually read. Generated "
     "from counted facts; edit it to say what mattered."),
    ("takeaways", "Key takeaways",
     "One line each. Drawn from deterministic observations - edit, reorder "
     "or remove them."),
    ("what_worked", "What worked",
     "What you would do more of. Written by a person."),
    ("what_changed", "What changed",
     "What was different this period, and why."),
    ("learned", "What we learned",
     "Observations with their sample sizes attached."),
    ("next_steps", "Next month",
     "Scale, test, stop, follow up. Editable before the client sees it."),
)

NARRATIVE_KEYS = tuple(k for k, _, _ in NARRATIVE)
NARRATIVE_LABEL = {k: label for k, label, _ in NARRATIVE}
NARRATIVE_WHY = {k: why for k, _, why in NARRATIVE}

# Recommendation categories the "Next month" block may carry. A closed set, so
# a client sees the same four words every month rather than whatever somebody
# typed.
SCALE = "scale"
TEST = "test"
STOP = "stop"
FOLLOW_UP = "follow_up"
RECOMMENDATIONS = (SCALE, TEST, STOP, FOLLOW_UP)
RECOMMENDATION_LABEL = {SCALE: "Scale", TEST: "Test", STOP: "Stop",
                        FOLLOW_UP: "Follow up"}


class DraftError(ValueError):
    """The draft is not one this system will store or render."""


def path():
    return os.path.abspath(os.environ.get(ENV)
                           or os.path.join(os.path.dirname(store.queue_path()),
                                           "report-drafts.jsonl"))


def load():
    return store.read_jsonl(path())


def save(rows, timeout=None):
    with store.lock(timeout, for_path=path()):
        store.write_jsonl(path(), rows)


def transaction(timeout=None):
    return store.file_transaction(path(), timeout)


def new_id():
    return f"draft-{uuid.uuid4().hex[:10]}"


def create(workspace, template, by, period=None, campaigns=None,
           sections=None, title=None, draft_id=None, at=None,
           narrative=None):
    """Start a draft. Version 1, and version 1 is what the screen shows.

    `narrative` seeds the generated first pass at creation rather than as an
    edit afterwards. Applying it through `edit()` made every new draft open
    at v2 with a v1 in its history that nobody wrote - a version list whose
    first entry is the machine is a version list a reader mistrusts.
    """
    if template not in clientreport.TEMPLATES:
        raise DraftError(f"unknown report template: {template!r}")
    chosen = clientreport.resolve_sections(template, sections)
    row = {
        "id": draft_id or new_id(),
        "workspace": workspace,
        "template": template,
        "period": period or "All time",
        "campaigns": list(campaigns or []),
        "sections": chosen,
        "status": DRAFT,
        "version": 1,
        "created_by": by,
        "created_at": at or store.now(),
        "updated_by": by,
        "updated_at": at or store.now(),
        "narrative": dict(narrative or {}, title=(
            title or (narrative or {}).get("title") or "")),
        "custom": [],
        "recommendations": [],
        # Every prior version, oldest first. Append-only.
        "history": [],
    }
    with transaction() as current:
        current.append(row)
    return row


def get(draft_id, rows=None):
    for row in (load() if rows is None else rows):
        if row.get("id") == draft_id:
            return row
    return None


def for_workspace(workspace, limit=100, rows=None):
    found = [r for r in (load() if rows is None else rows)
             if r.get("workspace") == workspace]
    return sorted(found, key=lambda r: str(r.get("updated_at")),
                  reverse=True)[:limit]


def _clean(text, limit=4000):
    """Narrative text, bounded. Stored as text; escaped when rendered."""
    if text is None:
        return ""
    return str(text).replace("\r\n", "\n").strip()[:limit]


def edit(draft_id, by, narrative=None, sections=None, custom=None,
         recommendations=None, at=None):
    """Apply an edit as a new version. Never rewrites a stored one.

    Anything not passed is left alone, so a form that submits one block does
    not silently blank the others.

    Note what this function cannot do: there is no parameter for a metric,
    because there is no field for one. The numbers are recomputed at render
    time from `src/report.py`.
    """
    updated = None
    with transaction() as current:
        for index, row in enumerate(current):
            if row.get("id") != draft_id:
                continue
            if row.get("status") == FINAL:
                raise DraftError(
                    "this report is marked final; create a new version to "
                    "change it")
            snapshot = {k: row.get(k) for k in
                        ("version", "narrative", "sections", "custom",
                         "recommendations", "updated_by", "updated_at")}
            new_narrative = dict(row.get("narrative") or {})
            for key, value in (narrative or {}).items():
                if key not in NARRATIVE_KEYS:
                    raise DraftError(f"{key!r} is not an editable block")
                new_narrative[key] = _clean(value)

            updated = dict(row)
            updated["narrative"] = new_narrative
            if sections is not None:
                # The template still decides what may exist. A reordered list
                # is honoured; an invented section is dropped.
                updated["sections"] = _order(row["template"], sections)
            if custom is not None:
                updated["custom"] = [_custom_section(c) for c in custom]
            if recommendations is not None:
                updated["recommendations"] = [_recommendation(r)
                                              for r in recommendations]
            updated["version"] = (row.get("version") or 1) + 1
            updated["updated_by"] = by
            updated["updated_at"] = at or store.now()
            updated["history"] = list(row.get("history") or []) + [snapshot]
            current[index] = updated
            break
    if updated is None:
        raise DraftError(f"no draft {draft_id!r}")
    return updated


def _order(template, requested):
    """Sections in the requested order, dropping anything the template lacks.

    Order is the editor's; membership is the template's. That split is what
    lets somebody move Replies above Campaigns without being able to move
    Provider Usage into a client report.
    """
    allowed = clientreport.sections_for(template)
    wanted = [str(s).strip() for s in requested if str(s).strip()]
    ordered = [s for s in wanted if s in allowed]
    return ordered or list(allowed)


def _custom_section(entry):
    """A custom section. Text only, and bounded.

    No HTML, no markup language, no template. A client report is a document
    that leaves the building, and an editor that accepted markup would be an
    injection surface pointed at a PDF somebody forwards.
    """
    kind = str((entry or {}).get("kind") or "text")
    if kind not in ("text", "note", "recommendation"):
        raise DraftError(f"{kind!r} is not a custom section kind")
    return {
        "kind": kind,
        "heading": _clean((entry or {}).get("heading"), 120),
        "body": _clean((entry or {}).get("body")),
        "after": str((entry or {}).get("after") or "") or None,
    }


def _recommendation(entry):
    kind = str((entry or {}).get("kind") or "").strip().lower()
    if kind not in RECOMMENDATIONS:
        raise DraftError(f"{kind!r} is not a recommendation category")
    return {"kind": kind, "text": _clean((entry or {}).get("text"), 400)}


def finalise(draft_id, by, at=None):
    """Mark a version final. Editing it afterwards is refused."""
    updated = None
    with transaction() as current:
        for index, row in enumerate(current):
            if row.get("id") == draft_id:
                updated = dict(row, status=FINAL, updated_by=by,
                               updated_at=at or store.now())
                current[index] = updated
                break
    if updated is None:
        raise DraftError(f"no draft {draft_id!r}")
    return updated


def reopen(draft_id, by, at=None):
    """Take a final report back to draft, as a new version.

    Allowed, and audited. A report that can never be corrected is a report
    somebody works around by making a second one.
    """
    updated = None
    with transaction() as current:
        for index, row in enumerate(current):
            if row.get("id") == draft_id:
                snapshot = {k: row.get(k) for k in
                            ("version", "narrative", "sections", "custom",
                             "recommendations", "updated_by", "updated_at")}
                updated = dict(row, status=DRAFT,
                               version=(row.get("version") or 1) + 1,
                               updated_by=by, updated_at=at or store.now(),
                               history=list(row.get("history") or [])
                               + [snapshot])
                current[index] = updated
                break
    if updated is None:
        raise DraftError(f"no draft {draft_id!r}")
    return updated


def seed_narrative(draft, data):
    """A first draft of the prose, from counted facts.

    Deterministic: the same numbers produce the same sentences. No model
    writes into a document a client will read - see `clientreport.observations`
    for the same discipline on the observations block.

    Returned rather than stored, so a person edits it before it is anybody's
    words but theirs.
    """
    observations = clientreport.observations(data)
    counted = {
        "companies": data.get("domains_uploaded") or 0,
        "contacts": data.get("contacts_found") or 0,
        "contactable": clientreport._reachable(data) or 0,
        "sent": data.get("emails_pushed") or 0,
        "replies": data.get("replies") or 0,
        "positive": data.get("positive_replies") or 0,
    }
    summary = (
        f"{counted['companies']:,} companies were assessed against the ICP, "
        f"producing {counted['contacts']:,} contacts of which "
        f"{counted['contactable']:,} are contactable by email after double "
        f"verification and email-security screening.")
    if counted["sent"]:
        summary += (f" {counted['sent']:,} touches were confirmed sent, "
                    f"producing {counted['replies']:,} replies and "
                    f"{counted['positive']:,} positive replies.")
    else:
        summary += (" No outreach has been confirmed sent in this period, so "
                    "no reply rate can be reported.")

    return {
        "title": (draft.get("narrative") or {}).get("title") or "",
        "summary": summary,
        "takeaways": "\n".join(text for _, text in observations[:4]),
        "what_worked": "",
        "what_changed": "",
        "learned": "\n".join(text for kind, text in observations
                             if kind in ("good", "warn")),
        "next_steps": "",
    }


def summarise(workspace=None, rows=None):
    found = [r for r in (load() if rows is None else rows)
             if workspace is None or r.get("workspace") == workspace]
    by_status = {}
    for row in found:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
    return {"total": len(found), "by_status": dict(sorted(by_status.items())),
            "last": (sorted(found, key=lambda r: str(r.get("updated_at")))
                     [-1] if found else None)}
