terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  # Helpful for local validation flows that should not contact AWS APIs.
  skip_credentials_validation = var.aws_provider_skip_credentials_validation
  skip_metadata_api_check     = var.aws_provider_skip_metadata_api_check
  skip_requesting_account_id  = var.aws_provider_skip_requesting_account_id
}
