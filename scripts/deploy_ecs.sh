#!/usr/bin/env bash

set -euo pipefail

: "${ECS_CLUSTER:?ECS_CLUSTER is required}"
: "${ECS_SERVICE:?ECS_SERVICE is required}"
: "${ECS_TASK_DEFINITION_PATH:?ECS_TASK_DEFINITION_PATH is required}"
: "${AWS_REGION:?AWS_REGION is required}"

register_output="$(aws ecs register-task-definition --cli-input-json "file://${ECS_TASK_DEFINITION_PATH}" --region "${AWS_REGION}")"
task_definition_arn="$(printf '%s' "${register_output}" | jq -r '.taskDefinition.taskDefinitionArn')"

if [[ -z "${task_definition_arn}" || "${task_definition_arn}" == "null" ]]; then
  echo "Failed to register ECS task definition"
  exit 1
fi

aws ecs update-service \
  --cluster "${ECS_CLUSTER}" \
  --service "${ECS_SERVICE}" \
  --task-definition "${task_definition_arn}" \
  --region "${AWS_REGION}" \
  --force-new-deployment \
  >/dev/null

aws ecs wait services-stable \
  --cluster "${ECS_CLUSTER}" \
  --services "${ECS_SERVICE}" \
  --region "${AWS_REGION}"
