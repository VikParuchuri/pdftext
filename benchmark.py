import argparse
import tempfile
import time
from collections import defaultdict
from functools import partial
from statistics import mean
import os
import json

import fitz as pymupdf
import datasets
import pdfplumber
from rapidfuzz import fuzz
import tabulate
from tqdm import tqdm
import pypdfium2 as pdfium

from pdftext.extraction import paginated_plain_text_output
from pdftext.model import get_model
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
                text = text.rstrip() + "\n"
            text = text.rstrip() + "\n\n"
        pages.append(text)
    return pages


def pdfplumber_inference(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        pages = []
        for i in range(len(pdf.pages)):
            page = pdf.pages[i]
            lines = page.extract_text_lines(strip=False, return_chars=True, keep_text_flow=True)
            text = ""
            for line in lines:
                text += line["text"].rstrip() + "\n"
            pages.append(text)
    return pages


def pdftext_inference(pdf_path, workers=None):
    return paginated_plain_text_output(pdf_path, workers=workers)


def compare_docs(doc1: str, doc2: str):
    return fuzz.ratio(doc1, doc2)


def main():
    parser = argparse.ArgumentParser(description="Benchmark pdf extraction.")
    parser.add_argument("--result_path", type=str, help="Path to the output text file, defaults to stdout", default=None)
    parser.add_argument("--max", type=int, help="Maximum number of pages to process.", default=None)
    parser.add_argument("--pdftext_only", action="store_true", help="Only run pdftext inference", default=False)
    parser.add_argument("--pdftext_workers", type=int, help="Number of workers to use for pdftext inference", default=None)
    args = parser.parse_args()

    split = "train"
    if args.max:
        split = f"train[:{args.max}]"
    dataset = datasets.load_dataset(settings.BENCH_DATASET_NAME, split=split)

    times = defaultdict(list)
    alignments = defaultdict(list)
    times_tools = ["pymupdf", "pdftext", "pdfplumber"]
    alignment_tools = ["pdftext", "pdfplumber"]
    if args.pdftext_only:
        times_tools = ["pymupdf", "pdftext"]
        alignment_tools = ["pdftext"]
    for i in tqdm(range(len(dataset)), desc="Benchmarking"):
        row = dataset[i]
        pdf = row["pdf"]
        tool_pages = {}
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(pdf)
            f.seek(0)
            pdf_path = f.name

            pdftext_inference_model = partial(pdftext_inference, workers=args.pdftext_workers)
            inference_funcs = [pymupdf_inference, pdftext_inference_model, pdfplumber_inference]
            for tool, inference_func in zip(times_tools, inference_funcs):
                start = time.time()
                pages = inference_func(pdf_path)
                times[tool].append(time.time() - start)
                tool_pages[tool] = pages

            for tool in alignment_tools:
                alignments[tool].append(
                    mean([compare_docs(tool_pages["pymupdf"][i], tool_pages[tool][i]) for i in range(len(tool_pages["pymupdf"]))])
                )

    print("Benchmark Scores")
    headers = ["Library", "Time (s per page)", "Alignment Score (% accuracy vs pymupdf)"]
    table_times = [round(mean(times[tool]), 2) for tool in times_tools]
    table_alignments = [round(mean(alignments[tool]), 2) for tool in alignment_tools]
    table_alignments.insert(0, "--")

    table = [(tool, time, alignment) for tool, time, alignment in zip(times_tools, table_times, table_alignments)]
    table = tabulate.tabulate(table, tablefmt="github", headers=headers)
    print(table)

    results = {
        "times": times,
        "alignments": alignments
    }

    result_path = args.result_path
    if result_path is None:
        result_path = settings.RESULTS_FOLDER

    os.makedirs(result_path, exist_ok=True)

    with open(os.path.join(result_path, "results.json"), "w+") as f:
        json.dump(results, f)


if __name__ == "__main__":
    main()
