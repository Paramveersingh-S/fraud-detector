from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FRAUD_")

    redis_url: str = "redis://localhost:6379/0"
    model_path: str = "models/fraud_spike_lgbm.txt"
    model_manifest_path: str = "models/manifest.json"
    score_threshold_override: float | None = None  # falls back to manifest value
    velocity_windows_seconds: tuple[int, ...] = (3600, 86400)
    service_name: str = "fraud-spike-detector"
    log_level: str = "INFO"

settings = Settings()
