import argparse
import json

from pdftext.inference import inference
from pdftext.model import get_model
from pdftext.pdf.extraction import get_pdfium_chars
from pdftext.postprocessing import merge_text


def main():
    parser = argparse.ArgumentParser(description="Extract plain text from PDF.  Not guaranteed to be in order.")
    parser.add_argument("pdf_path", type=str, help="Path to the PDF file")
    parser.add_argument("--out_path", type=str, help="Path to the output text file, defaults to stdout", default=None)
    parser.add_argument("--sort", action="store_true", help="Attempt to sort the text by reading order", default=False)
    args = parser.parse_args()

    model = get_model()
    text_chars = get_pdfium_chars(args.pdf_path)
    pages = inference(text_chars, model)

    text = ""
    for page in pages:
        text += merge_text(page, sort=args.sort).strip() + "\n"

    if args.out_path:
        with open(args.out_path, "w") as f:
            f.write(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
