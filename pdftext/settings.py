import os.path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BASE_PATH: str = os.path.dirname(os.path.dirname(__file__))
    MODEL_PATH: str = os.path.join(BASE_PATH, "models", "dt.joblib")

    # How many characters to buffer when reading a font name
    FONT_BUFFER_SIZE: int = 1024
    FONTNAME_SAMPLE_FREQ: int = 10

    # Benchmark
    RESULTS_FOLDER: str = "results"
    BENCH_DATASET_NAME: str = "vikp/pdf_bench"


settings = Settings()
