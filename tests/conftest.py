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
def surrogate_pdf_path(tmp_path_factory):
    # Minimal PDF whose ToUnicode CMap maps 'A' to a lone surrogate (U+D800)
    pdf = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj
4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica /ToUnicode 6 0 R >> endobj
5 0 obj << /Length 44 >> stream
BT /F1 24 Tf 72 700 Td (AB) Tj ET
endstream
endobj
6 0 obj << /Length 196 >> stream
/CIDInit /ProcSet findresource begin 12 dict begin begincmap
1 begincodespacerange <00> <FF> endcodespacerange
1 beginbfchar <41> <D800> endbfchar
endcmap CMapName currentdict /CMap defineresource pop end end
endstream
endobj
trailer << /Root 1 0 R >>"""
    path = tmp_path_factory.mktemp("fixtures") / "surrogate.pdf"
    path.write_bytes(pdf)
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
