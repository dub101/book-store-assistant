from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from probe_source import probe_isbn

SPAIN_ISBN_URL_TEMPLATES = [
    "https://www.culturaydeporte.gob.es/webISBN/tituloSimpleFilter.do?cache=init&prev_layout=busquedaisbn&layout=busquedaisbn&language=es&isbn={isbn}",
    "https://www.culturaydeporte.gob.es/webISBN/consultaSimpleFilter.do?cache=init&prev_layout=busquedaisbn&layout=busquedaisbn&language=es&isbn={isbn}",
    "https://www.mcu.es/webISBN/tituloSimpleFilter.do?cache=init&prev_layout=busquedaisbn&layout=busquedaisbn&language=es&isbn={isbn}",
    "https://www.mcu.es/webISBN/consultaSimpleFilter.do?cache=init&prev_layout=busquedaisbn&layout=busquedaisbn&language=es&isbn={isbn}",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe Spain ISBN / Ministry of Culture lookup surfaces for a single ISBN.",
    )
    parser.add_argument("isbn", help="ISBN to probe")
    parser.add_argument(
        "--output-dir",
        default="tmp/spain_isbn_probe",
        help="Directory where raw responses will be saved",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    probe_isbn(
        isbn=args.isbn,
        url_templates=SPAIN_ISBN_URL_TEMPLATES,
        output_dir=Path(args.output_dir) / args.isbn,
        follow_redirects=True,
        timeout_seconds=20.0,
        user_agent="book-store-assistant/0.1.0 (+manual-spain-isbn-probe)",
    )


if __name__ == "__main__":
    main()
