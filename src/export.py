#!/usr/bin/env python3
"""Writing our data into somebody else's program, without it being executed.

A CSV is not a data format so much as an invitation. Excel, Google Sheets and
LibreOffice all treat a leading `=`, `+`, `-` or `@` as the start of a formula,
and a prospect's name is attacker-controlled text that we did not write and a
provider did not sanitise. `=cmd|' /C calc'!A0` in a name column is a real
thing that has really happened, and the person who opens the file is usually a
client rather than us.

The defence is boring and total: prefix a single quote, which every
spreadsheet reads as "this is text", and strip the control characters that
break row framing. Nothing here tries to detect a malicious cell — it treats
every cell the same way, because a rule with an exception is a rule with a
bypass.

`csv.writer` already handles quoting for commas, quotes and newlines. It does
not, and should not, know anything about formulas. That is this module's job.
"""
import csv
import io
import json

# The four characters a spreadsheet reads as "evaluate what follows".
FORMULA_LEADERS = ("=", "+", "-", "@")

# Tab, carriage return and newline are also treated as formula-starting
# whitespace by some versions of Excel once a leader follows them, and they
# corrupt row framing besides.
LEADING_WHITESPACE = ("\t", "\r", "\n", " ")

GUARD = "'"

# Characters that have no business in a cell at all: NUL and the C0 controls
# other than tab/CR/LF, which we handle by escaping rather than deleting.
_CONTROL = {c: None for c in range(0x20) if c not in (0x09, 0x0A, 0x0D)}
_CONTROL[0x7F] = None


def strip_controls(value):
    """Remove NUL and friends. They are never meaningful and often deliberate."""
    return str(value).translate(_CONTROL)


def is_dangerous(value):
    """Would a spreadsheet evaluate this cell?"""
    text = strip_controls(value).lstrip("".join(LEADING_WHITESPACE))
    return bool(text) and text[0] in FORMULA_LEADERS


def safe_cell(value):
    """One cell, rendered so no spreadsheet will execute it.

    Returns a string always: `None` becomes empty, numbers become their own
    text. A genuinely numeric cell is passed through untouched, because
    quoting every number would make the file useless for the common case.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = strip_controls(value)
    if is_dangerous(text):
        return GUARD + text
    return text


def safe_row(row):
    return [safe_cell(cell) for cell in row]


def safe_rows(rows):
    return [safe_row(row) for row in rows]


def to_csv(header, rows):
    """The same guard, into a string rather than onto disk.

    A browser download hands bytes back over HTTP instead of writing a path,
    and a second CSV writer would be a second place for the formula guard to
    be forgotten. `write_csv` is this function plus a file handle.
    """
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(safe_row(header))
    writer.writerows(safe_rows(rows))
    return buf.getvalue()


def write_csv(path, header, rows):
    """The only way a CSV leaves this system.

    Newline handling is `csv`'s own convention: open with newline="" and let
    the writer decide, otherwise Windows doubles every line ending.
    """
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(to_csv(header, rows))
    return path


def write_json(path, payload):
    """JSON needs no formula guard, but it does need to be valid.

    `ensure_ascii=False` keeps names readable; `sort_keys` makes the file
    diffable, which matters more than it sounds when a client asks what
    changed between two exports.
    """
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    return path


def audit(rows):
    """Which cells would have been executed, for reporting rather than defence.

    Defence has already happened by the time anyone calls this. This answers
    "how much hostile data is in this batch", which is worth knowing.
    """
    found = []
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            if isinstance(cell, str) and is_dangerous(cell):
                found.append({"row": r, "column": c, "starts_with": cell[:1]})
    return found
