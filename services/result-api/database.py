import os
import json
import logging
from datetime import datetime, timezone, timedelta

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

CACHE_TTL_HOURS = 1


def _get_db_password() -> str:
    """Fetch the DB password from Secrets Manager, with a local env var fallback."""
    local = os.environ.get("DB_PASSWORD")
    if local:
        return local

    project = os.environ.get("PROJECT_NAME", "gitflow-analyzer")
    env = os.environ.get("ENVIRONMENT", "dev")
    region = os.environ.get("AWS_REGION", "eu-west-1")
    secret_name = f"{project}/{env}/db-password"

    client = boto3.client("secretsmanager", region_name=region)
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return response["SecretString"]
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "ResourceNotFoundException":
            raise ValueError(f"Secret {secret_name} not found in Secrets Manager")
        raise


def get_engine():
    """Build a SQLAlchemy engine from environment variables and Secrets Manager."""
    host = os.environ.get("DB_HOST")
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ.get("DB_NAME", "gitflow")
    user = os.environ.get("DB_USER", "gitflow")

    if not host:
        raise ValueError("DB_HOST environment variable is not set")

    password = _get_db_password()
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
    return create_engine(url, pool_pre_ping=True)
    # pool_pre_ping=True tests the connection before using it from the pool,
    # so the app recovers automatically if RDS restarts or the idle connection drops.


def init_db(engine) -> None:
    """Create the analyses table if it does not already exist."""
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS analyses (
                id          SERIAL PRIMARY KEY,
                repo_url    TEXT NOT NULL,
                result      JSONB NOT NULL,
                analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS analyses_repo_url_time_idx
            ON analyses (repo_url, analyzed_at DESC)
        """))
    logger.info("Database initialised")


def get_cached_result(engine, repo_url: str) -> dict | None:
    """
    Return the most recent cached analysis for repo_url if it is less than
    CACHE_TTL_HOURS old, otherwise return None.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=CACHE_TTL_HOURS)
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT result, analyzed_at
                FROM analyses
                WHERE repo_url = :url AND analyzed_at > :cutoff
                ORDER BY analyzed_at DESC
                LIMIT 1
            """),
            {"url": repo_url, "cutoff": cutoff},
        ).fetchone()

    if row:
        logger.info("Cache hit for %s (analyzed at %s)", repo_url, row.analyzed_at)
        return dict(row.result)
    return None


def store_result(engine, repo_url: str, result: dict) -> None:
    """Persist an analysis result to the database."""
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO analyses (repo_url, result)
                VALUES (:url, CAST(:result AS jsonb))
            """),
            {"url": repo_url, "result": json.dumps(result)},
        )
    logger.info("Stored result for %s", repo_url)
