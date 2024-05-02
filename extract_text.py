import argparse
import json
import pypdfium2 as pdfium

from pdftext.extraction import plain_text_output, dictionary_output


def main():
    parser = argparse.ArgumentParser(description="Extract plain text from PDF.  Not guaranteed to be in order.")
    parser.add_argument("pdf_path", type=str, help="Path to the PDF file")
    parser.add_argument("--out_path", type=str, help="Path to the output text file, defaults to stdout", default=None)
    parser.add_argument("--json", action="store_true", help="Output json instead of plain text", default=False)
    parser.add_argument("--sort", action="store_true", help="Attempt to sort the text by reading order", default=False)
    parser.add_argument("--keep_hyphens", action="store_true", help="Keep hyphens in words", default=False)
    parser.add_argument("--pages", type=str, help="Comma separated pages to extract, like 1,2,3", default=None)
    parser.add_argument("--keep_chars", action="store_true", help="Keep character level information", default=False)
    args = parser.parse_args()

    pdf_doc = pdfium.PdfDocument(args.pdf_path)
    pages = None
    if args.pages is not None:
        pages = [int(p) for p in args.pages.split(",")]
        assert all(p <= len(pdf_doc) for p in pages), "Invalid page number(s) provided"

    if args.json:
        text = dictionary_output(pdf_doc, sort=args.sort, page_range=pages, keep_chars=args.keep_chars)
        text = json.dumps(text)
    else:
        text = plain_text_output(pdf_doc, sort=args.sort, hyphens=args.keep_hyphens, page_range=pages)

    if args.out_path is None:
        print(text)
    else:
        with open(args.out_path, "w+") as f:
            f.write(text)


if __name__ == "__main__":
    main()
