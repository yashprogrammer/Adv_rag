#!/usr/bin/env bash
# Deploy ADV RAG to AWS using CloudFormation

set -euo pipefail

STACK_NAME="${STACK_NAME:-adv-rag-prod}"
TEMPLATE_FILE="${TEMPLATE_FILE:-infra/cloudformation.yaml}"
PARAMS_FILE="${PARAMS_FILE:-infra/cloudformation-params.json}"
AWS_REGION="${AWS_REGION:-us-east-1}"

if [[ ! -f "$PARAMS_FILE" ]]; then
    echo "❌ Parameters file not found: $PARAMS_FILE"
    echo "Copy the example and fill in your values:"
    echo "  cp infra/cloudformation-params.json.example infra/cloudformation-params.json"
    exit 1
fi

echo "=== Deploying CloudFormation stack: $STACK_NAME ==="
echo "Template: $TEMPLATE_FILE"
echo "Params:   $PARAMS_FILE"
echo "Region:   $AWS_REGION"
echo ""

# Check if stack exists
if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
    echo "Stack exists. Updating..."
    aws cloudformation update-stack \
        --stack-name "$STACK_NAME" \
        --template-body "file://$TEMPLATE_FILE" \
        --parameters "file://$PARAMS_FILE" \
        --capabilities CAPABILITY_IAM \
        --region "$AWS_REGION" || {
            echo "No changes to update."
            exit 0
        }
else
    echo "Stack does not exist. Creating..."
    aws cloudformation create-stack \
        --stack-name "$STACK_NAME" \
        --template-body "file://$TEMPLATE_FILE" \
        --parameters "file://$PARAMS_FILE" \
        --capabilities CAPABILITY_IAM \
        --region "$AWS_REGION"
fi

echo ""
echo "Waiting for stack to complete..."
aws cloudformation wait stack-update-complete \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" 2>/dev/null || \
aws cloudformation wait stack-create-complete \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION"

echo ""
echo "✅ Stack deployment complete!"
echo ""

# Print outputs
echo "=== Stack Outputs ==="
aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

# Get ALB DNS
ALB_DNS=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`AlbDnsName`].OutputValue' \
    --output text)

echo ""
echo "=== Quick Verification ==="
echo "Health URL: http://${ALB_DNS}/admin/health"
echo ""
echo "Test with:"
echo "  curl -s http://${ALB_DNS}/admin/health | python3 -m json.tool"
