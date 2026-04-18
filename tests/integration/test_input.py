from pathlib import Path

from book_store_assistant.pipeline.input import read_isbn_inputs


def test_read_isbn_inputs_splits_valid_and_invalid_values(tmp_path: Path) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\ninvalid\n0306406152\n", encoding="utf-8")

    result = read_isbn_inputs(input_file)

    assert [item.isbn for item in result.valid_inputs] == [
        "9780306406157",
        "0306406152",
    ]
    assert result.invalid_values == ["invalid"]


def test_read_isbn_inputs_ignores_header_row(tmp_path: Path) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("ISBN\n9780306406157\n", encoding="utf-8")

    result = read_isbn_inputs(input_file)

    assert [item.isbn for item in result.valid_inputs] == ["9780306406157"]
    assert result.invalid_values == []


def test_read_isbn_inputs_ignores_whitespace_only_rows(tmp_path: Path) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\n   \n0306406152\n", encoding="utf-8")

    result = read_isbn_inputs(input_file)

    assert [item.isbn for item in result.valid_inputs] == [
        "9780306406157",
        "0306406152",
    ]
    assert result.invalid_values == []


def test_read_isbn_inputs_ignores_bom_prefixed_header_row(tmp_path: Path) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("\ufeffISBN\n9780306406157\n", encoding="utf-8")

    result = read_isbn_inputs(input_file)

    assert [item.isbn for item in result.valid_inputs] == ["9780306406157"]
    assert result.invalid_values == []


def test_read_isbn_inputs_ignores_isbn13_header_row(tmp_path: Path) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("ISBN13\n9780306406157\n", encoding="utf-8")

    result = read_isbn_inputs(input_file)

    assert [item.isbn for item in result.valid_inputs] == ["9780306406157"]
    assert result.invalid_values == []


def test_read_isbn_inputs_collapses_duplicates_preserving_first_occurrence(
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text(
        "9780306406157\n9788408163435\n9780306406157\n0306406152\n9788408163435\n",
        encoding="utf-8",
    )

    result = read_isbn_inputs(input_file)

    assert [item.isbn for item in result.valid_inputs] == [
        "9780306406157",
        "9788408163435",
        "0306406152",
    ]
    assert result.duplicate_count == 2
    assert result.invalid_values == []


def test_read_isbn_inputs_collapses_dashed_duplicates(tmp_path: Path) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text(
        "9780306406157\n978-0-306-40615-7\n978 0306 406157\n",
        encoding="utf-8",
    )

    result = read_isbn_inputs(input_file)

    assert [item.isbn for item in result.valid_inputs] == ["9780306406157"]
    assert result.duplicate_count == 2


def test_read_isbn_inputs_reports_zero_duplicates_when_none_present(tmp_path: Path) -> None:
    input_file = tmp_path / "isbns.csv"
    input_file.write_text("9780306406157\n9788408163435\n", encoding="utf-8")

    result = read_isbn_inputs(input_file)

    assert result.duplicate_count == 0
    assert len(result.valid_inputs) == 2


def test_read_isbn_inputs_collapses_duplicates_in_sample_9_fixture() -> None:
    sample_9 = Path("data/input/sample_9.csv")

    result = read_isbn_inputs(sample_9)

    assert len(result.valid_inputs) == 20
    assert result.duplicate_count == 5
    isbns = [item.isbn for item in result.valid_inputs]
    assert len(isbns) == len(set(isbns)), "no duplicate ISBNs should remain"
