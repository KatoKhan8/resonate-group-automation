"""Bounded supervision for a trusted Python child; no network/grant/credential CLI.
Not a process-tree sandbox. Trusted child must not spawn descendants.
"""
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time


class ChildRefused(RuntimeError):
    def __init__(self, code, pid=None, reaped=False):
        super().__init__(code)
        self.pid, self.reaped = pid, reaped


def run_trusted_child(command, payload=b'', *, timeout_seconds=30, max_stdout=2097152):
    if (type(command) is not list or not 2 <= len(command) <= 16
            or any(type(x) is not str or not x or len(x) > 4096 or '\0' in x for x in command)
            or not Path(command[0]).is_absolute() or Path(command[0]).resolve() != Path(sys.executable).resolve()
            or type(payload) is not bytes or len(payload) > 65536
            or type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 30
            or type(max_stdout) is not int or not 1 <= max_stdout <= 2097152):
        raise ChildRefused('CHILD_INPUT_BOUND')
    # Fixed allowlist: no provider/model/auth keys or Python startup overrides.
    allowed = {'SYSTEMROOT','WINDIR','TEMP','TMP','PATH','PATHEXT','COMSPEC'}
    env = {k:v for k,v in os.environ.items() if k.upper() in allowed}
    deadline = time.monotonic() + timeout_seconds
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, env=env, shell=False,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        start_new_session=os.name != 'nt')
    data, faults = bytearray(), []
    def kill():
        try:
            if os.name != 'nt': os.killpg(proc.pid, signal.SIGKILL)
            elif proc.poll() is None: proc.kill()
        except ProcessLookupError: pass
    def read():
        try:
            while True:
                part = proc.stdout.read(min(65536, max_stdout + 1 - len(data)))
                if not part: break
                data.extend(part)
                if len(data) > max_stdout:
                    faults.append('CHILD_OUTPUT_BOUND');kill();break
        except Exception:
            faults.append('CHILD_OUTPUT_FAILURE');kill()
    def write():
        try:
            proc.stdin.write(payload);proc.stdin.close()
        except Exception:
            faults.append('CHILD_INPUT_FAILURE');kill()
    reader = threading.Thread(target=read, daemon=True)
    writer = threading.Thread(target=write, daemon=True)
    try:
        reader.start();writer.start()
        try: proc.wait(timeout=max(0.001, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            faults.append('CHILD_DEADLINE');kill();proc.wait(timeout=2)
        for thread in (reader, writer): thread.join(timeout=max(0, deadline - time.monotonic()))
        if reader.is_alive() or writer.is_alive():
            faults.append('CHILD_PIPE_UNCERTAIN');kill()
            for thread in (reader, writer): thread.join(timeout=0.5)
        if faults or proc.returncode != 0 or time.monotonic() > deadline:
            raise ChildRefused(faults[0] if faults else 'CHILD_EXIT_OR_DEADLINE', proc.pid, proc.poll() is not None)
        return bytes(data)
    except BaseException:
        kill()
        if proc.poll() is None: proc.wait(timeout=2)
        raise
    finally:
        # Closing a live reader's buffered handle can itself block on its lock.
        # A descendant holding a pipe violates the trusted-child contract.
        if not reader.is_alive(): proc.stdout.close()
        if not writer.is_alive(): proc.stdin.close()
