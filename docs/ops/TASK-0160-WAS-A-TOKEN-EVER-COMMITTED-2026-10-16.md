# TASK 0160 — was a token ever committed? **NO.**

Measured 2026-10-16 on `qwc` at **`22b64311e`** (branch
`task-qwen-0090-watcher-treekill-2026-10-15`, CRLF tree) and on
`Desktop\resonate-group-automation` at **`87fa57080`** (branch
`task-sandbox-phase2-horizon`, LF tree). `origin/master` was
**`b1f290c847eb2500b7eb39987ac34f6d6a8d00d2`** throughout, unchanged.

No credential or any part of one is printed below. No length, no prefix, no
character count of any value. Nothing was written to, moved or rotated.

---

## THE ANSWER

**No `.claude/settings.local.json` has ever been tracked, in any repository on
this machine, on any ref, at any time. No credential VALUE of any recognised
shape exists in any object store, referenced or not.**

The variable **name** `ANTHROPIC_AUTH_TOKEN` *is* in history, in three commits,
two of which are pushed. Names are not secrets and the operator's own rule is
that the name is what gets recorded. That is the whole exposure in git, and it
is the intended one.

## FOUR REPOSITORIES, NOT TWO

The estate is **four distinct object stores**, resolved by
`git rev-parse --path-format=absolute --git-common-dir` rather than by folder
name — `Desktop\resonate-infra`, `resonate-skills`, `resonate-slack-agent`, all
nine `resonate-trees\*`, every `resonate-qwen-*` and both `glm-review\*` trees
are **worktrees of `resonate-group-automation`**, so one history query covers
all of them. `Desktop\resonate-ops` is **not a git repository at all**.

| store | commits | refs |
|---|---|---|
| `Desktop\resonate-group-automation\.git` | 9,620 | 2,423 |
| `qwc\.git` | 4,119 | 508 |
| `Desktop\resonate-os-demo\.git` | 1,615 | 181 |
| `Desktop\buggie-skill\.git` | 6 | 3 |

`resonate-group-automation` declares **276 worktrees**, of which about **230
still exist on disk**. They share one object store, which is why the history
result is one measurement and not 230.

## 1. IS IT IGNORED, IN EVERY TREE?

The file exists in **75 places, not three.** 0120 said three; three is the count
of files that *hold the token*, and that part of 0120 stands. The other 72 are
Claude Code's own per-agent worktrees and hold permissions only.

    main checkout                                  1
    .claude\worktrees\agent-*  (nested worktrees)  71
    wt-glm-review / wt-glm-b / wt-glm-c            3
                                                  ---
                                                  75

`git check-ignore -v --no-index .claude/settings.local.json`, run **from inside
each of those 75 trees** and from `qwc`, `resonate-os-demo` and `buggie-skill`:

    trees where the file exists            : 75
    trees where it is NOT ignored          : 0
    rule that catches it, in all 75        : .gitignore:78:.claude/settings.local.json

**There is no per-tree divergence.** The rule is in the *tracked* `.gitignore`,
so it travels with the checkout; that is why it cannot be present in one tree
and absent in another the way a `.git/info/exclude` rule could.

The nested case — the shape that actually bites here — is covered separately
and deliberately. From the **main checkout**, `.claude/worktrees/agent-X/...`
is a path like any other, and `.gitignore:78` is directory-anchored so it would
**not** match `.claude/worktrees/agent-X/.claude/settings.local.json`. It is
caught by a second rule:

    .gitignore:82:.claude/worktrees/

whose own comment says why: *"Each is a FULL checkout of this repository, so
leaving them trackable means one `git add -A` commits a dozen copies of the
tree."* Confirmed by consequence, not by reading the rule:

    git status --porcelain -uall -- .claude/worktrees/   ->  0 paths

**One correction to a reading a future session will make.** `git check-ignore -v
--no-index .claude/` exits 0 and reports `.gitignore:99:` with an **empty
pattern**. Line 99 of `.gitignore` is a bare newline. It is a git reporting
artefact for a trailing-slash directory argument, **not a rule**:

    .claude                 -> exit 1   NOT ignored
    .claude/settings.json   -> exit 1   NOT ignored

So **`.claude/` is not blanket-ignored.** Only line 78 (the one file) and line
82 (the nested worktrees) protect anything. Anyone who concludes from that
exit-0 that the whole directory is covered will be wrong, and would then be
free to drop a second credentialled file beside it.

