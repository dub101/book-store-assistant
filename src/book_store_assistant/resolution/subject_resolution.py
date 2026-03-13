from collections import Counter
import re

from book_store_assistant.subject_selection import select_subject

BNE_FICTION_CATEGORY_PATTERN = re.compile(r"\b821(?:\.[0-9]+)*(?:\([^)]+\))?-31(?:\"[0-9]+\")?\b")


def _derive_controlled_subject_candidates(candidates: list[str]) -> list[str]:
    derived_candidates: list[str] = []

    for candidate in candidates:
        if BNE_FICTION_CATEGORY_PATTERN.search(candidate):
            derived_candidates.append("FICCION")

    return derived_candidates


def _expand_candidates(candidate: str) -> list[str]:
    expanded = [candidate]

    for separator in ("/", ",", ";", ">", "&"):
        parts: list[str] = []
        for item in expanded:
            parts.extend(item.split(separator))
        expanded = parts

    return [item.strip() for item in expanded if item.strip()]


def _score_subject_matches(
    candidates: list[str],
    allowed_subject_rows: list[list[str]],
) -> Counter[str]:
    scores: Counter[str] = Counter()

    for candidate in candidates:
        exact_match = select_subject(candidate, allowed_subject_rows)
        if exact_match is not None:
            scores[exact_match] += 2

        for expanded_candidate in _expand_candidates(candidate):
            expanded_match = select_subject(expanded_candidate, allowed_subject_rows)
            if expanded_match is not None:
                scores[expanded_match] += 1

    return scores


def resolve_subject(candidates: list[str], allowed_subject_rows: list[list[str]]) -> str | None:
    scores = _score_subject_matches(
        [
            *candidates,
            *_derive_controlled_subject_candidates(candidates),
        ],
        allowed_subject_rows,
    )
    if scores:
        return scores.most_common(1)[0][0]

    return None
