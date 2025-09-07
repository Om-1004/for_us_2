#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Auto Git Push (heartbeat edition)
---------------------------------
- Always writes/updates .autopush_heartbeat.txt so there's something to commit.
- Auto-initializes git if needed.
- Auto-adds 'origin' if REMOTE_URL is provided.
- Ensures upstream and pushes on every cycle.

ENV (optional):
- REPO_PATH=/absolute/path                (default: current working dir)
- BRANCH_NAME=main                        (default: auto-detect, else 'main')
- AUTOPUSH_INTERVAL=14400                 (seconds; default 4 hours)
- GIT_USER_NAME="Om-1004"                 (git config --global)
- GIT_USER_EMAIL="opatel101004@gmail.com" (git config --global)
- REMOTE_URL="https://github.com/USER/REPO.git"  (or SSH URL)
"""

import os
import time
import subprocess
from pathlib import Path
from datetime import datetime

# ----------------------------
# Config
# ----------------------------
# Default is now 4 hours = 14400 seconds
SLEEP_DURATION = int(os.getenv("AUTOPUSH_INTERVAL", "14400"))
REPO_PATH = os.path.abspath(os.getenv("REPO_PATH", os.getcwd()))
BRANCH_NAME_ENV = os.getenv("BRANCH_NAME", "").strip() or None
REMOTE_URL = os.getenv("REMOTE_URL", "").strip() or None

GIT_USER_NAME = os.getenv("GIT_USER_NAME", "Om-1004")
GIT_USER_EMAIL = os.getenv("GIT_USER_EMAIL", "opatel101004@gmail.com")

HEARTBEAT_FILE = ".autopush_heartbeat.txt"

# ----------------------------
# Helpers
# ----------------------------
def run(cmd, cwd=None, check=True):
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd, text=True, capture_output=True, check=check)
        return r.stdout.strip(), True
    except subprocess.CalledProcessError as e:
        msg = (e.stdout or e.stderr or str(e)).strip()
        return msg, False

def is_git_repo(path):
    out, ok = run("git rev-parse --is-inside-work-tree", cwd=path, check=False)
    return ok and out.lower() == "true"

def git_config_global():
    run(f'git config --global user.name "{GIT_USER_NAME}"', check=False)
    run(f'git config --global user.email "{GIT_USER_EMAIL}"', check=False)

def get_branch(path):
    out, ok = run("git rev-parse --abbrev-ref HEAD", cwd=path, check=False)
    if ok and out and out != "HEAD":
        return out
    out2, ok2 = run("git symbolic-ref --short HEAD", cwd=path, check=False)
    return out2 if ok2 and out2 else None

def checkout_or_create_branch(path, branch):
    _, ok = run(f"git rev-parse --verify {branch}", cwd=path, check=False)
    if ok:
        _, ok2 = run(f"git checkout {branch}", cwd=path, check=False)
        return ok2
    _, has_remote = run(f"git ls-remote --heads origin {branch}", cwd=path, check=False)
    if has_remote:
        _, ok3 = run(f"git checkout -b {branch} --track origin/{branch}", cwd=path, check=False)
        return ok3
    _, ok4 = run(f"git checkout -b {branch}", cwd=path, check=False)
    return ok4

def ensure_repo(path, branch_fallback="main"):
    if not is_git_repo(path):
        print(f"Git not found in {path}. Initializing...")
        out, ok = run("git init", cwd=path, check=False)
        if not ok:
            print("Failed to init git:", out)
            return False
        run("git add -A", cwd=path, check=False)
        run('git commit -m "Initial commit"', cwd=path, check=False)
    branch = get_branch(path) or branch_fallback
    checkout_or_create_branch(path, branch)
    return True

def ensure_origin(path):
    out, ok = run("git remote get-url origin", cwd=path, check=False)
    if ok and out:
        return True
    if not REMOTE_URL:
        print("No 'origin' remote and REMOTE_URL not set. Set REMOTE_URL to add remote automatically.")
        return False
    print(f"Adding origin -> {REMOTE_URL}")
    run("git remote remove origin", cwd=path, check=False)
    out, ok = run(f"git remote add origin {REMOTE_URL}", cwd=path, check=False)
    if not ok:
        print("Failed to add origin:", out)
        return False
    return True

def ensure_upstream(path, branch):
    _, ok = run(f"git rev-parse --abbrev-ref {branch}@{{upstream}}", cwd=path, check=False)
    if ok:
        return True
    _, push_ok = run(f"git push -u origin {branch}", cwd=path, check=False)
    return push_ok

def heartbeat(path):
    p = Path(path) / HEARTBEAT_FILE
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = f"[auto-push heartbeat] {now}\n"
    with p.open("a", encoding="utf-8") as f:
        f.write(payload)

def commit_and_push(path, branch):
    run("git add -A", cwd=path, check=False)
    msg = f'git commit -m "Auto-commit: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"'
    out, ok = run(msg, cwd=path, check=False)
    _, push_ok = run(f"git push origin {branch}", cwd=path, check=False)
    return push_ok

def get_repo_url(path):
    out, ok = run("git config --get remote.origin.url", cwd=path, check=False)
    return out if (ok and out) else "Unknown"

# ----------------------------
# Main
# ----------------------------
def main():
    print("Starting auto-push script (heartbeat mode, 4-hour interval)...")
    print(f"Local path: {REPO_PATH}")
    if not os.path.isdir(REPO_PATH):
        print(f"Error: Path does not exist: {REPO_PATH}")
        return

    git_config_global()
    if not ensure_repo(REPO_PATH):
        return

    branch = BRANCH_NAME_ENV or get_branch(REPO_PATH) or "main"
    if BRANCH_NAME_ENV:
        checkout_or_create_branch(REPO_PATH, BRANCH_NAME_ENV)
        branch = get_branch(REPO_PATH) or branch

    if not ensure_origin(REPO_PATH):
        print("Tip: export REMOTE_URL=https://github.com/USER/REPO.git")
    if not ensure_upstream(REPO_PATH, branch):
        print(f"Warning: could not set upstream for '{branch}'. Check credentials/remote.")

    print(f"Repository: {get_repo_url(REPO_PATH)}")
    print(f"Branch: {branch}")
    print(f"Interval: {SLEEP_DURATION} seconds ({SLEEP_DURATION/3600:.1f} hours)")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"{now}: Writing heartbeat, committing, pushing...")
            heartbeat(REPO_PATH)
            if commit_and_push(REPO_PATH, branch):
                print("✓ Pushed.")
            else:
                print("✗ Push failed (check remote/credentials).")
            print(f"Sleeping {SLEEP_DURATION}s...\n")
            time.sleep(SLEEP_DURATION)
    except KeyboardInterrupt:
        print("\nStopping auto-push script...")

if __name__ == "__main__":
    main()
