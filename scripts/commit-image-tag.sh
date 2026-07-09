#!/bin/bash
# Commits an updated Helm values file back to main after an image tag change.
# Usage: scripts/commit-image-tag.sh <image-tag> <values-file>
# Example: scripts/commit-image-tag.sh abc1234 k8s/helm/gitflow-analyzer/values-dev.yaml
#
# Pushes made with GITHUB_TOKEN do not re-trigger GitHub Actions workflows,
# so there is no risk of an infinite deploy loop.
set -e

TAG="$1"
VALUES_FILE="${2:-k8s/helm/gitflow-analyzer/values-dev.yaml}"

if [ -z "$TAG" ]; then
  echo "Usage: $0 <image-tag> [values-file]"
  exit 1
fi

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

# Commit first, then rebase onto main.
# git pull --rebase refuses to run if the index has staged changes, so we
# commit before pulling. The rebase replays our commit on top of any
# new commits that landed on main while the build was running.
git add "$VALUES_FILE"
git commit -m "chore: deploy image tag ${TAG} [$(basename "$VALUES_FILE" .yaml)]"
git pull --rebase origin main
git push origin main
