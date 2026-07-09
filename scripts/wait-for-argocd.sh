#!/bin/bash
# Waits for an ArgoCD Application to reach Synced + Healthy.
# Usage: scripts/wait-for-argocd.sh <app-name>
# Example: scripts/wait-for-argocd.sh gitflow-analyzer-dev
#
# Forces an immediate refresh first so you don't wait 3 minutes for ArgoCD's
# normal polling interval.
set -e

APP="${1:?Usage: $0 <app-name>}"
TIMEOUT=300
INTERVAL=10
ELAPSED=0

echo "Forcing immediate ArgoCD refresh for $APP..."
kubectl -n argocd annotate application "$APP" \
  argocd.argoproj.io/refresh=hard --overwrite

echo "Waiting for $APP to be Synced and Healthy (timeout: ${TIMEOUT}s)..."
while [ "$ELAPSED" -lt "$TIMEOUT" ]; do
  SYNC=$(kubectl -n argocd get application "$APP" \
    -o jsonpath='{.status.sync.status}' 2>/dev/null || echo "Unknown")
  HEALTH=$(kubectl -n argocd get application "$APP" \
    -o jsonpath='{.status.health.status}' 2>/dev/null || echo "Unknown")
  echo "  [${ELAPSED}s] sync=${SYNC} health=${HEALTH}"

  if [ "$SYNC" = "Synced" ] && [ "$HEALTH" = "Healthy" ]; then
    echo "$APP is Synced and Healthy"
    exit 0
  fi

  sleep "$INTERVAL"
  ELAPSED=$((ELAPSED + INTERVAL))
done

echo "TIMEOUT: $APP did not reach Synced+Healthy within ${TIMEOUT}s"
kubectl -n argocd get application "$APP" -o yaml | tail -40
exit 1
