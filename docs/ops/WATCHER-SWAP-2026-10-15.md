# The lane watcher tree-kill swap - paste-ready, NOT RUN

qwen TASK 0090, 2026-10-15. Produced by a session running **inside** the qwen
lane, with all seven lanes live. **Nothing in this document has been run, and no
running watcher was restarted, stopped or edited.**

Measured on `qwc` branch `task-qwen-0090-watcher-treekill-2026-10-15`, parent
`74fad6c2f`. The deployed file this patch was derived from:

    C:\Users\Zvonimir\Desktop\resonate-ops\tools\lane_watcher.ps1
    sha256 35d1a82051d091406f683d88daedcd45cb276a8210503bc2f344d7ce8c3c58e4
    242 lines, mtime 2026-10-15 03:44

**If that hash no longer matches, STOP.** Somebody has changed the watcher since
21:40 and this patch was built against bytes that no longer exist. Re-derive it.

## What it changes, and why it is two commits

    step 1   the timeout kills the TASK instead of the wrapper      (commit 1)
    step 2   -TaskTimeoutMinutes default 90 -> 150                  (commit 2)

In that order, and the order is the whole point. The 90-minute timeout does not
currently stop anything: measured 2026-10-15, it kills the `cmd.exe` wrapper and
leaves `claude` running, which kept working for 23 seconds in one case and 27
minutes in another, and both tasks finished. Raising the timeout first would only
postpone the same silent death. Fixing the kill without raising the timeout would
start genuinely killing two-leg suite tasks that would otherwise have finished -
glm 0065's two legs alone measured 2267.7s + 2355.3s = 77 minutes of suite,
inside the current 90 and with no room for the reading, diffing and writing
around them.

## Step 0 - the interlock

A gate with no re-check races. Re-read the hash at the moment you swap, not when
you read this.

    cd /d C:\Users\Zvonimir\Desktop\resonate-ops
    certutil -hashfile tools\lane_watcher.ps1 SHA256
    REM expected: 35d1a82051d091406f683d88daedcd45cb276a8210503bc2f344d7ce8c3c58e4

## Step 1 - copy two files in. NO LANE NEEDS TO BE DOWN FOR THIS.

The patch is two files, not one: the kill lives in `tools\lane_treekill.ps1`
because a test has to be able to call it, and the watcher takes mandatory
parameters and then loops forever, so a test cannot dot-source the watcher
itself.

    cd /d C:\Users\Zvonimir\Desktop\resonate-ops
    copy tools\lane_watcher.ps1 tools\lane_watcher.ps1.pre-0090
    copy /y C:\Users\Zvonimir\qwc\docs\ops\lane_treekill.ps1 tools\lane_treekill.ps1
    copy /y C:\Users\Zvonimir\qwc\docs\ops\lane_watcher.ps1  tools\lane_watcher.ps1
    certutil -hashfile tools\lane_watcher.ps1   SHA256
    certutil -hashfile tools\lane_treekill.ps1  SHA256

**Both copies are safe with all seven lanes running, and that is measured rather
than assumed.** A probe script was replaced on disk three seconds into an
eight-second sleep; the write was not refused, and the running process executed
the OLD text for the rest of its life:

    rewrote the script on disk 3s into an 8s sleep (replace succeeded: True)
    what the running process printed:   FIRST LINE: version A
                                        SECOND LINE: version A
    what is on disk now:                Write-Host "FIRST LINE: version B"

Windows PowerShell 5.1 parses a `-File` script completely at launch and never
re-reads it. So:

- no running watcher is disturbed by the copy, and no in-flight task is at risk;
- `lane_treekill.ps1` is referenced by no running watcher at all, because the
  version they are running does not mention it;
- **and nothing starts behaving differently until a watcher is restarted.**

## Step 2 - take the fix, one lane at a time, WITHOUT interrupting a task

The watcher tests `STOP-ALL` and `STOP-<lane>` at the TOP of its loop, so a STOP
file lets the current task run to completion and exits the watcher cleanly
afterwards. That releases the lane's pid lock, because `START-ALL-LANES.ps1`
dropped `-NoExit` at 21:00 today and the window now closes with the script.

