import pytest

from pdftext.extraction import table_output

def test_table_input_mismatch(pdf_path):
    with pytest.raises(ValueError):
        table_output(pdf_path, [], page_range=[5])

def test_table_pages_without_chars(pdf_path):
    from pdftext.extraction import dictionary_output
    pages = dictionary_output(pdf_path, page_range=[5], keep_chars=False)
    with pytest.raises(ValueError, match="keep_chars"):
        table_output(pdf_path, [{"tables": [[0, 0, 100, 100]], "img_size": [612, 792]}], pages=pages)

def test_table_cells_consistent_across_rotations(tmp_path):
    import fitz
    from pdftext.extraction import dictionary_output

    counts = {}
    for rot in (0, 90, 180, 270):
        doc = fitz.open()
        page = doc.new_page()
        for i in range(8):
            page.insert_text((72, 100 + i * 22), f"alpha beta    gamma delta   row{i} end")
        page.set_rotation(rot)
        path = tmp_path / f"table_rot{rot}.pdf"
        doc.save(str(path))
        doc.close()

        pages = dictionary_output(str(path), keep_chars=True)
        w, h = pages[0]["width"], pages[0]["height"]
        tables = table_output(str(path), [{"tables": [[0, 0, w, h]], "img_size": [w, h]}], pages=pages)
        cells = [c["text"] for c in tables[0][0]]
        assert not any("\r" in c or "\n" in c for c in cells), f"control chars in cells at rot={rot}"
        counts[rot] = len(cells)
    assert len(set(counts.values())) == 1, f"cell counts differ across rotations: {counts}"

def test_table_extraction(pdf_path, pdf_doc):
    _table_extraction(pdf_path, pdf_doc)

def test_table_extraction_small(pdf_path, pdf_doc):
    _table_extraction(pdf_path, pdf_doc, img_size_scaler=0.5)

def _table_extraction(pdf_path, pdf_doc, img_size_scaler: float = 2.0):
    pages = [5]
    page_size = pdf_doc[5].get_size()
    img_size = [p * img_size_scaler for p in page_size]

    # Rescale to img size
    def rescale_table(bbox):
        return [
            bbox[0] * img_size[0],
            bbox[1] * img_size[1],
            bbox[2] * img_size[0],
            bbox[3] * img_size[1]
        ]

    table_inputs = [
        {
            "tables": [
                rescale_table([0.0925, 0.116, 0.871, 0.324]),
                rescale_table([0.171, 0.365, 0.794, 0.492])
            ],
            "img_size": img_size
        }
    ]
    tables = table_output(pdf_path, table_inputs, page_range=pages)
    assert len(tables) == 1
    assert len(tables[0]) == 2
    assert len(tables[0][0]) == 127
    assert len(tables[0][1]) == 74
    assert tables[0][0][-1]["text"].strip() == "58.45"
    assert tables[0][1][-1]["text"].strip() == "7.0h"

    table1_bbox = table_inputs[0]["tables"][0]
    table1_width = table1_bbox[2] - table1_bbox[0]
    table1_height = table1_bbox[3] - table1_bbox[1]

    # Ensure bboxes are within table bounds (they should be rescaled)
    for cell in tables[0][0]:
        assert 0 <= cell["bbox"][0] <= table1_width
        assert 0 <= cell["bbox"][1] <= table1_height
        assert 0 <= cell["bbox"][2] <= table1_width
        assert 0 <= cell["bbox"][3] <= table1_height

