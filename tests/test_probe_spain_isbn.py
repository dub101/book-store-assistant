import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "probe_spain_isbn.py"
SPEC = importlib.util.spec_from_file_location("probe_spain_isbn", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None

probe_spain_isbn = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe_spain_isbn)


def test_spain_isbn_probe_defines_multiple_candidate_urls() -> None:
    assert len(probe_spain_isbn.SPAIN_ISBN_URL_TEMPLATES) == 4
    assert all("{isbn}" in template for template in probe_spain_isbn.SPAIN_ISBN_URL_TEMPLATES)


def test_spain_isbn_probe_includes_culturaydeporte_endpoint() -> None:
    assert any(
        "culturaydeporte.gob.es" in template
        for template in probe_spain_isbn.SPAIN_ISBN_URL_TEMPLATES
    )


def test_spain_isbn_probe_includes_legacy_mcu_endpoint() -> None:
    assert any("mcu.es" in template for template in probe_spain_isbn.SPAIN_ISBN_URL_TEMPLATES)


def test_spain_isbn_probe_default_output_dir_example() -> None:
    output_dir = Path("tmp/spain_isbn_probe") / "9780306406157"

    assert str(output_dir) == "tmp/spain_isbn_probe/9780306406157"
