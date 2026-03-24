from pathlib import Path

import book_store_assistant.config as config_module
from book_store_assistant.config import AIProvider, AppConfig


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
                "publisher_page_lookup_enabled = false",
                "retailer_page_lookup_enabled = false",
                "publisher_page_timeout_seconds = 2.5",
                "retailer_page_timeout_seconds = 1.5",
                "publisher_page_max_retries = 4",
                "retailer_page_max_retries = 1",
                "publisher_page_backoff_seconds = 0.75",
                "retailer_page_backoff_seconds = 0.1",
                "publisher_page_max_profiles_per_record = 5",
                "publisher_page_max_search_attempts_per_record = 9",
                "publisher_page_max_fetch_attempts_per_record = 4",
                "retailer_page_max_search_attempts_per_record = 6",
                "retailer_page_max_fetch_attempts_per_record = 3",
                "request_timeout_seconds = 6.0",
                "source_request_pause_seconds = 0.25",
                "open_library_batch_size = 12",
                "bne_lookup_enabled = false",
                'bne_sru_base_url = "https://catalogo.bne.test/view/sru/34BNE_INST"',
                "web_search_fallback_enabled = false",
                "web_search_timeout_seconds = 4.5",
                "web_search_max_retries = 2",
                "web_search_max_search_attempts_per_record = 5",
                "web_search_max_fetch_attempts_per_record = 4",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BSA_CONFIG_FILE", str(config_file))
    config_module._load_config_file.cache_clear()

    config = AppConfig()

    assert config.input_dir == Path("custom/input")
    assert config.output_dir == Path("custom/output")
    assert not hasattr(config, "intermediate_dir")
    assert not hasattr(config, "source_cache_dir")
    assert not hasattr(config, "publisher_page_cache_dir")
    assert not hasattr(config, "retailer_page_cache_dir")
    assert not hasattr(config, "publisher_page_cache_enabled")
    assert not hasattr(config, "retailer_page_cache_enabled")
    assert config.publisher_page_lookup_enabled is False
    assert config.retailer_page_lookup_enabled is False
    assert config.publisher_page_timeout_seconds == 2.5
    assert config.retailer_page_timeout_seconds == 1.5
    assert config.publisher_page_max_retries == 4
    assert config.retailer_page_max_retries == 1
    assert config.publisher_page_backoff_seconds == 0.75
    assert config.retailer_page_backoff_seconds == 0.1
    assert config.publisher_page_max_profiles_per_record == 5
    assert config.publisher_page_max_search_attempts_per_record == 9
    assert config.publisher_page_max_fetch_attempts_per_record == 4
    assert config.retailer_page_max_search_attempts_per_record == 6
    assert config.retailer_page_max_fetch_attempts_per_record == 3
    assert config.request_timeout_seconds == 6.0
    assert config.source_request_pause_seconds == 0.25
    assert config.open_library_batch_size == 12
    assert config.bne_lookup_enabled is False
    assert config.bne_sru_base_url == "https://catalogo.bne.test/view/sru/34BNE_INST"
    assert config.web_search_fallback_enabled is False
    assert config.web_search_timeout_seconds == 4.5
    assert config.web_search_max_retries == 2
    assert config.web_search_max_search_attempts_per_record == 5
    assert config.web_search_max_fetch_attempts_per_record == 4


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
    assert not hasattr(config, "publisher_page_cache_dir")
    assert not hasattr(config, "retailer_page_cache_dir")
    assert not hasattr(config, "publisher_page_cache_enabled")
    assert not hasattr(config, "retailer_page_cache_enabled")
    assert config.publisher_page_lookup_enabled is True
    assert config.retailer_page_lookup_enabled is True
    assert config.publisher_page_timeout_seconds == 6.0
    assert config.retailer_page_timeout_seconds == 4.0
    assert config.publisher_page_max_retries == 0
    assert config.retailer_page_max_retries == 0
    assert config.publisher_page_backoff_seconds == 0.5
    assert config.retailer_page_backoff_seconds == 0.25
    assert config.publisher_page_max_profiles_per_record == 3
    assert config.publisher_page_max_search_attempts_per_record == 8
    assert config.publisher_page_max_fetch_attempts_per_record == 4
    assert config.retailer_page_max_search_attempts_per_record == 6
    assert config.retailer_page_max_fetch_attempts_per_record == 3
    assert config.web_search_fallback_enabled is True
    assert config.web_search_timeout_seconds == 10.0
    assert config.web_search_max_retries == 1
    assert config.web_search_max_pages_per_record == 4
    assert config.web_search_max_search_attempts_per_record == 5
    assert config.web_search_max_fetch_attempts_per_record == 4
    assert config.ai_provider == AIProvider.OPENAI
    assert config.openai_api_base_url == "https://api.openai.com/v1"
    assert config.openai_model == "gpt-4o-mini"


