"""Central configuration loaded from environment variables (.env supported)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "FMN-AI Operations Agent"
    environment: str = "development"

    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 720

    admin_username: str = "admin"
    admin_password: str = "admin123"

    database_url: str = "sqlite:///./fmn.db"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "*"

    use_blockchain: bool = True
    use_vision: bool = False
    use_voice: bool = True
    scheduler_enabled: bool = True

    autonomy_level: int = 1

    blockchain_mode: str = "local"
    fabric_channel: str = "fmn-channel"
    fabric_chaincode: str = "fmn"
    fabric_msp_id: str = "FmnMSP"
    fabric_user: str = "Admin"
    fabric_gateway_endpoint: str = "localhost:7051"
    ethereum_rpc_url: str | None = None
    ethereum_contract_address: str | None = None

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    hedging_api_url: str | None = None

    vector_db_url: str = "http://localhost:6333"
    mongo_url: str | None = None
    s3_bucket: str | None = None

    fx_alert_threshold_pct: float = 2.0
    diesel_price_per_litre: float = 850.0
    grid_tariff_per_kwh: float = 65.0
    gas_tariff_per_kwh: float = 45.0
    solar_tariff_per_kwh: float = 8.0
    target_efficiency: float = 0.92
    orchestrator_interval_hours: int = 6

    # Performance tuning
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_recycle: int = 3600
    rate_limit_per_minute: int = 120
    cache_default_ttl: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
