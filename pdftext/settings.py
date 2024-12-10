import os.path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Inference
    WORKER_PAGE_THRESHOLD: int = 10  # Min number of pages per worker in parallel

    # Benchmark
    RESULTS_FOLDER: str = "results"
    BENCH_DATASET_NAME: str = "vikp/pdf_bench"


settings = Settings()