## 2. HAS IT EVER BEEN TRACKED?

Both the live-path query and the did-it-ever-get-added query, on all refs **and
the reflog**, at any depth, in all four stores:

    git log --all --reflog --full-history --oneline -- \
        '.claude/settings.local.json' '*/.claude/settings.local.json' '*settings.local.json'
    git log --all --reflog --full-history --diff-filter=A --name-only -- '*settings*.json'
    git ls-files '.claude*'

**Empty in all four stores. `git ls-files '.claude*'` returns 0 in all four.**

Also checked, because "absent from history" is weaker than "absent from the
repository": the main checkout's **index** (nothing staged), its **one stash
entry** (`stash@{0}`, WIP on `qwen-worker-5-r9`, no `.claude` path), and the
**whole object store including unreferenced objects** — see section 3.

## 3. SEARCH HISTORY FOR THE VARIABLE NAME

The three files hold exactly three keys. Harvested by pattern from the files
themselves rather than assumed, so the list cannot be short by habit:

    ANTHROPIC_AUTH_TOKEN
    ANTHROPIC_BASE_URL
    ANTHROPIC_MODEL

**`ANTHROPIC_AUTH_TOKEN` is the only auth-shaped name.** No other `*TOKEN`,
`*KEY`, `*SECRET`, `*PASSWORD`, `*CREDENTIAL` or `*AUTH` name appears in any of
the 75 files. The 72 non-glm files contain **no `env` block and no uppercase
key at all** — measured, 0 of 72.

`git log --all --reflog --full-history -S'ANTHROPIC_AUTH_TOKEN'` —
**three commits, all of them the name in prose or as a dict key:**

| commit | date | file | what it is | on `origin/master`? |
|---|---|---|---|---|
| `09e8e3ada` | 2026-10-15 23:17 | `docs/ops/SDK-RUNS-OUR-MODELS-2026-10-15.md` + 3 probe scripts | my own 0120 | no — lane branch, **pushed** |
| `ab839435c` | 2026-10-15 23:32 | `docs/TASK-0130-WHAT-A-LANE-DAY-COSTS-2026-10-15.md` | my own 0130 | no — lane branch, **pushed** |
| `e22e82564` | 2026-10-14 23:05 | `docs/HANDOFF-2026-10-14.md` | handoff prose | no — **local branch only** (`task-campaign-skeleton-review-2026-10-14`) |

`09e8e3ada` has four assignment-shaped occurrences. All four are the name used
as a **dict key**, with an identifier on the value side:

    "<KEY>": TOKEN,  "<KEY>": MODEL      "<KEY>": cfg["<KEY>"]

and `TOKEN` / `BASE` / `cfg` all resolve, in the committed blobs, to
`cfg = json.load(open(SETTINGS))["env"]` — the scripts **read the token from
disk at run time**. No literal. Independently: **zero** value-shaped strings in
the added lines of all three commits.

### the object store, not just the history

`git cat-file --batch-all-objects --batch` over **every object, referenced or
not** — 14,866 blobs in `resonate-group-automation`, the full store in `qwc`:

    ANTHROPIC_AUTH_TOKEN                                     15   consistent with the 3 commits above
    sk-ant-...                                                0
    sk-or-v1-...                                              0
    gsk_...                                                   0
    ghp_ / gho_ / ghu_ / ghs_ / github_pat_                   0
    AKIA...                                                   0
    the 32 + dot + 16 dotted-key form (strict, both bounds)   0
    xoxb-...                                                  1   explained below

`-G` pickaxe for the same shapes across all refs + reflog in all four stores
returns the same: two commits in `resonate-group-automation`, none anywhere
else.

**The `xoxb-` hit is a deliberate canary, and the history around it is a credit
to the repo rather than a defect.** At `51ca1382b` (2026-08-28 17:24),
`tests/test_tenancy_penetration.py` planted four shaped fakes — its siblings are
visibly `canary5igningsecret0000deadbeef`, `co_live_CANARYCONTACTOUTKEY`,
`apify_api_CANARYAPIFYTOKEN`. None matches a real provider format. **58 minutes
later**, `bd692e5f6` rewrote them to be joined from parts at run time, with the
comment: *"The repository scans its own tracked files for credential-shaped
strings and fails on them. That scanner is right, and a canary written as
`xoxb-...` in this file would be a real finding in the shape of a test
fixture."* What sits on `origin/master` today is that sentence — the literal
text `xoxb-...` inside a comment. Not a credential.

