from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./store.db"
    paystack_secret_key: str = ""
    paystack_base_url: str = "https://api.paystack.co"
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173"
    admin_api_key: str = "change-me"


settings = Settings()

# Delivery fees in naira, keyed by zone id (must match the frontend).
ZONES = {
    "lagos": {"label": "Lagos", "fee": 3000},
    "sw": {"label": "South-West (Ogun, Oyo, Osun, Ekiti, Ondo)", "fee": 4000},
    "sess": {"label": "South-East / South-South", "fee": 5000},
    "nc": {"label": "North Central + FCT", "fee": 5500},
    "fn": {"label": "Far North", "fee": 6500},
}
