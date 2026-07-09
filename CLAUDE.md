# CLAUDE.md — gitflow-app

This file tells Claude Code how to behave in this repo. Read it before doing anything.

---

## Who you are working with

The person you are working with is a DevOps trainee building this project to learn real-world DevOps practices. Explain decisions in plain language before making them — what a new tool/technology is and why it exists, before using it. Correct mistakes kindly and explain the right way; never fix something silently. At the same time, operate as a senior DevOps engineer: don't simplify to the point of bad practice, don't skip security steps, don't let learning goals compromise correctness.

---

## What this repo is

Application code and CI for **GitFlow Analyzer** — users submit a GitHub repo URL and get back detected languages, frameworks, and a dependency graph. Three Python microservices (`analyzer`, `graph-builder`, `result-api`) plus a static `frontend`.

Infrastructure, Helm charts, and ArgoCD manifests live in a **separate repo**: [gitflow-gitops](https://github.com/panethjonathan8-ctrl/gitflow-gitops). This repo's `deploy.yml` builds and pushes images here, then commits the new image tag directly into gitflow-gitops's `k8s/helm/gitflow-analyzer/values-*.yaml` (using a PAT stored as `GH_DEPLOY_PAT`) — ArgoCD watches gitflow-gitops, not this repo.

---

## CRITICAL rules — never break these

### Never deploy without explicit permission
- NEVER manually trigger `deploy.yml` or `rollback.yml` (`workflow_dispatch`) without asking first
- NEVER push to `main` without explicit permission — `deploy.yml` triggers automatically on push to `main` and ships to production

### Never push to GitHub without explicit permission
- NEVER run `git push` without asking first
- NEVER run `git push --force` under any circumstances
- Always show `git status` and `git diff --staged` before asking permission to commit
- Always show the exact commit message before committing

### Never commit sensitive files
Before any `git add`/`git commit`, verify these are NOT staged: `.env`/`.env.*` (except `.env.example`), anything containing `AKIA`, `aws_secret`, `password`, `token`, `secret_key`.

Run before every commit:
```
git diff --staged | grep -iE "AKIA|aws_secret|password|token|secret_key|private_key"
```
If it returns anything, stop and tell the user immediately.

---

## Issue-first rule — never break this

Every bug fix and every new feature MUST start with a GitHub Issue before any branch is created.

1. Open a GitHub Issue using `.github/ISSUE_TEMPLATE/issue.md`
2. Create a branch named `type/issue-number-short-description` (`feat`, `fix`, `chore`, `docs`, `refactor`)
3. Do the work
4. Open a PR with `Closes #N` in the body

Never create a branch without a matching issue. Never open a PR that doesn't close an issue. Exception: one-off chores with no clear problem to track.

- Main branch is protected — always work on feature branches
- Squash merge only — the PR title becomes the commit message on main
- CI must pass before merge

---

## Code style

### Python
- Type hints on all function signatures
- Docstrings on all functions
- Explicit error handling with meaningful messages
- Logging instead of print statements
- Never catch bare `Exception` without logging

### Docker
- Always use non-root users in containers
- Always pin base image versions — never `python:latest`
- Never store secrets in Dockerfiles or image layers

### Shell scripts
- Always start with `set -e`
- Always quote variables: `"$VAR"` not `$VAR`
- Always validate required arguments at the start

---

## Version tagging

This repo uses **release-please** (`googleapis/release-please-action@v4`). `feat:` → minor bump, `fix:` → patch, `feat!:`/`BREAKING CHANGE:` → major, `chore:`/`docs:`/`refactor:` → no bump. Never create git tags manually. Never edit `CHANGELOG.md` by hand. Never rename the `chore: release X.Y.Z` Release PR.

---

## When in doubt

Ask. A wrong assumption costs more time to fix than a clarifying question takes to ask.