def test_app_config_reads_runtime_overrides_from_environment(monkeypatch) -> None:
    monkeypatch.delenv("BSA_CONFIG_FILE", raising=False)
    config_module._load_config_file.cache_clear()
    monkeypatch.setenv("BSA_GOOGLE_BOOKS_MAX_RETRIES", "4")
    monkeypatch.setenv("BSA_GOOGLE_BOOKS_BACKOFF_SECONDS", "0.25")
    monkeypatch.setenv("BSA_BNE_LOOKUP_ENABLED", "0")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_LOOKUP_ENABLED", "0")
    monkeypatch.setenv("BSA_RETAILER_PAGE_LOOKUP_ENABLED", "0")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_TIMEOUT_SECONDS", "2.0")
    monkeypatch.setenv("BSA_RETAILER_PAGE_TIMEOUT_SECONDS", "1.25")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_MAX_RETRIES", "5")
    monkeypatch.setenv("BSA_RETAILER_PAGE_MAX_RETRIES", "1")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_BACKOFF_SECONDS", "0.2")
    monkeypatch.setenv("BSA_RETAILER_PAGE_BACKOFF_SECONDS", "0.1")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_MAX_PROFILES_PER_RECORD", "2")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_MAX_SEARCH_ATTEMPTS_PER_RECORD", "7")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_MAX_FETCH_ATTEMPTS_PER_RECORD", "4")
    monkeypatch.setenv("BSA_RETAILER_PAGE_MAX_SEARCH_ATTEMPTS_PER_RECORD", "3")
    monkeypatch.setenv("BSA_RETAILER_PAGE_MAX_FETCH_ATTEMPTS_PER_RECORD", "1")
    monkeypatch.setenv("BSA_REQUEST_TIMEOUT_SECONDS", "3.5")
    monkeypatch.setenv("BSA_WEB_SEARCH_FALLBACK_ENABLED", "0")
    monkeypatch.setenv("BSA_WEB_SEARCH_TIMEOUT_SECONDS", "5.5")
    monkeypatch.setenv("BSA_WEB_SEARCH_MAX_RETRIES", "3")
    monkeypatch.setenv("BSA_WEB_SEARCH_MAX_SEARCH_ATTEMPTS_PER_RECORD", "6")
    monkeypatch.setenv("BSA_WEB_SEARCH_MAX_FETCH_ATTEMPTS_PER_RECORD", "4")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")

    config = AppConfig()

    assert config.google_books_max_retries == 4
    assert config.google_books_backoff_seconds == 0.25
    assert config.bne_lookup_enabled is False
    assert not hasattr(config, "publisher_page_cache_enabled")
    assert not hasattr(config, "retailer_page_cache_enabled")
    assert config.publisher_page_lookup_enabled is False
    assert config.retailer_page_lookup_enabled is False
    assert config.publisher_page_timeout_seconds == 2.0
    assert config.retailer_page_timeout_seconds == 1.25
    assert config.publisher_page_max_retries == 5
    assert config.retailer_page_max_retries == 1
    assert config.publisher_page_backoff_seconds == 0.2
    assert config.retailer_page_backoff_seconds == 0.1
    assert config.publisher_page_max_profiles_per_record == 2
    assert config.publisher_page_max_search_attempts_per_record == 7
    assert config.publisher_page_max_fetch_attempts_per_record == 4
    assert config.retailer_page_max_search_attempts_per_record == 3
    assert config.retailer_page_max_fetch_attempts_per_record == 1
    assert config.request_timeout_seconds == 3.5
    assert config.web_search_fallback_enabled is False
    assert config.web_search_timeout_seconds == 5.5
    assert config.web_search_max_retries == 3
    assert config.web_search_max_search_attempts_per_record == 6
    assert config.web_search_max_fetch_attempts_per_record == 4
    assert config.openai_model == "gpt-4.1-mini"


