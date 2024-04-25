import argparse
import json

from pdftext.extraction import plain_text_output, dictionary_output


def main():
    parser = argparse.ArgumentParser(description="Extract plain text from PDF.  Not guaranteed to be in order.")
    parser.add_argument("pdf_path", type=str, help="Path to the PDF file")
    parser.add_argument("--out_path", type=str, help="Path to the output text file, defaults to stdout", default=None)
    parser.add_argument("--output_type", type=str, help="Type of output to generate", default="plain_text")
    parser.add_argument("--sort", action="store_true", help="Attempt to sort the text by reading order", default=False)
    args = parser.parse_args()

    assert args.output_type in ["plain_text", "json"], "Invalid output type, must be 'plain_text' or 'json'"

    if args.output_type == "plain_text":
        text = plain_text_output(args.pdf_path, sort=args.sort)
    elif args.output_type == "json":
        text = dictionary_output(args.pdf_path, sort=args.sort)
        text = json.dumps(text)

    if args.out_path is None:
        print(text)
    else:
        with open(args.out_path, "w+") as f:
            f.write(text)


if __name__ == "__main__":
    main()
