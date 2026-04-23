# AWS infrastructure (Terraform)

Creates:

- **Private S3 bucket** for proof uploads (versioning + SSE-S3).
- **ECR repository** for the API Docker image.
- **IAM policy** `api_task_uploads` — attach to your API runtime role (App Runner / ECS / EC2) so the process can use `AWS_S3_BUCKET`.
- **Optional GitHub OIDC** role — push-only to that ECR repo when `github_org` / `github_repo` are set.

## Prerequisites

- [Terraform](https://www.terraform.io/downloads) >= 1.5
- [AWS CLI](https://aws.amazon.com/cli/) configured (`aws sts get-caller-identity`)

## First-time apply

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars (region, GitHub org/repo if using CI).

terraform init
terraform plan
terraform apply
```

Copy outputs:

| Output | Use |
|--------|-----|
| `aws_account_id` | Optional: set `AWS_ACCOUNT_ID` in `.env` for your own reference (IAM policies / ARNs). Not a credential. |
| `uploads_bucket_name` | Set `AWS_S3_BUCKET` on the API. |
| `ecr_repository_url` | GitHub secret `ECR_REPOSITORY_URI` (full URL, **no** tag). |
| `api_task_uploads_policy_arn` | Attach to the API service **task/instance** role. |
| `github_actions_role_arn` | GitHub secret `AWS_DEPLOY_ROLE_ARN` (if OIDC enabled). |

**AWS authentication:** use `aws configure`, environment variables `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (and optional `AWS_SESSION_TOKEN`), or an **IAM role** on the host (EC2/ECS/App Runner). The app does not log in with `AWS_ACCOUNT_ID`.

## Scripts (from repo root)

| Script | Purpose |
|--------|---------|
| `./scripts/terraform-init.sh` | `terraform init` in `infra/terraform`. |
| `./scripts/terraform-plan.sh` | `terraform plan -out=tfplan`. |
| `./scripts/terraform-apply.sh` | `terraform apply` (uses `tfplan` if present). |
| `./scripts/docker-push-api.sh` | Local Docker build + `docker push` (needs `ECR_REPOSITORY_URI`, AWS creds). |

On Windows without Bash, run the same commands from `infra/terraform` in PowerShell.

## OpenRouter (API)

Set on the **API** service (not in the browser):

- `OPENROUTER_API_KEY` — required for AI-assisted `/upload` (no `pu_id`) and consensus vision calls.
- `OPENROUTER_BASE_URL` — default `https://openrouter.ai/api/v1`.
- `OPENROUTER_MODEL` — must be a **vision** model slug from [OpenRouter models](https://openrouter.ai/models).

In GitHub / AWS: store the key in **Secrets Manager** or **SSM Parameter Store** and inject as env; never commit keys.

## GitHub Actions

1. Apply Terraform with `github_org` / `github_repo` set (OIDC provider + role).
2. In the repo: **Settings → Secrets and variables → Actions**
   - Secret `AWS_DEPLOY_ROLE_ARN` = output `github_actions_role_arn`.
   - Secret `ECR_REPOSITORY_URI` = output `ecr_repository_url` (no `:tag`).
3. **Variables**: add `AWS_REGION` (e.g. `eu-west-1`) for the deploy workflow.

Workflows:

- **Terraform verify** — `fmt`, `validate` on `infra/terraform` changes.
- **Deploy API image to ECR** — on push to `main` under `backend/`, builds `backend/Dockerfile` and pushes `:sha`.

App Runner / ECS still need to be defined separately (or extend this stack) and must use the **API task policy** + env `AWS_S3_BUCKET`, `DATABASE_URL`, `PUBLIC_BASE_URL`, OpenRouter vars.

## Remote state (recommended)

For teams, configure an S3 + DynamoDB backend in a new `backend.tf` (bootstrap bucket first). This repo starts with **local** `terraform.tfstate` (gitignored under `infra/terraform/`).
