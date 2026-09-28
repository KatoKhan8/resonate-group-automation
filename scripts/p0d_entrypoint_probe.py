#!/usr/bin/env python3
"""P0-D read-only probe: does `python -m src.generate` actually EXECUTE?

The static call graph (`p0d_callgraph.py`) proves the EDGE
`src.generate:main -> src.generate:run` exists. That is reachability, not
execution. This probe runs the module CLI's own `main()` in its DRY mode and
reports whether `run()` was entered and how many records it planned.

SAFETY, and each of these is asserted rather than assumed:

  * The store is pointed at a COPY of production `work/` via
    `store.use_directory`, which is the same redirect the test base uses. The
    real `work/` is never opened. Pass --state to name the copy.
  * DRY: no `--live`, so `generate.run` builds `llm.NoModel()` and takes the
    `plan()` branch. `plan()` enumerates what WOULD be asked; it calls no
    model and writes no record.
  * Zero provider calls and zero spend follow from the above, and the probe
    asserts the record file is byte-identical afterwards rather than trusting
    that.

Usage:
    py -3 scripts/p0d_entrypoint_probe.py --state <copy-of-work>
"""
import argparse
import hashlib
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True,
                    help="a COPY of production work/, never the real one")
    ap.add_argument("--limit", default="3")
    ap.add_argument("--negative-control", action="store_true",
                    help="replace main() with a stub that does NOT call run(), "
                         "and prove this probe reports ENTERED False. A probe "
                         "that cannot report False is not a probe.")
    a = ap.parse_args(argv)

    state = os.path.abspath(a.state)
    queue = os.path.join(state, "queue.jsonl")
    if not os.path.exists(queue):
        print(f"REFUSED: {queue} does not exist. Point --state at a copy of "
              f"production work/.")
        return 2
    real = os.path.abspath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "work"))
    if state == real:
        print("REFUSED: --state is the real work/ directory. Use a copy.")
        return 2

    from src import store, generate, llm

    restore = store.use_directory(state)
    before = digest(queue)
    print(f"state      {state}")
    print(f"queue      {sum(1 for _ in open(queue, encoding='utf-8'))} records"
          f", sha256[:16]={before}")
    print(f"QUEUE env  {os.environ.get('QUEUE')}")
    print()

    # Did `run()` actually get entered, and with what? Wrap it rather than
    # trusting the static edge: a probe that assumes the call happened is the
    # thing this probe exists to replace.
    seen = {}
    real_run = generate.run

    def spy(*args, **kwargs):
        seen["called"] = True
        seen["kwargs"] = dict(kwargs)
        seen["model"] = type(kwargs.get("model")).__name__
        return real_run(*args, **kwargs)

    generate.run = spy
    entry = generate.main
    if a.negative_control:
        def stub(argv=None):
            print("NEGATIVE CONTROL: a main() that never calls run()")
            return 0
        entry = stub
    buf, out = io.StringIO(), sys.stdout
    try:
        sys.stdout = buf
        rc = entry(["--limit", str(a.limit)])
    finally:
        sys.stdout = out
        generate.run = real_run
        if callable(restore):
            restore()

    printed = buf.getvalue()
    after = digest(queue)

    print("== RESULT ==")
    print(f"  generate.main() exit code        {rc}")
    print(f"  generate.run() ENTERED           {seen.get('called', False)}")
    print(f"  model class run() received       {seen.get('model')}")
    print(f"  live kwarg                       "
          f"{seen.get('kwargs', {}).get('live')}")
    print(f"  queue sha256 before/after        {before} / {after}")
    print(f"  QUEUE UNCHANGED (zero writes)    {before == after}")
    print()
    print("== what the CLI printed (first 24 lines) ==")
    for line in printed.splitlines()[:24]:
        print("  " + line)
    return 0 if seen.get("called") and before == after else 1


if __name__ == "__main__":
    raise SystemExit(main())
