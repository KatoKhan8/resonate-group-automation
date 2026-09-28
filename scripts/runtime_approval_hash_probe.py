#!/usr/bin/env python3
"""RUNTIME verification of the P0-D approval-hash finding.

P0-D (`docs/P0D-PRODUCTION-CALLER-2026-09-28.md`, branch
`task-p0d-production-caller`, head `01dd7b78`) is a STATIC call-graph
measurement. It concluded:

    generate.run                        HAS a production caller (generate.main)
    sequenceplan.derive_*_payload       zero callers
    sequenceplan.approval_hash          only callers are those dead functions
    => the approval hash is never computed in production

A call graph proves an EDGE exists or does not. It does not prove a function
was ENTERED. This probe records ENTRY, at runtime, through the real production
CLI, and it is built so that every "NOT ENTERED" carries a positive control.

WHAT IS MEASURED, in the operator's own order:

    real production CLI (generate.main)
      -> COPIED production input
        -> generator ENTERED?
          -> canonical SequencePlan CREATED?
            -> canonical projection ENTERED?
              -> approval-hash function ENTERED?
                -> any provider write INTERCEPTED

TWO INDEPENDENT INSTRUMENTS, deliberately, because one instrument cannot
disagree with itself:

  A. WRAPPERS. Each target is replaced by a counting wrapper on its module
     attribute. Records count and first-call argument shape.
  B. CODE-OBJECT PROFILER. `sys.setprofile` records a 'call' event whose
     `frame.f_code` is one of the ORIGINAL target code objects, captured
     BEFORE the wrappers were installed. This instrument is immune to how the
     call is spelled - a bare same-module `approval_hash(plan)`, an alias, a
     deferred import, a locally-bound reference. That spelling blindness is
     exactly the defect that made TASK-425's grep wrong, so the second
     instrument exists to not repeat it in a new form.

  If A and B disagree, the probe says so and exits non-zero. A disagreement
  between two instruments is a finding, not a thing to tune away.

THE CONTROLS, all of them mandatory and all of them run:

  1. NEGATIVE CONTROL for the generator and the plan (`--negative-control`):
     `main()` is replaced by a stub that calls nothing. Every tracer must
     report NOT ENTERED. A probe that cannot report False is not a probe.
  2. POSITIVE CONTROL for the three projections and the approval hash: after
     the measured run has finished and its counters are frozen, this probe
     calls `derive_preview_data`, `derive_bison_payload`,
     `derive_heyreach_payload` and `approval_hash` DIRECTLY on the plan the
     production run actually built, and shows both instruments recording
     ENTERED. Until that fires, "NOT ENTERED" is UNKNOWN, not a finding.
  3. POSITIVE CONTROL for the provider-write interceptor: a deliberate
     `POST` to the REAL EmailBison base (`providers.bison.base()`), which
     must appear in the interceptor ledger and be refused BEFORE any socket
     is opened. A zero from an interceptor that never fired is column three
     of the authority registry, not evidence.

SAFETY, asserted rather than assumed:

  * The store is pointed at a COPY of production `work/` through
    `store.use_directory`. The probe REFUSES to run if `--state` resolves to
    any directory named `work` under a checkout, and separately refuses the
    real production `work/` by path.
  * `builtins.open` is wrapped for the whole run: any write-mode open of a
    path under a `work/` directory that is not the copy is REFUSED by name
    and recorded. This is stronger than comparing mtimes or even hashes,
    because 23 loops write the production checkout concurrently and a hash
    that moved would not tell you who moved it.
  * EVERY provider call goes through `providers.request`, whose transport is
    replaced by the interceptor. The interceptor forwards ONLY to
    127.0.0.1 (the local model stub) and refuses every other host after
    recording it. It calls `providers.refuse_unauthorized_write` first, so
    the production guard is exercised too rather than bypassed.
  * `socket.socket.connect` is wrapped as a second, independent barrier:
    any connect to a non-loopback address is recorded and refused. This is
    what catches a code path that never asked `providers.request`.
  * THE MODEL IS A LOCAL STUB, and this is a stated deviation, not a hidden
    one. `generate.main()` only builds a model under `--live`, and a real
    model call is real credit spend on a measurement run. `LLM_BASE_URL` is
    pointed at a loopback server that speaks `/chat/completions`. The model
    supplies CONTENT; it does not decide whether `derive_*` is called. See
    the document's "what this does not prove" section.

Usage:
    py -3 scripts/runtime_approval_hash_probe.py --state <copy-of-work> --id <record-id>
    py -3 scripts/runtime_approval_hash_probe.py --state <copy-of-work> --negative-control
"""
import argparse
import builtins
import hashlib
import json
import os
import socket
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PRODUCTION_WORK = os.path.join(
    r"C:\Users\Zvonimir\Desktop\resonate-group-automation", "work")


