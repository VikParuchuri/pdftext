import os.path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BASE_PATH: str = os.path.dirname(os.path.dirname(__file__))
    MODEL_PATH: str = os.path.join(BASE_PATH, "models", "dt.joblib")

    # Fonts
    FONT_BUFFER_SIZE: int = 1024 # How many characters to buffer when reading a font name
    FONTNAME_SAMPLE_FREQ: int = 10

    # Inference
    BLOCK_THRESHOLD: float = 0.8 # Confidence threshold for block detection

    # Benchmark
    RESULTS_FOLDER: str = "results"
    BENCH_DATASET_NAME: str = "vikp/pdf_bench"


settings = Settings()
