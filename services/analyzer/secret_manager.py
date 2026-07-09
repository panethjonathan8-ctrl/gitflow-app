import boto3
import os
from botocore.exceptions import ClientError


def get_github_token() -> str:
    """
    Fetch the GitHub token from AWS Secrets Manager.

    In production: fetches from Secrets Manager using the EC2 instance's
    IAM role — no credentials needed in code.

    In local development: reads from the GITHUB_TOKEN environment variable
    so you do not need AWS credentials just to run the app locally.
    """

    # Local development fallback.
    # When running locally you set GITHUB_TOKEN in your .env file.
    # When running on EC2 this env var is not set so it falls through
    # to the Secrets Manager call below.
    local_token = os.environ.get("GITHUB_TOKEN")
    if local_token:
        return local_token

    # Build the secret name from environment variables.
    # This means the same code works in dev, staging, and prod
    # because each environment has different values for these vars.
    project = os.environ.get("PROJECT_NAME", "gitflow-analyzer")
    env = os.environ.get("ENVIRONMENT", "dev")
    secret_name = f"{project}/{env}/github-token"

    # Create a Secrets Manager client.
    # On EC2 this automatically uses the instance's IAM role credentials.
    # No access keys needed anywhere in this code.
    region = os.environ.get("AWS_REGION", "eu-west-1")
    client = boto3.client("secretsmanager", region_name=region)

    try:
        response = client.get_secret_value(SecretId=secret_name)
        # get_secret_value returns the secret as a string.
        # Some secrets are stored as JSON, some as plain strings.
        # A GitHub token is a plain string so we return it directly.
        return response["SecretString"]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ResourceNotFoundException":
            raise ValueError(f"Secret {secret_name} not found in Secrets Manager")
        elif error_code == "AccessDeniedException":
            raise ValueError(
                f"IAM role does not have permission to read {secret_name}. "
                "Check the EC2 instance role has the read-secrets policy attached."
            )
        else:
            raise
