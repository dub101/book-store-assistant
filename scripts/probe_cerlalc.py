from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import quote_plus

import httpx

USER_AGENT = "book-store-assistant/0.1.0 (+manual-cerlalc-probe)"

CANDIDATE_URLS = (
    "https://cerlalc.org/?s={isbn}",
    "https://cerlalc.org/?s={isbn}&lang=es",
    "https://cerlalc.org/pt-br/?s={isbn}",
    "https://cerlalc.org/catalogo-historico-de-titulos-con-isbn-de-america-latina/",
)

TITLE_PATTERN = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def extract_title(html: str) -> str | None:
    match = TITLE_PATTERN.search(html)
    if match is None:
        return None

    return re.sub(r"\s+", " ", match.group(1)).strip() or None


def probe_isbn(isbn: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client(
        timeout=20.0,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for template in CANDIDATE_URLS:
            url = template.format(isbn=quote_plus(isbn))
            print(f"URL: {url}")

            try:
                response = client.get(url)
            except httpx.HTTPError as exc:
                print(f"  error: {exc}")
                print()
                continue

            title = extract_title(response.text)
            isbn_present = isbn.casefold() in response.text.casefold()

            print(f"  status: {response.status_code}")
            print(f"  final_url: {response.url}")
            print(f"  content_type: {response.headers.get('content-type')}")
            print(f"  isbn_present: {isbn_present}")
            print(f"  title: {title}")
            print()

            safe_name = re.sub(r"[^a-zA-Z0-9]+", "_", url).strip("_")
            output_path = output_dir / f"{safe_name}.html"
            output_path.write_text(response.text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe candidate Cerlalc lookup surfaces for a single ISBN.",
    )
    parser.add_argument("isbn", help="ISBN to probe")
    parser.add_argument(
        "--output-dir",
        default="tmp/cerlalc_probe",
        help="Directory where raw HTML responses will be saved",
    )
    args = parser.parse_args()

    probe_isbn(args.isbn, Path(args.output_dir) / args.isbn)


if __name__ == "__main__":
    main()
