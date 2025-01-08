import pytest
import pypdfium2 as pdfium

@pytest.fixture(scope="session")
def pdf_path():
    return "tests/data/adversarial.pdf"

@pytest.fixture()
def pdf_doc(pdf_path):
    doc = pdfium.PdfDocument(pdf_path)
    yield doc
    doc.close()
