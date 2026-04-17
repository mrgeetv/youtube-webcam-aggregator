#!/bin/bash
# PreToolUse hook: blocks `git commit` when the current branch is main or master.
# Referenced from .claude/settings.json with `if: "Bash(git commit*)"` so it only
# runs on commit attempts, not every bash call.
#
# Emits a deny decision as JSON on main/master; silent pass-through otherwise.

set -euo pipefail

branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")

case "$branch" in
  main|master)
    jq -n --arg b "$branch" '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: (
          "Blocked: direct commit to protected branch \"" + $b + "\". " +
          "Per project CLAUDE.md, create a feature branch first: " +
          "git checkout -b fix/your-change"
        )
      }
    }'
    ;;
esac