def test_app_config_falls_back_when_environment_overrides_are_invalid(monkeypatch) -> None:
    monkeypatch.delenv("BSA_CONFIG_FILE", raising=False)
    config_module._load_config_file.cache_clear()
    monkeypatch.setenv("BSA_GOOGLE_BOOKS_MAX_RETRIES", "not-an-int")
    monkeypatch.setenv("BSA_GOOGLE_BOOKS_BACKOFF_SECONDS", "not-a-float")
    monkeypatch.setenv("BSA_BNE_LOOKUP_ENABLED", "not-a-bool")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_LOOKUP_ENABLED", "not-a-bool")
    monkeypatch.setenv("BSA_RETAILER_PAGE_LOOKUP_ENABLED", "not-a-bool")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_TIMEOUT_SECONDS", "still-not-a-float")
    monkeypatch.setenv("BSA_RETAILER_PAGE_TIMEOUT_SECONDS", "still-not-a-float")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_MAX_RETRIES", "still-not-an-int")
    monkeypatch.setenv("BSA_RETAILER_PAGE_MAX_RETRIES", "still-not-an-int")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_BACKOFF_SECONDS", "still-not-a-float")
    monkeypatch.setenv("BSA_RETAILER_PAGE_BACKOFF_SECONDS", "still-not-a-float")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_MAX_PROFILES_PER_RECORD", "still-not-an-int")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_MAX_SEARCH_ATTEMPTS_PER_RECORD", "still-not-an-int")
    monkeypatch.setenv("BSA_PUBLISHER_PAGE_MAX_FETCH_ATTEMPTS_PER_RECORD", "still-not-an-int")
    monkeypatch.setenv("BSA_RETAILER_PAGE_MAX_SEARCH_ATTEMPTS_PER_RECORD", "still-not-an-int")
    monkeypatch.setenv("BSA_RETAILER_PAGE_MAX_FETCH_ATTEMPTS_PER_RECORD", "still-not-an-int")
    monkeypatch.setenv("BSA_REQUEST_TIMEOUT_SECONDS", "still-not-a-float")
    monkeypatch.setenv("BSA_WEB_SEARCH_FALLBACK_ENABLED", "not-a-bool")
    monkeypatch.setenv("BSA_WEB_SEARCH_TIMEOUT_SECONDS", "still-not-a-float")
    monkeypatch.setenv("BSA_WEB_SEARCH_MAX_RETRIES", "still-not-an-int")
    monkeypatch.setenv("BSA_WEB_SEARCH_MAX_SEARCH_ATTEMPTS_PER_RECORD", "still-not-an-int")
    monkeypatch.setenv("BSA_WEB_SEARCH_MAX_FETCH_ATTEMPTS_PER_RECORD", "still-not-an-int")

    config = AppConfig()

    assert config.google_books_max_retries == 2
    assert config.google_books_backoff_seconds == 1.0
    assert config.bne_lookup_enabled is True
    assert not hasattr(config, "publisher_page_cache_enabled")
    assert not hasattr(config, "retailer_page_cache_enabled")
    assert config.publisher_page_lookup_enabled is True
    assert config.retailer_page_lookup_enabled is True
    assert config.publisher_page_timeout_seconds == 6.0
    assert config.retailer_page_timeout_seconds == 4.0
    assert config.publisher_page_max_retries == 0
    assert config.retailer_page_max_retries == 0
    assert config.publisher_page_backoff_seconds == 0.5
    assert config.retailer_page_backoff_seconds == 0.25
    assert config.publisher_page_max_profiles_per_record == 3
    assert config.publisher_page_max_search_attempts_per_record == 8
    assert config.publisher_page_max_fetch_attempts_per_record == 4
    assert config.retailer_page_max_search_attempts_per_record == 6
    assert config.retailer_page_max_fetch_attempts_per_record == 3
    assert config.request_timeout_seconds == 10.0
    assert config.web_search_fallback_enabled is True
    assert config.web_search_timeout_seconds == 10.0
    assert config.web_search_max_retries == 1
    assert config.web_search_max_pages_per_record == 4
    assert config.web_search_max_search_attempts_per_record == 5
    assert config.web_search_max_fetch_attempts_per_record == 4