The two remaining dotted-form matches, chased to the object, are both
`raw_suite.txt` log lines: a long unittest class path in
`test_cadence_replies.<class>.test_it_says_why`. Not credentials.

## 4. IF A HIT EXISTS

No hit on a value exists, so there is nothing to name and no decision to leave.
**Nothing was rotated, moved, rewritten or force-pushed, and nothing needed to
be.** Three things are worth the operator's eye anyway, and none is urgent.

**(a) My own 0120 committed a hint, and it is pushed.**
`docs/ops/SDK-RUNS-OUR-MODELS-2026-10-15.md` at `09e8e3ada` records the token's
**length** on the same line as its name. This task's own brief says a length is
a hint and must not be printed, and 0120 printed one — while writing *"value
not printed"* beside it. It is on `origin/<lane branch>`, not on
`origin/master`. It narrows a brute-force search by a negligible amount on its
own and it is not a reason to rewrite history, which is forbidden.
**Recommendation: leave it, and delete the length in a future ordinary edit to
that file, with no rewrite.** I did not edit it — history rewrite is forbidden
and an ordinary content edit was not this task's licence.

**(b) The committed probe scripts hardcode the path to the live secret.**
`docs/ops/sdk_model_probe*.py` contain the absolute path
`wt-glm-c-2026-10-14\.claude\settings.local.json`. That is a map to where the
credential lives, and it is pushed. It matters **only if this repository is or
becomes public**, which I did not determine: `gh repo view` is a network call
and no task names one. **Repository visibility is UNKNOWN. The authority is the
GitHub repository settings page for `KatoKhan8/resonate-group-automation`, or
`gh repo view --json visibility`, and nothing on this disk can answer it.**

**(c) `buggie-skill` has no ignore rule for the file** (`check-ignore` exit 1).
It also has no `.claude/settings.local.json`, six commits and three refs. A
latent gap, not an exposure. Filed, not fixed.

---

## WOULD THE SDK CLOSE THIS, OR ONLY MOVE IT?

**Only move it — and the move is still worth making, because it takes the
credential from three places to one and out of the blast radius of the thing
most likely to leak it.** Today the token sits in three worktrees that agents
hold write access to and edit all day, and the only protection is a single
`.gitignore` line in a tracked file — which means an agent that regenerates,
reorders or inadvertently narrows `.gitignore` removes the one barrier, with the
secret sitting inside the directory git is walking. Under the SDK the token
lives in the dispatcher's own process environment, so it is outside every tree
an agent edits and outside anything `git add` can reach: a real reduction, and
it takes that `.gitignore` line off the critical path. But a process environment
is not a secret store. It is readable by anything running as this user, it is
inherited by every child the dispatcher spawns — which is precisely the agents
we just moved it away from, unless the dispatcher scrubs it from the child
environment, and that is a thing to **verify rather than assume** — and it lands
in a crash dump and in any debug path that prints its own environment. The
exposure that closes is "a secret in a git working tree". The exposure that
remains is "a secret in plaintext in process memory and in whatever the
dispatcher logs", and nothing about the SDK closes that. **Closing it needs a
credential store or an injected short-lived token, which is separate work and
is not what the SDK migration buys.**

---

## METHOD NOTES

- Every value-bearing string in this run was classified by **boolean or count**,
  never printed. Where a line had to be shown at all, quoted strings and long
  character runs were masked by `sed` before the line reached output.
- The first object-store scan **over-reported**, and the disagreement is the
  reason it is trustworthy now. My `awk` regex silently dropped the leading
  word-boundary assertion the `grep` version had, so a 48-character run anywhere
  inside a longer token matched and about 100 objects came back, where the
  strict form gives **0**. Both were run; the strict one is the measurement, and
  the loose one was chased down to the object to prove the difference was log
  noise and not a miss. A count that disagrees with another count is a question,
  not a result.
- `git log --all` does **not** cover unreachable commits. Every history query
  here was run as `--all --reflog --full-history`, and the object-store scan was
  then run on top, because even that does not cover a blob that was `git add`ed
  and never committed.
- `tasklist`-class pitfalls avoided: no measurement's stderr was sent to
  `/dev/null`, and every repository was identified by its resolved
  `--git-common-dir` rather than by its folder name — which is what revealed
  that eleven differently-named folders are one repository.

**ANSWER: NO. The file was never tracked and no credential value is in any
object store. The variable NAME is in three commits, two of them pushed to a
lane branch, and that is intended.**
