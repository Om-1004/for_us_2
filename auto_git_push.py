#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Auto Git Push Script (Om edition)
---------------------------------
Watches a repo for changes and periodically commits + pushes them.

Features
- Auto-init Git repo if missing (optional remote attach & first push)
- Auto-detect current branch (fallback to env or 'main')
- Ensures upstream is set (handles first push)
- Clear logs and safe error handling
- Fully configurable via env vars

Environment Variables (all optional)
- REPO_PATH:           Absolute path to repo (default: current working dir)
- BRANCH_NAME:         Branch to use (default: auto-detect, then 'main')
- AUTOPUSH_INTERVAL:   Seconds between checks (default: 60)
- GIT_USER_NAME:       Git user.name (default: "Om-1004")
- GIT_USER_EMAIL:      Git user.email (default: "opatel101004@gmail.com")
- REMOTE_URL:          If set AND repo not yet a git repo, add as origin & do first push
- CREATE_GITIGNORE:    If "1", create a simple .gitignore on init (default: "1")
- GITIGNORE_EXTRA:     Extra lines to append to .gitignore (newline-separated)

Examples
- export REPO_PATH="$HOME/Desktop/for_us_folder"
- export AUTOPUSH_INTERVAL=43200          # 12 hours
- export BRANCH_NAME=dev
- export REMOTE_URL="https://github.com/Om-1004/your-repo.git"

Run
- python3 auto_git_push.py
"""

import os
import time
import subprocess
from datetime import datetime
from pathlib import Path


# ----------------------------
# Configuration (with env vars)
# ----------------------------
DEFAULT_SLEEP = 60  # seconds
SLEEP_DURATION = int(os.getenv("AUTOPUSH_INTERVAL", DEFAULT_SLEEP))
REPO_PATH = os.path.abspath(os.getenv("REPO_PATH", os.getcwd()))
BRANCH_NAME_ENV = os.getenv("BRANCH_NAME", "").strip() or None

GIT_USER_NAME = os.getenv("GIT_USER_NAME", "Om-1004")
GIT_USER_EMAIL = os.getenv("GIT_USER_EMAIL", "opatel101004@gmail.com")

REMOTE_URL = os.getenv("REMOTE_URL", "").strip() or None
CREATE_GITIGNORE = os.getenv("CREATE_GITIGNORE", "1").strip() == "1"
GITIGNORE_EXTRA = os.getenv("GITIGNORE_EXTRA", "")

DEFAULT_GITIGNORE = """\
__pycache__/
*.log
.env
.DS_Store
node_modules/
dist/
build/
"""


# ----------------------------
# Helpers
# ----------------------------
def run_command(command: str, cwd: str | None = None, check: bool = True) -> tuple[str, bool]:
    """
    Run a shell command. Returns (output, success).
    On failure, returns (stdout or stderr or message, False).
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=check
        )
        return result.stdout.strip(), True
    except subprocess.CalledProcessError as e:
        msg = (e.stdout or e.stderr or str(e)).strip()
        return msg, False


def is_git_repo(repo_path: str) -> bool:
    out, ok = run_command("git rev-parse --is-inside-work-tree", cwd=repo_path, check=False)
    return ok and out.lower() == "true"


def get_repo_url(repo_path: str) -> str:
    out, ok = run_command("git config --get remote.origin.url", cwd=repo_path, check=False)
    return out if (ok and out) else "Unknown"


def get_current_branch(repo_path: str) -> str | None:
    # Try the common ways to detect branch; avoid 'HEAD' (detached)
    out, ok = run_command("git rev-parse --abbrev-ref HEAD", cwd=repo_path, check=False)
    if ok and out and out != "HEAD":
        return out

    out2, ok2 = run_command("git symbolic-ref --short HEAD", cwd=repo_path, check=False)
    if ok2 and out2:
        return out2

    return None  # unknown / detached


def checkout_or_create_branch(repo_path: str, branch: str) -> bool:
    """
    Checkout the given branch if it exists; otherwise create it.
    """
    # Does branch exist locally?
    _, ok = run_command(f"git rev-parse --verify {branch}", cwd=repo_path, check=False)
    if ok:
        _, ok2 = run_command(f"git checkout {branch}", cwd=repo_path, check=False)
        return ok2

    # Try to create from origin/<branch> if remote has it
    _, has_remote = run_command(f"git ls-remote --heads origin {branch}", cwd=repo_path, check=False)
    if has_remote:
        _, ok3 = run_command(f"git checkout -b {branch} --track origin/{branch}", cwd=repo_path, check=False)
        return ok3

    # Otherwise create empty local branch
    _, ok4 = run_command(f"git checkout -b {branch}", cwd=repo_path, check=False)
    return ok4


def setup_git_config():
    run_command(f'git config --global user.name "{GIT_USER_NAME}"', check=False)
    run_command(f'git config --global user.email "{GIT_USER_EMAIL}"', check=False)


def has_changes(repo_path: str) -> bool:
    out, ok = run_command("git status --porcelain", cwd=repo_path, check=False)
    return ok and len(out.strip()) > 0


def ensure_upstream(repo_path: str, branch: str) -> bool:
    """
    Ensure 'origin/<branch>' is set as upstream.
    If missing, attempt 'git push -u origin <branch>'.
    """
    out, ok = run_command(f"git rev-parse --abbrev-ref {branch}@{{upstream}}", cwd=repo_path, check=False)
    if ok:
        return True

    # Try to set upstream (works even if nothing to push, if remote branch exists)
    _, push_ok = run_command(f"git push -u origin {branch}", cwd=repo_path, check=False)
    return push_ok


