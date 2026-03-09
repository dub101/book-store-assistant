import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "probe_bne.py"
SPEC = importlib.util.spec_from_file_location("probe_bne", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None

probe_bne = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe_bne)


def test_bne_probe_defines_multiple_candidate_urls() -> None:
    assert len(probe_bne.BNE_URL_TEMPLATES) == 3
    assert all("{isbn}" in template for template in probe_bne.BNE_URL_TEMPLATES)


def test_bne_probe_includes_datos_bne_endpoint() -> None:
    assert any("datos.bne.es" in template for template in probe_bne.BNE_URL_TEMPLATES)


def test_bne_probe_includes_catalogo_bne_endpoint() -> None:
    assert any("catalogo.bne.es" in template for template in probe_bne.BNE_URL_TEMPLATES)


def test_bne_probe_default_output_dir_example() -> None:
    output_dir = Path("tmp/bne_probe") / "9780306406157"

    assert str(output_dir) == "tmp/bne_probe/9780306406157"
