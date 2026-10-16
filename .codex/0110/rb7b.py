# TASK-0110 B7 continuation (rb7b): M2 with the accent inserted at the end
# of the VALUE, before the line's trailing comment (rb7.py's m2 landed the
# accent inside the comment - caught by its own teeth pre-check, config
# never written, sha still 4ec1e1696efbcdfe). Then M3a, M3b, M5, L186.
# M1a/M1b are already recorded in rb7-console.txt / rb7-m1a-red.txt /
# rb7-m1b-red.txt. Same protocol: backup, plant, red, restore-by-sha256,
# green; 0079 pyc deletion per leg; value never printed, px only.
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
ACC = "́".encode("utf-8")


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
        verify(new, raw)
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
    m = re.match(rb"^([ \t]+name:[ \t]*)([^\r\n]*?)([ \t]#[^\r\n]*)?$", core)
    assert m, "name line shape unexpected"
    pre, val, com = m.group(1), m.group(2), m.group(3)
    assert val, "empty sender.name value"
    if val.startswith(b'"') and val.endswith(b'"') and len(val) >= 2:
        newval = val[:-1] + ACC + b'"'
    else:
        newval = val + ACC
    repl = pre + newval + (com or b"") + tail
    assert raw.count(repl) == 0
    return raw.replace(lb, repl)


def m2_verify(new, old):
    import yaml
    cfg = yaml.safe_load(new.decode("utf-8"))
    name = ((cfg.get("sender") or {}).get("name") or "")
    oname = (yaml.safe_load(old.decode("utf-8")).get("sender") or {}).get("name") or ""
    assert name and name != oname, "accent did not reach the parsed value"
    assert px_of(name) != px_of(oname), "accent did not move the px"
    print("  m2 pre-check: parsed value moved; px %s -> %s (pin %s holds for orig: %s)"
          % (CONFIG_PX_TODAY, px_of(name), CONFIG_PX_TODAY,
             px_of(oname) == CONFIG_PX_TODAY))


def m3a(raw):
    s = b'"name_px": "px-2f1dd920a186"'
    assert raw.count(s) == 5, raw.count(s)
    return raw.replace(s, b'"name_px": "px-387dd1f77205"')


def m3a_verify(new, old):
    doc = json.loads(new.decode("utf-8"))
    for i in (2910, 3425, 3426, 3430, 3435):
        r = next(x for x in doc["rows"] if x["id"] == i)
        assert r["name_px"] == r["owner_px"] == "px-387dd1f77205", i
    print("  m3a pre-check: the five now name_px == owner_px")


def m3b(raw):
    s = b'        result = f"{result}\\n\\n{sig}"\n'
    assert raw.count(s) == 1, raw.count(s)
    return raw.replace(s, b'        result = f"{result}\\n\\n{sig}\\n\\n{sig}"\n')


def m3b_verify(new, old):
    compile(new.decode("utf-8"), TC, "exec")
    print("  m3b pre-check: compiles")


def m5(raw):
    s = b'    result = (body or "").rstrip()\n    result = append_cta(result, cta_link)\n'
    assert raw.count(s) == 1, raw.count(s)
    r = (b'    result = (body or "").rstrip()\n'
         b'    from . import sendersignature as _ss  # 0110 M5 re-plant\n'
         b'    _ss.refuse_if_duplicate(result, (signature or "").strip())\n'
         b'    result = append_cta(result, cta_link)\n')
    return raw.replace(s, r)


def m5_verify(new, old):
    compile(new.decode("utf-8"), TC, "exec")
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


def l186_verify(new, old):
    compile(new.decode("utf-8"), TC, "exec")
    print("  l186 pre-check: compiles")


print("=== control legs (re-proven after the rb7 crash) ===")
run_tests("control-pools", POOLS, ["Ran ", "OK", "expected failures"])
run_tests("control-prov", PROV, ["Ran ", "OK", "expected failures"])
print("=== M2: config sender.name + diacritic (accent before the comment) ===")
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
