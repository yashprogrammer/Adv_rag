# Terraform: ECR + ECS Fargate + EFS + ALB

This module provisions production-practical AWS infrastructure for the FastAPI app:

- ECR repository for app image storage
- ECS Cluster, Task Definition, and Fargate Service
- ALB, target group, and HTTP listener forwarding to ECS
- Security groups for ALB, ECS tasks, and EFS
- EFS filesystem, mount targets, and access point mounted in task
- CloudWatch log group for ECS logs
- Secrets Manager runtime environment variable wiring
- Optional ECS autoscaling policy

## Prerequisites

- Existing VPC and subnets (passed as variables)
- Terraform >= 1.5.0
- AWS provider ~> 5.0

## Files

- `providers.tf`: Terraform and provider configuration
- `variables.tf`: explicit inputs and defaults
- `main.tf`: resources
- `outputs.tf`: key outputs
- `terraform.tfvars.example`: copy to `terraform.tfvars` and edit values

## Usage

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

## Notes on Local Validation

To support test and local validation flows without real AWS credentials, provider flags default to:

- `aws_provider_skip_credentials_validation = true`
- `aws_provider_skip_metadata_api_check = true`
- `aws_provider_skip_requesting_account_id = true`

Set these to `false` for normal AWS-backed planning/apply in CI or deployment environments.

## Runtime Secret Env Vars

The ECS task injects these as secrets:

- `OPENAI_API_KEY`
- `JWT_SECRET`
- `DATABASE_URL`
- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`
- `TAVILY_API_KEY`

Each is configured via a corresponding input variable ending in `_secret_arn`.
