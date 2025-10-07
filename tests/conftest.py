import pytest
import pypdfium2 as pdfium

@pytest.fixture(scope="session")
def pdf_path():
    return "tests/data/adversarial.pdf"

@pytest.fixture(scope="session")
def pdf_path2():
    return "tests/data/communication.pdf"

@pytest.fixture(scope="session")
def pdf_with_non_unicode_chars():
    return "tests/data/non_unicode_chars.pdf"

@pytest.fixture()
def pdf_doc(pdf_path):
    doc = pdfium.PdfDocument(pdf_path)
    yield doc
    doc.close()
