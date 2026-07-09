#!/bin/bash
# Commits a rollback image tag to the given environment's values file.
# ArgoCD detects the commit and rolls the deployment back automatically.
set -e

TAG="$1"
ENV="$2"

if [ -z "$TAG" ] || [ -z "$ENV" ]; then
  echo "Usage: $0 <image-tag> <environment>"
  exit 1
fi

VALUES_FILE="k8s/helm/gitflow-analyzer/values-${ENV}.yaml"

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

git pull --rebase origin main
git add "$VALUES_FILE"
git commit -m "chore: rollback ${ENV} to image tag ${TAG}"
git push origin main
