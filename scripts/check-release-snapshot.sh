#!/usr/bin/env bash
# A release snapshot is one generated commit on trusted main, never a merge.
set -euo pipefail
read -r -a revision <<< "$(git rev-list --parents -n 1 HEAD)"
if [ "${#revision[@]}" -ne 2 ]; then
  echo "::error::Release snapshot must have exactly one parent."
  exit 1
fi
parent="${revision[1]}"
git merge-base --is-ancestor "$parent" origin/main
# Compare trees explicitly. diff-tree without merge flags can report no paths for
# a merge commit; disabling rename detection also checks both paths of a rename.
changed="$(git diff --no-renames --name-only "$parent" HEAD)"
unexpected="$(printf '%s\n' "$changed" | grep -Ev '^(sdks/|openapi/v1\.yaml$|sdk-release\.json$|$)' || true)"
if [ -n "$unexpected" ]; then
  echo "::error::Release snapshot changes workflow/source files: $unexpected"
  exit 1
fi
