from book_store_assistant.enrichment.models import DescriptiveEvidence
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.synopsis import has_synopsis

SOURCE_SYNOPSIS_EVIDENCE = "source_synopsis"


def collect_descriptive_evidence(record: SourceBookRecord) -> list[DescriptiveEvidence]:
    evidence: list[DescriptiveEvidence] = []
    synopsis = record.synopsis

    if has_synopsis(synopsis):
        assert synopsis is not None

        evidence_source = record.field_sources.get("synopsis", record.source_name)
        quality_flags = ["trusted_source_synopsis"]

        if record.language == "es":
            quality_flags.append("spanish_language")
        elif record.language:
            quality_flags.append("non_spanish_language")
        else:
            quality_flags.append("unknown_language")

        evidence.append(
            DescriptiveEvidence(
                source_name=evidence_source,
                evidence_type=SOURCE_SYNOPSIS_EVIDENCE,
                text=synopsis.strip(),
                language=record.language,
                quality_flags=quality_flags,
            )
        )

    return evidence
