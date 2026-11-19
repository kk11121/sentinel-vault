#!/usr/bin/env python3
"""Durable manager for the Sentinel Vault verdict worker.

Replaces the old /tmp helper (wiped by VM restarts). Lives in the repo so
the restart procedure survives restarts. Usage:

    python3 scripts/wmanage.py status   # list worker PIDs
    python3 scripts/wmanage.py start    # start detached if not running
    python3 scripts/wmanage.py stop     # SIGTERM the worker

The worker is started with the repo venv's python, detached (setsid),
with stdout/stderr appended to worker/worker.log. The process needle is
built from split strings so this script (and any shell invoking it) never
matches itself when scanning or signalling processes.
"""
import os
import signal
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEEDLE = "worker/" + "worker.py"
VENV_PY = os.path.join(ROOT, ".venv", "bin", "python")
LOG = os.path.join(ROOT, "worker", "worker.log")


def find_pids():
    pids = []
    out = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True,
                         text=True).stdout
    for line in out.splitlines()[1:]:
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        pid, args = parts
        if NEEDLE in args and ROOT in args or (NEEDLE in args and "python" in args):
            if "wmanage" not in args:
                pids.append(int(pid))
    return pids


def status():
    pids = find_pids()
    if pids:
        print("running:", " ".join(str(p) for p in pids))
    else:
        print("not running")
    return 0


def start():
    pids = find_pids()
    if pids:
        print("already running:", " ".join(str(p) for p in pids))
        return 0
    py = VENV_PY if os.path.exists(VENV_PY) else sys.executable
    target = os.path.join(ROOT, NEEDLE)
    log = open(LOG, "ab")
    proc = subprocess.Popen(
        [py, target], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, start_new_session=True)
    print("started pid", proc.pid)
    return 0


def stop():
    pids = find_pids()
    if not pids:
        print("not running")
        return 0
    for pid in pids:
        os.kill(pid, signal.SIGTERM)
        print("sent SIGTERM to", pid)
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    fn = {"status": status, "start": start, "stop": stop}.get(cmd)
    if fn is None:
        print("usage: wmanage.py [status|start|stop]")
        sys.exit(2)
    sys.exit(fn())
