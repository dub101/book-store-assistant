from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import quote_plus

import httpx

DEFAULT_USER_AGENT = "book-store-assistant/0.1.0 (+manual-source-probe)"
TITLE_PATTERN = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def extract_title(text: str) -> str | None:
    match = TITLE_PATTERN.search(text)
    if match is None:
        return None

    return re.sub(r"\s+", " ", match.group(1)).strip() or None


def build_output_name(url: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", url).strip("_") or "response"


def probe_isbn(
    isbn: str,
    url_templates: list[str],
    output_dir: Path,
    follow_redirects: bool,
    timeout_seconds: float,
    user_agent: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client(
        timeout=timeout_seconds,
        follow_redirects=follow_redirects,
        headers={"User-Agent": user_agent},
    ) as client:
        for template in url_templates:
            url = template.format(isbn=quote_plus(isbn))
            print(f"URL: {url}")

            try:
                response = client.get(url)
            except httpx.HTTPError as exc:
                print(f"  error: {exc}")
                print()
                continue

            content_type = response.headers.get("content-type")
            title = extract_title(response.text)
            isbn_present = isbn.casefold() in response.text.casefold()

            print(f"  status: {response.status_code}")
            print(f"  final_url: {response.url}")
            print(f"  content_type: {content_type}")
            print(f"  isbn_present: {isbn_present}")
            print(f"  title: {title}")
            print()

            output_path = output_dir / f"{build_output_name(url)}.txt"
            output_path.write_text(response.text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe candidate metadata-source lookup surfaces for a single ISBN.",
    )
    parser.add_argument("isbn", help="ISBN to probe")
    parser.add_argument(
        "--url-template",
        action="append",
        dest="url_templates",
        required=True,
        help="Lookup URL template. Use {isbn} as the ISBN placeholder.",
    )
    parser.add_argument(
        "--output-dir",
        default="tmp/source_probe",
        help="Directory where raw responses will be saved",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=20.0,
        help="HTTP timeout in seconds",
    )
    parser.add_argument(
        "--no-follow-redirects",
        action="store_true",
        help="Disable redirect following",
    )
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="HTTP User-Agent header value",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    probe_isbn(
        isbn=args.isbn,
        url_templates=args.url_templates,
        output_dir=Path(args.output_dir) / args.isbn,
        follow_redirects=not args.no_follow_redirects,
        timeout_seconds=args.timeout_seconds,
        user_agent=args.user_agent,
    )


if __name__ == "__main__":
    main()
