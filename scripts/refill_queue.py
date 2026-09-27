#!/usr/bin/env python3
"""Refill docs/qwen-tasks/TODO/ from the standing backlog template when the
ready queue drops below the floor, so the watchdog does this itself instead
of waiting for Claude to notice and hand-write task files.

Operator instruction, 2026-09-27: "the watchdog must do this itself from
the template list, not wait for Claude." Source of truth for WHAT to write
is docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md - each entry there is a
reusable, always-legitimate-to-run kind of task (an audit, a drift check, a
consistency check), never a one-off. This script never invents backlog
content itself; it only turns the next unused template entry into a
concrete, freshly-numbered task file.

READ-ONLY toward the ready-queue question itself: it calls
scripts/claim_task.py --status to get the real ready count, the same
authority everything else uses, so this can never disagree with a human
running --status by hand.
"""
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = os.path.join(ROOT, "docs", "qwen-tasks", "STANDING-BACKLOG-TEMPLATE.md")
TODO_DIR = os.path.join(ROOT, "docs", "qwen-tasks", "TODO")
READY_FLOOR = 12

#: Where the refill script remembers which template it wrote last, so
#: repeated runs cycle through the list rather than always picking the
#: first entry. Gitignored (work/) since this is a per-machine cursor, not
#: shared state.
CURSOR_PATH = os.path.join(ROOT, "work", ".refill-template-cursor")


def parse_templates(text):
    """Each `### TEMPLATE: name` section up to the next `---` line."""
    blocks = re.split(r"\n---\n", text)
    out = []
    for block in blocks:
        m = re.search(r"### TEMPLATE:\s*(\S+)\n(.*)", block, re.S)
        if not m:
            continue
        name, body = m.group(1).strip(), m.group(2).strip()
        out.append((name, body))
    return out


def ready_count():
    out = subprocess.run(
        ["py", "-3", os.path.join(ROOT, "scripts", "claim_task.py"), "--status"],
        capture_output=True, text=True, cwd=ROOT)
    m = re.search(r"^ready \(unclaimed, deps met\): (\d+)", out.stdout, re.M)
    return int(m.group(1)) if m else 0


def next_task_number():
    """Highest TASK-nnn seen anywhere under docs/qwen-tasks/, plus one."""
    highest = 0
    base = os.path.join(ROOT, "docs", "qwen-tasks")
    for stage in ("TODO", "RUNNING", "REVIEW", "DONE", "REWORK", "BLOCKED"):
        d = os.path.join(base, stage)
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            m = re.match(r"TASK-(\d+)-", fn)
            if m:
                highest = max(highest, int(m.group(1)))
    return highest + 1


def load_cursor(n_templates):
    try:
        with open(CURSOR_PATH, encoding="utf-8") as fh:
            return int(fh.read().strip()) % n_templates
    except Exception:
        return 0


def save_cursor(i):
    os.makedirs(os.path.dirname(CURSOR_PATH), exist_ok=True)
    with open(CURSOR_PATH, "w", encoding="utf-8") as fh:
        fh.write(str(i))


def slugify(name):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", name.lower())).strip("-")


def write_task_file(tid, name, body):
    priority_m = re.search(r"^PRIORITY:\s*(\S+)", body, re.M)
    size_m = re.search(r"^SIZE:\s*(\S+)", body, re.M)
    priority = priority_m.group(1) if priority_m else "P2"
    size = size_m.group(1) if size_m else "M"
    rest = re.sub(r"^PRIORITY:.*\n|^SIZE:.*\n", "", body, flags=re.M).strip()
    title = " ".join(w.capitalize() if w.islower() else w for w in name.split("-"))
    fn = "TASK-%d-%s.md" % (tid, slugify(name))
    content = (
        "PRIORITY: %s\nSIZE: %s\nDEPENDS:\n\n"
        "# TASK-%d — %s (standing backlog refill, %s)\n\n"
        "**Auto-refilled by scripts/refill_queue.py, per the operator's "
        "2026-09-27 standing order: the watchdog refills TODO from the "
        "template list itself, before the ready queue drops below the "
        "12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-"
        "TEMPLATE.md`, entry `%s`.\n\n%s\n"
        % (priority, size, tid, title, datetime.now(timezone.utc).date(),
           name, rest)
    )
    path = os.path.join(TODO_DIR, fn)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


def main():
    current = ready_count()
    print("ready before refill:", current)
    if current >= READY_FLOOR:
        print("above the floor (%d), nothing to do" % READY_FLOOR)
        return 0

    with open(TEMPLATE_PATH, encoding="utf-8") as fh:
        templates = parse_templates(fh.read())
    if not templates:
        print("no templates found in %s" % TEMPLATE_PATH)
        return 1

    need = READY_FLOOR - current
    cursor = load_cursor(len(templates))
    written = []
    tid = next_task_number()
    for _ in range(need):
        name, body = templates[cursor]
        path = write_task_file(tid, name, body)
        written.append(path)
        tid += 1
        cursor = (cursor + 1) % len(templates)
    save_cursor(cursor)

    for p in written:
        print("wrote", os.path.relpath(p, ROOT))

    subprocess.run(["git", "add"] + written, cwd=ROOT, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m",
         "Auto-refill: %d task file(s) from the standing backlog template "
         "(ready count was %d, floor is %d)" % (len(written), current, READY_FLOOR)],
        cwd=ROOT, check=True)
    subprocess.run(["git", "push", "-q", "origin", "master"], cwd=ROOT, check=True)
    print("committed and pushed %d new task file(s)" % len(written))
    return 0


if __name__ == "__main__":
    sys.exit(main())
