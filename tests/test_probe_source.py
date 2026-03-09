import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "probe_source.py"
SPEC = importlib.util.spec_from_file_location("probe_source", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None

probe_source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe_source)


def test_extract_title_returns_none_when_title_tag_is_missing() -> None:
    assert probe_source.extract_title("<html><body>No title here</body></html>") is None


def test_extract_title_normalizes_whitespace() -> None:
    html = "<html><head><title>  Example \n Title  </title></head></html>"

    assert probe_source.extract_title(html) == "Example Title"


def test_build_output_name_sanitizes_url() -> None:
    url = "https://example.com/search?q=isbn:9780306406157"

    assert probe_source.build_output_name(url) == "https_example_com_search_q_isbn_9780306406157"


def test_build_output_name_falls_back_for_empty_value() -> None:
    assert probe_source.build_output_name("///") == "response"


def test_probe_output_directory_example_path() -> None:
    output_dir = Path("tmp/source_probe") / "9780306406157"

    assert str(output_dir) == "tmp/source_probe/9780306406157"
