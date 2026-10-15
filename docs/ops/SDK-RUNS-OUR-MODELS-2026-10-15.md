
---

## TASK 0120 - CAN THE AGENT SDK RUN A LANE ON A NON-ANTHROPIC MODEL? - 2026-10-15 23:30

Measured in `C:\Users\Zvonimir\qwc` at **`9f02ce7f9`**, tree clean before and
after. Nothing was installed into the project; nothing under
`resonate-ops\tools\` or `queue\` was created, edited or copied. No watcher
deployed, started, stopped or restarted. No push, no merge, no master commit.
I read `C:\Users\Zvonimir\Desktop\resonate-ops\queue\_STANDING-RULES.md` by its
absolute path; every file this task names opened.

### THE ANSWER

**SDK RUNS OUR MODELS.** One Agent SDK session, `glm-5.3`, over the lane's own
base URL and token, answered correctly in 5.6 seconds.

### 1. THE MECHANISM `claude -p` USES TODAY - NAMED, AND THE PREMISE DID NOT SURVIVE

It is **not** a flag. `tools\lane_watcher.ps1:287` builds exactly

    /c claude -p --permission-mode <mode> < "<brief>" > "<out>" 2>&1

with **no `--model`**, and `START-ALL-LANES.ps1` passes no model either. The
model comes from a **per-worktree `.claude\settings.local.json` `env` block**,
which Claude Code loads because the watcher sets the lane's worktree as the
working directory. Three variables, by name:

    ANTHROPIC_BASE_URL      host is api.z.ai        (value not printed)
    ANTHROPIC_AUTH_TOKEN    len 49                  (value not printed)
    ANTHROPIC_MODEL         glm-5.3

**The proposal says "six lanes run `glm-5.3`, one runs Qwen". Both halves are
false.** Measured two independent ways at 23:20:

| lane | `.claude\settings.local.json` | lane `.out` files | carry the `glm-5.3` banner |
|---|---|---|---|
| glm | present | 12 | **12** |
| glm-b | present | 15 | **15** |
| glm-c | present | 16 | **16** |
| suppression | **absent** | 12 | 0 |
| pilotcaps | **absent** | 18 | 0 |
| qwen | **absent** | 12 | 0 |
| webapp | **absent** | 4 | 0 |

Three lanes run `glm-5.3`. **Four run the operator's Anthropic account**, via
the claude.ai OAuth login recorded in `~\.claude.json` (`oauthAccount`). The
banner is Claude Code's own `"glm-5.3" is not a model this version ...` line
and it appears in 43 of 43 glm-lane outputs and 0 of 46 others, so this is a
census, not a sample.

**No lane runs Qwen.** There is no Qwen model, base URL or token anywhere:
`ANTHROPIC_*`, `GLM`, `QWEN`, `ZHIPU`, `DASHSCOPE`, `BIGMODEL` and `OPENAI`
are all **unset at Process, User and Machine scope**, and the only model
configuration on this machine is the three files above. "qwen" is the lane's
*name* and the name of its clone (`qwc`); the session answering this brief is
an Anthropic model. **That changes the money in the decision**: four of seven
lanes are already on Anthropic rates today, so the exposure the proposal feared
applies to three lanes, not six.

### 2. DOES THE PYTHON SDK EXPOSE THE SAME MECHANISM? YES, AND BETTER-PLACED

`claude-agent-sdk` **0.2.168**, read from the installed package rather than the
docs. `ClaudeAgentOptions` carries, as dataclass fields:

    env             dict[str, str]
    model           str | None
    settings        str | None
    cli_path        str | pathlib.Path | None
    setting_sources list[Literal['user','project','local']] | None
    permission_mode Literal['default','acceptEdits','plan','bypassPermissions','dontAsk','auto'] | None

`_internal/transport/subprocess_cli.py:819-824` composes the child environment
as `{**inherited, CLAUDE_CODE_ENTRYPOINT, **options.env, CLAUDE_AGENT_SDK_VERSION}`.
`options.env` **overrides** the inherited environment, and the SDK spawns the
same `claude` binary the watcher spawns - so every variable the binary already
honours is honoured, **per session, in the caller's code**, instead of in a
file sitting in the worktree the agent is editing.

### 3. THE PROOF

Disposable scratch: **`%TEMP%\sdkprobe-0120`** (venv + three scripts).
`Remove-Item -Recurse -Force "$env:TEMP\sdkprobe-0120"` erases all of it.
Credentials were read programmatically from
`wt-glm-c-2026-10-14\.claude\settings.local.json` and never printed.

**Control first, zero spend**, because a success proves nothing unless a
failure is possible: same code path, `ANTHROPIC_BASE_URL` pointed at
`http://127.0.0.1:1`.

      Assistant model='<synthetic>'  text='API Error: Connection refused ... (ECONNREFUSED)'
      is_error=True   cost_usd=0

