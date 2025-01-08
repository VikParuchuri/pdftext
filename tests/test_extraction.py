from pdftext.extraction import paginated_plain_text_output, plain_text_output


def test_paginated_output(pdf_path, pdf_doc):
    text = paginated_plain_text_output(pdf_path)
    assert len(text) == len(pdf_doc)
    assert "Subspace" in text[0]

def text_plain_text_output(pdf_path):
    text = plain_text_output(pdf_path)
    assert "Subspace" in text


def test_page_range(pdf_path):
