from pathlib import Path

from book_store_assistant.pipeline.input import read_isbn_inputs


def test_read_isbn_inputs_splits_valid_and_invalid_values(tmp_path: Path) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\ninvalid\n0-306-40615-2\n", encoding="utf-8")

    result = read_isbn_inputs(input_file)

    assert [item.isbn for item in result.valid_inputs] == ["9780306406157", "0306406152"]
    assert result.invalid_values == ["invalid"]