# --------------------------------------------------------------- the ledgers

class Ledger:
    """Entry counts from both instruments, with a freeze boundary.

    `phase` is switched from MEASURED to CONTROL between the production run
    and the positive controls, so a control can never be mistaken for a
    measurement. That boundary is the whole reason this class exists.
    """

    def __init__(self):
        self.phase = "MEASURED"
        self.wrapper = {}      # phase -> {name: count}
        self.profiler = {}     # phase -> {name: count}
        self.first_args = {}   # name -> short description of the first call
        for p in ("MEASURED", "CONTROL"):
            self.wrapper[p] = {}
            self.profiler[p] = {}

    def hit_wrapper(self, name, note=None):
        d = self.wrapper[self.phase]
        d[name] = d.get(name, 0) + 1
        if note and name not in self.first_args:
            self.first_args[name] = note

    def hit_profiler(self, name):
        d = self.profiler[self.phase]
        d[name] = d.get(name, 0) + 1

    def w(self, name, phase="MEASURED"):
        return self.wrapper[phase].get(name, 0)

    def p(self, name, phase="MEASURED"):
        return self.profiler[phase].get(name, 0)


LEDGER = Ledger()

# Provider calls seen at the single chokepoint, and sockets seen at the OS
# boundary. Both are lists rather than counters because WHICH call was
# attempted is the interesting part.
PROVIDER_CALLS = []
SOCKET_CONNECTS = []
FORBIDDEN_WRITES = []


# ------------------------------------------------------- instrument B: profiler

class Profiler:
    """Records entry by CODE OBJECT, so the call's spelling cannot hide it."""

    def __init__(self):
        self.targets = {}      # code object -> name
        self.installed = False

    def register(self, name, fn):
        code = getattr(fn, "__code__", None)
        if code is None:
            raise TypeError("%s has no __code__; cannot register" % name)
        self.targets[code] = name

    def _hook(self, frame, event, arg):
        if event == "call":
            name = self.targets.get(frame.f_code)
            if name is not None:
                LEDGER.hit_profiler(name)
        return None

    def install(self):
        sys.setprofile(self._hook)
        threading.setprofile(self._hook)
        self.installed = True

    def remove(self):
        sys.setprofile(None)
        threading.setprofile(None)
        self.installed = False


PROFILER = Profiler()


# ------------------------------------------------------- instrument A: wrappers

def wrap(module, attr, name, note_fn=None):
    """Replace `module.attr` with a counting wrapper.

    Module attribute assignment IS module global assignment, so this also
    intercepts a bare same-module call such as `approval_hash(plan)` inside
    `derive_bison_payload`. That is checked by the positive control rather
    than assumed.
    """
    original = getattr(module, attr)

    def wrapper(*args, **kwargs):
        note = None
        if note_fn is not None:
            try:
                note = note_fn(args, kwargs)
            except Exception as exc:                        # noqa: BLE001
                note = "<note failed: %s>" % type(exc).__name__
        LEDGER.hit_wrapper(name, note)
        return original(*args, **kwargs)

    wrapper.__name__ = getattr(original, "__name__", attr)
    wrapper.__wrapped_original__ = original
    setattr(module, attr, wrapper)
    return original


# ------------------------------------------------------ provider interceptor

