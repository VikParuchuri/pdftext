import argparse
import tempfile
import time
from statistics import mean
import os
import json

import fitz as pymupdf
import datasets

from pdftext.extraction import dictionary_output
from pdftext.settings import settings


def pymupdf_inference(pdf_path):
    doc = pymupdf.open(pdf_path)
    pages = []
    for i in range(len(doc)):
        page = doc[i]
        text = page.get_text("dict")
        pages.append(text)
    return pages


def main():
    parser = argparse.ArgumentParser(description="Benchmark pdf extraction.")
    parser.add_argument("--result_path", type=str, help="Path to the output text file, defaults to stdout", default=None)
    parser.add_argument("--max", type=int, help="Maximum number of pages to process.", default=None)
    args = parser.parse_args()

    split = "train"
    if args.max:
        split = f"train[:{args.max}]"
    dataset = datasets.load_dataset(settings.BENCH_DATASET_NAME, split=split)

    mu_times = []
    pdftext_times = []
    for i in range(len(dataset)):
        row = dataset[i]
        pdf = row["pdf"]
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(pdf)
            f.seek(0)
            pdf_path = f.name

            start = time.time()
            mu_pages = pymupdf_inference(pdf_path)
            mu_times.append(time.time() - start)


            start = time.time()
            pdftext_pages = dictionary_output(pdf_path)
            pdftext_times.append(time.time() - start)

    print(f"MuPDF avg time: {mean(mu_times):.2f}")
    print(f"pdftext avg time: {mean(pdftext_times):.2f}")

    results = {
        "mu_times": mu_times,
        "pdftext_times": pdftext_times
    }

    result_path = args.result_path
    if result_path is None:
        result_path = settings.RESULTS_FOLDER

    os.makedirs(result_path, exist_ok=True)

    with open(os.path.join(result_path, "results.json"), "w+") as f:
        json.dump(results, f)


if __name__ == "__main__":
    main()
