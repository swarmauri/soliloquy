# soliloquy/ops/git_ops.py

import subprocess
import sys
from typing import Optional


def git_add_all() -> bool:
    """
    Stages (adds) all changes (modified, deleted, new files).
    
    Returns:
        True if successful, False if an error occurs.
    """
    try:
        subprocess.run(["git", "add", "--all"], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[git_ops] 'git add --all' failed: {e}", file=sys.stderr)
        return False


def git_commit_all_changes(message: str = "chore: automated commit") -> bool:
    """
    Stages all changes and commits them with the specified message.
    If there are no changes to commit, this will fail by default.
    You can handle that exception or pass '--allow-empty' if desired.

    Returns:
        True if commit succeeded, False otherwise.
    """
    if not git_add_all():
        return False

    # Attempt the commit
    try:
        subprocess.run(["git", "commit", "-m", message], check=True)
    except subprocess.CalledProcessError as e:
        # This commonly fails if there's nothing to commit
        print(f"[git_ops] 'git commit' failed (maybe no changes to commit?): {e}", file=sys.stderr)
        return False

    return True


def git_push(remote: str = "origin", branch: str = "main") -> bool:
    """
    Pushes the local commits to the specified remote/branch.

    Returns:
        True if push succeeded, False otherwise.
    """
    cmd = ["git", "push", remote, branch]
    print(f"[git_ops] Running: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[git_ops] 'git push' failed: {e}", file=sys.stderr)
        return False


def git_tag(tag_name: str, message: Optional[str] = None) -> bool:
    """
    Creates a new Git tag locally. If a message is provided, it creates an annotated tag.

    Args:
        tag_name: The name of the tag to create (e.g. 'v1.2.3').
        message: Optional annotation message.

    Returns:
        True if the tag was created successfully, False otherwise.
    """
    if not tag_name:
        print("[git_ops] No tag_name provided.", file=sys.stderr)
        return False

    cmd = ["git", "tag"]
    if message:
        cmd += ["-a", tag_name, "-m", message]
    else:
        cmd.append(tag_name)

    print(f"[git_ops] Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[git_ops] 'git tag' failed: {e}", file=sys.stderr)
        return False


def git_push_tags(remote: str = "origin") -> bool:
    """
    Pushes all local tags to the specified remote.

    Returns:
        True if tags were pushed successfully, False otherwise.
    """
    cmd = ["git", "push", "--tags", remote]
    print(f"[git_ops] Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[git_ops] 'git push --tags' failed: {e}", file=sys.stderr)
        return False