So `options.env` genuinely reaches the binary and redirects it. Had this
answered, the live run would have been a claude.ai session wearing a label.

**Live**, `permission_mode='default'`, `allowed_tools=[]`, `max_turns=1`,
prompt `Reply with exactly: OK`:

      Assistant model='glm-5.3'  text='OK'
      subtype=success  is_error=False  turns=1
      input=13692  cache_read=8512  output=3
      elapsed 5.7s

`model='glm-5.3'` is the **provider's own echo in the assistant message**, not
our request parameter read back.

Command that proves it (from the scratch dir):

    & "$env:TEMP\sdkprobe-0120\venv\Scripts\python.exe" "$env:TEMP\sdkprobe-0120\probe.py"

### 4. COST PER TASK - THE SAME, AND THE USD FIGURE IS NOT THE BILL

Like-for-like, same model, same endpoint, same one-word prompt, same scratch
cwd, SDK configured as the CLI is (`setting_sources=['user','project','local']`,
`claude_code` system-prompt preset, full tool set):

| | input | cache read | output | elapsed |
|---|---|---|---|---|
| `claude -p --output-format json` (today) | 25,691 | 832 | 46 | 128.2s |
| Agent SDK, matched config | 24,144 | 896 | 15 | 5.6s |
| Agent SDK, tools off + no settings | 13,692 | 8,512 | 3 | 5.7s |

Row 2 against row 1 is a 6% difference in input tokens on n=1 - prompt-assembly
noise, not a harness cost. **Same model, same rate, same bill.** Row 3 is the
only real cost finding and it goes the right way: the SDK lets a session drop
tools and settings it does not need, and a lane that does so pays **47% fewer
input tokens** for the same work. The CLI has no comparable per-invocation
control.

**No new billable call classes.** The SDK fires one extra `generate_session_title`
query per session - and so does `claude -p`: that line is in **43 of 43**
existing glm lane `.out` files. It is current cost, not added cost.

**Do not use the reported dollars for attribution.** `claude -p` returned
`total_cost_usd=0.132391` with `"provider":"firstParty"` and
**`"costBasis":"unknown"`** - Claude Code priced `glm-5.3` off a table that
does not contain it. The figure is equally wrong on both paths, so the
comparison stands, but CLAUDE.md's rule that model spend is attributed to a
client or a task cannot be satisfied from this number on either path. The
authority is the z.ai console, which I did not query.

**Latency is n=1 and I am not claiming it.** 128.2s versus 5.6s is a real
observation, almost certainly cold `cmd.exe`/npm-shim start against a warm
in-process spawn, but one sample each is not a measurement of anything.

### WHAT THIS MEANS FOR THE PROPOSAL - AND THE DECISION THAT IS THE OPERATOR'S

The unknown that "decides everything" is closed in the SDK's favour, and the
per-tool permission model the proposal actually wants it for is reachable:
this probe ran at `permission_mode='default'` with `allowed_tools=[]` and the
session completed rather than stalling - the all-or-nothing
`bypassPermissions` every lane uses today is not forced by the SDK.

**For the operator, with my recommendation, not waiting on his answer:**
the proposal's model-cost risk was overstated by half (three glm lanes, not
six, and no Qwen lane at all), and understated in one place it did not look -
**`ANTHROPIC_AUTH_TOKEN` sits in plaintext in three worktrees'
`.claude\settings.local.json`**, which is how the model gets selected today.
Under the SDK that credential moves into the dispatcher process and out of the
tree the agent is editing. I recommend the proposal proceed as written -
`webapp` first, after the four exit criteria - and that the token's location be
treated as a separate finding. I have **not** moved, rotated or printed it.

### FILED, UNDONE AND NOT RE-QUEUED

- The plaintext `ANTHROPIC_AUTH_TOKEN` in three `.claude\settings.local.json`
  files. Named here; no file written for it.
- Real per-task spend in the z.ai console, which is the only authority for what
  three lanes actually cost. Not queried - no task names that call.

Nothing this run started is still running. The scratch venv is inert files
under `%TEMP%`. No provider, Apify or Slack call; no campaign read or written;
no suite run and `work/suite.lock` not taken; no worktree created or removed;
no other lane's tree written - `wt-glm-c-2026-10-14\.claude\settings.local.json`
was **read** and not modified.

**SDK RUNS OUR MODELS**
