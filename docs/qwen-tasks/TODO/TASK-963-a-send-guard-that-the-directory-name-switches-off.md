# TASK-963 — a send guard that the directory name switches off

## Why

`test_invariants.TestNothingCanSend.test_no_module_issues_an_http_post_outside_the_named_ones`
is one of the tests that says this system cannot send. It scans source text for
`request("POST"` and then excuses a hit like this:

    offenders = [f"{os.path.relpath(p, ROOT)}:{i}" for p, i, _ in issued
                 if not any(a in p for a in allowed)]

`p` is the **absolute path**. `allowed` is the provider names — `aiark`,
`apify`, `blitz`, `bison`, `contactout`, `glm`, `heyreach`, `slack`, `xai`.

So a checkout whose directory name contains one of those substrings exempts
**every file in the repository**, and the guard passes while watching nothing.

**MEASURED, 2026-10-02, on the same file and the same line in three trees:**

| tree | exempted by | verdict |
|---|---|---|
| the main checkout | nothing | **FAILS** |
| `…/scratchpad/wt-lockatomic` | nothing | **FAILS** |
| `…/scratchpad/glm-940` | `['glm']` | **PASSES** |

Run alone on master twice it fails deterministically; run alone in `glm-940` it
passes. `src/providers/__init__.py` is byte-identical in all three (md5
`efa5da11…`, and `git diff` across the two commits is empty), so the input is
the same and only the path differs.

**This is not hypothetical and it has already cost a measurement.** Tonight's
merge gate for TASK-940 ran in a worktree called `glm-940` and reported **230**
failing names against the reference's **231**. The vanished name is this test.
Nothing was fixed: the gate worktree's NAME switched a safety guard off. The
merge itself stands — the rule blocks on NEW names and there were none — but the
"1 GONE" in that record means this, and the merge commit's own wording
(`ae134dd2`) describes the symptom rather than this mechanism, which was
measured afterwards.

## The second half: it was excusing a COMMENT

What the guard flagged in the un-exempted trees is
`src/providers/__init__.py:376`, which is prose:

    #: provider module - `providers.request("POST", "https://send.resonate

`line.lstrip().startswith("#")` is True and the scanner's regex matches it
anyway. CLAUDE.md names this exact failure — "searching source for words
produces a test that fails when somebody writes a comment, which has happened
repeatedly here".

**And the fix already exists, in the other copy.** `tests/test_audit.py` carries
the same scan with `if line.lstrip().startswith("#"): continue` and a comment
citing that rule. `tests/test_invariants.py` does not. Two copies of one scan,
one of them corrected — which is the deeper defect of the pair, because the next
correction will go into one copy too.

`test_audit.py` is NOT safe either: its allowlist is the same
`any(a in p for a in allowed)` over a path.

## What to do, in the order that makes each step provable

1. **Match on the MODULE, not on a substring of the path.** The question the
   allowlist is asking is "is this `src/providers/<name>.py`" — so ask that:
   compare against the path RELATIVE to `ROOT`, split into parts, and require
   the provider name to BE a path component (or the module's stem), never to
   merely occur in the string. `os.path.relpath(p, ROOT)` is already computed one
   line below for the message; the exemption should use the same relative path.
2. **Skip whole-line comments** in `test_invariants.py` as `test_audit.py`
   already does, and then **put the scan in ONE place** that both call, so a
   third correction cannot miss a copy.
3. **Decide what the scan is for.** It reads source text, which this repository
   forbids elsewhere for good reason. If the invariant is "no module outside
   this list reaches the POST transport", the sound form is an import/call-graph
   assertion against `providers.request`, not a regex over lines. That is a
   larger change than 1 and 2 and should not be smuggled in with them — but it
   is the honest end state, and this task should say which it chose.

## Acceptance

```
python -c "import os,subprocess,sys,tempfile; out=subprocess.run([sys.executable,'-m','unittest','tests.test_invariants.TestNothingCanSend.test_no_module_issues_an_http_post_outside_the_named_ones'],capture_output=True,text=True,encoding='utf-8',errors='replace',env=dict(os.environ,PYTHONIOENCODING='utf-8')); print(out.stdout[-200:], out.stderr[-400:]); assert out.returncode==0, 'the guard still fails in a tree named without a provider substring - fix the comment half'"
```

```
python -c "import os,re,sys; sys.path.insert(0,'.'); import tests.test_invariants as t; allowed=('aiark','apify','blitz','bison','contactout','glm','heyreach','slack','xai'); fake=os.path.join('C:',os.sep,'x','glm-940','src','web','api.py'); rel=os.path.relpath(fake, os.path.join('C:',os.sep,'x','glm-940')); parts=set(rel.replace(chr(92),'/').split('/')); stems={p.rsplit('.',1)[0] for p in parts}; assert not (stems & set(allowed)), 'this fixture is wrong'; print('OK a path containing glm-940 exempts nothing when matched on components:', sorted(parts))"
```

### NEGATIVE CONTROL

Command 1 **fails today** — on master, in a directory whose name carries no
provider substring, the guard reports
`['src\\providers\\__init__.py:376'] != []`. That failure IS the comment half of
this defect, so the command cannot pass until it is fixed, and it cannot be made
to pass by renaming anything.

Command 2 is the control on the FIX's direction rather than on today's state: it
asserts that a path containing `glm-940` exempts nothing once the match is on
path COMPONENTS instead of substrings. Run it against the current substring
logic by swapping the assertion for `any(a in fake for a in allowed)` and it
goes the other way — that is the two readings, side by side, on the same string.

**Do not make command 1 pass by adding `src/providers/__init__.py` to an
exemption list.** The line it names is a comment; the fix is to stop reading
comments as code, not to widen the allowlist. Widening it would also silence the
real thing it exists to catch.

## Files

`tests/test_invariants.py`, `tests/test_audit.py`, and wherever the shared scan
ends up living.

## Not in scope

The 230-vs-231 gate record for TASK-940. That merge is landed and its gate was
satisfied on the rule that blocks it — NEW names — of which there were none. The
record is corrected in the defect map (A44) rather than by reopening the merge.
