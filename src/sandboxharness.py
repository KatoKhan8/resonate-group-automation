"""Isolation for the phase-2 horizon run, with both directions proven.

ONE COPY OF THE SAFETY RULE
===========================
Phase 1 (`tests/test_sandbox_phase1.py`, 43 tests) established these
primitives and proved them. They are lifted into `src/` here rather than
copied into a second test file, because this repository's own recurring
defect is two representations of one rule that drift - the status board and
the recovery check disagreeing about liveness is the example its own
`supervisor` docstring gives. The horizon runner and the horizon tests now
read the same module.

WHAT ISOLATION HAS TO MEAN HERE, AND WHY `set_transport` ALONE IS NOT IT
========================================================================
Phase 1 measured the trap: the writer model and the provider calls share ONE
transport seam, so a blanket sentinel at `providers.set_transport` kills copy
generation as well as provider traffic - that is what broke phase 0's first
attempt. So the wire is sealed BY HOST: the writer's host is allowed through
and every other host raises.

For the horizon run the operator's requirement is stricter than phase 1's:
"every transport and readback replaced by a raiser, with a positive control
where a deliberate call aborts the run with NETWORK TOUCHED". So this module
offers two modes:

  seal_wire(allow=WRITER_HOSTS)  - phase 1's host seal, for the bounded
                                   subset that exercises the real writer
  seal_wire(allow=())            - total seal, for the bulk of the horizon

Both are positively controlled: `assert_wire_sealed` makes a deliberate call
and requires `NetworkTouched`. A seal that has never been shown to fire is
not a seal.

THE PRODUCTION ASSERTION IS PER-WINDOW, NOT GLOBAL
==================================================
Phase 1 found that production `work/queue.jsonl` changes DURING a run,
because a parallel lane generates into it with the operator's approval. A
single md5 pair around the whole run would therefore fail for a reason that
is not a safety breach. The answer phase 1 settled on, and this keeps: each
unit takes its own snapshot and compares over ITS OWN window. The operator
additionally asked for mtime and size, so all three are carried - md5 proves
content, mtime and size make a change visible even if a file is rewritten
with identical bytes by a different writer.

`_production_root` resolves the MAIN checkout through `.git`, because a
linked worktree has no `work/` at all and without it every assertion would
compare `None` to `None` - a check that cannot fail.
"""
import hashlib
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The writer's host. Allowed through only when a caller explicitly asks for
#: it, because the bulk of the horizon must reach nothing at all.
WRITER_HOSTS = ("openrouter.ai",)

#: A host used only to prove the seal fires. Never a real call.
CONTROL_URL = "https://api.emailbison.com/api/v1/workspaces"

PRODUCTION_FILES = ("queue.jsonl", "campaigns.jsonl", "agency-dnc.jsonl")


class NetworkTouched(RuntimeError):
    """A host was reached that this run is not allowed to reach.

    The operator's abort condition. Named so the message is unmistakable in
    a log: a horizon run that touched the network proved nothing about
    isolation and its measurements are void.
    """


class ProductionTouched(RuntimeError):
    """A file under the production `work/` changed inside a measured window."""


def production_root():
    """The MAIN checkout, even when this file sits in a linked worktree."""
    dot = os.path.join(ROOT, ".git")
    if os.path.isdir(dot):
        return ROOT
    with open(dot, encoding="utf-8") as handle:
        pointer = handle.read().strip()
    gitdir = pointer.split(":", 1)[1].strip()
    if not os.path.isabs(gitdir):
        gitdir = os.path.abspath(os.path.join(ROOT, gitdir))
    return os.path.dirname(os.path.dirname(os.path.dirname(gitdir)))


def _md5(path):
    if not os.path.exists(path):
        return None
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def production_fingerprint(root=None):
    """md5, mtime and size of every production file we promise not to touch.

    Returns a dict keyed by filename. A file that does not exist maps to
    None, and `assert_production_unchanged` treats an appearing or vanishing
    file as a change rather than as equal-to-None.
    """
    root = root or production_root()
    out = {}
    for name in PRODUCTION_FILES:
        path = os.path.join(root, "work", name)
        if not os.path.exists(path):
            out[name] = None
            continue
        stat = os.stat(path)
        out[name] = {"md5": _md5(path), "mtime_ns": stat.st_mtime_ns,
                     "size": stat.st_size, "path": path}
    return out


def assert_production_unchanged(before, after=None, root=None):
    """Raise unless every production file is byte-identical over the window.

    The three fields are not redundant. md5 answers "same content"; size
    makes a truncation obvious without hashing; mtime_ns catches a rewrite
    whose bytes happen to match, which is exactly what a replayed generation
    pass would produce.
    """
    after = after if after is not None else production_fingerprint(root)
    problems = []
    for name in PRODUCTION_FILES:
        b, a = before.get(name), after.get(name)
        if b is None and a is None:
            continue
        if (b is None) != (a is None):
            problems.append("%s: %s" % (
                name, "appeared" if b is None else "vanished"))
            continue
        for field in ("md5", "size", "mtime_ns"):
            if b[field] != a[field]:
                problems.append("%s: %s %r -> %r"
                                % (name, field, b[field], a[field]))
    if problems:
        raise ProductionTouched(
            "production work/ changed inside a measured window: "
            + "; ".join(problems))
    return True


