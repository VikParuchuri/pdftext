import argparse
import tempfile
import time
from statistics import mean
import os
import json
import re

import fitz as pymupdf
import datasets
import pdfplumber
from rapidfuzz import fuzz
import tabulate

from pdftext.extraction import paginated_plain_text_output
from pdftext.settings import settings


def pymupdf_inference(pdf_path):
    doc = pymupdf.open(pdf_path)
    pages = []
    for i in range(len(doc)):
        page = doc[i]
        blocks = page.get_text("dict", flags=pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_LIGATURES & ~pymupdf.TEXT_PRESERVE_IMAGES)
        text = ""
        for block in blocks["blocks"]:
            for line in block["lines"]:
                for span in line["spans"]:
                    text += span["text"]
            if not text.endswith("\n"):
                text += "\n\n"
        pages.append(text)
    return pages


def pdfplumber_inference(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        pages = []
        for i in range(len(pdf.pages)):
            page = pdf.pages[i]
            text = page.extract_text()
            pages.append(text)
    return pages


def flatten_text(page: str):
    # Replace all text, except newlines, so we can compare block parsing effectively.
    return re.sub(r'[ \t\r\f\v]+', '', page)


def compare_docs(doc1: str, doc2: str):
    return fuzz.ratio(flatten_text(doc1), flatten_text(doc2))


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
    pdfplumber_times = []
    pdftext_alignment = []
    pdfplumber_alignment = []
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
            pdftext_pages = paginated_plain_text_output(pdf_path)
            pdftext_times.append(time.time() - start)

            start = time.time()
            pdfplumber_pages = pdfplumber_inference(pdf_path)
            pdfplumber_times.append(time.time() - start)

            alignments = [compare_docs(mu_page, pdftext_page) for mu_page, pdftext_page in zip(mu_pages, pdftext_pages)]
            pdftext_alignment.append(mean(alignments))

            alignments = [compare_docs(mu_page, pdfplumber_page) for mu_page, pdfplumber_page in zip(mu_pages, pdfplumber_pages)]
            pdfplumber_alignment.append(mean(alignments))

    print("Benchmark Scores")
    headers = ["Library", "Time (s per page)", "Alignment Score (% accuracy vs pymupdf)"]
    table = [
        ["pymupdf", round(mean(mu_times), 2), "--"],
        ["pdftext", round(mean(pdftext_times), 2), round(mean(pdftext_alignment), 2)],
        ["pdfplumber", round(mean(pdfplumber_times), 2), round(mean(pdfplumber_alignment), 2)]
    ]
    table = tabulate.tabulate(table, tablefmt="pretty", headers=headers)
    print(table)

    results = {
        "times": {
            "pymupdf": mean(mu_times),
            "pdftext": mean(pdftext_times),
            "pdfplumber": mean(pdfplumber_times)
        },
        "alignments": {
            "pdftext": pdftext_alignment,
            "pdfplumber": pdfplumber_alignment
        }
    }

    result_path = args.result_path
    if result_path is None:
        result_path = settings.RESULTS_FOLDER

    os.makedirs(result_path, exist_ok=True)

    with open(os.path.join(result_path, "results.json"), "w+") as f:
        json.dump(results, f)


if __name__ == "__main__":
    main()
