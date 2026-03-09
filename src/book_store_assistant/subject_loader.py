from pathlib import Path


def load_subject_rows(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = [part.strip() for part in line.split("|")]
        values = [part for part in parts if part]
        if values:
            rows.append(values)

    return rows


def load_subjects(path: Path) -> list[str]:
    return [row[0] for row in load_subject_rows(path)]
