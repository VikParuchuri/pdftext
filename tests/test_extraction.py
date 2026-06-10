import pytest

from pdftext.extraction import paginated_plain_text_output, plain_text_output, dictionary_output
from pdftext.schema import Pages, PdfPasswordError
from pdftext.settings import settings


def test_paginated_output(pdf_path, pdf_doc):
    text = paginated_plain_text_output(pdf_path)
    assert len(text) == len(pdf_doc)
    assert "Subspace" in text[0]

def test_plain_text_output(pdf_path):
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

def test_superscripts(pdf_path):
    pages: Pages = dictionary_output(pdf_path)
    for page in pages:
        for block in page["blocks"]:
            for line in block["lines"]:
                for span in line["spans"]:
                    if span["text"] == "∞":
                        assert span["superscript"] is True
                        return True


def test_line_joining(pdf_path2):
    pages = [11]
    text = plain_text_output(pdf_path2, page_range=pages).lower()
    assert "the axis media control viewer toolbar" in text
    assert "axismediacontrolviewertoolbar" not in text


def test_spans_have_script_flags(pdf_path):
    pages: Pages = dictionary_output(pdf_path, page_range=[0])
    for page in pages:
        for block in page["blocks"]:
            for line in block["lines"]:
                for span in line["spans"]:
                    assert isinstance(span["superscript"], bool)
                    assert isinstance(span["subscript"], bool)


def test_links_and_refs(pdf_path):
    pages: Pages = dictionary_output(pdf_path)
    assert all("refs" in page for page in pages)
    linked_spans = [
        span
        for page in pages
        for block in page["blocks"]
        for line in block["lines"]
        for span in line["spans"]
        if span["url"]
    ]
    assert linked_spans
    # link reconstruction must preserve the script flags
    for span in linked_spans:
        assert "superscript" in span
        assert "subscript" in span


def test_rotated_page(rotated_pdf_path):
    pages: Pages = dictionary_output(rotated_pdf_path, page_range=[0])
    assert pages[0]["rotation"] == 90
    text = plain_text_output(rotated_pdf_path, page_range=[0])
    assert "Subspace" in text


def test_empty_page(empty_pdf_path):
    pages: Pages = dictionary_output(empty_pdf_path)
    assert len(pages) == 1
    assert pages[0]["blocks"] == []


def test_encrypted_requires_password(encrypted_pdf_path):
    with pytest.raises(PdfPasswordError):
        plain_text_output(encrypted_pdf_path)


def test_encrypted_wrong_password(encrypted_pdf_path):
    with pytest.raises(PdfPasswordError):
        plain_text_output(encrypted_pdf_path, password="wrong")


def test_encrypted_with_password(encrypted_pdf_path):
    text = paginated_plain_text_output(encrypted_pdf_path, password="user")
    assert len(text) == 12
    assert "secret text on page 0" in text[0]


def test_encrypted_with_workers(encrypted_pdf_path, monkeypatch):
    monkeypatch.setattr(settings, "WORKER_PAGE_THRESHOLD", 1)
    text = paginated_plain_text_output(encrypted_pdf_path, password="user", workers=2)
    assert len(text) == 12
    assert "secret text on page 11" in text[11]


def test_page_range_out_of_bounds(pdf_path):
    with pytest.raises(ValueError):
        dictionary_output(pdf_path, page_range=[999])
    with pytest.raises(ValueError):
        dictionary_output(pdf_path, page_range=[-1])


def test_workers_match_serial(pdf_path, monkeypatch):
    monkeypatch.setattr(settings, "WORKER_PAGE_THRESHOLD", 1)
    serial = paginated_plain_text_output(pdf_path)
    parallel = paginated_plain_text_output(pdf_path, workers=2)
    assert serial == parallel


def test_flatten_pdf_repeated(pdf_path):
    for _ in range(3):
        pages = dictionary_output(pdf_path, page_range=[0], flatten_pdf=True)
        assert pages