def install_provider_interceptor(providers):
    """Replace the single transport chokepoint.

    `providers.request` is the one door every provider call goes through, and
    `providers.set_transport` is the seam the repository already provides for
    swapping the wire. The interceptor:

      1. records the (method, url) BEFORE anything else,
      2. calls `providers.refuse_unauthorized_write`, so the PRODUCTION guard
         runs rather than being bypassed by the probe,
      3. forwards to the real urllib transport ONLY for 127.0.0.1,
      4. refuses every other host, so no socket is ever opened to one.
    """
    real_transport = providers._urllib_transport

    def interceptor(method, url, headers, body, timeout):
        host = providers.host_of(url)
        record = {
            "phase": LEDGER.phase,
            "method": providers.normalise_method(method),
            "host": str(host),
            "url": providers.redact(str(url))[:160],
            "is_write": providers.normalise_method(method)
            in providers.WRITE_METHODS,
            "prospect_facing": bool(providers.is_prospect_facing(url)),
        }
        PROVIDER_CALLS.append(record)
        # The production guard, exercised, not bypassed.
        try:
            providers.refuse_unauthorized_write(method, url)
            record["production_guard"] = "did not refuse"
        except Exception as exc:                            # noqa: BLE001
            record["production_guard"] = type(exc).__name__
            record["outcome"] = "REFUSED by production guard"
            raise
        if host in ("127.0.0.1", "localhost", "[::1]"):
            record["outcome"] = "forwarded to loopback stub"
            return real_transport(method, url, headers, body, timeout)
        record["outcome"] = "REFUSED by probe interceptor, no socket opened"
        raise providers.HttpTransportError(
            "PROBE INTERCEPTOR: refused %s %s - this probe opens no socket to "
            "any host but 127.0.0.1." % (record["method"], record["host"]))

    providers.set_transport(interceptor)
    return interceptor


def install_socket_guard():
    """Second, independent barrier at the OS boundary."""
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def loopback(address):
        if isinstance(address, tuple) and address:
            host = str(address[0])
            return host in ("127.0.0.1", "::1", "localhost")
        return False

    def guarded(self, address, *a, **kw):
        SOCKET_CONNECTS.append({"phase": LEDGER.phase,
                                "address": str(address),
                                "loopback": loopback(address)})
        if not loopback(address):
            raise OSError(
                "PROBE SOCKET GUARD: refused a connect to %r. Only loopback "
                "is permitted during this probe." % (address,))
        return real_connect(self, address, *a, **kw)

    def guarded_ex(self, address, *a, **kw):
        SOCKET_CONNECTS.append({"phase": LEDGER.phase,
                                "address": str(address),
                                "loopback": loopback(address)})
        if not loopback(address):
            return 1
        return real_connect_ex(self, address, *a, **kw)

    socket.socket.connect = guarded
    socket.socket.connect_ex = guarded_ex
    return real_connect, real_connect_ex


def install_write_guard(allowed_dir):
    """Refuse, by name, any write-mode open of a work/ file outside the copy.

    The brief is explicit that mtime is the wrong instrument because 23 loops
    write the production checkout. So rather than inferring innocence from a
    hash, this records and REFUSES the act itself.
    """
    real_open = builtins.open
    allowed = os.path.abspath(allowed_dir).lower()

    def guarded_open(file, mode="r", *a, **kw):
        try:
            path = os.path.abspath(os.fspath(file))
        except TypeError:
            return real_open(file, mode, *a, **kw)
        writing = any(ch in str(mode) for ch in ("w", "a", "x", "+"))
        low = path.lower()
        if writing and (os.sep + "work" + os.sep) in (low + os.sep) \
                and not low.startswith(allowed):
            FORBIDDEN_WRITES.append({"phase": LEDGER.phase, "path": path,
                                     "mode": str(mode)})
            raise PermissionError(
                "PROBE WRITE GUARD: refused a write-mode open of %r. Only the "
                "state copy at %r may be written." % (path, allowed_dir))
        return real_open(file, mode, *a, **kw)

    builtins.open = guarded_open
    return real_open


# ------------------------------------------------------------- the model stub

