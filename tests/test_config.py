from pathlib import Path

import book_store_assistant.config as config_module
from book_store_assistant.config import AIProvider, AppConfig, ExecutionMode


def test_app_config_reads_non_secret_settings_from_config_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("BSA_PUBLISHER_PAGE_TIMEOUT_SECONDS", raising=False)
    config_file = tmp_path / "bsa.toml"
    config_file.write_text(
        "\n".join(
            [
                'input_dir = "custom/input"',
                'output_dir = "custom/output"',
                'intermediate_dir = "custom/intermediate"',
                'source_cache_dir = "custom/cache/fetch"',
                'publisher_page_cache_dir = "custom/cache/publisher_pages"',
                "publisher_page_cache_enabled = false",
                "publisher_page_negative_cache_ttl_seconds = 1800",
                "publisher_page_timeout_seconds = 2.5",
                "publisher_page_max_retries = 4",
                "publisher_page_backoff_seconds = 0.75",
                "request_timeout_seconds = 6.0",
                "source_request_pause_seconds = 0.25",
                "open_library_batch_size = 12",
                "bne_lookup_enabled = false",
                'bne_sru_base_url = "https://catalogo.bne.test/view/sru/34BNE_INST"',
                'execution_mode = "ai-enriched"',
                "llm_subject_mapping_enabled = false",
                "llm_subject_mapping_min_confidence = 0.9",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BSA_CONFIG_FILE", str(config_file))
    config_module._load_config_file.cache_clear()

    config = AppConfig()

    assert config.input_dir == Path("custom/input")
    assert config.output_dir == Path("custom/output")
    assert config.intermediate_dir == Path("custom/intermediate")
    assert config.source_cache_dir == Path("custom/cache/fetch")
    assert config.publisher_page_cache_dir == Path("custom/cache/publisher_pages")
    assert config.publisher_page_cache_enabled is False
    assert config.publisher_page_negative_cache_ttl_seconds == 1800
    assert config.publisher_page_timeout_seconds == 2.5
    assert config.publisher_page_max_retries == 4
    assert config.publisher_page_backoff_seconds == 0.75
    assert config.request_timeout_seconds == 6.0
    assert config.source_request_pause_seconds == 0.25
    assert config.open_library_batch_size == 12
    assert config.bne_lookup_enabled is False
    assert config.bne_sru_base_url == "https://catalogo.bne.test/view/sru/34BNE_INST"
    assert config.execution_mode == ExecutionMode.AI_ENRICHED
    assert config.llm_subject_mapping_enabled is False
    assert config.llm_subject_mapping_min_confidence == 0.9


def test_app_config_uses_project_data_directories(monkeypatch) -> None:
    monkeypatch.delenv("BSA_CONFIG_FILE", raising=False)
    monkeypatch.delenv("BSA_PUBLISHER_PAGE_TIMEOUT_SECONDS", raising=False)
    config_module._load_config_file.cache_clear()
    config = AppConfig()

    assert config.input_dir == Path("data/input")
    assert config.output_dir == Path("data/output")
    assert config.google_books_api_base_url == "https://www.googleapis.com/books/v1/volumes"
    assert config.google_books_max_retries == 2
    assert config.google_books_backoff_seconds == 1.0
    assert config.bne_lookup_enabled is True
    assert config.bne_sru_base_url == "https://catalogo.bne.es/view/sru/34BNE_INST"
    assert config.open_library_api_base_url == "https://openlibrary.org/api/books"
    assert config.publisher_page_cache_dir == Path("data/cache/publisher_pages")
    assert config.publisher_page_cache_enabled is True
    assert config.publisher_page_negative_cache_ttl_seconds == 21600.0
    assert config.publisher_page_timeout_seconds == 3.0
    assert config.publisher_page_max_retries == 2
    assert config.publisher_page_backoff_seconds == 0.5
    assert config.execution_mode == ExecutionMode.RULES_ONLY
    assert config.ai_provider == AIProvider.OPENAI
    assert config.openai_api_base_url == "https://api.openai.com/v1"
    assert config.openai_model == "gpt-4o-mini"


def test_app_config_reads_runtime_overrides_from_environment(monkeypatch) -> None:
    monkeypatch.delenv("BSA_CONFIG_FILE", raising=False)
    config_module._load_config_file.cache_clear()
    monkeypatch.setenv("BSA_GOOGLE_BOOKS_MAX_RETRIES", "4")
    monkeypatch.setenv("BSA_GOOGLE_BOOKS_BACKOFF_SECONDS", "0.25")
    monkeypatch.setenv("BSA_BNE_LOOKUP_ENABLED", "0")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_CACHE_ENABLED", "0")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_NEGATIVE_CACHE_TTL_SECONDS", "900")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_TIMEOUT_SECONDS", "2.0")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_MAX_RETRIES", "5")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_BACKOFF_SECONDS", "0.2")
    monkeypatch.setenv("BSA_REQUEST_TIMEOUT_SECONDS", "3.5")
    monkeypatch.setenv("BSA_EXECUTION_MODE", "ai-enriched")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")

    config = AppConfig()

    assert config.google_books_max_retries == 4
    assert config.google_books_backoff_seconds == 0.25
    assert config.bne_lookup_enabled is False
    assert config.publisher_page_cache_enabled is False
    assert config.publisher_page_negative_cache_ttl_seconds == 900
    assert config.publisher_page_timeout_seconds == 2.0
    assert config.publisher_page_max_retries == 5
    assert config.publisher_page_backoff_seconds == 0.2
    assert config.request_timeout_seconds == 3.5
    assert config.execution_mode == ExecutionMode.AI_ENRICHED
    assert config.openai_model == "gpt-4.1-mini"


def test_app_config_falls_back_when_environment_overrides_are_invalid(monkeypatch) -> None:
    monkeypatch.delenv("BSA_CONFIG_FILE", raising=False)
    config_module._load_config_file.cache_clear()
    monkeypatch.setenv("BSA_GOOGLE_BOOKS_MAX_RETRIES", "not-an-int")
    monkeypatch.setenv("BSA_GOOGLE_BOOKS_BACKOFF_SECONDS", "not-a-float")
    monkeypatch.setenv("BSA_BNE_LOOKUP_ENABLED", "not-a-bool")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_CACHE_ENABLED", "not-a-bool")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_NEGATIVE_CACHE_TTL_SECONDS", "still-not-a-float")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_TIMEOUT_SECONDS", "still-not-a-float")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_MAX_RETRIES", "still-not-an-int")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_BACKOFF_SECONDS", "still-not-a-float")
    monkeypatch.setenv("BSA_REQUEST_TIMEOUT_SECONDS", "still-not-a-float")
    monkeypatch.setenv("BSA_EXECUTION_MODE", "not-a-real-mode")

    config = AppConfig()

    assert config.google_books_max_retries == 2
    assert config.google_books_backoff_seconds == 1.0
    assert config.bne_lookup_enabled is True
    assert config.publisher_page_cache_enabled is True
    assert config.publisher_page_negative_cache_ttl_seconds == 21600.0
    assert config.publisher_page_timeout_seconds == 3.0
    assert config.publisher_page_max_retries == 2
    assert config.publisher_page_backoff_seconds == 0.5
    assert config.request_timeout_seconds == 10.0
    assert config.execution_mode == ExecutionMode.RULES_ONLY