For one lane:

    cd /d C:\Users\Zvonimir\Desktop\resonate-ops
    echo swap-0090 > STOP-glm-b
    REM Wait. The lane finishes its current task, logs "STOP-glm-b present.
    REM Exiting." and "watcher down.", and the window closes.
    type logs\watcher-glm-b.log | find "watcher down"
    REM Confirm the process is really gone before deleting the STOP file:
    powershell -NoProfile -Command "$p=(Get-Content logs\watcher-glm-b.pid).Trim(); Get-CimInstance Win32_Process -Filter \"ProcessId=$p\" | Select-Object ProcessId,Name,CreationDate"
    REM Expect NOTHING. Then:
    del STOP-glm-b
    powershell -ExecutionPolicy Bypass -File tools\lane_watcher.ps1 -Lane glm-b ^
      -Worktree C:\Users\Zvonimir\Desktop\wt-glm-b-2026-10-14 ^
      -PermissionMode bypassPermissions

The new watcher logs its own proof of pickup on the way up - a line the current
one cannot produce:

    REFUSING: the tree-kill module is missing: ...    <- if you forgot step 1
    watcher up. tree=... mode=... timeout=90m         <- step 1 only
    watcher up. tree=... mode=... timeout=150m        <- step 1 + step 2

### WHICH LANES HAVE TO BE DOWN, AND FOR HOW LONG

**For the file copy: none, for zero seconds.** Measured above.

**For taking the fix: each lane individually, and no task is ever interrupted.**
The downtime for a lane is the gap between its current task ending and the
operator starting it again - seconds, if the two commands are pasted together.
What you WAIT for is the current task to finish, which is bounded by the
timeout, so up to 90 minutes per lane in the worst case. The lanes do not have
to be down together and there is no moment at which the estate is idle.

Lane state measured 2026-10-15 21:3x-22:1x, all seven started 21:07:08, all
seven mid-task:

    glm          85960   0067-ceiling-on-the-composed-body.md
    glm-b        79568   0110-land-the-company-name-derivation.md
    glm-c        86716   0160-fix-the-resume-role.md
    pilotcaps    78160   0140-certify-d3-and-its-test.md
    suppression  45176   0100-apply-the-three.md
    webapp       31148   0010-the-map-nobody-has.md
    qwen         66028   0090-the-watcher-fix-in-your-order.md   <- THIS TASK

**qwen is the one lane that cannot be swapped by a session in it.** This task is
`claude` running under cmd 80556 under watcher 66028; stopping that watcher ends
this task. Do qwen last, after this task has left RUNNING.

**A cheaper option for six of the seven: do nothing and let them exit.** Every
lane's watcher exits by itself after three consecutive failures or an empty
queue plus a STOP file, and the fix is only needed when a task actually
overruns. There is no reason to hurry a lane that is working.

## Rollback

    cd /d C:\Users\Zvonimir\Desktop\resonate-ops
    copy /y tools\lane_watcher.ps1.pre-0090 tools\lane_watcher.ps1
    REM leave tools\lane_treekill.ps1 in place: the old watcher never reads it.
    REM Then restart the affected lane as in step 2.

Rollback is per-lane and takes effect on the next restart, for the same measured
reason the swap does.

## What is proven, and what is not

**Proven, by `docs\ops\test_lane_watcher_treekill.ps1` (eight legs, all green)
and `docs\ops\mutate_lane_treekill.py` (five mutations, each turning its named
leg red):** the kill reaches children and grandchildren; it reaches an orphan
that `taskkill /T` provably cannot see; it refuses a root that is the caller or
an ancestor of the caller; it never selects a process by command-line substring,
and a substring filter is measured matching its own shell in the same run; it
leaves a live process whose pid matches but whose creation time does not.

**Not proven: the watcher's own wiring has not been executed end to end.** The
kill module is tested directly, the patched watcher parses clean and its
`-Say ${function:Log}` plumbing is checked, but no task has been run under the
patched watcher and timed out, because `$Ops` is a hardcoded path to the live
`resonate-ops` and the task command is a hardcoded `claude -p`. Running it would
mean running it against the real queue. **The first real timeout under the
patched watcher is the measurement that closes this**, and the line to look for
is `KILL VERIFIED: 0 of N still alive`.

Filed, not done, because it is a change rather than a measurement: making
`$Ops` and the task command injectable would let the whole loop be tested
against a throwaway root. That is the right next task for this file and it is
not this one.