STUB_ANSWER = {
    # THE UNION OF EVERY STAGE'S SCHEMA, in one object. Each stage reads the
    # keys it needs; none of them rejects an extra key. One answer therefore
    # serves ICP, extract, hypothesis, match, strategy and the writer, which
    # keeps the stub small enough to be auditable.
    #
    # Nothing here is prospect-facing: no run in this probe reaches a
    # provider, and every string is visibly a probe placeholder.
    "is_agency": True,
    "what_they_actually_are": "an agency (probe stub)",
    "facts": [
        {"text": "PROBE STUB FACT: the team runs client projects.",
         "quote": "PROBE STUB FACT: the team runs client projects.",
         "label": "site", "source": "site", "verified": False},
    ],
    "qualification": "QUALIFIED",
    "hypothesis": "PROBE STUB HYPOTHESIS: project margin is hard to see.",
    "hypothesis_basis": "probe stub",
    "role_family": "operations",
    "capability_key": "profitability",
    "what_changes": "PROBE STUB: margin becomes visible per project.",
    "angle": "PROBE STUB ANGLE",
    "evidence": "PROBE STUB EVIDENCE",
    "strategy_id": "probe-stub",
    "primary_problem": "PROBE STUB PROBLEM",
    "offer": "A",
    "steps": ["PROBE STUB STEP 1"],
    "subject": "PROBE STUB SUBJECT A",
    "subject_alt": "PROBE STUB SUBJECT B",
    "subject_breakup": "PROBE STUB SUBJECT C",
    "emails": {"em%d" % i: "PROBE STUB EMAIL BODY %d." % i
               for i in range(1, 6)},
    "linkedin": {"connect": "PROBE STUB CONNECT NOTE.",
                 "msg1": "PROBE STUB LI 1.",
                 "msg2": "PROBE STUB LI 2.",
                 "msg3": "PROBE STUB LI 3."},
    "ps": {"em1": "PROBE STUB PS.", "em3": "PROBE STUB PS 3."},
}


