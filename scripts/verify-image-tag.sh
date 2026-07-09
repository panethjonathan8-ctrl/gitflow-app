#!/bin/bash
# Verifies that a given image tag exists in all four ECR repositories.
# Called before a rollback to ensure the target tag is actually available.
set -e

TAG="$1"
REGION="$2"

if [ -z "$TAG" ] || [ -z "$REGION" ]; then
  echo "Usage: $0 <image-tag> <aws-region>"
  exit 1
fi

echo "Verifying image tag '$TAG' exists in ECR..."

for repo in gitflow-analyzer/analyzer gitflow-analyzer/graph-builder gitflow-analyzer/result-api gitflow-analyzer/frontend; do
  STATUS=$(aws ecr describe-images \
    --repository-name "$repo" \
    --image-ids imageTag="$TAG" \
    --region "$REGION" \
    --query "imageDetails[0].imageTags[0]" \
    --output text 2>/dev/null || echo "NOT_FOUND")

  if [ "$STATUS" = "NOT_FOUND" ] || [ "$STATUS" = "None" ]; then
    echo "ERROR: Tag '$TAG' not found in ECR repo '$repo'"
    exit 1
  fi
  echo "Verified: $repo:$TAG"
done

echo "All images verified — safe to roll back"
