#!/bin/bash
# Registers the ArgoCD root Application (app-of-apps pattern). The root
# Application's source is k8s/argocd/apps/ in gitflow-gitops — ArgoCD syncs
# every Application manifest in that directory automatically, so this script
# only ever needs to apply the one root manifest, never the individual
# per-environment/component ones.
# Safe to run on every deploy — kubectl apply is idempotent.
# If ArgoCD is not yet ready (e.g. cluster just created), the script exits
# cleanly so the rest of the pipeline is not blocked.
#
# Usage: scripts/bootstrap-argocd.sh <path-to-gitflow-gitops-checkout>
# The manifest lives in the gitflow-gitops repo, not this one — the caller
# (deploy.yml) checks that repo out first and passes its local path here.
set -e

GITOPS_DIR="${1:?Usage: $0 <path-to-gitflow-gitops-checkout>}"

echo "Waiting for ArgoCD server to be ready..."
kubectl wait --for=condition=available deployment/argocd-server \
  --namespace argocd \
  --timeout=120s || {
  echo "ArgoCD not ready — skipping application bootstrap"
  exit 0
}

echo "Applying ArgoCD root Application manifest..."
kubectl apply -f "$GITOPS_DIR/k8s/argocd/root.yaml"

echo "ArgoCD root Application registered — child apps will sync within ~3 minutes"
