#!/usr/bin/env bash
# One-command AWS provisioning script for ADV RAG.
# This script creates the prerequisite AWS resources that Terraform consumes.
# Run this BEFORE `terraform apply`.

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
PROJECT_NAME="${PROJECT_NAME:-adv-rag}"
ENVIRONMENT="${ENVIRONMENT:-prod}"

# Secrets values (set these environment variables before running)
OPENAI_API_KEY="${OPENAI_API_KEY:-}"
JWT_SECRET="${JWT_SECRET:-change-me-in-production}"
DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/adv_rag}"
UPSTASH_REDIS_URL="${UPSTASH_REDIS_URL:-}"
UPSTASH_REDIS_TOKEN="${UPSTASH_REDIS_TOKEN:-}"
TAVILY_API_KEY="${TAVILY_API_KEY:-}"

echo "=== ADV RAG AWS Setup ==="
echo "Region: $AWS_REGION"
echo "Project: $PROJECT_NAME"
echo "Environment: $ENVIRONMENT"
echo ""

# Helper function to create or update a secret
create_secret() {
  local name="$1"
  local value="$2"
  local secret_name="${PROJECT_NAME}/${ENVIRONMENT}/${name}"

  if aws secretsmanager describe-secret --secret-id "$secret_name" --region "$AWS_REGION" >/dev/null 2>&1; then
    echo "Secret exists: $secret_name"
    if [[ -n "$value" ]]; then
      aws secretsmanager put-secret-value \
        --secret-id "$secret_name" \
        --secret-string "$value" \
        --region "$AWS_REGION" >/dev/null
      echo "  Updated secret value"
    fi
  else
    if [[ -n "$value" ]]; then
      aws secretsmanager create-secret \
        --name "$secret_name" \
        --secret-string "$value" \
        --region "$AWS_REGION" >/dev/null
      echo "Created secret: $secret_name"
    else
      echo "WARNING: Secret $secret_name not created (value is empty)"
    fi
  fi
}

echo "--- Creating Secrets Manager secrets ---"
create_secret "openai-api-key" "$OPENAI_API_KEY"
create_secret "jwt-secret" "$JWT_SECRET"
create_secret "database-url" "$DATABASE_URL"
create_secret "upstash-redis-url" "$UPSTASH_REDIS_URL"
create_secret "upstash-redis-token" "$UPSTASH_REDIS_TOKEN"
create_secret "tavily-api-key" "$TAVILY_API_KEY"

echo ""
echo "--- ECR Repository ---"
ECR_REPO_NAME="${PROJECT_NAME}-${ENVIRONMENT}-app"
if aws ecr describe-repositories --repository-names "$ECR_REPO_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "ECR repository exists: $ECR_REPO_NAME"
else
  aws ecr create-repository \
    --repository-name "$ECR_REPO_NAME" \
    --region "$AWS_REGION" \
    --image-scanning-configuration scanOnPush=true \
    --image-tag-mutability MUTABLE >/dev/null
  echo "Created ECR repository: $ECR_REPO_NAME"
fi

# Get ECR login and print push commands
ECR_REGISTRY="$(aws sts get-caller-identity --query 'Account' --output text).dkr.ecr.${AWS_REGION}.amazonaws.com"
echo ""
echo "=== Next Steps ==="
echo "1. Build and push the Docker image:"
echo "   aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY"
echo "   docker build -t $ECR_REGISTRY/$ECR_REPO_NAME:latest ."
echo "   docker push $ECR_REGISTRY/$ECR_REPO_NAME:latest"
echo ""
echo "2. Copy CloudFormation params example and fill in values:"
echo "   cd infra/"
echo "   cp cloudformation-params.json.example cloudformation-params.json"
echo "   # Edit cloudformation-params.json with your VPC/subnet IDs and secret ARNs"
echo ""
echo "3. Deploy with CloudFormation:"
echo "   ./deploy-cloudformation.sh"
echo ""
echo "4. Push to main branch to trigger CD pipeline."
