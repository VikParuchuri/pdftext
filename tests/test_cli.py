import json

from click.testing import CliRunner

from pdftext.scripts.extract_text import extract_text_cli


def test_cli_plain_text(pdf_path, tmp_path):
    out_path = tmp_path / "out.txt"
    result = CliRunner().invoke(extract_text_cli, [pdf_path, "--out_path", str(out_path)])
    assert result.exit_code == 0
    assert "Subspace" in out_path.read_text(encoding="utf-8")


def test_cli_json(pdf_path, tmp_path):
    out_path = tmp_path / "out.json"
    result = CliRunner().invoke(extract_text_cli, [pdf_path, "--json", "--page_range", "0", "--out_path", str(out_path)])
    assert result.exit_code == 0
    pages = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(pages) == 1


def test_cli_stdout_non_ascii(tmp_path):
    import os
    import subprocess
    import sys

    import fitz

    doc = fitz.open()
    # insert_htmlbox does font fallback so the Cyrillic actually renders
    doc.new_page().insert_htmlbox(fitz.Rect(40, 40, 550, 200), "<p>Кириллица ∑ ϵ test</p>")
    path = tmp_path / "nonascii.pdf"
    doc.save(str(path))
    doc.close()

    # Force a non-UTF-8 stdout encoding to emulate a Windows cp1252 console;
    # the CLI must emit UTF-8 bytes rather than crashing on non-encodable text
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    result = subprocess.run(
        [sys.executable, "-c",
         "from pdftext.scripts.extract_text import extract_text_cli; extract_text_cli()",
         str(path)],
        capture_output=True, env=env,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    assert "Кириллица".encode("utf-8") in result.stdout


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
    assert "secret text" in out_path.read_text(encoding="utf-8")
