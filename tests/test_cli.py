import json

from click.testing import CliRunner

from pdftext.scripts.extract_text import extract_text_cli


def test_cli_plain_text(pdf_path, tmp_path):
    out_path = tmp_path / "out.txt"
    result = CliRunner().invoke(extract_text_cli, [pdf_path, "--out_path", str(out_path)])
    assert result.exit_code == 0
    assert "Subspace" in out_path.read_text()


def test_cli_json(pdf_path, tmp_path):
    out_path = tmp_path / "out.json"
    result = CliRunner().invoke(extract_text_cli, [pdf_path, "--json", "--page_range", "0", "--out_path", str(out_path)])
    assert result.exit_code == 0
    pages = json.loads(out_path.read_text())
    assert len(pages) == 1


def test_cli_page_range(pdf_path):
    result = CliRunner().invoke(extract_text_cli, [pdf_path, "--page_range", "0,2-3"])
    assert result.exit_code == 0


def test_cli_page_range_out_of_bounds(pdf_path, pdf_doc):
    doc_len = len(pdf_doc)
    result = CliRunner().invoke(extract_text_cli, [pdf_path, "--page_range", str(doc_len)])
    assert result.exit_code != 0
    assert "out of range" in result.output


def test_cli_page_range_inverted(pdf_path):
    result = CliRunner().invoke(extract_text_cli, [pdf_path, "--page_range", "5-2"])
    assert result.exit_code != 0


def test_cli_page_range_not_numeric(pdf_path):
    result = CliRunner().invoke(extract_text_cli, [pdf_path, "--page_range", "abc"])
    assert result.exit_code != 0


def test_cli_password(encrypted_pdf_path, tmp_path):
    out_path = tmp_path / "out.txt"
    result = CliRunner().invoke(extract_text_cli, [encrypted_pdf_path, "--password", "user", "--out_path", str(out_path)])
    assert result.exit_code == 0
    assert "secret text" in out_path.read_text()
