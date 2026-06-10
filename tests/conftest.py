import pytest
import pypdfium2 as pdfium

@pytest.fixture(scope="session")
def pdf_path():
    return "tests/data/adversarial.pdf"

@pytest.fixture(scope="session")
def pdf_path2():
    return "tests/data/communication.pdf"

@pytest.fixture()
def pdf_doc(pdf_path):
    doc = pdfium.PdfDocument(pdf_path)
    yield doc
    doc.close()

@pytest.fixture(scope="session")
def rotated_pdf_path(pdf_path, tmp_path_factory):
    import fitz

    path = tmp_path_factory.mktemp("fixtures") / "rotated.pdf"
    doc = fitz.open(pdf_path)
    for page in doc:
        page.set_rotation(90)
    doc.save(str(path))
    doc.close()
    return str(path)

@pytest.fixture(scope="session")
def encrypted_pdf_path(tmp_path_factory):
    import fitz

    path = tmp_path_factory.mktemp("fixtures") / "encrypted.pdf"
    doc = fitz.open()
    for i in range(12):
        page = doc.new_page()
        page.insert_text((72, 72), f"secret text on page {i}")
    doc.save(str(path), owner_pw="owner", user_pw="user", encryption=fitz.PDF_ENCRYPT_AES_256)
    doc.close()
    return str(path)

@pytest.fixture(scope="session")
def empty_pdf_path(tmp_path_factory):
    import fitz

    path = tmp_path_factory.mktemp("fixtures") / "empty.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(path))
    doc.close()
    return str(path)
