from pdftext.postprocessing import handle_hyphens, postprocess_text


def test_handle_hyphens_keeps_last_char():
    assert handle_hyphens("abc", keep_hyphens=False) == "abc"


def test_handle_hyphens_joins_words():
    # hyphen char followed by a line break joins the word; the next space
    # restores the line break
    assert handle_hyphens("exam\x02\nple next", keep_hyphens=False) == "example\nnext"


def test_handle_hyphens_keep():
    assert handle_hyphens("exam\x02ple", keep_hyphens=True) == "exam-\nple"


def test_postprocess_text_ligatures():
    assert postprocess_text("eﬃcient") == "efficient"


def test_postprocess_text_special_chars():
    assert postprocess_text("a\xa0b\r\nc") == "a b\nc"


def test_postprocess_text_control_chars():
    assert postprocess_text("a\x00b\x02c\nd") == "ab\x02c\nd"
