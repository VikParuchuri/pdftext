import pytest

from pdftext.pdf.chars import utf8_int_to_string

@pytest.mark.unit
@pytest.mark.parametrize(
    "utf8_int, expected_str",
    [
        (65, "A"),  # uppercase letter
        (97, "a"),  # lowercase letter
        (51, "3"),  # number
        (64, "@"),  # special character
        # 3-byte UTF-8
        (15112101, "日"),  # japanese char for day
        (14989485, "中"),  # chinese char for middle
        (15111815, "文"),  # chinese char for text/writing
        (15113388, "本"),  # chinese char for book/origin
        (15570332, "한"),  # korean hangul syllable
        (14990232, "付"),  # japanese char for "attach/give" (part of date 日付)
        # 4-byte UTF-8
        (4036991104, "😀"),  # 😀
        (4036991616, "🚀"),  # 🚀
        (4036859279, "𝕏"),  # 𝕏, mathmetical notation
        (4037057678, "𠜎"),  # 𠜎, CJK ideograph
    ],
)
def test_utf8_int_to_string(utf8_int: int, expected_str: str) -> None:
    assert utf8_int_to_string(utf8_int) == expected_str