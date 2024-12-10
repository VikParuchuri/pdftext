import os.path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Inference
    BLOCK_THRESHOLD: float = 0.8  # Confidence threshold for block detection
    WORKER_PAGE_THRESHOLD: int = 10  # Min number of pages per worker in parallel

    # Benchmark
    RESULTS_FOLDER: str = "results"
    BENCH_DATASET_NAME: str = "vikp/pdf_bench"


settings = Settings()
