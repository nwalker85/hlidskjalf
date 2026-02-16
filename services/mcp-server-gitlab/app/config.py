from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the MCP GitLab server."""

    model_config = SettingsConfigDict(case_sensitive=False)

    app_name: str = "mcp-server-gitlab"
    host: str = "0.0.0.0"
    port: int = Field(default=9400, alias="MCP_SERVICE_PORT")

    gitlab_base_url: str = Field(
        default="https://gitlab.ravenhelm.test", alias="GITLAB_BASE_URL"
    )
    gitlab_api_url: str = Field(
        default="http://gitlab", alias="GITLAB_API_URL"
    )  # internal URL for speed
    gitlab_project_path: str = Field(
        default="ravenhelm/hlidskjalf", alias="GITLAB_PROJECT_PATH"
    )
    gitlab_verify_ssl: bool = Field(default=False, alias="GITLAB_VERIFY_SSL")

    # Secrets
    gitlab_token: str | None = Field(default=None, alias="GITLAB_MCP_TOKEN")
    gitlab_wiki_token: str | None = Field(default=None, alias="GITLAB_WIKI_TOKEN")
    gitlab_secret_name: str = Field(
        default="ravenhelm/dev/gitlab/mcp_service",
        alias="GITLAB_MCP_SECRET_NAME",
    )

    # Zitadel
    zitadel_base_url: str = Field(
        default="https://zitadel.ravenhelm.test", alias="ZITADEL_BASE_URL"
    )
    zitadel_project_id: str = Field(
        default="349394492048015386", alias="ZITADEL_PROJECT_ID"
    )
    zitadel_service_account_token: str | None = Field(
        default=None, alias="ZITADEL_SERVICE_ACCOUNT_TOKEN"
    )
    zitadel_service_account_secret: str = Field(
        default="ravenhelm/dev/zitadel/service_account",
        alias="ZITADEL_SERVICE_ACCOUNT_SECRET",
    )
    zitadel_verify_ssl: bool = Field(default=False, alias="ZITADEL_VERIFY_SSL")

    # Docker host (used for docker MCP tools)
    docker_host: str = Field(default="unix:///var/run/docker.sock", alias="DOCKER_HOST")

    # LocalStack / AWS Secrets Manager
    aws_access_key_id: str = Field(default="test", alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="test", alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    localstack_endpoint: str | None = Field(
        default="http://localstack:4566", alias="LOCALSTACK_ENDPOINT"
    )

    knowledge_reference_doc: str = Field(
        default="docs/KNOWLEDGE_AND_PROCESS.md",
        alias="KNOWLEDGE_REFERENCE_DOC",
    )

    # TLS / SPIRE
    tls_cert_file: str = Field(default="/run/spire/certs/svid.pem", alias="TLS_CERT_FILE")
    tls_key_file: str = Field(default="/run/spire/certs/key.pem", alias="TLS_KEY_FILE")
    tls_ca_file: str = Field(default="/run/spire/certs/bundle.pem", alias="TLS_CA_FILE")
    tls_require_client_cert: bool = Field(
        default=False, alias="TLS_REQUIRE_CLIENT_CERT"
    )

    # OAuth enforcement
    oauth_issuer: str = Field(default="https://zitadel.ravenhelm.test", alias="OAUTH_ISSUER")
    oauth_jwks_url: str = Field(
        default="https://zitadel.ravenhelm.test/oauth/v2/keys", alias="OAUTH_JWKS_URL"
    )
    oauth_audience: str | None = Field(default=None, alias="OAUTH_AUDIENCE")
    oauth_required_scope: str = Field(
        default="mcp.gitlab.manage", alias="OAUTH_REQUIRED_SCOPE"
    )
    oauth_cache_ttl: int = Field(default=300, alias="OAUTH_CACHE_TTL_SECONDS")

@lru_cache
def get_settings() -> Settings:
    return Settings()

