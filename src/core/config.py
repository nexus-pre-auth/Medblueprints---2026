"""
MedBlueprints Core Configuration
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Anthropic Claude API
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    claude_model: str = Field(default="claude-opus-4-6", validation_alias="CLAUDE_MODEL")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./medblueprints.db",
        validation_alias="DATABASE_URL",
    )

    # Neo4j Graph Database
    neo4j_uri: str = Field(default="bolt://localhost:7687", validation_alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", validation_alias="NEO4J_USER")
    neo4j_password: str = Field(default="", validation_alias="NEO4J_PASSWORD")
    use_neo4j: bool = Field(default=False, validation_alias="USE_NEO4J")

    # Vector Search
    embeddings_model: str = Field(default="all-MiniLM-L6-v2", validation_alias="EMBEDDINGS_MODEL")
    faiss_index_path: str = Field(default="./data/regulatory_index.faiss", validation_alias="FAISS_INDEX_PATH")

    # Approval Prediction Model
    model_path: str = Field(default="./data/approval_model.joblib", validation_alias="MODEL_PATH")

    # AR Visualization
    ar_output_path: str = Field(default="./data/ar_outputs", validation_alias="AR_OUTPUT_PATH")
    webxr_base_url: str = Field(default="http://localhost:8000/ar", validation_alias="WEBXR_BASE_URL")

    # CORS
    cors_origins: str = Field(default="*", validation_alias="CORS_ORIGINS")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # Logging
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")


settings = Settings()
