from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    stake_api_token: str = ""
    bet_amount: float = 0.00001
    mines_count: int = 3
    max_rounds: int = 50
    auto_cashout_multiplier: float = 1.5
    bet_delay: float = 2.0
    strategy: str = "conservative"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
