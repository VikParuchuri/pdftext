from pdftext.extraction import paginated_plain_text_output, plain_text_output, dictionary_output
from pdftext.schema import Pages


def test_paginated_output(pdf_path, pdf_doc):
    text = paginated_plain_text_output(pdf_path)
    assert len(text) == len(pdf_doc)
    assert "Subspace" in text[0]

def text_plain_text_output(pdf_path):
    text = plain_text_output(pdf_path)
    assert "Subspace" in text

def test_page_range(pdf_path):
    pages = [0, 1, 3]
    text = paginated_plain_text_output(pdf_path, page_range=pages)
    assert len(text) == len(pages)

def test_json_output(pdf_path, pdf_doc):
    pages: Pages = dictionary_output(pdf_path)
    assert len(pages) == len(pdf_doc)
    assert "Subspace" in pages[0]["blocks"][0]["lines"][0]["spans"][0]["text"]

def test_keep_chars(pdf_path):
    pages: Pages = dictionary_output(pdf_path, keep_chars=True)
    assert "Subspace" in pages[0]["blocks"][0]["lines"][0]["spans"][0]["text"]
    assert "bbox" in pages[0]["blocks"][0]["lines"][0]["spans"][0]["chars"][0]