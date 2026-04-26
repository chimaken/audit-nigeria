# AWS infrastructure (Terraform)

Creates:

- **Private S3 bucket** for proof uploads (versioning + SSE-S3).
- **ECR repository** for the API Docker image.
- **IAM policy** `api_task_uploads` — attach to your API runtime role (App Runner / ECS / EC2) so the process can use `AWS_S3_BUCKET`.
- **Optional GitHub OIDC** role — push-only to that ECR repo when `github_org` / `github_repo` are set.
- **Optional App Runner** API service and **optional CloudFront + S3** for a static Next.js dashboard (`frontend_cloudfront_enabled`).

## Prerequisites

- [Terraform](https://www.terraform.io/downloads) >= 1.5
- [AWS CLI](https://aws.amazon.com/cli/) configured (`aws sts get-caller-identity`)

## First-time apply

The root module uses an **S3 backend** with an empty `backend "s3" {}` block: **bucket, key, region, and lock table** are supplied at init time. Running **`terraform init` without flags** will prompt for those values and fail if you leave `key` blank or omit `region`.

**Remote state (recommended, matches GitHub Actions):**

1. Apply **`infra/terraform-state-bootstrap`** once and note **`terraform_state_bucket`** and **`terraform_state_lock_table`**.
2. In **`infra/terraform`**:

   ```bash
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars (region, GitHub org/repo if using CI).

   cp backend.hcl.example backend.hcl
   # Edit backend.hcl: set bucket, dynamodb_table, region, key (e.g. audit-nigeria/prod/terraform.tfstate).
   ```

3. Initialize **with** the partial backend file. On **Windows PowerShell**, quote the flag so `backend.hcl` is not parsed as a separate argument (avoids `Too many command line arguments`):

   ```bash
   terraform init -backend-config=backend.hcl
   ```

   ```powershell
   terraform init "-backend-config=backend.hcl"
   ```

   If you already have a **local** `terraform.tfstate` from before the S3 backend was added, migrate once (bash: **`terraform init -migrate-state -backend-config=backend.hcl`**; PowerShell: **`terraform init "-migrate-state" "-backend-config=backend.hcl"`**).

**Local state only** (quick `plan` / `validate` without touching remote): **`terraform init -backend=false`**. The PR workflow **Terraform verify** uses this mode.

After a successful init, run **`terraform plan`** then **`terraform apply`** from **`infra/terraform`**.

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

### Deploy (single script)

| Linux / macOS | Windows (PowerShell 5.1+) |
|---------------|---------------------------|
| `./scripts/deploy/deploy.sh` | `.\scripts\deploy\deploy.ps1` |

**`-Mode` / `--mode`:** `Infra` | `Backend` | `Frontend` | `App` (default **`App`** = API image then static site).

| Mode | What it does |
|------|----------------|
| **Infra** | `terraform init` + `terraform apply -auto-approve` in `infra/terraform` (needs `terraform.tfvars`). Optional bash `--infra-init-only` / PowerShell `-InfraInitOnly` for init only. |
| **Backend** | Docker build `backend/Dockerfile`, push to ECR. Optional `-ApplyTerraform` / `--apply-terraform` to set `apprunner_image_tag`. Optional `-SkipPush` / `--skip-push`. |
| **Frontend** | `STATIC_EXPORT=1`, `npm run build:static` in `frontend/`, then `terraform apply` for S3/CloudFront. Optional `-SkipFrontendTerraform` / `--skip-frontend-terraform`. API URL: `-ApiUrl` / `--api-url`, or Terraform output `apprunner_public_url`. |
| **App** | Backend then Frontend (typical after code changes). |

Examples:

```powershell
.\scripts\deploy\deploy.ps1 -Mode Infra
.\scripts\deploy\deploy.ps1 -Mode App -ApplyTerraform
.\scripts\deploy\deploy.ps1 -Mode Backend -ApplyTerraform
.\scripts\deploy\deploy.ps1 -Mode Frontend -ApiUrl "https://xxx.awsapprunner.com"
```

```bash
./scripts/deploy/deploy.sh --mode infra
./scripts/deploy/deploy.sh --mode app --apply-terraform
./scripts/deploy/deploy.sh --help
```

PowerShell examples avoid `&&` (use separate lines or check `$LASTEXITCODE`).

**Fresh environment (typical order):** `.\scripts\deploy\deploy.ps1 -Mode Infra` (or `deploy.sh --mode infra`) → set GitHub secrets from outputs → **`App`** with **`-ApplyTerraform` / `--apply-terraform`** (or rely on CI for ECR and only run **Frontend** / Terraform as needed).

### Other helper scripts

| Script | Purpose |
|--------|---------|
| `./scripts/terraform-init.sh` | `terraform init` in `infra/terraform`. |
| `./scripts/terraform-plan.sh` | `terraform plan -out=tfplan`. |
| `./scripts/terraform-apply.sh` | `terraform apply` (uses `tfplan` if present). |
| `./scripts/docker-push-api.sh` | Local Docker build + `docker push` (needs `ECR_REPOSITORY_URI`, AWS creds). |

On Windows without Bash, use `deploy.ps1` or run Terraform from `infra/terraform` in PowerShell.

## OpenRouter (API)

Set on the **API** service (not in the browser):

- `OPENROUTER_API_KEY` — required for AI-assisted `/upload` (no `pu_id`) and consensus vision calls.
- `OPENROUTER_BASE_URL` — default `https://openrouter.ai/api/v1`.
- `OPENROUTER_MODEL` — must be a **vision** model slug from [OpenRouter models](https://openrouter.ai/models).

In GitHub / AWS: store the key in **Secrets Manager** or **SSM Parameter Store** and inject as env; never commit keys.

## GitHub Actions (push-to-deploy on `main`)

The workflow **`.github/workflows/deploy-main.yml`** runs on every push to **`main`**. It path-filters **infra**, **backend**, and **frontend**. When any of those paths change, it runs **`terraform apply`** first (remote state), then **backend** (ECR / App Runner / Lambda image updates) and/or **frontend** (S3 sync) only if their paths changed and Terraform succeeded.

When **`frontend_cloudfront_enabled = true`** in the decoded **`terraform.tfvars`**, the Terraform job runs **`npm ci`** + **`npm run build:static`** in **`frontend/`** first so **`frontend/out`** exists. That satisfies the **`check`** in **`frontend_cloudfront.tf`** and matches how **`aws_s3_object.frontend`** is built from **`fileset()`** (without **`out/`**, Terraform would plan to **remove** all managed dashboard objects). Set repository variable **`NEXT_PUBLIC_API_URL`** the same as for the frontend deploy step.

**Runtime images** for the API, App Runner, and the upload-worker Lambda are rolled to **`${ECR}:${{ github.sha }}`** by that workflow (not by `apprunner_image_tag` / `upload_worker_image_tag` in routine use). The main Terraform stack **ignores drift** on App Runner and Lambda **image identifiers** so `terraform apply` does not revert CI to an older tag.

### Remote state + CI secrets (required for `terraform apply` in Actions)

1. **One-time:** from a machine with AWS credentials, create the state bucket and lock table (this module uses **local** state only — it is tiny):

   ```bash
   cd infra/terraform-state-bootstrap
   terraform init -input=false
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars if project/environment differ from the main stack.
   terraform apply -input=false
   ```

   If you see **Inconsistent dependency lock file** / **no version is selected**, run **`terraform init -input=false`** in this folder first (a **`.terraform.lock.hcl`** is committed so providers resolve without a network lock step when possible).

   Copy outputs **`terraform_state_bucket`** → GitHub secret **`TF_STATE_BUCKET`**, **`terraform_state_lock_table`** → **`TF_STATE_LOCK_TABLE`**. Optionally set repo variable **`TF_STATE_KEY`** to **`suggested_tf_state_key`** (defaults in the workflow if unset).

2. **Migrate** existing main-stack state to S3 once (from `infra/terraform` with your current `terraform.tfvars`), e.g. [Terraform `terraform state push`](https://developer.hashicorp.com/terraform/cli/commands/state/push) after reconfiguring the backend, or follow HashiCorp’s “migrate existing state” prompt on `terraform init` with the new backend block.

3. **`TFVARS_B64`:** base64 **UTF-8** of the **same** `terraform.tfvars` you use locally (sensitive — **never commit**). The workflow decodes it in the runner to `infra/terraform/terraform.tfvars`. Examples:

   ```bash
   # Linux / macOS (from infra/terraform, file must be gitignored)
   base64 -w0 < terraform.tfvars | gh secret set TFVARS_B64 --repo OWNER/REPO
   ```

   ```powershell
   # Windows PowerShell (path to your gitignored tfvars)
   $raw = Get-Content -Raw "C:\path\to\audit-nigeria-mvp\infra\terraform\terraform.tfvars"
   [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($raw)) | gh secret set TFVARS_B64 --repo OWNER/REPO
   ```

   If **`terraform apply`** in Actions exits **1** right after **`Plan:`**, scroll further down in the job log for **`Error:`** or **`Check block assertion failed`**. Typical causes: **`telegram_create_secret = true`** with an empty **`telegram_bot_token`** in **`TFVARS_B64`** (fix by adding the optional **`TELEGRAM_BOT_TOKEN`** secret, or embedding the token in **`TFVARS_B64`**, or setting **`telegram_create_secret = false`** and using **`telegram_bot_token_secret_arn`**).

4. **`github_terraform_apply_enabled`:** set **`true`** in `terraform.tfvars` and run **`terraform apply` once from a trusted machine** so the GitHub OIDC role receives policies that allow **`terraform apply`** in CI (see `variables.tf` / `github_oidc.tf`). Review IAM scope; tighten later if needed.

5. Apply the main stack with `github_org` / `github_repo` set so the **GitHub OIDC role** exists. The stack **reuses** the account OIDC URL `token.actions.githubusercontent.com` (one per AWS account).

6. In the repo: **Settings → Secrets and variables → Actions**

**Secrets (repository)**

| Secret | Value |
|--------|--------|
| `TF_STATE_BUCKET` | Output `terraform_state_bucket` from **`infra/terraform-state-bootstrap`**. |
| `TF_STATE_LOCK_TABLE` | Output `terraform_state_lock_table` from that bootstrap. |
| `TFVARS_B64` | Base64-encoded full **`terraform.tfvars`** for the main stack (UTF-8). |
| `TELEGRAM_BOT_TOKEN` | **Optional.** When set, exported as **`TF_VAR_telegram_bot_token`** so CI can satisfy **`telegram_create_requires_token`** without putting the token inside **`TFVARS_B64`**. |
| `TERRAFORM_OPENROUTER_API_KEY` | **Optional.** When set, exported as **`TF_VAR_apprunner_openrouter_api_key`** when **`apprunner_create_openrouter_secret`** is true (same idea: avoid duplicating the key only in base64 tfvars). |
| `AWS_DEPLOY_ROLE_ARN` | Main stack output `github_actions_role_arn` |
| `ECR_REPOSITORY_URI` | `ecr_repository_url` (no `:tag`) |
| `APPRUNNER_SERVICE_ARN` | `apprunner_service_arn` — **optional**; if set, backend job points App Runner at the new image on each qualifying push. |
| `UPLOAD_WORKER_ECR_REPOSITORY_URI` | `upload_worker_ecr_url` (no tag) — **optional**; Lambda worker image push. |
| `UPLOAD_WORKER_LAMBDA_ARN` | `upload_worker_lambda_arn` — **optional**; updates the function after a worker image push. |

**Variables (repository)** — for the **Deploy main** frontend job (and manual **Deploy static frontend** runs)

| Variable | Value |
|----------|--------|
| `AWS_REGION` | e.g. `eu-west-1` |
| `FRONTEND_S3_BUCKET` | `frontend_s3_bucket_id` |
| `CLOUDFRONT_DISTRIBUTION_ID` | `frontend_cloudfront_distribution_id` |
| `NEXT_PUBLIC_API_URL` | `apprunner_public_url` (same URL the static site should call, no trailing slash) |

### Workflows

| Workflow | Trigger | What it does |
|----------|---------|----------------|
| **Deploy main** | Push to `main` | Path filters → **`terraform apply`** (needs **`TF_STATE_*`**, **`TFVARS_B64`**, **`AWS_DEPLOY_ROLE_ARN`**) → optional **backend** / **frontend** jobs. |
| **Terraform verify** | Pull requests touching `infra/terraform/**` or deploy workflow | `terraform fmt -check`, `validate` only (no apply). |
| **Deploy API and workers to ECR** | **`workflow_dispatch` only** | Same ECR / App Runner / Lambda steps as the backend job in **Deploy main**; use for manual reruns. |
| **Deploy static frontend to S3** | **`workflow_dispatch` only** | Same as the frontend job in **Deploy main**; use for manual reruns. |

**Note:** **`apply_human_review_sql_migration`** and other **`psql`**-on-apply paths are for trusted hosts with RDS reachability, not typical GitHub-hosted runners against a private RDS.

**First-time bootstrap:** `apprunner_image_tag` and `upload_worker_image_tag` must point at an **existing** ECR image for the **first** `terraform apply` that creates the service and Lambda. After that, **GitHub Actions** owns the running image revision (**`github.sha`** per push); Terraform’s tags are not reapplied to those resources.

### App Runner (optional, in this stack)

Set in `terraform.tfvars`:

- `apprunner_enabled = true`
- `apprunner_image_tag = "<tag>"` — an image you already pushed to `ecr_repository_url`
- `rds_enabled = true` and `rds_create_api_client_security_group = true` — App Runner uses a **VPC connector** with the managed API client SG so Postgres is reachable (same subnets as RDS).

Terraform creates: ECR pull role, instance role (S3 uploads policy + Secrets Manager read), optional **Secrets Manager** secret for `DATABASE_URL` (when RDS is in this stack), VPC connector, optional **NAT gateway + EIP** (when **`apprunner_manage_nat_gateway`** is true, the default with App Runner + RDS), and the App Runner service (port **8000**, health check **`/health`**).

**NAT (OpenRouter / public HTTPS from the VPC):** With **`rds_enabled`** and **`apprunner_enabled`**, App Runner egress uses the **VPC**; outbound internet needs **`0.0.0.0/0` → NAT** on the connector subnets’ route tables. Terraform creates one NAT in **`apprunner_nat_public_subnet_id`** (or the first **`rds_subnet_ids`** subnet) and adds **`aws_route`** entries where the table has **no** IPv4 default route yet. If your subnets use the **default VPC** pattern (**`0.0.0.0/0` → Internet Gateway**), run the **`terraform output apprunner_nat_replace_default_route_commands`** lines once (AWS CLI) to point the default route at the new NAT. Disable with **`apprunner_manage_nat_gateway = false`** if you manage NAT elsewhere. NAT adds ongoing AWS cost (gateway hourly, EIP, data processing).

**IAM for NAT:** The Terraform principal (e.g. IAM user running `terraform apply`) must be allowed to allocate Elastic IPs and manage NAT gateways and routes (`ec2:AllocateAddress`, `ec2:DescribeAddresses`, **`ec2:DescribeAddressesAttribute`** (used by the AWS provider when reading `aws_eip`), `ec2:CreateNatGateway`, `ec2:CreateRoute`, etc.). If you see **`UnauthorizedOperation`**, update the policy from **`infra/terraform/policies/terraform-nat-minimum.json`** (review and attach in IAM; tighten `Resource` if your org requires it). Alternatively use an account admin for Terraform, or set **`apprunner_manage_nat_gateway = false`** and create NAT/routes outside this stack.

After the **first** apply, copy **`terraform output -raw apprunner_public_url`**, set **`apprunner_public_base_url`** and **`apprunner_cors_allow_origins`** in `terraform.tfvars`, and **apply again** so the API gets the correct `PUBLIC_BASE_URL` and CORS.

**OpenRouter on App Runner** (optional vision for upload without `pu_id`):

- **Terraform-managed secret:** set **`apprunner_create_openrouter_secret = true`** and **`apprunner_openrouter_api_key`** (sensitive string) in `terraform.tfvars` (gitignored) or export **`TF_VAR_apprunner_openrouter_api_key`**. Terraform creates **`${project}/${environment}/openrouter-api-key`** in Secrets Manager and wires **`OPENROUTER_API_KEY`**. Output: **`apprunner_openrouter_secret_arn`**.
- **Existing secret:** set **`apprunner_openrouter_api_key_secret_arn`** only (do **not** set `apprunner_create_openrouter_secret` at the same time).

Without either, **`POST /upload` requires `pu_id`**. After changing the key, run **`terraform apply`** so the secret version updates; App Runner may need a new deployment to pick up the value.

**Telegram human-in-the-loop (optional):** when **`apprunner_enabled`**, Terraform can wire **`TELEGRAM_BOT_TOKEN`** (Secrets Manager), **`TELEGRAM_CHAT_IDS`**, **`TELEGRAM_HIL_CONFIDENCE_BELOW`**, and **`FRONTEND_PUBLIC_BASE_URL`** on **App Runner** and on the **upload worker Lambda** (same rules). Use either **`telegram_create_secret = true`** plus **`telegram_bot_token`** (sensitive — `terraform.tfvars` gitignored or **`TF_VAR_telegram_bot_token`**) or **`telegram_bot_token_secret_arn`** for an existing secret; do not set both. If **`hil_frontend_public_base_url`** is empty and **`frontend_cloudfront_enabled`** is true, **`FRONTEND_PUBLIC_BASE_URL`** defaults to the CloudFront HTTPS URL so Telegram alert links match the static dashboard. See **`terraform.tfvars.example`**.

**HIL DB column (optional migration):** set **`apply_human_review_sql_migration = true`** (with **`rds_enabled`**) to run **`backend/sql/patch_human_review_alert.sql`** once during **`terraform apply`** via **`psql`**. The machine running apply must have **`psql`** and **network reachability to RDS** (for example your laptop with SG access, or **`rds_publicly_accessible`** plus your IP). This is **not** a fit for GitHub-hosted runners against a **private** RDS; use a bastion, VPN, or run **`psql`** manually against the same file, then leave **`apply_human_review_sql_migration`** at **`false`**. Re-applying after the patch is harmless if the SQL is idempotent; toggling the flag off avoids relying on **`null_resource`** triggers for routine applies.

**Demo: reset collated votes** (optional): set **`apprunner_dashboard_reset_token`** in `terraform.tfvars` (sensitive random string) and **`terraform apply`**. That sets **`DASHBOARD_RESET_TOKEN`** on App Runner; **`GET /health`** then reports **`reset_collated_votes_enabled: true`**, and the **Upload** page shows a CTA that calls **`POST /demo/reset-collated-votes?election_id=…`** with header **`X-Dashboard-Reset-Token`**. It deletes uploads (and S3 proof objects), result clusters, and national/state/LGA rollups for that election. The API task IAM policy includes **`s3:DeleteObject`** on the uploads bucket for this path.

**Seed on AWS (App Runner):** there is no shell into App Runner. To run **`app.db.seed`** on the service, use **`apprunner_run_db_seed = true`** in `terraform.tfvars` (sets **`RUN_DB_SEED=1`**), **rebuild and push** the API image (the Dockerfile entrypoint runs `python -m app.db.seed` before uvicorn), run **`terraform apply`**, wait until healthy, then set **`apprunner_run_db_seed = false`** and apply again so new instances do not re-seed every start. The seed is idempotent.

Without RDS in Terraform: set **`apprunner_database_secret_arn`** to a secret holding the full `DATABASE_URL`; egress stays **default** (public internet), so the database must be reachable that way.

Outputs: `apprunner_service_url`, `apprunner_public_url`, `apprunner_database_secret_arn` (when Terraform owns the DB secret).

If you prefer manual AWS Console setup instead, use the **API task policy** + env `AWS_S3_BUCKET`, `DATABASE_URL`, `PUBLIC_BASE_URL`, OpenRouter vars on any container runtime.

### Static frontend on CloudFront (optional)

1. Point the static build at your real API (browser calls App Runner / ALB directly; CORS must allow the CloudFront origin — Terraform appends it when **`frontend_cloudfront_enabled = true`** and **`apprunner_enabled = true`**).

2. From repo root (PowerShell example):

   ```powershell
   cd frontend
   $env:STATIC_EXPORT = "1"
   $env:NEXT_PUBLIC_API_URL = "https://YOUR-APPRUNNER-HOST.awsapprunner.com"
   npm run build:static
   ```

   This produces `frontend/out/` (trailing slashes on routes; see `next.config.mjs`).

3. In `terraform.tfvars`: `frontend_cloudfront_enabled = true` (optional: `frontend_static_out_dir` if your `out` folder is elsewhere).

4. `terraform apply` — uploads `out/**` to a private S3 bucket and creates a CloudFront distribution (OAC). A **viewer-request function** rewrites paths like `/upload` or `/upload/` to `upload/index.html` (Next `trailingSlash: true` export layout), so links such as `/upload?election_id=1` do not hit a missing S3 key and return XML `AccessDenied`. Outputs: **`frontend_cloudfront_url`**, `frontend_cloudfront_domain_name`.

5. Re-apply after changing the UI: rebuild `out/`, then `terraform apply` (object ETags bump the CDN).

## API env vars you get **after** other AWS pieces exist

**`DATABASE_URL`:** enable **`rds_enabled = true`** in `terraform.tfvars` to create **Amazon RDS for PostgreSQL** in the **default VPC** and get a ready-made URL from **`terraform output -raw database_url`** (sensitive). Otherwise create RDS manually or use another DB.

The Terraform stack still does **not** create the public **API** URL. Set these on the API service when you have them:

| Variable | When you know it |
|----------|------------------|
| **`DATABASE_URL`** | From **`terraform output -raw database_url`** (if `rds_enabled`), or hand-built from any RDS/Aurora endpoint → `postgresql+asyncpg://...` (query `ssl=require` is included by default in the Terraform output). |
| **`PUBLIC_BASE_URL`** | After the API has a **stable public URL** (custom domain + TLS on ALB, App Runner default URL, API Gateway, etc.), no trailing slash. |
| **`CORS_ALLOW_ORIGINS`** | After the **Next.js** (or other) frontend has its public origin(s), comma-separated — must include the exact scheme + host (+ port if non‑443) browsers use. |

**Frontend:** set `NEXT_PUBLIC_API_URL` in the app to the same host you allow in `CORS_ALLOW_ORIGINS` (see `frontend/.env.local.example`).

### RDS via Terraform (`rds.tf`)

1. In **`terraform.tfvars`**, set **`rds_enabled = true`**. Allow Postgres access using any combination of: **`rds_allowed_cidr_blocks`** (e.g. your IP `/32`), **`rds_allowed_security_group_ids`** (existing compute SG IDs), and/or **`rds_create_api_client_security_group = true`** (default), which creates a managed SG you attach to the API — see **`terraform output -raw api_rds_client_security_group_id`** after apply.
2. Default VPC must have **≥ 2 subnets**, or set **`rds_subnet_ids`** to two subnet IDs in **different AZs**.
3. Run **`terraform apply`**, then:  
   **`terraform output -raw database_url`** → paste into **`DATABASE_URL`** (do not commit; password is in Terraform state).
4. Other outputs: **`rds_address`**, **`rds_master_username`**, **`rds_security_group_id`**, **`api_rds_client_security_group_id`** (attach to API), **`rds_master_password`** (sensitive).
5. **Cost / security:** `db.t4g.micro` by default; **`rds_publicly_accessible`** defaults to `true` for dev-style access. Tighten SGs and set **`rds_publicly_accessible = false`** when the API runs in the same VPC. Rotate the master password after bootstrap if you rely on state file secrecy.
6. **Migrations:** API `create_all` is fine for early deploys; plan Alembic (or similar) for production.
7. **Seed geography (Lagos + FCT LGAs):** with **`DATABASE_URL`** set in repo-root **`.env`** (or exported), from **`backend`**: `set PYTHONPATH=.` then **`python -m app.db.seed`** (Windows), or **`docker compose run --rm --no-deps api python -m app.db.seed`** when Docker Desktop is running. Your client IP must be allowed on the RDS security group if the DB is not only reachable from App Runner.

If you prefer not to manage RDS in Terraform, create an instance in the [RDS console](https://console.aws.amazon.com/rds/) and build **`DATABASE_URL`** manually (see `.env.example`).

### If `terraform apply` failed on RDS with `InvalidGroup.Duplicate`

That usually means Terraform tried to **replace** the RDS security group (e.g. description-only change) with **`create_before_destroy`**, while the SG still used a **fixed `name`** — AWS rejects the second group with the same name.

This stack now uses **`name_prefix`** on the RDS SG and **`ignore_changes = [description]`** so that does not recur. **Recovery:** in **EC2 → Security groups**, delete the orphaned group named like **`audit-nigeria-prod-rds-pg`** if it is unused (no RDS ENI), run **`terraform refresh`**, then **`terraform apply`**. If the DB was destroyed mid-apply, a new instance will be created; run **`terraform output -raw database_url`** again and update **`.env`**.

## Remote state (recommended)

For teams, configure an S3 + DynamoDB backend in a new `backend.tf` (bootstrap bucket first). This repo starts with **local** `terraform.tfstate` (gitignored under `infra/terraform/`).
