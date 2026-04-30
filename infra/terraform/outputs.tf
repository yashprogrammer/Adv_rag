output "ecr_repository_url" {
  description = "ECR repository URL for pushing the app image."
  value       = aws_ecr_repository.app.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "ECS service name."
  value       = aws_ecs_service.app.name
}

output "alb_dns_name" {
  description = "Public DNS name of the application load balancer."
  value       = aws_lb.app.dns_name
}

output "efs_file_system_id" {
  description = "EFS file system ID used by the service."
  value       = aws_efs_file_system.app.id
}

output "efs_access_point_id" {
  description = "EFS access point ID mounted by ECS tasks."
  value       = aws_efs_access_point.app.id
}

output "cloudwatch_log_group_name" {
  description = "CloudWatch log group for ECS task logs."
  value       = aws_cloudwatch_log_group.app.name
}
