"""webapp/0410 - the PLANTED AMBIGUOUS-NEEDLE control, and the naive contrast.

Two things the brief asks for, both measured rather than argued:

 1. 0380's uniqueness rule (count >= 2 -> AMBIGUOUS-NEEDLE, REFUSE) fired on a
    needle PLANTED to be ambiguous in a synthetic scratch repo.  A rule that
    only ever fires on the estate's own four real needles could be firing for
    a reason peculiar to them; a plant proves it is the count that fires it.
    The negative arm is planted beside it: the same repo, one occurrence,
    UNIQUE-AT-REF.  Without that arm a precheck that refused everything would
    score identically.

 2. The naive oldest-hit each class member's BARE needle would have given, so
    the dating coupling is visible as a wrong answer rather than described.
"""
import os
import shutil
import stat
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from safe_dating import uniqueness_precheck, log_s, git  # noqa: E402
from step6_corrections import PUBLISHED, ESTATE, CONTESTED  # noqa: E402

FIXTURE = os.path.join(HERE, "plant-repo")

AMBIG = b"THE PLANTED NEEDLE"     # written twice -> must REFUSE
UNIQ = b"THE LONE NEEDLE"         # written once  -> must proceed


def _onexc(func, path, exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def run(args, cwd):
    p = subprocess.run(args, cwd=cwd, capture_output=True)
    if p.returncode != 0:
        raise SystemExit("failed %s\n%s" % (args, p.stderr.decode("utf-8", "replace")))
    return p.stdout


def build():
    if os.path.isdir(FIXTURE):
        shutil.rmtree(FIXTURE, onexc=_onexc)
    os.makedirs(FIXTURE)
    run(["git", "init", "-q", "-b", "main"], FIXTURE)
    for k, v in (("user.name", "fixture"), ("user.email", "fixture@example.invalid"),
                 ("core.autocrlf", "false"), ("commit.gpgsign", "false")):
        run(["git", "config", k, v], FIXTURE)
    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = "2020-01-01T00:00:00+00:00"

    def commit(name, body, msg):
        with open(os.path.join(FIXTURE, name), "wb") as fh:
            fh.write(body)
        subprocess.run(["git", "add", name], cwd=FIXTURE, check=True,
                       capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", msg], cwd=FIXTURE,
                       check=True, capture_output=True, env=env)
        return run(["git", "rev-parse", "HEAD"], FIXTURE).decode().strip()

    c0 = commit("p.txt", b"nothing here yet\n", "P0")
    c1 = commit("p.txt",
                b"nothing here yet\n" + UNIQ + b" appears once\n", "P1")
    c2 = commit("p.txt",
                b"nothing here yet\n" + UNIQ + b" appears once\n"
                + AMBIG + b" first site\n" + AMBIG + b" second site\n", "P2")
    return c0, c1, c2


def main():
    print("#" * 78)
    print("# webapp/0410 - PLANTED AMBIGUOUS-NEEDLE CONTROL (synthetic scratch)")
    print("#" * 78)
    c0, c1, c2 = build()
    print("fixture repo %s" % FIXTURE)
    print("  P0 %s  neither needle" % c0)
    print("  P1 %s  the LONE needle arrives (1 site)" % c1)
    print("  P2 %s  the PLANTED needle arrives twice (2 sites)" % c2)
    print()

    print("POSITIVE ARM - the plant is ambiguous, the rule must REFUSE")
    v_amb, n_amb = uniqueness_precheck(FIXTURE, "p.txt", AMBIG, "HEAD")
    print("  -> verdict %s  count %s" % (v_amb, n_amb))
    assert v_amb == "AMBIGUOUS-NEEDLE" and n_amb == 2, (v_amb, n_amb)
    print("  [PASS] planted ambiguous needle: count>=2 -> AMBIGUOUS-NEEDLE REFUSE")
    print()

    print("NEGATIVE ARM - same repo, same rule, a needle planted ONCE")
    v_u, n_u = uniqueness_precheck(FIXTURE, "p.txt", UNIQ, "HEAD")
    print("  -> verdict %s  count %s" % (v_u, n_u))
    assert v_u == "UNIQUE-AT-REF" and n_u == 1, (v_u, n_u)
    print("  [PASS] the precheck is not a refusal machine: 1 site -> proceed")
    print()

    print("ABSENT ARM - a needle planted nowhere")
    v_a, n_a = uniqueness_precheck(FIXTURE, "p.txt", b"NEVER WRITTEN", "HEAD")
    print("  -> verdict %s  count %s" % (v_a, n_a))
    assert v_a == "NEEDLE-ABSENT-AT-REF" and n_a == 0, (v_a, n_a)
    print("  [PASS] 0 sites -> NEEDLE-ABSENT-AT-REF")
    print()
    print("PLANT CONTROL: 3 of 3 PASS")
    print()

    print("#" * 78)
    print("# THE NAIVE CONTRAST - what an -S walk on each BARE needle says")
    print("#" * 78)
    for row in (2, 4, 8, 9):
        label, needle_b, published, _src = PUBLISHED[row - 1]
        hits = log_s(ESTATE, needle_b, CONTESTED)
        naive = hits[0] if hits else None
        agree = "AGREES with published" if naive == published else "DISAGREES with published"
        print("  ROW %-2d %-24r hits=%d naive=%s  %s"
              % (row, needle_b.decode("utf-8")[:24], len(hits), naive, agree))
    print()
    print("A naive reader taking the oldest -S hit on the BARE needle would")
    print("publish the figures above.  Where that DISAGREES with the published")
    print("figure, the dating coupling is live on that needle.")

    shutil.rmtree(FIXTURE, onexc=_onexc)
    print()
    print("fixture removed: %s" % (not os.path.isdir(FIXTURE)))


if __name__ == "__main__":
    main()
