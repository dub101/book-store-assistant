from book_store_assistant.publisher_identity.models import PublisherIdentityResult
from book_store_assistant.publisher_identity.service import (
    attach_publisher_identities,
    resolve_publisher_identities,
    resolve_publisher_identity,
)
from book_store_assistant.sources.models import SourceBookRecord
from book_store_assistant.sources.results import FetchResult


def test_resolve_publisher_identity_uses_editorial_field_when_available() -> None:
    fetch_result = FetchResult(
        isbn="9780306406157",
        record=SourceBookRecord(
            source_name="google_books",
            isbn="9780306406157",
            editorial="Planeta",
            field_sources={"editorial": "open_library"},
        ),
        errors=[],
    )

    result = resolve_publisher_identity(fetch_result)

    assert result == PublisherIdentityResult(
        isbn="9780306406157",
        publisher_name="Planeta",
        imprint_name="Planeta",
        publisher_group_key="planeta",
        source_name="open_library",
        source_field="editorial",
        confidence=0.95,
        resolution_method="editorial_field",
        evidence=["editorial:Planeta"],
    )


def test_resolve_publisher_identity_splits_catalog_style_editorial_into_imprint_and_group() -> None:
    fetch_result = FetchResult(
        isbn="9780306406157",
        record=SourceBookRecord(
            source_name="bne",
            isbn="9780306406157",
            editorial="Barcelona, Paidós",
            field_sources={"editorial": "bne"},
        ),
        errors=[],
    )

    result = resolve_publisher_identity(fetch_result)

    assert result == PublisherIdentityResult(
        isbn="9780306406157",
        publisher_name="Planeta",
        imprint_name="Paidós",
        publisher_group_key="planeta",
        source_name="bne",
        source_field="editorial",
        confidence=0.95,
        resolution_method="editorial_field",
        evidence=["editorial:Barcelona, Paidós"],
    )


def test_resolve_publisher_identity_normalizes_catalog_style_group_name() -> None:
    fetch_result = FetchResult(
        isbn="9780306406157",
        record=SourceBookRecord(
            source_name="bne",
            isbn="9780306406157",
            editorial="Barcelona, Planeta",
            field_sources={"editorial": "bne"},
        ),
        errors=[],
    )

    result = resolve_publisher_identity(fetch_result)

    assert result == PublisherIdentityResult(
        isbn="9780306406157",
        publisher_name="Planeta",
        imprint_name="Planeta",
        publisher_group_key="planeta",
        source_name="bne",
        source_field="editorial",
        confidence=0.95,
        resolution_method="editorial_field",
        evidence=["editorial:Barcelona, Planeta"],
    )


def test_resolve_publisher_identity_can_fall_back_to_source_url_domain() -> None:
    fetch_result = FetchResult(
        isbn="9780306406157",
        record=SourceBookRecord(
            source_name="publisher_page:planeta",
            isbn="9780306406157",
            source_url="https://www.planetadelibros.com/libro/ejemplo/123",
            field_sources={"source_url": "publisher_page:planeta"},
        ),
        errors=[],
    )

    result = resolve_publisher_identity(fetch_result)

    assert result.publisher_name == "Planeta"
    assert result.publisher_group_key == "planeta"
    assert result.source_name == "publisher_page:planeta"
    assert result.source_field == "source_url"
    assert result.resolution_method == "source_url_domain"


def test_resolve_publisher_identity_maps_new_supported_publisher_domains() -> None:
    fetch_result = FetchResult(
        isbn="9780306406157",
        record=SourceBookRecord(
            source_name="publisher_page:kalandraka",
            isbn="9780306406157",
            source_url="https://kalandraka.com/cuando-a-matias-le-entraron-ganas-castellano.html",
            field_sources={"source_url": "publisher_page:kalandraka"},
        ),
        errors=[],
    )

    result = resolve_publisher_identity(fetch_result)

    assert result.publisher_name == "Kalandraka"
    assert result.publisher_group_key == "kalandraka"
    assert result.source_name == "publisher_page:kalandraka"
    assert result.source_field == "source_url"
    assert result.resolution_method == "source_url_domain"


def test_attach_publisher_identities_adds_result_to_fetch_results() -> None:
    fetch_results = [
        FetchResult(
            isbn="9780306406157",
            record=SourceBookRecord(source_name="google_books", isbn="9780306406157"),
            errors=[],
        )
    ]
    publisher_identity_results = resolve_publisher_identities(fetch_results)

    attached_results = attach_publisher_identities(fetch_results, publisher_identity_results)

    assert attached_results[0].publisher_identity == PublisherIdentityResult(
        isbn="9780306406157"
    )
