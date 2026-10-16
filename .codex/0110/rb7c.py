# TASK-0110 B7 final legs (rb7c): M3b, M5, L186 in src/trailingcontent.py.
# The file is CRLF on disk (probe8: 135 CRLF, 0 bare LF, sha256
# 368c09f16a14aac9), so every multi-line search is eol-joined and the m3b
# search carries no line terminator. M1a/M1b/M2/M3a are recorded in
# rb7-console.txt / rb7b-console.txt with restores MATCH. Same protocol:
# backup, plant, pre-check (compile), red, restore-by-sha256, green;
# 0079 pyc deletion per leg.
import hashlib
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.join(ROOT, ".codex", "0110")
BAK = os.path.join(HERE, "backup")
os.makedirs(BAK, exist_ok=True)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
for k in [k for k in os.environ if k.startswith("GIT_CONFIG")]:
    del os.environ[k]

POOLS = "tests.test_every_body_is_signed_by_the_pools_owner"
PROV = "tests.test_the_provider_does_the_signing"
TC = "src/trailingcontent.py"


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


def leg(tag, mutate, verify, test, needles):
    p = os.path.join(ROOT, TC)
    orig = sha(TC)
    assert orig.startswith("368c09f16a14aac9"), orig
    shutil.copyfile(p, os.path.join(BAK, "trailingcontent.py." + tag + ".orig"))
    with open(p, "rb") as fh:
        raw = fh.read()
    new = mutate(raw)
    verify(new)
    with open(p, "wb") as fh:
        fh.write(new)
    print("planted %s in %s (%s -> %s)" % (tag, TC, orig[:16], sha(TC)[:16]))
    try:
        run_tests(tag + "-red", test, needles)
    finally:
        shutil.copyfile(os.path.join(BAK, "trailingcontent.py." + tag + ".orig"), p)
        ok = sha(TC) == orig
        print("restored %s -> %s" % (tag, "MATCH" if ok else "MISMATCH"))
        assert ok
    run_tests(tag + "-green", test, ["FAILED", "Ran "])


def m3b(raw):
    eol = b"\r\n" if raw.count(b"\r\n") else b"\n"
    s = b'        result = f"{result}\\n\\n{sig}"'
    assert raw.count(s) == 1, raw.count(s)
    r = b'        result = f"{result}\\n\\n{sig}\\n\\n{sig}"'
    assert raw.count(r) == 0
    return raw.replace(s, r)


def m3b_verify(new):
    compile(new.decode("utf-8"), TC, "exec")
    print("  m3b pre-check: compiles")


def m5(raw):
    eol = b"\r\n" if raw.count(b"\r\n") else b"\n"
    s = eol.join([b'    result = (body or "").rstrip()',
                  b'    result = append_cta(result, cta_link)', b''])
    assert raw.count(s) == 1, raw.count(s)
    r = eol.join([b'    result = (body or "").rstrip()',
                  b'    from . import sendersignature as _ss  # 0110 M5 re-plant',
                  b'    _ss.refuse_if_duplicate(result, (signature or "").strip())',
                  b'    result = append_cta(result, cta_link)', b''])
    return raw.replace(s, r)


def m5_verify(new):
    compile(new.decode("utf-8"), TC, "exec")
    print("  m5 pre-check: compiles")


def l186(raw):
    eol = b"\r\n" if raw.count(b"\r\n") else b"\n"
    s = eol.join([b'    if sig and result:',
                  b'        result = f"{result}\\n\\n{sig}"',
                  b'    elif sig:',
                  b'        result = sig', b''])
    assert raw.count(s) == 1, raw.count(s)
    r = eol.join([b'    if False and sig and result:  # 0110 L186 re-plant',
                  b'        result = f"{result}\\n\\n{sig}"',
                  b'    elif False and sig:',
                  b'        result = sig', b''])
    return raw.replace(s, r)


def l186_verify(new):
    compile(new.decode("utf-8"), TC, "exec")
    print("  l186 pre-check: compiles")


print("=== M3b: double-append in trailingcontent.compose ===")
leg("m3b", m3b, m3b_verify, POOLS,
    ["SignatureDoubled", "times", "errors", "FAILED"])
print("=== M5: double-sign guard wired into compose ===")
leg("m5", m5, m5_verify, POOLS,
    ["UNEXPECTED SUCCESS", "unexpected successes"])
print("=== L186: rendering no signature (provider module) ===")
leg("l186", l186, l186_verify, PROV,
    ["UNEXPECTED SUCCESS", "unexpected successes"])

st = subprocess.run(["git", "status", "--porcelain", "src/", "config/",
                     "tests/fixtures/"], cwd=ROOT, capture_output=True, text=True)
print("git status src/ config/ tests/fixtures/ -> %r" % st.stdout.strip())
