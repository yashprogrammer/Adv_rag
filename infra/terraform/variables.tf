variable "project_name" {
  description = "Project/application name used in resource naming."
  type        = string
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)."
  type        = string
}

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
}

variable "vpc_id" {
  description = "Existing VPC ID where ECS/ALB/EFS resources are deployed."
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for ALB and EFS mount targets."
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for ECS tasks."
  type        = list(string)
}

variable "container_image" {
  description = "Container image URI (usually from ECR) for the FastAPI app."
  type        = string
}

variable "container_port" {
  description = "App container listening port."
  type        = number
  default     = 8000
}

variable "ecs_task_cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 2048
}

variable "ecs_task_memory" {
  description = "Fargate task memory (MiB)."
  type        = number
  default     = 16384
}

variable "desired_count" {
  description = "Desired number of ECS tasks."
  type        = number
  default     = 1
}

variable "assign_public_ip" {
  description = "Whether ECS tasks should get a public IP."
  type        = bool
  default     = false
}

variable "health_check_path" {
  description = "ALB target group health check path."
  type        = string
  default     = "/admin/health"
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days."
  type        = number
  default     = 14
}

variable "efs_transition_to_ia" {
  description = "EFS lifecycle transition policy (AFTER_7_DAYS, AFTER_14_DAYS, AFTER_30_DAYS, AFTER_60_DAYS, AFTER_90_DAYS)."
  type        = string
  default     = "AFTER_30_DAYS"
}

variable "openai_api_key_secret_arn" {
  description = "Secrets Manager secret ARN for OPENAI_API_KEY."
  type        = string
}

variable "jwt_secret_secret_arn" {
  description = "Secrets Manager secret ARN for JWT_SECRET."
  type        = string
}

variable "database_url_secret_arn" {
  description = "Secrets Manager secret ARN for DATABASE_URL."
  type        = string
}

variable "upstash_redis_url_secret_arn" {
  description = "Secrets Manager secret ARN for UPSTASH_REDIS_URL."
  type        = string
}

variable "upstash_redis_token_secret_arn" {
  description = "Secrets Manager secret ARN for UPSTASH_REDIS_TOKEN."
  type        = string
}

variable "tavily_api_key_secret_arn" {
  description = "Secrets Manager secret ARN for TAVILY_API_KEY."
  type        = string
}

variable "enable_autoscaling" {
  description = "Enable ECS service autoscaling based on CPU usage."
  type        = bool
  default     = false
}

variable "autoscaling_min_capacity" {
  description = "Autoscaling minimum ECS task count."
  type        = number
  default     = 1
}

variable "autoscaling_max_capacity" {
  description = "Autoscaling maximum ECS task count."
  type        = number
  default     = 4
}

variable "autoscaling_target_cpu" {
  description = "Target average ECS CPU utilization percentage."
  type        = number
  default     = 60
}

variable "aws_provider_skip_credentials_validation" {
  description = "Set true for local/offline validation without AWS credentials."
  type        = bool
  default     = true
}

variable "aws_provider_skip_metadata_api_check" {
  description = "Set true to skip EC2 metadata API checks in local validation."
  type        = bool
  default     = true
}

variable "aws_provider_skip_requesting_account_id" {
  description = "Set true to avoid account ID lookup during local validation."
  type        = bool
  default     = true
}
