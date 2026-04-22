#!/usr/bin/env bash
# Daemonstrate post-commit hook.
#
# Runs the daemonstrate skill in incremental mode, non-blocking, with a lockfile
# so back-to-back commits don't stack overlapping Claude invocations.
#
# Installed by scripts/install-hooks.sh — do not edit in place (it's copied into
# .git/hooks/post-commit on install).

set -u

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
LOCK="$REPO_ROOT/docs/.daemonstrate.lock"

# Skip during rebase/merge — partial state would mis-diff.
if [ -f "$REPO_ROOT/.git/rebase-merge/interactive" ] \
  || [ -d "$REPO_ROOT/.git/rebase-apply" ] \
  || [ -f "$REPO_ROOT/.git/MERGE_HEAD" ]; then
  exit 0
fi

# Bail if a previous run is still going.
if [ -f "$LOCK" ]; then
  # Stale lock guard: older than 30 minutes → assume crashed.
  if [ "$(find "$LOCK" -mmin +30 2>/dev/null)" ]; then
    rm -f "$LOCK"
  else
    exit 0
  fi
fi

# Require claude CLI — otherwise silently skip so broken tooling doesn't break commits.
command -v claude >/dev/null 2>&1 || exit 0

mkdir -p "$REPO_ROOT/docs"
touch "$LOCK"

# Run in background, detached. The lock file is released by the spawned process.
(
  cd "$REPO_ROOT" || exit 0
  # Natural-language prompt — skills trigger on description matching, not slash
  # commands, so this phrasing is what actually routes to Daemonstrate.
  claude -p "Run Daemonstrate in incremental mode to refresh the architecture diagrams for this repo. This was triggered by a post-commit hook, so only re-examine layers that changed since the last .daemonstrate-state.json SHA." \
    >/dev/null 2>&1
  rm -f "$LOCK"
) &

disown 2>/dev/null || true
exit 0
