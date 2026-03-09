from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROBE_SOURCE_PATH = SCRIPT_DIR / "probe_source.py"
PROBE_SOURCE_SPEC = importlib.util.spec_from_file_location("probe_source", PROBE_SOURCE_PATH)
assert PROBE_SOURCE_SPEC is not None
assert PROBE_SOURCE_SPEC.loader is not None

probe_source = importlib.util.module_from_spec(PROBE_SOURCE_SPEC)
PROBE_SOURCE_SPEC.loader.exec_module(probe_source)
probe_isbn = probe_source.probe_isbn

BNE_URL_TEMPLATES = [
    "https://datos.bne.es/resource/?query={isbn}",
    "https://www.bne.es/es/catalogos/biblioteca-digital-hispanica/inicio/index.html?query={isbn}",
    "https://catalogo.bne.es/uhtbin/cgisirsi/?searchdata1={isbn}&srchfield1=GENERAL%5ESUBJECT%5EGENERAL%5ETodos+los+campos&searchoper1=&thesaurus=GENERAL&search_type=Keyword&user_id=WEBSERVER",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe Biblioteca Nacional de Espana lookup surfaces for a single ISBN.",
    )
    parser.add_argument("isbn", help="ISBN to probe")
    parser.add_argument(
        "--output-dir",
        default="tmp/bne_probe",
        help="Directory where raw responses will be saved",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    probe_isbn(
        isbn=args.isbn,
        url_templates=BNE_URL_TEMPLATES,
        output_dir=Path(args.output_dir) / args.isbn,
        follow_redirects=True,
        timeout_seconds=20.0,
        user_agent="book-store-assistant/0.1.0 (+manual-bne-probe)",
    )


if __name__ == "__main__":
    main()