def start_model_stub():
    """A loopback `/chat/completions` server. Returns (base_url, shutdown)."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    calls = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):                          # noqa: A003
            return

        def do_POST(self):                                  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                sent = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                sent = {}
            prompt = ""
            for msg in sent.get("messages") or ():
                prompt += str(msg.get("content") or "")
            calls.append({"path": self.path, "prompt_chars": len(prompt)})
            payload = {
                "id": "probe-stub",
                "object": "chat.completion",
                "model": sent.get("model") or "probe-stub",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant",
                                         "content": json.dumps(STUB_ANSWER)}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1,
                          "total_tokens": 2},
            }
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    return "http://127.0.0.1:%d" % port, server.shutdown, calls


# ------------------------------------------------------------------ utilities

def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


TARGETS = (
    # (label,                             module key,      attribute)
    ("generate.run", "generate", "run"),
    ("generate.generate_record", "generate", "generate_record"),
    ("generate._generate_via_campaign", "generate", "_generate_via_campaign"),
    ("generate._adapt_plan_to_cadence", "generate", "_adapt_plan_to_cadence"),
    ("generate_campaign.generate", "generate_campaign", "generate"),
    ("sequenceplan.new", "sequenceplan", "new"),
    ("sequenceplan.approval_hash", "sequenceplan", "approval_hash"),
    ("sequenceplan.derive_preview_data", "sequenceplan", "derive_preview_data"),
    ("sequenceplan.derive_bison_payload", "sequenceplan",
     "derive_bison_payload"),
    ("sequenceplan.derive_heyreach_payload", "sequenceplan",
     "derive_heyreach_payload"),
    # THE DOWNSTREAM HALF, for --mode project. P0-D's claim is that
    # `sequenceplan` is HALF wired: the SHAPE flows through `for_campaign` ->
    # `derive_bison_sequence`, and the WORDS do not. These four targets make
    # that a runtime measurement rather than a source reading, and they give
    # the derive_* zero a second context - one where the canonical projection
    # actually had a reason to be called.
    ("sequenceplan.for_campaign", "sequenceplan", "for_campaign"),
    ("sequenceplan.derive_bison_sequence", "sequenceplan",
     "derive_bison_sequence"),
    ("bisonfactory._plan", "bisonfactory", "_plan"),
    ("bisonfactory._approved_copy", "bisonfactory", "_approved_copy"),
)

# The five questions the operator asked, and which target answers each.
QUESTIONS = (
    ("generator", ("generate.run",)),
    ("SequencePlan", ("sequenceplan.new",)),
    ("canonical projection", ("sequenceplan.derive_preview_data",
                              "sequenceplan.derive_bison_payload",
                              "sequenceplan.derive_heyreach_payload")),
    ("approval hash", ("sequenceplan.approval_hash",)),
)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True,
                    help="a COPY of production work/, never the real one")
    ap.add_argument("--id", action="append", dest="ids",
                    help="record id(s) to run; repeatable")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--negative-control", action="store_true",
                    help="replace main() with a stub that calls nothing, and "
                         "prove every tracer reports NOT ENTERED")
    ap.add_argument("--no-live", action="store_true",
                    help="run the CLI without --live (the NoModel/plan branch)")
    ap.add_argument("--mode", choices=("generate", "project"),
                    default="generate",
                    help="generate: python -m src.generate (the generation "
                         "half). project: python -m src.bisonfactory <id> "
                         "(the provider-projection half, dry).")
    ap.add_argument("--campaign",
                    help="canonical campaign id, required for --mode project")
    ap.add_argument("--construct-from",
                    help="CONSTRUCTED INPUT, labelled as such. Clone this "
                         "production campaign row inside the COPY and give the "
                         "clone record_ids whose cadence already carries all "
                         "five stored email steps, so `bisonfactory._plan` "
                         "reaches `_approved_copy` instead of stopping at "
                         "`_require_declared_cadence`. The 13 stale stored "
                         "three-step declarations are a known, separately "
                         "owned problem (OPERATING-MODE launch blocker 9), and "
                         "this flag routes around it rather than pretending it "
                         "is not there. Only the MEMBERSHIP is constructed: "
                         "the cadence declaration is the production row's own.")
    ap.add_argument("--construct-limit", type=int, default=3)
    ap.add_argument("--json", dest="json_out",
                    help="write the machine-readable result here")
    a = ap.parse_args(argv)

    state = os.path.abspath(a.state)
    queue = os.path.join(state, "queue.jsonl")
    if not os.path.exists(queue):
        print("REFUSED: %s does not exist. Point --state at a COPY of "
              "production work/." % queue)
        return 2
    for forbidden in (os.path.join(ROOT, "work"), PRODUCTION_WORK):
        if os.path.normcase(state) == os.path.normcase(
                os.path.abspath(forbidden)):
            print("REFUSED: --state is %r, a real work/ directory. Use a copy."
                  % forbidden)
            return 2
    if os.path.basename(state).lower() == "work":
        print("REFUSED: --state is named 'work'. Use a copy under a scratch "
              "directory, so no reader can mistake it for a checkout's own.")
        return 2

    # Production hashes BEFORE, taken here and re-taken by a fresh process
    # afterwards. The write guard is the real evidence; these are corroboration.
    prod_before = {}
    for name in ("queue.jsonl", "campaigns.jsonl"):
        p = os.path.join(PRODUCTION_WORK, name)
        prod_before[name] = sha256_of(p) if os.path.exists(p) else None

    base_url, shutdown, stub_calls = start_model_stub()
    os.environ["LLM_BASE_URL"] = base_url
    os.environ["LLM_API_KEY"] = "probe-stub-not-a-credential"
    os.environ["LLM_MODEL"] = "probe-stub"

    from src import (store, providers, generate, generate_campaign,
                     sequenceplan, bisonfactory)

    if a.mode == "project" and not a.campaign:
        print("REFUSED: --mode project needs --campaign <canonical id>.")
        return 2

    restore_env = store.use_directory(state)

    constructed = None
    if a.construct_from:
        from src import campaigns as campaigns_mod
        rows = campaigns_mod.load()
        source = campaigns_mod.require(a.construct_from, rows)
        members = []
        for rec in store.load():
            for _ck, steps in (rec.get("cadence") or {}).items():
                if not isinstance(steps, dict):
                    continue
                if all(isinstance(steps.get(k), dict) and steps[k].get("body")
                       for k in ("em1", "em2", "em3", "em4", "em5")):
                    members.append(rec["id"])
                    break
            if len(members) >= a.construct_limit:
                break
        clone = json.loads(json.dumps(source))
        clone["campaign_id"] = a.campaign
        clone["record_ids"] = members
        clone["bison_campaign_id"] = None
        clone["status"] = "draft"
        # THE CADENCE DECLARATION COMES FROM THE CANONICAL LIBRARY, not from
        # me. `cadencelibrary.named()` is the authority OPERATING-MODE names
        # as correct ("the config and the library AGREE and are correct; what
        # is wrong is history"), so the constructed row declares exactly what
        # a NEW productive campaign would declare. Nothing about the cadence
        # is invented here; only the membership is.
        from src import cadencelibrary, clients as clients_mod
        cfg = clients_mod.load(source.get("client"))
        lib = cadencelibrary.named(cfg.get("cadence", "productive_li_heavy_v1"))
        clone["cadence_steps"] = [dict(s) for s in (lib or ())]
        rows = [r for r in rows if r.get("campaign_id") != a.campaign]
        rows.append(clone)
        campaigns_mod.save(rows)
        constructed = {"cloned_from": a.construct_from,
                       "campaign_id": a.campaign,
                       "record_ids": members,
                       "cadence_steps": [s.get("key") for s in
                                         (clone.get("cadence_steps") or ())]}
        print("== CONSTRUCTED INPUT (in the COPY only) ==")
        print("  %s" % json.dumps(constructed))
        print()

    # Register the ORIGINAL code objects with the profiler first, then wrap.
    modules = {"generate": generate, "generate_campaign": generate_campaign,
               "sequenceplan": sequenceplan, "bisonfactory": bisonfactory}
    originals = {}
    for label, mod_name, attr in TARGETS:
        fn = getattr(modules[mod_name], attr)
        PROFILER.register(label, fn)
        originals[label] = fn

    notes = {
        "generate.run": lambda args, kw: "live=%r model=%s" % (
            kw.get("live"), type(kw.get("model")).__name__),
        "sequenceplan.new": lambda args, kw: "client=%r account=%r" % (
            args[0] if args else None,
            (args[1] or {}).get("domain") if len(args) > 1 else None),
    }
    for label, mod_name, attr in TARGETS:
        wrap(modules[mod_name], attr, label, notes.get(label))

    real_open = install_write_guard(state)
    real_connect, real_connect_ex = install_socket_guard()
    install_provider_interceptor(providers)

    if a.mode == "project":
        argv_cli = [a.campaign]          # DRY: no --live, deliberately
        entry = bisonfactory.main
        cli_name = "python -m src.bisonfactory"
    else:
        argv_cli = []
        if not a.no_live:
            argv_cli.append("--live")
        argv_cli += ["--client", "productive", "--regenerate-whole-set"]
        for rid in (a.ids or ()):
            argv_cli += ["--id", rid]
        if a.limit:
            argv_cli += ["--limit", str(a.limit)]
        entry = generate.main
        cli_name = "python -m src.generate"

    if a.negative_control:
        def stub(argv=None):
            print("NEGATIVE CONTROL: a main() that calls nothing at all.")
            return 0
        entry = stub

    queue_before = sha256_of(queue)
    print("== SETUP ==")
    print("  state (COPY)            %s" % state)
    print("  QUEUE env               %s" % os.environ.get("QUEUE"))
    print("  copy queue sha256       %s" % queue_before)
    print("  model stub              %s  (loopback, not a real provider)"
          % base_url)
    print("  CLI argv                %s %s" % (cli_name, " ".join(argv_cli)))
    print("  instruments             A wrappers + B code-object profiler")
    print()

    cli_rc, cli_error, cli_output = None, None, ""
    PROFILER.install()
    try:
        import io
        buf, out = io.StringIO(), sys.stdout
        try:
            sys.stdout = buf
            cli_rc = entry(argv_cli)
        except BaseException as exc:                        # noqa: BLE001
            cli_error = "%s: %s" % (type(exc).__name__, str(exc)[:400])
        finally:
            sys.stdout = out
            cli_output = buf.getvalue()
    finally:
        PROFILER.remove()

    # ---- FREEZE. Everything after this line is a CONTROL, never a measurement.
    measured = {"wrapper": dict(LEDGER.wrapper["MEASURED"]),
                "profiler": dict(LEDGER.profiler["MEASURED"])}
    measured_provider = list(PROVIDER_CALLS)
    LEDGER.phase = "CONTROL"

    print("== MEASURED PHASE: the real CLI, on copied production input ==")
    print("  generate.main() exit     %s" % cli_rc)
    if cli_error:
        print("  generate.main() raised   %s" % cli_error)
    print("  stub model calls         %d" % len(stub_calls))
    print()
    print("  %-38s %8s %8s" % ("target", "wrapper", "profiler"))
    for label, _m, _a in TARGETS:
        print("  %-38s %8d %8d"
              % (label, measured["wrapper"].get(label, 0),
                 measured["profiler"].get(label, 0)))
    print()
    for label, note in sorted(LEDGER.first_args.items()):
        print("  first call to %-28s %s" % (label, note))
    print()

    # The plan the production run actually built, recovered for the controls.
    # Not synthesised: the control must fire the tracers on the same objects
    # the production path produced, or it is proving something else.
    control_plan = None
    try:
        real_gen = originals["generate_campaign.generate"]
        holder = {}

        def capture(*args, **kwargs):
            plan = real_gen(*args, **kwargs)
            holder["plan"] = plan
            return plan
        # A second, separate generation purely to hold a plan object for the
        # controls. It is in the CONTROL phase and its counts are reported
        # separately.
        setattr(generate_campaign, "generate", capture)
        if a.mode == "generate" and not a.negative_control and not cli_error:
            generate.main(argv_cli)
        control_plan = holder.get("plan")
    except BaseException as exc:                            # noqa: BLE001
        print("  (control generation raised %s: %s)"
              % (type(exc).__name__, str(exc)[:200]))
    finally:
        setattr(generate_campaign, "generate",
                originals["generate_campaign.generate"])

    if control_plan is None:
        control_plan = {"client": "probe-control", "account": {},
                        "strategy": {"strategy_id": "probe"},
                        "contacts": [{"email": "probe@example.invalid",
                                      "contact_key": "probe",
                                      "sequences": {"em1": "x"},
                                      "subjects": {"A": "y"}}]}

    print("== POSITIVE CONTROL 1: the projection and approval-hash tracers ==")
    print("  Each is called DIRECTLY. Both instruments must record ENTERED,")
    print("  or the NOT ENTERED above is UNKNOWN rather than a finding.")
    PROFILER.install()
    control_results = {}
    try:
        for attr in ("derive_preview_data", "derive_bison_payload",
                     "derive_heyreach_payload"):
            fn = getattr(sequenceplan, attr)
            control_results[attr] = type(fn(control_plan)).__name__
        control_results["approval_hash"] = sequenceplan.approval_hash(
            control_plan)
    except BaseException as exc:                            # noqa: BLE001
        control_results["error"] = "%s: %s" % (type(exc).__name__,
                                               str(exc)[:200])
    finally:
        PROFILER.remove()
    print()
    print("  %-38s %8s %8s" % ("target", "wrapper", "profiler"))
    for label, _m, _a in TARGETS:
        if "derive_" in label or "approval_hash" in label:
            print("  %-38s %8d %8d"
                  % (label, LEDGER.w(label, "CONTROL"),
                     LEDGER.p(label, "CONTROL")))
    print("  direct-call returns      %s" % json.dumps(control_results)[:200])
    print()

    print("== POSITIVE CONTROL 2: the provider-write interceptor ==")
    from src.providers import bison as bison_mod
    real_base = bison_mod.base()
    write_url = real_base + "/leads"
    guard_outcome = None
    try:
        providers.request("POST", write_url, {}, {"probe": True})
        guard_outcome = "NOT REFUSED - the interceptor did not fire"
    except BaseException as exc:                            # noqa: BLE001
        guard_outcome = "%s: %s" % (type(exc).__name__, str(exc)[:200])
    fired = [c for c in PROVIDER_CALLS
             if c["phase"] == "CONTROL" and c["host"] in real_base]
    print("  deliberate write         POST %s" % providers.redact(write_url))
    print("  outcome                  %s" % guard_outcome)
    print("  interceptor recorded it  %s" % bool(fired))
    if fired:
        print("  record                   %s" % json.dumps(fired[-1])[:300])
    print()

    # -------------------------------------------------------------- teardown
    providers.reset_transport()
    socket.socket.connect = real_connect
    socket.socket.connect_ex = real_connect_ex
    builtins.open = real_open
    for label, mod_name, attr in TARGETS:
        setattr(modules[mod_name], attr, originals[label])
    shutdown()
    if callable(restore_env):
        restore_env()

    # ------------------------------------------------------------- the verdict
    print("== THE FIVE ANSWERS, MEASURED PHASE ONLY ==")
    disagreements = []
    answers = {}
    for question, labels in QUESTIONS:
        w = sum(measured["wrapper"].get(l, 0) for l in labels)
        p = sum(measured["profiler"].get(l, 0) for l in labels)
        if (w > 0) != (p > 0):
            disagreements.append((question, w, p))
        state_word = "ENTERED" if (w > 0 or p > 0) else "NOT ENTERED"
        if question == "SequencePlan":
            state_word = "CREATED" if (w > 0 or p > 0) else "NOT CREATED"
        answers[question] = {"wrapper": w, "profiler": p, "state": state_word}
        print("  %-24s %-12s  (wrapper %d, profiler %d)"
              % (question, state_word, w, p))

    provider_writes = [c for c in measured_provider
                       if c["is_write"] and c["host"] not in
                       ("127.0.0.1", "localhost")]
    print("  %-24s %d" % ("provider writes", len(provider_writes)))
    answers["provider writes"] = {"count": len(provider_writes)}
    print()

    print("== INTEGRITY ==")
    print("  copy queue sha256 after  %s" % sha256_of(queue))
    print("  forbidden work/ writes   %d  %s"
          % (len(FORBIDDEN_WRITES),
             json.dumps(FORBIDDEN_WRITES[:3]) if FORBIDDEN_WRITES else ""))
    non_loopback = [s for s in SOCKET_CONNECTS if not s["loopback"]]
    print("  non-loopback connects    %d  %s"
          % (len(non_loopback), json.dumps(non_loopback[:3])
             if non_loopback else ""))
    print("  provider calls, MEASURED %d (all hosts)" % len(measured_provider))
    hosts = sorted({c["host"] for c in measured_provider})
    print("  provider hosts, MEASURED %s" % (hosts or "none"))
    for name, before in prod_before.items():
        p = os.path.join(PRODUCTION_WORK, name)
        after = sha256_of(p) if os.path.exists(p) else None
        print("  production %-14s %s" % (name,
              "UNCHANGED" if before == after else "CHANGED (see the doc; the "
              "write guard is the authority on whether THIS process did it)"))
        print("    before %s" % before)
        print("    after  %s" % after)
    print()

    if disagreements:
        print("!! INSTRUMENT DISAGREEMENT - STOP AND REPORT, DO NOT TUNE !!")
        for q, w, p in disagreements:
            print("   %s: wrapper=%d profiler=%d" % (q, w, p))

    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as fh:
            json.dump({
                "answers": answers,
                "measured": measured,
                "control": {"wrapper": LEDGER.wrapper["CONTROL"],
                            "profiler": LEDGER.profiler["CONTROL"]},
                "provider_calls_measured": measured_provider,
                "provider_control_fired": bool(fired),
                "provider_control_outcome": guard_outcome,
                "forbidden_writes": FORBIDDEN_WRITES,
                "non_loopback_connects": non_loopback,
                "cli": {"argv": argv_cli, "rc": cli_rc, "error": cli_error,
                        "stub_model_calls": len(stub_calls)},
                "cli_output_head": cli_output.splitlines()[:40],
                "production_sha_before": prod_before,
                "negative_control": bool(a.negative_control),
                "disagreements": disagreements,
            }, fh, indent=2)
        print("wrote %s" % a.json_out)

    print("== WHAT THE CLI PRINTED (first 30 lines) ==")
    for line in cli_output.splitlines()[:30]:
        print("  " + line)

    return 1 if disagreements else 0


if __name__ == "__main__":
    raise SystemExit(main())
