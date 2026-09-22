"""One resolved interpreter for every background dispatch, and 127 means FAILED.

WHY THIS FILE EXISTS. On 2026-09-22 a background task reported "completed"
with exit code 0 to its caller while its own inner command had exited 127:
`py -3` was not on PATH in that dispatch context. The walk it was supposed to
finish had not advanced a single page, and the caller had no way to tell that
from a successful no-op. **A task that exits 127 has not done the work**, and a
dispatch layer that cannot say so will keep reporting silence as success.

The three rules this module enforces:

  RESOLVE ONCE     The interpreter is `sys.executable` of the running process -
                   the one that is demonstrably working, because it is the one
                   executing this line. Never the string "python", never
                   "py -3", never "python3". Those are PATH lookups, and a PATH
                   lookup is a different question from "what is running now".

  ECHO THE COMMAND Every dispatch prints the exact argv it ran. A failure whose
                   command is not quoted cannot be reproduced, and reproducing
                   it is the whole job.

  127 IS FAILED    Exit 127 is "command not found". It is never a result. It is
                   raised as `DispatchFailed` with the command echoed, so it
                   can never be mistaken for a run that found nothing to do.

This machine has no venv, `python` is the Microsoft Store shim, and pytest is
not installed - the suite is `unittest`. Those facts are why the interpreter
has to be carried rather than looked up.
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Where the resolved interpreter is recorded so a handoff can quote it rather
#: than a session re-deriving it - which is how the wrong one gets written down.
RECORD = os.path.join(ROOT, "work", "dispatch-interpreter.json")

#: Exit code a shell returns when the command itself was not found. The whole
#: point of this module: it is a dispatch fault, never an answer.
COMMAND_NOT_FOUND = 127

#: Spellings that must never reach a dispatch. Each is a PATH lookup that has
#: already failed in this estate at least once.
FORBIDDEN = ("python", "python3", "py", "py -3", "python.exe")


class DispatchFailed(RuntimeError):
    """A dispatch did not run, or ran and could not be trusted.

    Distinct from a non-zero exit that MEANS something (a test suite failing,
    a guard going red). This is the layer below that: the command did not
    execute as asked.
    """


def interpreter():
    """The interpreter to dispatch with. Resolved once, from what is running.

    `sys.executable` is the only answer that cannot be stale: it is the binary
    currently executing this function. A PATH lookup asks a different question
    and, in the dispatch context that produced the 127, got a different answer.
    """
    exe = sys.executable
    if not exe or not os.path.exists(exe):
        raise DispatchFailed(
            "sys.executable is empty or missing, so there is no interpreter to "
            "carry. Refusing to guess with a PATH lookup - guessing is what "
            "produced exit 127.")
    return exe


def record_interpreter():
    """Write the resolved interpreter where a handoff can quote it verbatim."""
    data = {
        "interpreter": interpreter(),
        "version": sys.version.split()[0],
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "Resolved from sys.executable. Never 'py -3' or bare 'python'.",
    }
    os.makedirs(os.path.dirname(RECORD), exist_ok=True)
    tmp = RECORD + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=1)
    os.replace(tmp, RECORD)
    return data


def handoff_line():
    """The one line a handoff should carry about how to run anything here."""
    return (f"INTERPRETER: {interpreter()}  (python {sys.version.split()[0]}; "
            "no venv, pytest NOT installed, suite is unittest)")


def argv_for(args):
    """Turn a script path or module spec into a full argv led by the interpreter.

    Accepts what a caller naturally writes - `"scripts/x.py"`, a list, or a
    list already starting with `-m` - and refuses any argv whose first element
    is one of the PATH spellings this module exists to eliminate.
    """
    if isinstance(args, str):
        args = [args]
    args = [str(a) for a in args]
    if not args:
        raise DispatchFailed("empty command")
    head = args[0].strip().lower()
    if head in FORBIDDEN or head.rstrip(".exe") in ("python", "python3", "py"):
        raise DispatchFailed(
            f"refusing to dispatch via {args[0]!r}: that is a PATH lookup, and "
            f"a PATH lookup returned 127 on this machine. Pass the script or "
            f"'-m module' and let dispatch supply {interpreter()}")
    return [interpreter()] + args


def run(args, cwd=None, timeout=None, capture=True, check=True, echo=True):
    """Dispatch a python command. Echoes it, and treats 127 as FAILED.

    Returns the CompletedProcess so a caller can read a meaningful non-zero
    exit (a red suite) itself. Only 127 - and, with `check`, any non-zero - is
    turned into `DispatchFailed`, because only 127 means the command never ran.
    """
    argv = argv_for(args)
    shown = " ".join(argv)
    if echo:
        print(f"  dispatch: {shown}", flush=True)
    try:
        proc = subprocess.run(argv, cwd=cwd or ROOT, timeout=timeout,
                              capture_output=capture, text=True)
    except FileNotFoundError as exc:
        raise DispatchFailed(
            f"interpreter not found dispatching: {shown}") from exc
    if proc.returncode == COMMAND_NOT_FOUND:
        raise DispatchFailed(
            f"EXIT 127 (command not found), so NOTHING RAN: {shown}\n"
            "  This is a dispatch fault, not a result. It must never be "
            "reported as completed.")
    if check and proc.returncode != 0:
        raise DispatchFailed(
            f"exit {proc.returncode} from: {shown}\n"
            f"{(proc.stderr or '').strip()[:800]}")
    return proc


def spawn(args, log_path, cwd=None):
    """Start a long-running dispatch detached, with its command echoed into the log.

    The log opens with the argv that produced it, so a log found later says how
    to reproduce the run without anybody having to remember.
    """
    argv = argv_for(args)
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    handle = open(log_path, "a", encoding="utf-8", newline="\n")
    handle.write(f"\n=== dispatch {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
    handle.write(f"=== argv: {' '.join(argv)}\n")
    handle.flush()
    proc = subprocess.Popen(argv, cwd=cwd or ROOT, stdout=handle,
                            stderr=subprocess.STDOUT)
    print(f"  dispatched pid={proc.pid}: {' '.join(argv)}", flush=True)
    return proc


def main(argv=None):
    data = record_interpreter()
    print(handoff_line())
    print(f"  recorded to {RECORD}")
    return 0 if data else 1


if __name__ == "__main__":
    raise SystemExit(main())
