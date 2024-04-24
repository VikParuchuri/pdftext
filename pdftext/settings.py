import os.path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BASE_PATH: str = os.path.dirname(os.path.dirname(__file__))
    MODEL_PATH: str = os.path.join(BASE_PATH, "models", "dt.joblib")


settings = Settings()
