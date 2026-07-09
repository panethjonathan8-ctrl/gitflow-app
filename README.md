# gitflow-app

Application code and CI for GitFlow Analyzer — users submit a GitHub repo URL and get back detected languages, frameworks, and a dependency graph.

## Services

| Service | What it does |
|---|---|
| `services/analyzer` | Detects languages/frameworks in the submitted repo |
| `services/graph-builder` | Builds the dependency graph |
| `services/result-api` | Serves results to the frontend, talks to RDS |
| `services/frontend` | Static frontend, served from S3/CloudFront |

## Related repo

Infrastructure (Terraform/Terragrunt), Helm charts, and ArgoCD manifests live in a separate repo: [gitflow-gitops](https://github.com/panethjonathan8-ctrl/gitflow-gitops). This repo's `deploy.yml` builds images here and commits the new image tag there — ArgoCD watches gitflow-gitops, not this repo.

## CI/CD

- `ci.yml` — tests on every PR touching `services/**`
- `docker-lint.yml` — hadolint on every Dockerfile change
- `deploy.yml` — on push to `main`: build + push images to ECR, deploy to dev, then staging, then production (manual approval gate)
- `rollback.yml` — manual workflow to roll an environment back to a previous image tag

See CLAUDE.md for how this project expects changes to be made (issue-first, branch naming, PR rules).
