# Step-by-Step AWS Deployment Guide — ADV RAG E-commerce Customer Support Copilot

**Account:** Your AWS Account | **Region:** `us-east-1` (configurable) | **Stack:** ECS Fargate + ECR + EFS + ALB + Postgres + Qdrant

This guide is the single source of truth for deploying the ADV RAG pipeline to AWS from a completely fresh account. Follow the phases in order — each phase depends on the one before it.

> **Project:** ADV RAG — E-commerce Customer Support Copilot  
> **Architecture:** FastAPI app + Qdrant (vector DB) + Postgres (relational DB) in a single ECS Fargate task  
> **LLM:** OpenAI (gpt-4o, gpt-4o-mini, text-embedding-3-small)  
> **Auth:** JWT + bcrypt, OIDC-based GitHub Actions CD  
> **Cache:** Upstash Redis (HTTP REST)  
> **Web Fallback:** Tavily  

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [IAM — Create Admin User](#2-iam--create-admin-user)
3. [Shell Variables](#3-shell-variables)
4. [Pre-Deployment: Create AWS Resources](#4-pre-deployment-create-aws-resources)
5. [Secrets Manager](#5-secrets-manager)
6. [Docker Build & ECR Push](#6-docker-build--ecr-push)
7. [Terraform: Deploy Infrastructure](#7-terraform-deploy-infrastructure)
8. [Verify Deployment](#8-verify-deployment)
9. [GitHub Actions CD Setup (OIDC)](#9-github-actions-cd-setup-oidc)
10. [Troubleshooting](#10-troubleshooting)
11. [CI/CD Flow Reference](#11-cicd-flow-reference)
12. [Rollback Procedure](#12-rollback-procedure)
13. [Cost Overview](#13-cost-overview)
14. [How to Stop (Save Money)](#14-how-to-stop-save-money-keep-data)
15. [How to Restart](#15-how-to-restart)
16. [How to Tear Down Everything](#16-how-to-tear-down-everything)

---

## 1. Prerequisites

### 1.1 AWS CLI v2

```bash
aws --version
# Expected: aws-cli/2.x.x
```

Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html

### 1.2 Docker

```bash
docker --version
# Expected: Docker version 24.x or higher
```

### 1.3 Terraform >= 1.5.0

```bash
terraform -version
# Expected: Terraform v1.5.x or higher
```

Install: https://developer.hashicorp.com/terraform/downloads

### 1.4 jq

```bash
brew install jq       # macOS
# apt-get install jq  # Ubuntu/Debian
```

### 1.5 GitHub CLI (optional, for setting secrets)

```bash
brew install gh
gh auth login
```

---

## 2. IAM — Create Admin User

This step is done **once via the AWS Console** using your root account.

### 2.1 Create the user

1. AWS Console → **IAM** → **Users** → **Create user**
2. **User name:** `adv-rag-admin`
3. Do **not** enable console access (CLI only)
4. Click **Next**

### 2.2 Attach permissions

Choose **"Attach policies directly"** → check **`AdministratorAccess`**

> `AdministratorAccess` is used here because the setup phase touches EC2, ECS, ECR, EFS, ALB, Secrets Manager, IAM, and CloudWatch. The CI/CD role created later is tightly scoped.

### 2.3 Generate access keys

1. Click through to **Create user**
2. Open the user → **Security credentials** tab → **Create access key**
3. Choose **"Command Line Interface (CLI)"** → confirm → **Create access key**
4. **Save the Access Key ID and Secret Access Key** — shown only once

### 2.4 Configure AWS CLI

```bash
aws configure --profile adv-rag-admin
# AWS Access Key ID:     <paste key id>
# AWS Secret Access Key: <paste secret key>
# Default region name:   us-east-1
# Default output format: json
```

### 2.5 Verify

```bash
aws sts get-caller-identity --profile adv-rag-admin
# Expected: "Arn": "arn:aws:iam::<account-id>:user/adv-rag-admin"
```

### 2.6 Export profile for the session

```bash
export AWS_PROFILE=adv-rag-admin
```

---

## 3. Shell Variables

Run these at the start of every terminal session before executing commands.

### 3.1 Retrieve your default VPC and subnets

```bash
# Get default VPC ID
aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query 'Vpcs[0].VpcId' \
  --output text \
  --region us-east-1

# List all default subnets (pick 2 from different AZs)
aws ec2 describe-subnets \
  --filters "Name=defaultForAz,Values=true" \
  --query 'Subnets[*].{SubnetId:SubnetId,AZ:AvailabilityZone}' \
  --output table \
  --region us-east-1
```

### 3.2 Export all variables

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
export PROJECT_NAME=adv-rag
export ENVIRONMENT=prod
export ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# Replace with your actual IDs from the commands above
export VPC_ID=vpc-XXXXXXXXXXXXXXXXX
export PUBLIC_SUBNET_IDS="subnet-XXXXXXXXXXXXXXXXX,subnet-YYYYYYYYYYYYYYYYY"
export PRIVATE_SUBNET_IDS="subnet-ZZZZZZZZZZZZZZZZZ,subnet-WWWWWWWWWWWWWWWWW"
```

### 3.3 Verify

```bash
echo "Account : $AWS_ACCOUNT_ID"
echo "Region  : $AWS_REGION"
echo "VPC     : $VPC_ID"
echo "Public  : $PUBLIC_SUBNET_IDS"
echo "Private : $PRIVATE_SUBNET_IDS"
echo "ECR     : $ECR_REGISTRY"
```

All lines must be non-empty before proceeding.

---

## 4. Pre-Deployment: Create AWS Resources

Use the included setup script to create prerequisite resources:

```bash
cd /path/to/My_project

# Set your actual secrets
export OPENAI_API_KEY="sk-..."
export JWT_SECRET="your-jwt-secret-min-32-chars"
export UPSTASH_REDIS_URL="https://..."
export UPSTASH_REDIS_TOKEN="..."
export TAVILY_API_KEY="tvly-..."

# Run the setup script
bash infra/setup.sh
```

This creates:
- **Secrets Manager** secrets for all runtime env vars
- **ECR repository** for the app image
- Prints next steps

### 4.1 Verify ECR repository

```bash
aws ecr describe-repositories \
  --repository-names "${PROJECT_NAME}-${ENVIRONMENT}-app" \
  --region $AWS_REGION \
  --query 'repositories[*].repositoryUri' \
  --output table
```

### 4.2 Verify secrets

```bash
aws secretsmanager list-secrets \
  --region $AWS_REGION \
  --query 'SecretList[*].Name' \
  --output table
```

Expected: `adv-rag/prod/openai-api-key`, `adv-rag/prod/jwt-secret`, etc.

---

## 5. Secrets Manager

The setup script already created secrets. To update a secret later:

```bash
aws secretsmanager put-secret-value \
  --secret-id "${PROJECT_NAME}/${ENVIRONMENT}/openai-api-key" \
  --secret-string "sk-...NEW-KEY..." \
  --region $AWS_REGION
```

> **Note:** After rotating a secret, force a new ECS deployment for the task to pick it up:
> ```bash
> aws ecs update-service \
>   --cluster "${PROJECT_NAME}-${ENVIRONMENT}-cluster" \
>   --service "${PROJECT_NAME}-${ENVIRONMENT}-service" \
>   --force-new-deployment \
>   --region $AWS_REGION
> ```

---

## 6. Docker Build & ECR Push

### 6.1 Login to ECR

```bash
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ECR_REGISTRY
```

### 6.2 Build the image

```bash
docker build -t "${ECR_REGISTRY}/${PROJECT_NAME}-${ENVIRONMENT}-app:latest" .
```

### 6.3 Push to ECR

```bash
docker push "${ECR_REGISTRY}/${PROJECT_NAME}-${ENVIRONMENT}-app:latest"
```

### 6.4 Verify

```bash
aws ecr describe-images \
  --repository-name "${PROJECT_NAME}-${ENVIRONMENT}-app" \
  --region $AWS_REGION \
  --query 'imageDetails[*].{tag:imageTags[0],pushed:imagePushedAt}' \
  --output table
```

---

## 7. Terraform: Deploy Infrastructure

### 7.1 Configure terraform.tfvars

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your actual values:

```hcl
project_name = "adv-rag"
environment  = "prod"
aws_region   = "us-east-1"

# Networking (from Step 3)
vpc_id             = "vpc-XXXXXXXXXXXXXXXXX"
public_subnet_ids  = ["subnet-XXXXXXXXXXXXXXXXX", "subnet-YYYYYYYYYYYYYYYYY"]
private_subnet_ids = ["subnet-ZZZZZZZZZZZZZZZZZ", "subnet-WWWWWWWWWWWWWWWWW"]

# Container image (from Step 6)
container_image = "123456789012.dkr.ecr.us-east-1.amazonaws.com/adv-rag-prod-app:latest"

# Secrets Manager ARNs (from Step 4)
openai_api_key_secret_arn      = "arn:aws:secretsmanager:us-east-1:123456789012:secret:adv-rag/prod/openai-api-key-XXXXXX"
jwt_secret_secret_arn          = "arn:aws:secretsmanager:us-east-1:123456789012:secret:adv-rag/prod/jwt-secret-XXXXXX"
database_url_secret_arn        = "arn:aws:secretsmanager:us-east-1:123456789012:secret:adv-rag/prod/database-url-XXXXXX"
upstash_redis_url_secret_arn   = "arn:aws:secretsmanager:us-east-1:123456789012:secret:adv-rag/prod/upstash-redis-url-XXXXXX"
upstash_redis_token_secret_arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:adv-rag/prod/upstash-redis-token-XXXXXX"
tavily_api_key_secret_arn      = "arn:aws:secretsmanager:us-east-1:123456789012:secret:adv-rag/prod/tavily-api-key-XXXXXX"

# Optional overrides
# ecs_task_cpu    = 2048
# ecs_task_memory = 16384
# desired_count   = 1
# enable_autoscaling = false
```

### 7.2 Initialize Terraform

```bash
terraform init
```

### 7.3 Plan

```bash
terraform plan -out=tfplan
```

Review the plan carefully. Expected resources:
- ECR repository
- ECS cluster + service + task definition (3 containers)
- ALB + target group + listener
- EFS filesystem + 3 access points
- Security groups (ALB, ECS, EFS)
- CloudWatch log group
- IAM roles and policies
- Optional: autoscaling target + policy

### 7.4 Apply

```bash
terraform apply tfplan
```

This takes ~5-10 minutes. Wait for completion.

### 7.5 Capture outputs

```bash
terraform output
```

Save these values:
- `ecr_repository_url`
- `ecs_cluster_name`
- `ecs_service_name`
- `alb_dns_name`
- `efs_file_system_id`
- `efs_access_point_id`
- `efs_qdrant_access_point_id`
- `efs_postgres_access_point_id`
- `cloudwatch_log_group_name`

---

## 8. Verify Deployment

### 8.1 Check service status

```bash
aws ecs describe-services \
  --cluster "${PROJECT_NAME}-${ENVIRONMENT}-cluster" \
  --services "${PROJECT_NAME}-${ENVIRONMENT}-service" \
  --region $AWS_REGION \
  --query 'services[*].{name:serviceName,running:runningCount,desired:desiredCount,status:status,pending:pendingCount}' \
  --output table
```

Expected: `runningCount == desiredCount == 1`, `status == ACTIVE`

### 8.2 Check ALB health

```bash
ALB_DNS=$(terraform output -raw alb_dns_name)
echo "ALB URL: http://${ALB_DNS}"

# Health check (public, no auth)
curl -s "http://${ALB_DNS}/admin/health" | python3 -m json.tool
```

Expected response:
```json
{
  "status": "ok",
  "qdrant": true,
  "postgres": true,
  "redis": true,
  "openai": true,
  "tavily": true
}
```

### 8.3 Check logs

```bash
aws logs tail "$(terraform output -raw cloudwatch_log_group_name)" --follow --region $AWS_REGION
```

### 8.4 Test authentication

```bash
# Register a test user
curl -s -X POST "http://${ALB_DNS}/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"tester@demo.local","password":"test1234"}' | python3 -m json.tool

# Login
curl -s -X POST "http://${ALB_DNS}/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"tester@demo.local","password":"test1234"}' | python3 -m json.tool
```

### 8.5 Test RAG query

```bash
TOKEN=$(curl -s -X POST "http://${ALB_DNS}/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin@demo.local","password":"admin123"}' | jq -r '.token')

curl -s -X POST "http://${ALB_DNS}/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "question": "What is the return policy?",
    "search_mode": "hybrid",
    "top_k": 5,
    "enable_hyde": false,
    "enable_rerank": true,
    "enable_crag": false,
    "enable_self_reflective": false
  }' | python3 -m json.tool
```

Expected: A `ChatResponse` with `answer`, `sources`, `confidence` fields.

---

## 9. GitHub Actions CD Setup (OIDC)

The CD workflow (`.github/workflows/cd.yml`) uses **OIDC authentication** — no long-lived AWS credentials in GitHub Secrets.

### 9.1 Create OIDC Identity Provider in IAM

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --thumbprint-list 6938fd4e98bab03faadb97b34396831e3780aea1 \
  --client-id-list sts.amazonaws.com \
  --region $AWS_REGION
```

> If the provider already exists, you'll get an error — that's fine, proceed to the next step.

### 9.2 Create the GitHub Actions IAM Role

```bash
# Get the OIDC provider ARN
OIDC_ARN=$(aws iam list-open-id-connect-providers \
  --query 'OpenIDConnectProviderList[?contains(Arn, `token.actions.githubusercontent.com`)].Arn' \
  --output text)
echo "OIDC ARN: $OIDC_ARN"

# Create the trust policy
cat > /tmp/github-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "${OIDC_ARN}"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:<your-github-org>/<your-repo>:*"
        }
      }
    }
  ]
}
EOF

# Create the role
aws iam create-role \
  --role-name "${PROJECT_NAME}-${ENVIRONMENT}-github-actions-deployer" \
  --assume-role-policy-document file:///tmp/github-trust-policy.json \
  --region $AWS_REGION
```

> **Replace `<your-github-org>/<your-repo>`** with your actual GitHub org and repository name (e.g., `yashprogrammer/Adv_rag`).

### 9.3 Attach deployer policy

```bash
cat > /tmp/github-deployer-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ECRAuth",
      "Effect": "Allow",
      "Action": ["ecr:GetAuthorizationToken"],
      "Resource": "*"
    },
    {
      "Sid": "ECRPushPull",
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "arn:aws:ecr:${AWS_REGION}:${AWS_ACCOUNT_ID}:repository/${PROJECT_NAME}-${ENVIRONMENT}-app"
    },
    {
      "Sid": "ECSDeploy",
      "Effect": "Allow",
      "Action": [
        "ecs:UpdateService",
        "ecs:DescribeServices",
        "ecs:DescribeTaskDefinition",
        "ecs:RegisterTaskDefinition",
        "ecs:ListTasks",
        "ecs:DescribeTasks"
      ],
      "Resource": "*"
    },
    {
      "Sid": "PassRole",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": [
        "arn:aws:iam::${AWS_ACCOUNT_ID}:role/${PROJECT_NAME}-${ENVIRONMENT}-ecs-execution-role",
        "arn:aws:iam::${AWS_ACCOUNT_ID}:role/${PROJECT_NAME}-${ENVIRONMENT}-ecs-task-role"
      ]
    },
    {
      "Sid": "ALBDescribe",
      "Effect": "Allow",
      "Action": [
        "elasticloadbalancing:DescribeLoadBalancers"
      ],
      "Resource": "*"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name "${PROJECT_NAME}-${ENVIRONMENT}-github-actions-deployer" \
  --policy-name "deployer-policy" \
  --policy-document file:///tmp/github-deployer-policy.json \
  --region $AWS_REGION
```

### 9.4 Get the role ARN

```bash
DEPLOYER_ROLE_ARN=$(aws iam get-role \
  --role-name "${PROJECT_NAME}-${ENVIRONMENT}-github-actions-deployer" \
  --query 'Role.Arn' \
  --output text)
echo "Deployer Role ARN: ${DEPLOYER_ROLE_ARN}"
```

### 9.5 Configure GitHub repository secrets and variables

#### Repository Secrets

| Secret | Value |
|--------|-------|
| `AWS_ROLE_TO_ASSUME` | The deployer role ARN from above |

#### Repository Variables (Settings → Secrets and variables → Actions → Variables tab)

| Variable | Value |
|----------|-------|
| `AWS_REGION` | `us-east-1` |
| `ECS_CLUSTER` | Output from `terraform output ecs_cluster_name` |
| `ECS_SERVICE` | Output from `terraform output ecs_service_name` |
| `ECS_TASK_FAMILY` | `${PROJECT_NAME}-${ENVIRONMENT}-task` |
| `ECR_REPOSITORY` | `${PROJECT_NAME}-${ENVIRONMENT}-app` |

Using GitHub CLI:

```bash
# Set secret
gh secret set AWS_ROLE_TO_ASSUME --body "${DEPLOYER_ROLE_ARN}"

# Set variables
gh variable set AWS_REGION --body "us-east-1"
gh variable set ECS_CLUSTER --body "$(terraform output -raw ecs_cluster_name)"
gh variable set ECS_SERVICE --body "$(terraform output -raw ecs_service_name)"
gh variable set ECS_TASK_FAMILY --body "${PROJECT_NAME}-${ENVIRONMENT}-task"
gh variable set ECR_REPOSITORY --body "${PROJECT_NAME}-${ENVIRONMENT}-app"
```

### 9.6 Trigger CD

```bash
git push origin main
```

Go to GitHub → Actions → CD workflow and verify it goes green.

---

## 10. Troubleshooting

### 10.1 — Task fails to start: `CannotPullContainerError`

**Symptom:** Task stops immediately after launch.

**Diagnose:**
```bash
aws ecs describe-tasks \
  --cluster "${PROJECT_NAME}-${ENVIRONMENT}-cluster" \
  --tasks <task-arn> \
  --region $AWS_REGION \
  --query 'tasks[0].stoppedReason'
```

**Fix:** Ensure ECS task execution role has ECR pull permissions. Terraform should have created this. If missing:
```bash
aws iam attach-role-policy \
  --role-name "${PROJECT_NAME}-${ENVIRONMENT}-ecs-execution-role" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

### 10.2 — Task fails: `AccessDeniedException` on Secrets Manager

**Symptom:** `TaskFailedToStart`, cannot read secrets.

**Diagnose:** Check CloudWatch logs or task stopped reason.

**Fix:** Ensure the execution role policy includes `secretsmanager:GetSecretValue` for your secret ARNs. Terraform creates this. Verify:
```bash
aws iam get-role-policy \
  --role-name "${PROJECT_NAME}-${ENVIRONMENT}-ecs-execution-role" \
  --policy-name "${PROJECT_NAME}-${ENVIRONMENT}-ecs-execution-secrets"
```

### 10.3 — ALB health checks failing: `Target.Timeout`

**Symptom:** ALB target stays unhealthy. Task is running but health checks time out.

**Diagnose:**
```bash
# Check target health
aws elbv2 describe-target-health \
  --target-group-arn "$(terraform output -raw alb_target_group_arn 2>/dev/null || echo 'check terraform state')" \
  --region $AWS_REGION

# Check security group rules
aws ec2 describe-security-groups \
  --group-ids $(terraform output -raw ecs_security_group_id 2>/dev/null || aws ec2 describe-security-groups --filters "Name=group-name,Values=${PROJECT_NAME}-${ENVIRONMENT}-ecs-tasks-sg" --query 'SecurityGroups[0].GroupId' --output text) \
  --region $AWS_REGION \
  --query 'SecurityGroups[0].IpPermissions'
```

**Fix:** Ensure ECS security group allows port 8000 from ALB security group. Terraform should configure this. If the ALB was recreated manually, the security group reference may be stale.

### 10.4 — `/admin/health` returns `degraded` or missing services

**Symptom:** Health endpoint shows some services as `false`.

**Diagnose:** Check which service is failing:
```bash
curl -s "http://${ALB_DNS}/admin/health" | python3 -m json.tool
```

**Common causes:**
- **Qdrant `false`:** Qdrant container is still starting. Wait 30-60 seconds and retry.
- **Postgres `false`:** Postgres container failed to start or is unhealthy. Check CloudWatch logs.
- **Redis `false`:** Upstash Redis URL/token is incorrect or network is unreachable. Verify secrets.
- **OpenAI `false`:** API key is invalid or rate-limited. Verify `OPENAI_API_KEY` secret.
- **Tavily `false`:** API key is missing. This is expected if you haven't configured Tavily.

### 10.5 — Query returns 500 or empty answer

**Diagnose:** Check CloudWatch logs for the app container:
```bash
aws logs tail "$(terraform output -raw cloudwatch_log_group_name)" --follow --region $AWS_REGION
```

**Common causes:**
- LangGraph checkpointer connection to Postgres failed
- OpenAI API key exhausted or invalid
- Qdrant collection not created yet (first query triggers creation)

### 10.6 — Qdrant NFS warning on EFS (harmless)

**Symptom:** Qdrant logs show warnings about NFS file locking.

**Explanation:** EFS is NFS-backed. Qdrant warns about this but runs normally. No action needed.

---

## 11. CI/CD Flow Reference

```
Push to main branch
        │
        ▼
┌─────────────────────────────────────┐
│  GitHub Actions: CI workflow        │
│  (ci.yml)                           │
│  ├── ruff format --check            │
│  ├── ruff check                     │
│  ├── mypy app/                      │
│  └── pytest                         │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  GitHub Actions: CD workflow        │
│  (cd.yml)                           │
│  ├── Configure AWS (OIDC)           │
│  ├── Login ECR                      │
│  ├── docker build + push :sha       │
│  ├── docker push :latest            │
│  ├── Render ECS task definition     │
│  ├── Register new task def          │
│  ├── Update ECS service             │
│  ├── Wait services-stable           │
│  └── Smoke test /admin/health       │
└─────────────────────────────────────┘
        │
        ▼
    Deployed ✅
```

Every deployment creates a new ECS task definition revision. Clean rollbacks are possible by updating the service to a previous revision.

---

## 12. Rollback Procedure

### 12.1 List recent task definition revisions

```bash
aws ecs list-task-definitions \
  --family-prefix "${PROJECT_NAME}-${ENVIRONMENT}-task" \
  --sort DESC \
  --region $AWS_REGION \
  --query 'taskDefinitionArns[:5]' \
  --output table
```

### 12.2 Roll back to a specific revision

```bash
# Replace 7 with the desired revision number
aws ecs update-service \
  --cluster "${PROJECT_NAME}-${ENVIRONMENT}-cluster" \
  --service "${PROJECT_NAME}-${ENVIRONMENT}-service" \
  --task-definition "${PROJECT_NAME}-${ENVIRONMENT}-task:7" \
  --region $AWS_REGION

# Wait for stable
aws ecs wait services-stable \
  --cluster "${PROJECT_NAME}-${ENVIRONMENT}-cluster" \
  --services "${PROJECT_NAME}-${ENVIRONMENT}-service" \
  --region $AWS_REGION

echo "Rollback complete."
```

---

## 13. Cost Overview

### Fixed charges (running 24/7 with 1 task)

| Service | Calculation | ~Monthly Cost |
|---------|------------|---------------|
| **ECS Fargate — 2 vCPU** | $0.04048/vCPU-hr × 2 × 730 hr | ~$59 |
| **ECS Fargate — 16 GB RAM** | $0.004445/GB-hr × 16 × 730 hr | ~$52 |
| **Application Load Balancer** | $0.0225/hr × 730 hr | ~$16 |
| **EFS storage (~10 GB)** | $0.30/GB-mo | ~$3 |
| **CloudWatch Logs** | ~$0.50/GB ingested | ~$1 |
| **Secrets Manager** | $0.40/secret × 6 secrets | ~$2.40 |
| **ECR storage** | $0.10/GB-mo | ~$0.20 |
| **Total fixed** | | **~$134/month** |

### Variable charges

| Service | Cost |
|---------|------|
| OpenAI API (embeddings + LLM) | Usage-dependent (~$0.002–$0.03 per request) |
| Upstash Redis | Free tier covers dev; paid ~$10/mo for production |
| Tavily web search | Free tier covers dev; paid ~$25/mo for production |
| ALB LCU | ~$0.008/LCU-hr |
| Data transfer out | $0.09/GB |

### Cost optimization

| Action | Monthly savings |
|--------|----------------|
| Scale ECS to 0 tasks | ~$111 (keeps ALB) |
| Delete ALB + scale to 0 | ~$127 (keeps EFS data) |
| Full teardown | ~$134 |

---

## 14. How to Stop (Save Money, Keep Data)

Scale the ECS service to zero tasks. Fargate billing stops immediately. EFS data (Qdrant vectors, Postgres data) is preserved.

```bash
aws ecs update-service \
  --cluster "${PROJECT_NAME}-${ENVIRONMENT}-cluster" \
  --service "${PROJECT_NAME}-${ENVIRONMENT}-service" \
  --desired-count 0 \
  --region $AWS_REGION

aws ecs wait services-stable \
  --cluster "${PROJECT_NAME}-${ENVIRONMENT}-cluster" \
  --services "${PROJECT_NAME}-${ENVIRONMENT}-service" \
  --region $AWS_REGION

echo "Service stopped. Fargate billing paused."
```

**What you still pay:**
- ALB: ~$16/month
- EFS: ~$3/month
- Secrets Manager: ~$2.40/month
- CloudWatch Logs: ~$1/month
- **Total while paused: ~$22/month**

---

## 15. How to Restart

```bash
aws ecs update-service \
  --cluster "${PROJECT_NAME}-${ENVIRONMENT}-cluster" \
  --service "${PROJECT_NAME}-${ENVIRONMENT}-service" \
  --desired-count 1 \
  --region $AWS_REGION

aws ecs wait services-stable \
  --cluster "${PROJECT_NAME}-${ENVIRONMENT}-cluster" \
  --services "${PROJECT_NAME}-${ENVIRONMENT}-service" \
  --region $AWS_REGION

echo "Service restarted."

# Verify health
ALB_DNS=$(terraform output -raw alb_dns_name)
curl -s "http://${ALB_DNS}/admin/health" | python3 -m json.tool
```

---

## 16. How to Tear Down Everything

> **⚠️ Warning: This is irreversible.** All data (Qdrant vectors, Postgres data, uploaded documents) will be permanently deleted.

### 16.1 Destroy Terraform-managed resources

```bash
cd infra/terraform
terraform destroy
```

Confirm with `yes`. This destroys:
- ECS cluster, service, task definition
- ALB, target group, listener
- EFS access points, mount targets, file system
- Security groups
- CloudWatch log group
- IAM roles and policies (if managed by Terraform)
- ECR repository (if managed by Terraform)

### 16.2 Delete remaining resources (if not managed by Terraform)

```bash
# Delete Secrets Manager secrets
for secret in openai-api-key jwt-secret database-url upstash-redis-url upstash-redis-token tavily-api-key; do
  aws secretsmanager delete-secret \
    --secret-id "${PROJECT_NAME}/${ENVIRONMENT}/${secret}" \
    --force-delete-without-recovery \
    --region $AWS_REGION 2>/dev/null || true
done

# Delete ECR repository (if it has images)
aws ecr delete-repository \
  --repository-name "${PROJECT_NAME}-${ENVIRONMENT}-app" \
  --force \
  --region $AWS_REGION 2>/dev/null || true

# Delete OIDC provider (optional)
OIDC_ARN=$(aws iam list-open-id-connect-providers \
  --query 'OpenIDConnectProviderList[?contains(Arn, `token.actions.githubusercontent.com`)].Arn' \
  --output text)
if [ -n "$OIDC_ARN" ]; then
  aws iam delete-open-id-connect-provider \
    --open-id-connect-provider-arn "$OIDC_ARN" 2>/dev/null || true
fi

# Delete GitHub Actions deployer role (optional)
aws iam delete-role \
  --role-name "${PROJECT_NAME}-${ENVIRONMENT}-github-actions-deployer" 2>/dev/null || true

echo "Teardown complete."
```

### 16.3 Verify nothing remains

```bash
echo "=== ECS Services ==="
aws ecs list-services --cluster "${PROJECT_NAME}-${ENVIRONMENT}-cluster" --region $AWS_REGION 2>&1 || true

echo "=== ALBs ==="
aws elbv2 describe-load-balancers --names "${PROJECT_NAME}-${ENVIRONMENT}-alb" --region $AWS_REGION 2>&1 | head -5 || true

echo "=== EFS ==="
aws efs describe-file-systems --creation-token "${PROJECT_NAME}-${ENVIRONMENT}-efs" --region $AWS_REGION 2>&1 | head -5 || true
```

---

## Quick Reference — Commands at a Glance

| Goal | Command |
|------|---------|
| **Deploy** | `terraform apply` |
| **Update image** | `docker build` → `docker push` → `terraform apply` (or push to main for CD) |
| **Check health** | `curl http://$(terraform output -raw alb_dns_name)/admin/health` |
| **View logs** | `aws logs tail $(terraform output -raw cloudwatch_log_group_name) --follow` |
| **Scale to 0** | `aws ecs update-service --desired-count 0` |
| **Scale to 1** | `aws ecs update-service --desired-count 1` |
| **Rollback** | `aws ecs update-service --task-definition family:revision` |
| **Destroy** | `terraform destroy` |

---

*Last updated: 2026-05-01 | Stack: ECS Fargate + ECR + EFS + ALB + Postgres + Qdrant + OpenAI | CD: GitHub Actions OIDC*