def commit_all(repo_path: str, message: str) -> bool:
    _, add_ok = run_command("git add -A", cwd=repo_path, check=False)
    if not add_ok:
        return False

    out, commit_ok = run_command(f'git commit -m "{message}"', cwd=repo_path, check=False)
    if not commit_ok:
        # Common case: nothing to commit
        if "nothing to commit" in out.lower():
            return True
        return False
    return True


def push(repo_path: str, branch: str) -> bool:
    _, ok = run_command(f"git push origin {branch}", cwd=repo_path, check=False)
    return ok


def write_gitignore_if_needed(repo_path: str):
    """
    Create a starter .gitignore if not present and CREATE_GITIGNORE=1.
    Append any extra patterns from GITIGNORE_EXTRA (newline-separated).
    """
    if not CREATE_GITIGNORE:
        return
    gitignore_path = Path(repo_path) / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(DEFAULT_GITIGNORE, encoding="utf-8")

    if GITIGNORE_EXTRA.strip():
        with gitignore_path.open("a", encoding="utf-8") as fh:
            if not DEFAULT_GITIGNORE.endswith("\n"):
                fh.write("\n")
            fh.write("\n# Extra patterns from env\n")
            for line in GITIGNORE_EXTRA.splitlines():
                fh.write(line.rstrip() + "\n")


def ensure_git_repo(repo_path: str, remote_url: str | None, default_branch: str = "main") -> bool:
    """
    Ensure repo_path is a git repo. If not:
      - git init
      - optional: create .gitignore
      - initial commit if there are files
      - optional: add remote origin <remote_url>
      - create/checkout default_branch
      - optional: first push to set upstream
    """
    if is_git_repo(repo_path):
        return True

    print(f"Git not initialized at {repo_path}. Initializing repository...")
    out, ok = run_command("git init", cwd=repo_path, check=False)
    if not ok:
        print(f"Error initializing git: {out}")
        return False

    write_gitignore_if_needed(repo_path)

    # Create first commit if there is anything to commit
    run_command("git add -A", cwd=repo_path, check=False)
    # If add had nothing, commit will fail; that's fine.
    run_command('git commit -m "Initial commit"', cwd=repo_path, check=False)

    # Ensure default branch exists and is checked out
    # (Some Git configs default to 'master'—we standardize to default_branch)
    # If we're already on default_branch, this is a no-op.
    checkout_or_create_branch(repo_path, default_branch)

    if remote_url:
        print(f"Adding remote 'origin' -> {remote_url}")
        # Add origin (ignore error if already exists)
        run_command(f"git remote remove origin", cwd=repo_path, check=False)  # ensure clean state
        _, add_ok = run_command(f"git remote add origin {remote_url}", cwd=repo_path, check=False)
        if not add_ok:
            print("Warning: failed to add remote origin.")

        # First push to set upstream (OK if it fails; user can fix credentials/URL)
        ensure_upstream(repo_path, default_branch)

    return True


# ----------------------------
# Main loop
# ----------------------------
def auto_push_loop():
    print("Starting auto-push script...")
    print(f"Local path: {REPO_PATH}")

    if not os.path.exists(REPO_PATH):
        print(f"Error: Path does not exist: {REPO_PATH}")
        return

    setup_git_config()

    # Ensure repo (and optionally set remote + first push)
    if not ensure_git_repo(REPO_PATH, REMOTE_URL, default_branch=BRANCH_NAME_ENV or "main"):
        return

    # Figure out the branch to use
    branch = BRANCH_NAME_ENV or get_current_branch(REPO_PATH) or "main"

    # If user forced a branch via env, make sure we are on it
    if BRANCH_NAME_ENV:
        if not checkout_or_create_branch(REPO_PATH, BRANCH_NAME_ENV):
            print(f"Warning: Could not switch/create branch '{BRANCH_NAME_ENV}'. Continuing on detected branch.")

        # Re-detect in case checkout succeeded
        branch = get_current_branch(REPO_PATH) or branch

    repo_url = get_repo_url(REPO_PATH)

    print(f"Repository: {repo_url}")
    print(f"Branch: {branch}")
    print(f"Push interval: {SLEEP_DURATION} seconds")
    print("Press Ctrl+C to stop")

    # Ensure upstream set (best effort)
    if not ensure_upstream(REPO_PATH, branch):
        print(f"Warning: Could not set upstream for '{branch}'. "
              f"Ensure 'origin' exists and credentials are valid (especially on first push).")

    try:
        while True:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"{current_time}: Checking for changes...")

            if has_changes(REPO_PATH):
                print("Changes detected. Adding, committing, and pushing...")
                msg = f"Auto-commit: {current_time}"
                if not commit_all(REPO_PATH, msg):
                    print("Error: Failed to commit changes.")
                else:
                    if push(REPO_PATH, branch):
                        print(f"Successfully pushed changes at {current_time}")
                    else:
                        print(f"Error: Failed to push changes at {current_time}")
            else:
                print("No changes detected.")

            print(f"Waiting {SLEEP_DURATION} seconds until next check...")
            time.sleep(SLEEP_DURATION)

    except KeyboardInterrupt:
        print("\nStopping auto-push script...")


if __name__ == "__main__":
    auto_push_loop()
