"""Unit tests for CD workflow and ECS deploy helper script."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CD_WORKFLOW = ROOT / ".github" / "workflows" / "cd.yml"
DEPLOY_SCRIPT = ROOT / "scripts" / "deploy_ecs.sh"


def test_cd_workflow_file_exists() -> None:
    assert CD_WORKFLOW.exists()


def test_cd_workflow_contains_required_permissions() -> None:
    content = CD_WORKFLOW.read_text(encoding="utf-8")
    assert "permissions:" in content
    assert "id-token: write" in content
    assert "contents: read" in content


def test_cd_workflow_has_oidc_credentials_step() -> None:
    content = CD_WORKFLOW.read_text(encoding="utf-8")
    assert "aws-actions/configure-aws-credentials@v4" in content
    assert "role-to-assume:" in content


def test_cd_workflow_has_ecr_build_push_and_deploy_steps() -> None:
    content = CD_WORKFLOW.read_text(encoding="utf-8")
    assert "aws-actions/amazon-ecr-login@v2" in content
    assert "docker build" in content
    assert "docker push" in content
    assert "Render ECS task definition" in content
    assert "Deploy ECS service" in content


def test_deploy_script_exists_with_expected_commands() -> None:
    assert DEPLOY_SCRIPT.exists()
    content = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    assert content.startswith("#!/usr/bin/env bash")
    assert "aws ecs register-task-definition" in content
    assert "aws ecs update-service" in content
    assert "aws ecs wait services-stable" in content
