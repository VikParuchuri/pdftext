from pdftext.extraction import table_output


def test_table_extraction(pdf_path, pdf_doc):
    pages = [5]
    page_size = pdf_doc[5].get_size()
    img_size = [p * 2 for p in page_size]

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
