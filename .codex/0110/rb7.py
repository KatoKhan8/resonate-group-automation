# TASK-0110 B7 group re-derivation at HEAD 8dc1ed55f.
# The six recorded mutations (LANE-glm.md 2026-10-15, B7 entry): M1 pool
# flip, M2 config->diacritic, M3a five-fixed, M3b double-append, M5
# guard-wired (tests/test_every_body_is_signed_by_the_pools_owner.py,
# commit fca459853) and the no-signature render
# (tests/test_the_provider_does_the_signing.py, commit 25364e9b6).
# All five touched files are byte-identical at those commits and at HEAD
# (git diff --stat empty, verified before this run).
# Byte-exact backup/restore by sha256; 0079 pyc protocol on every leg.
# HYGIENE: the config's sender.name is never printed - only its px.
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.join(ROOT, ".codex", "0110")
BAK = os.path.join(HERE, "backup")
os.makedirs(BAK, exist_ok=True)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
for k in [k for k in os.environ if k.startswith("GIT_CONFIG")]:
    del os.environ[k]

POOLS = "tests.test_every_body_is_signed_by_the_pools_owner"
PROV = "tests.test_the_provider_does_the_signing"
FIX = "tests/fixtures/sender-estate-2026-09-21.json"
CFG = "config/clients/productive.yaml"
TC = "src/trailingcontent.py"
SALT = "resonate-pii-salt-2026-09-16"
CONFIG_PX_TODAY = "px-fc7d1255b8a3"


def px_of(name):
    return "px-" + hashlib.sha256(
        (SALT + unicodedata.normalize("NFC", name or "")).encode()
    ).hexdigest()[:12]


