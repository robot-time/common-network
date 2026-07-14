from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://localhost/common_network"
    registry_secret: str = "change-me-dev-secret"

    embed_model_name: str = "BAAI/bge-small-en-v1.5"
    embed_dim: int = 384

    # Routing weights. Must not be relied on to sum to 1 exactly; kept simple and tunable.
    w_sim: float = 0.7
    w_cost: float = 0.15
    w_lat: float = 0.15
    region_bonus: float = 0.05

    health_check_interval_seconds: int = 30
    health_check_timeout_seconds: float = 5.0
    forward_timeout_seconds: float = 60.0

    seed_file: str = "nodes.seed.yaml"
    seed_on_startup: bool = True


settings = Settings()
