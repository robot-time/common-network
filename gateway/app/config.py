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

    # Local dev runs uvicorn from gateway/, where catalogue/ is a sibling
    # directory (../catalogue). The Docker image copies catalogue/ in as a
    # child of /app instead -- Railway sets CATALOGUE_SEED_FILE=catalogue/...
    # to override this default for deployment.
    catalogue_seed_file: str = "../catalogue/catalogue.seed.yaml"
    catalogue_seed_on_startup: bool = True

    # Routing refinement (v0.3): below this *topical* score (similarity + tag
    # overlap only, not cost/latency -- see ScoredNode.topical_score), prefer
    # a generalist node over a low-confidence specialist match. Calibrated
    # empirically: observed topical scores clustered ~0.35-0.40 for vague/
    # generic queries and ~0.47+ for clearly on-topic ones in local testing.
    routing_confidence_threshold: float = 0.40
    # Tag overlap contributes this weight alongside the existing similarity/
    # cost/latency score (see app/router.py).
    w_tag_overlap: float = 0.15

    # Node onboarding (v0.3): only ever assign a catalogue model if it leaves
    # this much RAM headroom, so a specialist never swaps and times out.
    assignment_ram_headroom: float = 0.8


settings = Settings()