def sha(rel):
    with open(os.path.join(ROOT, rel), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def kill_pycs():
    for d in (os.path.join(ROOT, "src", "__pycache__"),
              os.path.join(ROOT, "scripts", "__pycache__"),
              os.path.join(ROOT, "tests", "__pycache__")):
        if os.path.isdir(d):
            shutil.rmtree(d)


def run_tests(tag, test, needles):
    kill_pycs()
    out = os.path.join(HERE, "rb7-%s.txt" % tag)
    with open(out, "wb") as fh:
        p = subprocess.run([sys.executable, "-m", "unittest", "-v", test],
                           cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    with open(out, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    print("  %s: exit=%d -> rb7-%s.txt" % (tag, p.returncode, tag))
    shown = set()
    for l in lines:
        for n in needles:
            if n in l and l[:60] not in shown:
                print("    | %s" % l[:170])
                shown.add(l[:60])
                break
    for l in lines[-2:]:
        if l.strip():
            print("    | %s" % l[:170])


def leg(tag, rel, mutate, verify, test, needles):
    p = os.path.join(ROOT, rel)
    orig = sha(rel)
    shutil.copyfile(p, os.path.join(BAK, os.path.basename(rel) + "." + tag + ".orig"))
    with open(p, "rb") as fh:
        raw = fh.read()
    new = mutate(raw)
    if verify:
        verify(new)
    with open(p, "wb") as fh:
        fh.write(new)
    print("planted %s in %s (%s -> %s)"
          % (tag, rel, orig[:16], sha(rel)[:16]))
    try:
        run_tests(tag + "-red", test, needles)
    finally:
        shutil.copyfile(os.path.join(BAK, os.path.basename(rel) + "." + tag + ".orig"), p)
        ok = sha(rel) == orig
        print("restored %s -> %s" % (tag, "MATCH" if ok else "MISMATCH"))
        assert ok
    run_tests(tag + "-green", test, ["FAILED", "Ran "])


# --- fixture mutations -------------------------------------------------------

def m1a(raw):
    s = b'"owner_px": "px-75ee916b9999"'
    assert raw.count(s) == 13, raw.count(s)
    i = raw.index(s)
    return raw[:i] + b'"owner_px": "px-0110abcdef01"' + raw[i + len(s):]


def m1a_verify(raw):
    doc = json.loads(raw.decode("utf-8"))
    rows = doc["rows"]
    pool = [x for x in rows if x["owner_px"] == "px-75ee916b9999"]
    flipped = [x["id"] for x in rows if x["owner_px"] == "px-0110abcdef01"]
    assert len(pool) == 12 and flipped == [2738], (len(pool), flipped)
    print("  m1a pre-check: pool 12 rows, flipped row id %s" % flipped)


def m1b(raw):
    a = b'"id": 2742,'
    assert raw.count(a) == 1
    i = raw.index(a)
    win = raw[i:i + 300]
    assert win.count(b'"owner_present": false') == 1
    assert win.count(b'"owner_px": null') == 1
    win = win.replace(b'"owner_present": false', b'"owner_present": true')
    win = win.replace(b'"owner_px": null', b'"owner_px": "px-75ee916b9999"')
    return raw[:i] + win + raw[i + 300:]


def m1b_verify(raw):
    doc = json.loads(raw.decode("utf-8"))
    rows = doc["rows"]
    assert sorted(x["id"] for x in rows if not x["owner_present"]) == [2782]
    assert len([x for x in rows if x["owner_px"] == "px-75ee916b9999"]) == 14
    print("  m1b pre-check: ownerless now [2782] only, pool 14 rows")


def m3a(raw):
    s = b'"name_px": "px-2f1dd920a186"'
    assert raw.count(s) == 5, raw.count(s)
    return raw.replace(s, b'"name_px": "px-387dd1f77205"')


def m3a_verify(raw):
    doc = json.loads(raw.decode("utf-8"))
    for i in (2910, 3425, 3426, 3430, 3435):
        r = next(x for x in doc["rows"] if x["id"] == i)
        assert r["name_px"] == r["owner_px"] == "px-387dd1f77205", i
    print("  m3a pre-check: the five now name_px == owner_px")


# --- config mutation (value never printed) -----------------------------------

def m2(raw):
    ms = re.search(rb"(?m)^sender:[^\n]*\n", raw)
    assert ms, "no sender: block"
    mn = re.search(rb"(?m)^[A-Za-z_][A-Za-z0-9_]*:[^\n]*\n", raw[ms.end():])
    block = raw[ms.end():ms.end() + (mn.start() if mn else len(raw))]
    cands = list(re.finditer(rb"(?m)^([ \t]+)name:[ \t]*[^\n]*\n", block))
    assert len(cands) == 1, "sender.name lines in block: %d" % len(cands)
    lb = cands[0].group(0)
    assert raw.count(lb) == 1
    core = lb.rstrip(b"\r\n")
    tail = lb[len(core):]
    cut = len(core) - (1 if core.endswith(b'"') else 0)
    repl = core[:cut] + "́".encode("utf-8") + core[cut:] + tail
    return raw.replace(lb, repl)


def m2_verify(raw):
    try:
        import yaml
    except ImportError:
        print("  m2 pre-check: pyyaml absent, skipped (the leg itself proves)")
        return
    cfg = yaml.safe_load(raw.decode("utf-8"))
    name = ((cfg.get("sender") or {}).get("name") or "")
    assert name, "sender.name vanished from planted config"
    newpx = px_of(name)
    assert newpx != CONFIG_PX_TODAY, "accent did not move the px"
    print("  m2 pre-check: planted name px %s != pin %s (name not printed)"
          % (newpx, CONFIG_PX_TODAY))


# --- trailingcontent.py mutations (source carries literal \\n escapes) -------

def m3b(raw):
    s = b'        result = f"{result}\\n\\n{sig}"\n'
    assert raw.count(s) == 1, raw.count(s)
    return raw.replace(s, b'        result = f"{result}\\n\\n{sig}\\n\\n{sig}"\n')


def m3b_verify(raw):
    compile(raw.decode("utf-8"), TC, "exec")
    print("  m3b pre-check: compiles")


def m5(raw):
    s = b'    result = (body or "").rstrip()\n    result = append_cta(result, cta_link)\n'
    assert raw.count(s) == 1, raw.count(s)
    r = (b'    result = (body or "").rstrip()\n'
         b'    from . import sendersignature as _ss  # 0110 M5 re-plant\n'
         b'    _ss.refuse_if_duplicate(result, (signature or "").strip())\n'
         b'    result = append_cta(result, cta_link)\n')
    return raw.replace(s, r)


def m5_verify(raw):
    compile(raw.decode("utf-8"), TC, "exec")
    print("  m5 pre-check: compiles")


def l186(raw):
    s = (b'    if sig and result:\n'
         b'        result = f"{result}\\n\\n{sig}"\n'
         b'    elif sig:\n'
         b'        result = sig\n')
    assert raw.count(s) == 1, raw.count(s)
    r = (b'    if False and sig and result:  # 0110 L186 re-plant\n'
         b'        result = f"{result}\\n\\n{sig}"\n'
         b'    elif False and sig:\n'
         b'        result = sig\n')
    return raw.replace(s, r)


def l186_verify(raw):
    compile(raw.decode("utf-8"), TC, "exec")
    print("  l186 pre-check: compiles")


print("=== control legs (record: pools 26 tests OK + 4 expected failures; "
      "provider 6 tests OK + 3) ===")
run_tests("control-pools", POOLS, ["Ran ", "OK", "expected failures"])
run_tests("control-prov", PROV, ["Ran ", "OK", "expected failures"])

print("=== M1a: pool flip (one pool row's owner -> foreign px) ===")
leg("m1a", FIX, m1a, m1a_verify, POOLS,
    ["!= 13", "px-0110abcdef01", "expected failures"])
print("=== M1b: pool flip (ownerless row 2742 flipped INTO the pool) ===")
leg("m1b", FIX, m1b, m1b_verify, POOLS,
    ["!= 13", "2742", "expected failures"])
print("=== M2: config sender.name + diacritic ===")
leg("m2", CFG, m2, m2_verify, POOLS,
    ["!= ", "changed since", "expected failures"])
print("=== M3a: the five display names fixed in the fixture ===")
leg("m3a", FIX, m3a, m3a_verify, POOLS,
    ["UNEXPECTED SUCCESS", "moved", "unexpected successes"])
print("=== M3b: double-append in trailingcontent.compose ===")
leg("m3b", TC, m3b, m3b_verify, POOLS,
    ["SignatureDoubled", "times", "errors"])
print("=== M5: double-sign guard wired into compose ===")
leg("m5", TC, m5, m5_verify, POOLS,
    ["UNEXPECTED SUCCESS", "unexpected successes"])
print("=== L186: rendering no signature (provider module) ===")
leg("l186", TC, l186, l186_verify, PROV,
    ["UNEXPECTED SUCCESS", "unexpected successes"])

st = subprocess.run(["git", "status", "--porcelain", "src/", "config/",
                     "tests/fixtures/"], cwd=ROOT, capture_output=True, text=True)
print("git status src/ config/ tests/fixtures/ -> %r" % st.stdout.strip())
