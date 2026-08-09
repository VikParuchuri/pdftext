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


def test_refs_present_with_disable_links(pdf_path):
    pages: Pages = dictionary_output(pdf_path, page_range=[0], disable_links=True)
    assert pages[0]["refs"] == []


def test_rotated_page_bbox_not_inverted(rotated_pdf_path):
    pages: Pages = dictionary_output(rotated_pdf_path, page_range=[0])
    bbox = pages[0]["bbox"]
    assert bbox[0] <= bbox[2] and bbox[1] <= bbox[3], f"inverted page bbox {bbox}"
    assert round(bbox[2] - bbox[0]) == pages[0]["width"]
    assert round(bbox[3] - bbox[1]) == pages[0]["height"]


def test_surrogate_unicode_sanitized(surrogate_pdf_path):
    import json

    pages: Pages = dictionary_output(surrogate_pdf_path, keep_chars=True)
    json.dumps(pages, ensure_ascii=False).encode("utf-8")  # must not raise
    chars = [
        c["char"]
        for b in pages[0]["blocks"]
        for l in b["lines"]
        for s in l["spans"]
        for c in s["chars"]
    ]
    assert "�" in chars and "B" in chars


def test_cjk_text(tmp_path):
    import fitz

    samples = {
        "chinese": ("china-s", "人工智能正在改变世界这是测试"),
        "japanese": ("japan", "人工知能は世界を変えていますこれはテスト"),
        "korea": ("korea", "인공지능이세상을바꾸고있습니다"),
    }
    for name, (font, text) in samples.items():
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 100), text, fontname=font)
        path = tmp_path / f"{name}.pdf"
        doc.save(str(path))
        doc.close()
        extracted = plain_text_output(str(path))
        assert text in extracted.replace(" ", ""), f"{name}: {extracted!r}"


def test_cyrillic_greek_vietnamese(tmp_path):
    import fitz

    text = "Тест Δοκιμή thử nghiệm"
    doc = fitz.open()
    page = doc.new_page()
    rc = page.insert_htmlbox(fitz.Rect(50, 50, 550, 200), f"<p>{text}</p>")
    path = tmp_path / "multi.pdf"
    doc.save(str(path))
    doc.close()
    extracted = plain_text_output(str(path))
    for word in ("Тест", "Δοκιμή", "nghiệm"):
        assert word in extracted, f"missing {word!r} in {extracted!r}"


def test_perpendicular_text_separate_lines(tmp_path):
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 400), "horizontal body text")
    page.insert_text((60, 400), "vertical label", rotate=90)
    path = tmp_path / "perp.pdf"
    doc.save(str(path))
    doc.close()

    pages: Pages = dictionary_output(str(path))
    for block in pages[0]["blocks"]:
        for line in block["lines"]:
            texts = {span["text"].strip() for span in line["spans"] if span["text"].strip()}
            assert not ({"horizontal body text", "vertical label"} <= texts), \
                "perpendicular text merged into one line"


def test_link_spans_whole_anchor(tmp_path):
    import fitz

    url = "https://example.com/anchor"
    doc = fitz.open()
    page = doc.new_page(width=400, height=140)
    size, baseline, left = 18, 60, 40
    first, second = "Claude ", "Sonnet"
    first_width = fitz.get_text_length(first, fontname="helv", fontsize=size)
    second_width = fitz.get_text_length(second, fontname="hebo", fontsize=size)
    # One link annotation over two runs that pdftext splits into separate spans
    page.insert_text((left, baseline), first, fontname="helv", fontsize=size)
    page.insert_text((left + first_width, baseline), second, fontname="hebo", fontsize=size)
    page.insert_link({
        "kind": fitz.LINK_URI,
        "uri": url,
        "from": fitz.Rect(left, baseline - size, left + first_width + second_width, baseline + 4),
    })
    # An unlinked line right below, so a link bleeding into its neighbour is caught
    page.insert_text((left, baseline + 40), "unlinked tail", fontname="helv", fontsize=size)
    path = tmp_path / "multi_span_link.pdf"
    doc.save(str(path))
    doc.close()

    pages: Pages = dictionary_output(str(path))
    spans = [
        span
        for page in pages
        for block in page["blocks"]
        for line in block["lines"]
        for span in line["spans"]
    ]
    linked = "".join(span["text"] for span in spans if span["url"] == url)
    assert linked.strip() == "Claude Sonnet"
    assert all(not span["url"] for span in spans if "unlinked" in span["text"])
