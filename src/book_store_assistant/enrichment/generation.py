from book_store_assistant.enrichment.models import DescriptiveEvidence, GeneratedSynopsis
from book_store_assistant.resolution.synopsis_resolution import is_spanish_language
from book_store_assistant.synopsis import has_synopsis

MIN_EVIDENCE_CHARACTERS = 80
MIN_GENERATED_SYNOPSIS_CHARACTERS = 40
DESCRIPTIVE_EVIDENCE_TYPES = frozenset(
    {
        "source_synopsis",
        "source_page_structured_data",
        "source_page_meta_description",
        "source_page_body_description",
    }
)


def has_sufficient_evidence(evidence: list[DescriptiveEvidence]) -> bool:
    return any(len(item.text.strip()) >= MIN_EVIDENCE_CHARACTERS for item in evidence)


def validate_generated_synopsis(
    synopsis: GeneratedSynopsis,
    evidence: list[DescriptiveEvidence],
) -> list[str]:
    validation_flags = list(synopsis.validation_flags)

    if not has_synopsis(synopsis.text):
        validation_flags.append("empty_generated_synopsis")
        return validation_flags

    if not is_spanish_language(synopsis.language):
        validation_flags.append("non_spanish_generated_synopsis")

    if len(synopsis.text.strip()) < MIN_GENERATED_SYNOPSIS_CHARACTERS:
        validation_flags.append("generated_synopsis_too_short")

    if not synopsis.evidence_indexes:
        validation_flags.append("missing_evidence_references")

    has_descriptive_reference = False
    for evidence_index in synopsis.evidence_indexes:
        if evidence_index < 0 or evidence_index >= len(evidence):
            validation_flags.append("invalid_evidence_reference")
            break
        if evidence[evidence_index].evidence_type in DESCRIPTIVE_EVIDENCE_TYPES:
            has_descriptive_reference = True

    if synopsis.evidence_indexes and not has_descriptive_reference:
        validation_flags.append("insufficient_descriptive_evidence_reference")

    return validation_flags
