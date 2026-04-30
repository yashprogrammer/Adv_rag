from pathlib import Path

TERRAFORM_DIR = Path("infra/terraform")


def test_required_terraform_files_exist() -> None:
    required_files = [
        "providers.tf",
        "variables.tf",
        "main.tf",
        "outputs.tf",
        "README.md",
        "terraform.tfvars.example",
    ]

    for file_name in required_files:
        assert (TERRAFORM_DIR / file_name).exists(), f"Missing {file_name}"


def test_main_tf_contains_required_resources() -> None:
    main_tf = (TERRAFORM_DIR / "main.tf").read_text(encoding="utf-8")

    required_tokens = [
        'resource "aws_ecr_repository" "app"',
        'resource "aws_ecs_cluster" "main"',
        'resource "aws_ecs_task_definition" "app"',
        'resource "aws_ecs_service" "app"',
        'resource "aws_lb" "app"',
        'resource "aws_lb_target_group" "app"',
        'resource "aws_lb_listener" "http"',
        'resource "aws_security_group" "alb"',
        'resource "aws_security_group" "ecs_tasks"',
        'resource "aws_efs_file_system" "app"',
        'resource "aws_efs_mount_target" "app"',
        'resource "aws_efs_access_point" "app"',
        'resource "aws_cloudwatch_log_group" "app"',
        "OPENAI_API_KEY",
        "JWT_SECRET",
        "DATABASE_URL",
        "UPSTASH_REDIS_REST_URL",
        "UPSTASH_REDIS_REST_TOKEN",
        "TAVILY_API_KEY",
    ]

    for token in required_tokens:
        assert token in main_tf, f"Expected token not found: {token}"