def assert_production_exists(root=None):
    """The files we assert on must BE there.

    Without this the whole guarantee is a test that cannot fail: in a linked
    worktree `work/` is absent, every fingerprint is None, and None == None
    passes forever. Phase 1 hit exactly this.
    """
    root = root or production_root()
    missing = [n for n in ("queue.jsonl", "campaigns.jsonl")
               if not os.path.exists(os.path.join(root, "work", n))]
    if missing:
        raise ProductionTouched(
            "refusing to claim isolation: production work/%s not found under "
            "%s, so the assertion would compare None to None and could never "
            "fail" % (", ".join(missing), root))
    return True


# ----------------------------------------------------------------- the wire

def seal_wire(allow=()):
    """Replace the transport with a raiser. Returns (undo, calls).

    `allow` is a tuple of hostnames let through. Empty means total seal,
    which is what the bulk of the horizon runs under. `calls` accumulates
    every attempted (method, url) so the run can report what it tried to
    reach even when nothing got out.
    """
    from . import providers

    calls = []
    allowed = tuple(allow)

    def sealed(method, url, headers=None, body=None, timeout=None):
        calls.append((method, url))
        host = str(url).split("//", 1)[-1].split("/", 1)[0].lower()
        if any(host == a or host.endswith("." + a) for a in allowed):
            return providers._urllib_transport(method, url, headers, body,
                                               timeout)
        raise NetworkTouched(
            "NETWORK TOUCHED: %s %s. The horizon run reaches no host%s. "
            "Nothing was sent." % (
                method, url,
                "" if not allowed else " but %s" % (", ".join(allowed),)))

    previous = providers.set_transport(sealed)

    def undo():
        providers.set_transport(previous)

    return undo, calls


def assert_wire_sealed(expect_allowed=()):
    """POSITIVE CONTROL: make a deliberate call and require it to abort.

    Called before any probe, every time. A seal is a claim about what cannot
    happen, and the only evidence for such a claim is that it demonstrably
    stops something.
    """
    from . import providers

    try:
        providers.request("GET", CONTROL_URL, {})
    except NetworkTouched:
        return True
    raise AssertionError(
        "the wire is NOT sealed: a deliberate GET to %s was not refused, so "
        "every isolation claim in this run is void" % (CONTROL_URL,))


def seal_readbacks():
    """Replace provider readbacks with raisers. Returns an undo callable.

    Separate from the transport seal because a readback is a different
    failure: a run whose readback silently returns a cached or default value
    would report a write as confirmed without anything confirming it. The
    operator asked for both to be raisers.
    """
    import importlib

    undo = []
    targets = (
        ("src.providers.bison", ("campaign", "campaign_lead_count",
                                 "membership", "scheduled_emails",
                                 "sending_schedule", "campaign_senders")),
        ("src.providers.heyreach", ("campaign_status", "campaign_stats",
                                    "campaign_read", "campaign_leads")),
    )
    for mod_name, attrs in targets:
        try:
            mod = importlib.import_module(mod_name)
        except Exception:                                       # noqa: BLE001
            continue
        for attr in attrs:
            if not hasattr(mod, attr):
                continue
            previous = getattr(mod, attr)

            def raiser(*_a, _n="%s.%s" % (mod_name, attr), **_k):
                raise NetworkTouched(
                    "NETWORK TOUCHED: readback %s was called. The horizon "
                    "run confirms nothing against a provider." % (_n,))

            setattr(mod, attr, raiser)
            undo.append((mod, attr, previous))

    def _undo():
        for mod, attr, previous in reversed(undo):
            setattr(mod, attr, previous)

    return _undo


# ------------------------------------------------- both-direction domains

def real_client_domains(root=None):
    """Domains that must NEVER appear in a synthetic fixture.

    Read from the two files that actually hold them rather than from a
    literal list, so the assertion tracks the estate instead of a snapshot.
    """
    root = root or production_root()
    out = set()
    supp = os.path.join(root, "config", "suppress.local.txt")
    if os.path.exists(supp):
        with open(supp, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip().lower()
                if line and not line.startswith("#"):
                    out.add(line)
    client = os.path.join(root, "config", "clients", "productive.yaml")
    if os.path.exists(client):
        import re
        with open(client, encoding="utf-8", errors="replace") as handle:
            for match in re.finditer(
                    r"\b([a-z0-9][a-z0-9-]*\.(?:[a-z]{2,}\.)?[a-z]{2,})\b",
                    handle.read().lower()):
                out.add(match.group(1))
    return out


SYNTHETIC_SUFFIXES = (".invalid", "example.com")


def is_synthetic_domain(domain):
    domain = str(domain or "").strip().lower()
    return domain.endswith(".invalid") or domain == "example.com" \
        or domain.endswith(".example.com")
