"""Configuration settings for the PDF extractor."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM Configuration
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    default_provider: str = "anthropic"  # "openai" or "anthropic"

    # OpenAI settings
    openai_model: str = "gpt-4o"

    # Anthropic settings
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Processing settings
    dpi: int = 300  # Resolution for PDF to image conversion
    max_retries: int = 3

    # Output settings
    output_dir: str = "output"
    figures_dir: str = "figures"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
