#!/usr/bin/env bash
# install-hooks.sh — Install the Daemonstrate post-commit hook into the target repo.
#
# Usage: install-hooks.sh [repo-root]
#
# Behavior:
#   - Resolves repo root (argument, or `git rev-parse --show-toplevel`).
#   - If .git/hooks/post-commit already exists, backs it up as .post-commit.bak
#     (unless the existing file is already a Daemonstrate hook — detected by marker).
#   - Writes the hook from ../post-commit.sh next to this script.
#   - Marks the hook executable.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_HOOK="$SCRIPT_DIR/post-commit.sh"

if [ ! -f "$SOURCE_HOOK" ]; then
  echo "error: source hook not found at $SOURCE_HOOK" >&2
  exit 1
fi

REPO_ROOT="${1:-$(git rev-parse --show-toplevel 2>/dev/null || true)}"
if [ -z "$REPO_ROOT" ] || [ ! -d "$REPO_ROOT/.git" ]; then
  echo "error: not a git repository (pass repo root as first arg)" >&2
  exit 1
fi

HOOK_DEST="$REPO_ROOT/.git/hooks/post-commit"
MARKER="# Daemonstrate post-commit hook."

if [ -f "$HOOK_DEST" ]; then
  if grep -qF "$MARKER" "$HOOK_DEST"; then
    echo "Daemonstrate hook already installed — overwriting with latest version."
  else
    BACKUP="$HOOK_DEST.bak"
    # Don't clobber a previous backup.
    if [ -e "$BACKUP" ]; then
      BACKUP="$HOOK_DEST.bak.$(date +%s)"
    fi
    echo "Existing post-commit hook backed up to: $BACKUP"
    mv "$HOOK_DEST" "$BACKUP"
  fi
fi

cp "$SOURCE_HOOK" "$HOOK_DEST"
chmod +x "$HOOK_DEST"

echo "Installed: $HOOK_DEST"
echo "Test with: git commit --allow-empty -m 'daemonstrate hook test'"
